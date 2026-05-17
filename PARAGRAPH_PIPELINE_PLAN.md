# Paragraph-First Rewrite Pipeline

## Context

The simplifier (`ml-service/models/simplifier.py`, 9017 lines) treats entire documents as a single rewrite unit. For long texts this means:
- Up to 40 full-document `_measure_text_metrics()` calls in the greedy loop
- Word-by-word synonym lookup with sequential Datamuse HTTP calls
- Multiple cascading Fireworks LLM calls on the full document
- **Result: 3-8 minute wall time for 500+ word texts**

The fix: split into paragraphs, rewrite each one with strict grade targets, assemble, verify once, repair only the paragraph causing the miss. Short texts (< 350 words or < 3 paragraphs) keep the existing whole-document pipeline.

## URGENT: Fireworks Model Migration (Day 0 — do before anything else)

`llama-v3p3-70b-instruct` is being decommissioned May 14 (3 days). It's used in 4 files:
- `ml-service/models/simplifier.py:28` — `FIREWORKS_MODEL` constant
- `ml-service/models/llm_validator.py:5` — `FIREWORKS_MODEL` constant
- `ml-service/models/concept_extractor.py:7` — `FIREWORKS_MODEL` constant
- `ml-service/models/rag_engine.py:549` — hardcoded inline

Fireworks recommends `gpt-oss-120b`. Evaluate against `kimi-k2.6` and `glm-5.1`:
- **gpt-oss-120b**: Largest (120B), likely best instruction-following for metric targets. Higher latency per call, but paragraph pipeline uses smaller prompts so this may be offset.
- **kimi-k2.6**: Mid-size, potentially faster. Need to test if it follows precise syllable/WPS targets.
- **glm-5.1**: Another option, recommended for Deepseek/GLM users.

**Action**: Swap model ID, test with 3-4 existing simplification scenarios (grade 5 downgrade, grade 10 upgrade, grade 3 extreme downgrade), verify grade accuracy hasn't regressed. This is a one-line change per file once the model is chosen.

## Files to Modify

| File | Change |
|------|--------|
| `ml-service/models/simplifier.py` | Add 7 new methods, modify routing in `simplify_to_grade()`, update `FIREWORKS_MODEL` |
| `ml-service/models/llm_validator.py` | Update `FIREWORKS_MODEL` |
| `ml-service/models/concept_extractor.py` | Update `FIREWORKS_MODEL` |
| `ml-service/models/rag_engine.py` | Update hardcoded model string at line 549 |
| `ml-service/app.py` | Add progress tracking dict + `/simplify/progress/<task_id>` endpoint |
| `backend/src/controllers/simplifyController.ts` | Add async analyze + progress polling proxy |
| `backend/src/routes/simplifyRoutes.ts` | Add progress route |
| `frontend/src/components/Simplification/SimplifyPage.tsx` | Add progress polling + progress bar UI |
| `frontend/src/services/api.ts` | Add progress polling method |

## New Methods on TextSimplifier

### 1. `_should_use_paragraph_pipeline(self, text) -> bool`
Simple gate: returns `True` when `word_count >= 350` or `paragraph_count >= 3`. Uses `_extract_paragraph_chunks()` (line 6785) for paragraph count.

### 2. `_split_into_rewrite_groups(self, text) -> list[dict]`
Splits via existing `_extract_paragraph_chunks()` (line 6785). Each group is:
```python
{'text': str, 'start': int, 'end': int, 'group_indices': list[int], 'word_count': int}
```
- Paragraphs under 80 words are merged with their shortest neighbor (forward-merge, backward if last)
- Never merge more than 3 original paragraphs into one group
- `group_indices` tracks original paragraph indices for reassembly

### 3. `_build_paragraph_glossary(self, original_para: str, rewritten_para: str) -> dict`
After paragraph 0 is rewritten, diff it against the original to extract word replacements. Returns `{original_word: replacement_word}`, capped at 20 entries. Uses the existing `_diff_changes()` to find word-level swaps.

### 4. `_build_paragraph_prompt(self, paragraph_text, target_grade, going_up, glossary, para_index, total_paras) -> str`
Adapts the existing prompt templates from `_llm_full_rewrite()` (lines 8673-8765) for paragraph-level use:
- **Sentence count**: `max(1, round(para_word_count / target_wps))` instead of whole-doc count
- **Remove**: "Keep the SAME number of paragraphs" rule (it IS one paragraph)
- **Add**: Glossary section — `TERMINOLOGY (use consistently): "X" -> "Y", ...`
- **Add**: Position context — `This is paragraph {i+1} of {N}. Do NOT add a concluding summary.` (unless last paragraph)
- **Keep**: All metric targets from `GRADE_TARGET_METRICS`, style rules, vocabulary rules, contextual fit rules, ending discipline
- **Keep**: Same `_low_grade_downgrade_instructions()` for grade <= 4

