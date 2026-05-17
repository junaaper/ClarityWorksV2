from .base import *


class ParagraphPipelineMixin:
    def _should_use_paragraph_pipeline(self, text):
        words = len(text.split())
        if words < 350:
            return False
        paragraphs = self._extract_paragraph_chunks(text)
        return len(paragraphs) >= 3

    def _split_into_rewrite_groups(self, text):
        paragraphs = self._extract_paragraph_chunks(text)
        groups = []
        for i, para in enumerate(paragraphs):
            wc = len(para['raw'].split())
            groups.append({
                'text': para['raw'].strip(),
                'start': para['start'],
                'end': para['end'],
                'paragraph_index': i,
                'group_indices': [i],
                'word_count': wc,
            })
        return groups

    def _build_paragraph_glossary(self, original_para, rewritten_para):
        glossary = {}
        orig_words = original_para.lower().split()
        new_words = rewritten_para.lower().split()
        import difflib
        matcher = difflib.SequenceMatcher(None, orig_words, new_words)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace' and (i2 - i1) == 1 and (j2 - j1) == 1:
                ow = orig_words[i1]
                nw = new_words[j1]
                if ow != nw and len(ow) > 2 and len(nw) > 2:
                    glossary[ow] = nw
                    if len(glossary) >= 20:
                        break
        return glossary

    def _paragraph_metric_contract(self, paragraph_text, target_grade, going_up):
        source_grade, source_syl, source_wps = self._measure_text_metrics(paragraph_text)
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        lower, upper = self._get_target_band(target_grade)
        target_wps = metrics['target_wps']
        target_syl = metrics['target_syl']
        target_mid = (
            lower + 0.35
            if target_grade < 13 and lower != float('-inf') and upper != float('inf')
            else (13.25 if target_grade >= 13 else 3.5)
        )
        if source_grade < lower:
            local_direction = 1
        elif source_grade >= upper:
            local_direction = -1
        else:
            local_direction = 0
        words = len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", paragraph_text or ''))
        sentences = max(1, len(self._extract_sentence_chunks(paragraph_text)))
        ideal_sentence_count = max(1, round(words / max(1, target_wps)))
        syl_delta = target_syl - source_syl
        wps_delta = target_wps - source_wps
        grade_delta = target_mid - source_grade

        if abs(grade_delta) <= 1.25:
            move_label = "small calibration"
            scope_rule = (
                "Make only light local edits. Keep the paragraph close to the source; "
                "do not inflate vocabulary or restructure every sentence."
            )
        elif abs(grade_delta) <= 3.0:
            move_label = "controlled shift"
            scope_rule = (
                "Make a controlled rewrite. Change sentence length and vocabulary enough "
                "to reach the band, but keep wording natural and paragraph-local."
            )
        else:
            move_label = "large shift"
            if target_grade >= 11 and grade_delta > 5.0:
                scope_rule = (
                    "A comprehensive academic rewrite is required. Transform the prose to match "
                    "the target grade's vocabulary and sentence complexity. Hit the syllable and "
                    "words-per-sentence targets."
                )
            else:
                scope_rule = (
                    "A broader rewrite is allowed, but the numeric targets still matter more "
                    "than sounding impressive."
                )

        if local_direction > 0:
            if grade_delta > 5.0 and target_grade >= 13:
                direction_rule = (
                    "This is a MAJOR upgrade to College level. Use professional academic prose: "
                    "multi-syllable domain vocabulary, complex subordinate clauses, and long "
                    "information-dense sentences. Academic terminology IS required to reach the target. "
                    f"Aim for avg {target_syl:.2f} syllables/word and {target_wps} words/sentence."
                )
            elif grade_delta > 5.0 and target_grade >= 11:
                direction_rule = (
                    "This is a MAJOR upgrade. Use sophisticated academic vocabulary, longer sentences "
                    "with multiple clauses, and formal prose structure. Multi-syllable academic words "
                    f"ARE required. Aim for avg {target_syl:.2f} syllables/word and {target_wps} words/sentence."
                )
            elif grade_delta > 3.0:
                direction_rule = (
                    "Raise readability substantially. Use academic vocabulary and longer, more complex "
                    "sentences to reach the target. Multi-syllable words are appropriate."
                )
            else:
                direction_rule = (
                    "Raise readability gradually. Prefer slightly longer, clearer sentences "
                    "and a few natural two-syllable words. Do not use rare academic words just "
                    "to raise the score."
                )
            task_label = "UPGRADE THIS PARAGRAPH"
        elif local_direction < 0:
            direction_rule = (
                "Lower readability gradually. Prefer shorter sentences and common words. "
                "Do not delete facts or collapse the paragraph."
            )
            task_label = "SIMPLIFY THIS PARAGRAPH"
        else:
            direction_rule = (
                "This paragraph is already inside the target band. Keep it close to the "
                "source and make only tiny grammar, flow, or consistency edits."
            )
            task_label = "KEEP THIS PARAGRAPH NEAR THE TARGET"

        band_text = (
            f"[{lower:.1f}, {upper:.1f})"
            if lower != float('-inf') and upper != float('inf')
            else ("13.0+" if target_grade >= 13 else "<4.0")
        )
        sentence_rule = (
            f"Use about {ideal_sentence_count} sentences for this paragraph "
            f"(source has {sentences}); stay within +/-1 sentence unless grammar requires otherwise."
        )
        formula_rule = (
            "The local grade model is approximately: "
            "grade = -21.16 + 14.33*(avg syllables/word) + 0.60*(avg words/sentence). "
            "This means a syllable jump of 0.50 can overshoot by about 7 grade levels."
        )

        return {
            'source_grade': source_grade,
            'source_syl': source_syl,
            'source_wps': source_wps,
            'word_count': words,
            'sentence_count': sentences,
            'ideal_sentence_count': ideal_sentence_count,
            'target_mid': target_mid,
            'target_band_text': band_text,
            'syl_delta': syl_delta,
            'wps_delta': wps_delta,
            'grade_delta': grade_delta,
            'local_direction': local_direction,
            'task_label': task_label,
            'move_label': move_label,
            'scope_rule': scope_rule,
            'direction_rule': direction_rule,
            'sentence_rule': sentence_rule,
            'formula_rule': formula_rule,
        }

    def _build_paragraph_prompt(self, paragraph_text, target_grade, going_up, glossary, para_index, total_paras):
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_wps = metrics['target_wps']
        min_wps = metrics['min_wps']
        max_wps = metrics['max_wps']
        target_syl = metrics['target_syl']
        grade_label = 'College' if target_grade >= 13 else f'Grade {target_grade}'
        contract = self._paragraph_metric_contract(paragraph_text, target_grade, going_up)

        para_word_count = len(paragraph_text.split())
        ideal_sentence_count = contract['ideal_sentence_count']

        glossary_block = ""
        if glossary:
            entries = [f'  "{k}" -> "{v}"' for k, v in list(glossary.items())[:15]]
            glossary_block = "\nTERMINOLOGY (use these consistently):\n" + "\n".join(entries) + "\n"

        position_note = f"\nThis is paragraph {para_index + 1} of {total_paras}."
        if para_index < total_paras - 1:
            position_note += " Do NOT add a concluding summary."
        else:
            position_note += " This is the final paragraph — keep it within its original local scope. Do NOT broaden it into a summary of the whole passage."

        if going_up:
            if target_grade <= 6:
                vocab_level = "slightly more formal words with some two-syllable terms"
                clause_rule = "Write clear, simple sentences. Use 'and', 'but', 'so' to combine ideas."
            elif target_grade <= 8:
                vocab_level = "clear middle-school vocabulary with natural two-syllable words; avoid stiff words like utilize"
                clause_rule = "Use AT MOST one subordinate clause per sentence."
            elif target_grade <= 10:
                vocab_level = "plain high-school vocabulary with common two-syllable words; avoid college, technical, or rare academic terms"
                clause_rule = "Use at most one subordinate clause per sentence. Keep sentences direct."
            elif target_grade <= 12:
                if contract['grade_delta'] > 5.0:
                    vocab_level = "sophisticated academic vocabulary with multi-syllable terms and formal register"
                    clause_rule = "Use 2-3 clauses per sentence. Employ subordinate clauses and complex syntax to reach the target."
                else:
                    vocab_level = "sophisticated high-school academic vocabulary — NOT college prose"
                    clause_rule = "Use 2-3 clauses per sentence maximum."
            else:
                vocab_level = "professional academic prose with domain-specific terminology"
                clause_rule = "Use full academic sentence complexity."

            return f"""Rewrite this paragraph at exactly {grade_label} writing level.

TASK: {contract['task_label']}.

LOCAL READABILITY CONTRACT:
  - Current paragraph: raw grade {contract['source_grade']:.2f}, {contract['source_syl']:.2f} syllables/word, {contract['source_wps']:.1f} words/sentence, {contract['sentence_count']} sentences, {contract['word_count']} words
  - Target paragraph band: {grade_label} raw {contract['target_band_text']}; aim near raw {contract['target_mid']:.2f}, not above the band
  - Target metrics: {target_syl:.2f} syllables/word and about {target_wps} words/sentence
  - Required movement: {contract['move_label']} of about {contract['grade_delta']:+.2f} raw grades, {contract['syl_delta']:+.2f} syllables/word, {contract['wps_delta']:+.1f} words/sentence
  - Sentence budget: {contract['sentence_rule']}
  - Calibration note: {contract['formula_rule']}

RULES:
1. SCOPE: {contract['scope_rule']}
2. DIRECTION: {contract['direction_rule']}
3. VOCABULARY: Use {vocab_level}.
4. CLAUSE COMPLEXITY: {clause_rule}
5. SYLLABLE COUNT: Aim for avg {target_syl:.2f} syllables/word.{' Do not overshoot this.' if contract['grade_delta'] <= 5.0 else ''}
6. SENTENCE LENGTH: Every sentence must be {min_wps}-{max_wps} words.
7. CONTEXTUAL FIT: Every word must make sense in context.
8. {'TARGET FLOOR: You MUST reach College level (raw grade 13+). Use academic vocabulary and complex sentences to ensure you hit the target.' if target_grade >= 13 else ('TARGET: Hit ' + grade_label + ' level. Academic vocabulary IS appropriate for this grade. Focus on reaching the syllable and sentence length targets.' if target_grade >= 11 and contract['grade_delta'] > 5.0 else 'TARGET CEILING: Do NOT write above ' + grade_label + '. Do not use college-level diction, technical jargon, or rare Latinate words to raise the score.')}
9. PRESERVE MEANING: Keep all facts and proper nouns exactly.
10. NO REPETITION: Each idea appears once only.
11. OUTPUT: Write ONLY the rewritten paragraph. No labels or commentary.{glossary_block}{position_note}

PARAGRAPH TO REWRITE:
{paragraph_text}

REWRITTEN PARAGRAPH ({grade_label}):"""
        else:
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
                source_grade=self._measure_text_metrics(paragraph_text)[0],
            )

            # Grade style profile (gives LLM concrete prose anchor, not just numbers)
            grade_profile = GRADE_PROFILES.get(target_grade, '')
            profile_block = f"\nTARGET STYLE PROFILE:\n{grade_profile}\n" if grade_profile else ""

            # Few-shot example for large downgrade gaps (most effective for style transfer)
            source_para_grade = contract['source_grade']
            example_block = ""
            if source_para_grade - target_grade >= 3 and target_grade <= 6:
                if target_grade <= 4:
                    example_block = """
EXAMPLE of Grade 4 writing (study this pattern):
  Original (Grade 8): "The accumulation of moisture in atmospheric pressure systems generates precipitation patterns that affect regional agriculture."
  Grade 4 rewrite: "Water builds up in the air around pressure systems. This causes rain that helps farms in the area grow food."
  Note: every hard word is replaced with a short one; long sentences become two short ones; "pressure" is kept as the domain term.

"""
                else:
                    example_block = """
EXAMPLE of Grade 5-6 writing (study this pattern):
  Original (Grade 9): "Environmental conservation requires comprehensive strategies that address both industrial emissions and individual consumption patterns."
  Grade 5 rewrite: "To protect nature, people need good plans. These plans should deal with pollution from factories and with how much people buy and use."

"""

            # Content nouns that must be preserved (replaced with simpler synonym if needed, never dropped)
            content_nouns = self._extract_key_content_nouns(paragraph_text)
            noun_block = ""
            if content_nouns:
                noun_list = ", ".join(content_nouns)
                noun_block = f"""
CONTENT WORDS TO PRESERVE (use a simpler synonym if needed, but NEVER drop entirely):
  {noun_list}

"""

            return f"""Rewrite this paragraph at exactly {grade_label} reading level.

TASK: {contract['task_label']}.

LOCAL READABILITY CONTRACT:
  - Current paragraph: raw grade {contract['source_grade']:.2f}, {contract['source_syl']:.2f} syllables/word, {contract['source_wps']:.1f} words/sentence, {contract['sentence_count']} sentences, {contract['word_count']} words
  - Target paragraph band: {grade_label} raw {contract['target_band_text']}; aim near raw {contract['target_mid']:.2f}, not below the band
  - Target metrics: {target_syl:.2f} syllables/word and about {target_wps} words/sentence
  - Required movement: {contract['move_label']} of about {contract['grade_delta']:+.2f} raw grades, {contract['syl_delta']:+.2f} syllables/word, {contract['wps_delta']:+.1f} words/sentence
  - Sentence budget: {contract['sentence_rule']}
  - Calibration note: {contract['formula_rule']}
{profile_block}
RULES:
1. SCOPE: {contract['scope_rule']}
2. DIRECTION: {contract['direction_rule']}
3. VOCABULARY: Use {vocab_level}.
4. SYLLABLE COUNT: Aim for avg {target_syl:.2f} syllables/word. Prefer short words, but do not undershoot the target band.
5. SENTENCE LENGTH: Every sentence must be {min_wps}-{max_wps} words. Split longer ones.
6. CONTEXTUAL FIT: Every simpler word must make sense in context.
7. PRESERVE MEANING: Keep ALL facts and proper nouns. Never drop a content word without replacing it with a simpler synonym.
8. NO REPETITION: Each idea appears once only. Do NOT generate new content.
9. OUTPUT: Write ONLY the simplified paragraph. No labels or commentary.{glossary_block}{position_note}
{example_block}{noun_block}{low_grade_block}
PARAGRAPH TO REWRITE:
{paragraph_text}

SIMPLIFIED PARAGRAPH ({grade_label}):"""

    def _rewrite_single_paragraph(self, paragraph_text, target_grade, going_up, glossary, para_index, total_paras, metric_feedback=None):
        metrics = GRADE_TARGET_METRICS.get(target_grade, GRADE_TARGET_METRICS[8])
        target_syl = metrics['target_syl']
        min_wps = metrics['min_wps']
        max_wps = metrics['max_wps']
        source_grade, source_syl, source_wps = self._measure_text_metrics(paragraph_text)
        band_lower, band_upper = self._get_target_band(target_grade)

        prompt = self._build_paragraph_prompt(
            paragraph_text, target_grade, going_up, glossary, para_index, total_paras,
        )

        if metric_feedback:
            cur_grade = metric_feedback.get('grade', 0)
            cur_syl = metric_feedback.get('syl', 0)
            cur_wps = metric_feedback.get('wps', 0)
            unusable_reason = metric_feedback.get('unusable_reason')
            if cur_grade < band_lower:
                gap_to_band = band_lower - cur_grade
                if gap_to_band > 3.0:
                    direction_hint = (
                        f"Your result ({cur_grade:.1f}) is FAR BELOW the target band "
                        f"[{band_lower:.0f}-{band_upper:.0f}). Use significantly longer sentences with "
                        f"multiple clauses and replace simple words with multi-syllable academic equivalents. "
                        f"Aim for avg {target_syl:.2f} syllables/word and {metrics['target_wps']} words/sentence."
                    )
                elif gap_to_band > 1.5:
                    direction_hint = (
                        f"Your result ({cur_grade:.1f}) is well below the target band "
                        f"[{band_lower:.0f}-{band_upper:.0f}). Use noticeably longer sentences "
                        f"and higher-syllable vocabulary to raise the grade toward the band."
                    )
                else:
                    direction_hint = (
                        f"Your result ({cur_grade:.1f}) is BELOW the target band "
                        f"[{band_lower:.0f}-{band_upper:.0f}). Use slightly longer sentences "
                        f"and slightly higher syllable vocabulary to raise the grade, but stay inside the band."
                    )
            elif cur_grade >= band_upper:
                direction_hint = (
                    f"Your result ({cur_grade:.1f}) is ABOVE the target band "
                    f"[{band_lower:.0f}-{band_upper:.0f}). Use shorter sentences "
                    f"and simpler vocabulary to lower the grade. Do not add more academic wording."
                )
            else:
                direction_hint = (
                    f"Your result ({cur_grade:.1f}) is in the target band but the "
                    f"document average needs adjustment."
                )
            dropped_noun_note = ""
            if unusable_reason and 'content_nouns_dropped:' in unusable_reason:
                dropped_part = unusable_reason.split('content_nouns_dropped:')[1]
                dropped_noun_note = (
                    f"\nCRITICAL: The previous rewrite dropped these content words entirely: {dropped_part}. "
                    "Each must appear in the rewrite — use a simpler synonym if needed, but do not omit them.\n"
                )
            correction = f"""The previous rewrite of this paragraph missed the target.

SOURCE PARAGRAPH: grade={source_grade:.2f}, syl={source_syl:.2f}, wps={source_wps:.1f}
PREVIOUS RESULT: grade={cur_grade:.2f}, syl={cur_syl:.2f}, wps={cur_wps:.1f}
TARGET CONTRACT: raw band=[{band_lower:.1f}, {band_upper:.1f}), syl={target_syl:.2f}, wps={metrics['target_wps']}, sentence length={min_wps}-{max_wps}
REJECTION REASON: {unusable_reason or 'target miss'}

{direction_hint}
{dropped_noun_note}
Rewrite this paragraph to correct the grade level. Move the metrics toward the TARGET CONTRACT only; do not make a broad stylistic rewrite.
"""
            prompt = correction + prompt

        source_gap = abs(float(target_grade) - float(source_grade))
        if source_gap <= 2.0:
            temperature = 0.08
        elif source_gap <= 3.0:
            temperature = 0.14
        elif source_gap <= 5.0:
            temperature = 0.28
        elif target_grade >= 11 and source_gap > 7.0:
            temperature = 0.42
        else:
            temperature = 0.35
        if metric_feedback:
            temperature = min(0.50, temperature + 0.15)
        resp = self._llm_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=2200,
        )
        if resp is None:
            return paragraph_text, 0.0, 0.0, 0.0

        text_out = self._strip_llm_meta_commentary(resp.choices[0].message.content.strip())

        g, s, w = self._measure_text_metrics(text_out)

        print(f"[para-pipeline] group {para_index}: grade={g:.1f}, syl={s:.2f}, wps={w:.1f}")
        return text_out, g, s, w

    def _assemble_paragraphs(self, rewrite_groups, rewritten_texts):
        return '\n\n'.join(rewritten_texts)

    def _paragraph_level_diff(self, original_text, rewrite_groups, rewritten_texts, target_grade, going_up):
        all_changes = []
        rewritten_offset = 0

        for group, rtext in zip(rewrite_groups, rewritten_texts):
            orig_slice = original_text[group['start']:group['end']]

            if orig_slice.strip() == rtext.strip():
                rewritten_offset += len(rtext) + 2
                continue

            changes = self._diff_sentence_changes(
                original_text=orig_slice,
                rewritten_text=rtext,
                target_grade=target_grade,
                going_up=going_up,
                original_offset=group['start'],
                rewritten_offset=rewritten_offset,
            )

            if not changes:
                fallback = self._build_patch_change(
                    original_raw=orig_slice,
                    replacement_raw=rtext,
                    start=group['start'],
                    end=group['end'],
                    preview_start=rewritten_offset,
                    target_grade=target_grade,
                    going_up=going_up,
                    allow_fallback=True,
                )
                if fallback:
                    changes = [fallback]

            for change in changes:
                change['paragraph_index'] = group.get('paragraph_index')
                change['rewrite_group_index'] = group.get('paragraph_index')
                change['paragraph_start'] = group['start']
                change['paragraph_end'] = group['end']

            all_changes.extend(changes)
            rewritten_offset += len(rtext) + 2

        for i, change in enumerate(all_changes):
            change['id'] = i

        return self._assign_dependency_groups(all_changes)

    def _paragraph_rewrite_is_usable(self, original_para, rewritten_para, target_grade, going_up, measured_grade=None):
        if not rewritten_para or not rewritten_para.strip():
            return False, 'empty_paragraph_rewrite'

        para_metrics = self._measure_candidate_preview_metrics(
            original_para,
            rewritten_para,
            target_grade,
        )
        if measured_grade is not None:
            para_metrics['raw_score'] = round(measured_grade, 2)
            para_metrics['target_distance'] = round(
                self._distance_to_target_band(measured_grade, target_grade),
                2,
            )
        orig_grade = self._measure_text_metrics(original_para)[0]
        sanity = self._run_local_sanity_check(
            original_text=original_para,
            candidate_text=rewritten_para,
            target_grade=target_grade,
            source_grade=orig_grade,
            final_metrics=para_metrics,
        )

        # Compute improvement: how many grades closer to target the candidate is vs the original
        cand_grade = measured_grade if measured_grade is not None else float(
            para_metrics.get('raw_score', 0) or 0
        )
        orig_dist = self._distance_to_target_band(orig_grade, target_grade)
        cand_dist = self._distance_to_target_band(cand_grade, target_grade)
        improvement = orig_dist - cand_dist

        severe = list(sanity.get('severe_flags', []))
        if severe and improvement > 3.0:
            # Large improvement — relax content/protected-term flags; keep structural flags strict
            relaxable = {f for f in severe if
                         f.startswith('missing_protected_term:') or
                         f.startswith('content_nouns_dropped') or
                         f == 'worse_than_original_for_target'}
            if relaxable:
                severe = [f for f in severe if f not in relaxable]
                print(f"[para-usable] relaxed {len(relaxable)} flag(s) (improvement={improvement:.1f} grades, cand={cand_grade:.2f}→target={target_grade})")

        if severe:
            return False, 'local_sanity:' + ','.join(severe[:3])

        # Check for mass content noun dropping during downgrade
        if not going_up:
            content_nouns = self._extract_key_content_nouns(original_para)
            if content_nouns:
                rewritten_lower = rewritten_para.lower()
                dropped = [n for n in content_nouns if n.lower() not in rewritten_lower]
                # Relax thresholds when candidate represents a large grade improvement
                drop_limit = 5 if improvement > 3.0 else 3
                drop_ratio = 0.60 if improvement > 3.0 else 0.40
                if len(dropped) >= drop_limit or len(dropped) / max(1, len(content_nouns)) > drop_ratio:
                    return False, f'content_nouns_dropped:{",".join(dropped[:3])}'

        raw_score = float(para_metrics.get('raw_score', measured_grade or 0.0) or 0.0)
        display_delta = self._display_grade_delta_from_score(raw_score, target_grade)
        if going_up and target_grade < 13:
            hard_ceiling = float(target_grade) + 2.25
            if raw_score > hard_ceiling or display_delta > 2:
                return False, f'overshot_target:raw_{raw_score:.2f}'
        elif (not going_up) and display_delta > 3 and para_metrics.get('target_distance', 0) > 2.5:
            return False, f'missed_target:raw_{raw_score:.2f}'

        return True, ''

    def _paragraph_pipeline(self, text, target_grade, mode, progress_callback=None):
        source_grade, source_syl, source_wps = self._measure_text_metrics(text)
        going_up = target_grade > source_grade
        groups = self._split_into_rewrite_groups(text)
        n_groups = len(groups)

        print(f"[para-pipeline] {n_groups} groups, source_grade={source_grade:.1f}, target={target_grade}, going_up={going_up}")

        rewritten_texts = []
        glossary = {}
        failed_paragraphs = []
        repair_attempts = {}
        repair_rounds_used = 0
        rate_limited = False

        def rule_fallback_for_group(group_text, max_rounds=2):
            rule_fallback = self._rule_adjust_llm_candidate_to_target(
                group_text,
                target_grade=target_grade,
                going_up=going_up,
                max_rounds=max_rounds,
            )
            text_out = (
                rule_fallback
                if rule_fallback and rule_fallback.strip() != group_text.strip()
                else group_text
            )
            g, s, w = self._measure_text_metrics(text_out)
            return text_out, g, s, w

        for i, group in enumerate(groups):
            pct = (i / max(1, n_groups)) * 0.85
            self._emit_progress(
                progress_callback,
                pct,
                f'Rewriting paragraph {i + 1} of {n_groups}...',
                None,
                rewrite_route='large_shift_llm',
                phase='paragraph_rewrite',
                current_paragraph=i + 1,
                total_paragraphs=n_groups,
                llm_calls_used=self._llm_calls_made,
                llm_call_budget=self._llm_call_budget,
            )

            # Change C: skip LLM for very short groups (headers, labels, metadata)
            group_word_count = len(group['text'].split())
            if group_word_count < 25:
                print(f"[para-pipeline] group {i}: short group ({group_word_count} words), skipping LLM")
                text_out, g, s, w = rule_fallback_for_group(group['text'], max_rounds=1)
                if i == 0 and text_out != group['text']:
                    glossary = self._build_paragraph_glossary(group['text'], text_out)
                rewritten_texts.append(text_out)
                continue

            # Change B: guard initial LLM call — skip to rule fallback if budget already exhausted
            if rate_limited or not self._llm_calls_remaining():
                reason = 'rate limit reached' if rate_limited else 'no LLM budget remaining'
                print(f"[para-pipeline] group {i}: {reason}, applying rule fallback directly")
                text_out, g, s, w = rule_fallback_for_group(group['text'], max_rounds=2)
                failed_paragraphs.append(i)
                if i == 0 and text_out != group['text']:
                    glossary = self._build_paragraph_glossary(group['text'], text_out)
                rewritten_texts.append(text_out)
                continue

            try:
                text_out, g, s, w = self._rewrite_single_paragraph(
                    group['text'], target_grade, going_up, glossary, i, n_groups,
                )
            except Exception as exc:
                if not self._is_rate_limit_error(exc):
                    raise
                rate_limited = True
                print(
                    f"[para-pipeline] group {i}: Fireworks rate limit hit; "
                    "using rule fallback for this and remaining paragraphs"
                )
                text_out, g, s, w = rule_fallback_for_group(group['text'], max_rounds=2)
                failed_paragraphs.append(i)
                if i == 0 and text_out != group['text']:
                    glossary = self._build_paragraph_glossary(group['text'], text_out)
                rewritten_texts.append(text_out)
                continue

            usable, unusable_reason = self._paragraph_rewrite_is_usable(
                group['text'],
                text_out,
                target_grade,
                going_up,
                measured_grade=g,
            )
            if not usable:
                print(f"[para-pipeline] group {i} rejected ({unusable_reason}); retrying once with metric feedback")
                retry_text = ''
                if not rate_limited and self._llm_calls_remaining():
                    try:
                        retry_text, retry_g, retry_s, retry_w = self._rewrite_single_paragraph(
                            group['text'],
                            target_grade,
                            going_up,
                            glossary,
                            i,
                            n_groups,
                            metric_feedback={
                                'grade': g,
                                'syl': s,
                                'wps': w,
                                'unusable_reason': unusable_reason,
                            },
                        )
                    except Exception as exc:
                        if not self._is_rate_limit_error(exc):
                            raise
                        rate_limited = True
                        print(
                            f"[para-pipeline] group {i} retry hit Fireworks rate limit; "
                            "applying rule fallback"
                        )
                        text_out, g, s, w = rule_fallback_for_group(group['text'], max_rounds=2)
                        failed_paragraphs.append(i)
                        repair_attempts[i] = repair_attempts.get(i, 0) + 1
                        retry_text = ''
                    if not retry_text:
                        pass
                    else:
                        retry_usable, retry_reason = self._paragraph_rewrite_is_usable(
                            group['text'],
                            retry_text,
                            target_grade,
                            going_up,
                            measured_grade=retry_g,
                        )
                        if retry_usable:
                            text_out, g, s, w = retry_text, retry_g, retry_s, retry_w
                            repair_attempts[i] = repair_attempts.get(i, 0) + 1
                        else:
                            print(
                                f"[para-pipeline] group {i} retry rejected ({retry_reason}); "
                                "applying rule fallback"
                            )
                            text_out, g, s, w = rule_fallback_for_group(group['text'], max_rounds=2)
                            failed_paragraphs.append(i)
                            repair_attempts[i] = repair_attempts.get(i, 0) + 1
                elif not rate_limited:
                    print(
                        f"[para-pipeline] group {i} rejected ({unusable_reason}); "
                        "applying rule fallback"
                    )
                    text_out, g, s, w = rule_fallback_for_group(group['text'], max_rounds=2)
                    failed_paragraphs.append(i)
                    repair_attempts[i] = repair_attempts.get(i, 0) + 1
                else:
                    print(
                        f"[para-pipeline] group {i} rejected ({unusable_reason}) after rate limit; "
                        "applying rule fallback"
                    )
                    text_out, g, s, w = rule_fallback_for_group(group['text'], max_rounds=2)
                    failed_paragraphs.append(i)
                    repair_attempts[i] = repair_attempts.get(i, 0) + 1

            pct = ((i + 1) / max(1, n_groups)) * 0.85
            self._emit_progress(
                progress_callback,
                pct,
                f'Paragraph {i + 1} complete (grade {g:.1f})...',
                None,
                rewrite_route='large_shift_llm',
                phase='paragraph_complete',
                current_paragraph=i + 1,
                total_paragraphs=n_groups,
                llm_calls_used=self._llm_calls_made,
                llm_call_budget=self._llm_call_budget,
            )

            if i == 0 and text_out != group['text']:
                glossary = self._build_paragraph_glossary(group['text'], text_out)

            rewritten_texts.append(text_out)

        assembled = self._assemble_paragraphs(groups, rewritten_texts)

        self._emit_progress(
            progress_callback,
            0.88,
            'Checking document grade...',
            None,
            rewrite_route='large_shift_llm',
            phase='document_check',
            current_paragraph=n_groups,
            total_paragraphs=n_groups,
            llm_calls_used=self._llm_calls_made,
            llm_call_budget=self._llm_call_budget,
        )

        doc_grade, doc_syl, doc_wps = self._measure_text_metrics(assembled)
        distance = self._distance_to_target_band(doc_grade, target_grade)
        print(f"[para-pipeline] assembled: grade={doc_grade:.1f}, distance={distance:.2f}")

        band_lower, band_upper = self._get_target_band(target_grade)

        grade_gap = abs(float(target_grade) - source_grade)
        max_repair_rounds = 1 if grade_gap <= 3.0 else (2 if grade_gap <= 6.0 else 3)
        for repair_round in range(max_repair_rounds):
            if distance <= 0:
                break
            if rate_limited:
                break
            if not self._llm_calls_remaining():
                break

            doc_below = doc_grade < band_lower
            doc_above = doc_grade >= band_upper

            worst_idx = -1
            worst_distance = -1
            for j, (group, rtext) in enumerate(zip(groups, rewritten_texts)):
                if repair_attempts.get(j, 0) >= max_repair_rounds:
                    continue
                pg, _, _ = self._measure_text_metrics(rtext)
                pd = self._distance_to_target_band(pg, target_grade)
                pg_below = pg < band_lower
                pg_above = pg >= band_upper
                if doc_below and pg_above:
                    continue
                if doc_above and pg_below:
                    continue
                if pd > worst_distance:
                    worst_distance = pd
                    worst_idx = j

            if worst_idx < 0 or worst_distance <= 0:
                break

            self._emit_progress(
                progress_callback,
                0.88 + repair_round * 0.03,
                f'Repairing paragraph {worst_idx + 1}...',
                None,
                rewrite_route='large_shift_llm',
                phase='paragraph_repair',
                current_paragraph=worst_idx + 1,
                total_paragraphs=n_groups,
                llm_calls_used=self._llm_calls_made,
                llm_call_budget=self._llm_call_budget,
            )

            pg, ps, pw = self._measure_text_metrics(rewritten_texts[worst_idx])
            feedback = {'grade': pg, 'syl': ps, 'wps': pw}
            try:
                repaired, rg, rs, rw = self._rewrite_single_paragraph(
                    groups[worst_idx]['text'], target_grade, going_up, glossary,
                    worst_idx, n_groups, metric_feedback=feedback,
                )
            except Exception as exc:
                if not self._is_rate_limit_error(exc):
                    raise
                rate_limited = True
                failed_paragraphs.append(worst_idx)
                print(
                    f"[para-pipeline] repair paragraph {worst_idx} hit Fireworks rate limit; "
                    "ending paragraph repairs"
                )
                break
            usable, unusable_reason = self._paragraph_rewrite_is_usable(
                groups[worst_idx]['text'],
                repaired,
                target_grade,
                going_up,
                measured_grade=rg,
            )
            repair_attempts[worst_idx] = repair_attempts.get(worst_idx, 0) + 1
            if not usable:
                print(
                    f"[para-pipeline] repair paragraph {worst_idx} rejected "
                    f"({unusable_reason})"
                )
                failed_paragraphs.append(worst_idx)
                continue

            old_distance = self._distance_to_target_band(pg, target_grade)
            new_distance = self._distance_to_target_band(rg, target_grade)
            if new_distance < old_distance:
                rewritten_texts[worst_idx] = repaired
                assembled = self._assemble_paragraphs(groups, rewritten_texts)
                doc_grade, doc_syl, doc_wps = self._measure_text_metrics(assembled)
                distance = self._distance_to_target_band(doc_grade, target_grade)
                repair_rounds_used += 1
                print(f"[para-pipeline] repair round {repair_round + 1}: grade={doc_grade:.1f}, distance={distance:.2f}")

        far_miss = distance > 2.0
        fallback_used = False
        if far_miss and not rate_limited and self._llm_calls_remaining():
            print(f"[para-pipeline] distance {distance:.2f} > 2.0, attempting whole-doc fallback")
            fallback_feedback = {'raw_score': doc_grade, 'target_distance': distance}
            try:
                fallback_result, _ = self._llm_full_rewrite(
                    original_text=text,
                    target_grade=target_grade,
                    going_up=going_up,
                    rewrite_style='aggressive',
                    reference_text=assembled,
                    metric_feedback=fallback_feedback,
                    plan_label='wholedoc_fallback',
                    include_diff=False,
                )
                if fallback_result:
                    fb_grade, fb_syl, fb_wps = self._measure_text_metrics(fallback_result)
                    fb_distance = self._distance_to_target_band(fb_grade, target_grade)
                    print(f"[para-pipeline] whole-doc fallback: grade={fb_grade:.1f}, distance={fb_distance:.2f}")
                    if fb_distance < distance:
                        assembled = fallback_result
                        doc_grade, doc_syl, doc_wps = fb_grade, fb_syl, fb_wps
                        distance = fb_distance
                        far_miss = distance > 2.0
                        fallback_used = True
            except Exception as exc:
                print(f"[para-pipeline] whole-doc fallback failed: {exc}")
        elif far_miss:
            print(f"[para-pipeline] distance {distance:.2f} > 2.0, no LLM budget for whole-doc fallback")

        self._emit_progress(
            progress_callback,
            0.95,
            'Analyzing changes...',
            None,
            rewrite_route='large_shift_llm',
            phase='diff',
            current_paragraph=n_groups,
            total_paragraphs=n_groups,
            llm_calls_used=self._llm_calls_made,
            llm_call_budget=self._llm_call_budget,
        )

        score = self._alignment_score(doc_grade, target_grade)
        return {
            'text': assembled,
            'score': score,
            'going_up': going_up,
            'selection_summary': {
                'generation_mode': 'paragraph_pipeline',
                'paragraph_count': n_groups,
                'doc_grade': round(doc_grade, 2),
                'distance': round(distance, 2),
                'repair_rounds': repair_rounds_used,
                'paragraph_pipeline_far_miss': far_miss,
                'paragraph_pipeline_failed_paragraphs': sorted(set(failed_paragraphs)),
                'paragraph_pipeline_rate_limited': rate_limited,
                'fallback_used': fallback_used,
                '_rewrite_groups': groups,
                '_rewritten_texts': rewritten_texts,
            },
            'top_candidates': [{
                'text': assembled,
                'score': score,
                'raw_score': round(doc_grade, 2),
                'selection_path': ['paragraph_pipeline'],
            }],
        }

    # ------------------------------------------------------------------ #
    #  LLM rewrite candidate generation
    # ------------------------------------------------------------------ #
