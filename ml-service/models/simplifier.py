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

# Minimum Zipf frequency improvement required for a synonym to be accepted.
# Candidate must be at least this many Zipf units more common than the original.
# Prevents borderline or semantically wrong replacements.
MIN_FREQ_IMPROVEMENT = 0.8

# Words that must NEVER be used as synonyms regardless of frequency.
# Includes vulgar terms, slang that would be inappropriate or semantically wrong.
BLOCKED_SYNONYMS = {
    # Vulgar / offensive
    'dick', 'dicks', 'cock', 'ass', 'arse', 'bastard', 'bitch', 'shit',
    'crap', 'damn', 'hell', 'prick', 'twat', 'wanker', 'bollocks',
    # Common wrong replacements seen in the wild
    'lamb', 'lambs', 'stool', 'stools', 'tool',
    # Single-letter or very short that are meaningless in context
}

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
    13: 2.5,  # College: allows rare academic terminology
}

# Precise target metrics per grade — these are the two levers that drive the ML model.
# The ML model formula approximates: grade ≈ -21.16 + 14.33*(avg_syl) + 0.6*(avg_wps)
# Values are empirically calibrated: Grade 5 (syl=1.32, wps=12) and Grade 9 (syl=1.45, wps=19)
# have been validated to predict correctly. Others are interpolated.
#
#   target_syl  - target average syllables per word
#   target_wps  - target average words per sentence
#   min_wps     - minimum sentence length to avoid choppy text
#   max_wps     - maximum sentence length
GRADE_TARGET_METRICS = {
    3:  {'target_syl': 1.20, 'target_wps': 8,  'min_wps': 5,  'max_wps': 10},
    4:  {'target_syl': 1.26, 'target_wps': 10, 'min_wps': 7,  'max_wps': 13},
    5:  {'target_syl': 1.32, 'target_wps': 12, 'min_wps': 8,  'max_wps': 16},
    6:  {'target_syl': 1.35, 'target_wps': 14, 'min_wps': 10, 'max_wps': 18},
    7:  {'target_syl': 1.38, 'target_wps': 16, 'min_wps': 11, 'max_wps': 21},
    8:  {'target_syl': 1.41, 'target_wps': 17, 'min_wps': 12, 'max_wps': 22},
    9:  {'target_syl': 1.45, 'target_wps': 19, 'min_wps': 13, 'max_wps': 25},
    10: {'target_syl': 1.48, 'target_wps': 21, 'min_wps': 14, 'max_wps': 28},
    11: {'target_syl': 1.51, 'target_wps': 23, 'min_wps': 16, 'max_wps': 30},
    12: {'target_syl': 1.55, 'target_wps': 25, 'min_wps': 18, 'max_wps': 33},
    13: {'target_syl': 1.60, 'target_wps': 28, 'min_wps': 20, 'max_wps': 38},
}