### 5. `_rewrite_single_paragraph(self, paragraph_text, original_paragraph, target_grade, going_up, glossary, para_index, total_paras, metric_feedback=None) -> tuple[str, float, float, float]`
Core rewrite method for one paragraph:
1. Build prompt via `_build_paragraph_prompt()`
2. Call `self._llm_chat()` (line 816) — one LLM call
3. Strip preamble via `_strip_llm_meta_commentary()`
4. Measure: `grade, syl, wps = _measure_text_metrics(result)` (cheap — small paragraph)
5. Apply `_rule_correct()` (line 8848) on just this paragraph for fine-tuning
6. Return `(rewritten_text, grade, syl, wps)`

If `metric_feedback` is provided (repair round), prepend correction context using `_build_correction_prompt()` logic (line 8795).

### 6. `_assemble_paragraphs(self, rewrite_groups, rewritten_texts, original_text) -> str`
- Join rewritten paragraphs with `'\n\n'`
- If a group spans multiple original paragraphs, use `_restore_paragraph_shape()` (line 6811) logic to re-insert breaks
- Verify paragraph count matches original; log warning if not

### 7. `_paragraph_pipeline(self, text, target_grade, mode) -> dict`
Orchestrator. Returns the same dict shape that the existing finalization code expects (starting at line 937):

```python
{
    'text': str,        # assembled rewritten text
    'score': float,     # alignment score
    'going_up': bool,
    'selection_summary': dict,
    'top_candidates': list,
}
```

**Flow:**
1. `groups = _split_into_rewrite_groups(text)`
2. `source_grade, _, _ = _measure_text_metrics(text)` (already done at line 908)
3. `going_up = target_grade > source_grade`
4. Rewrite group 0 -> extract glossary
5. Rewrite groups 1..N with glossary
6. Assemble via `_assemble_paragraphs()`
7. `doc_grade, _, _ = _measure_text_metrics(assembled)` — **one whole-doc check**
8. `distance = _distance_to_target_band(doc_grade, target_grade)` (line 5006)
9. If `distance > 0` and budget allows: find worst paragraph (largest individual distance among groups with 80+ words), re-prompt with metric_feedback, re-assemble, re-check. Max 2 repair rounds.
10. If final result has `distance > 2.0`, return `None` (fall through to existing pipeline)
11. Build selection_summary with `'generation_mode': 'paragraph_pipeline'`

**LLM budget**: `N_groups + 2` (one per group + up to 2 repairs), capped at `max_llm_calls_per_request`. If more groups than budget, batch remaining groups into one concatenated LLM call with paragraph markers.

## Routing in `simplify_to_grade()` (line 897)

Insert after line 913 (budget setup), before the `try` block at line 915:

```python
if (self.llm_client and not prefer_rule_based 
    and self._should_use_paragraph_pipeline(text)):
    try:
        para_result = self._paragraph_pipeline(text, target_grade, mode)
        if para_result is not None:
            selection = para_result  # same shape -> feeds into line 927+
    except Exception as e:
        print(f"[paragraph_pipeline] failed, falling back: {e}")
        selection = None
    
    if selection is None:
        # Fall through to existing whole-document pipeline
        selection = self._select_authoring_candidate(...)
else:
    selection = self._select_authoring_candidate(...)
```

Everything after line 927 (finalization, greedy, validation, summary) stays unchanged. The paragraph pipeline's output feeds into the same `_finalize_preview_candidate()` -> `_diff_changes()` -> change generation path.

## Position Mapping (no new code needed)

The existing `_diff_changes()` (line 8457) already does paragraph -> sentence -> word hierarchical diffing. After assembly, calling `_diff_changes(original_text, assembled_text, target_grade, going_up)` produces correctly positioned changes. The existing `_finalize_preview_candidate()` (called at line 937) handles this automatically.

## Change Reasons — No Impact

The paragraph pipeline's assembled output feeds into the exact same finalization path:
1. `_finalize_preview_candidate()` (line 937) calls `_diff_changes()` on (original, assembled) pair
2. `_diff_changes()` (line 8457) does paragraph -> sentence -> word hierarchical diffing
3. Each change gets `reason`, `explanation_items`, `rule_id`, `reason_code`, `evidence` populated by `_build_patch_change()` (line 7815)
4. `_assign_dependency_groups()` links related structural changes

