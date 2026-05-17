from .base import *


class LlmFallbackMixin:
    def _llm_full_rewrite(
        self,
        original_text,
        target_grade,
        going_up=False,
        rewrite_style='balanced',
        reference_text=None,
        metric_feedback=None,
        plan_label='pass1',
        include_diff=True,
    ):
        """
        Generate one LLM rewrite candidate.

        The LLM remains the authoring engine here, but the chosen output is
        still diffed back into deterministic patches so the UI can explain
        lexical swaps, sentence splits, and sentence combinations.
        """
        if not self.llm_client:
            return None, []

        try:
            reference_text = reference_text or original_text
            metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
            target_wps = metrics['target_wps']
            min_wps = metrics['min_wps']
            max_wps = metrics['max_wps']
            target_syl = metrics['target_syl']
            grade_label = 'College' if target_grade >= 13 else f'Grade {target_grade}'

            style_rules = {
                'conservative': (
                    "Prefer local edits. Keep the same paragraph order and sentence order whenever possible. "
                    "Use word substitutions, sentence splits, and sentence combinations before broader paraphrasing."
                ),
                'balanced': (
                    "Keep the same paragraph order and overall idea order. Prefer local edits first, "
                    "but you may fully rewrite an individual sentence when needed to hit the target naturally."
                ),
                'aggressive': (
                    "You may rewrite sentences more strongly inside each paragraph to hit the target, "
                    "but keep paragraph order, factual content, and the order of main ideas unchanged."
                ),
                'corrective': (
                    "This is a correction pass on a near-miss. Stay very close to the current wording. "
                    "Change only the words or sentence boundaries needed to fix the target grade, grammar, or awkward phrasing."
                ),
            }
            style_rule = style_rules.get(rewrite_style, style_rules['balanced'])
            style_temperature = {
                'conservative': 0.0,
                'balanced': 0.2,
                'aggressive': 0.35,
                'corrective': 0.1,
            }.get(rewrite_style, 0.2)

            reference_block = ""
            if reference_text != original_text:
                reference_block = f"""

FACT REFERENCE:
{reference_text}

Use the fact reference to preserve who did what, what causes what, and every original fact. Do not copy its harder or easier wording blindly; only use it to keep meaning exact."""

            metric_hint = ""
            if metric_feedback:
                metric_hint = f"""

CURRENT CANDIDATE METRICS:
- Estimated grade: {metric_feedback.get('raw_score', 0):.2f}
- Target distance: {metric_feedback.get('target_distance', 0):.2f}
- Invalid sentence count: {metric_feedback.get('invalid_sentence_count', 0)}
- Semantic similarity: {metric_feedback.get('semantic_similarity_score', 0):.2f}

Use these numbers to correct the current wording instead of rewriting the full passage from scratch."""

            source_grade_estimate = self._measure_text_metrics(original_text)[0]
            wholedoc_grade_delta = float(target_grade) - source_grade_estimate

            def _build_upgrade_prompt(text_to_rewrite):
                large_jump = wholedoc_grade_delta > 5.0
                if target_grade <= 6:
                    vocab_level = "slightly more formal words with some two-syllable terms"
                    clause_rule = "Write clear, simple sentences. Use 'and', 'but', 'so' to combine ideas. AVOID complex clause nesting."
                elif target_grade <= 8:
                    vocab_level = "clear middle-school vocabulary with natural two-syllable words; avoid stiff words like utilize"
                    clause_rule = "Use AT MOST one subordinate clause per sentence (e.g. one 'which', 'because', or 'while'). Keep sentences clear and direct."
                elif target_grade <= 10:
                    vocab_level = "plain high-school vocabulary with common two-syllable words; avoid college, technical, or rare academic terms"
                    clause_rule = "Use at most one subordinate clause per sentence. Keep sentences direct."
                elif target_grade <= 12:
                    if large_jump:
                        vocab_level = "sophisticated academic vocabulary with multi-syllable terms and formal register"
                        clause_rule = "Use 2–3 clauses per sentence. Employ subordinate clauses, relative clauses, and complex syntax."
                    else:
                        vocab_level = "sophisticated high-school academic vocabulary with argument structure — NOT college/graduate prose"
                        clause_rule = "Use 2–3 clauses per sentence maximum. Do NOT write at College level — keep it high-school."
                else:
                    vocab_level = "professional academic prose with domain-specific terminology"
                    clause_rule = "Use full academic sentence complexity with multiple clauses and transitions."

                if target_grade >= 13:
                    ceiling_rule = "7. TARGET FLOOR: You MUST reach College level (raw grade 13+). Use academic vocabulary and complex sentences to ensure you hit the target."
                elif target_grade >= 11 and large_jump:
                    ceiling_rule = f"7. TARGET: Hit {grade_label} level. Academic vocabulary IS appropriate for this grade. Focus on reaching the syllable and sentence length targets."
                else:
                    ceiling_rule = f"7. TARGET CEILING: Do NOT write above {grade_label}. Do not use college-level diction, technical jargon, or rare Latinate words to raise the score."

                return f"""Rewrite the following text at exactly {grade_label} writing level.

THIS IS AN UPGRADE — make it MORE COMPLEX than the original.

STRICT METRIC TARGETS (the readability grade depends on hitting these precisely):
  - Average words per sentence: {target_wps}  (HARD LIMIT: each sentence must be {min_wps}–{max_wps} words)
  - Average syllables per word: {target_syl:.2f}
  - Sentence count: approximately {ideal_sentence_count} sentences

RULES:
1. REWRITE SHAPE: {style_rule}
2. SENTENCE LENGTH: Write approximately {ideal_sentence_count} sentences. Every sentence must be {min_wps}–{max_wps} words. NO sentence may exceed {max_wps} words. Combine short sentences using conjunctions and connectors.
3. VOCABULARY: Use {vocab_level}. Replace simple words only when the new word fits the local context:
   "show" → "explain" or "show clearly"  |  "need" → "require" only in formal factual contexts
   "big" → "major"  |  "start" → "begin"  |  "help" → "support"
   "get" → "obtain"  |  "find" → "discover"  |  "make" → "create" or "produce"
4. CONTEXTUAL FIT: Every word replacement MUST make sense in the sentence's context. Do NOT use a word just because it is more complex — it must fit the noun/verb it modifies. "big park" → "large park" is OK. "big park" → "substantial park" is WRONG because parks are not "substantial". Always ask: would a native speaker naturally use this word here?
5. CLAUSE COMPLEXITY: {clause_rule}
6. SYLLABLE COUNT: Aim for avg {target_syl:.2f} syllables/word.{'' if large_jump else ' Use 2-syllable words (per-son, com-plete, for-mal, dai-ly, of-ten).'}
{ceiling_rule}
8. PARAGRAPH SHAPE: Keep the SAME number of paragraphs as the original. Each rewritten paragraph must correspond to the same original paragraph and stay within that paragraph's scope.
9. ENDING DISCIPLINE: Do NOT add a conclusion, takeaway, moral, reflection, or whole-text summary. Do NOT turn the final paragraph into an academic wrap-up. If the original final paragraph is short, keep it proportionally short unless grammar forces a small adjustment.
10. PRESERVE MEANING: Keep all facts. Do not omit any information.
11. NAMES & ACRONYMS: Keep all proper nouns and abbreviations exactly as written.
12. NO REPETITION: Each idea appears once only.
13. OUTPUT: Write ONLY the rewritten text. No labels, headings, or commentary.{metric_hint}{reference_block}

TEXT TO REWRITE:
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
                low_grade_block = self._low_grade_downgrade_instructions(
                    target_grade,
                    target_metrics=metrics,
                    source_grade=self._measure_text_metrics(reference_text)[0] if reference_text else None,
                )
                domain_block = self._domain_term_paraphrase_instructions(
                    text_to_rewrite, target_grade
                )

                return f"""Rewrite the following text at exactly {grade_label} reading level.