# Kept for backward-compat with upgrade complexification code
GRADE_TARGET_SYLLABLES = {g: m['target_syl'] for g, m in GRADE_TARGET_METRICS.items()}


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

        # Grade-specific constraints derived from GRADE_TARGET_METRICS
        self.grade_constraints = {
            g: {'max_words': m['max_wps'], 'max_syllables': 4}
            for g, m in GRADE_TARGET_METRICS.items()
        }

        # Cache for synonym lookups (word -> best simple synonym)
        self._synonym_cache = {}

    # ------------------------------------------------------------------ #
    #  Main entry point
    # ------------------------------------------------------------------ #

    def simplify_to_grade(self, text, target_grade, mode='auto'):
        """
        Main rewrite function: bidirectional rule-based rewrite, then optional Groq polish.

        Direction-aware:
          - DOWNGRADE (target < estimated current): aggressive word simplification + sentence splitting
          - UPGRADE (target > estimated current): vocabulary complexification + sentence combining

        mode='auto'       — apply all changes automatically; try Groq if available
        mode='interactive' — rule-based only, individual changes for user to accept/deny

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

        # Measure current metrics and determine direction
        estimated_grade, current_syl, current_wps = self._measure_text_metrics(text)
        target_metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        going_up = target_grade > estimated_grade + 0.5

        print(f"[rewrite] estimated={estimated_grade:.1f} (syl={current_syl:.2f}, wps={current_wps:.1f}) "
              f"-> target={target_grade} (syl={target_metrics['target_syl']:.2f}, wps={target_metrics['target_wps']}) "
              f"going_up={going_up}")

        if going_up:
            # UPGRADE: add syllable complexity first, then lengthen sentences
            current_text, word_changes = self._complexify_text(current_text, target_grade)
            changes.extend(word_changes)
            # Combine short sentences to hit target_wps
            current_text, combine_changes = self._combine_short_sentences(current_text, target_grade)
            changes.extend(combine_changes)
        else:
            # DOWNGRADE: simplify vocabulary to hit target_syl, then split sentences to hit target_wps
            current_text, word_changes = self._replace_difficult_words(current_text, target_grade)
            changes.extend(word_changes)
            current_text, split_changes = self._split_long_sentences(current_text, target_grade)
            changes.extend(split_changes)

        validation = {'valid': True, 'issues': [], 'suggestions': []}

        if mode == 'auto':
            # Try Groq full rewrite for best quality.
            # When Groq succeeds, it completely replaces the text — return ONLY the
            # ai_rewrite change so the UI doesn't try to highlight rule-based changes
            # inside Groq-generated text (they won't match and cause false highlights).
            groq_text, groq_changes = self._groq_full_rewrite(text, target_grade, going_up)
            if groq_text:
                return {
                    'simplified_text': groq_text,
                    'changes': groq_changes,  # Only the single ai_rewrite change
                    'original_text': text,
                    'validation': {'valid': True, 'issues': [], 'suggestions': []}
                }
            # Groq unavailable: rule-based result stands
        else:
            # Interactive: light validation only, keep individual changes for user review
            validation = self.groq_validator.validate_changes(text, current_text, changes)
            if not validation['valid'] and validation['issues']:
                print(f"[interactive] Validation issues (not auto-fixing): {validation['issues']}")

        return {
            'simplified_text': current_text,
            'changes': changes,
            'original_text': text,
            'validation': validation
        }

    def _measure_text_metrics(self, text):
        """
        Measure actual text metrics and estimate grade.
        Returns: (estimated_grade, avg_syllables_per_word, avg_words_per_sentence)

        Uses the model approximation formula: grade ≈ -21.16 + 14.33*syl + 0.6*wps
        """
        doc = nlp(text)
        words = [t for t in doc if t.is_alpha]
        sentences = list(doc.sents)

        if not words or not sentences:
            return 8.0, 1.4, 15.0  # safe defaults

        total_syl = sum(self.text_processor.count_syllables(w.text.lower()) for w in words)
        avg_syl = total_syl / len(words)
        avg_wps = len(words) / len(sentences)

        predicted = -21.16 + 14.33 * avg_syl + 0.6 * avg_wps
        return max(3.0, min(14.0, predicted)), avg_syl, avg_wps

    def _estimate_current_grade(self, text):
        """Backward-compat wrapper."""
        grade, _, _ = self._measure_text_metrics(text)
        return grade

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
        # Datamuse uses "means like" which can return phonetically similar but semantically
        # unrelated words (e.g., "zone" -> "sun"). Apply much stricter checks:
        #   1. Must be significantly more common (>=1.5 Zipf units, not just 0.8)
        #   2. Must be in the Dale-Chall 3000 easy words list (proven simple vocabulary)
        if not candidates:
            datamuse_result = self.datamuse_finder.get_simpler_synonym(lemma)
            if datamuse_result:
                dm_freq = zipf_frequency(datamuse_result, 'en')
                dm_syl = self.text_processor.count_syllables(datamuse_result)
                dm_is_easy = self.synonym_lookup.is_easy_word(datamuse_result)
                if (dm_freq >= original_freq + 1.5 and
                        dm_syl <= original_syllables and
                        dm_is_easy):
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

            # Never use blocked/inappropriate synonyms
            if candidate in BLOCKED_SYNONYMS:
                continue

            cand_freq = zipf_frequency(candidate, 'en')
            cand_syllables = self.text_processor.count_syllables(candidate)

            # Must be significantly more frequent (MIN_FREQ_IMPROVEMENT Zipf units) AND fewer/equal syllables.
            # The minimum improvement threshold prevents borderline or semantically wrong replacements.
            if cand_freq >= original_freq + MIN_FREQ_IMPROVEMENT and cand_syllables <= original_syllables:
                candidates.append((candidate, cand_freq, cand_syllables))

    def _pos_matches(self, spacy_pos, wordnet_pos):
        """Map spaCy POS to WordNet POS for filtering.
        Note: many English adjectives in WordNet use ADJ_SAT ('s'), not ADJ ('a').
        Both must match for spaCy ADJ tokens.
        """
        if spacy_pos == 'ADJ':
            return wordnet_pos in (wn.ADJ, wn.ADJ_SAT)  # 'a' or 's'
        mapping = {
            'NOUN': wn.NOUN,
            'VERB': wn.VERB,
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
                # If the word already ends in 's', it is likely already in plural/invariant form.
                # Adding another 's' or 'es' would create non-words like "mechanicses".
                if last.endswith('s'):
                    plural = last  # already looks plural — use as-is
                elif last.endswith(('sh', 'ch', 'x', 'z')):
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
                if simple_word.endswith('e'):
                    return simple_word + 'r'
                elif self._should_double_final(simple_word):
                    return simple_word + simple_word[-1] + 'er'
                else:
                    return simple_word + 'er'
            elif tag == 'JJS':
                if simple_word.endswith('e'):
                    return simple_word + 'st'
                elif self._should_double_final(simple_word):
                    return simple_word + simple_word[-1] + 'est'
                else:
                    return simple_word + 'est'

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

            # Skip ALL_CAPS tokens — these are acronyms/abbreviations (e.g., IDPS, TCP, HTML)
            if token.text.isupper() and len(token.text) > 1:
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
            if syn_freq < orig_freq + MIN_FREQ_IMPROVEMENT:
                continue

            # Never use blocked synonyms at the final step either
            base_lower = base_synonym.lower().split()[0]
            if base_lower in BLOCKED_SYNONYMS:
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
    #  Upgrade path: complexification
    # ------------------------------------------------------------------ #

    def _complexify_text(self, text, target_grade):
        """
        Replace simple/common words with more formal/academic alternatives.
        Used when upgrading text to a higher grade level.

        Strategy:
        1. Check complexification_map first (curated quality mappings)
        2. Use WordNet to find synonyms with MORE syllables + appropriate Zipf frequency
        3. Skip stop words, proper nouns, acronyms, very short words
        """
        changes = []
        doc = nlp(text)
        new_text = text
        offset = 0

        target_syl = GRADE_TARGET_SYLLABLES.get(target_grade, 1.55)
        target_threshold = GRADE_ZIPF_THRESHOLDS.get(target_grade, 3.0)

        for token in doc:
            if not token.is_alpha or token.is_stop:
                continue
            if token.pos_ in ('PROPN', 'NUM'):
                continue
            if token.text.isupper() and len(token.text) > 1:
                continue
            if len(token.text) < 3:
                continue

            word_lower = token.text.lower()

            orig_freq = zipf_frequency(word_lower, 'en')
            orig_syl = self.text_processor.count_syllables(word_lower)

            # Skip words that are already complex enough for the target grade:
            #   - already has 3+ syllables, OR
            #   - already rare enough (freq below target threshold + small buffer)
            if orig_syl >= 3:
                continue
            if orig_freq <= target_threshold + 0.5:
                continue

            complex_syn = self._find_complex_synonym(token, target_grade, target_threshold, target_syl)
            if not complex_syn:
                continue

            # Check it's actually more complex (more syllables or lower freq)
            syn_freq = zipf_frequency(complex_syn.split()[0], 'en')
            syn_syl = self.text_processor.count_syllables(complex_syn)
            if syn_syl <= orig_syl and syn_freq >= orig_freq:
                continue  # Not actually more complex

            # Apply inflection
            inflected = self._apply_inflection(complex_syn, token)

            # Preserve capitalization
            if token.text[0].isupper():
                inflected = inflected[0].upper() + inflected[1:]

            # Replace in text
            start = token.idx + offset
            end = start + len(token.text)
            new_text = new_text[:start] + inflected + new_text[end:]
            offset += len(inflected) - len(token.text)

            changes.append({
                'type': 'word_upgrade',
                'original': token.text,
                'simplified': inflected,
                'position': token.idx,
                'reason': f"'{token.text}' → '{inflected}': More formal vocabulary for Grade {target_grade}.",
                'id': len(changes)
            })

        return new_text, changes

    def _find_complex_synonym(self, token, target_grade, target_threshold, target_syl):
        """
        Find a more complex/formal synonym for vocabulary upgrading.

        Primarily uses the curated complexification_map. Falls back to WordNet
        only with strict POS matching and sanity checks to avoid nonsensical output.
        """
        word_lower = token.text.lower()
        lemma = token.lemma_.lower()
        orig_freq = zipf_frequency(word_lower, 'en')
        orig_syl = self.text_processor.count_syllables(word_lower)

        # --- Strategy 1: Curated complexification_map ---
        complex_options = (self.synonym_lookup.get_complex_synonyms(lemma) or
                           self.synonym_lookup.get_complex_synonyms(word_lower))
        if complex_options:
            # POS validation: curated map doesn't store POS, so verify the
            # complex synonym can function as the same POS as the original token.
            wn_pos_map = {'VERB': wn.VERB, 'NOUN': wn.NOUN, 'ADV': wn.ADV}
            wn_pos = wn_pos_map.get(token.pos_)  # ADJ checked separately (ADJ_SAT)

            best = None
            best_dist = float('inf')
            for opt in complex_options:
                first_word = opt.split()[0]
                freq = zipf_frequency(first_word, 'en')
                # Must be more formal (lower freq) and reasonably accessible
                if freq >= orig_freq - 0.1 or freq < target_threshold - 0.5:
                    continue
                # POS sanity: complex synonym must exist with same POS in WordNet
                if wn_pos and not wn.synsets(first_word, pos=wn_pos):
                    continue  # e.g. rejects "comparable" for a VERB token
                if token.pos_ == 'ADJ':
                    if not (wn.synsets(first_word, pos=wn.ADJ) or
                            wn.synsets(first_word, pos=wn.ADJ_SAT)):
                        continue
                dist = abs(freq - target_threshold)
                if dist < best_dist:
                    best_dist = dist
                    best = opt
            if best:
                return best

        # Strategy 2: not used for upgrade — curated map is higher quality than
        # unconstrained WordNet reverse lookup, which produces semantic errors.
        # Groq handles vocabulary upgrade for words not in the curated map.
        return None

    def _combine_short_sentences(self, text, target_grade):
        """
        Combine consecutive short sentences to reach target avg words-per-sentence.
        Used for upgrading text to higher grades where longer sentences are expected.
        """
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_wps = metrics['target_wps']
        max_wps = metrics['max_wps']
        min_words = metrics['min_wps']  # Combine if sentence is shorter than this

        changes = []
        doc = nlp(text)
        sentences = list(doc.sents)
        result_sentences = []
        i = 0

        while i < len(sentences):
            sent = sentences[i]
            word_count = len([t for t in sent if t.is_alpha])

            # Combine if sentence is shorter than grade's min_wps AND a next sentence exists
            if word_count < min_words and i + 1 < len(sentences):
                next_sent = sentences[i + 1]
                next_words = len([t for t in next_sent if t.is_alpha])
                combined_words = word_count + next_words

                # Only combine if result is within the grade's max_wps
                if combined_words <= max_wps:
                    text1 = sent.text.rstrip('.!?')
                    text2 = next_sent.text[0].lower() + next_sent.text[1:]
                    combined = f"{text1}, and {text2}"

                    original_pair = sent.text + ' ' + next_sent.text
                    changes.append({
                        'type': 'sentence_combine',
                        'original': original_pair,
                        'simplified': combined,
                        'position': sent.start_char,
                        'reason': (f"Combined short sentences ({word_count} + {next_words} = {combined_words} words). "
                                   f"Grade {target_grade} target: avg {target_wps} words/sentence."),
                        'id': len(changes)
                    })
                    result_sentences.append(combined)
                    i += 2
                    continue

            result_sentences.append(sent.text)
            i += 1

        return ' '.join(result_sentences), changes

    # ------------------------------------------------------------------ #
    #  Sentence splitting (conservative, NLP-based)
    # ------------------------------------------------------------------ #

    def _split_long_sentences(self, text, target_grade):
        """
        Split sentences that exceed target_wps for the grade.
        Uses target_wps (not max_wps) so we actually hit the target metric.
        """
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_wps = metrics['target_wps']
        max_wps = metrics['max_wps']

        changes = []
        doc = nlp(text)
        new_sentences = []

        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            word_count = len(words)

            # Split any sentence that exceeds max_wps
            if word_count <= max_wps:
                new_sentences.append(sent.text)
                continue

            split_result = self._try_split_sentence(sent, target_wps)

            if split_result and len(split_result) > 1:
                new_sentences.extend(split_result)
                changes.append({
                    'type': 'sentence_split',
                    'original': sent.text,
                    'simplified': ' '.join(split_result),
                    'position': sent.start_char,
                    'reason': f"Split long sentence ({word_count} words) into {len(split_result)} shorter sentences. Target for Grade {target_grade}: avg {target_wps} words/sentence.",
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
    #  Change diffing: extract word-level changes from rewritten text
    # ------------------------------------------------------------------ #

    def _diff_changes(self, original_text, rewritten_text, target_grade, going_up):
        """
        Compare original vs rewritten text and extract meaningful changes WITHOUT
        any AI/Groq branding. Shown in the changes panel in auto mode.

        Strategy:
        - Single-word substitutions: show original → replacement with freq/syllable info
        - Sentence structure changes (splits/combines): summarized as a single entry
        - Multi-word chunk replacements are skipped to avoid noisy diffs
        """
        import difflib
        import re

        def strip_punct(w):
            # Keep internal apostrophes (contractions, possessives) but strip other punctuation
            return re.sub(r"^[^\w']+|[^\w']+$", '', w)

        def word_for_freq(w):
            # Strip everything including apostrophes for frequency lookup
            return re.sub(r"[^\w]", '', w).lower()

        orig_words = original_text.split()
        new_words = rewritten_text.split()

        matcher = difflib.SequenceMatcher(
            None,
            [strip_punct(w).lower() for w in orig_words],
            [strip_punct(w).lower() for w in new_words],
            autojunk=False
        )

        word_changes = []
        has_structural_changes = False

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue
            if len(word_changes) >= 25:
                break

            orig_raw = orig_words[i1:i2]
            new_raw = new_words[j1:j2]

            if tag == 'replace' and i2 - i1 == 1 and j2 - j1 == 1:
                # ---- Single word substitution — extract freq/syllable detail ----
                orig_word = strip_punct(orig_raw[0])
                new_word = strip_punct(new_raw[0])
                if not orig_word or not new_word or orig_word.lower() == new_word.lower():
                    continue

                # Skip if BOTH words are very high-frequency function words (stop words).
                # difflib alignment artifacts commonly swap articles/conjunctions/prepositions
                # when sentence structure changes — these are NOT real vocabulary substitutions.
                # e.g., "The" ↔ "and", "a" ↔ "the", "in" ↔ "of" are all false positives.
                _o = word_for_freq(orig_word)
                _n = word_for_freq(new_word)
                if zipf_frequency(_o, 'en') >= 6.5 and zipf_frequency(_n, 'en') >= 6.5:
                    has_structural_changes = True
                    continue

                # Also skip if either word is shorter than 2 characters (e.g., "a", "I")
                if len(_o) < 2 or len(_n) < 2:
                    has_structural_changes = True
                    continue

                orig_freq = zipf_frequency(word_for_freq(orig_word), 'en')
                new_freq = zipf_frequency(word_for_freq(new_word), 'en')
                orig_syl = self.text_processor.count_syllables(word_for_freq(orig_word))
                new_syl = self.text_processor.count_syllables(word_for_freq(new_word))

                if going_up:
                    reason = (f"'{orig_word}' ({orig_syl} syl, freq {orig_freq:.1f}) "
                              f"\u2192 '{new_word}' ({new_syl} syl, freq {new_freq:.1f}). "
                              f"More formal vocabulary for Grade {target_grade}.")
                else:
                    reason = (f"'{orig_word}' ({orig_syl} syl, freq {orig_freq:.1f}) "
                              f"\u2192 '{new_word}' ({new_syl} syl, freq {new_freq:.1f}). "
                              f"Simpler word for Grade {target_grade}.")

                word_changes.append({
                    'type': 'word_replacement',
                    'original': orig_raw[0],
                    'simplified': new_raw[0],
                    'position': i1,
                    'reason': reason,
                    'id': len(word_changes)
                })
            else:
                # Multi-word structural change — flag for the summary entry
                has_structural_changes = True

        # Add one structural summary entry (avoids noisy partial-chunk diffs)
        if has_structural_changes:
            metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
            if going_up:
                word_changes.append({
                    'type': 'sentence_combine',
                    'original': 'Short sentences',
                    'simplified': 'Combined sentences',
                    'position': 999,
                    'reason': (f"Short sentences combined to reach Grade {target_grade} target "
                               f"({metrics['target_wps']} words/sentence, range {metrics['min_wps']}–{metrics['max_wps']})."),
                    'id': len(word_changes)
                })
            else:
                word_changes.append({
                    'type': 'sentence_split',
                    'original': 'Long sentences',
                    'simplified': 'Split sentences',
                    'position': 999,
                    'reason': (f"Long sentences split to reach Grade {target_grade} target "
                               f"({metrics['target_wps']} words/sentence, range {metrics['min_wps']}–{metrics['max_wps']})."),
                    'id': len(word_changes)
                })

        return word_changes

    # ------------------------------------------------------------------ #
    #  Groq full rewrite (auto mode — always runs)
    # ------------------------------------------------------------------ #

    def _groq_full_rewrite(self, original_text, target_grade, going_up=False):
        """
        Rewrite the entire text at the target grade level using Groq.
        Direction-aware: uses a different prompt for upgrade vs downgrade.

        Includes a metric verification pass: if the first rewrite misses the targets
        by too much, a correction prompt is sent with the actual vs target metrics.

        Returns (rewritten_text, [change_obj]) or (None, []) if Groq unavailable.
        """
        if not self.groq_client:
            return None, []

        try:
            metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
            target_wps = metrics['target_wps']
            min_wps = metrics['min_wps']
            max_wps = metrics['max_wps']
            target_syl = metrics['target_syl']
            grade_label = 'College' if target_grade >= 13 else f'Grade {target_grade}'

            def _build_upgrade_prompt(text_to_rewrite):
                if target_grade <= 6:
                    vocab_level = "slightly more formal words with some two-syllable terms"
                    clause_rule = "Write clear, simple sentences. Use 'and', 'but', 'so' to combine ideas. AVOID complex clause nesting."
                elif target_grade <= 8:
                    vocab_level = "formal vocabulary with academic terms (utilize, demonstrate, significant, establish)"
                    clause_rule = "Use AT MOST one subordinate clause per sentence (e.g. one 'which', 'because', or 'while'). Keep sentences clear and direct."
                elif target_grade <= 10:
                    vocab_level = "academic vocabulary with clear transitions and logical connectors"
                    clause_rule = "You may use subordinate clauses and transitions. Aim for 1–2 clauses per sentence maximum."
                elif target_grade <= 12:
                    vocab_level = "sophisticated academic vocabulary with argument structure"
                    clause_rule = "Complex sentences with multiple clauses are appropriate at this level."
                else:
                    vocab_level = "professional academic prose with domain-specific terminology"
                    clause_rule = "Use full academic sentence complexity with multiple clauses and transitions."

                return f"""Rewrite the following text at exactly {grade_label} writing level.

