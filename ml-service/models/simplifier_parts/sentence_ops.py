from .base import *


class SentenceOpsMixin:
    def _combine_short_sentences(self, text, target_grade, max_combinations=None, relaxed=False):
        """
        Combine consecutive short sentences to reach target avg words-per-sentence.
        Used for upgrading text to higher grades where longer sentences are expected.
        """
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_label = self._target_grade_label(target_grade)
        target_wps = metrics['target_wps']
        max_wps = metrics['max_wps']
        min_words = metrics['min_wps']  # Combine if sentence is shorter than this
        combine_trigger = min(max(min_words, target_wps - 4), max_wps - 3)
        combine_cap = max(max_wps + 6, target_wps + 11)
        if relaxed:
            combine_trigger = max(combine_trigger, target_wps + 3)
            combine_cap = max(combine_cap, max_wps + 14, target_wps + 18)

        changes = []
        result_paragraphs = []
        combinations_made = 0
        paragraphs = self._extract_paragraph_chunks(text) or [{
            'raw': text,
            'start': 0,
            'end': len(text),
        }]

        for paragraph in paragraphs:
            raw_paragraph = paragraph['raw']
            leading_ws = len(raw_paragraph) - len(raw_paragraph.lstrip())
            paragraph_text = raw_paragraph.strip()
            paragraph_start = paragraph['start'] + leading_ws

            if not paragraph_text:
                continue

            doc = nlp(paragraph_text)
            sentences = list(doc.sents)
            if not sentences:
                result_paragraphs.append(paragraph_text)
                continue

            result_sentences = []
            i = 0

            while i < len(sentences):
                sent = sentences[i]
                word_count = len([t for t in sent if t.is_alpha])

                if (
                    i + 1 < len(sentences) and
                    (max_combinations is None or combinations_made < max_combinations)
                ):
                    next_sent = sentences[i + 1]
                    next_words = len([t for t in next_sent if t.is_alpha])
                    combined_words = word_count + next_words
                    should_consider_pair = (
                        word_count <= combine_trigger or
                        (word_count <= target_wps + 1 and next_words <= target_wps + 1)
                    )

                    if should_consider_pair and combined_words <= combine_cap:
                        text1 = sent.text.rstrip('.!?')
                        first_alpha = next((token for token in next_sent if token.is_alpha), None)
                        if first_alpha is not None and (first_alpha.pos_ == 'PROPN' or first_alpha.ent_type_):
                            text2 = next_sent.text
                        else:
                            text2 = next_sent.text[0].lower() + next_sent.text[1:]
                        if target_grade >= 9:
                            combined = f"{text1}; {text2}"
                        else:
                            combined = f"{text1}, and {text2}"

                        original_pair = sent.text + ' ' + next_sent.text
                        changes.append({
                            'type': 'sentence_combine',
                            'original': original_pair,
                            'simplified': combined,
                            'position': paragraph_start + sent.start_char,
                            'start': paragraph_start + sent.start_char,
                            'end': paragraph_start + next_sent.end_char,
                            'reason': (f"Combined short sentences ({word_count} + {next_words} = {combined_words} words). "
                                       f"{target_label} target: avg {target_wps} words/sentence."),
                            'id': len(changes)
                        })
                        result_sentences.append(combined)
                        combinations_made += 1
                        i += 2
                        continue

                result_sentences.append(sent.text)
                i += 1

            result_paragraphs.append(' '.join(result_sentences).strip())

        return '\n\n'.join(paragraph for paragraph in result_paragraphs if paragraph.strip()), changes

    # ------------------------------------------------------------------ #
    #  Sentence splitting (conservative, NLP-based)
    # ------------------------------------------------------------------ #

    def _split_long_sentences(self, text, target_grade, max_sentence_changes=None):
        """
        Split sentences that exceed the target range for the grade.
        Run recursively so large downscales do not stop after a single split.
        """
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_label = self._target_grade_label(target_grade)
        target_wps = metrics['target_wps']
        max_wps = metrics['max_wps']
        split_threshold = min(max_wps, target_wps + 2)

        changes = []
        new_paragraphs = []
        changed_sentence_count = 0
        paragraphs = self._extract_paragraph_chunks(text) or [{
            'raw': text,
            'start': 0,
            'end': len(text),
        }]

        for paragraph in paragraphs:
            raw_paragraph = paragraph['raw']
            leading_ws = len(raw_paragraph) - len(raw_paragraph.lstrip())
            paragraph_text = raw_paragraph.strip()
            paragraph_start = paragraph['start'] + leading_ws

            if not paragraph_text:
                continue

            doc = nlp(paragraph_text)
            new_sentences = []

            for sent in doc.sents:
                original_word_count = self._count_alpha_words(sent)
                fragments = [(sent.text.strip(), 0)]
                changed = False

                if max_sentence_changes is not None and changed_sentence_count >= max_sentence_changes:
                    new_sentences.append(sent.text)
                    continue

                for _ in range(4):
                    progress = False
                    updated_fragments = []

                    for fragment, depth in fragments:
                        fragment_doc = nlp(fragment)
                        fragment_sent = next(fragment_doc.sents, None)
                        if fragment_sent is None:
                            updated_fragments.append((fragment, depth))
                            continue

                        fragment_word_count = self._count_alpha_words(fragment_sent)
                        if fragment_word_count <= split_threshold:
                            normalized_fragment = self._normalize_split_fragment(fragment)
                            updated_fragments.append((normalized_fragment or fragment.strip(), depth))
                            continue

                        # Prevent over-splitting already shortened fragments. A
                        # single safe split is usually enough; repeated splits on
                        # medium-length fragments are where we start producing
                        # broken outputs such as "They forms ..." or "It ideas ...".
                        if depth > 0 and fragment_word_count <= max(split_threshold + 2, target_wps + 4):
                            normalized_fragment = self._normalize_split_fragment(fragment)
                            updated_fragments.append((normalized_fragment or fragment.strip(), depth))
                            continue

                        split_result = self._try_split_sentence(fragment_sent, target_wps)
                        if split_result and len(split_result) > 1:
                            updated_fragments.extend((piece, depth + 1) for piece in split_result)
                            progress = True
                            changed = True
                        else:
                            updated_fragments.append((fragment.strip(), depth))

                    fragments = updated_fragments
                    if not progress:
                        break

                if changed:
                    new_sentences.extend(fragment for fragment, _ in fragments)
                    changed_sentence_count += 1
                    changes.append({
                        'type': 'sentence_split',
                        'original': sent.text,
                        'simplified': ' '.join(fragment for fragment, _ in fragments),
                        'position': paragraph_start + sent.start_char,
                        'start': paragraph_start + sent.start_char,
                        'end': paragraph_start + sent.end_char,
                        'reason': (
                            f"Split long sentence ({original_word_count} words) into {len(fragments)} "
                            f"shorter sentences. {target_label} target: about {target_wps} "
                            f"words per sentence, max {max_wps}."
                        ),
                        'id': len(changes)
                    })
                else:
                    new_sentences.append(sent.text)

            new_paragraphs.append(' '.join(new_sentences).strip())

        return '\n\n'.join(paragraph for paragraph in new_paragraphs if paragraph.strip()), changes

    def _count_alpha_words(self, text_or_doc):
        if isinstance(text_or_doc, str):
            doc = nlp(text_or_doc)
            return len([t for t in doc if t.is_alpha])
        return len([t for t in text_or_doc if t.is_alpha])

    def _is_finite_verb_token(self, token):
        if token.pos_ not in ('VERB', 'AUX'):
            return False

        morph = str(token.morph)
        if 'VerbForm=Fin' in morph:
            return True
        if any(flag in morph for flag in ('VerbForm=Inf', 'VerbForm=Ger', 'VerbForm=Part')):
            return False
        return token.tag_ in FINITE_VERB_TAGS

    def _starts_with_bad_fragment_phrase(self, tokens):
        alpha_tokens = [token for token in tokens if token.is_alpha]
        if len(alpha_tokens) >= 2:
            pair = (alpha_tokens[0].lower_, alpha_tokens[1].lower_)
            if pair in BAD_FRAGMENT_OPENING_PAIRS:
                return True

        return False

    def _ends_with_bad_fragment_tail(self, text):
        words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text or '')
        if not words:
            return False
        return words[-1].lower() in BAD_FRAGMENT_ENDINGS

    def _has_unfinished_clause_tail(self, text_or_doc):
        if isinstance(text_or_doc, str):
            doc = nlp(text_or_doc)
        else:
            doc = text_or_doc

        alpha_tokens = [token for token in doc if token.is_alpha]
        if not alpha_tokens:
            return False

        unfinished_markers = {
            'after', 'before', 'because', 'if', 'since', 'that',
            'until', 'when', 'where', 'which', 'while', 'who', 'whose',
        }

        for index, token in enumerate(alpha_tokens):
            if token.lower_ not in unfinished_markers:
                continue

            trailing_tokens = alpha_tokens[index + 1:]
            if any(self._is_finite_verb_token(trailing) for trailing in trailing_tokens):
                continue
            return True

        return False

    def _has_subject_and_verb(self, text_or_doc, min_words=4):
        if isinstance(text_or_doc, str):
            doc = nlp(text_or_doc)
        else:
            doc = text_or_doc

        tokens = [t for t in doc if not t.is_space]
        words = [t for t in doc if t.is_alpha]
        if len(words) < min_words or not tokens:
            return False

        if self._starts_with_bad_fragment_phrase(tokens):
            return False
        if self._has_unfinished_clause_tail(doc) and not self._has_long_misparse_predicate_cue(doc):
            return False

        root = next((t for t in doc if t.dep_ == 'ROOT'), None)
        if root is None:
            return False

        has_finite_verb = self._is_finite_verb_token(root)
        if not has_finite_verb:
            has_finite_verb = any(
                child.dep_ in ('aux', 'auxpass', 'cop') and self._is_finite_verb_token(child)
                for child in root.children
            )
        if not has_finite_verb:
            return False

        def attached_to_main_clause(token):
            if token.head == root:
                return True
            if token.head.dep_ in ('aux', 'auxpass', 'cop', 'conj') and token.head.head == root:
                return True
            return False

        has_subject = any(
            token.dep_ in ('nsubj', 'nsubjpass', 'expl') and attached_to_main_clause(token)
            for token in doc
        )
        if not has_subject and self._has_subordinate_and_main_clause(doc):
            return True
        return has_subject

    def _looks_like_complete_sentence(self, text_or_doc, min_words=3):
        if isinstance(text_or_doc, str):
            doc = nlp(text_or_doc)
        else:
            doc = text_or_doc

        tokens = [t for t in doc if not t.is_space]
        words = [t for t in doc if t.is_alpha]
        if len(words) < min_words or not tokens:
            return False

        if self._starts_with_bad_fragment_phrase(tokens):
            return False
        if self._has_unfinished_clause_tail(doc) and not self._has_long_misparse_predicate_cue(doc):
            return False

        alpha_words = [word.text.lower() for word in words]
        if self._has_simple_subject_agreement_error(alpha_words):
            return False

        has_finite_verb = any(self._is_finite_verb_token(token) for token in doc)
        has_subject = any(token.dep_ in ('nsubj', 'nsubjpass', 'expl') for token in doc)
        if has_finite_verb and has_subject:
            return True

        if self._has_subordinate_and_main_clause(doc):
            return True

        if self._has_surface_clause_cues(alpha_words):
            return True

        return self._has_long_misparse_predicate_cue(doc)

    def _has_simple_subject_agreement_error(self, alpha_words):
        if len(alpha_words) < 2:
            return False

        subject = alpha_words[0]
        verb = alpha_words[1]
        if verb.endswith('ly') or verb in LEADING_ADVERB_MARKERS:
            return False
        if self.wordnet_available and verb not in AUXILIARY_HINTS and not wn.synsets(verb, pos=wn.VERB):
            return False

        if subject in {'they', 'we', 'you', 'i'} and re.fullmatch(r"[a-z]+s", verb):
            return verb not in {'is', 'was', 'has'}
        if subject in {'it', 'he', 'she'} and verb in {'be', 'do', 'go', 'have', 'make', 'say', 'see', 'work'}:
            return True
        if subject in {'it', 'he', 'she'} and verb in {'are', 'were', 'have', 'do'}:
            return True
        return False

    def _has_surface_clause_cues(self, alpha_words):
        """
        spaCy occasionally mis-tags long technical sentences as noun phrases.
        When that happens, fall back to a lightweight surface heuristic so we do
        not reject otherwise valid structure rewrites.
        """
        if len(alpha_words) < 8:
            return False
        if self._has_simple_subject_agreement_error(alpha_words):
            return False

        for index in range(1, len(alpha_words)):
            word = alpha_words[index]
            previous_word = alpha_words[index - 1]
            next_word = alpha_words[index + 1] if index + 1 < len(alpha_words) else ''

            if word in AUXILIARY_HINTS:
                return True

            if not self.wordnet_available:
                continue
            if not wn.synsets(word, pos=wn.VERB):
                continue
            if previous_word in DETERMINER_HINTS:
                continue
            if next_word and next_word not in PREPOSITION_HINTS and next_word not in DETERMINER_HINTS:
                continue

            return True

        return False

    def _has_long_misparse_predicate_cue(self, doc):
        """
        Accept dense long sentences where spaCy attaches the true predicate
        inside a relative/prepositional clause and leaves a noun as ROOT.
        """
        alpha_tokens = [token for token in doc if token.is_alpha]
        if len(alpha_tokens) < 16:
            return False

        predicate_verbs = []
        for token in doc:
            if self._is_finite_verb_token(token):
                predicate_verbs.append(token)
                continue
            previous = doc[token.i - 1] if token.i > 0 else None
            if token.pos_ == 'VERB' and token.tag_ == 'VB' and (previous is None or previous.lower_ != 'to'):
                predicate_verbs.append(token)

        if not predicate_verbs:
            return False

        connective_words = {
            'which', 'that', 'who', 'whom', 'where', 'when',
            'while', 'because', 'although', 'and', 'but',
        }
        if not any(token.lower_ in connective_words for token in alpha_tokens):
            return False

        for verb in predicate_verbs:
            has_prior_nominal = any(
                token.i < verb.i and token.pos_ in {'NOUN', 'PROPN', 'PRON'}
                for token in doc
            )
            has_following_object_or_modifier = any(
                token.i > verb.i and token.pos_ in {'NOUN', 'PROPN', 'PRON', 'ADJ', 'ADV'}
                for token in doc
            )
            if has_prior_nominal and has_following_object_or_modifier:
                return True

        return False

    def _has_subordinate_and_main_clause(self, doc):
        alpha_words = [token.text.lower() for token in doc if token.is_alpha]
        if not alpha_words:
            return False
        if alpha_words[0] not in {'when', 'while', 'if', 'because', 'although', 'though', 'since', 'after', 'before'}:
            return False

        finite_verbs = [token for token in doc if self._is_finite_verb_token(token)]
        subjects = [token for token in doc if token.dep_ in ('nsubj', 'nsubjpass', 'expl')]
        return len(finite_verbs) >= 2 and len(subjects) >= 2

    _ADJ_SUFFIXES = ('ical', 'ional', 'ative', 'ible', 'able', 'ious', 'eous',
                      'ular', 'iful', 'rous', 'ient', 'iant', 'uous', 'ive',
                      'ent', 'ant', 'ous')

    def _ends_with_dangling_modifier(self, text):
        """Catch sentences ending with determiner+adjective but no noun,
        e.g. 'interested in the ethical.' or 'a comprehensive.'
        SpaCy sometimes tags these adjectives as NOUN in pobj position,
        so we also check for adjective-like suffixes after a determiner."""
        doc = nlp(text)
        alpha_tokens = [t for t in doc if t.is_alpha]
        if len(alpha_tokens) < 3:
            return False
        last = alpha_tokens[-1]
        second_last = alpha_tokens[-2]
        is_det = second_last.pos_ == 'DET' or second_last.lower_ in (
            'the', 'a', 'an', 'this', 'that', 'these', 'those')
        if not is_det:
            return False
        if last.pos_ == 'ADJ':
            return True
        if last.lower_.endswith(self._ADJ_SUFFIXES):
            return True
        return False

    def _collect_invalid_sentences(self, text):
        invalid = []
        if not text or not text.strip():
            return invalid

        doc = nlp(text)
        for sent in doc.sents:
            sentence_text = sent.text.strip()
            if not sentence_text:
                continue
            word_count = len([token for token in sent if token.is_alpha])

            if self._ends_with_bad_fragment_tail(sentence_text) and word_count <= 12:
                invalid.append(sentence_text)
                continue

            if self._ends_with_dangling_modifier(sentence_text):
                invalid.append(sentence_text)
                continue

            if not self._looks_like_complete_sentence(sentence_text, min_words=3):
                invalid.append(sentence_text)
                continue

            # Short split fragments are where the dependency-based validation is
            # most reliable, so keep an extra guard here to catch outputs such as
            # "They forms in ..." without rejecting dense but valid long sentences.
            if word_count <= 12 and not self._has_subject_and_verb(sentence_text, min_words=3):
                invalid.append(sentence_text)

        return invalid

    def _text_has_valid_sentence_structure(self, text):
        return not self._collect_invalid_sentences(text)

    def _extract_subject_info(self, tokens):
        """Extract the main subject phrase and whether it is plural."""
        for token in tokens:
            if token.dep_ not in ('nsubj', 'nsubjpass'):
                continue

            subtree = sorted(list(token.subtree), key=lambda t: t.i)
            subject_text = ' '.join(
                t.text for t in subtree
                if t.dep_ not in ('relcl', 'acl', 'advcl')
            ).strip()
            if not subject_text:
                continue

            is_plural = (
                token.tag_ in ('NNS', 'NNPS') or
                'Number=Plur' in str(token.morph) or
                token.lower_ in ('they', 'we', 'these', 'those')
            )
            return subject_text, is_plural

        return None, False

    def _get_main_subject(self, tokens):
        """Backward-compatible main subject extractor."""
        subject_text, _ = self._extract_subject_info(tokens)
        return subject_text

    def _get_carry_subject(self, tokens):
        """
        Pick a subject to reuse in split fragments. Long noun phrases become a
        pronoun so the split sentences stay readable.
        """
        subject_text, is_plural = self._extract_subject_info(tokens)
        if not subject_text:
            return None, False

        subject_doc = nlp(subject_text)
        alpha_words = [t.text for t in subject_doc if t.is_alpha]
        first_word = alpha_words[0].lower() if alpha_words else ''
        if len(alpha_words) > 4 and first_word not in ('he', 'she', 'they', 'it', 'we', 'you', 'i'):
            return ('They' if is_plural else 'It'), is_plural

        return subject_text, is_plural

    def _conjugate_present(self, lemma, subject_plural):
        """Convert a lemma into a simple present-tense verb for repaired clauses."""
        lemma = lemma.lower()

        if lemma == 'be':
            return 'are' if subject_plural else 'is'
        if lemma == 'have':
            return 'have' if subject_plural else 'has'
        if lemma == 'do':
            return 'do' if subject_plural else 'does'
        if lemma in ('can', 'could', 'may', 'might', 'must', 'should', 'will', 'would'):
            return lemma

        if subject_plural:
            return lemma

        if lemma in self.IRREGULAR_VERBS and 'VBZ' in self.IRREGULAR_VERBS[lemma]:
            return self.IRREGULAR_VERBS[lemma]['VBZ']

        if lemma.endswith(('s', 'sh', 'ch', 'x', 'z')):
            return lemma + 'es'
        if lemma.endswith('y') and len(lemma) > 2 and lemma[-2] not in 'aeiou':
            return lemma[:-1] + 'ies'
        return lemma + 's'

    def _clean_sentence_fragment(self, text):
        text = re.sub(r'\s+', ' ', text or '')
        text = re.sub(r'\s+([,.;!?])', r'\1', text)
        return text.strip(" \t\r\n,;:")

    def _normalize_split_fragment(self, fragment_text, carry_subject=None, subject_plural=False):
        """
        Turn a clause fragment into a standalone sentence.
        Repair subject-less right-hand clauses such as "and then building..."
        into "They then build...".
        """
        text = self._clean_sentence_fragment(fragment_text)
        if not text:
            return None

        doc = nlp(text)
        tokens = [t for t in doc if not t.is_space]
        if not tokens:
            return None

        leading_markers = []
        leading_adverbs = []
        idx = 0
        while idx < len(tokens) and tokens[idx].lower_ in LEADING_ADVERB_MARKERS:
            leading_adverbs.append(tokens[idx].text.lower())
            idx += 1
        while idx < len(tokens) and (tokens[idx].is_punct or tokens[idx].lower_ in LEADING_SPLIT_MARKERS):
            if tokens[idx].lower_ in LEADING_SPLIT_MARKERS:
                leading_markers.append(tokens[idx].lower_)
            idx += 1
        while idx < len(tokens) and tokens[idx].lower_ in LEADING_ADVERB_MARKERS:
            leading_adverbs.append(tokens[idx].text.lower())
            idx += 1
        while idx < len(tokens) and carry_subject and tokens[idx].lower_ in {'by'}:
            idx += 1

        if idx >= len(tokens):
            return None

        text = self._clean_sentence_fragment(text[tokens[idx].idx:])
        if not text:
            return None

        parsed = nlp(text)
        prefix = ' '.join(leading_adverbs).strip()
        can_repair_with_carry = (
            carry_subject and
            bool(leading_markers or leading_adverbs) and
            (not leading_markers or set(leading_markers).issubset(ALLOWED_CARRY_REPAIR_MARKERS))
        )

        if not self._has_subject_and_verb(parsed) and can_repair_with_carry:
            core_tokens = [t for t in parsed if not t.is_space and not t.is_punct]
            if not core_tokens:
                return None

            first = core_tokens[0]
            if first.pos_ not in ('VERB', 'AUX') and first.tag_ != 'VBD':
                return None
            if first.tag_ in ('VB', 'VBG', 'VBN') and not prefix:
                return None

            remainder = text[first.idx + len(first.text):].lstrip()
            intro = f"{prefix}, " if prefix else ""
            carry_text = carry_subject
            carry_lower = (carry_text or '').strip().lower()
            subject_uses_base_form = subject_plural or carry_lower in {'i', 'we', 'they', 'you'}
            if intro and carry_text:
                carry_text = carry_text[0].lower() + carry_text[1:]
            if first.tag_ in ('VB', 'VBP', 'VBZ', 'VBG', 'VBN'):
                repaired = (
                    f"{intro}{carry_text} "
                    f"{self._conjugate_present(first.lemma_, subject_uses_base_form)}"
                )
                if remainder:
                    repaired += f" {remainder}"
                text = repaired
            elif first.tag_ == 'VBD':
                lowered = text[0].lower() + text[1:] if len(text) > 1 else text.lower()
                text = f"{intro}{carry_text} {lowered}"
            else:
                lowered = text[0].lower() + text[1:] if len(text) > 1 else text.lower()
                repaired = f"{intro}{carry_text} {lowered}"
                text = repaired
        elif prefix:
            text = f"{prefix}, {text}"
        elif leading_markers and not can_repair_with_carry:
            return None

        text = self._clean_sentence_fragment(text)
        if not text:
            return None
        if self._has_unfinished_clause_tail(text):
            return None

        text = text[0].upper() + text[1:]
        if text[-1] not in '.!?':
            text += '.'

        if self._ends_with_bad_fragment_tail(text):
            return None

        word_count = self._count_alpha_words(text)
        if not self._looks_like_complete_sentence(text, min_words=3):
            return None
        if word_count <= 18 and not self._has_subject_and_verb(text, min_words=3):
            return None

        return text

    def _normalize_split_pair(self, before_text, after_text, carry_subject, subject_plural):
        before_words = re.findall(r"[A-Za-z']+", before_text.lower())
        if before_words and before_words[-1] in BAD_FRAGMENT_ENDINGS:
            return None
        if self._has_unfinished_clause_tail(before_text):
            return None

        before = self._normalize_split_fragment(before_text)
        after = self._normalize_split_fragment(after_text, carry_subject, subject_plural)

        if not before or not after:
            return None

        if self._count_alpha_words(before) < 4 or self._count_alpha_words(after) < 4:
            return None

        if self._ends_with_bad_fragment_tail(before) or self._ends_with_bad_fragment_tail(after):
            return None

        return [before, after]

    def _select_best_split_candidate(self, sent, candidate_tokens, target_words):
        tokens = list(sent)
        if not candidate_tokens:
            return None

        carry_subject, subject_plural = self._get_carry_subject(tokens)
        sentence_text = sent.text.strip()
        candidates = []
        seen = set()

        for token in candidate_tokens:
            if token.i in seen:
                continue
            seen.add(token.i)

            if token.i <= sent.start + 1 or token.i >= sent.end - 2:
                continue

            split_char = token.idx - sent.start_char
            before_text = sentence_text[:split_char].strip().rstrip(',;:')
            after_text = sentence_text[split_char:].strip().lstrip(',;:')

            pair = self._normalize_split_pair(before_text, after_text, carry_subject, subject_plural)
            if not pair:
                continue

            left_words = self._count_alpha_words(pair[0])
            right_words = self._count_alpha_words(pair[1])
            score = (
                max(abs(left_words - target_words), abs(right_words - target_words)),
                abs(left_words - right_words),
                abs((left_words + right_words) - (2 * target_words))
            )
            candidates.append((score, pair))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def _try_split_sentence(self, sent, target_words):
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
        split_result = self._split_at_clause_boundary(sent, target_words)
        if split_result:
            return split_result

        # Strategy 3: Split at conjunctions and markers, repairing the second
        # clause into a full sentence where needed.
        split_result = self._split_at_conjunction_safe(sent, target_words)
        if split_result:
            return split_result

        split_result = self._split_at_marker_boundary(sent, target_words)
        if split_result:
            return split_result

        return self._split_near_midpoint(sent, target_words)

    def _split_at_clause_boundary(self, sent, target_words):
        """Split at clause heads, then normalize each side into a sentence."""
        candidate_tokens = [
            token for token in sent
            if token.dep_ in ('ccomp', 'conj') and
            token.pos_ in ('VERB', 'AUX')
        ]
        return self._select_best_split_candidate(sent, candidate_tokens, target_words)

    def _split_at_conjunction_safe(self, sent, target_words):
        """Split at coordinating conjunctions and repair the right-hand clause."""
        candidate_tokens = [
            token for token in sent
            if (
                token.dep_ == 'cc' and
                token.text.lower() in ('and', 'but', 'yet') and
                token.head.pos_ in ('VERB', 'AUX')
            )
        ]
        return self._select_best_split_candidate(sent, candidate_tokens, target_words)

    def _split_at_marker_boundary(self, sent, target_words):
        """Split at a narrow set of mid-sentence markers when both sides stay valid."""
        candidate_tokens = [
            token for token in sent
            if token.is_alpha and token.text.lower() in MID_SENTENCE_SPLIT_MARKERS
        ]
        return self._select_best_split_candidate(sent, candidate_tokens, target_words)

    def _split_near_midpoint(self, sent, target_words):
        """
        Last-resort split near the target word count. This keeps large
        downscales moving even when dependency labels are not very helpful.
        """
        tokens = [t for t in sent if not t.is_space]
        alpha_tokens = [t for t in tokens if t.is_alpha]
        if len(alpha_tokens) < 10:
            return None

        preferred_alpha_count = min(max(target_words, 4), len(alpha_tokens) - 4)
        candidate_tokens = []
        alpha_count = 0
        for token in tokens:
            if token.is_alpha:
                alpha_count += 1

            remaining = len(alpha_tokens) - alpha_count
            if alpha_count < 4 or remaining < 4:
                continue

            if (
                token.text in {',', ';', ':'} or
                token.text.lower() in MID_SENTENCE_SPLIT_MARKERS or
                token.dep_ in ('conj', 'advcl', 'ccomp')
            ):
                candidate_tokens.append(token)

        if candidate_tokens:
            candidate_tokens.sort(
                key=lambda token: abs(
                    len([t for t in sent if t.is_alpha and t.i < token.i]) - preferred_alpha_count
                )
            )
            result = self._select_best_split_candidate(sent, candidate_tokens[:6], target_words)
            if result:
                return result

        return None

    # ------------------------------------------------------------------ #
    #  Change diffing: stable original->preview patches
    # ------------------------------------------------------------------ #
