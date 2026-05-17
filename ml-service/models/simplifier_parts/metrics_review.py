from .base import *


class MetricsReviewMixin:
    def _grade_label_from_score(self, score):
        if score < 4:
            return 'Grade 3'
        if score < 5:
            return 'Grade 4'
        if score < 6:
            return 'Grade 5'
        if score < 7:
            return 'Grade 6'
        if score < 8:
            return 'Grade 7'
        if score < 9:
            return 'Grade 8'
        if score < 10:
            return 'Grade 9'
        if score < 11:
            return 'Grade 10'
        if score < 12:
            return 'Grade 11'
        if score < 13:
            return 'Grade 12'
        return 'College'

    def _grade_complexity_from_label(self, label):
        if label == 'College':
            return 'Expert'
        number = int(label.replace('Grade ', ''))
        if number <= 6:
            return 'Beginner'
        if number <= 9:
            return 'Intermediate'
        if number <= 12:
            return 'Advanced'
        return 'Expert'

    def _measure_preview_metrics(self, text):
        raw_score, avg_syl, avg_wps = self._measure_text_metrics(text)
        predicted_grade_level = self._grade_label_from_score(raw_score)
        predicted_complexity = self._grade_complexity_from_label(predicted_grade_level)

        if self.readability_model is not None:
            try:
                prediction = self.readability_model.predict(text)['predictions']
                raw_score = float(prediction.get('raw_score', raw_score))
                predicted_grade_level = prediction.get('predicted_grade_level', predicted_grade_level)
                predicted_complexity = prediction.get('predicted_complexity', predicted_complexity)
            except Exception as exc:
                print(f"Preview metrics fallback in simplifier: {exc}")

        return {
            'raw_score': round(raw_score, 2),
            'predicted_grade_level': predicted_grade_level,
            'predicted_complexity': predicted_complexity,
            'avg_syllables_per_word': round(avg_syl, 2),
            'avg_words_per_sentence': round(avg_wps, 2),
            'invalid_sentence_count': len(self._collect_invalid_sentences(text)),
            'semantic_similarity_score': round(self._semantic_similarity_score(text, text), 2),
            'target_distance': 0.0,
        }

    def _greedy_select_changes_for_target(self, original_text, changes, target_grade, going_up):
        """Auto-mode optimization: incrementally apply changes, keep only the subset that hits the target."""
        if not changes:
            metrics = self._measure_preview_metrics(original_text)
            metrics['target_distance'] = self._distance_to_target_band(metrics['raw_score'], target_grade)
            return changes, original_text, metrics

        units = self._build_change_units(changes, going_up)
        units.sort(key=lambda u: u['sort_key'], reverse=True)

        baseline_grade, _, _ = self._measure_text_metrics(original_text)
        baseline_distance = self._distance_to_target_band(baseline_grade, target_grade)
        measurements = 1

        best_ids = set()
        best_text = original_text
        best_distance = baseline_distance
        applied_ids = set()

        for unit in units:
            if measurements >= AUTO_GREEDY_MAX_MEASUREMENTS:
                break

            candidate_ids = applied_ids | set(unit['change_ids'])
            rebuilt = apply_changes_by_span(original_text, changes, list(candidate_ids))
            grade, _, _ = self._measure_text_metrics(rebuilt)
            measurements += 1
            distance = self._distance_to_target_band(grade, target_grade)

            if distance < best_distance:
                best_ids = set(candidate_ids)
                best_text = rebuilt
                best_distance = distance
                applied_ids = set(candidate_ids)
                if distance == 0:
                    break
            elif distance <= best_distance + AUTO_GREEDY_TOLERANCE:
                applied_ids = set(candidate_ids)

        selected_changes = [c for c in changes if c['id'] in best_ids]
        final_metrics = self._measure_preview_metrics(best_text)
        final_metrics['semantic_similarity_score'] = round(
            self._semantic_similarity_score(original_text, best_text), 2
        )
        final_metrics['target_distance'] = round(best_distance, 2)
        return selected_changes, best_text, final_metrics

    def _build_change_units(self, changes, going_up):
        """Group changes into atomic units respecting dependency groups."""
        groups = {}
        ungrouped = []

        for change in changes:
            dep_id = change.get('dependency_group_id')
            if dep_id:
                groups.setdefault(dep_id, []).append(change)
            else:
                ungrouped.append(change)

        units = []
        for change in ungrouped:
            impact = self._estimate_change_grade_impact(change, going_up)
            units.append({
                'change_ids': [change['id']],
                'sort_key': impact,
            })

        for dep_id, group_changes in groups.items():
            total_impact = sum(self._estimate_change_grade_impact(c, going_up) for c in group_changes)
            units.append({
                'change_ids': [c['id'] for c in group_changes],
                'sort_key': total_impact,
            })

        return units

    def _estimate_change_grade_impact(self, change, going_up):
        """Heuristic: estimate how much this patch moves the grade toward the target."""
        original_text = change.get('original_text', change.get('original', ''))
        replacement_text = change.get('replacement_text', change.get('simplified', ''))

        orig_words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", original_text)
        repl_words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", replacement_text)

        if not orig_words and not repl_words:
            return 0.0

        orig_syls = sum(self.text_processor.count_syllables(w.lower()) for w in orig_words) if orig_words else 0
        repl_syls = sum(self.text_processor.count_syllables(w.lower()) for w in repl_words) if repl_words else 0
        syl_impact = (repl_syls - orig_syls) * 0.5

        orig_sents = len(re.findall(r'[.!?]+', original_text)) if original_text.strip() else 0
        repl_sents = len(re.findall(r'[.!?]+', replacement_text)) if replacement_text.strip() else 0
        sent_delta = repl_sents - orig_sents
        wps_impact = -sent_delta * 2.0 + (len(repl_words) - len(orig_words)) * 0.1

        raw_impact = syl_impact + wps_impact
        return raw_impact if going_up else -raw_impact

    def _confidence_label(self, candidate_score, invalid_sentence_count, semantic_similarity_score, target_distance):
        if invalid_sentence_count:
            return 'Low'
        if target_distance <= 0.5 and semantic_similarity_score >= 0.9 and candidate_score <= 2.5:
            return 'High'
        if target_distance <= 1.0 and semantic_similarity_score >= 0.82 and candidate_score <= 5.0:
            return 'Medium'
        return 'Low'

    def _should_force_selected_candidate_delivery(self, selection, final_metrics):
        summary = selection.get('selection_summary', {}) if selection else {}
        selected_distance = float(summary.get('target_distance', 999) or 999)
        delivered_distance = float(final_metrics.get('target_distance', 999) or 999)
        selected_delta = int(summary.get('display_grade_delta', 999) or 999)
        delivered_delta = self._display_grade_delta_from_score(final_metrics.get('raw_score', 99), summary.get('target_grade', 13))
        if selected_delta <= TARGET_LOCK_DISPLAY_BAND_TOLERANCE and delivered_delta > TARGET_LOCK_DISPLAY_BAND_TOLERANCE:
            selected_raw = summary.get('selected_raw_score')
            print(
                "[selection] forcing exact candidate delivery: "
                f"selected_raw={selected_raw} selected_delta={selected_delta} "
                f"delivered_raw={final_metrics.get('raw_score')} delivered_delta={delivered_delta}"
            )
            return True
        if selected_distance > 1.0:
            return False
        if delivered_distance <= selected_distance + 1.5:
            return False
        selected_raw = summary.get('selected_raw_score')
        print(
            "[selection] forcing exact candidate delivery: "
            f"selected_raw={selected_raw} selected_distance={selected_distance:.2f} "
            f"delivered_raw={final_metrics.get('raw_score')} delivered_distance={delivered_distance:.2f}"
        )
        return True

    def _should_use_local_repair(self, target_grade, final_metrics, validation):
        if not validation.get('issues'):
            return False
        return final_metrics['target_distance'] <= LOCAL_REPAIR_GRADE_GAP

    def _repair_is_safe(self, original_text, current_text, repaired_text, target_grade):
        if not repaired_text or repaired_text == current_text:
            return False

        current_grade, _, _ = self._measure_text_metrics(current_text)
        repaired_grade, _, _ = self._measure_text_metrics(repaired_text)
        current_distance = self._distance_to_target_band(current_grade, target_grade)
        repaired_distance = self._distance_to_target_band(repaired_grade, target_grade)
        if repaired_distance > current_distance + 0.25:
            return False

        repaired_similarity = self._semantic_similarity_score(original_text, repaired_text)
        current_similarity = self._semantic_similarity_score(original_text, current_text)
        if repaired_similarity + 0.03 < current_similarity:
            return False

        return True

    @staticmethod
    def _dedupe_preserve_order(values):
        seen = set()
        ordered = []
        for value in values:
            normalized = (value or '').strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def _collect_final_review_issues(self, validation, critic_review):
        issues = list(validation.get('issues', [])) if validation else []
        for review in (critic_review or {}).get('reviews', []):
            if review.get('meaning_drift'):
                issues.append("Preserve the original meaning more accurately.")
            if review.get('awkward_phrase'):
                issues.append("Fix awkward or unnatural wording.")
            if review.get('grade_too_low'):
                issues.append("Keep the result closer to the requested grade instead of oversimplifying.")
            if review.get('grade_too_high'):
                issues.append("Keep the result closer to the requested grade instead of staying too difficult.")
            for note in review.get('notes', []):
                if isinstance(note, str):
                    issues.append(note)
        return self._dedupe_preserve_order(issues)

    def _collect_preview_diff_ranges(self, original_text, revised_text):
        import difflib

        if original_text == revised_text:
            return []

        original_chunks = self._extract_diff_chunks(original_text)
        revised_chunks = self._extract_diff_chunks(revised_text)
        if not original_chunks or not revised_chunks:
            return [(0, len(revised_text))]

        matcher = difflib.SequenceMatcher(
            None,
            [chunk['normalized'] for chunk in original_chunks],
            [chunk['normalized'] for chunk in revised_chunks],
            autojunk=False,
        )

        ranges = []
        revised_length = len(revised_text)
        for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                continue

            if j1 < len(revised_chunks):
                start = revised_chunks[j1]['start']
            else:
                start = revised_length

            if j2 > j1 and (j2 - 1) < len(revised_chunks):
                end = revised_chunks[j2 - 1]['end']
            else:
                end = start

            if end < start:
                end = start
            ranges.append((start, end))

        return ranges

    @staticmethod
    def _ranges_overlap(left_start, left_end, right_start, right_end):
        return left_start < right_end and right_start < left_end

    @staticmethod
    def _overlap_length(left_start, left_end, right_start, right_end):
        return max(0, min(left_end, right_end) - max(left_start, right_start))

    def _build_final_review_reason(self, change, target_grade):
        change_type = change.get('type')
        scope = change.get('review_scope', 'sentence')
        scope_label = 'wording' if scope == 'word' else scope
        target_label = self._target_grade_label(target_grade)

        if change_type in {'word_replacement', 'word_upgrade'}:
            return (
                f"Adjusted this {scope_label} during the final meaning check so it stays accurate "
                f"and reads naturally at {target_label}."
            )
        if change_type == 'sentence_split':
            return (
                f"Adjusted this sentence break during the final meaning check so the shorter version "
                f"still says the same thing at {target_label}."
            )
        if change_type == 'sentence_combine':
            return (
                f"Adjusted this sentence combination during the final meaning check so the denser version "
                f"still says the same thing at {target_label}."
            )
        return (
            f"Adjusted this {scope_label} during the final meaning check to keep the wording clear, "
            f"natural, and faithful to the original text at {target_label}."
        )

    def _should_mark_final_reviewed(self, change, revised_ranges):
        preview_start = change.get('preview_start', change.get('start', 0))
        preview_end = change.get('preview_end', preview_start)
        patch_length = max(1, preview_end - preview_start)
        total_overlap = sum(
            self._overlap_length(preview_start, preview_end, range_start, range_end)
            for range_start, range_end in revised_ranges
        )
        overlap_ratio = total_overlap / patch_length

        scope = change.get('review_scope', 'sentence')
        threshold = 0.55 if scope == 'paragraph' else 0.35 if scope == 'sentence' else 0.2
        return total_overlap > 0 and overlap_ratio >= threshold

    def _annotate_final_reviewed_changes(self, changes, revised_ranges, target_grade, issues):
        if not changes:
            return []

        issue_summary = " | ".join(self._dedupe_preserve_order(issues)[:3])
        fallback_change_id = None
        if revised_ranges:
            best_overlap = 0
            for change in changes:
                preview_start = change.get('preview_start', change.get('start', 0))
                preview_end = change.get('preview_end', preview_start)
                total_overlap = sum(
                    self._overlap_length(preview_start, preview_end, range_start, range_end)
                    for range_start, range_end in revised_ranges
                )
                if total_overlap > best_overlap:
                    best_overlap = total_overlap
                    fallback_change_id = change.get('id')

        annotated = []
        for change in changes:
            updated = dict(change)
            updated['change_origin'] = 'rule'
            updated['final_reviewed'] = False
            updated['final_review_note'] = None

            touched = (
                self._should_mark_final_reviewed(updated, revised_ranges) or
                (fallback_change_id is not None and updated.get('id') == fallback_change_id)
            )

            if touched:
                updated['change_origin'] = 'rule+final_review'
                updated['final_reviewed'] = True
                updated['final_review_note'] = self._build_final_review_reason(updated, target_grade)
                validation_flags = list(updated.get('validation_flags') or [])
                if 'final_review_adjusted' not in validation_flags:
                    validation_flags.append('final_review_adjusted')
                updated['validation_flags'] = validation_flags

                evidence = dict(updated.get('evidence') or {})
                if updated.get('rule_id'):
                    evidence['base_rule_id'] = updated['rule_id']
                if updated.get('reason_code'):
                    evidence['base_reason_code'] = updated['reason_code']
                if updated.get('reason'):
                    evidence['base_reason'] = updated['reason']
                evidence['final_reviewed'] = True
                if issue_summary:
                    evidence['review_focus'] = issue_summary
                updated['evidence'] = evidence

            annotated.append(updated)

        return annotated

    def _apply_llm_repair_pass(
        self,
        original_text,
        current_text,
        target_grade,
        going_up,
        changes,
        validation,
        critic_review,
    ):
        summary = {
            'final_review_applied': True,
            'review_adjusted_change_count': 0,
        }
        if not self.llm_validator.client:
            summary['final_review_applied'] = False
            final_metrics = self._measure_preview_metrics(current_text)
            final_metrics['semantic_similarity_score'] = round(
                self._semantic_similarity_score(original_text, current_text),
                2,
            )
            final_metrics['target_distance'] = round(
                self._distance_to_target_band(final_metrics['raw_score'], target_grade),
                2,
            )
            return current_text, changes, validation, final_metrics, summary

        review_issues = self._collect_final_review_issues(validation, critic_review)
        revised_text = self.llm_validator.polish_text(
            original_text=original_text,
            rewritten_text=current_text,
            target_grade=target_grade,
            issues=review_issues,
            going_up=going_up,
        )

        if self._repair_is_safe(original_text, current_text, revised_text, target_grade):
            revised_ranges = self._collect_preview_diff_ranges(current_text, revised_text)
            current_text, changes, final_metrics = self._finalize_preview_candidate(
                original_text=original_text,
                candidate_text=revised_text,
                target_grade=target_grade,
                going_up=going_up,
                prefer_sentence_level=True,
            )
            changes = self._annotate_final_reviewed_changes(
                changes=changes,
                revised_ranges=revised_ranges,
                target_grade=target_grade,
                issues=review_issues,
            )
            summary['review_adjusted_change_count'] = sum(
                1 for change in changes if change.get('final_reviewed')
            )
        else:
            current_text, changes, final_metrics = self._finalize_preview_candidate(
                original_text=original_text,
                candidate_text=current_text,
                target_grade=target_grade,
                going_up=going_up,
            )

        validation = self.llm_validator.validate_changes(original_text, current_text, changes)
        if validation.get('issues') and self._should_use_local_repair(target_grade, final_metrics, validation):
            repaired_text = self.llm_validator.local_repair(
                original_text=original_text,
                candidate_text=current_text,
                target_grade=target_grade,
                issues=validation.get('issues', []),
            )
            if self._repair_is_safe(original_text, current_text, repaired_text, target_grade):
                repaired_ranges = self._collect_preview_diff_ranges(current_text, repaired_text)
                current_text, changes, final_metrics = self._finalize_preview_candidate(
                    original_text=original_text,
                    candidate_text=repaired_text,
                    target_grade=target_grade,
                    going_up=going_up,
                    prefer_sentence_level=True,
                )
                changes = self._annotate_final_reviewed_changes(
                    changes=changes,
                    revised_ranges=repaired_ranges,
                    target_grade=target_grade,
                    issues=validation.get('issues', []),
                )
                summary['review_adjusted_change_count'] = sum(
                    1 for change in changes if change.get('final_reviewed')
                )
                validation = self.llm_validator.validate_changes(original_text, current_text, changes)

        return current_text, changes, validation, final_metrics, summary

    def _maybe_adopt_critic_candidate(
        self,
        preferred_index,
        selection,
        original_text,
        target_grade,
        current_text,
        changes,
        validation,
        final_metrics,
    ):
        top_candidates = selection.get('top_candidates', [])
        if preferred_index < 0 or preferred_index >= len(top_candidates):
            return current_text, changes, validation, final_metrics

        preferred = top_candidates[preferred_index]
        preferred_text = preferred.get('text')
        if not preferred_text or preferred_text == current_text:
            return current_text, changes, validation, final_metrics
        if not self._repair_is_safe(original_text, current_text, preferred_text, target_grade):
            return current_text, changes, validation, final_metrics

        current_text = preferred_text
        changes = self._diff_changes(original_text, current_text, target_grade, selection['going_up'])
        changes = self._assign_dependency_groups(changes)
        if changes:
            current_text = apply_changes_by_span(
                original_text,
                changes,
                [change['id'] for change in changes]
            )
        final_metrics = self._measure_preview_metrics(current_text)
        final_metrics['semantic_similarity_score'] = round(
            self._semantic_similarity_score(original_text, current_text),
            2,
        )
        final_metrics['target_distance'] = round(
            self._distance_to_target_band(final_metrics['raw_score'], target_grade),
            2,
        )
        validation = self.llm_validator.validate_changes(original_text, current_text, changes)
        return current_text, changes, validation, final_metrics

    def _get_target_band(self, target_grade):
        """
        Convert a target display grade into the raw-score band that produces that label.
        This keeps rewrite control aligned with what users actually see in the UI.
        """
        if target_grade <= 3:
            return float('-inf'), 4.0
        if target_grade >= 13:
            return 13.0, float('inf')
        return float(target_grade), float(target_grade + 1)

    def _get_target_direction(self, estimated_grade, target_grade):
        """
        Return:
          1  -> keep upgrading until the score enters the target display-grade band
          0  -> already in the target display-grade band
         -1  -> downgrade until the score re-enters the band
        """
        lower, upper = self._get_target_band(target_grade)
        if estimated_grade < lower:
            return 1
        if estimated_grade >= upper:
            return -1
        return 0

    def _should_use_full_rewrite_rescue(self, text, target_grade, final_grade):
        """
        Decide when auto mode should escalate from the rule engine to a
        full-text rescue rewrite.
        """
        if not self.llm_client:
            return False

        if self._get_target_direction(final_grade, target_grade) != 0:
            return True

        if abs(final_grade - target_grade) >= REWRITE_RESCUE_GRADE_GAP:
            return True

        return self._needs_llm_help(text, target_grade)

    def _distance_to_target_band(self, estimated_grade, target_grade):
        """Distance from the displayed target-grade band."""
        lower, upper = self._get_target_band(target_grade)
        if estimated_grade < lower:
            return lower - estimated_grade
        if estimated_grade >= upper:
            return estimated_grade - upper
        return 0.0

    def _alignment_score(self, estimated_grade, target_grade):
        """
        Lower is better. Being inside the displayed grade band wins; otherwise,
        prefer the closest grade to that band.
        """
        band_distance = self._distance_to_target_band(estimated_grade, target_grade)
        if band_distance == 0:
            center = target_grade + (0.25 if target_grade < 13 else 0.5)
            return abs(estimated_grade - center) * 0.01
        return band_distance

    def _accept_structural_rewrite(self, original_text, candidate_text, changes):
        """
        Keep structure-changing edits only when they still read as complete,
        standalone sentences after the rule-based pass.
        """
        if not changes:
            return candidate_text, changes

        baseline_invalid_count = len(self._collect_invalid_sentences(original_text))
        candidate_invalid_count = len(self._collect_invalid_sentences(candidate_text))
        local_replacements_are_valid = True
        for change in changes:
            replacement = (
                change.get('replacement_text') or
                change.get('simplified') or
                ''
            ).strip()
            if replacement and not self._text_has_valid_sentence_structure(replacement):
                local_replacements_are_valid = False
                break

        if local_replacements_are_valid and candidate_invalid_count <= baseline_invalid_count:
            return candidate_text, changes

        accepted = []
        best_invalid_count = baseline_invalid_count
        ordered_changes = sorted(
            changes,
            key=lambda change: (
                change.get('start', change.get('position', 0)),
                change.get('end', change.get('start', change.get('position', 0))),
                change.get('id', 0),
            )
        )

        for change in ordered_changes:
            replacement = (
                change.get('replacement_text') or
                change.get('simplified') or
                ''
            ).strip()
            if not replacement:
                continue
            if not self._text_has_valid_sentence_structure(replacement):
                continue

            candidate_changes = accepted + [change]
            candidate_ids = [accepted_change['id'] for accepted_change in candidate_changes]
            filtered_text = apply_changes_by_span(original_text, candidate_changes, candidate_ids)
            filtered_invalid_count = len(self._collect_invalid_sentences(filtered_text))
            if filtered_invalid_count <= best_invalid_count:
                accepted.append(change)
                best_invalid_count = filtered_invalid_count

        if not accepted:
            return original_text, []

        accepted_ids = [change['id'] for change in accepted]
        filtered_text = apply_changes_by_span(original_text, accepted, accepted_ids)
        if len(self._collect_invalid_sentences(filtered_text)) > baseline_invalid_count:
            return original_text, []

        return filtered_text, accepted

    def _measure_text_metrics(self, text):
        """
        Measure actual text metrics and estimate grade.
        Returns: (estimated_grade, avg_syllables_per_word, avg_words_per_sentence)

        Prefer the same readability model used by the rest of the app so
        targeting decisions match the grade shown to users. Fall back to the
        older syllable/words-per-sentence approximation when no model is wired in.
        """
        cache = getattr(self._metrics_tls, 'cache', None)
        if cache is not None:
            cached = cache.get(text)
            if cached is not None:
                return cached

        doc = nlp(text)
        words = [t for t in doc if t.is_alpha]
        sentences = list(doc.sents)

        if not words or not sentences:
            return 8.0, 1.4, 15.0  # safe defaults

        total_syl = sum(self.text_processor.count_syllables(w.text.lower()) for w in words)
        avg_syl = total_syl / len(words)
        avg_wps = len(words) / len(sentences)

        predicted = None
        if self.readability_model is not None:
            try:
                predicted = float(self.readability_model.predict(text)['predictions']['raw_score'])
            except Exception as e:
                print(f"Readability model scoring fallback in simplifier: {e}")

        if predicted is None:
            predicted = -21.16 + 14.33 * avg_syl + 0.6 * avg_wps

        # Do NOT clamp; targeting must match the raw_score the UI renders.
        result = (predicted, avg_syl, avg_wps)
        cache = getattr(self._metrics_tls, 'cache', None)
        if cache is not None:
            cache[text] = result
        return result

    def _estimate_current_grade(self, text):
        """Backward-compat wrapper."""
        grade, _, _ = self._measure_text_metrics(text)
        return grade

    def _is_domain_sensitive_term(self, word_lower, token, explicit_synonym=None):
        if explicit_synonym:
            return False
        if token.pos_ not in ('NOUN', 'PROPN'):
            return False
        if len(word_lower) < 8:
            return False
        if any(word_lower.endswith(suffix) for suffix in DOMAIN_TERM_SUFFIXES):
            return True
        if token.ent_type_:
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Word difficulty assessment (data-driven)
    # ------------------------------------------------------------------ #
