from .base import *


class DiffingMixin:
    @staticmethod
    def _extract_diff_chunks(text):
        chunks = []
        for match in re.finditer(r'\S+\s*', text):
            raw = match.group(0)
            stripped = raw.strip()
            core = re.sub(r"^[^\w']+|[^\w']+$", '', stripped)
            if not core:
                core = stripped
            chunks.append({
                'raw': raw,
                'display': stripped,
                'normalized': core.lower(),
                'normalized_cased': core,
                'start': match.start(),
                'end': match.end(),
            })
        return chunks

    def _extract_sentence_chunks(self, text):
        if not text.strip():
            return []

        doc = nlp(text)
        chunks = []
        for sent in doc.sents:
            raw = sent.text
            normalized = re.sub(r'\s+', ' ', raw).strip().lower()
            chunks.append({
                'raw': raw,
                'normalized': normalized,
                'start': sent.start_char,
                'end': sent.end_char,
            })

        if chunks:
            return chunks

        return [{
            'raw': text,
            'normalized': re.sub(r'\s+', ' ', text).strip().lower(),
            'start': 0,
            'end': len(text),
        }]

    def _extract_paragraph_chunks(self, text):
        if not text.strip():
            return []

        chunks = []
        for match in re.finditer(r'.*?(?:\n\s*\n|$)', text, flags=re.S):
            raw = match.group(0)
            if not raw or not raw.strip():
                continue
            chunks.append({
                'raw': raw,
                'normalized': re.sub(r'\s+', ' ', raw).strip().lower(),
                'start': match.start(),
                'end': match.end(),
            })

        if chunks:
            return chunks

        return [{
            'raw': text,
            'normalized': re.sub(r'\s+', ' ', text).strip().lower(),
            'start': 0,
            'end': len(text),
        }]

    def _restore_paragraph_shape(self, original_text, candidate_text):
        """
        LLM rewrites sometimes preserve idea order but collapse blank lines.
        Restore the original paragraph count by distributing candidate
        sentences according to the source paragraph word proportions.
        """
        if not candidate_text or not candidate_text.strip():
            return candidate_text

        original_paragraphs = self._extract_paragraph_chunks(original_text or '')
        candidate_paragraphs = self._extract_paragraph_chunks(candidate_text or '')
        if len(original_paragraphs) <= 1:
            return candidate_text.strip()
        if len(candidate_paragraphs) == len(original_paragraphs):
            return '\n\n'.join(paragraph['raw'].strip() for paragraph in candidate_paragraphs)
        if len(candidate_paragraphs) > 1 and len(candidate_paragraphs) != len(original_paragraphs):
            return candidate_text.strip()

        candidate_sentences = self._extract_sentence_chunks(candidate_text)
        if len(candidate_sentences) < len(original_paragraphs):
            return candidate_text.strip()

        original_word_counts = [
            max(1, self._fragment_stats(paragraph['raw'])['word_count'])
            for paragraph in original_paragraphs
        ]
        total_original_words = max(1, sum(original_word_counts))
        candidate_sentence_word_counts = [
            max(1, self._fragment_stats(sentence['raw'])['word_count'])
            for sentence in candidate_sentences
        ]
        total_candidate_words = max(1, sum(candidate_sentence_word_counts))

        groups = []
        sentence_index = 0
        remaining_sentences = len(candidate_sentences)
        for paragraph_index, original_words in enumerate(original_word_counts):
            remaining_paragraphs = len(original_word_counts) - paragraph_index
            if paragraph_index == len(original_word_counts) - 1:
                take_count = remaining_sentences
            else:
                target_words = total_candidate_words * (original_words / total_original_words)
                running_words = 0
                take_count = 0
                while (
                    sentence_index + take_count < len(candidate_sentences) and
                    remaining_sentences - take_count > remaining_paragraphs - 1
                ):
                    next_words = candidate_sentence_word_counts[sentence_index + take_count]
                    if take_count > 0 and running_words + next_words > target_words * 1.18:
                        break
                    running_words += next_words
                    take_count += 1

                if take_count == 0:
                    take_count = 1

            sentence_group = candidate_sentences[sentence_index:sentence_index + take_count]
            if sentence_group:
                paragraph_text = candidate_text[sentence_group[0]['start']:sentence_group[-1]['end']].strip()
                groups.append(paragraph_text)
            sentence_index += take_count
            remaining_sentences = len(candidate_sentences) - sentence_index

        if len(groups) != len(original_paragraphs) or any(not group for group in groups):
            return candidate_text.strip()
        return '\n\n'.join(groups)

    @staticmethod
    def _extract_single_word(raw_text):
        stripped = (raw_text or '').strip()
        if not stripped:
            return None

        words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", stripped)
        if len(words) != 1:
            return None

        candidate = words[0]
        cleaned = re.sub(rf"^[^A-Za-z']*{re.escape(candidate)}[^A-Za-z']*$", candidate, stripped)
        if cleaned != candidate:
            return None
        return candidate

    def _fragment_stats(self, text):
        words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text or '')
        if not words:
            return {'word_count': 0, 'avg_syllables': 0.0, 'sentence_count': 0}

        avg_syllables = (
            sum(self.text_processor.count_syllables(word.lower()) for word in words) / len(words)
        )
        sentence_count = max(1, len(re.findall(r'[.!?]+', text or '')))
        return {
            'word_count': len(words),
            'avg_syllables': avg_syllables,
            'sentence_count': sentence_count,
        }

    @staticmethod
    def _normalize_visible_span(text):
        if not text:
            return 0, 0

        leading = len(text) - len(text.lstrip())
        trailing = len(text) - len(text.rstrip())
        start = leading
        end = len(text) - trailing
        if end < start:
            end = start
        return start, end

    def _word_complexity_delta(self, original_display, replacement_display):
        original_word = self._extract_single_word(original_display)
        replacement_word = self._extract_single_word(replacement_display)
        if not original_word or not replacement_word:
            return None

        original_lookup = re.sub(r"[^\w]", '', original_word).lower()
        replacement_lookup = re.sub(r"[^\w]", '', replacement_word).lower()
        if not original_lookup or not replacement_lookup:
            return None

        original_freq = zipf_frequency(original_lookup, 'en')
        replacement_freq = zipf_frequency(replacement_lookup, 'en')
        original_syllables = self.text_processor.count_syllables(original_lookup)
        replacement_syllables = self.text_processor.count_syllables(replacement_lookup)
        return (
            (original_freq - replacement_freq) +
            0.35 * (replacement_syllables - original_syllables)
        )

    def _get_review_scope(self, original_display, replacement_display, change_type):
        if change_type in ('word_replacement', 'word_upgrade'):
            original_stats = self._fragment_stats(original_display)
            replacement_stats = self._fragment_stats(replacement_display)
            max_words = max(original_stats['word_count'], replacement_stats['word_count'])
            if max_words > 15:
                return 'sentence'
            return 'word'

        if '\n\n' in (original_display or '') or '\n\n' in (replacement_display or ''):
            return 'paragraph'

        original_stats = self._fragment_stats(original_display)
        replacement_stats = self._fragment_stats(replacement_display)
        sentence_count = max(original_stats['sentence_count'], replacement_stats['sentence_count'])
        return 'sentence' if sentence_count <= STRUCTURAL_REVIEW_SENTENCE_LIMIT else 'paragraph'

    def _assess_patch_change_quality(self, original_display, replacement_display, change_type, going_up):
        review_scope = self._get_review_scope(original_display, replacement_display, change_type)
        local_going_up = self._infer_patch_direction(original_display, replacement_display, going_up)
        flags = []
        quality_score = 0.75
        original_stats = self._fragment_stats(original_display)
        replacement_stats = self._fragment_stats(replacement_display)

        if change_type in ('word_replacement', 'word_upgrade'):
            delta = self._word_complexity_delta(original_display, replacement_display)
            if delta is not None:
                quality_score = min(1.0, abs(delta) / max(WORD_QUALITY_DELTA, 0.01))
                if abs(delta) < WORD_QUALITY_DELTA:
                    flags.append('low_impact')
            if local_going_up != going_up:
                flags.append('direction_mismatch')
        else:
            should_validate_fragment = True
            if change_type in {'sentence_split', 'sentence_combine'}:
                local_word_count = max(original_stats['word_count'], replacement_stats['word_count'])
                if local_word_count <= 8:
                    should_validate_fragment = False

            if should_validate_fragment:
                invalid_sentences = self._collect_invalid_sentences(replacement_display)
                if invalid_sentences:
                    flags.append('invalid_sentence_structure')
            sentence_delta = abs(
                replacement_stats['sentence_count'] -
                original_stats['sentence_count']
            )
            quality_score = min(1.0, 0.55 + 0.15 * sentence_delta)

        accepted = not any(
            flag in {'direction_mismatch', 'invalid_sentence_structure'}
            for flag in flags
        )
        return {
            'accepted': accepted,
            'review_scope': review_scope,
            'local_going_up': local_going_up,
            'quality_flags': flags,
            'quality_score': round(max(0.0, min(1.0, quality_score)), 2),
        }

    def _infer_patch_direction(self, original_display, replacement_display, fallback_going_up):
        original_word = self._extract_single_word(original_display)
        replacement_word = self._extract_single_word(replacement_display)

        if original_word and replacement_word:
            complexity_delta = self._word_complexity_delta(original_display, replacement_display)
            if complexity_delta is None:
                complexity_delta = 0.0
            if complexity_delta > 0.15:
                return True
            if complexity_delta < -0.15:
                return False

        original_stats = self._fragment_stats(original_display)
        replacement_stats = self._fragment_stats(replacement_display)
        if original_stats['word_count'] and replacement_stats['word_count']:
            complexity_delta = (
                (replacement_stats['avg_syllables'] - original_stats['avg_syllables']) +
                0.1 * (replacement_stats['word_count'] - original_stats['word_count']) -
                0.3 * (replacement_stats['sentence_count'] - original_stats['sentence_count'])
            )
            if complexity_delta > 0.2:
                return True
            if complexity_delta < -0.2:
                return False

        return fallback_going_up

    @staticmethod
    def _approx_clause_count(text):
        """
        Rough clause-count approximation from clause-level connectors and
        sentence-final punctuation. Good enough for reason text; we don't
        need parse-tree precision here.
        """
        if not text:
            return 0
        sentence_count = max(1, len(re.findall(r'[.!?]+', text)))
        subordinators = re.findall(
            r"\b(?:because|although|though|while|whereas|since|when|if|unless|until|"
            r"before|after|as|which|who|whom|whose|that)\b",
            text,
            re.IGNORECASE,
        )
        commas = len(re.findall(r',', text))
        semicolons = len(re.findall(r';', text))
        return sentence_count + len(subordinators) + commas + semicolons

    def _extract_key_word_swaps(self, original_display, replacement_display, max_swaps=5):
        """
        Find clean single-word substitutions between two spans via word-level
        difflib. Used to enrich paragraph- and phrase-level change reasons
        with the specific word swaps the reader can see at a glance.
        """
        import difflib

        if not original_display or not replacement_display:
            return []

        original_tokens = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_display)
        replacement_tokens = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", replacement_display)
        if not original_tokens or not replacement_tokens:
            return []

        matcher = difflib.SequenceMatcher(
            None,
            [token.lower() for token in original_tokens],
            [token.lower() for token in replacement_tokens],
            autojunk=False,
        )

        swaps = []
        seen_pairs = set()

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'replace':
                continue
            if (i2 - i1) != 1 or (j2 - j1) != 1:
                continue

            before = original_tokens[i1]
            after = replacement_tokens[j1]
            before_lower = before.lower()
            after_lower = after.lower()

            if before_lower == after_lower:
                continue

            before_freq = zipf_frequency(before_lower, 'en')
            after_freq = zipf_frequency(after_lower, 'en')

            # Skip function-word churn (e.g. "the" <-> "a") — not a meaningful swap.
            if before_freq >= 6.5 and after_freq >= 6.5:
                continue

            key = (before_lower, after_lower)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)

            swaps.append({
                'before': before,
                'after': after,
                'frequency_before': round(before_freq, 2),
                'frequency_after': round(after_freq, 2),
            })
            if len(swaps) >= max_swaps:
                break

        return swaps

    def _extract_explanation_items(self, original_display, replacement_display, going_up, max_items=6):
        """
        Pull old-style explanation evidence out of broad paragraph rewrites
        without creating overlapping apply patches. These items are display
        evidence only; the paragraph patch remains the single source of truth
        for applying the selected candidate exactly.
        """
        import difflib

        original_tokens = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_display or '')
        replacement_tokens = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", replacement_display or '')
        if not original_tokens or not replacement_tokens:
            return []

        matcher = difflib.SequenceMatcher(
            None,
            [token.lower() for token in original_tokens],
            [token.lower() for token in replacement_tokens],
            autojunk=False,
        )

        items = []
        seen_pairs = set()
        function_words = {
            'a', 'an', 'the', 'and', 'or', 'but', 'so', 'for', 'nor', 'yet',
            'if', 'then', 'because', 'since', 'unless', 'though', 'although',
            'to', 'of', 'in', 'on', 'at', 'by', 'with', 'from', 'into', 'over',
            'under', 'as', 'than', 'that', 'which', 'who', 'whom', 'whose',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am', 'do',
            'does', 'did', 'has', 'have', 'had', 'will', 'would', 'can',
            'could', 'may', 'might', 'must', 'shall', 'should', 'it', 'its',
            'he', 'she', 'they', 'them', 'we', 'us', 'you', 'i', 'me', 'my',
            'his', 'her', 'their', 'our', 'your', 'this', 'these', 'those',
            'there', 'here', 'when', 'where', 'why', 'how',
        }

        def token_stats(token):
            lookup = re.sub(r"[^\w]", '', token or '').lower()
            return {
                'lookup': lookup,
                'frequency': zipf_frequency(lookup, 'en') if lookup else 0.0,
                'syllables': self.text_processor.count_syllables(lookup) if lookup else 0,
            }

        def is_useful_pair(before, after):
            before_stats = token_stats(before)
            after_stats = token_stats(after)
            if not before_stats['lookup'] or not after_stats['lookup']:
                return None
            if before_stats['lookup'] == after_stats['lookup']:
                return None
            if (before_stats['lookup'], after_stats['lookup']) in seen_pairs:
                return None
            if before_stats['lookup'] in function_words or after_stats['lookup'] in function_words:
                return None
            # Skip tiny function-word churn. It is visible, but it is not the
            # old explanation users found valuable.
            if before_stats['frequency'] >= 6.2 and after_stats['frequency'] >= 6.2:
                return None

            freq_delta = before_stats['frequency'] - after_stats['frequency']
            syl_delta = after_stats['syllables'] - before_stats['syllables']
            direction_hit = (freq_delta > 0.25 or syl_delta > 0) if going_up else (freq_delta < -0.25 or syl_delta < 0)
            if not direction_hit:
                return None

            impact = abs(freq_delta) + 0.35 * abs(syl_delta)
            if impact < 0.25:
                return None

            return {
                'kind': 'word_upgrade' if going_up else 'word_replacement',
                'before': before,
                'after': after,
                'frequency_before': round(before_stats['frequency'], 2),
                'frequency_after': round(after_stats['frequency'], 2),
                'syllables_before': before_stats['syllables'],
                'syllables_after': after_stats['syllables'],
                'impact': round(impact, 2),
                'text': self._format_explanation_item(
                    before,
                    after,
                    before_stats['frequency'],
                    after_stats['frequency'],
                    before_stats['syllables'],
                    after_stats['syllables'],
                    going_up,
                ),
            }

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if len(items) >= max_items:
                break
            if tag == 'equal':
                continue
            if tag == 'insert':
                inserted = [
                    token for token in replacement_tokens[j1:j2]
                    if token.lower() in {
                        'consequently', 'subsequently', 'therefore', 'however',
                        'furthermore', 'moreover', 'although', 'during', 'while'
                    }
                ]
                for token in inserted:
                    if len(items) >= max_items:
                        break
                    items.append({
                        'kind': 'connector_added',
                        'before': '',
                        'after': token,
                        'text': f"Added connector '{token}' to make relationships between ideas more explicit.",
                    })
                continue
            if tag != 'replace':
                continue

            before_block = original_tokens[i1:i2]
            after_block = replacement_tokens[j1:j2]
            candidates = []
            used_after = set()

            if len(before_block) == len(after_block):
                for before, after in zip(before_block, after_block):
                    item = is_useful_pair(before, after)
                    if item:
                        candidates.append(item)
            else:
                for before in before_block:
                    best_item = None
                    best_index = None
                    for after_index, after in enumerate(after_block):
                        if after_index in used_after:
                            continue
                        item = is_useful_pair(before, after)
                        if not item:
                            continue
                        if best_item is None or item['impact'] > best_item['impact']:
                            best_item = item
                            best_index = after_index
                    if best_item:
                        used_after.add(best_index)
                        candidates.append(best_item)

            candidates.sort(key=lambda item: item.get('impact', 0), reverse=True)
            for item in candidates:
                if len(items) >= max_items:
                    break
                seen_pairs.add((item['before'].lower(), item['after'].lower()))
                items.append(item)

        return items

    def _enrich_changes_with_display_items(self, changes, display_items):
        """Copy explanation metadata from display items onto the composable patches."""
        word_items = [d for d in display_items if d.get('review_scope') == 'word']
        for change in changes:
            if change.get('review_scope') != 'word':
                continue
            for item in word_items:
                if item.get('start') == change.get('start') and item.get('end') == change.get('end'):
                    if item.get('explanation_items'):
                        change['explanation_items'] = item['explanation_items']
                    if item.get('reason') and not change.get('reason'):
                        change['reason'] = item['reason']
                    break

    def _build_display_changes(self, original_text, rewritten_text, target_grade, going_up):
        """
        Post-processing diff: compare original and final rewritten text
        paragraph-by-paragraph to extract granular display changes.
        Runs after all rewriting is complete — purely for UI display.
        Each word swap becomes its own top-level change.
        """
        orig_paragraphs = [p.strip() for p in re.split(r'\n\s*\n', original_text) if p.strip()]
        new_paragraphs = [p.strip() for p in re.split(r'\n\s*\n', rewritten_text) if p.strip()]

        if not orig_paragraphs or not new_paragraphs:
            return []

        pairs = list(zip(orig_paragraphs, new_paragraphs))
        if len(orig_paragraphs) > len(new_paragraphs):
            last_orig = '\n\n'.join(orig_paragraphs[len(new_paragraphs) - 1:])
            pairs[-1] = (last_orig, pairs[-1][1])
        elif len(new_paragraphs) > len(orig_paragraphs):
            last_new = '\n\n'.join(new_paragraphs[len(orig_paragraphs) - 1:])
            pairs[-1] = (pairs[-1][0], last_new)

        changes = []
        change_id = 0
        orig_offset = 0
        new_offset = 0
        grade_label = f"Grade {target_grade}" if target_grade <= 12 else "College"
        candidate_score = self._selection_context.get('candidate_score', 0.8)

        for orig_para, new_para in pairs:
            orig_start = original_text.find(orig_para, orig_offset)
            new_start = rewritten_text.find(new_para, new_offset)
            if orig_start == -1:
                orig_start = orig_offset
            if new_start == -1:
                new_start = new_offset

            if orig_para == new_para:
                orig_offset = orig_start + len(orig_para)
                new_offset = new_start + len(new_para)
                continue

            explanation_items = self._extract_explanation_items(
                orig_para, new_para, going_up, max_items=30
            )

            for item in explanation_items:
                word_before = item['before']
                word_after = item['after']
                word_pos = orig_para.lower().find(word_before.lower())
                preview_pos = new_para.lower().find(word_after.lower())

                abs_start = orig_start + (word_pos if word_pos != -1 else 0)
                abs_preview = new_start + (preview_pos if preview_pos != -1 else 0)

                reason = self._format_explanation_item(
                    word_before, word_after,
                    item.get('frequency_before', 0), item.get('frequency_after', 0),
                    item.get('syllables_before', 0), item.get('syllables_after', 0),
                    going_up,
                )

                changes.append({
                    'type': item['kind'],
                    'original': word_before,
                    'simplified': word_after,
                    'original_text': word_before,
                    'replacement_text': word_after,
                    'position': abs_start,
                    'start': abs_start,
                    'end': abs_start + len(word_before),
                    'preview_start': abs_preview,
                    'preview_end': abs_preview + len(word_after),
                    'review_scope': 'word',
                    'direction': 'up' if going_up else 'down',
                    'quality_score': 0.8,
                    'quality_flags': [],
                    'rule_id': 'display.word_upgrade' if going_up else 'display.word_swap',
                    'reason_code': 'raise_vocabulary_difficulty' if going_up else 'use_more_common_word',
                    'evidence': {
                        'target_grade': target_grade,
                        'direction': 'up' if going_up else 'down',
                        'review_scope': 'word',
                        'word_before': word_before,
                        'word_after': word_after,
                        'frequency_before': item.get('frequency_before', 0),
                        'frequency_after': item.get('frequency_after', 0),
                        'syllables_before': item.get('syllables_before', 0),
                        'syllables_after': item.get('syllables_after', 0),
                        'candidate_score': candidate_score,
                    },
                    'candidate_score': candidate_score,
                    'reason': reason,
                    'id': change_id,
                })
                change_id += 1

            orig_sentences = len(re.findall(r'[.!?]+', orig_para)) or 1
            new_sentences = len(re.findall(r'[.!?]+', new_para)) or 1
            if orig_sentences != new_sentences:
                struct_type = 'sentence_combine' if going_up else 'sentence_split'
                struct_details = []
                orig_semicolons = orig_para.count(';')
                new_semicolons = new_para.count(';')
                if new_semicolons > orig_semicolons:
                    struct_details.append(f"{new_semicolons - orig_semicolons} semicolon(s) inserted to join independent clauses")
                elif orig_semicolons > new_semicolons:
                    struct_details.append(f"{orig_semicolons - new_semicolons} semicolon(s) replaced with periods")
                if new_sentences < orig_sentences:
                    struct_details.append(f"{orig_sentences - new_sentences} sentence(s) combined into longer clauses")
                elif new_sentences > orig_sentences:
                    struct_details.append(f"{new_sentences - orig_sentences} sentence(s) split for shorter, clearer phrasing")
                struct_reason = "; ".join(struct_details) + f" ({orig_sentences} → {new_sentences} sentences)." if struct_details else f"Sentence structure changed ({orig_sentences} → {new_sentences} sentences)."

                changes.append({
                    'type': struct_type,
                    'original': '',
                    'simplified': '',
                    'original_text': orig_para,
                    'replacement_text': new_para,
                    'position': orig_start,
                    'start': orig_start,
                    'end': orig_start + len(orig_para),
                    'preview_start': new_start,
                    'preview_end': new_start + len(new_para),
                    'review_scope': 'sentence',
                    'direction': 'up' if going_up else 'down',
                    'quality_score': 0.8,
                    'quality_flags': [],
                    'rule_id': 'display.sentence_split' if not going_up else 'display.sentence_combine',
                    'reason_code': 'shorten_sentence_for_target' if not going_up else 'increase_clause_density',
                    'evidence': {
                        'target_grade': target_grade,
                        'direction': 'up' if going_up else 'down',
                        'review_scope': 'sentence',
                        'sentence_count_before': orig_sentences,
                        'sentence_count_after': new_sentences,
                        'candidate_score': candidate_score,
                    },
                    'candidate_score': candidate_score,
                    'reason': struct_reason,
                    'id': change_id,
                })
                change_id += 1

            orig_offset = orig_start + len(orig_para)
            new_offset = new_start + len(new_para)

        return changes

    @staticmethod
    def _format_explanation_item(before, after, freq_before, freq_after, syl_before, syl_after, going_up):
        if going_up:
            return (
                f"Replaced '{before}' with '{after}' — more formal/academic "
                f"(Zipf {freq_before:.1f} -> {freq_after:.1f}, "
                f"{syl_before} -> {syl_after} syllable(s))."
            )
        return (
            f"Replaced '{before}' with '{after}' — easier and more familiar "
            f"(Zipf {freq_before:.1f} -> {freq_after:.1f}, "
            f"{syl_before} -> {syl_after} syllable(s))."
        )

    def _build_reason_metadata(
        self,
        original_display,
        replacement_display,
        target_grade,
        going_up,
        change_type,
        review_scope,
        quality,
    ):
        original_stats = self._fragment_stats(original_display)
        replacement_stats = self._fragment_stats(replacement_display)
        local_going_up = quality['local_going_up']
        candidate_score = self._selection_context.get('candidate_score')

        metadata = {
            'rule_id': 'selection.patch_rewrite',
            'reason_code': 'reshape_text_for_target',
            'evidence': {
                'target_grade': target_grade,
                'direction': 'up' if local_going_up else 'down',
                'review_scope': review_scope,
                'word_count_before': original_stats['word_count'],
                'word_count_after': replacement_stats['word_count'],
                'sentence_count_before': original_stats['sentence_count'],
                'sentence_count_after': replacement_stats['sentence_count'],
                'boundary_count_before': len(re.findall(r'[.!?]+', original_display or '')),
                'boundary_count_after': len(re.findall(r'[.!?]+', replacement_display or '')),
                'clause_count_before': self._approx_clause_count(original_display),
                'clause_count_after': self._approx_clause_count(replacement_display),
                'avg_syllables_before': round(original_stats['avg_syllables'], 2),
                'avg_syllables_after': round(replacement_stats['avg_syllables'], 2),
                'candidate_score': candidate_score if candidate_score is not None else quality['quality_score'],
            },
        }

        if change_type in ('word_replacement', 'word_upgrade'):
            original_word = self._extract_single_word(original_display) or original_display.strip()
            replacement_word = self._extract_single_word(replacement_display) or replacement_display.strip()
            original_lookup = re.sub(r"[^\w]", '', original_word).lower()
            replacement_lookup = re.sub(r"[^\w]", '', replacement_word).lower()
            original_freq = zipf_frequency(original_lookup, 'en') if original_lookup else 0.0
            replacement_freq = zipf_frequency(replacement_lookup, 'en') if replacement_lookup else 0.0
            original_syllables = self.text_processor.count_syllables(original_lookup) if original_lookup else 0
            replacement_syllables = self.text_processor.count_syllables(replacement_lookup) if replacement_lookup else 0
            metadata.update({
                'rule_id': 'lexical.academic_upgrade' if local_going_up else 'lexical.common_word_swap',
                'reason_code': 'raise_vocabulary_difficulty' if local_going_up else 'use_more_common_word',
                'evidence': {
                    **metadata['evidence'],
                    'word_before': original_word,
                    'word_after': replacement_word,
                    'frequency_before': round(original_freq, 2),
                    'frequency_after': round(replacement_freq, 2),
                    'syllables_before': original_syllables,
                    'syllables_after': replacement_syllables,
                },
            })
            return metadata

        structural_explanation_items = self._extract_explanation_items(
            original_display,
            replacement_display,
            local_going_up,
        ) if review_scope == 'paragraph' else []

        if change_type == 'sentence_split':
            metadata.update({
                'rule_id': 'syntactic.sentence_split',
                'reason_code': 'shorten_sentence_for_target',
                'evidence': {
                    **metadata['evidence'],
                    'explanation_items': structural_explanation_items,
                },
            })
            return metadata

        if change_type == 'sentence_combine':
            metadata.update({
                'rule_id': 'syntactic.sentence_combine',
                'reason_code': 'increase_clause_density',
                'evidence': {
                    **metadata['evidence'],
                    'explanation_items': structural_explanation_items,
                },
            })
            return metadata

        key_swaps = self._extract_key_word_swaps(original_display, replacement_display)
        explanation_items = structural_explanation_items or self._extract_explanation_items(
            original_display,
            replacement_display,
            local_going_up,
        )
        metadata.update({
            'rule_id': 'discourse.connector_rewrite' if review_scope == 'sentence' else 'discourse.paragraph_reframe',
            'reason_code': 'improve_flow_for_target',
            'evidence': {
                **metadata['evidence'],
                'key_swaps': key_swaps,
                'explanation_items': explanation_items,
            },
        })
        return metadata

    def _build_patch_reason(self, metadata):
        evidence = metadata['evidence']
        target_grade = evidence['target_grade']
        target_label = self._target_grade_label(target_grade)
        reason_code = metadata['reason_code']
        review_scope = evidence.get('review_scope', 'sentence')
        scope_label = 'paragraph' if review_scope == 'paragraph' else 'sentence'
        direction = evidence.get('direction', 'down')

        if reason_code in {'use_more_common_word', 'raise_vocabulary_difficulty'}:
            word_before = evidence['word_before']
            word_after = evidence['word_after']
            freq_before = evidence.get('frequency_before', 0.0)
            freq_after = evidence.get('frequency_after', 0.0)
            syl_before = evidence.get('syllables_before', 0)
            syl_after = evidence.get('syllables_after', 0)

            if reason_code == 'use_more_common_word':
                return (
                    f"Replaced '{word_before}' with '{word_after}' — '{word_after}' is a more common, "
                    f"easier synonym (zipf frequency {freq_after:.1f} vs {freq_before:.1f}, "
                    f"{syl_after} syllable(s) vs {syl_before}) that {target_label} readers recognize quickly."
                )
            return (
                f"Replaced '{word_before}' with '{word_after}' — '{word_after}' is a more formal, academic "
                f"synonym (less common, zipf frequency {freq_after:.1f} vs {freq_before:.1f}, "
                f"{syl_after} syllable(s) vs {syl_before}) expected at {target_label}."
            )

        clauses_before = evidence.get('clause_count_before', evidence['sentence_count_before'])
        clauses_after = evidence.get('clause_count_after', evidence['sentence_count_after'])
        words_before = evidence.get('word_count_before', 0)

        if reason_code == 'shorten_sentence_for_target':
            if review_scope == 'paragraph':
                explanation_items = evidence.get('explanation_items') or []
                if explanation_items:
                    examples = "; ".join(item.get('text', '') for item in explanation_items[:3] if item.get('text'))
                    return (
                        f"Split and simplified this paragraph for {target_label}: "
                        f"sentence structure became easier ({clauses_before} -> {clauses_after} clause units), "
                        f"with concrete vocabulary evidence such as {examples}"
                    )
                return (
                    f"Restructured this paragraph into shorter sentence units so the ideas are easier "
                    f"to follow at {target_label}."
                )
            return (
                f"Split the sentence because it was long ({words_before} words with about "
                f"{clauses_before} clauses) — too much subordination to follow at {target_label}. "
                f"Shorter sentences with fewer clauses are easier to read."
            )

        if reason_code == 'increase_clause_density':
            if review_scope == 'paragraph':
                explanation_items = evidence.get('explanation_items') or []
                if explanation_items:
                    examples = "; ".join(item.get('text', '') for item in explanation_items[:3] if item.get('text'))
                    return (
                        f"Combined and upgraded this paragraph for {target_label}: "
                        f"sentence structure became denser ({clauses_before} -> {clauses_after} clause units), "
                        f"with concrete vocabulary evidence such as {examples}"
                    )
                return (
                    f"Restructured this paragraph into denser sentence groupings so the ideas read "
                    f"at {target_label} complexity."
                )
            return (
                f"Combined short sentences into one with about {clauses_after} clauses — "
                f"{target_label} expects denser subordination and longer sentences, "
                f"so merging related ideas raises the complexity to fit."
            )

        swaps = evidence.get('key_swaps') or []
        explanation_items = evidence.get('explanation_items') or []
        action = 'Raised' if direction == 'up' else 'Simplified'

        if explanation_items:
            examples = "; ".join(item.get('text', '') for item in explanation_items[:3] if item.get('text'))
            clause_delta = ''
            if clauses_before != clauses_after:
                direction_verb = 'raising' if clauses_after > clauses_before else 'reducing'
                clause_delta = (
                    f" Clause structure also changed ({clauses_before} -> {clauses_after}), "
                    f"{direction_verb} sentence complexity."
                )
            return (
                f"{action} this {scope_label} for {target_label} with visible word-level evidence: "
                f"{examples}{clause_delta}"
            )

        if swaps:
            def _format_swap(swap):
                fa = swap.get('frequency_after')
                fb = swap.get('frequency_before')
                if fa is not None and fb is not None:
                    return f"'{swap['before']}' -> '{swap['after']}' (freq {fb:.1f} -> {fa:.1f})"
                return f"'{swap['before']}' -> '{swap['after']}'"

            formatted = ", ".join(_format_swap(swap) for swap in swaps[:5])
            clause_delta = ''
            if clauses_before != clauses_after:
                direction_verb = 'raising' if clauses_after > clauses_before else 'reducing'
                clause_delta = (
                    f" Also restructured clauses ({clauses_before} -> {clauses_after}), "
                    f"{direction_verb} sentence complexity for the target."
                )
            synonym_rationale = (
                'more common, easier synonyms' if direction == 'down' else 'more formal, academic synonyms'
            )
            return (
                f"{action} the vocabulary in this {scope_label} with {synonym_rationale} for {target_label}. "
                f"Replaced: {formatted}.{clause_delta}"
            )

        if clauses_before != clauses_after:
            direction_verb = 'raising' if clauses_after > clauses_before else 'reducing'
            return (
                f"Restructured clauses in this {scope_label} ({clauses_before} -> {clauses_after}), "
                f"{direction_verb} sentence complexity to fit {target_label}."
            )

        avg_syl_before = evidence.get('avg_syllables_before', 0.0)
        avg_syl_after = evidence.get('avg_syllables_after', 0.0)
        words_after = evidence.get('word_count_after', words_before)
        if direction == 'up':
            return (
                f"Rephrased this {scope_label} to sound more formal and academically dense for {target_label} "
                f"(avg syllables {avg_syl_before:.2f} -> {avg_syl_after:.2f}, edited span {words_before} -> {words_after} words)."
            )
        return (
            f"Rephrased this {scope_label} to use clearer, more familiar wording for {target_label} "
            f"(avg syllables {avg_syl_before:.2f} -> {avg_syl_after:.2f}, edited span {words_before} -> {words_after} words)."
        )

    def _classify_patch_change(self, original_display, replacement_display, going_up):
        original_word = self._extract_single_word(original_display)
        replacement_word = self._extract_single_word(replacement_display)
        if original_word and replacement_word and original_word.lower() != replacement_word.lower():
            return (
                'word_upgrade'
                if self._infer_patch_direction(original_display, replacement_display, going_up)
                else 'word_replacement'
            )

        original_sentences = len(re.findall(r'[.!?]+', original_display or ''))
        replacement_sentences = len(re.findall(r'[.!?]+', replacement_display or ''))
        if replacement_sentences > original_sentences:
            return 'sentence_split'
        if replacement_sentences < original_sentences:
            return 'sentence_combine'

        return 'phrase_rewrite'

    @staticmethod
    def _extract_patch_words(text):
        return re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text or '')

    def _is_low_signal_patch_change(
        self,
        original_display,
        replacement_display,
        change_type,
        review_scope,
        allow_fallback=False,
    ):
        original_words = self._extract_patch_words(original_display)
        replacement_words = self._extract_patch_words(replacement_display)
        original_core = [word.lower() for word in original_words]
        replacement_core = [word.lower() for word in replacement_words]
        boundary_changed = (
            bool(re.search(r'[.!?]+$', original_display or '')) !=
            bool(re.search(r'[.!?]+$', replacement_display or ''))
        )

        if original_core == replacement_core and not boundary_changed:
            return True

        max_words = max(len(original_words), len(replacement_words))
        min_words = min(len(original_words), len(replacement_words))

        if change_type == 'phrase_rewrite' and max_words <= 1:
            return True

        if not allow_fallback:
            return False

        if change_type == 'phrase_rewrite' and review_scope == 'paragraph':
            if max_words <= 4:
                return True
            if min_words <= 1 and max_words <= 6:
                return True
            if min_words == 0 and max_words <= 6:
                return True

        contentful_before = [
            word for word in original_words
            if zipf_frequency(word.lower(), 'en') < 5.8
        ]
        contentful_after = [
            word for word in replacement_words
            if zipf_frequency(word.lower(), 'en') < 5.8
        ]
        if not contentful_before and not contentful_after and max_words <= 4:
            return True

        return False

    def _build_patch_change(
        self,
        original_raw,
        replacement_raw,
        start,
        end,
        preview_start,
        target_grade,
        going_up,
        allow_fallback=False
    ):
        if original_raw == replacement_raw:
            return None

        original_display = original_raw.strip() or original_raw
        replacement_display = replacement_raw.strip() or replacement_raw

        if not original_display and not replacement_display:
            return None

        change_type = self._classify_patch_change(original_display, replacement_display, going_up)
        quality = self._assess_patch_change_quality(
            original_display,
            replacement_display,
            change_type,
            going_up
        )
        if not quality['accepted'] and not allow_fallback:
            return None
        if allow_fallback and not quality['accepted']:
            quality = {
                **quality,
                'review_scope': 'paragraph',
                'quality_flags': quality['quality_flags'] + ['coarse_review'],
                'quality_score': min(quality['quality_score'], 0.35),
            }

        if self._is_low_signal_patch_change(
            original_display,
            replacement_display,
            change_type,
            quality['review_scope'],
            allow_fallback=allow_fallback,
        ):
            return None

        visible_preview_start, visible_preview_end = self._normalize_visible_span(replacement_raw)
        metadata = self._build_reason_metadata(
            original_display,
            replacement_display,
            target_grade,
            going_up,
            change_type,
            quality['review_scope'],
            quality,
        )
        top_candidates = self._selection_context.get('selection_summary', {}).get('top_candidates', [])
        selection_flags = list((top_candidates[0] if top_candidates else {}).get('validation_flags', []))
        validation_flags = quality['quality_flags'] + [
            flag for flag in selection_flags if flag not in quality['quality_flags']
        ]

        return {
            'type': change_type,
            'original': original_display,
            'simplified': replacement_display,
            'original_text': original_raw,
            'replacement_text': replacement_raw,
            'position': start,
            'start': start,
            'end': end,
            'preview_start': preview_start + visible_preview_start,
            'preview_end': preview_start + visible_preview_end,
            'review_scope': quality['review_scope'],
            'direction': 'up' if quality['local_going_up'] else 'down',
            'quality_score': quality['quality_score'],
            'quality_flags': quality['quality_flags'],
            'rule_id': metadata['rule_id'],
            'reason_code': metadata['reason_code'],
            'evidence': metadata['evidence'],
            'candidate_score': metadata['evidence']['candidate_score'],
            'validation_flags': validation_flags,
            'explanation_items': metadata['evidence'].get('explanation_items', []),
            'reason': self._build_patch_reason(metadata),
        }

    def _assign_dependency_groups(self, changes):
        if not changes:
            return changes

        group_ids = {}
        structural_changes = sorted(
            [
                change for change in changes
                if change.get('type') in {'sentence_split', 'sentence_combine'}
            ],
            key=lambda change: (change.get('start', 0), change.get('end', 0), change.get('id', 0)),
        )
        current_group = []
        group_index = 0

        def flush_group():
            nonlocal group_index
            if len(current_group) <= 1:
                return
            group_index += 1
            group_id = f"struct-{group_index}"
            for grouped_change in current_group:
                group_ids[grouped_change['id']] = group_id

        for change in structural_changes:
            if not current_group:
                current_group = [change]
                continue

            previous = current_group[-1]
            overlaps = (
                change.get('start', 0) < previous.get('end', 0) and
                previous.get('start', 0) < change.get('end', 0)
            )
            if overlaps and change.get('direction') == previous.get('direction'):
                current_group.append(change)
                continue

            flush_group()
            current_group = [change]

        flush_group()

        grouped_changes = []
        for change in changes:
            updated = dict(change)
            dependency_group_id = group_ids.get(change['id'])
            if dependency_group_id:
                updated['dependency_group_id'] = dependency_group_id
            grouped_changes.append(updated)

        return grouped_changes

    @staticmethod
    def _chunk_pair_has_meaningful_diff(original_chunk, rewritten_chunk):
        if original_chunk['raw'] == rewritten_chunk['raw']:
            return False

        original_display = (original_chunk.get('display') or '').strip()
        rewritten_display = (rewritten_chunk.get('display') or '').strip()
        if original_display == rewritten_display:
            return False

        original_boundary = bool(re.search(r'[.!?]+$', original_display))
        rewritten_boundary = bool(re.search(r'[.!?]+$', rewritten_display))
        if original_boundary != rewritten_boundary:
            return True

        original_core = re.sub(r"[^A-Za-z0-9']+", '', original_display).lower()
        rewritten_core = re.sub(r"[^A-Za-z0-9']+", '', rewritten_display).lower()
        return original_core != rewritten_core

    def _collect_local_patch_segments(self, opcodes, original_chunks, rewritten_chunks):
        segments = []

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                chunk_count = min(i2 - i1, j2 - j1)
                run_start = None

                for offset in range(chunk_count):
                    if self._chunk_pair_has_meaningful_diff(
                        original_chunks[i1 + offset],
                        rewritten_chunks[j1 + offset],
                    ):
                        if run_start is None:
                            run_start = offset
                    elif run_start is not None:
                        segments.append((
                            i1 + run_start,
                            i1 + offset,
                            j1 + run_start,
                            j1 + offset,
                        ))
                        run_start = None

                if run_start is not None:
                    segments.append((
                        i1 + run_start,
                        i1 + chunk_count,
                        j1 + run_start,
                        j1 + chunk_count,
                    ))
                continue

            segments.append((i1, i2, j1, j2))

        if not segments:
            return []

        merged_segments = [list(segments[0])]
        for i1, i2, j1, j2 in segments[1:]:
            previous = merged_segments[-1]
            if i1 <= previous[1] + 1 and j1 <= previous[3] + 1:
                previous[1] = max(previous[1], i2)
                previous[3] = max(previous[3], j2)
            else:
                merged_segments.append([i1, i2, j1, j2])

        return [tuple(segment) for segment in merged_segments]

    def _diff_change_block(
        self,
        original_block,
        rewritten_block,
        target_grade,
        going_up,
        original_offset=0,
        rewritten_offset=0,
        prefer_sentence_level=False,
    ):
        import difflib

        if original_block == rewritten_block:
            return []

        original_chunks = self._extract_diff_chunks(original_block)
        rewritten_chunks = self._extract_diff_chunks(rewritten_block)

        if not original_chunks or not rewritten_chunks:
            change = self._build_patch_change(
                original_block,
                rewritten_block,
                original_offset,
                original_offset + len(original_block),
                rewritten_offset,
                target_grade,
                going_up,
                allow_fallback=True
            )
            return [change] if change else []

        matcher = difflib.SequenceMatcher(
            None,
            [chunk['normalized_cased'] for chunk in original_chunks],
            [chunk['normalized_cased'] for chunk in rewritten_chunks],
            autojunk=False
        )
        opcodes = matcher.get_opcodes()
        segments = self._collect_local_patch_segments(opcodes, original_chunks, rewritten_chunks)
        if not segments:
            change = self._build_patch_change(
                original_block,
                rewritten_block,
                original_offset,
                original_offset + len(original_block),
                rewritten_offset,
                target_grade,
                going_up,
                allow_fallback=True
            )
            return [change] if change else []

        changes = []
        original_length = len(original_block)
        rewritten_length = len(rewritten_block)
        original_boundary_count = len(re.findall(r'[.!?]+', original_block or ''))
        rewritten_boundary_count = len(re.findall(r'[.!?]+', rewritten_block or ''))

        for i1, i2, j1, j2 in segments:
            local_start = original_chunks[i1]['start'] if i1 < len(original_chunks) else original_length
            local_end = original_chunks[i2 - 1]['end'] if i2 > i1 else local_start
            local_preview_start = rewritten_chunks[j1]['start'] if j1 < len(rewritten_chunks) else rewritten_length
            local_preview_end = rewritten_chunks[j2 - 1]['end'] if j2 > j1 else local_preview_start

            change = self._build_patch_change(
                original_block[local_start:local_end],
                rewritten_block[local_preview_start:local_preview_end],
                original_offset + local_start,
                original_offset + local_end,
                rewritten_offset + local_preview_start,
                target_grade,
                going_up
            )
            if not change:
                change = self._build_patch_change(
                    original_block[local_start:local_end],
                    rewritten_block[local_preview_start:local_preview_end],
                    original_offset + local_start,
                    original_offset + local_end,
                    rewritten_offset + local_preview_start,
                    target_grade,
                    going_up,
                    allow_fallback=True
                )
            if change:
                if (
                    change.get('type') == 'phrase_rewrite' and
                    change.get('review_scope') == 'sentence' and
                    original_boundary_count != rewritten_boundary_count
                ):
                    change = self._retag_boundary_change(
                        change,
                        target_grade=target_grade,
                        original_boundary_count=original_boundary_count,
                        rewritten_boundary_count=rewritten_boundary_count,
                    )
                changes.append(change)

        if not changes:
            change = self._build_patch_change(
                original_block,
                rewritten_block,
                original_offset,
                original_offset + len(original_block),
                rewritten_offset,
                target_grade,
                going_up,
                allow_fallback=True
            )
            return [change] if change else []

        return changes

    @staticmethod
    def _retag_boundary_change(change, target_grade, original_boundary_count, rewritten_boundary_count):
        updated = dict(change)
        split = rewritten_boundary_count > original_boundary_count
        target_label = 'College' if target_grade >= 13 else f'Grade {target_grade}'
        updated['type'] = 'sentence_split' if split else 'sentence_combine'
        updated['rule_id'] = 'syntactic.sentence_split' if split else 'syntactic.sentence_combine'
        updated['reason_code'] = 'shorten_sentence_for_target' if split else 'increase_clause_density'
        evidence = dict(updated.get('evidence') or {})
        evidence.update({
            'boundary_count_before': original_boundary_count,
            'boundary_count_after': rewritten_boundary_count,
        })
        updated['evidence'] = evidence
        if split:
            updated['reason'] = (
                f"Created a clearer sentence break for {target_label} readers "
                f"({original_boundary_count} -> {rewritten_boundary_count} sentence boundary markers), "
                "while preserving the surrounding wording."
            )
        else:
            updated['reason'] = (
                f"Combined nearby sentence units for {target_label} complexity "
                f"({original_boundary_count} -> {rewritten_boundary_count} sentence boundary markers), "
                "while preserving the surrounding wording."
            )
        return updated

    def _diff_uneven_sentence_group_by_order(
        self,
        original_text,
        rewritten_text,
        original_sentences,
        rewritten_sentences,
        target_grade,
        going_up,
        original_offset,
        rewritten_offset,
    ):
        original_count = len(original_sentences)
        rewritten_count = len(rewritten_sentences)
        if not original_count or not rewritten_count or original_count == rewritten_count:
            return []

        changes = []

        def proportional_bounds(index, source_count, target_count):
            start = round(index * target_count / source_count)
            end = round((index + 1) * target_count / source_count)
            start = max(0, min(target_count, start))
            end = max(start + 1, min(target_count, end))
            return start, end

        if rewritten_count > original_count:
            for original_index, original_sentence in enumerate(original_sentences):
                rewritten_start_index, rewritten_end_index = proportional_bounds(
                    original_index,
                    original_count,
                    rewritten_count,
                )
                rewritten_group = rewritten_sentences[rewritten_start_index:rewritten_end_index]
                if not rewritten_group:
                    continue

                change = self._build_patch_change(
                    original_sentence['raw'],
                    rewritten_text[rewritten_group[0]['start']:rewritten_group[-1]['end']],
                    original_offset + original_sentence['start'],
                    original_offset + original_sentence['end'],
                    rewritten_offset + rewritten_group[0]['start'],
                    target_grade,
                    going_up,
                    allow_fallback=True,
                )
                if change:
                    changes.append(change)
            return changes

        for rewritten_index, rewritten_sentence in enumerate(rewritten_sentences):
            original_start_index, original_end_index = proportional_bounds(
                rewritten_index,
                rewritten_count,
                original_count,
            )
            original_group = original_sentences[original_start_index:original_end_index]
            if not original_group:
                continue

            change = self._build_patch_change(
                original_text[original_group[0]['start']:original_group[-1]['end']],
                rewritten_sentence['raw'],
                original_offset + original_group[0]['start'],
                original_offset + original_group[-1]['end'],
                rewritten_offset + rewritten_sentence['start'],
                target_grade,
                going_up,
                allow_fallback=True,
            )
            if change:
                changes.append(change)

        return changes

    def _diff_sentence_changes(
        self,
        original_text,
        rewritten_text,
        target_grade,
        going_up,
        original_offset=0,
        rewritten_offset=0,
        prefer_sentence_level=False,
    ):
        """Diff a paragraph-sized block sentence-by-sentence."""
        import difflib

        if original_text == rewritten_text:
            return []

        original_sentences = self._extract_sentence_chunks(original_text)
        rewritten_sentences = self._extract_sentence_chunks(rewritten_text)

        if not original_sentences or not rewritten_sentences:
            return self._diff_change_block(
                original_text,
                rewritten_text,
                target_grade,
                going_up,
                original_offset=original_offset,
                rewritten_offset=rewritten_offset,
                prefer_sentence_level=prefer_sentence_level,
            )

        matcher = difflib.SequenceMatcher(
            None,
            [sentence['normalized'] for sentence in original_sentences],
            [sentence['normalized'] for sentence in rewritten_sentences],
            autojunk=False
        )

        changes = []
        original_length = len(original_text)
        rewritten_length = len(rewritten_text)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue

            sentence_aligned_changes = self._diff_sentence_block_by_order(
                original_text=original_text,
                rewritten_text=rewritten_text,
                original_sentences=original_sentences[i1:i2],
                rewritten_sentences=rewritten_sentences[j1:j2],
                target_grade=target_grade,
                going_up=going_up,
                original_offset=original_offset,
                rewritten_offset=rewritten_offset,
            )
            if sentence_aligned_changes:
                changes.extend(sentence_aligned_changes)
                continue

            original_start = original_sentences[i1]['start'] if i1 < len(original_sentences) else original_length
            original_end = original_sentences[i2 - 1]['end'] if i2 > i1 else original_start
            rewritten_start = rewritten_sentences[j1]['start'] if j1 < len(rewritten_sentences) else rewritten_length
            rewritten_end = rewritten_sentences[j2 - 1]['end'] if j2 > j1 else rewritten_start
            original_span_count = i2 - i1
            rewritten_span_count = j2 - j1

            if original_span_count != rewritten_span_count:
                ordered_structural_changes = self._diff_uneven_sentence_group_by_order(
                    original_text=original_text,
                    rewritten_text=rewritten_text,
                    original_sentences=original_sentences[i1:i2],
                    rewritten_sentences=rewritten_sentences[j1:j2],
                    target_grade=target_grade,
                    going_up=going_up,
                    original_offset=original_offset,
                    rewritten_offset=rewritten_offset,
                )
                if ordered_structural_changes:
                    changes.extend(ordered_structural_changes)
                    continue

                structural_change = self._build_patch_change(
                    original_text[original_start:original_end],
                    rewritten_text[rewritten_start:rewritten_end],
                    original_offset + original_start,
                    original_offset + original_end,
                    rewritten_offset + rewritten_start,
                    target_grade,
                    going_up,
                    allow_fallback=True,
                )
                if structural_change:
                    changes.append(structural_change)
                    continue

            block_changes = self._diff_change_block(
                original_text[original_start:original_end],
                rewritten_text[rewritten_start:rewritten_end],
                target_grade,
                going_up,
                original_offset=original_offset + original_start,
                rewritten_offset=rewritten_offset + rewritten_start,
                prefer_sentence_level=prefer_sentence_level,
            )

            if not block_changes:
                change = self._build_patch_change(
                    original_text[original_start:original_end],
                    rewritten_text[rewritten_start:rewritten_end],
                    original_offset + original_start,
                    original_offset + original_end,
                    rewritten_offset + rewritten_start,
                    target_grade,
                    going_up,
                    allow_fallback=True
                )
                if change:
                    block_changes = [change]

            changes.extend(block_changes)

        return changes

    def _diff_sentence_block_by_order(
        self,
        original_text,
        rewritten_text,
        original_sentences,
        rewritten_sentences,
        target_grade,
        going_up,
        original_offset=0,
        rewritten_offset=0,
    ):
        if not original_sentences or not rewritten_sentences:
            return None

        pairings = []
        original_count = len(original_sentences)
        rewritten_count = len(rewritten_sentences)

        if original_count == rewritten_count:
            for index in range(original_count):
                pairings.append((index, index, 1, 1))
        elif rewritten_count == original_count + 1 and original_count >= 2:
            for index in range(original_count - 1):
                pairings.append((index, index, 1, 1))
            pairings.append((original_count - 1, original_count - 1, 1, 2))
        elif original_count == rewritten_count + 1 and rewritten_count >= 2:
            for index in range(rewritten_count - 1):
                pairings.append((index, index, 1, 1))
            pairings.append((rewritten_count - 1, rewritten_count - 1, 2, 1))
        else:
            return None

        changes = []
        llm_pairs = []
        pair_to_change_index = {}

        for original_index, rewritten_index, original_span_count, rewritten_span_count in pairings:
            original_start = original_sentences[original_index]['start']
            original_end = original_sentences[original_index + original_span_count - 1]['end']
            rewritten_start = rewritten_sentences[rewritten_index]['start']
            rewritten_end = rewritten_sentences[rewritten_index + rewritten_span_count - 1]['end']

            orig_span = original_text[original_start:original_end]
            rew_span = rewritten_text[rewritten_start:rewritten_end]

            if orig_span.strip() == rew_span.strip():
                continue

            change = self._build_patch_change(
                orig_span,
                rew_span,
                original_offset + original_start,
                original_offset + original_end,
                rewritten_offset + rewritten_start,
                target_grade,
                going_up,
                allow_fallback=True,
            )
            if change:
                pair_to_change_index[len(llm_pairs)] = len(changes)
                llm_pairs.append({'original': orig_span.strip(), 'rewritten': rew_span.strip()})
                changes.append(change)

        if llm_pairs and self._llm_calls_remaining():
            llm_explanations = self.llm_validator.explain_sentence_changes(llm_pairs, going_up)
            self._llm_calls_made += 1
            for pair_idx_str, items in llm_explanations.items():
                try:
                    pair_idx = int(pair_idx_str)
                except (ValueError, TypeError):
                    continue
                change_idx = pair_to_change_index.get(pair_idx)
                if change_idx is None or change_idx >= len(changes):
                    continue
                explanation_items = []
                for item in (items or []):
                    if not isinstance(item, dict):
                        continue
                    before = item.get('before', '')
                    after = item.get('after', '')
                    reason = item.get('reason', '')
                    before_lookup = re.sub(r"[^\w]", '', before).lower()
                    after_lookup = re.sub(r"[^\w]", '', after).lower()
                    freq_before = zipf_frequency(before_lookup, 'en') if before_lookup else 0.0
                    freq_after = zipf_frequency(after_lookup, 'en') if after_lookup else 0.0
                    syl_before = self.text_processor.count_syllables(before_lookup) if before_lookup else 0
                    syl_after = self.text_processor.count_syllables(after_lookup) if after_lookup else 0
                    kind = 'word_upgrade' if going_up else 'word_replacement'
                    if 'split' in reason.lower() or 'combin' in reason.lower():
                        kind = 'sentence_rewrite'
                    explanation_items.append({
                        'kind': kind,
                        'before': before,
                        'after': after,
                        'frequency_before': round(freq_before, 2),
                        'frequency_after': round(freq_after, 2),
                        'syllables_before': syl_before,
                        'syllables_after': syl_after,
                        'text': f"Replaced '{before}' with '{after}' — {reason}" if before and after else reason,
                    })
                if explanation_items:
                    changes[change_idx]['explanation_items'] = explanation_items

        return changes or None

    def _fuzzy_sentence_diff(self, original_text, rewritten_text, target_grade, going_up):
        """Fallback diff using word-overlap similarity to align sentences.

        When SequenceMatcher fails because the LLM rewrote sentences too
        heavily, pair each original sentence with the most similar rewritten
        sentence and produce per-sentence changes.
        """
        orig_sents = self._extract_sentence_chunks(original_text)
        new_sents = self._extract_sentence_chunks(rewritten_text)
        if not orig_sents or not new_sents:
            return None

        def _word_set(text):
            return set(w.lower() for w in text.split() if len(w) > 2)

        orig_words = [_word_set(s['raw']) for s in orig_sents]
        new_words = [_word_set(s['raw']) for s in new_sents]

        used_new = set()
        pairings = []

        for i, ow in enumerate(orig_words):
            best_j, best_sim = -1, 0.0
            for j, nw in enumerate(new_words):
                if j in used_new or not ow or not nw:
                    continue
                overlap = len(ow & nw)
                sim = overlap / max(len(ow | nw), 1)
                if sim > best_sim:
                    best_sim = sim
                    best_j = j
            if best_j >= 0 and best_sim >= 0.25:
                pairings.append((i, best_j, best_sim))
                used_new.add(best_j)

        if not pairings:
            return None

        grade_label = 'College' if target_grade >= 13 else f'Grade {target_grade}'
        changes = []
        for orig_idx, new_idx, _sim in pairings:
            orig_sent = orig_sents[orig_idx]
            new_sent = new_sents[new_idx]
            if orig_sent['raw'].strip() == new_sent['raw'].strip():
                continue

            change = self._build_patch_change(
                orig_sent['raw'],
                new_sent['raw'],
                orig_sent['start'],
                orig_sent['end'],
                new_sent['start'],
                target_grade,
                going_up,
                allow_fallback=True,
            )
            if change:
                changes.append(change)

        matched_orig = {p[0] for p in pairings}
        unmatched_orig = [i for i in range(len(orig_sents)) if i not in matched_orig]
        for i in unmatched_orig:
            nearest_idx = None
            nearest_dist = float('inf')
            for ci, change in enumerate(changes):
                change_start = change.get('start', 0)
                change_end = change.get('end', 0)
                dist = min(
                    abs(orig_sents[i]['start'] - change_end),
                    abs(orig_sents[i]['end'] - change_start),
                )
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_idx = ci
            if nearest_idx is not None:
                neighbor = changes[nearest_idx]
                new_start = min(neighbor['start'], orig_sents[i]['start'])
                new_end = max(neighbor['end'], orig_sents[i]['end'])
                neighbor['start'] = new_start
                neighbor['position'] = new_start
                neighbor['end'] = new_end
                neighbor['original'] = original_text[new_start:new_end].strip()
                neighbor['original_text'] = original_text[new_start:new_end]

        if len(changes) >= 2:
            for idx, c in enumerate(changes):
                c['id'] = idx
            return changes

        return None

    def _diff_changes(
        self,
        original_text,
        rewritten_text,
        target_grade,
        going_up,
        prefer_sentence_level=False,
    ):
        """
        Build stable patches anchored to the ORIGINAL text.

        Diff paragraphs first, then sentences inside each changed paragraph,
        and only fall back to word-level patches when the local edit is a clean
        one-word substitution. This keeps previews reviewable instead of
        turning large structural rewrites into misleading micro-diffs.
        """
        import difflib

        if original_text == rewritten_text:
            return []

        original_paragraphs = self._extract_paragraph_chunks(original_text)
        rewritten_paragraphs = self._extract_paragraph_chunks(rewritten_text)

        if not original_paragraphs or not rewritten_paragraphs:
            changes = self._diff_sentence_changes(
                original_text,
                rewritten_text,
                target_grade,
                going_up,
                prefer_sentence_level=prefer_sentence_level,
            )
            for index, change in enumerate(changes):
                change['id'] = index
            return changes

        matcher = difflib.SequenceMatcher(
            None,
            [paragraph['normalized'] for paragraph in original_paragraphs],
            [paragraph['normalized'] for paragraph in rewritten_paragraphs],
            autojunk=False
        )

        changes = []
        original_length = len(original_text)
        rewritten_length = len(rewritten_text)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue

            if tag == 'replace' and (i2 - i1) == (j2 - j1) and (i2 - i1) > 1:
                for paragraph_index in range(i2 - i1):
                    original_paragraph = original_paragraphs[i1 + paragraph_index]
                    rewritten_paragraph = rewritten_paragraphs[j1 + paragraph_index]
                    paragraph_changes = self._diff_sentence_changes(
                        original_paragraph['raw'],
                        rewritten_paragraph['raw'],
                        target_grade,
                        going_up,
                        original_offset=original_paragraph['start'],
                        rewritten_offset=rewritten_paragraph['start'],
                        prefer_sentence_level=prefer_sentence_level,
                    )
                    if not paragraph_changes:
                        change = self._build_patch_change(
                            original_paragraph['raw'],
                            rewritten_paragraph['raw'],
                            original_paragraph['start'],
                            original_paragraph['end'],
                            rewritten_paragraph['start'],
                            target_grade,
                            going_up,
                            allow_fallback=True
                        )
                        if change:
                            paragraph_changes = [change]
                    changes.extend(paragraph_changes)
                continue

            original_start = original_paragraphs[i1]['start'] if i1 < len(original_paragraphs) else original_length
            original_end = original_paragraphs[i2 - 1]['end'] if i2 > i1 else original_start
            rewritten_start = rewritten_paragraphs[j1]['start'] if j1 < len(rewritten_paragraphs) else rewritten_length
            rewritten_end = rewritten_paragraphs[j2 - 1]['end'] if j2 > j1 else rewritten_start

            paragraph_changes = self._diff_sentence_changes(
                original_text[original_start:original_end],
                rewritten_text[rewritten_start:rewritten_end],
                target_grade,
                going_up,
                original_offset=original_start,
                rewritten_offset=rewritten_start,
                prefer_sentence_level=prefer_sentence_level,
            )

            if not paragraph_changes:
                change = self._build_patch_change(
                    original_text[original_start:original_end],
                    rewritten_text[rewritten_start:rewritten_end],
                    original_start,
                    original_end,
                    rewritten_start,
                    target_grade,
                    going_up,
                    allow_fallback=True
                )
                if change:
                    paragraph_changes = [change]

            changes.extend(paragraph_changes)

        for index, change in enumerate(changes):
            change['id'] = index

        if len(changes) <= 1 and original_text != rewritten_text:
            fuzzy = self._fuzzy_sentence_diff(original_text, rewritten_text, target_grade, going_up)
            if fuzzy and len(fuzzy) > len(changes):
                return fuzzy
            if not changes:
                fallback_change = self._build_patch_change(
                    original_text,
                    rewritten_text,
                    0,
                    len(original_text),
                    0,
                    target_grade,
                    going_up,
                    allow_fallback=True
                )
                if fallback_change:
                    fallback_change['id'] = 0
                    return [fallback_change]

        return changes

    # ------------------------------------------------------------------ #
    #  Paragraph-first rewrite pipeline
    # ------------------------------------------------------------------ #
