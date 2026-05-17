from .base import *


class CandidateSelectionMixin:
    @staticmethod
    def _candidate_has_summary_wrapup(candidate):
        flags = candidate.get('validation_flags', []) or []
        return any(flag.startswith('summary_wrapup:') for flag in flags)

    @staticmethod
    def _candidate_invalid_delta(candidate):
        return int(candidate.get('invalid_sentence_delta', candidate.get('invalid_sentence_count', 0)) or 0)

    @classmethod
    def _candidate_has_paragraph_scope_drift(cls, candidate):
        flags = candidate.get('validation_flags', []) or []
        return (
            cls._candidate_has_summary_wrapup(candidate) or
            'final_paragraph_expanded' in flags or
            'final_paragraph_sentence_growth' in flags or
            'paragraph_count_changed' in flags or
            any(flag.startswith('paragraph_scope_shift:') for flag in flags)
        )

    @classmethod
    def _candidate_blocking_flags(cls, candidate):
        flags = candidate.get('validation_flags', []) or []
        hard_prefixes = (
            'blocked_substitution:',
            'missing_protected_term:',
            'word_artifact:',
            'paragraph_scope_shift:',
        )
        hard_flags = [
            flag for flag in flags
            if (
                flag != 'blocked_substitution:but' and (
                    flag == 'llm_meta_artifact' or
                    flag == 'major_length_expansion' or
                    flag == 'empty_candidate' or
                    flag.startswith(hard_prefixes)
                )
            )
        ]
        if cls._candidate_invalid_delta(candidate) > 3:
            hard_flags.append('too_many_new_invalid_sentences')
        return hard_flags

    @classmethod
    def _candidate_is_low_grade_rescue(cls, candidate, target_grade=None):
        if target_grade is None or target_grade > 7:
            return False
        flags = candidate.get('validation_flags', []) or []
        blocking_flags = cls._candidate_blocking_flags(candidate)
        if blocking_flags:
            return False
        if 'paragraph_count_changed' in flags:
            return False
        if 'major_length_compression' in flags and candidate.get('semantic_similarity_score', 0.0) < 0.35:
            return False
        if candidate.get('raw_score', 99) > float(target_grade) + 1.5:
            return False
        return (
            candidate.get('direction_hit') and
            candidate.get('target_distance', 999) <= 1.0 and
            cls._candidate_invalid_delta(candidate) <= 2
        )

    @classmethod
    def _candidate_is_repairable_near_hit(cls, candidate, target_grade=None):
        flags = candidate.get('validation_flags', []) or []
        blocking_flags = cls._candidate_blocking_flags(candidate)
        target_distance = candidate.get('target_distance', 999)
        semantic_floor = 0.28 if target_grade is not None and target_grade <= 7 and target_distance <= 1.0 else (
            0.35 if target_distance <= 1.0 else 0.72
        )
        raw_score = candidate.get('raw_score', 0.0)
        if target_grade is not None and target_grade <= 7:
            target_level_ok = raw_score <= float(target_grade) + 3.0
        else:
            target_level_ok = raw_score >= max(6.0, float(target_grade or 9) - 2.0)
        return (
            candidate.get('direction_hit') and
            target_distance <= 2.0 and
            cls._candidate_invalid_delta(candidate) <= 3 and
            candidate.get('semantic_similarity_score', 0.0) >= semantic_floor and
            not blocking_flags and
            target_level_ok
        )

    @classmethod
    def _candidate_has_hard_safety_failure(cls, candidate, target_grade=None):
        flags = candidate.get('validation_flags', []) or []
        if cls._candidate_invalid_delta(candidate) > 3:
            return True
        if (
            candidate.get('semantic_similarity_score', 1.0) < 0.28 and
            not cls._candidate_is_low_grade_rescue(candidate, target_grade)
        ):
            return True
        return bool(cls._candidate_blocking_flags(candidate))

    @classmethod
    def _candidate_display_delta(cls, candidate, target_grade):
        if target_grade is None:
            return 999
        return cls._display_grade_delta_from_score(candidate.get('raw_score', 99), target_grade)

    @classmethod
    def _candidate_target_status(cls, candidate, target_grade):
        if target_grade is None:
            return 'miss'
        if candidate.get('target_distance', 999) == 0:
            return 'exact'
        if cls._candidate_display_delta(candidate, target_grade) <= TARGET_LOCK_DISPLAY_BAND_TOLERANCE:
            return 'near'
        return 'miss'

    @classmethod
    def _candidate_is_target_lock_safe(cls, candidate, target_grade):
        if target_grade is None:
            return False
        if cls._candidate_has_hard_safety_failure(candidate, target_grade):
            return False
        if not candidate.get('direction_hit'):
            return False
        if cls._candidate_invalid_delta(candidate) > 3:
            return False
        return True

    @classmethod
    def _target_lock_rank_key(cls, candidate, target_grade):
        status = cls._candidate_target_status(candidate, target_grade)
        status_rank = {'exact': 0, 'near': 1, 'miss': 2}.get(status, 2)
        return (
            status_rank,
            cls._candidate_display_delta(candidate, target_grade),
            candidate.get('target_distance', 999),
            cls._candidate_invalid_delta(candidate),
            candidate.get('candidate_score', 999),
            -candidate.get('semantic_similarity_score', 0),
            candidate.get('paragraph_rewrite_count', 99),
        )

    @classmethod
    def _select_target_locked_candidate(cls, candidates, target_grade):
        if target_grade is None:
            return None
        safe_candidates = [
            candidate for candidate in candidates
            if cls._candidate_is_target_lock_safe(candidate, target_grade)
        ]
        exact_or_near = [
            candidate for candidate in safe_candidates
            if cls._candidate_target_status(candidate, target_grade) in {'exact', 'near'}
        ]
        if not exact_or_near:
            return None
        return min(exact_or_near, key=lambda candidate: cls._target_lock_rank_key(candidate, target_grade))

    @classmethod
    def _select_preferred_candidate(cls, ranked_candidates, target_grade=None):
        if not ranked_candidates:
            return None

        candidate_pool = [
            candidate for candidate in ranked_candidates
            if not cls._candidate_has_hard_safety_failure(candidate, target_grade)
        ] or ranked_candidates

        best_overall = candidate_pool[0]
        target_locked = cls._select_target_locked_candidate(candidate_pool, target_grade)
        if target_locked:
            return target_locked

        def near_hit_override(strict_choice):
            if target_grade is None:
                return strict_choice

            low_grade_rescue = [
                candidate for candidate in ranked_candidates
                if cls._candidate_is_low_grade_rescue(candidate, target_grade)
            ]
            if low_grade_rescue:
                best_low_grade_rescue = min(
                    low_grade_rescue,
                    key=lambda candidate: (
                        candidate['target_distance'],
                        cls._candidate_invalid_delta(candidate),
                        candidate['candidate_score'],
                        -candidate['semantic_similarity_score'],
                        candidate['paragraph_rewrite_count'],
                    ),
                )
                if strict_choice is None:
                    return best_low_grade_rescue
                if best_low_grade_rescue['target_distance'] + 1.5 < strict_choice.get('target_distance', 999):
                    return best_low_grade_rescue

            repairable = [
                candidate for candidate in candidate_pool
                if cls._candidate_is_repairable_near_hit(candidate, target_grade)
            ]
            if not repairable:
                return strict_choice

            best_repairable = min(
                repairable,
                key=lambda candidate: (
                    candidate['target_distance'],
                    cls._candidate_invalid_delta(candidate),
                    candidate['candidate_score'],
                    -candidate['semantic_similarity_score'],
                    candidate['paragraph_rewrite_count'],
                ),
            )
            if strict_choice is None:
                return best_repairable
            if best_repairable is strict_choice:
                return strict_choice

            strict_distance = strict_choice.get('target_distance', 999)
            repair_distance = best_repairable.get('target_distance', 999)
            strict_invalid_delta = cls._candidate_invalid_delta(strict_choice)

            # A target miss is not a rejection. If the closest safe-ish candidate
            # is much nearer to the requested band, keep it for final repair
            # instead of snapping back to a much lower clean rule candidate.
            if repair_distance == 0 and (strict_distance > 0 or strict_invalid_delta > 0):
                return best_repairable
            if repair_distance + 0.75 < strict_distance:
                return best_repairable
            if (
                repair_distance + 0.35 < strict_distance and
                best_repairable['candidate_score'] <= strict_choice['candidate_score'] + 8.0
            ):
                return best_repairable

            return strict_choice

        if target_grade is not None and target_grade >= 11:
            clean_valid_directional = [
                candidate for candidate in candidate_pool
                if (
                    cls._candidate_invalid_delta(candidate) == 0 and
                    candidate.get('direction_hit') and
                    not cls._candidate_has_paragraph_scope_drift(candidate)
                )
            ]
            exact_valid = [
                candidate for candidate in candidate_pool
                if (
                    cls._candidate_invalid_delta(candidate) == 0 and
                    candidate.get('direction_hit') and
                    candidate.get('target_distance', 999) == 0
                )
            ]
            clean_exact_valid = [
                candidate for candidate in exact_valid
                if not cls._candidate_has_paragraph_scope_drift(candidate)
            ]
            if clean_exact_valid:
                return min(
                    clean_exact_valid,
                    key=lambda candidate: (
                        candidate['candidate_score'],
                        -candidate['semantic_similarity_score'],
                        candidate['paragraph_rewrite_count'],
                    ),
                )
            if exact_valid:
                best_exact = min(
                    exact_valid,
                    key=lambda candidate: (
                        candidate['candidate_score'],
                        -candidate['semantic_similarity_score'],
                        candidate['paragraph_rewrite_count'],
                    ),
                )
                if clean_valid_directional:
                    best_clean = min(
                        clean_valid_directional,
                        key=lambda candidate: (
                            candidate['target_distance'],
                            candidate['candidate_score'],
                            -candidate['semantic_similarity_score'],
                            candidate['paragraph_rewrite_count'],
                        ),
                    )
                    if (
                        best_clean['target_distance'] <= best_exact['target_distance'] + 0.35 or
                        best_clean['candidate_score'] <= best_exact['candidate_score'] + 2.0
                    ):
                        return near_hit_override(best_clean)
                return best_exact

        valid_directional = [
            candidate for candidate in candidate_pool
            if (
                cls._candidate_invalid_delta(candidate) == 0 and
                candidate.get('direction_hit')
            )
        ]
        valid_any = [
            candidate for candidate in candidate_pool
            if cls._candidate_invalid_delta(candidate) == 0
        ]

        for pool in (valid_directional, valid_any):
            if not pool:
                continue
            if target_grade is not None and target_grade >= 11:
                clean_pool = [
                    candidate for candidate in pool
                    if not cls._candidate_has_paragraph_scope_drift(candidate)
                ]
                if clean_pool:
                    pool = clean_pool
                strict_choice = min(
                    pool,
                    key=lambda candidate: (
                        candidate['target_distance'],
                        candidate['candidate_score'],
                        -candidate['semantic_similarity_score'],
                        candidate['paragraph_rewrite_count'],
                    ),
                )
                return near_hit_override(strict_choice)
            strict_choice = min(
                pool,
                key=lambda candidate: (
                    candidate['target_distance'],
                    candidate['candidate_score'],
                    -candidate['semantic_similarity_score'],
                    candidate['paragraph_rewrite_count'],
                ),
            )
            return near_hit_override(strict_choice)

        return near_hit_override(best_overall)

    def _select_rewrite_candidate(self, text, target_grade, mode):
        source_grade, _, _ = self._measure_text_metrics(text)
        direction = self._get_target_direction(source_grade, target_grade)
        going_up = direction > 0
        policy = self._get_target_policy(target_grade, going_up, source_grade=source_grade)

        if direction == 0:
            base_metrics = self._score_candidate(
                original_text=text,
                candidate_text=text,
                target_grade=target_grade,
                mode=mode,
                source_grade=source_grade,
                policy=policy,
            )
            summary = self._build_selection_summary(
                policy=policy,
                source_grade=source_grade,
                target_grade=target_grade,
                selected_candidate={
                    'text': text,
                    'rule_history': ['selection.identity'],
                    **base_metrics,
                },
                top_candidates=[{
                    'text': text,
                    'rule_history': ['selection.identity'],
                    **base_metrics,
                }],
            )
            return {
                'text': text,
                'score': base_metrics['candidate_score'],
                'going_up': going_up,
                'selection_summary': summary,
                'top_candidates': summary['top_candidates'],
            }

        beam = [{
            'text': text,
            'rule_history': ['selection.identity'],
            'stage_notes': ['original'],
        }]

        stage_order = ['lexical', 'syntactic', 'discourse']
        for stage in stage_order:
            stage_candidates = []
            for candidate in beam:
                stage_candidates.extend(
                    self._generate_stage_candidates(
                        candidate=candidate,
                        stage=stage,
                        target_grade=target_grade,
                        going_up=going_up,
                        policy=policy,
                    )
                )
            beam = self._rank_candidates(
                original_text=text,
                candidates=stage_candidates,
                target_grade=target_grade,
                mode=mode,
                source_grade=source_grade,
                policy=policy,
            )

        beam.append(self._iterative_rule_rewrite(text, target_grade))
        beam.extend(self._target_lock_repair_candidates(
            original_text=text,
            candidates=beam,
            target_grade=target_grade,
            source_grade=source_grade,
            going_up=going_up,
            mode=mode,
            policy=policy,
        ))
        ranked = self._rank_candidates(
            original_text=text,
            candidates=beam,
            target_grade=target_grade,
            mode=mode,
            source_grade=source_grade,
            policy=policy,
        )
        selected = self._select_preferred_candidate(ranked, target_grade=target_grade)
        summary = self._build_selection_summary(
            policy=policy,
            source_grade=source_grade,
            target_grade=target_grade,
            selected_candidate=selected,
            top_candidates=ranked[:policy['beam_width']],
        )

        return {
            'text': selected['text'],
            'score': selected['candidate_score'],
            'going_up': going_up,
            'selection_summary': summary,
            'top_candidates': summary['top_candidates'],
        }

    def _target_lock_repair_candidates(
        self,
        original_text,
        candidates,
        target_grade,
        source_grade,
        going_up,
        mode,
        policy,
    ):
        repaired = []
        seen = {
            re.sub(r'\s+', ' ', candidate.get('text', '')).strip().lower()
            for candidate in candidates
            if candidate.get('text')
        }

        for candidate in candidates:
            repaired_candidate = self._target_lock_repair_candidate(
                original_text=original_text,
                candidate=candidate,
                target_grade=target_grade,
                source_grade=source_grade,
                going_up=going_up,
                mode=mode,
                policy=policy,
            )
            if not repaired_candidate:
                continue
            key = re.sub(r'\s+', ' ', repaired_candidate['text']).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            repaired.append(repaired_candidate)

        return repaired

    def _target_lock_repair_candidate(
        self,
        original_text,
        candidate,
        target_grade,
        source_grade,
        going_up,
        mode,
        policy,
    ):
        candidate_text = self._restore_paragraph_shape(
            original_text,
            self._strip_llm_meta_commentary(candidate.get('text', '') or ''),
        )
        if not candidate_text.strip():
            return None

        def score_text(text_to_score):
            metrics = self._score_candidate(
                original_text=original_text,
                candidate_text=text_to_score,
                target_grade=target_grade,
                mode=mode,
                source_grade=source_grade,
                policy=policy,
            )
            return {**candidate, 'text': text_to_score, **metrics}

        best = score_text(candidate_text)
        if best.get('target_distance', 999) == 0:
            return None
        if self._candidate_blocking_flags(best) or self._candidate_invalid_delta(best) > 3:
            return None

        current_text = candidate_text
        lower, upper = self._get_target_band(target_grade)
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])

        for _round in range(TARGET_LOCK_REPAIR_ROUNDS):
            grade, _syl, wps = self._measure_text_metrics(current_text)
            next_text = current_text

            if grade < lower:
                if target_grade <= 7:
                    combined, _ = self._combine_short_sentences(current_text, target_grade)
                    if combined != current_text:
                        next_text = combined
                    elif wps >= metrics['min_wps']:
                        # Last resort for extreme undershoots: a tiny curated
                        # vocabulary lift is safer than bouncing to academic prose.
                        next_text, _ = self._complexify_text(current_text, target_grade)
                else:
                    if wps < metrics['target_wps'] - 0.5:
                        next_text, _ = self._combine_short_sentences(current_text, target_grade)
                    if next_text == current_text:
                        next_text, _ = self._complexify_text(current_text, target_grade)
            elif grade >= upper:
                next_text, _ = self._replace_difficult_words(current_text, target_grade)
                next_grade, _next_syl, next_wps = self._measure_text_metrics(next_text)
                if next_wps > metrics['max_wps'] or next_grade >= upper:
                    split_text, _ = self._split_long_sentences(next_text, target_grade)
                    if split_text != next_text:
                        next_text = split_text
                    elif next_wps > metrics['max_wps'] or next_grade >= upper:
                        forced_split, _ = self._force_split_long_sentences_for_target_lock(
                            next_text,
                            target_grade,
                        )
                        if forced_split != next_text:
                            next_text = forced_split

            next_text = self._restore_paragraph_shape(original_text, next_text)
            if next_text == current_text:
                break

            current_text = next_text
            scored = score_text(current_text)
            if self._candidate_blocking_flags(scored) or self._candidate_invalid_delta(scored) > 3:
                continue
            if self._target_lock_rank_key(scored, target_grade) < self._target_lock_rank_key(best, target_grade):
                best = scored
            if best.get('target_distance', 999) == 0:
                break

        if best['text'] == candidate_text:
            return None

        return {
            'text': best['text'],
            'rule_history': candidate.get('rule_history', []) + ['target_lock.repair'],
            'stage_notes': candidate.get('stage_notes', []) + ['target_lock:repair'],
        }

    def _force_split_long_sentences_for_target_lock(self, text, target_grade):
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_wps = metrics['target_wps']
        min_wps = metrics['min_wps']
        max_wps = metrics['max_wps']
        changes = []
        new_paragraphs = []

        def split_words(sentence_text):
            words = sentence_text.strip().split()
            if len(words) <= max_wps + 2 or len(words) < min_wps * 2:
                return [sentence_text.strip()]

            pieces = []
            remaining = words
            while len(remaining) > max_wps + 2 and len(remaining) >= min_wps * 2:
                split_at = min(max(target_wps, min_wps), len(remaining) - min_wps)
                search_start = max(min_wps, split_at - 4)
                search_end = min(len(remaining) - min_wps, split_at + 4)
                best_at = split_at
                found_boundary = False
                for index in range(search_end, search_start - 1, -1):
                    token = re.sub(r"[^A-Za-z']+", '', remaining[index - 1]).lower()
                    raw_next = remaining[index] if index < len(remaining) else ''
                    next_token = (
                        re.sub(r"[^A-Za-z']+", '', raw_next).lower()
                        if index < len(remaining) else ''
                    )
                    blocked_boundary = {'and', 'or', 'but', 'so', 'to', 'of', 'that', 'which', 'who', 'whom', 'whose'}
                    safe_next_start = (
                        next_token in {
                            'the', 'this', 'these', 'those', 'a', 'an', 'it', 'they', 'we',
                            'people', 'scientists', 'researchers', 'models', 'ideas',
                            'facts', 'results', 'evidence', 'knowledge',
                        } or
                        bool(raw_next[:1].isupper())
                    )
                    if (
                        token and
                        token not in PREPOSITION_HINTS and
                        token not in blocked_boundary and
                        token not in AUXILIARY_HINTS and
                        token not in {'make', 'makes', 'made', 'allow', 'allows', 'allowed'} and
                        next_token not in PREPOSITION_HINTS and
                        next_token not in blocked_boundary and
                        safe_next_start
                    ):
                        best_at = index
                        found_boundary = True
                        break
                if not found_boundary:
                    break

                left_words = remaining[:best_at]
                remaining = remaining[best_at:]
                left = ' '.join(left_words).strip().rstrip(',;:')
                if left and left[-1] not in '.!?':
                    left += '.'
                pieces.append(left)

            right = ' '.join(remaining).strip()
            if not pieces:
                return [sentence_text.strip()]
            if right:
                right = right[0].upper() + right[1:]
                if right[-1] not in '.!?':
                    right += '.'
                pieces.append(right)

            return [piece for piece in pieces if piece]

        for paragraph in self._extract_paragraph_chunks(text) or [{'raw': text, 'start': 0, 'end': len(text)}]:
            paragraph_text = paragraph['raw'].strip()
            if not paragraph_text:
                continue
            result_sentences = []
            for sent in nlp(paragraph_text).sents:
                sent_text = sent.text.strip()
                word_count = len([token for token in sent if token.is_alpha])
                if word_count <= max_wps:
                    result_sentences.append(sent_text)
                    continue
                pieces = split_words(sent_text)
                if len(pieces) > 1:
                    changes.append({
                        'type': 'sentence_split',
                        'original': sent_text,
                        'simplified': ' '.join(pieces),
                    })
                result_sentences.extend(pieces)
            new_paragraphs.append(' '.join(result_sentences).strip())

        return '\n\n'.join(paragraph for paragraph in new_paragraphs if paragraph), changes

    def _get_target_policy(self, target_grade, going_up, source_grade=None):
        policy_map = UPGRADE_TARGET_BUCKET_POLICIES if going_up else DOWNGRADE_TARGET_BUCKET_POLICIES
        if target_grade <= 5:
            policy = policy_map['3-5']
        elif target_grade <= 8:
            policy = policy_map['6-8']
        elif target_grade <= 10:
            policy = policy_map['9-10']
        else:
            policy = policy_map['11-college']

        policy = dict(policy)
        if source_grade is None:
            return policy

        gap = abs(float(target_grade) - float(source_grade))
        if gap < 3.5:
            return policy

        policy['beam_width'] = max(policy['beam_width'], BEAM_WIDTH + 1)
        policy['lexical_rounds'] += 1
        policy['lexical_max'] += 3

        if going_up:
            policy['combine_rounds'] += 1
            if policy['combine_changes'] is not None:
                policy['combine_changes'] += 2
        else:
            policy['split_rounds'] += 1
            if policy['split_changes'] is not None:
                policy['split_changes'] += 2

        if gap >= 6.5:
            policy['beam_width'] = max(policy['beam_width'], BEAM_WIDTH + 2)
            policy['lexical_rounds'] += 1
            policy['lexical_max'] += 3
            if going_up:
                policy['combine_rounds'] += 1
                if policy['combine_changes'] is not None:
                    policy['combine_changes'] += 2
            else:
                policy['split_rounds'] += 1
                if policy['split_changes'] is not None:
                    policy['split_changes'] += 2

        return policy

    def _generate_stage_candidates(self, candidate, stage, target_grade, going_up, policy):
        variants = [{
            'text': candidate['text'],
            'rule_history': candidate.get('rule_history', []) + [f'{stage}.identity'],
            'stage_notes': candidate.get('stage_notes', []) + [f'{stage}:identity'],
        }]

        if stage == 'lexical':
            if going_up and 5 <= target_grade <= 10:
                rewritten = self._apply_low_mid_upgrade_phrases(candidate['text'], target_grade)
                if rewritten != candidate['text']:
                    variants.append({
                        'text': rewritten,
                        'rule_history': candidate.get('rule_history', []) + ['lexical.targeted_phrase'],
                        'stage_notes': candidate.get('stage_notes', []) + ['lexical:targeted_phrase'],
                    })
            for intensity in ('balanced', 'strong'):
                rewritten = self._apply_lexical_stage(
                    candidate['text'],
                    target_grade,
                    going_up,
                    policy,
                    intensity=intensity,
                )
                if rewritten != candidate['text']:
                    variants.append({
                        'text': rewritten,
                        'rule_history': candidate.get('rule_history', []) + [f'lexical.{intensity}'],
                        'stage_notes': candidate.get('stage_notes', []) + [f'lexical:{intensity}'],
                    })
        elif stage == 'syntactic':
            for intensity in ('balanced', 'strong'):
                rewritten = self._apply_syntactic_stage(
                    candidate['text'],
                    target_grade,
                    going_up,
                    policy,
                    intensity=intensity,
                )
                if rewritten != candidate['text']:
                    variants.append({
                        'text': rewritten,
                        'rule_history': candidate.get('rule_history', []) + [f'syntactic.{intensity}'],
                        'stage_notes': candidate.get('stage_notes', []) + [f'syntactic:{intensity}'],
                    })
        elif stage == 'discourse':
            for intensity in ('balanced', 'strong'):
                rewritten = self._apply_discourse_stage(
                    candidate['text'],
                    target_grade,
                    going_up,
                    policy,
                    intensity=intensity,
                )
                if rewritten != candidate['text']:
                    variants.append({
                        'text': rewritten,
                        'rule_history': candidate.get('rule_history', []) + [f'discourse.{intensity}'],
                        'stage_notes': candidate.get('stage_notes', []) + [f'discourse:{intensity}'],
                    })

        return variants

    def _apply_low_mid_upgrade_phrases(self, text, target_grade):
        if not (5 <= target_grade <= 10):
            return text

        if target_grade <= 7:
            phrase_rules = LOW_MID_UPGRADE_PHRASES
        elif target_grade <= 8:
            phrase_rules = MID_GRADE_UPGRADE_PHRASES
        else:
            phrase_rules = HIGH_GRADE_NARRATIVE_UPGRADE_PHRASES

        current_text = text
        for pattern, replacement in phrase_rules:
            current_text = re.sub(pattern, replacement, current_text)

        return current_text

    def _apply_lexical_stage(self, text, target_grade, going_up, policy, intensity='balanced'):
        rounds = policy['lexical_rounds'] + (1 if intensity == 'strong' else 0)
        max_changes = policy['lexical_max'] + (2 if intensity == 'strong' else 0)
        current_text = text

        for round_index in range(rounds):
            per_round_max = max(2, max_changes - round_index)
            if going_up:
                next_text, _ = self._complexify_text(current_text, target_grade, max_changes=per_round_max)
            else:
                next_text, _ = self._replace_difficult_words(current_text, target_grade, max_changes=per_round_max)

            if next_text == current_text:
                break
            current_text = next_text

        return current_text

    def _apply_syntactic_stage(self, text, target_grade, going_up, policy, intensity='balanced'):
        current_text = text
        base_rounds = policy['combine_rounds'] if going_up else policy['split_rounds']
        extra_rounds = 0
        if intensity == 'strong':
            # Mild downgrades like Grade 12 -> 10 need an in-between option:
            # more structural edits than "balanced", but not an entire extra
            # simplification round that drops the text a full grade too far.
            if going_up or target_grade <= 8:
                extra_rounds = 1
        rounds = base_rounds + extra_rounds
        if rounds <= 0:
            return text

        for _ in range(rounds):
            structure_base_text = current_text
            if going_up:
                max_combinations = policy['combine_changes'] or None
                if intensity == 'strong' and max_combinations is not None:
                    max_combinations += 1
                next_text, structural_changes = self._combine_short_sentences(
                    current_text,
                    target_grade,
                    max_combinations=max_combinations,
                )
            else:
                max_sentence_changes = policy['split_changes']
                if intensity == 'strong' and max_sentence_changes is not None:
                    max_sentence_changes += 1
                next_text, structural_changes = self._split_long_sentences(
                    current_text,
                    target_grade,
                    max_sentence_changes=max_sentence_changes,
                )

            next_text, _ = self._accept_structural_rewrite(
                structure_base_text,
                next_text,
                structural_changes,
            )
            if next_text == current_text:
                break
            current_text = next_text

        return current_text

    def _apply_discourse_stage(self, text, target_grade, going_up, policy, intensity='balanced'):
        current_text = self._rewrite_discourse_markers(text, going_up, target_grade=target_grade, intensity=intensity)
        if current_text != text:
            return current_text

        if not going_up and target_grade <= 7 and intensity == 'strong':
            softened = re.sub(r'\s*;\s*', '. ', text)
            softened = re.sub(r'\s*:\s*', '. ', softened)
            if softened != text:
                return softened

        return text

    def _rewrite_discourse_markers(self, text, going_up, target_grade=None, intensity='balanced'):
        if going_up and target_grade is not None and target_grade <= 6:
            return text

        mapping = DISCOURSE_UPGRADE_MAP if going_up else DISCOURSE_DOWNGRADE_MAP
        if not text.strip():
            return text

        current_text = text
        replacements = 0
        max_replacements = 2 if intensity == 'balanced' else 4

        doc = nlp(text)
        offset = 0
        for token in doc:
            if replacements >= max_replacements:
                break

            lookup = token.text.lower()
            replacement = mapping.get(lookup)
            if not replacement:
                continue

            if token.pos_ not in ('ADV', 'CCONJ', 'SCONJ'):
                continue

            start = token.idx + offset
            end = start + len(token.text)
            rendered = replacement.capitalize() if token.text[:1].isupper() else replacement
            current_text = current_text[:start] + rendered + current_text[end:]
            offset += len(rendered) - len(token.text)
            replacements += 1

        return current_text

    def _rank_candidates(self, original_text, candidates, target_grade, mode, source_grade, policy):
        ranked = {}
        for candidate in candidates:
            normalized_key = re.sub(r'\s+', ' ', candidate['text']).strip().lower()
            metrics = self._score_candidate(
                original_text=original_text,
                candidate_text=candidate['text'],
                target_grade=target_grade,
                mode=mode,
                source_grade=source_grade,
                policy=policy,
            )
            enriched = {
                **candidate,
                **metrics,
            }
            existing = ranked.get(normalized_key)
            if existing is None or enriched['candidate_score'] < existing['candidate_score']:
                ranked[normalized_key] = enriched

        high_upgrade = target_grade >= 9 and target_grade > source_grade
        if high_upgrade:
            ordered = sorted(
                ranked.values(),
                key=lambda candidate: (
                    candidate['candidate_score'],
                    candidate['target_distance'],
                    self._candidate_invalid_delta(candidate),
                    candidate['invalid_sentence_count'],
                    -candidate['semantic_similarity_score'],
                    len(candidate.get('rule_history', [])),
                )
            )
        else:
            ordered = sorted(
                ranked.values(),
                key=lambda candidate: (
                    self._candidate_invalid_delta(candidate) > 0,
                    self._candidate_invalid_delta(candidate),
                    candidate['invalid_sentence_count'],
                    candidate['candidate_score'],
                    candidate['target_distance'],
                    -candidate['semantic_similarity_score'],
                    len(candidate.get('rule_history', [])),
                )
            )
        selected = ordered[:policy['beam_width']]

        def ensure_candidate(candidate):
            nonlocal selected
            if not candidate or candidate in selected:
                return
            if len(selected) < policy['beam_width']:
                selected.append(candidate)
                return
            replace_index = max(
                range(len(selected)),
                key=lambda index: self._target_lock_rank_key(selected[index], target_grade),
            )
            if self._target_lock_rank_key(candidate, target_grade) < self._target_lock_rank_key(selected[replace_index], target_grade):
                selected[replace_index] = candidate

        exact_or_near = [
            candidate for candidate in ordered
            if (
                self._candidate_is_target_lock_safe(candidate, target_grade) and
                self._candidate_target_status(candidate, target_grade) in {'exact', 'near'}
            )
        ]
        if exact_or_near:
            ensure_candidate(min(
                exact_or_near,
                key=lambda candidate: self._target_lock_rank_key(candidate, target_grade),
            ))

        target_pressure = abs(float(target_grade) - float(source_grade)) >= 3.0 or high_upgrade
        if target_pressure and ordered:
            target_seeking = [
                candidate for candidate in ordered
                if candidate.get('direction_hit') and not self._candidate_has_hard_safety_failure(candidate, target_grade)
            ]
            if target_seeking:
                closest_target_seeking = min(
                    target_seeking,
                    key=lambda candidate: (
                        candidate['target_distance'],
                        self._candidate_invalid_delta(candidate),
                        candidate['candidate_score'],
                        -candidate['semantic_similarity_score'],
                    ),
                )
                if closest_target_seeking not in selected:
                    ensure_candidate(closest_target_seeking)

            near_hits = [
                candidate for candidate in ordered
                if self._candidate_is_repairable_near_hit(candidate, target_grade)
            ]
            if target_grade <= 7:
                low_grade_rescue = [
                    candidate for candidate in ordered
                    if self._candidate_is_low_grade_rescue(candidate, target_grade)
                ]
                if low_grade_rescue:
                    near_hits.extend(low_grade_rescue)
            blocked_target_band = [
                candidate for candidate in ordered
                if (
                    candidate.get('direction_hit') and
                    candidate.get('target_distance', 999) <= 1.0 and
                    self._candidate_blocking_flags(candidate)
                )
            ]
            if blocked_target_band:
                ensure_candidate(min(
                    blocked_target_band,
                    key=lambda candidate: (
                        self._candidate_display_delta(candidate, target_grade),
                        candidate.get('target_distance', 999),
                        candidate.get('candidate_score', 999),
                    ),
                ))
            if near_hits:
                closest_near_hit = min(
                    near_hits,
                    key=lambda candidate: (
                        candidate['target_distance'],
                        self._candidate_invalid_delta(candidate),
                        candidate['candidate_score'],
                        -candidate['semantic_similarity_score'],
                    ),
                )
                if closest_near_hit not in selected:
                    farthest_selected_distance = max(
                        (candidate['target_distance'] for candidate in selected),
                        default=float('inf'),
                    )
                    if closest_near_hit['target_distance'] + 0.75 < farthest_selected_distance:
                        ensure_candidate(closest_near_hit)

        return selected

    def _score_candidate(self, original_text, candidate_text, target_grade, mode, source_grade, policy):
        candidate_grade, avg_syl, avg_wps = self._measure_text_metrics(candidate_text)
        _, source_avg_syl, source_avg_wps = self._measure_text_metrics(original_text)
        target_metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_distance = self._distance_to_target_band(candidate_grade, target_grade)
        source_distance = self._distance_to_target_band(source_grade, target_grade)
        invalid_sentences = self._collect_invalid_sentences(candidate_text)
        baseline_invalid_count = len(self._collect_invalid_sentences(original_text))
        invalid_sentence_delta = max(0, len(invalid_sentences) - baseline_invalid_count)
        semantic_similarity = self._semantic_similarity_score(original_text, candidate_text)
        lexical_flags = self._lexical_sanity_flags(original_text, candidate_text)
        artifact_flags = self._llm_artifact_flags(candidate_text)
        word_artifact_flags = self._word_artifact_flags(candidate_text)
        awkward_phrase_flags = self._awkward_phrase_flags(original_text, candidate_text)
        protected_term_flags = self._protected_term_flags(original_text, candidate_text)
        strict_protected_term_flags = [
            flag for flag in protected_term_flags
            if flag.startswith('missing_protected_term:')
        ]
        soft_protected_term_flags = [
            flag for flag in protected_term_flags
            if flag.startswith('missing_soft_protected_term:')
        ]
        length_scope_flags = self._length_scope_flags(original_text, candidate_text)
        paragraph_topic_flags = self._paragraph_topic_drift_flags(original_text, candidate_text)
        directional_flags = self._directional_candidate_flags(
            source_grade=source_grade,
            target_grade=target_grade,
            source_avg_syl=source_avg_syl,
            source_avg_wps=source_avg_wps,
            candidate_avg_syl=avg_syl,
            candidate_avg_wps=avg_wps,
            semantic_similarity=semantic_similarity,
        )
        paragraph_rewrites = self._count_heavy_paragraph_rewrites(original_text, candidate_text)
        summary_wrapup_flags = []
        paragraph_scope_flags = []
        final_paragraph_scope_penalty = 0.0
        if target_grade >= 8:
            summary_wrapup_flags = self._summary_wrapup_flags(original_text, candidate_text)
            final_paragraph_scope_penalty, paragraph_scope_flags = self._final_paragraph_scope_penalty(
                original_text,
                candidate_text,
            )
        moving_up = target_grade > source_grade
        direction_hit = (
            (moving_up and candidate_grade >= source_grade - 0.05) or
            ((not moving_up) and candidate_grade <= source_grade + 0.05)
        )

        score = target_distance * 6.0
        score += abs(avg_syl - target_metrics['target_syl']) * policy['syllable_weight']
        score += abs(avg_wps - target_metrics['target_wps']) * policy['wps_weight']
        score += invalid_sentence_delta * 24.0
        score += min(len(invalid_sentences), baseline_invalid_count) * 1.5
        score += max(0.0, 0.88 - semantic_similarity) * 6.0
        score += len(lexical_flags) * 3.5
        score += len(artifact_flags) * 20.0
        score += len(word_artifact_flags) * 18.0
        score += len(awkward_phrase_flags) * 14.0
        score += len(strict_protected_term_flags) * 18.0
        score += len(soft_protected_term_flags) * 1.5
        score += len(length_scope_flags) * 6.0
        score += len(paragraph_topic_flags) * 12.0
        score += len(directional_flags) * 3.0
        score += len(summary_wrapup_flags) * 4.5
        if len(summary_wrapup_flags) >= 2:
            score += 8.0
        if not direction_hit:
            score += 9.0
        score += paragraph_rewrites * policy['paragraph_penalty']
        score += final_paragraph_scope_penalty
        if target_grade <= 7 and avg_wps > target_metrics['target_wps']:
            score += (avg_wps - target_metrics['target_wps']) * 0.35
        if target_grade >= 11 and avg_wps < target_metrics['target_wps']:
            score += (target_metrics['target_wps'] - avg_wps) * 0.25
        if target_grade >= 11 and candidate_grade < target_grade:
            score += (target_grade - candidate_grade) * 4.0
        if target_distance > source_distance + 0.1:
            score += (target_distance - source_distance) * 2.5
        if abs(source_grade - target_grade) <= 2.5 and semantic_similarity < 0.9:
            score += (0.9 - semantic_similarity) * 12.0

        return {
            'candidate_score': round(score, 2),
            'raw_score': round(candidate_grade, 2),
            'target_distance': round(target_distance, 2),
            'direction_hit': direction_hit,
            'invalid_sentence_count': len(invalid_sentences),
            'invalid_sentence_delta': invalid_sentence_delta,
            'semantic_similarity_score': round(semantic_similarity, 2),
            'avg_syllables_per_word': round(avg_syl, 2),
            'avg_words_per_sentence': round(avg_wps, 2),
            'validation_flags': (
                lexical_flags +
                artifact_flags +
                word_artifact_flags +
                awkward_phrase_flags +
                protected_term_flags +
                length_scope_flags +
                paragraph_topic_flags +
                directional_flags +
                summary_wrapup_flags +
                paragraph_scope_flags +
                (['new_invalid_sentence_structure'] if invalid_sentence_delta else []) +
                (['inherited_invalid_sentence_structure'] if invalid_sentences and not invalid_sentence_delta else [])
            ),
            'paragraph_rewrite_count': paragraph_rewrites,
            'summary_wrapup_flag_count': len(summary_wrapup_flags),
            'final_paragraph_scope_penalty': round(final_paragraph_scope_penalty, 2),
        }

    def _directional_candidate_flags(
        self,
        source_grade,
        target_grade,
        source_avg_syl,
        source_avg_wps,
        candidate_avg_syl,
        candidate_avg_wps,
        semantic_similarity,
    ):
        flags = []
        going_up = target_grade > source_grade

        if going_up:
            if candidate_avg_syl < source_avg_syl - 0.03:
                flags.append('lexical_direction_mismatch')
            if candidate_avg_wps < source_avg_wps - 0.5 and target_grade >= 9:
                flags.append('sentence_length_direction_mismatch')
        else:
            if candidate_avg_syl > source_avg_syl + 0.03:
                flags.append('lexical_direction_mismatch')
            if candidate_avg_wps > source_avg_wps + 0.75:
                flags.append('sentence_length_direction_mismatch')

        if semantic_similarity < 0.82:
            flags.append('meaning_drift_risk')

        return flags

    def _semantic_similarity_score(self, original_text, candidate_text):
        original_norm = re.sub(r'\s+', ' ', original_text or '').strip().lower()
        candidate_norm = re.sub(r'\s+', ' ', candidate_text or '').strip().lower()
        if not original_norm and not candidate_norm:
            return 1.0

        original_doc = nlp(original_text or '')
        candidate_doc = nlp(candidate_text or '')
        original_lemmas = {
            token.lemma_.lower()
            for token in original_doc
            if token.is_alpha and not token.is_stop
        }
        candidate_lemmas = {
            token.lemma_.lower()
            for token in candidate_doc
            if token.is_alpha and not token.is_stop
        }

        lemma_union = original_lemmas | candidate_lemmas
        lemma_overlap = (
            len(original_lemmas & candidate_lemmas) / len(lemma_union)
            if lemma_union else 1.0
        )
        sequence_ratio = difflib.SequenceMatcher(
            None,
            original_norm,
            candidate_norm,
            autojunk=False,
        ).ratio()
        length_ratio = (
            min(len(original_norm), len(candidate_norm)) / max(len(original_norm), len(candidate_norm))
            if original_norm and candidate_norm else 1.0
        )
        return max(0.0, min(1.0, 0.45 * lemma_overlap + 0.35 * sequence_ratio + 0.2 * length_ratio))

    def _lexical_sanity_flags(self, original_text, candidate_text):
        flags = []
        original_words = Counter(
            re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", (original_text or '').lower())
        )
        candidate_words = Counter(
            re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", (candidate_text or '').lower())
        )

        for blocked in BLOCKED_SYNONYMS:
            if len(blocked) <= 2:
                continue
            if candidate_words[blocked] > original_words[blocked]:
                flags.append(f'blocked_substitution:{blocked}')

        return flags

    def _llm_artifact_flags(self, candidate_text):
        text = candidate_text or ''
        if not text.strip():
            return ['empty_candidate']
        artifact_patterns = [
            r'\b(?:note|notes|rationale|explanation|changes made|changes)\s*:',
            r'\bI (?:changed|rewrote|simplified|upgraded|removed|adjusted)\b',
            r'\bthe (?:rewritten|simplified|upgraded) text\b',
            r'^\s*```',
            r'"variants"\s*:',
        ]
        return [
            'llm_meta_artifact'
            for pattern in artifact_patterns[:1]
            if re.search(pattern, text, flags=re.IGNORECASE)
        ] or (
            ['llm_meta_artifact']
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in artifact_patterns[1:])
            else []
        )

    def _word_artifact_flags(self, candidate_text):
        words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", candidate_text or '')
        flags = []
        for word in words:
            lower = word.lower()
            malformed = (
                re.search(r'(?:er){2,}$', lower) or
                re.search(r'(?:est){2,}$', lower) or
                lower.endswith(('erer', 'errer', 'ierier', 'estest')) or
                lower in {'widerrer', 'broaderer', 'widerer', 'moreer'}
            )
            if malformed:
                flags.append(f'word_artifact:{lower}')
            if len(flags) >= 5:
                break
        return flags

    def _awkward_phrase_flags(self, original_text, candidate_text):
        text = re.sub(r'\s+', ' ', candidate_text or '').strip().lower()
        if not text:
            return []

        phrase_checks = [
            (
                r'\bfacilitat(?:e|es|ed|ing)\s+(?:us|me|him|her|them|you)\s+'
                r'(?!to\b|with\b|in\b|by\b)[a-z]+\b',
                'awkward_phrase:facilitate_bare_verb',
            ),
            (
                r'\b(?:construct|constructs|constructed|constructing)\s+'
                r'(?:a\s+|an\s+|the\s+)?(?:fresh\s+)?(?:salad|meal|dinner|lunch|food)\b',
                'awkward_phrase:construct_food',
            ),
            (
                r'\b(?:construct|constructs|constructed|constructing)\s+it\s+(?:all\s+)?worth\b',
                'awkward_phrase:construct_worth',
            ),
            (
                r'\b(?:expand|expands|expanded|expanding)\s+(?:fresh\s+)?food\b'
                r'|\bfood\s+(?:we|they|people|students|families)\s+(?:expand|expanded)\b',
                'awkward_phrase:expand_food',
            ),
            (
                r'\b(?:commence|commences|commenced|commencing)\s+to\s+'
                r'(?:push|dig|pull|pick|eat|grow|water|plant)\b',
                'awkward_phrase:commence_basic_action',
            ),
            (
                r'\b(?:bug|bugs|insect|insects)\s+(?:endeavor|endeavors|strive|strives)\s+to\s+eat\b',
                'awkward_phrase:nonhuman_endeavor',
            ),
            (
                r'\butiliz(?:e|es|ed|ing)\s+(?:a\s+|an\s+|the\s+)?'
                r'(?:dog|cat|boy|girl|person|child|student|friend|teacher|parent)\b',
                'awkward_phrase:utilize_living_being',
            ),
        ]

        flags = []
        for pattern, flag in phrase_checks:
            if re.search(pattern, text):
                flags.append(flag)
        original_norm = re.sub(r'\s+', ' ', original_text or '').strip().lower()
        if 'utiliz' in text and 'utiliz' not in original_norm:
            flags.append('awkward_phrase:context_blind_utilize')
        if re.search(r'\bplaces?\s+closer\b', original_norm) and re.search(r'\bpositions?\s+closer\b', text):
            flags.append('awkward_phrase:places_to_positions')
        if re.search(r'\bpressure\s+systems?\b', original_norm) and re.search(r'\bpressure\s+networks?\b', text):
            flags.append('awkward_phrase:pressure_systems_to_networks')
        if re.search(r'\bforms?\s+of\b', original_norm) and re.search(r'\bshapes?\s+of\b', text):
            flags.append('awkward_phrase:unsupported_forms_to_shapes')
        return flags

    @staticmethod
    def _protected_term_slug(term):
        return re.sub(r'[^a-z0-9]+', '_', (term or '').lower()).strip('_')[:40]

    @staticmethod
    def _looks_like_strict_protected_term(term):
        text = (term or '').strip()
        if not text:
            return False
        if re.search(r'\d', text):
            return True
        if re.search(r'\b[A-Z]{2,}\b', text):
            return True
        if any(char.isupper() for char in text):
            return True
        if len(text.split()) > 1:
            return True
        return False

    @staticmethod
    def _is_core_strict_protected_term(term, reasons=None):
        text = re.sub(r'\s+', ' ', (term or '').strip())
        lower = text.lower()
        reason_set = set(reasons or [])
        if not text:
            return False
        if 'number' in reason_set or re.search(r'\d', text):
            return True
        if 'ent:PERSON' in reason_set:
            return True
        if 'ent:ORG' in reason_set and 'university' in lower:
            return True
        if 'programme' in lower or 'program' in lower:
            return True
        if re.fullmatch(r'[A-Z]{2,}', text):
            return True
        if any(marker in lower for marker in ('cgpa', 'gpa', 'student number')):
            return True
        return False

    @staticmethod
    def _is_advisory_protected_term(term):
        lower = re.sub(r'\s+', ' ', (term or '').strip().lower())
        if not lower:
            return False
        advisory_markers = (
            'campus',
            'bachelor',
            'degree',
            'course',
            'coursework',
            'langgraph',
            'cs50x',
        )
        return any(marker in lower for marker in advisory_markers)

    def _extract_key_content_nouns(self, text, max_nouns=10):
        """Extract subject/object nouns that must be preserved or substituted during rewriting."""
        doc = nlp(text or '')
        key_nouns = []
        seen = set()
        for token in doc:
            if token.pos_ not in ('NOUN', 'PROPN'):
                continue
            if token.is_stop or len(token.text) < 3:
                continue
            if token.dep_ in ('nsubj', 'nsubjpass', 'dobj', 'pobj', 'attr'):
                chunk_text = token.text
                for chunk in doc.noun_chunks:
                    if token in chunk:
                        chunk_text = chunk.root.text
                        break
                lower = chunk_text.lower()
                if lower not in seen and lower not in PROTECTED_PROPN_EXCEPTIONS:
                    seen.add(lower)
                    key_nouns.append(chunk_text)
                    if len(key_nouns) >= max_nouns:
                        break
        return key_nouns

    def _protected_term_records(self, original_text):
        original_doc = nlp(original_text or '')
        records = {}

        def add(term, strict, reason):
            cleaned = re.sub(r'\s+', ' ', (term or '').strip())
            if not cleaned or cleaned.lower() in PROTECTED_PROPN_EXCEPTIONS:
                return
            effective_strict = bool(strict and not self._is_advisory_protected_term(cleaned))
            slug = self._protected_term_slug(cleaned)
            if not slug:
                return
            existing = records.get(slug)
            if existing:
                existing['strict'] = existing['strict'] or effective_strict
                existing['core_strict'] = (
                    existing.get('core_strict', False) or
                    bool(effective_strict and self._is_core_strict_protected_term(cleaned, [reason]))
                )
                if reason not in existing['reasons']:
                    existing['reasons'].append(reason)
                return
            records[slug] = {
                'term': cleaned,
                'slug': slug,
                'strict': effective_strict,
                'core_strict': bool(effective_strict and self._is_core_strict_protected_term(cleaned, [reason])),
                'reasons': [reason],
            }

        for ent in original_doc.ents:
            if ent.label_ in {'PERSON', 'ORG', 'GPE', 'LOC', 'PRODUCT', 'EVENT', 'WORK_OF_ART', 'LAW', 'NORP', 'FAC'}:
                ent_text = ent.text.strip()
                strict = ent.label_ in {'PERSON', 'ORG'} and self._looks_like_strict_protected_term(ent_text)
                add(ent_text, strict=strict, reason=f'ent:{ent.label_}')

        for token in original_doc:
            token_text = token.text.strip()
            if not token_text:
                continue
            if token.like_num or re.fullmatch(r'\d+(?:[.,:/-]\d+)*', token_text):
                add(token_text, strict=True, reason='number')
                continue
            if re.fullmatch(r'[A-Z]{2,}', token_text):
                add(token_text, strict=True, reason='acronym')
                continue
            if (
                token.pos_ == 'PROPN' and
                len(token_text) > 1 and
                token_text.lower() not in PROTECTED_PROPN_EXCEPTIONS
            ):
                add(token_text, strict=False, reason='proper_noun')

        return sorted(
            records.values(),
            key=lambda item: (not item['strict'], -len(item['term']), item['term'].lower()),
        )

    def _protected_term_manifest(self, original_text, strict_only=False):
        records = self._protected_term_records(original_text)
        if strict_only:
            records = [record for record in records if record['strict']]
        return [record['term'] for record in records]

    def _missing_protected_terms_from_flags(self, original_text, flags, strict_only=True, core_only=False):
        wanted_slugs = {
            flag.split(':', 1)[1]
            for flag in (flags or [])
            if flag.startswith('missing_protected_term:') or (
                not strict_only and flag.startswith('missing_soft_protected_term:')
            )
        }
        if not wanted_slugs:
            return []
        terms = []
        for record in self._protected_term_records(original_text):
            if strict_only and not record['strict']:
                continue
            if core_only and not record.get('core_strict'):
                continue
            if record['slug'] in wanted_slugs:
                terms.append(record['term'])
        return terms

    def _protected_term_flags(self, original_text, candidate_text):
        candidate_norm = re.sub(r'\s+', ' ', candidate_text or '').lower()

        flags = []
        for record in self._protected_term_records(original_text):
            normalized = re.sub(r'\s+', ' ', record['term']).strip().lower()
            if normalized and normalized not in candidate_norm:
                prefix = 'missing_protected_term' if record.get('core_strict') else 'missing_soft_protected_term'
                flags.append(f"{prefix}:{record['slug']}")
            if len(flags) >= 5:
                break
        return flags

    def _length_scope_flags(self, original_text, candidate_text):
        original_words = len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_text or ''))
        candidate_words = len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", candidate_text or ''))
        if original_words < 8 or candidate_words < 1:
            return []

        ratio = candidate_words / max(1, original_words)
        flags = []
        if ratio > 1.85 and candidate_words - original_words >= 20:
            flags.append('major_length_expansion')
        if ratio < 0.55 and original_words - candidate_words >= 12:
            flags.append('major_length_compression')
        return flags

    def _paragraph_content_terms(self, text):
        generic_terms = {
            'thing', 'things', 'people', 'person', 'make', 'made', 'take',
            'give', 'get', 'use', 'work', 'try', 'keep', 'help', 'show',
            'change', 'changes', 'different', 'important', 'simple',
        }
        terms = set()
        for token in nlp(text or ''):
            if not token.is_alpha or token.is_stop or len(token.text) <= 2:
                continue
            lemma = (token.lemma_ or token.text).lower()
            lemma = re.sub(r'[^a-z]+', '', lemma)
            if not lemma or lemma in generic_terms or len(lemma) <= 2:
                continue
            terms.add(lemma)
        return terms

    @staticmethod
    def _paragraph_term_overlap(left_terms, right_terms):
        if not left_terms or not right_terms:
            return 0.0
        overlap = len(left_terms & right_terms)
        precision = overlap / max(1, len(left_terms))
        recall = overlap / max(1, len(right_terms))
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def _paragraph_topic_drift_flags(self, original_text, candidate_text):
        original_paragraphs = self._extract_paragraph_chunks(original_text)
        candidate_paragraphs = self._extract_paragraph_chunks(candidate_text)
        if len(original_paragraphs) <= 1 or len(candidate_paragraphs) <= 1:
            return []

        original_terms = [self._paragraph_content_terms(paragraph['raw']) for paragraph in original_paragraphs]
        candidate_terms = [self._paragraph_content_terms(paragraph['raw']) for paragraph in candidate_paragraphs]
        flags = []
        for candidate_index, terms in enumerate(candidate_terms[:len(original_terms)]):
            if len(terms) < 3:
                continue
            same_terms = original_terms[candidate_index]
            if len(same_terms) < 3:
                continue

            same_score = self._paragraph_term_overlap(terms, same_terms)
            scored = [
                (original_index, self._paragraph_term_overlap(terms, source_terms))
                for original_index, source_terms in enumerate(original_terms)
                if source_terms
            ]
            if not scored:
                continue

            best_index, best_score = max(scored, key=lambda item: item[1])
            if best_index == candidate_index:
                continue
            if best_score >= 0.22 and best_score >= same_score + 0.12:
                flags.append(f'paragraph_scope_shift:p{candidate_index + 1}_from_p{best_index + 1}')
            elif same_score < 0.12 and best_score >= 0.18 and best_score >= same_score + 0.08:
                flags.append(f'paragraph_scope_shift:p{candidate_index + 1}_weak_scope')

            if len(flags) >= 3:
                break

        return flags

    def _summary_wrapup_flags(self, original_text, candidate_text):
        original_norm = re.sub(r'\s+', ' ', (original_text or '').lower())
        candidate_norm = re.sub(r'\s+', ' ', (candidate_text or '').lower())
        flags = []
        for marker in SUMMARY_WRAPUP_PHRASES:
            if candidate_norm.count(marker) > original_norm.count(marker):
                marker_slug = re.sub(r'[^a-z0-9]+', '_', marker).strip('_')
                flags.append(f'summary_wrapup:{marker_slug}')
        return flags

    def _final_paragraph_scope_penalty(self, original_text, candidate_text):
        original_paragraphs = self._extract_paragraph_chunks(original_text)
        candidate_paragraphs = self._extract_paragraph_chunks(candidate_text)
        if not original_paragraphs or not candidate_paragraphs:
            return 0.0, []

        penalty = 0.0
        flags = []

        if len(original_paragraphs) != len(candidate_paragraphs):
            penalty += abs(len(original_paragraphs) - len(candidate_paragraphs)) * 2.5
            flags.append('paragraph_count_changed')

        original_last = original_paragraphs[-1]['raw']
        candidate_last = candidate_paragraphs[-1]['raw']
        original_stats = self._fragment_stats(original_last)
        candidate_stats = self._fragment_stats(candidate_last)

        original_words = max(1, original_stats['word_count'])
        word_ratio = candidate_stats['word_count'] / original_words
        word_ratio_threshold = 1.3 if original_stats['sentence_count'] <= 1 else 1.6
        if word_ratio > word_ratio_threshold:
            penalty += min(7.5, (word_ratio - word_ratio_threshold) * 4.5)
            flags.append('final_paragraph_expanded')

        sentence_growth = candidate_stats['sentence_count'] - original_stats['sentence_count']
        sentence_growth_threshold = 0 if original_stats['sentence_count'] <= 1 else 1
        if sentence_growth > sentence_growth_threshold:
            penalty += min(4.0, (sentence_growth - sentence_growth_threshold) * 2.0)
            flags.append('final_paragraph_sentence_growth')

        return penalty, flags

    def _count_heavy_paragraph_rewrites(self, original_text, candidate_text):
        original_paragraphs = self._extract_paragraph_chunks(original_text)
        candidate_paragraphs = self._extract_paragraph_chunks(candidate_text)
        if not original_paragraphs or not candidate_paragraphs:
            return 0

        heavy_rewrites = 0
        for original_paragraph, candidate_paragraph in zip(original_paragraphs, candidate_paragraphs):
            if original_paragraph['normalized'] == candidate_paragraph['normalized']:
                continue
            ratio = difflib.SequenceMatcher(
                None,
                original_paragraph['normalized'],
                candidate_paragraph['normalized'],
                autojunk=False,
            ).ratio()
            if ratio < 0.45 and self._fragment_stats(original_paragraph['raw'])['word_count'] >= 20:
                heavy_rewrites += 1

        heavy_rewrites += abs(len(original_paragraphs) - len(candidate_paragraphs))
        return heavy_rewrites

    def _build_selection_summary(self, policy, source_grade, target_grade, selected_candidate, top_candidates):
        selected_text_key = re.sub(r'\s+', ' ', selected_candidate.get('text', '')).strip()
        selected_display_grade = self._display_grade_number_from_score(selected_candidate['raw_score'])
        display_grade_delta = abs(selected_display_grade - int(target_grade))
        target_status = self._target_status_from_score(selected_candidate['raw_score'], target_grade)
        rejected_target_band = [
            candidate for candidate in top_candidates
            if (
                re.sub(r'\s+', ' ', candidate.get('text', '')).strip() != selected_text_key and
                candidate.get('direction_hit') and
                candidate.get('target_distance', 999) <= 1.0
            )
        ]
        closest_rejected = None
        if rejected_target_band:
            candidate = min(
                rejected_target_band,
                key=lambda item: (
                    item.get('target_distance', 999),
                    self._candidate_invalid_delta(item),
                    item.get('candidate_score', 999),
                    -item.get('semantic_similarity_score', 0),
                ),
            )
            closest_rejected = {
                'raw_score': candidate['raw_score'],
                'target_distance': candidate['target_distance'],
                'score': candidate['candidate_score'],
                'semantic_similarity_score': candidate['semantic_similarity_score'],
                'blocking_flags': self._candidate_blocking_flags(candidate),
                'validation_flags': candidate.get('validation_flags', []),
                'selection_path': candidate.get('rule_history', []),
            }

        def summarize_candidate(candidate):
            if not candidate:
                return None
            return {
                'raw_score': candidate['raw_score'],
                'display_grade': self._display_grade_number_from_score(candidate['raw_score']),
                'target_status': self._target_status_from_score(candidate['raw_score'], target_grade),
                'display_grade_delta': self._display_grade_delta_from_score(candidate['raw_score'], target_grade),
                'target_distance': candidate['target_distance'],
                'score': candidate['candidate_score'],
                'semantic_similarity_score': candidate['semantic_similarity_score'],
                'blocking_flags': self._candidate_blocking_flags(candidate),
                'validation_flags': candidate.get('validation_flags', []),
                'selection_path': candidate.get('rule_history', []),
            }

        closest_safe = None
        safe_candidates = [
            candidate for candidate in top_candidates
            if (
                re.sub(r'\s+', ' ', candidate.get('text', '')).strip() != selected_text_key and
                self._candidate_is_target_lock_safe(candidate, target_grade)
            )
        ]
        if safe_candidates:
            closest_safe = min(
                safe_candidates,
                key=lambda item: self._target_lock_rank_key(item, target_grade),
            )

        blocked_candidates = [
            candidate for candidate in top_candidates
            if (
                re.sub(r'\s+', ' ', candidate.get('text', '')).strip() != selected_text_key and
                self._candidate_blocking_flags(candidate)
            )
        ]
        closest_blocked = None
        if blocked_candidates:
            closest_blocked = min(
                blocked_candidates,
                key=lambda item: (
                    self._candidate_display_delta(item, target_grade),
                    item.get('target_distance', 999),
                    item.get('candidate_score', 999),
                ),
            )

        print(
            "[selection] selected "
            f"path={selected_candidate.get('rule_history', [])} "
            f"raw={selected_candidate['raw_score']:.2f} "
            f"display_grade={selected_display_grade} "
            f"target_status={target_status} "
            f"target_distance={selected_candidate['target_distance']:.2f} "
            f"flags={selected_candidate.get('validation_flags', [])[:6]}"
        )
        if closest_safe:
            print(
                "[selection] closest_safe "
                f"path={closest_safe.get('rule_history', [])} "
                f"raw={closest_safe['raw_score']:.2f} "
                f"display_grade={self._display_grade_number_from_score(closest_safe['raw_score'])} "
                f"target_distance={closest_safe['target_distance']:.2f} "
                f"flags={closest_safe.get('validation_flags', [])[:6]}"
            )
        if closest_blocked:
            print(
                "[selection] closest_blocked "
                f"path={closest_blocked.get('rule_history', [])} "
                f"raw={closest_blocked['raw_score']:.2f} "
                f"display_grade={self._display_grade_number_from_score(closest_blocked['raw_score'])} "
                f"target_distance={closest_blocked['target_distance']:.2f} "
                f"blocking={self._candidate_blocking_flags(closest_blocked)} "
                f"flags={closest_blocked.get('validation_flags', [])[:6]}"
            )
        if closest_rejected:
            print(
                "[selection] closest_rejected_target_band "
                f"path={closest_rejected.get('selection_path', [])} "
                f"raw={closest_rejected['raw_score']:.2f} "
                f"target_distance={closest_rejected['target_distance']:.2f} "
                f"blocking={closest_rejected.get('blocking_flags', [])} "
                f"flags={closest_rejected.get('validation_flags', [])[:6]}"
            )
        return {
            'policy_bucket': policy['label'],
            'beam_width': policy['beam_width'],
            'source_grade': round(source_grade, 2),
            'target_grade': target_grade,
            'selected_score': selected_candidate['candidate_score'],
            'selected_raw_score': selected_candidate['raw_score'],
            'selected_display_grade': selected_display_grade,
            'display_grade_delta': display_grade_delta,
            'target_status': target_status,
            'selected_path': selected_candidate.get('rule_history', []),
            'selected_validation_flags': selected_candidate.get('validation_flags', []),
            'selected_blocking_flags': self._candidate_blocking_flags(selected_candidate),
            'direction_hit': selected_candidate['direction_hit'],
            'target_distance': selected_candidate['target_distance'],
            'invalid_sentence_count': selected_candidate['invalid_sentence_count'],
            'invalid_sentence_delta': selected_candidate.get('invalid_sentence_delta', 0),
            'semantic_similarity_score': selected_candidate['semantic_similarity_score'],
            'closest_rejected_target_band_candidate': closest_rejected,
            'closest_safe_candidate': summarize_candidate(closest_safe),
            'closest_blocked_candidate': summarize_candidate(closest_blocked),
            'top_candidates': [
                {
                    'index': index,
                    'score': candidate['candidate_score'],
                    'raw_score': candidate['raw_score'],
                    'display_grade': self._display_grade_number_from_score(candidate['raw_score']),
                    'target_status': self._target_status_from_score(candidate['raw_score'], target_grade),
                    'display_grade_delta': self._display_grade_delta_from_score(candidate['raw_score'], target_grade),
                    'target_distance': candidate['target_distance'],
                    'direction_hit': candidate['direction_hit'],
                    'invalid_sentence_count': candidate['invalid_sentence_count'],
                    'invalid_sentence_delta': candidate.get('invalid_sentence_delta', 0),
                    'semantic_similarity_score': candidate['semantic_similarity_score'],
                    'selection_path': candidate.get('rule_history', []),
                    'validation_flags': candidate.get('validation_flags', []),
                    'blocking_flags': self._candidate_blocking_flags(candidate),
                    'text': candidate['text'],
                }
                for index, candidate in enumerate(top_candidates)
            ],
        }
