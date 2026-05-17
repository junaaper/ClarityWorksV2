from .base import *


class AuthoringMixin:
    def _select_authoring_candidate(self, text, target_grade, mode, prefer_rule_based=False, progress_callback=None):
        source_grade, _, _ = self._measure_text_metrics(text)
        direction = self._get_target_direction(source_grade, target_grade)
        going_up = direction > 0
        policy = self._get_target_policy(target_grade, going_up, source_grade=source_grade)

        if progress_callback:
            progress_callback(0.10, 'Analyzing text...', None)

        rule_selection = self._select_rewrite_candidate(text, target_grade, mode)
        if prefer_rule_based or not self.llm_client or direction == 0:
            summary = {
                **dict(rule_selection['selection_summary']),
                'generation_mode': 'rule_primary',
                'candidate_pool': {
                    'rule': len(rule_selection['top_candidates']),
                    'llm': 0,
                },
            }
            return {
                **rule_selection,
                'selection_summary': summary,
            }

        rule_candidates = []
        for candidate in rule_selection['top_candidates']:
            rule_candidates.append({
                'text': candidate['text'],
                'rule_history': candidate.get('selection_path', ['selection.rule_candidate']),
                'stage_notes': candidate.get('selection_path', ['rule']),
            })

        if progress_callback:
            progress_callback(0.25, 'Exploring rewrites...', None)

        llm_candidates = self._generate_llm_candidates(
            original_text=text,
            target_grade=target_grade,
            source_grade=source_grade,
            going_up=going_up,
            mode=mode,
            policy=policy,
            rule_selection=rule_selection,
        )
        if not llm_candidates:
            summary = {
                **dict(rule_selection['selection_summary']),
                'generation_mode': 'rule_primary_fallback',
                'candidate_pool': {
                    'rule': len(rule_candidates),
                    'llm': 0,
                },
            }
            return {
                **rule_selection,
                'selection_summary': summary,
            }

        if progress_callback:
            progress_callback(0.55, 'Evaluating results...', None)

        all_candidates = rule_candidates + llm_candidates
        target_repair_candidates = self._target_lock_repair_candidates(
            original_text=text,
            candidates=all_candidates,
            target_grade=target_grade,
            source_grade=source_grade,
            going_up=going_up,
            mode=mode,
            policy=policy,
        )
        ranked = self._rank_candidates(
            original_text=text,
            candidates=all_candidates + target_repair_candidates,
            target_grade=target_grade,
            mode=mode,
            source_grade=source_grade,
            policy=policy,
        )
        protected_repair_candidates = self._near_target_guardrail_repair_candidates(
            original_text=text,
            ranked_candidates=ranked,
            target_grade=target_grade,
            source_grade=source_grade,
            going_up=going_up,
            mode=mode,
            policy=policy,
        )
        if protected_repair_candidates:
            ranked = self._rank_candidates(
                original_text=text,
                candidates=all_candidates + target_repair_candidates + protected_repair_candidates,
                target_grade=target_grade,
                mode=mode,
                source_grade=source_grade,
                policy=policy,
            )
        selected = self._select_preferred_candidate(ranked, target_grade=target_grade)

        if progress_callback:
            progress_callback(0.75, 'Refining...', None)

        target_contract_candidates = []
        post_contract_repair_candidates = []
        if self._selection_needs_target_contract_rescue(
            selected_candidate=selected,
            target_grade=target_grade,
            source_grade=source_grade,
            going_up=going_up,
        ):
            target_contract_candidates = self._target_contract_rescue_candidates(
                original_text=text,
                selected_candidate=selected,
                top_candidates=ranked,
                target_grade=target_grade,
                source_grade=source_grade,
                going_up=going_up,
                mode=mode,
                policy=policy,
            )
            if target_contract_candidates:
                post_contract_repair_candidates = self._target_lock_repair_candidates(
                    original_text=text,
                    candidates=target_contract_candidates,
                    target_grade=target_grade,
                    source_grade=source_grade,
                    going_up=going_up,
                    mode=mode,
                    policy=policy,
                )
                ranked = self._rank_candidates(
                    original_text=text,
                    candidates=(
                        all_candidates +
                        target_repair_candidates +
                        protected_repair_candidates +
                        target_contract_candidates +
                        post_contract_repair_candidates
                    ),
                    target_grade=target_grade,
                    mode=mode,
                    source_grade=source_grade,
                    policy=policy,
                )
                post_contract_protected_repairs = self._near_target_guardrail_repair_candidates(
                    original_text=text,
                    ranked_candidates=ranked,
                    target_grade=target_grade,
                    source_grade=source_grade,
                    going_up=going_up,
                    mode=mode,
                    policy=policy,
                )
                if post_contract_protected_repairs:
                    post_contract_repair_candidates.extend(post_contract_protected_repairs)
                    ranked = self._rank_candidates(
                        original_text=text,
                        candidates=(
                            all_candidates +
                            target_repair_candidates +
                            protected_repair_candidates +
                            target_contract_candidates +
                            post_contract_repair_candidates
                        ),
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
        summary.update({
            'generation_mode': 'llm_augmented_single_pass' if self.rate_limited_llm else 'llm_augmented',
            'candidate_pool': {
                'rule': len(rule_candidates),
                'llm': len(llm_candidates),
                'target_repair': len(target_repair_candidates),
                'protected_repair': len(protected_repair_candidates),
                'target_contract_rescue': len(target_contract_candidates),
                'post_contract_repair': len(post_contract_repair_candidates),
            },
        })

        return {
            'text': selected['text'],
            'score': selected['candidate_score'],
            'going_up': going_up,
            'selection_summary': summary,
            'top_candidates': summary['top_candidates'],
        }

    def _generate_llm_candidates(
        self,
        original_text,
        target_grade,
        source_grade,
        going_up,
        mode,
        policy,
        rule_selection,
    ):
        if not self.llm_client:
            return []

        generated = []
        hard_jump = self._is_hard_llm_jump(source_grade, target_grade)

        # One Fireworks call asks for multiple full-text variants. This keeps
        # the request call-efficient while still giving the local scorer real
        # choices instead of betting the whole rewrite on one draft.
        rule_seed_text = rule_selection.get('text')
        seed = rule_seed_text if (rule_seed_text and rule_seed_text != original_text) else original_text
        seed_label = 'rule_seeded' if seed != original_text else 'direct'

        timed_out = False
        try:
            variants = self._llm_multi_variant_rewrite(
                original_text=original_text,
                seed_text=seed,
                target_grade=target_grade,
                source_grade=source_grade,
                going_up=going_up,
                policy=policy,
                seed_label=seed_label,
            )
        except Exception as exc:
            if not self._is_timeout_error(exc):
                raise
            self._mark_llm_timeout_fallback()
            print(f"[fireworks] multi-variant rewrite timed out; using deterministic fallback: {exc}")
            timed_out = True
            variants = []
        for variant in variants:
            variant_name = variant.get('name') or 'targeted'
            if hard_jump:
                variant_text = self._strip_llm_meta_commentary(variant['text'] or '').strip()
            else:
                variant_text = self._rule_adjust_llm_candidate_to_target(
                    variant['text'],
                    target_grade=target_grade,
                    going_up=going_up,
                )
            variant_text = self._restore_paragraph_shape(original_text, variant_text)
            if not variant_text or not variant_text.strip():
                continue
            generated.append({
                'text': variant_text,
                'rule_history': [f'llm.{seed_label}.{variant_name}.single_call'],
                'stage_notes': [f'llm:{seed_label}:{variant_name}:single_call'],
            })

        if generated:
            return self._add_llm_cascade_candidates(
                original_text=original_text,
                generated=generated,
                target_grade=target_grade,
                source_grade=source_grade,
                going_up=going_up,
                mode=mode,
                policy=policy,
            )
        if timed_out:
            return []

        if self._llm_call_budget is not None and self._llm_calls_made >= self._llm_call_budget:
            return []

        try:
            llm_text, _ = self._llm_full_rewrite(
                seed,
                target_grade,
                going_up=going_up,
                rewrite_style='balanced',
                reference_text=original_text,
                plan_label=f'llm.{seed_label}.fallback_balanced',
                include_diff=False,
            )
        except Exception as exc:
            if not self._is_timeout_error(exc):
                raise
            self._mark_llm_timeout_fallback()
            print(f"[fireworks] fallback rewrite timed out; using deterministic fallback: {exc}")
            llm_text = None
        if llm_text and llm_text.strip():
            llm_text = self._restore_paragraph_shape(original_text, llm_text)
            generated.append({
                'text': llm_text,
                'rule_history': [f'llm.{seed_label}.fallback_balanced'],
                'stage_notes': [f'llm:{seed_label}:fallback_balanced'],
            })

        return self._add_llm_cascade_candidates(
            original_text=original_text,
            generated=generated,
            target_grade=target_grade,
            source_grade=source_grade,
            going_up=going_up,
            mode=mode,
            policy=policy,
        )

    def _add_llm_cascade_candidates(
        self,
        original_text,
        generated,
        target_grade,
        source_grade,
        going_up,
        mode,
        policy,
    ):
        if not generated:
            return []

        hard_jump = self._is_hard_llm_jump(source_grade, target_grade)
        if not hard_jump:
            return generated

        best = self._best_llm_cascade_seed(
            original_text=original_text,
            candidates=generated,
            target_grade=target_grade,
            source_grade=source_grade,
            mode=mode,
            policy=policy,
        )
        if not best:
            return generated

        if not self._llm_cascade_needs_more_work(best, target_grade, source_grade):
            return generated

        short_high_upgrade = self._is_short_high_upgrade(original_text, source_grade, target_grade)
        should_try_correction = self._llm_calls_remaining()
        if short_high_upgrade and 11 <= int(target_grade) <= 12:
            should_try_correction = should_try_correction and float(best.get('raw_score', 0.0) or 0.0) < 10.0

        if should_try_correction:
            try:
                corrected = self._llm_target_correction(
                    original_text=original_text,
                    candidate_text=best['text'],
                    metrics=best,
                    target_grade=target_grade,
                    source_grade=source_grade,
                    going_up=going_up,
                    pass_label='target_correction',
                )
            except Exception as exc:
                if not self._is_timeout_error(exc):
                    raise
                self._mark_llm_timeout_fallback()
                print(f"[fireworks] cascade/target_correction timed out; keeping first-pass candidates: {exc}")
                corrected = None
            if corrected:
                corrected = self._restore_paragraph_shape(original_text, corrected)
                generated.append({
                    'text': corrected,
                    'rule_history': best.get('rule_history', []) + ['llm.target_correction'],
                    'stage_notes': best.get('stage_notes', []) + ['llm:target_correction'],
                })
        elif short_high_upgrade:
            print(
                "[fireworks] cascade/target_correction skipped for short high upgrade: "
                f"raw={float(best.get('raw_score', 0.0) or 0.0):.2f}"
            )

        best_after_correction = self._best_llm_cascade_seed(
            original_text=original_text,
            candidates=generated,
            target_grade=target_grade,
            source_grade=source_grade,
            mode=mode,
            policy=policy,
        )
        if not best_after_correction:
            return generated
        if short_high_upgrade:
            return generated

        reserve_target_contract = self._should_reserve_target_contract_call(
            source_grade=source_grade,
            target_grade=target_grade,
            going_up=going_up,
        )
        if (
            self._llm_calls_remaining(reserve=1 if reserve_target_contract else 0) and
            self._llm_cascade_needs_cleanup(best_after_correction, target_grade, source_grade)
        ):
            repaired = self._llm_safety_cleanup(
                original_text=original_text,
                candidate_text=best_after_correction['text'],
                metrics=best_after_correction,
                target_grade=target_grade,
                source_grade=source_grade,
                going_up=going_up,
            )
            if repaired:
                repaired = self._restore_paragraph_shape(original_text, repaired)
                generated.append({
                    'text': repaired,
                    'rule_history': best_after_correction.get('rule_history', []) + ['llm.safety_cleanup'],
                    'stage_notes': best_after_correction.get('stage_notes', []) + ['llm:safety_cleanup'],
                })
        elif (
            reserve_target_contract and
            self._llm_cascade_needs_cleanup(best_after_correction, target_grade, source_grade)
        ):
            print(
                "[fireworks] cascade/safety_cleanup skipped: "
                "reserving final call for target_contract_rescue"
            )

        return generated

    def _near_target_guardrail_repair_candidates(
        self,
        original_text,
        ranked_candidates,
        target_grade,
        source_grade,
        going_up,
        mode,
        policy,
    ):
        if not self.llm_client or not ranked_candidates:
            return []

        repairable = [
            candidate for candidate in ranked_candidates
            if self._candidate_needs_near_target_guardrail_repair(candidate, target_grade)
        ]
        if not repairable:
            return []
        if not self._llm_calls_remaining():
            print("[selection] near_target_repair skipped: LLM call budget exhausted")
            return []

        candidate = min(
            repairable,
            key=lambda item: (
                self._candidate_display_delta(item, target_grade),
                item.get('target_distance', 999),
                item.get('candidate_score', 999),
            ),
        )
        return self._repair_near_target_candidate(
            original_text=original_text,
            candidate=candidate,
            target_grade=target_grade,
            source_grade=source_grade,
            going_up=going_up,
            mode=mode,
            policy=policy,
        )

    def _candidate_needs_near_target_guardrail_repair(self, candidate, target_grade):
        if target_grade is None:
            return False
        status = self._candidate_target_status(candidate, target_grade)
        repairable_demo_miss = (
            target_grade <= 7 and
            candidate.get('target_distance', 999) <= 2.0 and
            self._candidate_display_delta(candidate, target_grade) <= 2
        )
        if status not in {'exact', 'near'} and not repairable_demo_miss:
            return False
        if self._candidate_invalid_delta(candidate) > 3:
            return False
        blocking = self._candidate_blocking_flags(candidate)
        if not blocking:
            return False
        return all(
            flag.startswith('missing_protected_term:') or flag == 'blocked_substitution:but'
            for flag in blocking
        )

    def _repair_near_target_candidate(
        self,
        original_text,
        candidate,
        target_grade,
        source_grade,
        going_up,
        mode,
        policy,
    ):
        missing_terms = self._missing_protected_terms_from_flags(
            original_text,
            candidate.get('validation_flags', []),
            strict_only=True,
            core_only=True,
        )
        if not missing_terms:
            print(
                "[selection] near_target_repair skipped: "
                f"no strict terms resolved for flags={candidate.get('validation_flags', [])[:6]}"
            )
            return []

        target_metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        grade_label = self._target_grade_label(target_grade)
        paragraph_count = max(1, len(self._extract_paragraph_chunks(original_text)))
        missing_manifest = "\n".join(f"- {term}" for term in missing_terms)
        prompt = f"""Repair this near-target rewrite without changing its readability level.

The candidate is already close to {grade_label}; do NOT make it harder or more academic.
Only restore the missing protected terms/facts listed below. Keep the same paragraph count and idea order.
Paragraph mapping is strict: paragraph 1 may only rewrite paragraph 1, paragraph 2 may only rewrite paragraph 2, and so on.

Target metrics to preserve:
- Average words per sentence: about {target_metrics['target_wps']} ({target_metrics['min_wps']}-{target_metrics['max_wps']})
- Average syllables per word: about {target_metrics['target_syl']:.2f}
- Paragraph count: exactly {paragraph_count}

Missing protected terms/facts to restore exactly:
{missing_manifest}

Rules:
- Preserve names, numbers, acronyms, university/program/campus/tool/product names, and GPA/CGPA values exactly.
- Do not add explanations, labels, markdown, notes, or commentary.
- Return only the repaired rewrite.

ORIGINAL FACT REFERENCE:
{original_text}

NEAR-TARGET CANDIDATE:
{candidate.get('text', '')}

REPAIRED REWRITE:"""
        response = self._llm_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.08,
            max_tokens=4096,
        )
        if response is None:
            print("[selection] near_target_repair skipped: LLM returned no response")
            return []

        text = self._normalize_llm_variant_text(response.choices[0].message.content.strip())
        text = self._restore_paragraph_shape(original_text, text)
        if not text.strip():
            print("[selection] near_target_repair skipped: empty repaired text")
            return []

        scored = self._score_candidate(
            original_text=original_text,
            candidate_text=text,
            target_grade=target_grade,
            mode=mode,
            source_grade=source_grade,
            policy=policy,
        )
        print(
            "[selection] near_target_repair candidate "
            f"raw={scored['raw_score']:.2f} "
            f"display_grade={self._display_grade_number_from_score(scored['raw_score'])} "
            f"target_distance={scored['target_distance']:.2f} "
            f"blocking={self._candidate_blocking_flags(scored)} "
            f"flags={scored.get('validation_flags', [])[:6]}"
        )
        return [{
            'text': text,
            'rule_history': candidate.get('rule_history', []) + ['llm.near_target_protected_repair'],
            'stage_notes': candidate.get('stage_notes', []) + ['llm:near_target_protected_repair'],
        }]

    def _selection_needs_target_contract_rescue(self, selected_candidate, target_grade, source_grade, going_up):
        if not self.llm_client or not selected_candidate:
            return False
        if not self._llm_calls_remaining():
            print(
                "[selection] target_contract_rescue skipped: "
                f"LLM budget exhausted ({self._llm_calls_made}/{self._llm_call_budget})"
            )
            return False
        if self._candidate_display_delta(selected_candidate, target_grade) <= TARGET_LOCK_DISPLAY_BAND_TOLERANCE:
            return False
        hard_gap = abs(float(target_grade) - float(source_grade)) >= 3.0
        defence_downgrade = target_grade <= 7 and not going_up
        return hard_gap or defence_downgrade

    def _target_contract_rescue_candidates(
        self,
        original_text,
        selected_candidate,
        top_candidates,
        target_grade,
        source_grade,
        going_up,
        mode,
        policy,
    ):
        if not self._llm_calls_remaining():
            return []

        target_metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        grade_label = self._target_grade_label(target_grade)
        source_label = self._grade_label_from_score(source_grade)
        word_count = max(1, len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_text or '')))
        ideal_sentence_count = max(2, round(word_count / max(1, target_metrics['target_wps'])))
        paragraph_count = max(1, len(self._extract_paragraph_chunks(original_text)))
        protected_terms = self._protected_term_manifest(original_text, strict_only=True)
        protected_manifest = "\n".join(f"- {term}" for term in protected_terms[:40]) or "- None detected"
        far_candidate = selected_candidate or {}
        closest_candidates = sorted(
            [
                candidate for candidate in (top_candidates or [])
                if candidate.get('text') and candidate is not selected_candidate
            ],
            key=lambda candidate: (
                self._candidate_display_delta(candidate, target_grade),
                candidate.get('target_distance', 999),
                candidate.get('candidate_score', 999),
            ),
        )[:3]
        closest_context = "\n\n".join(
            (
                f"CANDIDATE {index + 1}: raw={candidate.get('raw_score', 0):.2f}, "
                f"display_grade={self._display_grade_number_from_score(candidate.get('raw_score', 99))}, "
                f"flags={candidate.get('validation_flags', [])[:6]}\n"
                f"{candidate.get('text', '')}"
            )
            for index, candidate in enumerate(closest_candidates)
        )
        if not closest_context:
            closest_context = "No alternate candidates were available."

        low_target_failure = ""
        if not going_up and target_grade <= 7:
            low_target_failure = (
                f"- For this {grade_label} target, Grade 8-12 output is a failure. "
                "Do not return high-school or college prose.\n"
            )

        json_shape = json.dumps({
            "variants": [
                {"name": "contract_target", "text": "..."},
                {"name": "contract_safe", "text": "..."},
            ]
        })
        prompt = f"""You are the final target-contract rewrite step for a readability demo.

The previous selected rewrite missed the requested display grade by more than one band. Rewrite broadly enough to hit the target, while preserving protected facts.

TARGET CONTRACT:
- Source estimate: {source_label} ({source_grade:.2f})
- Requested target: {grade_label}
- Required result: exact {grade_label} if possible; otherwise at most one display grade away.
{low_target_failure}- Average words per sentence target: about {target_metrics['target_wps']} ({target_metrics['min_wps']}-{target_metrics['max_wps']} per sentence)
- Average syllables per word target: about {target_metrics['target_syl']:.2f}
- Expected sentence count: about {ideal_sentence_count}
- Paragraph count: keep exactly {paragraph_count}
- Use broad paragraph rewriting. You may split, combine, and replace sentence structures inside each paragraph.
- Do not do a tiny conservative edit if the source is far above the target.
- Preserve names, numbers, acronyms, university/program names, GPA/CGPA values, paragraph count, and idea order.
- Keep paragraph topics in their original paragraphs; do not move paragraph 3 facts into paragraph 2 or create a cross-paragraph summary.
- Do not add a conclusion, moral, whole-text summary, labels, markdown, notes, or commentary.
- Return valid JSON only with this exact shape:
{json_shape}
- If JSON fails, return only the rewritten text with no explanation; the system will still score it.

PROTECTED TERMS TO PRESERVE:
{protected_manifest}

ORIGINAL TEXT:
{original_text}

PREVIOUS FAR-OFF SELECTION:
raw={far_candidate.get('raw_score', 0):.2f}, display_grade={self._display_grade_number_from_score(far_candidate.get('raw_score', 99))}
{far_candidate.get('text', '')}

OTHER NEARER/BLOCKED CONTEXT:
{closest_context}
"""
        try:
            response = self._llm_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.28 if (not going_up and target_grade <= 7) else 0.18,
                max_tokens=4096,
            )
        except Exception as exc:
            if not self._is_timeout_error(exc):
                raise
            self._mark_llm_timeout_fallback()
            print(f"[selection] target_contract_rescue timed out; keeping selected candidate: {exc}")
            return []
        if response is None:
            return []

        raw = response.choices[0].message.content.strip()
        parsed = self._parse_llm_variant_response(raw)
        if not parsed:
            fallback_text = self._normalize_llm_variant_text(raw)
            if fallback_text and len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", fallback_text)) >= 12:
                print("[selection] target_contract_rescue using plain-text fallback response")
                parsed = [{'name': 'contract_plain', 'text': fallback_text}]
            else:
                print("[selection] target_contract_rescue skipped: response did not parse into variants")
                return []
        rescue_candidates = []
        seen = set()
        min_words = max(12, int(word_count * 0.45))
        for item in parsed:
            name = re.sub(r'[^a-z0-9_-]+', '_', str(item.get('name') or 'contract').lower()).strip('_')
            text = self._normalize_llm_variant_text(item.get('text') or '')
            text = self._restore_paragraph_shape(original_text, text)
            key = re.sub(r'\s+', ' ', text).strip().lower()
            if not text or key in seen:
                continue
            if len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text)) < min_words:
                print(
                    "[selection] target_contract_rescue skipped variant: "
                    f"name={name or 'contract'} too_short"
                )
                continue
            seen.add(key)
            score_preview = self._score_candidate(
                original_text=original_text,
                candidate_text=text,
                target_grade=target_grade,
                mode=mode,
                source_grade=source_grade,
                policy=policy,
            )
            print(
                "[selection] target_contract_rescue candidate "
                f"name={name or 'contract'} raw={score_preview['raw_score']:.2f} "
                f"display_grade={self._display_grade_number_from_score(score_preview['raw_score'])} "
                f"target_distance={score_preview['target_distance']:.2f} "
                f"blocking={self._candidate_blocking_flags(score_preview)} "
                f"flags={score_preview.get('validation_flags', [])[:6]}"
            )
            rescue_candidates.append({
                'text': text,
                'rule_history': ['llm.target_contract_rescue', f'variant.{name or "contract"}'],
                'stage_notes': ['llm:target_contract_rescue', f'variant:{name or "contract"}'],
            })

        if not rescue_candidates:
            print("[selection] target_contract_rescue skipped: no usable variants after filtering")
        return rescue_candidates

    def _best_llm_cascade_seed(self, original_text, candidates, target_grade, source_grade, mode, policy):
        scored = []
        for candidate in candidates:
            if not candidate.get('text'):
                continue
            metrics = self._score_candidate(
                original_text=original_text,
                candidate_text=candidate['text'],
                target_grade=target_grade,
                mode=mode,
                source_grade=source_grade,
                policy=policy,
            )
            scored.append({**candidate, **metrics})
        if not scored:
            return None

        safe = [
            candidate for candidate in scored
            if not self._candidate_has_hard_safety_failure(candidate, target_grade)
        ]
        pool = safe or scored
        return min(
            pool,
            key=lambda candidate: (
                candidate['target_distance'],
                self._candidate_invalid_delta(candidate),
                candidate['candidate_score'],
                -candidate['semantic_similarity_score'],
            ),
        )

    def _llm_cascade_needs_more_work(self, candidate, target_grade, source_grade):
        if self._candidate_has_hard_safety_failure(candidate, target_grade):
            return True
        if target_grade >= 13:
            return candidate.get('raw_score', 0.0) < 12.75
        gap = abs(float(target_grade) - float(source_grade))
        tolerance = 0.35 if gap >= 6 else 0.75
        return candidate.get('target_distance', 999) > tolerance

    def _llm_cascade_needs_cleanup(self, candidate, target_grade, source_grade):
        flags = candidate.get('validation_flags', []) or []
        if self._candidate_has_hard_safety_failure(candidate, target_grade):
            return True
        if candidate.get('invalid_sentence_count', 0):
            return True
        if any(
            flag in {'possible_neologism', 'llm_meta_artifact'} or
            flag.startswith('word_artifact:') or
            flag.startswith('awkward_phrase:')
            for flag in flags
        ):
            return True
        gap = abs(float(target_grade) - float(source_grade))
        if target_grade >= 13:
            return candidate.get('raw_score', 0.0) < 12.9
        return gap >= 6 and candidate.get('target_distance', 999) > 0.5

    def _llm_target_correction(
        self,
        original_text,
        candidate_text,
        metrics,
        target_grade,
        source_grade,
        going_up,
        pass_label,
    ):
        target_metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        grade_label = self._target_grade_label(target_grade)
        source_label = self._grade_label_from_score(source_grade)
        direction_label = 'raise' if going_up else 'lower'
        current_raw = float(metrics.get('raw_score', 0) or 0)
        lower, upper = self._get_target_band(target_grade)
        if current_raw < lower:
            correction_direction = (
                "The candidate is TOO EASY for the target. Raise it only enough to enter the target band."
            )
        elif current_raw >= upper:
            correction_direction = (
                "The candidate is TOO HARD for the target. Lower it only enough to enter the target band."
            )
        else:
            correction_direction = "The candidate is already near the target. Make only small safety edits."
        low_grade_undershoot_block = ''
        if not going_up and target_grade <= 7 and current_raw < lower:
            low_grade_undershoot_block = f"""
LOW/MIDDLE-GRADE UNDERSHOOT REPAIR:
- The current text is below {grade_label}. Do NOT make it academic.
- Raise the score mainly by combining very short sentences into clear {target_metrics['min_wps']}-{target_metrics['max_wps']} word sentences.
- Keep simple common words. Do not introduce Grade 8-12 vocabulary, semicolons, or formal essay phrasing.
- A result above Grade {min(12, target_grade + 1)} is a failure for this correction.
"""
        low_grade_block = '' if going_up else self._low_grade_downgrade_instructions(
            target_grade,
            target_metrics=target_metrics,
            source_grade=source_grade,
        )
        word_count = max(1, len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_text or '')))
        ideal_sentence_count = max(2, round(word_count / max(1, target_metrics['target_wps'])))
        paragraph_count = max(1, len(self._extract_paragraph_chunks(original_text)))
        low_target_failure = (
            "- If simplifying for Grade 3-7, a Grade 8-12 result is a failure.\n"
            if not going_up and target_grade <= 7 else
            ""
        )
        prompt = f"""Revise the candidate so it gets much closer to the requested readability level.

Target: {grade_label}
Source estimate: {source_label} ({source_grade:.2f})
Current candidate raw score: {metrics.get('raw_score', 0):.2f}
Current target distance: {metrics.get('target_distance', 999):.2f}
Current words per sentence: {metrics.get('avg_words_per_sentence', 0):.2f}
Current syllables per word: {metrics.get('avg_syllables_per_word', 0):.2f}

Metric target:
- Average words per sentence: about {target_metrics['target_wps']} ({target_metrics['min_wps']}-{target_metrics['max_wps']} per sentence)
- Average syllables per word: about {target_metrics['target_syl']:.2f}
- Expected sentence count: about {ideal_sentence_count}
- Paragraph count: keep exactly {paragraph_count}

Instruction:
- {direction_label.capitalize()} readability enough to approach {grade_label}; do not make a tiny surface edit.
- {correction_direction}
{low_target_failure}- If simplifying, broad paragraph rewriting is allowed when needed to hit the target.
- Preserve every fact, name, number, acronym, cause/effect relation, paragraph count, and paragraph scope.
- Keep paragraph mapping strict: paragraph 1 rewrites only paragraph 1, paragraph 2 rewrites only paragraph 2, and so on.
- Do not add a conclusion, takeaway, moral, reflection, or summary.
- Do not use fake words or awkward invented comparatives.
- Return only the revised text, with no labels or commentary.
{low_grade_block}
{low_grade_undershoot_block}

ORIGINAL FACT REFERENCE:
{original_text}

CURRENT CANDIDATE:
{candidate_text}

REVISED TEXT:"""
        response = self._llm_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.15 if going_up else (0.22 if target_grade <= 7 else 0.1),
            max_tokens=4000,
        )
        if response is None:
            return None
        text = self._normalize_llm_variant_text(response.choices[0].message.content.strip())
        print(
            f"[fireworks] cascade/{pass_label}: "
            f"raw={self._measure_text_metrics(text)[0]:.2f} target={target_grade}"
        )
        return text or None

    def _llm_safety_cleanup(
        self,
        original_text,
        candidate_text,
        metrics,
        target_grade,
        source_grade,
        going_up,
    ):
        grade_label = self._target_grade_label(target_grade)
        flags = ", ".join(metrics.get('validation_flags', [])[:8]) or "none"
        target_metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        low_grade_block = '' if going_up else self._low_grade_downgrade_instructions(
            target_grade,
            target_metrics=target_metrics,
            source_grade=source_grade,
        )
        target_gap_line = (
            "- If the current rewrite is still too hard, simplify it aggressively while keeping facts.\n"
            if not going_up else
            ""
        )
        word_count = max(1, len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_text or '')))
        ideal_sentence_count = max(2, round(word_count / max(1, target_metrics['target_wps'])))
        paragraph_count = max(1, len(self._extract_paragraph_chunks(original_text)))
        low_target_failure = (
            "- For Grade 3-7 simplification targets, Grade 8-12 output is a failure.\n"
            if not going_up and target_grade <= 7 else
            ""
        )
        prompt = f"""Repair this rewrite while keeping it close to {grade_label}.

Current raw score: {metrics.get('raw_score', 0):.2f}
Current validation flags: {flags}

Fix only real quality problems:
- remove fake words, malformed inflections, and awkward phrases
- fix grammar and sentence fragments
{target_gap_line}- keep sentence length and word difficulty close to {grade_label}
- aim for about {target_metrics['target_wps']} words per sentence and {target_metrics['target_syl']:.2f} syllables per word
- expected sentence count is about {ideal_sentence_count}; keep exactly {paragraph_count} paragraphs
{low_target_failure}- use broad paragraph rewriting if the current text is far too hard for the target
- remove notes, labels, or commentary
- preserve every fact, name, number, acronym, paragraph count, and idea order
- keep each paragraph about the same source paragraph; do not move topics/facts across paragraph boundaries
- keep the result as close as safely possible to {grade_label}
{low_grade_block}

ORIGINAL FACT REFERENCE:
{original_text}

REWRITE TO REPAIR:
{candidate_text}

REPAIRED TEXT:"""
        response = self._llm_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.14 if (not going_up and target_grade <= 7) else 0.05,
            max_tokens=4000,
        )
        if response is None:
            return None
        text = self._normalize_llm_variant_text(response.choices[0].message.content.strip())
        print(
            f"[fireworks] cascade/safety_cleanup: "
            f"raw={self._measure_text_metrics(text)[0]:.2f} target={target_grade}"
        )
        return text or None

    def _llm_multi_variant_rewrite(
        self,
        original_text,
        seed_text,
        target_grade,
        source_grade,
        going_up,
        policy,
        seed_label,
    ):
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        grade_label = 'College' if target_grade >= 13 else f'Grade {target_grade}'
        source_label = self._grade_label_from_score(source_grade)
        direction_label = 'upgrade' if going_up else 'simplify'
        low_grade_block = '' if going_up else self._low_grade_downgrade_instructions(
            target_grade,
            target_metrics=metrics,
            source_grade=source_grade,
        )
        word_count = max(1, len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_text or '')))
        variant_names = ['conservative', 'targeted', 'aggressive'] if word_count <= 700 else ['targeted', 'conservative']
        ideal_sentence_count = max(2, round(word_count / max(1, metrics['target_wps'])))
        paragraph_count = max(1, len(self._extract_paragraph_chunks(original_text)))
        low_target_failure = (
            "- For Grade 3-7 simplification targets, Grade 8-12 output is a failure.\n"
            if not going_up and target_grade <= 7 else
            ""
        )
        seed_block = ""
        if seed_text and seed_text != original_text:
            seed_block = f"""

RULE-SEED CANDIDATE:
{seed_text}

You may borrow useful wording from the rule-seed candidate, but the original text is the fact authority."""

        variant_lines = "\n".join(
            f"- {name}: {self._llm_variant_style_instruction(name, going_up)}"
            for name in variant_names
        )
        json_shape = json.dumps({
            "variants": [
                {"name": name, "text": "..."}
                for name in variant_names
            ]
        })
        prompt = f"""Rewrite the text for the requested readability target and return JSON only.

TASK:
- Direction: {direction_label}
- Source estimate: {source_label} ({source_grade:.2f})
- Target: {grade_label}
- Average words per sentence target: {metrics['target_wps']} ({metrics['min_wps']}-{metrics['max_wps']} per sentence)
- Average syllables per word target: {metrics['target_syl']:.2f}
- Approximate sentence count: {ideal_sentence_count}
- Paragraph count: keep exactly {paragraph_count}

VARIANTS TO RETURN:
{variant_lines}

HARD RULES:
1. Preserve every original fact, name, number, acronym, cause/effect relation, and paragraph scope.
2. Do not add a conclusion, takeaway, moral, reflection, or whole-text summary.
3. Do not include labels, headings, markdown, notes, rationale, or commentary inside any variant text.
4. If the exact target is not safely reachable, return the closest safe near-hit rather than inventing facts.
5. Keep the same paragraph count and the same order of main ideas.
6. Paragraph mapping is strict: variant paragraph 1 rewrites source paragraph 1 only, variant paragraph 2 rewrites source paragraph 2 only, and so on.
7. Use broad paragraph rewriting when the source is far from the target; minimal edits are not enough for hard jumps.
{low_target_failure}8. Return valid JSON only, with this exact shape:
{json_shape}
{low_grade_block}

ORIGINAL TEXT:
{original_text}{seed_block}
"""

        response = self._llm_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2 if going_up else 0.1,
            max_tokens=4000,
        )
        if response is None:
            return []

        raw = response.choices[0].message.content.strip()
        parsed = self._parse_llm_variant_response(raw)
        variants = []
        seen = set()
        min_words = max(6, int(word_count * 0.35))
        for item in parsed:
            name = re.sub(r'[^a-z0-9_-]+', '_', str(item.get('name') or 'targeted').lower()).strip('_')
            text = self._normalize_llm_variant_text(item.get('text') or '')
            normalized_key = re.sub(r'\s+', ' ', text).strip().lower()
            if not text or normalized_key in seen:
                continue
            if len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text)) < min_words:
                continue
            seen.add(normalized_key)
            variants.append({'name': name or 'targeted', 'text': text})
        return variants

    @staticmethod
    def _llm_variant_style_instruction(name, going_up):
        if name == 'conservative':
            return (
                "minimal local edits, strongest meaning preservation, accepts a near-hit"
                if going_up else
                "minimal local edits, simple wording, strongest meaning preservation"
            )
        if name == 'aggressive':
            return (
                "stronger academic wording and sentence combining while staying factual"
                if going_up else
                "stronger simplification with sentence splitting while preserving every fact"
            )
        return "best attempt to hit the target band naturally and safely"

    def _parse_llm_variant_response(self, raw):
        if not raw:
            return []

        cleaned = raw.strip()
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        candidates = [cleaned]
        first_brace = cleaned.find('{')
        last_brace = cleaned.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            candidates.append(cleaned[first_brace:last_brace + 1])

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                variants = payload.get('variants') or payload.get('rewrites') or payload.get('candidates')
                if isinstance(variants, list):
                    return [
                        item for item in variants
                        if isinstance(item, dict) and item.get('text')
                    ]
                text_items = [
                    {'name': key, 'text': value}
                    for key, value in payload.items()
                    if isinstance(value, str) and key.lower() in {
                        'conservative',
                        'targeted',
                        'target',
                        'balanced',
                        'aggressive',
                        'contract_target',
                        'contract_safe',
                        'contract_plain',
                    }
                ]
                if text_items:
                    return text_items
            elif isinstance(payload, list):
                return [
                    item for item in payload
                    if isinstance(item, dict) and item.get('text')
                ]

        label_pattern = re.compile(
            r'(?:^|\n)\s*(?:#+\s*)?'
            r'(conservative|targeted|target|balanced|aggressive|contract_target|contract_safe|contract_plain)'
            r'\s*:?\s*\n'
            r'(.+?)(?=\n\s*(?:#+\s*)?'
            r'(?:conservative|targeted|target|balanced|aggressive|contract_target|contract_safe|contract_plain)'
            r'\s*:?\s*\n|\Z)',
            flags=re.IGNORECASE | re.DOTALL,
        )
        return [
            {'name': match.group(1).lower(), 'text': match.group(2).strip()}
            for match in label_pattern.finditer(cleaned)
        ]

    def _normalize_llm_variant_text(self, text):
        if not text:
            return ''
        cleaned = str(text).strip()
        cleaned = re.sub(r'^```(?:text)?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        cleaned = cleaned.strip().strip('"').strip("'").strip()
        cleaned = self._strip_llm_meta_commentary(cleaned)
        if cleaned.startswith('{') or '"variants"' in cleaned[:120].lower():
            return ''
        return cleaned

    def _rule_adjust_llm_candidate_to_target(self, candidate_text, target_grade, going_up, max_rounds=2):
        adjusted = self._strip_llm_meta_commentary(candidate_text or '').strip()
        if not adjusted:
            return ''

        lower, upper = self._get_target_band(target_grade)
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        for _ in range(max_rounds):
            grade, _, wps = self._measure_text_metrics(adjusted)
            in_band = lower <= grade < upper
            if in_band:
                break

            before = adjusted
            if going_up and grade < lower:
                adjusted, _ = self._complexify_text(adjusted, target_grade)
                if wps < metrics['min_wps']:
                    adjusted, _ = self._combine_short_sentences(adjusted, target_grade)
            elif (not going_up) and grade >= upper:
                adjusted, _ = self._replace_difficult_words(adjusted, target_grade)
                if wps > metrics['max_wps']:
                    adjusted, _ = self._split_long_sentences(adjusted, target_grade)
            else:
                break

            if adjusted == before:
                break

        return self._strip_llm_meta_commentary(adjusted).strip()
