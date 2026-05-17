from .base import *


class FinalizeMixin:
    def _reason_coverage_summary(self, changes):
        if not changes:
            return {
                'reason_coverage_rate': 1.0,
                'generic_reason_count': 0,
                'change_reason_count': 0,
            }

        generic_markers = (
            'AI-assisted simplification',
            'Sentence structure adjusted',
            'Wording adjusted during the final meaning check',
            'Paragraph rewrite kept as one exact preview patch',
        )
        meaningful = 0
        generic = 0
        for change in changes:
            reason = (change.get('reason') or '').strip()
            evidence = change.get('evidence') or {}
            has_structured_reason = bool(change.get('reason_code')) and bool(evidence)
            has_explanation_items = bool(change.get('explanation_items'))
            is_generic = (not reason) or any(marker in reason for marker in generic_markers)
            if is_generic and not has_explanation_items:
                generic += 1
            if reason and (has_structured_reason or has_explanation_items) and not is_generic:
                meaningful += 1

        return {
            'reason_coverage_rate': round(meaningful / max(1, len(changes)), 2),
            'generic_reason_count': generic,
            'change_reason_count': len(changes),
        }

    def _finalize_preview_candidate(
        self,
        original_text,
        candidate_text,
        target_grade,
        going_up,
        prefer_sentence_level=False,
    ):
        candidate_text = self._strip_llm_meta_commentary(candidate_text)
        candidate_text = self._restore_paragraph_shape(original_text, candidate_text)
        desired_candidate_text = candidate_text

        def exact_fallback():
            fallback_change = self._build_exact_rebuild_change(
                original_text,
                desired_candidate_text,
                target_grade,
                going_up,
            )
            if not fallback_change:
                return [], desired_candidate_text
            fallback_change['id'] = 0
            fallback_changes = self._assign_dependency_groups([fallback_change])
            fallback_rebuilt = apply_changes_by_span(
                original_text,
                fallback_changes,
                [change['id'] for change in fallback_changes],
            )
            return fallback_changes, fallback_rebuilt

        changes = self._diff_changes(
            original_text,
            desired_candidate_text,
            target_grade,
            going_up,
            prefer_sentence_level=prefer_sentence_level,
        )
        changes = self._assign_dependency_groups(changes)
        if changes:
            rebuilt_candidate_text = apply_changes_by_span(
                original_text,
                changes,
                [change['id'] for change in changes],
            )

            if rebuilt_candidate_text != desired_candidate_text and not prefer_sentence_level:
                changes = self._diff_changes(
                    original_text,
                    desired_candidate_text,
                    target_grade,
                    going_up,
                    prefer_sentence_level=True,
                )
                changes = self._assign_dependency_groups(changes)
                if changes:
                    rebuilt_candidate_text = apply_changes_by_span(
                        original_text,
                        changes,
                        [change['id'] for change in changes],
                    )
                else:
                    rebuilt_candidate_text = original_text

            if rebuilt_candidate_text != desired_candidate_text:
                if rebuilt_candidate_text.split() == desired_candidate_text.split():
                    pass
                else:
                    # Per-sentence fallback: pair each original sentence with the
                    # closest rewritten sentence instead of collapsing to one patch.
                    fuzzy = self._fuzzy_sentence_diff(
                        original_text, desired_candidate_text, target_grade, going_up,
                    )
                    if fuzzy and len(fuzzy) >= 2:
                        fuzzy = self._assign_dependency_groups(fuzzy)
                        fuzzy_rebuilt = apply_changes_by_span(
                            original_text,
                            fuzzy,
                            [c['id'] for c in fuzzy],
                        )
                        if fuzzy_rebuilt.split() == desired_candidate_text.split():
                            changes = fuzzy
                            rebuilt_candidate_text = fuzzy_rebuilt
                        else:
                            changes, rebuilt_candidate_text = exact_fallback()
                    else:
                        changes, rebuilt_candidate_text = exact_fallback()

            candidate_text = rebuilt_candidate_text
        else:
            changes, candidate_text = exact_fallback()

        final_metrics = self._measure_preview_metrics(candidate_text)
        final_metrics['semantic_similarity_score'] = round(
            self._semantic_similarity_score(original_text, candidate_text),
            2,
        )
        final_metrics['target_distance'] = round(
            self._distance_to_target_band(final_metrics['raw_score'], target_grade),
            2,
        )
        return candidate_text, changes, final_metrics

    def _build_exact_rebuild_change(self, original_text, desired_candidate_text, target_grade, going_up):
        """
        Last-resort review patch for cases where granular anchors cannot
        reconstruct the selected candidate exactly. The selected text has
        already been scored, so finalization must not silently deliver a
        different grade because a smaller diff dropped a split sentence.
        """
        if original_text == desired_candidate_text:
            return None

        fallback_change = self._build_patch_change(
            original_text,
            desired_candidate_text,
            0,
            len(original_text),
            0,
            target_grade,
            going_up,
            allow_fallback=True,
        )
        if fallback_change:
            validation_flags = list(fallback_change.get('validation_flags') or [])
            if 'exact_preview_rebuild' not in validation_flags:
                validation_flags.append('exact_preview_rebuild')
            fallback_change['validation_flags'] = validation_flags
            return fallback_change

        original_display = original_text.strip() or original_text
        replacement_display = desired_candidate_text.strip() or desired_candidate_text
        original_stats = self._fragment_stats(original_display)
        replacement_stats = self._fragment_stats(replacement_display)
        candidate_score = self._selection_context.get('candidate_score', 0.0)
        change_type = 'phrase_rewrite'
        explanation_items = self._extract_explanation_items(
            original_display,
            replacement_display,
            going_up,
        )
        clauses_before = self._approx_clause_count(original_display)
        clauses_after = self._approx_clause_count(replacement_display)
        examples = "; ".join(item.get('text', '') for item in explanation_items[:3] if item.get('text'))
        target_label = self._target_grade_label(target_grade)
        if examples:
            reason = (
                f"Rebuilt this broad paragraph rewrite exactly while preserving word-level evidence: "
                f"{examples} Clause complexity changed {clauses_before} -> {clauses_after} for {target_label}."
            )
        else:
            reason = (
                f"Rebuilt this broad paragraph rewrite exactly so the delivered text matches the selected "
                f"{target_label} candidate (avg syllables {original_stats['avg_syllables']:.2f} -> "
                f"{replacement_stats['avg_syllables']:.2f}, clauses {clauses_before} -> {clauses_after})."
            )

        return {
            'type': change_type,
            'original': original_display,
            'simplified': replacement_display,
            'original_text': original_text,
            'replacement_text': desired_candidate_text,
            'position': 0,
            'start': 0,
            'end': len(original_text),
            'preview_start': 0,
            'preview_end': len(desired_candidate_text),
            'review_scope': 'paragraph',
            'direction': 'up' if going_up else 'down',
            'quality_score': 0.35,
            'quality_flags': ['coarse_review', 'forced_exact_rebuild'],
            'rule_id': 'selection.exact_preview_rebuild',
            'reason_code': 'reshape_text_for_target',
            'evidence': {
                'target_grade': target_grade,
                'direction': 'up' if going_up else 'down',
                'review_scope': 'paragraph',
                'word_count_before': original_stats['word_count'],
                'word_count_after': replacement_stats['word_count'],
                'sentence_count_before': original_stats['sentence_count'],
                'sentence_count_after': replacement_stats['sentence_count'],
                'boundary_count_before': len(re.findall(r'[.!?]+', original_display or '')),
                'boundary_count_after': len(re.findall(r'[.!?]+', replacement_display or '')),
                'clause_count_before': clauses_before,
                'clause_count_after': clauses_after,
                'avg_syllables_before': round(original_stats['avg_syllables'], 2),
                'avg_syllables_after': round(replacement_stats['avg_syllables'], 2),
                'candidate_score': candidate_score,
                'explanation_items': explanation_items,
            },
            'candidate_score': candidate_score,
            'validation_flags': ['exact_preview_rebuild'],
            'explanation_items': explanation_items,
            'reason': reason,
        }

    def _iterative_rule_rewrite(self, text, target_grade):
        """
        Preserve the old pass-based rule engine as one deterministic candidate.
        This remains useful when a single linear strategy outperforms beam
        combinations for a specific source/target pair.
        """
        current_text = text
        target_metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        initial_grade, _, _ = self._measure_text_metrics(text)
        best_text = text
        best_grade = initial_grade
        best_score = self._alignment_score(initial_grade, target_grade)
        pass_budget = 5 + min(3, int(abs(float(target_grade) - float(initial_grade)) // 2))

        for pass_index in range(pass_budget):
            estimated_grade, current_syl, current_wps = self._measure_text_metrics(current_text)
            direction = self._get_target_direction(estimated_grade, target_grade)
            going_up = direction > 0
            near_target = self._distance_to_target_band(estimated_grade, target_grade) <= 0.75

            print(f"[rewrite] pass={pass_index + 1} estimated={estimated_grade:.1f} "
                  f"(syl={current_syl:.2f}, wps={current_wps:.1f}) "
                  f"-> target={target_grade} (syl={target_metrics['target_syl']:.2f}, "
                  f"wps={target_metrics['target_wps']}) going_up={going_up}")

            if direction == 0:
                break

            previous_text = current_text

            if going_up:
                if near_target:
                    if current_wps < target_metrics['target_wps'] - 0.5:
                        structure_base_text = current_text
                        current_text, combine_changes = self._combine_short_sentences(
                            current_text,
                            target_grade,
                            max_combinations=1
                        )
                        current_text, _ = self._accept_structural_rewrite(
                            structure_base_text,
                            current_text,
                            combine_changes
                        )
                    else:
                        current_text, _ = self._complexify_text(
                            current_text,
                            target_grade,
                            max_changes=2
                        )
                else:
                    current_text, _ = self._complexify_text(current_text, target_grade)
                    structure_base_text = current_text
                    current_text, combine_changes = self._combine_short_sentences(current_text, target_grade)
                    current_text, _ = self._accept_structural_rewrite(
                        structure_base_text,
                        current_text,
                        combine_changes
                    )
            else:
                if near_target:
                    if current_wps > target_metrics['target_wps'] + 0.5:
                        structure_base_text = current_text
                        current_text, split_changes = self._split_long_sentences(
                            current_text,
                            target_grade,
                            max_sentence_changes=1
                        )
                        current_text, _ = self._accept_structural_rewrite(
                            structure_base_text,
                            current_text,
                            split_changes
                        )
                    else:
                        current_text, _ = self._replace_difficult_words(
                            current_text,
                            target_grade,
                            max_changes=3
                        )
                else:
                    current_text, _ = self._replace_difficult_words(current_text, target_grade)
                    structure_base_text = current_text
                    current_text, split_changes = self._split_long_sentences(current_text, target_grade)
                    current_text, _ = self._accept_structural_rewrite(
                        structure_base_text,
                        current_text,
                        split_changes
                    )

            candidate_grade, _, _ = self._measure_text_metrics(current_text)
            candidate_score = self._alignment_score(candidate_grade, target_grade)
            if candidate_score < best_score:
                best_text = current_text
                best_grade = candidate_grade
                best_score = candidate_score

            if current_text == previous_text:
                break

        if best_score <= self._alignment_score(self._measure_text_metrics(current_text)[0], target_grade) + 1e-9:
            current_text = best_text

        return {
            'text': current_text,
            'rule_history': ['selection.legacy_iterative'],
            'stage_notes': ['legacy_iterative'],
        }