THIS IS A SIMPLIFICATION — make it EASIER than the original.

STRICT METRIC TARGETS (the ML model grade is determined ONLY by these two numbers):
  - Average words per sentence: {target_wps}  (HARD LIMIT: each sentence must be {min_wps}–{max_wps} words)
  - Average syllables per word: {target_syl:.2f}  (use short, common words)
  - Sentence count: approximately {ideal_sentence_count} sentences

RULES:
1. REWRITE SHAPE: {style_rule}
2. SENTENCE LENGTH: Write approximately {ideal_sentence_count} sentences. Every sentence must be {min_wps}–{max_wps} words. Split any longer sentence into two shorter ones. Use a period, not a semicolon.
3. VOCABULARY: Use {vocab_level}. Replace difficult words with simpler ones that mean THE SAME THING:
   "utilize" → "use"  |  "demonstrate" → "show"  |  "require" → "need"
   "obtain" → "get"  |  "substantial" → "large"  |  "facilitate" → "help"
   NEVER change word meaning: "zones" → "areas" is OK, "zones" → "suns" is WRONG.
4. CONTEXTUAL FIT: Every word replacement MUST make sense in the sentence's context. A simpler word must fit naturally where the original word was used. Would a native speaker say this? If not, pick a different simpler word.
5. SYLLABLE COUNT: Aim for avg {target_syl:.2f} syllables/word. Prefer short words.
6. PARAGRAPH SHAPE: Keep the SAME number of paragraphs as the original. Each rewritten paragraph must correspond to the same original paragraph and stay within that paragraph's scope.
7. ENDING DISCIPLINE: Do NOT add a conclusion, takeaway, moral, reflection, or whole-text summary. Do NOT turn the final paragraph into an academic wrap-up. If the original final paragraph is short, keep it proportionally short unless grammar forces a small adjustment.
8. PRESERVE MEANING: Keep ALL facts. Do not skip any paragraphs.
9. NAMES & ACRONYMS: Keep all proper nouns and abbreviations exactly as written.
10. NO REPETITION: Each idea appears once only. Do NOT generate new content beyond what exists in the original.
11. OUTPUT: Write ONLY the simplified text. No labels or commentary.{metric_hint}{reference_block}
{low_grade_block}{domain_block}