All of this runs on the (original_text, candidate_text) pair regardless of how the candidate was produced. The paragraph pipeline only changes *how the candidate is generated*, not how changes/reasons are extracted from it.

## Polling-Based Progress Indicator

### ML Service (`app.py`)

Add an in-memory progress store and async processing:

```python
import threading, uuid

_simplify_tasks = {}  # {task_id: {status, progress, message, eta_seconds, result, error}}

@app.route('/simplify/analyze', methods=['POST'])
def simplify_analyze():
    # ... existing validation ...
    task_id = str(uuid.uuid4())
    _simplify_tasks[task_id] = {
        'status': 'processing', 'progress': 0.0,
        'message': 'Starting...', 'eta_seconds': None, 'result': None
    }
    
    def run_simplification():
        try:
            # Pass a progress callback to the simplifier
            def on_progress(pct, msg, eta):
                _simplify_tasks[task_id].update(
                    progress=pct, message=msg, eta_seconds=eta
                )
            result = simplifier.simplify_to_grade(
                text, target_grade, mode, progress_callback=on_progress
            )
            _simplify_tasks[task_id].update(status='complete', progress=1.0, result=result)
        except Exception as e:
            _simplify_tasks[task_id].update(status='error', error=str(e))
    
    thread = threading.Thread(target=run_simplification)
    thread.start()
    return jsonify({'task_id': task_id}), 202

@app.route('/simplify/progress/<task_id>', methods=['GET'])
def simplify_progress(task_id):
    task = _simplify_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Unknown task'}), 404
    if task['status'] == 'complete':
        result = task['result']
        del _simplify_tasks[task_id]  # cleanup
        return jsonify({**result, 'status': 'complete'})
    return jsonify({
        'status': task['status'],
        'progress': task['progress'],
        'message': task['message'],
        'eta_seconds': task['eta_seconds'],
    })
```

### Simplifier Integration

Add optional `progress_callback` param to `simplify_to_grade()` and `_paragraph_pipeline()`. In the paragraph pipeline, call it after each paragraph:

```python
if progress_callback:
    pct = (i + 1) / len(groups)
    eta = avg_time_per_para * (len(groups) - i - 1)
    progress_callback(pct * 0.85, f'Rewriting paragraph {i+1} of {len(groups)}...', eta)
```

Reserve 0.85-1.0 for the whole-doc check and diff generation phase.

For the existing whole-document pipeline (short texts), call progress with coarser milestones:
- 0.0: "Analyzing text..."
- 0.3: "Generating candidates..."
- 0.7: "Optimizing grade level..."
- 0.9: "Generating changes..."

### Backend (`simplifyController.ts` + `simplifyRoutes.ts`)

Add two new routes:
- `POST /api/simplify/analyze-async` — calls ML service `/simplify/analyze`, returns `{task_id}`
- `GET /api/simplify/progress/:taskId` — proxies to ML service `/simplify/progress/<taskId>`

### Frontend (`SimplifyPage.tsx`)

Replace the single API call with:
1. Call `simplifyApi.analyzeAsync(data)` -> get `task_id`
2. Start polling `simplifyApi.progress(taskId)` every 2 seconds
3. Render a progress bar component:
   - Percentage bar (0-100%)
   - Message text ("Rewriting paragraph 3 of 6...")
   - ETA countdown ("~15 seconds remaining")
4. On `status === 'complete'`, stop polling, process result as before

### Frontend Progress Bar Component

Replace the current `LoadingSpinner` fullscreen overlay in SimplifyPage with a progress panel:
- Centered card with progress bar (Tailwind: `bg-blue-500 h-2 rounded-full` with animated width)
- Message text below the bar
- ETA in lighter text
- Keep the dimmed background overlay for focus

## Key Design Decisions

1. **Glossary is advisory, not mandatory.** The LLM prompt includes it but may deviate if context demands. Cross-paragraph consistency is a goal, not a hard gate.

2. **Per-paragraph scores are sanity checks, not precision instruments.** Paragraphs under 80 words are too short for reliable ML scoring. The whole-document check is the real gate.

3. **Repair targets the worst paragraph only.** After the whole-doc check misses, re-prompt only the paragraph with the largest `_distance_to_target_band()`. This is 90% of the value at 10% of the complexity of a full paragraph-level repair loop.

4. **Fallback to existing pipeline.** If paragraph pipeline returns `None` (failed or `distance > 2.0`), the existing whole-document pipeline runs. No regression possible.