THIS IS AN UPGRADE — make it MORE COMPLEX than the original.

STRICT METRIC TARGETS (the readability grade depends on hitting these precisely):
  - Average words per sentence: {target_wps}  (HARD LIMIT: each sentence must be {min_wps}–{max_wps} words)
  - Average syllables per word: {target_syl:.2f}

RULES:
1. SENTENCE LENGTH: Every sentence must be {min_wps}–{max_wps} words. NO sentence may exceed {max_wps} words. Combine short sentences using conjunctions and connectors.
2. VOCABULARY: Use {vocab_level}. Replace simple words with formal 2-syllable alternatives:
   "use" → "utilize"  |  "show" → "demonstrate"  |  "need" → "require"
   "big" → "significant"  |  "start" → "begin" or "establish"  |  "help" → "support"
   "get" → "obtain"  |  "find" → "discover"  |  "make" → "create" or "produce"
3. CLAUSE COMPLEXITY: {clause_rule}
4. SYLLABLE COUNT: Aim for avg {target_syl:.2f} syllables/word. Use 2-syllable words (per-son, com-plete, for-mal, dai-ly, of-ten).
5. PRESERVE MEANING: Keep all facts. Do not omit any information.
6. NAMES & ACRONYMS: Keep all proper nouns and abbreviations exactly as written.
7. NO REPETITION: Each idea appears once only.
8. OUTPUT: Write ONLY the rewritten text. No labels, headings, or commentary.