TEXT TO REWRITE:
{text_to_rewrite}

SIMPLIFIED TEXT ({grade_label}):"""

            def _strip_preamble(text):
                return self._strip_llm_meta_commentary(text)

            # ---- Estimate ideal sentence count from the original text ----
            orig_doc = nlp(original_text)
            orig_word_count = len([t for t in orig_doc if t.is_alpha])
            ideal_sentence_count = max(2, round(orig_word_count / target_wps))

            def _do_llm_pass(text_to_rewrite, pass_label="pass1"):
                prompt = _build_upgrade_prompt(text_to_rewrite) if going_up else _build_downgrade_prompt(text_to_rewrite)
                resp = self._llm_chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=style_temperature,
                    max_tokens=4000,
                )
                if resp is None:
                    return None, 0.0, 0.0, 0.0
                text_out = _strip_preamble(resp.choices[0].message.content.strip())
                g, s, w = self._measure_text_metrics(text_out)
                print(f"[fireworks] {plan_label}/{pass_label}: actual grade={g:.1f}, syl={s:.2f}, wps={w:.1f} "
                      f"(targets: grade={target_grade}, syl={target_syl:.2f}, wps={target_wps}, range {min_wps}-{max_wps})")
                return text_out, g, s, w

            # ---- First pass ----
            rewritten, actual_grade, actual_syl, actual_wps = _do_llm_pass(original_text, "pass1")
            if rewritten is None:
                return None, []

            def _build_correction_prompt(text_to_fix, cur_grade, cur_syl, cur_wps, aggressive=False):
                syl_direction = ""
                if cur_syl < target_syl - 0.05:
                    syl_examples = ('show -> explain, help -> support, '
                                    'get -> obtain, find -> discover, need -> require')
                    syl_direction = f"\nSYLLABLE FIX: Current avg is {cur_syl:.2f}, need {target_syl:.2f}. Replace 1-syllable words with 2-syllable equivalents:\n   {syl_examples}"
                elif cur_syl > target_syl + 0.05:
                    syl_examples = ('utilize -> use, demonstrate -> show, require -> need, '
                                    'obtain -> get, additional -> more, significant -> big')
                    syl_direction = f"\nSYLLABLE FIX: Current avg is {cur_syl:.2f}, need {target_syl:.2f}. Replace multi-syllable words with shorter equivalents:\n   {syl_examples}"

                wps_direction = ""
                if cur_wps > max_wps + 2:
                    wps_direction = (f"\nSENTENCE FIX: Sentences average {cur_wps:.0f} words but must be {min_wps}-{max_wps}. "
                                     f"The text should have approximately {ideal_sentence_count} sentences. "
                                     f"Split the longest sentences at natural breakpoints (periods, not semicolons).")
                elif cur_wps < min_wps - 1:
                    wps_direction = (f"\nSENTENCE FIX: Sentences average only {cur_wps:.0f} words but must be {min_wps}-{max_wps}. "
                                     f"The text should have approximately {ideal_sentence_count} sentences. "
                                     f"Combine the shortest adjacent sentences using 'and', 'but', 'which', or 'because'.")

                if aggressive:
                    intensity = (f"This is a MAJOR correction — the text is far from the target. "
                                 f"Rewrite freely to hit the targets. Split or combine as many sentences as needed. "
                                 f"The text MUST have approximately {ideal_sentence_count} sentences, "
                                 f"each {min_wps}-{max_wps} words.")
                else:
                    intensity = (f"Make ONLY the minimum changes needed. "
                                 f"Replace 3-6 words max for syllable adjustment. "
                                 f"Split or combine 1-2 sentences max for length adjustment.")

                scope_instruction = (
                    "Use broad paragraph rewriting if needed; the target grade matters more than minimal edits."
                    if not going_up and target_grade <= 7 else
                    "Prefer local edits over rewriting whole paragraphs."
                )
                return f"""The text below needs adjustments to reach {grade_label} level.

