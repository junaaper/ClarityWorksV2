from .base import *


class RuleRewriteMixin:
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
        if target_grade <= 4 and syllables >= 3 and freq < threshold + 0.5:
            return True

        return False

    def _get_lookup_keys(self, *values):
        """Return de-duplicated lowercase lookup keys in priority order."""
        keys = []
        seen = set()

        for value in values:
            if not value:
                continue

            lowered = value.lower()
            if lowered in seen:
                continue

            seen.add(lowered)
            keys.append(lowered)

        return keys

    def _get_explicit_simplification(self, word, lemma=None):
        """Check curated and supplemental rule maps before dynamic synonym search."""
        for key in self._get_lookup_keys(word, lemma):
            curated = self.synonym_lookup.simplification_map.get(key)
            if curated:
                return curated['simple']

            supplemental = SUPPLEMENTAL_SIMPLIFICATIONS.get(key)
            if supplemental:
                return supplemental

        return None

    def _get_explicit_complex_options(self, word, lemma=None):
        """Merge curated and supplemental complexification options."""
        options = []
        seen = set()

        for key in self._get_lookup_keys(word, lemma):
            explicit_buckets = [
                self.synonym_lookup.get_complex_synonyms(key) or [],
                self.synonym_lookup.get_reverse_curated_complex_synonyms(key) or [],
            ]
            for bucket in explicit_buckets:
                for option in bucket:
                    lowered = option.lower()
                    if lowered not in seen:
                        seen.add(lowered)
                        options.append(option)

            for option in SUPPLEMENTAL_COMPLEXIFICATIONS.get(key, []):
                lowered = option.lower()
                if lowered not in seen:
                    seen.add(lowered)
                    options.append(option)

        return options

    def _is_explicit_simplification_candidate(self, word, lemma, candidate):
        """True when a replacement came from the deterministic rule maps."""
        explicit = self._get_explicit_simplification(word, lemma)
        return bool(explicit and explicit.lower() == candidate.lower())

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
        target_threshold = GRADE_ZIPF_THRESHOLDS.get(target_grade, 3.0)

        candidates = []

        explicit_simple = self._get_explicit_simplification(word_lower, lemma)
        if explicit_simple:
            freq = zipf_frequency(explicit_simple.split()[0], 'en')
            candidates.append((explicit_simple, freq, self.text_processor.count_syllables(explicit_simple)))

        if self.wordnet_available:
            # Use simplified Lesk to pick the best synset
            best_synset, lesk_score = self._disambiguate_sense(token)
            lesk_identified_sense = False

            if best_synset and lesk_score > 0:
                self._collect_synset_candidates(
                    best_synset, word_lower, lemma, original_freq,
                    original_syllables, candidates, set()
                )
                lesk_identified_sense = True

            # Fall back to first synset (most common sense) ONLY when:
            # - Lesk didn't identify a specific sense, AND
            # - Word isn't a highly polysemous verb (too risky without context)
            if len(candidates) <= (1 if explicit_simple else 0) and not lesk_identified_sense:
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

        # Rank: prefer easy/common candidates that hit the target grade threshold.
        candidates.sort(key=lambda c: (
            0 if self.synonym_lookup.is_easy_word(c[0].split()[0]) else 1,
            0 if c[1] >= target_threshold else 1,
            c[2],
            -c[1],
            len(c[0])
        ))

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
        if not self.wordnet_available:
            return None, 0

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
                if synset.pos() == wn.VERB:
                    max_senses = 4
                elif synset.pos() == wn.NOUN:
                    max_senses = 10
                else:
                    max_senses = 8
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

            # Avoid double-inflecting replacements that are already in the
            # requested surface form (e.g. "suggested" -> "suggestedded").
            if tag in ('VBD', 'VBN') and base.endswith('ed'):
                return simple_word
            if tag == 'VBG' and base.endswith('ing'):
                return simple_word
            if tag == 'VBZ' and base.endswith('s'):
                return simple_word

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

    def _replace_difficult_words(self, text, target_grade, max_changes=None):
        """
        Replace difficult words using:
        1. Difficulty check via zipf_frequency + Dale-Chall + syllables
        2. Synonym lookup via WordNet, ranked by frequency
        3. Inflection preservation via spaCy POS tags
        """
        changes = []
        target_label = self._target_grade_label(target_grade)
        doc = nlp(text)
        new_text = text
        offset = 0

        for token in doc:
            if max_changes is not None and len(changes) >= max_changes:
                break

            if not token.is_alpha:
                continue

            # Skip proper nouns
            if token.pos_ == 'PROPN':
                continue

            # Skip ALL_CAPS tokens — these are acronyms/abbreviations (e.g., IDPS, TCP, HTML)
            if token.text.isupper() and len(token.text) > 1:
                continue

            word_lower = token.text.lower()
            explicit_synonym = self._get_explicit_simplification(word_lower, token.lemma_.lower())

            if self._is_domain_sensitive_term(word_lower, token, explicit_synonym=explicit_synonym):
                continue

            if token.is_stop and not explicit_synonym:
                continue

            # Skip short words
            if len(word_lower) < 4 and not explicit_synonym:
                continue

            # Skip words that are not too hard for target grade
            if not explicit_synonym and not self._is_word_too_hard(word_lower, target_grade):
                continue

            # Skip verbs in phrasal constructions (verb + preposition)
            # e.g., "attest to", "refer to" - replacing the verb often breaks the phrase
            if token.pos_ == 'VERB':
                next_token = doc[token.i + 1] if token.i + 1 < len(doc) else None
                if next_token and next_token.dep_ == 'prep' and next_token.head == token:
                    continue

            # Find a simpler synonym dynamically
            base_synonym = explicit_synonym or self._find_simpler_synonym(word_lower, token, target_grade)
            if not base_synonym:
                continue

            candidate_head = re.sub(r"^[^\w']+|[^\w']+$", '', base_synonym.split()[0].lower())
            if (
                not explicit_synonym and
                candidate_head and
                nlp.vocab[candidate_head].is_stop
            ):
                continue

            # Check the synonym is actually simpler (guard rail)
            orig_freq = zipf_frequency(word_lower, 'en')
            syn_freq = zipf_frequency(base_synonym.split()[0], 'en')
            if (not self._is_explicit_simplification_candidate(word_lower, token.lemma_.lower(), base_synonym) and
                    syn_freq < orig_freq + MIN_FREQ_IMPROVEMENT):
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
                'start': token.idx,
                'end': token.idx + len(token.text),
                'reason': f"'{token.text}' (freq {orig_zipf:.1f}, {syllables_before} syl) -> '{simple_word}' (freq {syn_zipf:.1f}, {syllables_after} syl). More common word for {target_label}.",
                'id': len(changes)
            })

        return new_text, changes

    # ------------------------------------------------------------------ #
    #  Upgrade path: complexification
    # ------------------------------------------------------------------ #

    def _complexify_text(self, text, target_grade, max_changes=None):
        """
        Replace simple/common words with more formal/academic alternatives.
        Used when upgrading text to a higher grade level.

        Strategy:
        1. Check complexification_map first (curated quality mappings)
        2. Use WordNet to find synonyms with MORE syllables + appropriate Zipf frequency
        3. Skip stop words, proper nouns, acronyms, very short words
        """
        changes = []
        target_label = self._target_grade_label(target_grade)
        doc = nlp(text)
        new_text = text
        offset = 0

        target_syl = GRADE_TARGET_SYLLABLES.get(target_grade, 1.55)
        target_threshold = GRADE_ZIPF_THRESHOLDS.get(target_grade, 3.0)

        for token in doc:
            if max_changes is not None and len(changes) >= max_changes:
                break

            if not token.is_alpha:
                continue
            if token.pos_ in ('PROPN', 'NUM'):
                continue
            if token.text.isupper() and len(token.text) > 1:
                continue
            if len(token.text) < 3:
                continue

            word_lower = token.text.lower()
            complex_options = self._get_explicit_complex_options(word_lower, token.lemma_.lower())

            # Most stop words should stay untouched, but curated discourse-marker
            # upgrades such as "also -> furthermore" help adjacent grade bumps
            # without changing the meaning of the sentence.
            if token.is_stop and not (complex_options and token.pos_ == 'ADV'):
                continue
            if token.pos_ == 'VERB':
                next_token = doc[token.i + 1] if token.i + 1 < len(doc) else None
                if next_token and next_token.head == token and next_token.dep_ in ('prep', 'acomp', 'oprd', 'xcomp'):
                    continue

            orig_freq = zipf_frequency(word_lower, 'en')
            orig_syl = self.text_processor.count_syllables(word_lower)

            # Skip words that are already complex enough for the target grade:
            #   - already has 3+ syllables, OR
            #   - already rare enough (freq below target threshold + small buffer)
            if orig_syl >= 3:
                continue
            if orig_freq <= target_threshold + 0.5:
                continue

            complex_syn = self._find_complex_synonym(
                token,
                target_grade,
                target_threshold,
                target_syl,
                complex_options=complex_options
            )
            if not complex_syn:
                continue
            if self._is_unsafe_complex_upgrade_context(token, complex_syn):
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
                'start': token.idx,
                'end': token.idx + len(token.text),
                'reason': f"'{token.text}' → '{inflected}': More formal vocabulary for {target_label}.",
                'id': len(changes)
            })

        return new_text, changes

    def _is_unsafe_complex_upgrade_context(self, token, complex_syn):
        lemma = token.lemma_.lower()
        replacement_head = (complex_syn or '').split()[0].lower()
        children = list(token.children)
        child_deps = {child.dep_ for child in children}
        doc = token.doc
        forward_window = [
            doc[i].lemma_.lower()
            for i in range(token.i + 1, min(len(doc), token.i + 7))
            if doc[i].is_alpha
        ]

        # Local one-word replacements cannot repair the grammar of
        # "helps us dig" into "assists us with digging".
        if lemma in {'help', 'assist', 'facilitate'} and child_deps & {'xcomp', 'ccomp'}:
            return True

        # "make" is highly idiomatic: make it worth, make a salad, make sure,
        # etc. Generic formal verbs sound broken in those frames.
        if lemma == 'make':
            if child_deps & {'acomp', 'xcomp', 'oprd', 'ccomp'}:
                return True
            if any(word in {'worth', 'possible', 'sure', 'clear'} for word in forward_window):
                return True
            object_terms = {
                child.lemma_.lower()
                for child in children
                if child.dep_ in {'dobj', 'obj', 'attr'}
            }
            if (
                object_terms & {'salad', 'meal', 'dinner', 'lunch', 'food'}
                and replacement_head in {'create', 'produce', 'generate', 'construct'}
            ):
                return True

        # "grow food/plants" and "days grow longer" need phrase-level wording
        # such as "cultivate food" or "become longer"; isolated replacement is unsafe.
        if lemma == 'grow':
            if child_deps & {'dobj', 'obj', 'acomp', 'xcomp', 'oprd', 'ccomp'}:
                return True
            if any(word in {'food', 'plant', 'seed', 'shoot', 'leaf', 'leaves', 'garden'} for word in forward_window):
                return True

        # "commence to push/eat/dig" is grammatical in a narrow register but
        # reads awkwardly in simple concrete passages.
        if lemma == 'start' and replacement_head in {'commence', 'initiate'} and child_deps & {'xcomp'}:
            return True

        return False

    def _find_complex_synonym(self, token, target_grade, target_threshold, target_syl, complex_options=None):
        """
        Find a more complex/formal synonym for vocabulary upgrading.

        Primarily uses the curated complexification_map. Falls back to WordNet
        only with strict POS matching and sanity checks to avoid nonsensical output.
        """
        word_lower = token.text.lower()
        lemma = token.lemma_.lower()
        orig_freq = zipf_frequency(word_lower, 'en')
        orig_syl = self.text_processor.count_syllables(word_lower)

        if target_grade <= 10 and (word_lower in {'also', 'then'} or lemma in {'also', 'then'}):
            return None
        if target_grade <= 6 and (word_lower in LOW_MID_UPGRADE_BLOCKED_WORDS or lemma in LOW_MID_UPGRADE_BLOCKED_WORDS):
            return None

        # --- Strategy 1: Curated complexification_map ---
        if complex_options is None:
            complex_options = (self.synonym_lookup.get_complex_synonyms(lemma) or
                               self.synonym_lookup.get_complex_synonyms(word_lower))
        if complex_options:
            # POS validation: curated map doesn't store POS, so verify the
            # complex synonym can function as the same POS as the original token.
            wn_pos_map = {'VERB': wn.VERB, 'NOUN': wn.NOUN, 'ADV': wn.ADV} if self.wordnet_available else {}
            wn_pos = wn_pos_map.get(token.pos_)  # ADJ checked separately (ADJ_SAT)

            best = None
            best_dist = float('inf')
            for opt in complex_options:
                first_word = opt.split()[0]
                first_lower = first_word.lower()
                if target_grade <= 10 and first_lower in {
                    'utilize',
                    'utilizes',
                    'utilized',
                    'utilizing',
                    'utilise',
                    'utilises',
                    'utilised',
                    'utilising',
                    'moreover',
                    'furthermore',
                    'position',
                    'positions',
                    'network',
                    'networks',
                }:
                    continue
                freq = zipf_frequency(first_word, 'en')
                syllables = self.text_processor.count_syllables(first_word)
                if target_grade <= 6 and syllables > 2:
                    continue
                # Must be more formal (lower freq) and reasonably accessible
                if syllables <= orig_syl and freq >= orig_freq - 0.1:
                    continue
                if freq < target_threshold - (0.2 if target_grade <= 6 else 0.7):
                    continue
                # POS sanity: complex synonym must exist with same POS in WordNet.
                # If WordNet data is unavailable, fall back to curated-map trust.
                if self.wordnet_available and wn_pos and not wn.synsets(first_word, pos=wn_pos):
                    continue  # e.g. rejects "comparable" for a VERB token
                if self.wordnet_available and token.pos_ == 'ADJ':
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
        # LLM handles vocabulary upgrade for words not in the curated map.
        return None