ORIGINAL TEXT:
{text_to_rewrite}

REWRITTEN TEXT ({grade_label}):"""

            def _build_downgrade_prompt(text_to_rewrite):
                if target_grade <= 4:
                    vocab_level = "only very simple 1-syllable everyday words a young child knows"
                elif target_grade <= 6:
                    vocab_level = "simple common words (mostly 1 syllable), no jargon"
                elif target_grade <= 8:
                    vocab_level = "common vocabulary, avoid technical or academic terms"
                else:
                    vocab_level = "standard vocabulary"

                return f"""Rewrite the following text at exactly {grade_label} reading level.

THIS IS A SIMPLIFICATION — make it EASIER than the original.

STRICT METRIC TARGETS (the ML model grade is determined ONLY by these two numbers):
  - Average words per sentence: {target_wps}  (HARD LIMIT: each sentence must be {min_wps}–{max_wps} words)
  - Average syllables per word: {target_syl:.2f}  (use short, common words)

RULES:
1. SENTENCE LENGTH: Every sentence must be {min_wps}–{max_wps} words. Split any longer sentence into two shorter ones. Use a period, not a semicolon.
2. VOCABULARY: Use {vocab_level}. Replace difficult words with simpler ones that mean THE SAME THING:
   "utilize" → "use"  |  "demonstrate" → "show"  |  "require" → "need"
   "obtain" → "get"  |  "substantial" → "large"  |  "facilitate" → "help"
   NEVER change word meaning: "zones" → "areas" is OK, "zones" → "suns" is WRONG.