Current metrics: avg {cur_syl:.2f} syl/word, avg {cur_wps:.1f} words/sentence (estimated grade {cur_grade:.1f}).
Target metrics: avg {target_syl:.2f} syl/word, avg {target_wps} words/sentence (grade {target_grade}).
Target sentence count: approximately {ideal_sentence_count} sentences.
{syl_direction}{wps_direction}

{intensity}
Keep the same facts, paragraph order, and idea order. {scope_instruction}
Do NOT add a conclusion, takeaway, moral, or wrap-up summary. Do NOT expand the final paragraph beyond its original local scope.{reference_block}

TEXT:
{text_to_fix}

ADJUSTED TEXT:"""

            # ---- Rule-based metric correction (replaces LLM correction loop) ----
            def _rule_correct(text_to_fix, cur_grade, cur_syl, cur_wps, max_rounds=2):
                """Apply rule-based vocabulary and structure adjustments to move toward target."""
                adjusted = text_to_fix
                g, s, w = cur_grade, cur_syl, cur_wps
                best_adjusted = adjusted
                best_metrics = (g, s, w)
                best_distance = self._distance_to_target_band(g, target_grade)
                for tune_round in range(max_rounds):
                    grade_ok = self._distance_to_target_band(g, target_grade) == 0
                    wps_ok = min_wps - 2 <= w <= max_wps + 3
                    syl_ok = abs(s - target_syl) <= 0.10
                    if grade_ok and wps_ok and syl_ok:
                        break

                    if g > target_grade + 1.0:
                        adjusted, _ = self._replace_difficult_words(adjusted, target_grade)
                        if w > max_wps:
                            adjusted, _ = self._split_long_sentences(adjusted, target_grade)
                    elif g < target_grade - 1.0:
                        if target_grade <= 7:
                            combined, _ = self._combine_short_sentences(adjusted, target_grade)
                            if combined != adjusted:
                                adjusted = combined
                            elif w >= min_wps:
                                adjusted, _ = self._complexify_text(adjusted, target_grade)
                        else:
                            if w < min_wps:
                                adjusted, _ = self._combine_short_sentences(adjusted, target_grade)
                            else:
                                adjusted, _ = self._complexify_text(adjusted, target_grade)

                    g, s, w = self._measure_text_metrics(adjusted)
                    distance = self._distance_to_target_band(g, target_grade)
                    if distance < best_distance:
                        best_adjusted = adjusted
                        best_metrics = (g, s, w)
                        best_distance = distance
                    print(f"[rule-correct] round {tune_round + 1}: grade={g:.1f}, syl={s:.2f}, wps={w:.1f}")
                return best_adjusted, best_metrics[0], best_metrics[1], best_metrics[2]

            rewritten, actual_grade, actual_syl, actual_wps = _rule_correct(
                rewritten, actual_grade, actual_syl, actual_wps
            )

            # Safety net for paid/unrestricted environments only. Free-tier
            # runs keep one authoring call per request and rely on rule-based
            # metric correction after that draft.
            needs_llm_metric_correction = (
                abs(actual_grade - target_grade) > 2.0 or
                (target_grade >= 13 and self._distance_to_target_band(actual_grade, target_grade) > 0)
            )
            if not self.rate_limited_llm and needs_llm_metric_correction:
                correction_prompt = _build_correction_prompt(
                    rewritten,
                    actual_grade,
                    actual_syl,
                    actual_wps,
                    aggressive=(rewrite_style == 'aggressive'),
                )
                resp_corr = self._llm_chat(
                    messages=[{"role": "user", "content": correction_prompt}],
                    temperature=min(0.2, style_temperature),
                    max_tokens=4000,
                )
                if resp_corr is not None:
                    corrected = _strip_preamble(resp_corr.choices[0].message.content.strip())
                    c_grade, c_syl, c_wps = self._measure_text_metrics(corrected)
                    print(
                        f"[fireworks] {plan_label}/correction: grade={c_grade:.1f}, "
                        f"syl={c_syl:.2f}, wps={c_wps:.1f}"
                    )
                    current_band_distance = self._distance_to_target_band(actual_grade, target_grade)
                    correction_band_distance = self._distance_to_target_band(c_grade, target_grade)
                    if correction_band_distance < current_band_distance:
                        rewritten, actual_grade, actual_syl, actual_wps = corrected, c_grade, c_syl, c_wps
                        rewritten, actual_grade, actual_syl, actual_wps = _rule_correct(
                            rewritten, actual_grade, actual_syl, actual_wps
                        )

            # Clamp extreme undershoot on downgrades to Grade 3-4
            if target_grade <= 4 and actual_grade < target_grade - 1.5:
                rewritten, _ = self._combine_short_sentences(rewritten, target_grade)
                actual_grade, actual_syl, actual_wps = self._measure_text_metrics(rewritten)
                print(f"[clamp] undershoot fix: grade={actual_grade:.1f}, syl={actual_syl:.2f}, wps={actual_wps:.1f}")

            if not include_diff:
                return rewritten, []

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
            print(f"LLM full rewrite error: {e}")
            return None, []

    # ------------------------------------------------------------------ #
    #  LLM fallback (optional)
    # ------------------------------------------------------------------ #

    def _needs_llm_help(self, text, target_grade):
        if not self.llm_client:
            return False
        doc = nlp(text)
        constraints = self.grade_constraints.get(target_grade, {'max_words': 20})
        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            if len(words) > constraints['max_words'] + 5:
                return True
        return False

    def llm_fallback(self, text, target_grade):
        if not self.llm_client:
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

            response = self._llm_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=2000,
            )
            if response is None:
                return text, []
            simplified = self._strip_llm_meta_commentary(response.choices[0].message.content.strip())
            return simplified, [{
                'type': 'ai_enhanced',
                'original': text,
                'simplified': simplified,
                'position': 0,
                'reason': 'AI-assisted simplification.',
                'id': 999
            }]
        except Exception as e:
            print(f"Fireworks API error: {e}")
            return text, []

    # Backward compatibility
    def replace_difficult_words(self, text, target_grade):
        return self._replace_difficult_words(text, target_grade)

    def split_long_sentences(self, text, target_grade):
        return self._split_long_sentences(text, target_grade)

    def convert_passive_to_active(self, text):
        return text, []