5. **No greedy loop on individual paragraphs.** The existing greedy optimization (line 944) still runs on the assembled output, but operates on the diff changes, not on re-measuring full paragraphs. This is fast because the assembled text is already close to target.

## Expected Performance

| Metric | Current | Paragraph-first |
|--------|---------|-----------------|
| LLM calls (4-para, medium gap) | 3-6 on full doc | 4-6 on paragraphs (smaller prompts) |
| `_measure_text_metrics` calls | ~40 (greedy loop) | ~8-10 (per-para + 1-3 doc checks) |
| Datamuse HTTP calls | 50+ sequential | 0 (LLM handles vocabulary) |
| Rule candidate stages | 3 full-doc passes | 0 (LLM-first, rule-correct after) |
| Wall time (500 word text) | 3-8 min | ~30-90 sec |

## Implementation Order

### Day 0 (today): Model migration
1. Evaluate `gpt-oss-120b` vs alternatives (check Fireworks pricing page, latency docs)
2. Swap `FIREWORKS_MODEL` in all 4 files
3. Test: run 3 simplification scenarios, verify grade accuracy, check latency

### Day 1-2: Core paragraph pipeline
4. Add `_should_use_paragraph_pipeline()` and `_split_into_rewrite_groups()` — pure functions, test in isolation
5. Add `_build_paragraph_prompt()` — adapt existing prompt templates
6. Add `_rewrite_single_paragraph()` — wrap `_llm_chat()` + `_rule_correct()`
7. Add `_build_paragraph_glossary()` — diff first paragraph to extract word map
8. Add `_assemble_paragraphs()` — join with paragraph break restoration
9. Add `_paragraph_pipeline()` orchestrator — wire everything, whole-doc check, worst-paragraph repair
10. Modify `simplify_to_grade()` routing — gate on text length, try paragraph pipeline, fall through on failure

### Day 3: Progress indicator (polling)
11. ML service: add `_simplify_tasks` dict, async `/simplify/analyze` with threading, `/simplify/progress/<task_id>` endpoint
12. Add `progress_callback` param to `simplify_to_grade()` and `_paragraph_pipeline()`
13. Backend: add `POST /api/simplify/analyze-async` and `GET /api/simplify/progress/:taskId` routes
14. Frontend: replace `LoadingSpinner` with progress bar, polling loop in `SimplifyPage.tsx`
15. Add `simplifyApi.analyzeAsync()` and `simplifyApi.progress()` to `api.ts`

### Day 4: Integration + test suite
16. Run existing golden tests — verify API contract preserved
17. Test through frontend UI — both auto and interactive modes
18. Fix edge cases (single-paragraph fallback, budget exhaustion, empty paragraphs)
19. Verify progress bar renders correctly, ETA is reasonable

### Day 5: Prompt tuning + performance
20. Test grade accuracy across grade 3-12 targets on 400-600 word texts
21. Tune paragraph prompt (sentence count formula, glossary format)
22. Measure wall-clock improvement
23. Adjust repair threshold if needed

### Day 6: Demo tuning + polish
24. Test with thesis-defense demo texts
25. Handle edge cases found during demo (very long paragraphs, bullet lists, etc.)
26. Add logging for paragraph pipeline (`[para-pipeline] group {i}: grade={g:.1f}`)

### Day 7: Regression + buffer
27. Full regression test: short texts still use whole-doc pipeline
28. Verify interactive mode works (changes panel, accept/deny)
29. Buffer for thesis prep

## Verification

1. **API contract**: Run existing test suite — return shape must be identical
2. **Grade accuracy**: Test 5 texts (400+ words) at targets grade 5, 8, 10, 12, College. All must hit within `_distance_to_target_band() == 0`
3. **Performance**: Time comparison on a 500-word, 4-paragraph text. Target: 50%+ reduction
4. **Frontend**: Load SimplifyPage, run auto mode on a long text, verify changes panel renders correctly with word/sentence-level changes
5. **Interactive mode**: Verify accept/deny works, preview updates correctly
6. **Short text fallback**: Submit a 200-word text, confirm it uses the existing pipeline (check logs for absence of `[para-pipeline]` messages)
7. **Repair rounds**: Submit a text where paragraph 1 is very different difficulty from paragraph 3. Verify the pipeline identifies and repairs the outlier
8. **Progress indicator**: Start a long-text simplification, verify progress bar shows real paragraph-by-paragraph updates with ETA. Verify it transitions to results cleanly on completion.
9. **Model migration**: After swapping the Fireworks model, run the same 5 grade-accuracy tests. No regression in target_distance.