3. SYLLABLE COUNT: Aim for avg {target_syl:.2f} syllables/word. Prefer short words.
4. PRESERVE MEANING: Keep ALL facts. Do not skip any paragraphs.
5. NAMES & ACRONYMS: Keep all proper nouns and abbreviations exactly as written.
6. NO REPETITION: Do NOT repeat any sentence or paragraph.
7. OUTPUT: Write ONLY the simplified text. No labels or commentary.

ORIGINAL TEXT:
{text_to_rewrite}

SIMPLIFIED TEXT ({grade_label}):"""

            def _strip_preamble(text):
                for prefix in ["REWRITTEN TEXT:", "UPGRADED TEXT:", "SIMPLIFIED TEXT:", "Here is", "Grade", "College"]:
                    if text.startswith(prefix) and '\n' in text:
                        text = text[text.index('\n') + 1:].strip()
                return text

            # ---- First pass ----
            prompt = _build_upgrade_prompt(original_text) if going_up else _build_downgrade_prompt(original_text)
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000
            )
            rewritten = _strip_preamble(response.choices[0].message.content.strip())

            # ---- Metric verification ----
            actual_grade, actual_syl, actual_wps = self._measure_text_metrics(rewritten)

            # Primary check: is the estimated grade close enough to the target?
            # Small grade jumps (e.g., Grade 4→6) need tight tolerance.
            grade_ok = abs(actual_grade - target_grade) <= 1.0
            # Secondary checks for individual metric violations
            wps_ok = min_wps <= actual_wps <= max_wps + 3
            syl_ok_up = not going_up or actual_syl >= target_syl - 0.10
            syl_ok_dn = going_up or actual_syl <= target_syl + 0.10

            print(f"[groq] pass1: actual grade={actual_grade:.1f}, syl={actual_syl:.2f}, wps={actual_wps:.1f} "
                  f"(targets: grade={target_grade}, syl={target_syl:.2f}, wps={target_wps}, range {min_wps}-{max_wps})")

            # ---- Correction pass if grade or metrics are off ----
            if not (grade_ok and wps_ok and syl_ok_up and syl_ok_dn):
                issues = []
                if not grade_ok:
                    if going_up and actual_grade < target_grade - 1:
                        issues.append(
                            f"result is Grade {actual_grade:.0f} but target is Grade {target_grade} — "
                            f"use more multi-syllable words and longer sentences"
                        )
                    elif not going_up and actual_grade > target_grade + 1:
                        issues.append(
                            f"result is Grade {actual_grade:.0f} but target is Grade {target_grade} — "
                            f"use shorter simpler words and split long sentences"
                        )
                if actual_wps > max_wps + 3:
                    issues.append(f"sentences averaged {actual_wps:.0f} words — must be {min_wps}–{max_wps} words EACH")
                elif actual_wps < min_wps - 2:
                    issues.append(f"sentences averaged only {actual_wps:.0f} words — must be {min_wps}–{max_wps} words EACH")
                if going_up and not syl_ok_up:
                    issues.append(f"vocabulary too simple ({actual_syl:.2f} syl/word) — need ~{target_syl:.2f}, use more 2–3 syllable words")
                elif not going_up and not syl_ok_dn:
                    issues.append(f"vocabulary too complex ({actual_syl:.2f} syl/word) — need ~{target_syl:.2f}, use shorter simpler words")

                if issues:
                    issue_str = '; '.join(issues)
                    correction_note = f"IMPORTANT — your previous attempt had these problems: {issue_str}. Fix them this time.\n\n"
                    base_prompt = _build_upgrade_prompt(original_text) if going_up else _build_downgrade_prompt(original_text)
                    correction_prompt = correction_note + base_prompt

                    resp2 = self.groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": correction_prompt}],
                        temperature=0.2,
                        max_tokens=4000
                    )
                    corrected = _strip_preamble(resp2.choices[0].message.content.strip())
                    c_grade, c_syl, c_wps = self._measure_text_metrics(corrected)
                    print(f"[groq] pass2: actual grade={c_grade:.1f}, syl={c_syl:.2f}, wps={c_wps:.1f}")

                    # Use the correction if it brings the grade closer to target
                    if abs(c_grade - target_grade) < abs(actual_grade - target_grade):
                        rewritten = corrected
                        actual_grade = c_grade

            # Extract granular word/sentence changes by diffing original vs rewritten.
            # These are shown in the changes panel without any AI branding.
            diff_changes = self._diff_changes(original_text, rewritten, target_grade, going_up)

            # If the diff found nothing meaningful (total rewrite), add one summary entry
            if not diff_changes:
                direction_label = 'upgraded' if going_up else 'simplified'
                diff_changes = [{
                    'type': 'sentence_combine' if going_up else 'sentence_split',
                    'original': original_text[:70] + ('...' if len(original_text) > 70 else ''),
                    'simplified': rewritten[:70] + ('...' if len(rewritten) > 70 else ''),
                    'position': 0,
                    'reason': f'Text {direction_label} to {grade_label} level (avg {GRADE_TARGET_METRICS[target_grade]["target_wps"]} words/sentence, {GRADE_TARGET_METRICS[target_grade]["target_syl"]:.2f} syl/word).',
                    'id': 0
                }]

            return rewritten, diff_changes

        except Exception as e:
            print(f"Groq full rewrite error: {e}")
            return None, []

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
