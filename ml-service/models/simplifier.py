import spacy
from models.synonym_lookup import SynonymLookup
from models.text_processor import TextProcessor
from models.datamuse_synonyms import DatamuseSynonymFinder
from models.groq_validator import GroqValidator
import os

from nltk.corpus import wordnet as wn
from wordfreq import zipf_frequency

# Try to import Groq, but don't fail if not available
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("Warning: Groq not installed. Advanced simplification will be limited.")

nlp = spacy.load('en_core_web_sm')

# Zipf frequency thresholds for grade estimation
# Higher zipf = more common word. Scale is roughly 0-7.
# 7 = "the", 6 = "is", 5 = "know", 4 = "allow", 3 = "magnificent", 2 = "trepidation"
GRADE_ZIPF_THRESHOLDS = {
    3: 5.5,   # Grade 3: only very common words (zipf >= 5.5)
    4: 5.2,
    5: 4.9,
    6: 4.6,
    7: 4.3,
    8: 4.0,
    9: 3.7,
    10: 3.4,
    11: 3.1,
    12: 2.8,
}


class TextSimplifier:
    """Simplify text to target grade level using dynamic NLP-based word replacement."""

    def __init__(self):
        self.synonym_lookup = SynonymLookup()
        self.text_processor = TextProcessor()
        self.datamuse_finder = DatamuseSynonymFinder()
        self.groq_validator = GroqValidator()

        # Initialize Groq client if available
        self.groq_client = None
        if GROQ_AVAILABLE and os.getenv('GROQ_API_KEY'):
            self.groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

        # Grade-specific constraints for sentence length
        self.grade_constraints = {
            3: {'max_words': 10, 'max_syllables': 2},
            4: {'max_words': 12, 'max_syllables': 2},
            5: {'max_words': 15, 'max_syllables': 2},
            6: {'max_words': 18, 'max_syllables': 3},
            7: {'max_words': 20, 'max_syllables': 3},
            8: {'max_words': 20, 'max_syllables': 3},
            9: {'max_words': 22, 'max_syllables': 3},
            10: {'max_words': 25, 'max_syllables': 4},
            11: {'max_words': 28, 'max_syllables': 4},
            12: {'max_words': 30, 'max_syllables': 4}
        }

        # Cache for synonym lookups (word -> best simple synonym)
        self._synonym_cache = {}

    # ------------------------------------------------------------------ #
    #  Main entry point
    # ------------------------------------------------------------------ #

    def simplify_to_grade(self, text, target_grade):
        """
        Main simplification function with hybrid synonym finding + Groq validation.

        Returns:
            {
                'simplified_text': str,
                'changes': [array of change objects],
                'original_text': str,
                'validation': {valid, issues, suggestions}
            }
        """
        changes = []
        current_text = text

        # Step 1: Replace difficult words with simpler synonyms
        # Uses: curated map -> WordNet+Lesk -> Datamuse API fallback
        current_text, word_changes = self._replace_difficult_words(current_text, target_grade)
        changes.extend(word_changes)

        # Step 2: Split long sentences
        current_text, split_changes = self._split_long_sentences(current_text, target_grade)
        changes.extend(split_changes)

        # Step 3: Groq validation (sanity check on rule-based changes)
        validation = self.groq_validator.validate_changes(
            text, current_text, changes
        )

        # Step 4: If validation found issues, let Groq fix them
        if not validation['valid'] and validation['issues']:
            print(f"Validation found issues: {validation['issues']}")
            fixed_text = self.groq_validator.fix_with_groq(
                current_text, target_grade, validation['issues']
            )
            if fixed_text != current_text:
                changes.append({
                    'type': 'groq_correction',
                    'original': current_text,
                    'simplified': fixed_text,
                    'position': 0,
                    'reason': f"AI corrected issues: {', '.join(validation['issues'])}",
                    'id': len(changes)
                })
                current_text = fixed_text

        # Step 5: Groq fallback for remaining complexity
        if self._needs_groq_help(current_text, target_grade):
            current_text, api_changes = self.groq_fallback(current_text, target_grade)
            changes.extend(api_changes)

        return {
            'simplified_text': current_text,
            'changes': changes,
            'original_text': text,
            'validation': validation
        }

    # ------------------------------------------------------------------ #
    #  Word difficulty assessment (data-driven)
    # ------------------------------------------------------------------ #

    def _is_word_too_hard(self, word, target_grade):
        """
        Determine if a word is too difficult for the target grade.
        Uses: zipf frequency, Dale-Chall list, syllable count.
        """
        word_lower = word.lower()

        # Dale-Chall easy words are fine for any grade
        if self.synonym_lookup.is_easy_word(word_lower):
            return False

        # Get the zipf frequency (higher = more common)
        freq = zipf_frequency(word_lower, 'en')

        # Get the threshold for this grade
        threshold = GRADE_ZIPF_THRESHOLDS.get(target_grade, 3.0)

        # Word is too hard if its frequency is below the grade threshold
        if freq < threshold:
            return True

        # Also flag words with many syllables even if somewhat frequent
        syllables = self.text_processor.count_syllables(word_lower)
        if syllables >= 4 and freq < threshold + 0.5:
            return True

        return False

    # ------------------------------------------------------------------ #
    #  Dynamic synonym finding via WordNet + frequency ranking
    # ------------------------------------------------------------------ #

    def _find_simpler_synonym(self, word, token, target_grade):
        """
        Find the simplest synonym for a word using WordNet + context disambiguation.

        Strategy:
        1. Check curated simplification_map first (highest quality)
        2. Use simplified Lesk algorithm to pick the best WordNet sense
        3. Only allow SINGLE-WORD replacements from WordNet
        4. Require candidate to be both more frequent AND fewer/equal syllables
        5. Pick the highest-frequency candidate from the best sense
        """
        word_lower = word.lower()
        lemma = token.lemma_.lower()
        cache_key = f"{lemma}_{target_grade}"

        if cache_key in self._synonym_cache:
            return self._synonym_cache[cache_key]

        original_freq = zipf_frequency(word_lower, 'en')
        original_syllables = self.text_processor.count_syllables(word_lower)

        # Check curated simplification_map first (highest quality, allows multi-word)
        curated = self.synonym_lookup.simplification_map.get(word_lower) or \
                  self.synonym_lookup.simplification_map.get(lemma)

        candidates = []

        if curated:
            simple = curated['simple']
            freq = zipf_frequency(simple.split()[0], 'en')
            candidates.append((simple, freq, self.text_processor.count_syllables(simple)))

        # Use simplified Lesk to pick the best synset
        best_synset, lesk_score = self._disambiguate_sense(token)
        lesk_identified_sense = False

        if best_synset and lesk_score > 0:
            # High-confidence: use only the Lesk-selected synset
            before_count = len(candidates)
            self._collect_synset_candidates(
                best_synset, word_lower, lemma, original_freq,
                original_syllables, candidates, set()
            )
            lesk_identified_sense = True

        # Fall back to first synset (most common sense) ONLY when:
        # - Lesk didn't identify a specific sense, AND
        # - Word isn't a highly polysemous verb (too risky without context)
        if len(candidates) <= (1 if curated else 0) and not lesk_identified_sense:
            seen = set()
            for lookup_word in set([word_lower, lemma]):
                synsets = wn.synsets(lookup_word)
                matching = [s for s in synsets if self._pos_matches(token.pos_, s.pos())]
                if matching:
                    if token.pos_ == 'VERB' and len(matching) >= 4:
                        continue
                    self._collect_synset_candidates(
                        matching[0], word_lower, lemma, original_freq,
                        original_syllables, candidates, seen
                    )

        # Datamuse API fallback (only if WordNet found nothing)
        if not candidates:
            datamuse_result = self.datamuse_finder.get_simpler_synonym(lemma)
            if datamuse_result:
                dm_freq = zipf_frequency(datamuse_result, 'en')
                dm_syl = self.text_processor.count_syllables(datamuse_result)
                if dm_freq > original_freq and dm_syl <= original_syllables:
                    candidates.append((datamuse_result, dm_freq, dm_syl))

        if not candidates:
            self._synonym_cache[cache_key] = None
            return None

        # Rank: prefer highest frequency, then fewest syllables
        candidates.sort(key=lambda c: (-c[1], c[2]))

        best = candidates[0][0]
        self._synonym_cache[cache_key] = best
        return best

    def _disambiguate_sense(self, token):
        """
        Simplified Lesk algorithm: pick the WordNet synset whose definition
        has the most overlap with the surrounding sentence context.

        Returns:
            (best_synset, overlap_score) - score of 0 means no context match (ambiguous)
        """
        word_lower = token.lemma_.lower()
        synsets = wn.synsets(word_lower)
        matching = [s for s in synsets if self._pos_matches(token.pos_, s.pos())]

        if not matching:
            return None, 0
        if len(matching) == 1:
            return matching[0], 1

        # Build context from surrounding tokens (nouns, verbs, adjectives)
        context_words = set()
        sent = token.sent
        for t in sent:
            if t.i != token.i and t.pos_ in ('NOUN', 'VERB', 'ADJ') and t.is_alpha:
                context_words.add(t.lemma_.lower())

        best_synset = None
        best_overlap = -1

        for synset in matching[:5]:
            # Words from the definition + examples
            definition_words = set(synset.definition().lower().split())
            for example in synset.examples():
                definition_words.update(example.lower().split())
            # Also add hypernym definitions for richer context
            for hypernym in synset.hypernyms():
                definition_words.update(hypernym.definition().lower().split())

            overlap = len(context_words & definition_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_synset = synset

        return best_synset, best_overlap

    def _collect_synset_candidates(self, synset, word_lower, lemma,
                                    original_freq, original_syllables,
                                    candidates, seen):
        """Extract valid simpler synonyms from a single synset."""
        for wn_lemma in synset.lemmas():
            candidate = wn_lemma.name().replace('_', ' ').lower()

            if candidate == word_lower or candidate == lemma:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)

            # ONLY single-word replacements from WordNet, min 2 chars
            if ' ' in candidate or len(candidate) < 2:
                continue

            # Sense validation for verbs: the candidate's common meaning must
            # align with this synset. Reject if this synset is only a rare sense
            # of the candidate (e.g., "dig" meaning "understand" is rare).
            # Nouns/adjectives are safer - use broader tolerance.
            cand_synsets = wn.synsets(candidate, pos=synset.pos())
            if cand_synsets:
                max_senses = 4 if synset.pos() == wn.VERB else 6
                if synset not in cand_synsets[:max_senses]:
                    continue

            cand_freq = zipf_frequency(candidate, 'en')
            cand_syllables = self.text_processor.count_syllables(candidate)

            # Must be BOTH more frequent AND fewer/equal syllables
            if cand_freq > original_freq and cand_syllables <= original_syllables:
                candidates.append((candidate, cand_freq, cand_syllables))

    def _pos_matches(self, spacy_pos, wordnet_pos):
        """Map spaCy POS to WordNet POS for filtering."""
        mapping = {
            'NOUN': wn.NOUN,
            'VERB': wn.VERB,
            'ADJ': wn.ADJ,
            'ADV': wn.ADV,
        }
        return mapping.get(spacy_pos) == wordnet_pos

    # ------------------------------------------------------------------ #
    #  Inflection handling
    # ------------------------------------------------------------------ #

    IRREGULAR_VERBS = {
        'keep': {'VBD': 'kept', 'VBN': 'kept', 'VBG': 'keeping', 'VBZ': 'keeps'},
        'get': {'VBD': 'got', 'VBN': 'gotten', 'VBG': 'getting', 'VBZ': 'gets'},
        'give': {'VBD': 'gave', 'VBN': 'given', 'VBG': 'giving', 'VBZ': 'gives'},
        'show': {'VBD': 'showed', 'VBN': 'shown', 'VBG': 'showing', 'VBZ': 'shows'},
        'find': {'VBD': 'found', 'VBN': 'found', 'VBG': 'finding', 'VBZ': 'finds'},
        'make': {'VBD': 'made', 'VBN': 'made', 'VBG': 'making', 'VBZ': 'makes'},
        'take': {'VBD': 'took', 'VBN': 'taken', 'VBG': 'taking', 'VBZ': 'takes'},
        'see': {'VBD': 'saw', 'VBN': 'seen', 'VBG': 'seeing', 'VBZ': 'sees'},
        'come': {'VBD': 'came', 'VBN': 'come', 'VBG': 'coming', 'VBZ': 'comes'},
        'tell': {'VBD': 'told', 'VBN': 'told', 'VBG': 'telling', 'VBZ': 'tells'},
        'run': {'VBD': 'ran', 'VBN': 'run', 'VBG': 'running', 'VBZ': 'runs'},
        'build': {'VBD': 'built', 'VBN': 'built', 'VBG': 'building', 'VBZ': 'builds'},
        'buy': {'VBD': 'bought', 'VBN': 'bought', 'VBG': 'buying', 'VBZ': 'buys'},
        'send': {'VBD': 'sent', 'VBN': 'sent', 'VBG': 'sending', 'VBZ': 'sends'},
        'think': {'VBD': 'thought', 'VBN': 'thought', 'VBG': 'thinking', 'VBZ': 'thinks'},
        'know': {'VBD': 'knew', 'VBN': 'known', 'VBG': 'knowing', 'VBZ': 'knows'},
        'have': {'VBD': 'had', 'VBN': 'had', 'VBG': 'having', 'VBZ': 'has'},
        'do': {'VBD': 'did', 'VBN': 'done', 'VBG': 'doing', 'VBZ': 'does'},
        'go': {'VBD': 'went', 'VBN': 'gone', 'VBG': 'going', 'VBZ': 'goes'},
        'say': {'VBD': 'said', 'VBN': 'said', 'VBG': 'saying', 'VBZ': 'says'},
        'write': {'VBD': 'wrote', 'VBN': 'written', 'VBG': 'writing', 'VBZ': 'writes'},
        'read': {'VBD': 'read', 'VBN': 'read', 'VBG': 'reading', 'VBZ': 'reads'},
        'put': {'VBD': 'put', 'VBN': 'put', 'VBG': 'putting', 'VBZ': 'puts'},
        'set': {'VBD': 'set', 'VBN': 'set', 'VBG': 'setting', 'VBZ': 'sets'},
        'cut': {'VBD': 'cut', 'VBN': 'cut', 'VBG': 'cutting', 'VBZ': 'cuts'},
        'hold': {'VBD': 'held', 'VBN': 'held', 'VBG': 'holding', 'VBZ': 'holds'},
        'grow': {'VBD': 'grew', 'VBN': 'grown', 'VBG': 'growing', 'VBZ': 'grows'},
        'lead': {'VBD': 'led', 'VBN': 'led', 'VBG': 'leading', 'VBZ': 'leads'},
        'stand': {'VBD': 'stood', 'VBN': 'stood', 'VBG': 'standing', 'VBZ': 'stands'},
        'lose': {'VBD': 'lost', 'VBN': 'lost', 'VBG': 'losing', 'VBZ': 'loses'},
        'pay': {'VBD': 'paid', 'VBN': 'paid', 'VBG': 'paying', 'VBZ': 'pays'},
        'meet': {'VBD': 'met', 'VBN': 'met', 'VBG': 'meeting', 'VBZ': 'meets'},
        'feel': {'VBD': 'felt', 'VBN': 'felt', 'VBG': 'feeling', 'VBZ': 'feels'},
        'leave': {'VBD': 'left', 'VBN': 'left', 'VBG': 'leaving', 'VBZ': 'leaves'},
        'begin': {'VBD': 'began', 'VBN': 'begun', 'VBG': 'beginning', 'VBZ': 'begins'},
        'break': {'VBD': 'broke', 'VBN': 'broken', 'VBG': 'breaking', 'VBZ': 'breaks'},
        'bring': {'VBD': 'brought', 'VBN': 'brought', 'VBG': 'bringing', 'VBZ': 'brings'},
        'choose': {'VBD': 'chose', 'VBN': 'chosen', 'VBG': 'choosing', 'VBZ': 'chooses'},
        'draw': {'VBD': 'drew', 'VBN': 'drawn', 'VBG': 'drawing', 'VBZ': 'draws'},
        'drive': {'VBD': 'drove', 'VBN': 'driven', 'VBG': 'driving', 'VBZ': 'drives'},
        'fall': {'VBD': 'fell', 'VBN': 'fallen', 'VBG': 'falling', 'VBZ': 'falls'},
        'fly': {'VBD': 'flew', 'VBN': 'flown', 'VBG': 'flying', 'VBZ': 'flies'},
        'forget': {'VBD': 'forgot', 'VBN': 'forgotten', 'VBG': 'forgetting', 'VBZ': 'forgets'},
        'hide': {'VBD': 'hid', 'VBN': 'hidden', 'VBG': 'hiding', 'VBZ': 'hides'},
        'rise': {'VBD': 'rose', 'VBN': 'risen', 'VBG': 'rising', 'VBZ': 'rises'},
        'speak': {'VBD': 'spoke', 'VBN': 'spoken', 'VBG': 'speaking', 'VBZ': 'speaks'},
        'spend': {'VBD': 'spent', 'VBN': 'spent', 'VBG': 'spending', 'VBZ': 'spends'},
        'teach': {'VBD': 'taught', 'VBN': 'taught', 'VBG': 'teaching', 'VBZ': 'teaches'},
        'understand': {'VBD': 'understood', 'VBN': 'understood', 'VBG': 'understanding', 'VBZ': 'understands'},
        'win': {'VBD': 'won', 'VBN': 'won', 'VBG': 'winning', 'VBZ': 'wins'},
    }

    def _apply_inflection(self, simple_word, token):
        """Apply the original word's inflection (tense, plural, etc.) to the replacement."""
        tag = token.tag_
        morph = token.morph

        if token.pos_ == 'VERB':
            if ' ' in simple_word:
                # Inflect the first word of multi-word phrases (e.g., "take part" -> "took part")
                parts = simple_word.split()
                base = parts[0].lower()
                if base in self.IRREGULAR_VERBS and tag in self.IRREGULAR_VERBS[base]:
                    parts[0] = self.IRREGULAR_VERBS[base][tag]
                    return ' '.join(parts)
                return simple_word
            base = simple_word.lower()

            # Irregular verbs first
            if base in self.IRREGULAR_VERBS and tag in self.IRREGULAR_VERBS[base]:
                return self.IRREGULAR_VERBS[base][tag]

            # Regular inflection
            if tag in ('VBD', 'VBN'):
                if base.endswith('e'):
                    return base + 'd'
                elif base.endswith('y') and len(base) > 2 and base[-2] not in 'aeiou':
                    return base[:-1] + 'ied'
                elif self._should_double_final(base):
                    return base + base[-1] + 'ed'
                else:
                    return base + 'ed'
            elif tag == 'VBG':
                if base.endswith('e') and not base.endswith('ee'):
                    return base[:-1] + 'ing'
                elif self._should_double_final(base):
                    return base + base[-1] + 'ing'
                else:
                    return base + 'ing'
            elif tag == 'VBZ':
                if base.endswith(('s', 'sh', 'ch', 'x', 'z')):
                    return base + 'es'
                elif base.endswith('y') and len(base) > 2 and base[-2] not in 'aeiou':
                    return base[:-1] + 'ies'
                else:
                    return base + 's'

        elif token.pos_ == 'NOUN':
            if 'Number=Plur' in str(morph):
                last = simple_word.split()[-1] if ' ' in simple_word else simple_word
                if last.endswith(('s', 'sh', 'ch', 'x', 'z')):
                    plural = last + 'es'
                elif last.endswith('y') and len(last) > 2 and last[-2] not in 'aeiou':
                    plural = last[:-1] + 'ies'
                else:
                    plural = last + 's'
                if ' ' in simple_word:
                    words = simple_word.split()
                    words[-1] = plural
                    return ' '.join(words)
                return plural

        elif token.pos_ == 'ADJ':
            if tag == 'JJR':
                return simple_word + ('r' if simple_word.endswith('e') else 'er')
            elif tag == 'JJS':
                return simple_word + ('st' if simple_word.endswith('e') else 'est')

        return simple_word

    @staticmethod
    def _should_double_final(word):
        """Check if final consonant should be doubled (CVC rule for 1-syllable words)."""
        vowels = set('aeiou')
        if len(word) < 3:
            return False
        # Don't double w, x, y
        if word[-1] in 'wxy':
            return False
        # Must end in consonant-vowel-consonant
        if word[-1] not in vowels and word[-2] in vowels and word[-3] not in vowels:
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Word replacement (the core engine)
    # ------------------------------------------------------------------ #

    def _replace_difficult_words(self, text, target_grade):
        """
        Replace difficult words using:
        1. Difficulty check via zipf_frequency + Dale-Chall + syllables
        2. Synonym lookup via WordNet, ranked by frequency
        3. Inflection preservation via spaCy POS tags
        """
        changes = []
        doc = nlp(text)
        new_text = text
        offset = 0

        for token in doc:
            if not token.is_alpha or token.is_stop:
                continue

            # Skip proper nouns
            if token.pos_ == 'PROPN':
                continue

            word_lower = token.text.lower()

            # Skip short words
            if len(word_lower) < 4:
                continue

            # Skip words that are not too hard for target grade
            if not self._is_word_too_hard(word_lower, target_grade):
                continue

            # Skip verbs in phrasal constructions (verb + preposition)
            # e.g., "attest to", "refer to" - replacing the verb often breaks the phrase
            if token.pos_ == 'VERB':
                next_token = doc[token.i + 1] if token.i + 1 < len(doc) else None
                if next_token and next_token.dep_ == 'prep' and next_token.head == token:
                    continue

            # Find a simpler synonym dynamically
            base_synonym = self._find_simpler_synonym(word_lower, token, target_grade)
            if not base_synonym:
                continue

            # Check the synonym is actually simpler (guard rail)
            orig_freq = zipf_frequency(word_lower, 'en')
            syn_freq = zipf_frequency(base_synonym.split()[0], 'en')
            if syn_freq <= orig_freq:
                continue

            # Apply inflection to match original form
            simple_word = self._apply_inflection(base_synonym, token)

            # Preserve capitalization
            if token.text[0].isupper():
                simple_word = simple_word[0].upper() + simple_word[1:]
            if token.text.isupper():
                simple_word = simple_word.upper()

            # Replace in text
            start = token.idx + offset
            end = start + len(token.text)
            new_text = new_text[:start] + simple_word + new_text[end:]
            offset += len(simple_word) - len(token.text)

            orig_zipf = zipf_frequency(word_lower, 'en')
            syn_zipf = zipf_frequency(base_synonym, 'en')
            syllables_before = self.text_processor.count_syllables(word_lower)
            syllables_after = self.text_processor.count_syllables(base_synonym)

            changes.append({
                'type': 'word_replacement',
                'original': token.text,
                'simplified': simple_word,
                'position': token.idx,
                'reason': f"'{token.text}' (freq {orig_zipf:.1f}, {syllables_before} syl) -> '{simple_word}' (freq {syn_zipf:.1f}, {syllables_after} syl). More common word for Grade {target_grade}.",
                'id': len(changes)
            })

        return new_text, changes

    # ------------------------------------------------------------------ #
    #  Sentence splitting (conservative, NLP-based)
    # ------------------------------------------------------------------ #

    def _split_long_sentences(self, text, target_grade):
        """Split sentences too long for target grade. Uses spaCy dep parsing."""
        constraints = self.grade_constraints.get(target_grade, {'max_words': 20})
        max_words = constraints['max_words']

        changes = []
        doc = nlp(text)
        new_sentences = []

        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            word_count = len(words)

            if word_count <= max_words + 5:
                new_sentences.append(sent.text)
                continue

            split_result = self._try_split_sentence(sent, max_words)

            if split_result and len(split_result) > 1:
                new_sentences.extend(split_result)
                changes.append({
                    'type': 'sentence_split',
                    'original': sent.text,
                    'simplified': ' '.join(split_result),
                    'position': sent.start_char,
                    'reason': f"Split long sentence ({word_count} words) into {len(split_result)} shorter sentences. Target for Grade {target_grade}: max {max_words} words.",
                    'id': len(changes)
                })
            else:
                new_sentences.append(sent.text)

        return ' '.join(new_sentences), changes

    def _try_split_sentence(self, sent, max_words):
        """Try strategies to split a long sentence safely."""
        sent_text = sent.text.strip()

        # Strategy 1: Split at semicolons
        if ';' in sent_text:
            parts = sent_text.split(';')
            result = []
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                part = part[0].upper() + part[1:]
                if part[-1] not in '.!?':
                    part += '.'
                result.append(part)
            if len(result) > 1 and all(len(p.split()) >= 3 for p in result):
                return result

        # Strategy 2: Split at safe clause boundaries
        split_result = self._split_at_clause_boundary(sent)
        if split_result:
            return split_result

        # Strategy 3: Split at conjunctions (only if both sides have subjects)
        split_result = self._split_at_conjunction_safe(sent)
        if split_result:
            return split_result

        return None

    def _split_at_clause_boundary(self, sent):
        """Split at advcl/relcl boundaries, but ONLY at safe points."""
        tokens = list(sent)
        sent_text = sent.text

        clause_heads = []
        for token in tokens:
            if token.dep_ == 'advcl':
                # Skip infinitive "to" clauses
                if any(c.dep_ == 'mark' and c.text.lower() == 'to' for c in token.children):
                    continue
                # Must have comma or subordinating marker
                subtree = sorted(list(token.subtree), key=lambda t: t.i)
                if subtree:
                    first = subtree[0]
                    prev_idx = first.i - 1
                    has_comma = prev_idx >= sent.start and sent.doc[prev_idx].text == ','
                    has_marker = any(c.dep_ == 'mark' for c in token.children)
                    if not has_comma and not has_marker:
                        continue
                clause_heads.append(token)
            elif token.dep_ == 'relcl':
                # Only non-restrictive (preceded by comma)
                subtree = sorted(list(token.subtree), key=lambda t: t.i)
                if subtree:
                    first = subtree[0]
                    prev_idx = first.i - 1
                    if prev_idx >= sent.start and sent.doc[prev_idx].text == ',':
                        clause_heads.append(token)

        if not clause_heads:
            return None

        clause_heads.sort(key=lambda t: t.i, reverse=True)

        for clause_head in clause_heads:
            subtree_tokens = sorted(list(clause_head.subtree), key=lambda t: t.i)
            if not subtree_tokens:
                continue

            clause_start = subtree_tokens[0]
            clause_start_idx = clause_start.i - sent.start

            # Find marker token
            marker_token = None
            for child in clause_head.children:
                if child.dep_ in ('mark', 'ref') and child.i < clause_head.i:
                    marker_token = child
            for child in clause_head.children:
                if child.dep_ == 'nsubj' and child.text.lower() in ('which', 'who', 'whom', 'that', 'where'):
                    marker_token = child

            split_idx = clause_start_idx
            if marker_token:
                split_idx = min(split_idx, marker_token.i - sent.start)

            if split_idx <= 2 or split_idx >= len(tokens) - 3:
                continue

            before_tokens = tokens[:split_idx]
            after_tokens = tokens[split_idx:]
            main_subject = self._get_main_subject(tokens)

            before_text = sent_text[before_tokens[0].idx - sent.start_char:
                                    before_tokens[-1].idx - sent.start_char + len(before_tokens[-1].text)].strip()
            after_text = sent_text[after_tokens[0].idx - sent.start_char:].strip()

            after_text = after_text.lstrip(', ')
            before_text = before_text.rstrip(', ')

            # Handle relative pronouns
            rel_pronouns = {'where', 'which', 'who', 'whom', 'whose', 'that'}
            words_after = after_text.split()
            first_word = words_after[0].lower() if words_after else ''

            if first_word in rel_pronouns:
                rest = ' '.join(words_after[1:])
                if not rest:
                    continue
                if first_word == 'where':
                    after_text = 'There, ' + rest
                elif first_word in ('which', 'that', 'who', 'whom'):
                    rest_doc = nlp(rest)
                    if not any(t.dep_ in ('nsubj', 'nsubjpass') for t in rest_doc) and main_subject:
                        after_text = main_subject + ' ' + rest
                    else:
                        after_text = rest
                else:
                    after_text = rest
            else:
                after_doc = nlp(after_text)
                if not any(t.dep_ in ('nsubj', 'nsubjpass') for t in after_doc) and main_subject:
                    after_text = main_subject + ' ' + after_text[0].lower() + after_text[1:]

            # Validate second part is a real sentence
            after_doc = nlp(after_text)
            if not (any(t.pos_ == 'VERB' for t in after_doc) and
                    any(t.dep_ in ('nsubj', 'nsubjpass') for t in after_doc)):
                continue

            if before_text and before_text[-1] not in '.!?':
                before_text += '.'
            if after_text:
                after_text = after_text[0].upper() + after_text[1:]
                if after_text[-1] not in '.!?':
                    after_text += '.'

            if len(before_text.split()) >= 5 and len(after_text.split()) >= 5:
                return [before_text, after_text]

        return None

    def _split_at_conjunction_safe(self, sent):
        """Split at coordinating conjunctions ONLY when both halves have subjects."""
        tokens = list(sent)
        sent_text = sent.text

        for token in tokens:
            if token.dep_ == 'cc' and token.text.lower() in ('and', 'but', 'or', 'yet', 'so'):
                cc_idx = token.i - sent.start
                if cc_idx <= 1 or cc_idx >= len(tokens) - 2:
                    continue

                conj_token = None
                for t in tokens:
                    if t.dep_ == 'conj' and t.head == token.head:
                        conj_token = t
                        break
                if not conj_token:
                    continue

                # Check conjunct has its own subject
                conj_has_subject = any(
                    t.dep_ in ('nsubj', 'nsubjpass')
                    for t in conj_token.subtree
                )
                if not conj_has_subject:
                    continue

                cc_char = token.idx - sent.start_char
                before_text = sent_text[:cc_char].strip().rstrip(', ')
                after_text = sent_text[cc_char + len(token.text):].strip().lstrip(', ')

                if not before_text or not after_text:
                    continue

                if before_text[-1] not in '.!?':
                    before_text += '.'
                after_text = after_text[0].upper() + after_text[1:]
                if after_text[-1] not in '.!?':
                    after_text += '.'

                if len(before_text.split()) >= 5 and len(after_text.split()) >= 5:
                    return [before_text, after_text]

        return None

    def _get_main_subject(self, tokens):
        """Extract the main subject noun phrase."""
        for token in tokens:
            if token.dep_ in ('nsubj', 'nsubjpass'):
                subtree = sorted(list(token.subtree), key=lambda t: t.i)
                return ' '.join(t.text for t in subtree if t.dep_ not in ('relcl', 'acl', 'advcl'))
        return None

    # ------------------------------------------------------------------ #
    #  Groq fallback (optional)
    # ------------------------------------------------------------------ #

    def _needs_groq_help(self, text, target_grade):
        if not self.groq_client:
            return False
        doc = nlp(text)
        constraints = self.grade_constraints.get(target_grade, {'max_words': 20})
        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            if len(words) > constraints['max_words'] + 5:
                return True
        return False

    def groq_fallback(self, text, target_grade):
        if not self.groq_client:
            return text, []
        try:
            prompt = f"""Simplify this text to Grade {target_grade} reading level.
Rules:
- Use shorter sentences (max {self.grade_constraints[target_grade]['max_words']} words)
- Replace difficult words with simpler alternatives
- Maintain the original meaning
- Be natural and clear

Text:
{text}

Simplified version:"""

            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            simplified = response.choices[0].message.content.strip()
            return simplified, [{
                'type': 'ai_enhanced',
                'original': text,
                'simplified': simplified,
                'position': 0,
                'reason': 'AI-assisted simplification (Groq Llama 3.3 70B).',
                'id': 999
            }]
        except Exception as e:
            print(f"Groq API error: {e}")
            return text, []

    # Backward compatibility
    def replace_difficult_words(self, text, target_grade):
        return self._replace_difficult_words(text, target_grade)

    def split_long_sentences(self, text, target_grade):
        return self._split_long_sentences(text, target_grade)

    def convert_passive_to_active(self, text):
        return text, []
