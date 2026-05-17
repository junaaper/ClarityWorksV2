from .base import *


class PublicSimplifierMixin:
    def simplify_to_grade(self, text, target_grade, mode='auto', prefer_rule_based=False, progress_callback=None):
        """
        Rewrite pipeline:
          1. Build a candidate pool for the requested target grade.
          2. When LLM authoring is enabled, spend one rewrite call, mix that
             draft with deterministic rule candidates, and score them together.
          3. Finalize the winning text into anchored word/sentence patches so
             Auto and Interactive expose the same reviewable change set.
        """
        previous_budget = self._llm_call_budget
        previous_calls = self._llm_calls_made
        source_grade_for_budget = self._measure_text_metrics(text)[0]
        rewrite_route = self._classify_rewrite_route(text, source_grade_for_budget, target_grade)
        self._llm_call_budget = (
            self._planned_llm_call_budget(source_grade_for_budget, target_grade, text=text)
            if self.llm_client else None
        )
        self._llm_calls_made = 0
        self._metrics_tls.cache = {}
        self._metrics_tls.llm_timeout_fallback = False
        self._emit_progress(
            progress_callback,
            0.03,
            f'Using {rewrite_route.replace("_", " ")} route...',
            None,
            rewrite_route=rewrite_route,
            phase='route',
            llm_calls_used=0,
            llm_call_budget=self._llm_call_budget,
        )

        try:
            selection = None
            paragraph_pipeline_failed = False
            paragraph_pipeline_failed_reason = ''
            if (self.llm_client and not prefer_rule_based
                    and rewrite_route == 'large_shift_llm'):
                try:
                    para_result = self._paragraph_pipeline(text, target_grade, mode, progress_callback=progress_callback)
                    if para_result is not None:
                        selection = para_result
                except Exception as e:
                    print(f"[paragraph_pipeline] failed, using rule fallback instead of whole-document LLM: {e}")
                    paragraph_pipeline_failed = True
                    paragraph_pipeline_failed_reason = str(e)
                    if self._is_timeout_error(e):
                        self._mark_llm_timeout_fallback()
                    selection = None

            if selection is None:
                self._emit_progress(
                    progress_callback,
                    0.05,
                    'Analyzing text...',
                    None,
                    rewrite_route=rewrite_route,
                    phase='analyze',
                )
                use_rule_first = (
                    prefer_rule_based or
                    self._route_uses_rule_first(rewrite_route) or
                    paragraph_pipeline_failed
                )
                if (
                    paragraph_pipeline_failed and
                    self._is_timeout_error(paragraph_pipeline_failed_reason) and
                    self._is_short_high_upgrade(text, source_grade_for_budget, target_grade)
                ):
                    use_rule_first = False
                selection = self._select_authoring_candidate(
                    text=text,
                    target_grade=target_grade,
                    mode=mode,
                    prefer_rule_based=use_rule_first,
                    progress_callback=progress_callback,
                )
                if paragraph_pipeline_failed:
                    selection['selection_summary'] = {
                        **dict(selection.get('selection_summary') or {}),
                        'generation_mode': (
                            'whole_text_after_paragraph_pipeline_timeout'
                            if not use_rule_first else
                            'rule_primary_after_paragraph_pipeline_failure'
                        ),
                        'paragraph_pipeline_failed': True,
                        'paragraph_pipeline_failed_reason': paragraph_pipeline_failed_reason,
                        'llm_timeout_fallback': self._is_timeout_error(paragraph_pipeline_failed_reason),
                    }
                # Escalate to LLM when rule-based returned identity and target hasn't been met
                if (
                    use_rule_first
                    and not paragraph_pipeline_failed
                    and self.llm_client
                    and selection['text'].strip() == text.strip()
                    and self._get_target_direction(
                        self._measure_text_metrics(text)[0], target_grade
                    ) != 0
                ):
                    # For small_shift_fast, cap escalation to 2 LLM calls for speed
                    saved_budget = None
                    if rewrite_route == 'small_shift_fast':
                        saved_budget = self._llm_call_budget
                        self._llm_call_budget = self._llm_calls_made + 2

                    print(f"[identity-escalation] rule returned identity, escalating to LLM for {rewrite_route}")
                    llm_selection = self._select_authoring_candidate(
                        text=text,
                        target_grade=target_grade,
                        mode=mode,
                        prefer_rule_based=False,
                        progress_callback=progress_callback,
                    )

                    if saved_budget is not None:
                        self._llm_call_budget = saved_budget

                    if llm_selection['text'].strip() != text.strip():
                        selection = llm_selection
                        selection['selection_summary'] = {
                            **dict(selection.get('selection_summary') or {}),
                            'generation_mode': 'llm_escalation_from_identity',
                        }
        finally:
            llm_calls_used = self._llm_calls_made
            self._llm_call_budget = previous_budget
            self._llm_calls_made = previous_calls
            self._metrics_tls.cache = None

        current_text = selection['text']
        going_up = selection['going_up']
        critic_review = None
        used_paragraph_pipeline = selection.get('selection_summary', {}).get('generation_mode') == 'paragraph_pipeline'

        self._selection_context = {
            'candidate_score': selection['score'],
            'selection_summary': selection['selection_summary'],
            'top_candidates': selection['top_candidates'],
        }

        self._emit_progress(
            progress_callback,
            0.90,
            'Generating changes...',
            None,
            rewrite_route=rewrite_route,
            phase='diff',
            llm_calls_used=llm_calls_used,
        )

        if used_paragraph_pipeline:
            groups = selection['selection_summary'].get('_rewrite_groups')
            rtexts = selection['selection_summary'].get('_rewritten_texts')
            changes = self._paragraph_level_diff(text, groups, rtexts, target_grade, going_up)
            final_metrics = self._measure_preview_metrics(current_text)
            final_metrics['semantic_similarity_score'] = round(
                self._semantic_similarity_score(text, current_text), 2
            )
            final_metrics['target_distance'] = round(
                self._distance_to_target_band(final_metrics['raw_score'], target_grade), 2
            )
        else:
            current_text, changes, final_metrics = self._finalize_preview_candidate(
                original_text=text,
                candidate_text=current_text,
                target_grade=target_grade,
                going_up=going_up,
            )

        if not used_paragraph_pipeline and changes and final_metrics.get('target_distance', 0) > 0:
            greedy_changes, greedy_text, greedy_metrics = self._greedy_select_changes_for_target(
                original_text=text,
                changes=changes,
                target_grade=target_grade,
                going_up=going_up,
            )
            if greedy_metrics['target_distance'] <= final_metrics['target_distance']:
                changes = greedy_changes
                current_text = greedy_text
                final_metrics = greedy_metrics

        normalized_current_text = re.sub(r'\n +', '\n', current_text).strip()
        if normalized_current_text != current_text:
            current_text, changes, final_metrics = self._finalize_preview_candidate(
                original_text=text,
                candidate_text=normalized_current_text,
                target_grade=target_grade,
                going_up=going_up,
            )

        forced_exact_delivery = False
        defence_target_fallback_used = False
        if not used_paragraph_pipeline and self._should_force_selected_candidate_delivery(selection, final_metrics):
            exact_change = self._build_exact_rebuild_change(
                original_text=text,
                desired_candidate_text=selection['text'],
                target_grade=target_grade,
                going_up=going_up,
            )
            if exact_change:
                exact_change['id'] = 0
                current_text = selection['text']
                changes = self._assign_dependency_groups([exact_change])
                final_metrics = self._measure_preview_metrics(current_text)
                final_metrics['semantic_similarity_score'] = round(
                    self._semantic_similarity_score(text, current_text),
                    2,
                )
                final_metrics['target_distance'] = round(
                    self._distance_to_target_band(final_metrics['raw_score'], target_grade),
                    2,
                )
                forced_exact_delivery = True

        if not used_paragraph_pipeline and self._should_apply_defence_target_fallback(
            original_text=text,
            target_grade=target_grade,
            going_up=going_up,
            final_metrics=final_metrics,
        ):
            fallback_text = self._build_defence_target_fallback(text, target_grade)
            if fallback_text:
                fallback_metrics = self._measure_preview_metrics(fallback_text)
                fallback_metrics['semantic_similarity_score'] = round(
                    self._semantic_similarity_score(text, fallback_text),
                    2,
                )
                fallback_metrics['target_distance'] = round(
                    self._distance_to_target_band(fallback_metrics['raw_score'], target_grade),
                    2,
                )
                if self._display_grade_delta_from_score(
                    fallback_metrics['raw_score'],
                    target_grade,
                ) <= TARGET_LOCK_DISPLAY_BAND_TOLERANCE:
                    exact_change = self._build_exact_rebuild_change(
                        original_text=text,
                        desired_candidate_text=fallback_text,
                        target_grade=target_grade,
                        going_up=going_up,
                    )
                    if exact_change:
                        exact_change['id'] = 0
                        current_text = fallback_text
                        changes = self._assign_dependency_groups([exact_change])
                        final_metrics = fallback_metrics
                        forced_exact_delivery = True
                        defence_target_fallback_used = True
                        print(
                            "[selection] defence_target_fallback selected "
                            f"raw={final_metrics['raw_score']:.2f} "
                            f"display_grade={self._display_grade_number_from_score(final_metrics['raw_score'])} "
                            f"target={target_grade}"
                        )

        self._emit_progress(
            progress_callback,
            0.96,
            'Running local sanity checks...',
            None,
            rewrite_route=rewrite_route,
            phase='sanity',
            llm_calls_used=llm_calls_used,
        )
        local_sanity = self._run_local_sanity_check(
            original_text=text,
            candidate_text=current_text,
            target_grade=target_grade,
            source_grade=source_grade_for_budget,
            final_metrics=final_metrics,
        )
        current_text, changes, final_metrics, local_sanity, route_polish_summary = self._maybe_apply_route_polish(
            original_text=text,
            current_text=current_text,
            target_grade=target_grade,
            going_up=going_up,
            rewrite_route=rewrite_route,
            changes=changes,
            final_metrics=final_metrics,
            sanity=local_sanity,
        )
        llm_calls_used += route_polish_summary.get('route_polish_calls_used', 0)
        normalized_current_text = re.sub(r'\n[ \t]+', '\n', current_text).strip()
        if normalized_current_text != current_text:
            current_text, changes, final_metrics = self._finalize_preview_candidate(
                original_text=text,
                candidate_text=normalized_current_text,
                target_grade=target_grade,
                going_up=going_up,
                prefer_sentence_level=True,
            )
            local_sanity = self._run_local_sanity_check(
                original_text=text,
                candidate_text=current_text,
                target_grade=target_grade,
                source_grade=source_grade_for_budget,
                final_metrics=final_metrics,
            )

        post_review_allowed = False
        validation = self._local_validation_result(current_text, final_metrics, sanity=local_sanity)
        if self.llm_validator.client and post_review_allowed:
            critic_review = self.llm_validator.critic_candidates(
                original_text=text,
                target_grade=target_grade,
                candidates=selection['top_candidates'],
            )
            current_text, changes, validation, final_metrics, final_review_summary = self._apply_llm_repair_pass(
                original_text=text,
                current_text=current_text,
                target_grade=target_grade,
                going_up=going_up,
                changes=changes,
                validation=validation,
                critic_review=critic_review,
            )
        else:
            final_review_summary = {
                'final_review_applied': False,
                'review_adjusted_change_count': 0,
                'llm_calls_used': llm_calls_used,
                'llm_review_skipped_for_rate_limit': bool(self.llm_validator.client),
            }

        selection_summary = dict(selection['selection_summary'])
        candidate_score = selection['score']

        if mode == 'interactive' and not validation['valid'] and validation['issues']:
            print(f"[interactive] Validation issues (not auto-fixing): {validation['issues']}")

        selection_summary = {
            **selection_summary,
            'rewrite_route': rewrite_route,
            'delivered_display_grade': self._display_grade_number_from_score(final_metrics['raw_score']),
            'delivered_display_grade_delta': self._display_grade_delta_from_score(final_metrics['raw_score'], target_grade),
            'delivered_target_status': self._target_status_from_score(final_metrics['raw_score'], target_grade),
            'target_status': self._target_status_from_score(final_metrics['raw_score'], target_grade),
            'confidence_label': self._confidence_label(
                candidate_score,
                final_metrics['invalid_sentence_count'],
                final_metrics['semantic_similarity_score'],
                final_metrics['target_distance'],
            ),
            'invalid_sentence_count': final_metrics['invalid_sentence_count'],
            'semantic_similarity_score': final_metrics['semantic_similarity_score'],
            'llm_calls_used': llm_calls_used,
            'llm_timeout_fallback': bool(getattr(self._metrics_tls, 'llm_timeout_fallback', False)),
            'forced_exact_delivery': forced_exact_delivery,
            'defence_target_fallback_used': defence_target_fallback_used,
            'local_sanity_valid': local_sanity['valid'],
            'local_sanity_flags': local_sanity['flags'],
            'local_sanity_severe_flags': local_sanity['severe_flags'],
            **route_polish_summary,
            **final_review_summary,
        }
        if critic_review:
            selection_summary['critic_review'] = critic_review
        self._selection_context['selection_summary'] = selection_summary

        display_items = self._build_display_changes(text, current_text, target_grade, going_up)
        if display_items:
            self._enrich_changes_with_display_items(changes, display_items)
        reason_summary = self._reason_coverage_summary(changes)
        selection_summary.update(reason_summary)
        self._selection_context['selection_summary'] = selection_summary

        api_summary = {k: v for k, v in selection_summary.items() if not k.startswith('_')}

        return {
            'simplified_text': current_text,
            'changes': changes,
            'original_text': text,
            'validation': validation,
            'preview_metrics': final_metrics,
            'target_distance': final_metrics['target_distance'],
            'selection_summary': api_summary,
        }
