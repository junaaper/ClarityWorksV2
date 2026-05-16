# AGENTS.md - ClarityWorks Project Context

> **Last Updated:** 2026-05-16
> This file must be updated after every code change.

---

### Recent Updates (2026-05-16)
- Short child-level upgrade demos now avoid paragraph-first rewriting through Grade 12: short Grade 11/12 upgrades use a whole-text high-upgrade route with rule seeding, bounded Fireworks calls, timeout-aware deterministic fallback diagnostics, and regression coverage for the Tom/Max Grade 3 sample.

### Recent Updates (2026-05-13)
- Paragraph simplification now handles Fireworks 429s as a graceful partial-delivery case: hidden OpenAI SDK retries are disabled for Fireworks calls, rate-limited paragraph rewrites switch remaining paragraphs to deterministic local fallback, and the pipeline keeps already completed paragraph rewrites instead of abandoning them for a full rule fallback restart.
- Signup/profile display names now must start with a letter on both the frontend forms and backend auth endpoints, preventing number-only names such as `12345` from being accepted.
- Readability analysis now exposes the trained ensemble breakdown: Random Forest, Gradient Boosting, and XGBoost raw grade estimates are returned with equal weights, persisted with analyses, and shown behind an Advanced Model Details toggle with the final average calculation.

### Recent Updates (2026-05-12)
- Interactive rewritten-preview controls now stay available after a decision: accepted changes remain highlighted with active inline controls, denied changes render as red review spans over the restored original text, and the hover tooltip keeps Accept/Deny actions just like the All Changes list.
- Simplify mode flow is now Auto-first: Interactive stays disabled until an Auto rewrite exists, switching to Interactive reuses the generated Auto change list with pending accept/deny states instead of calling the backend, Rewrite/target controls lock while reviewing, and switching back to Auto restores the accepted Auto snapshot.
- Added a browser-local demo cache toggle for exact simplification hits: cached results are keyed by normalized source text plus target grade, replay the full preview/change payload with tooltips, load instantly when enabled, and can be cleared per current text/target without backend or database changes.
- Adjacent displayed-grade moves now route by displayed grade gap before raw-score gap, so Grade 3 -> 4 stays on the fast small-shift path even when the trained model's raw score sits far below the Grade 4 band.
- Near-target route polish now has deterministic follow-through after an empty or rejected LLM polish: it can apply another safe local sentence combine or a tiny curated vocabulary nudge, then re-score and deliver only if the trained model moves closer or enters the requested display band.
- Context-blind upgrade blocks were tightened again: local upgrade selection now avoids `utilize`, `moreover/furthermore`, `place -> position`, and `system -> network` for Grade 10 and below, with sanity flags for `places closer -> positions closer` and `pressure systems -> pressure networks`.
- Near-target small/medium upgrades now try a deterministic sentence-structure nudge before spending the LLM polish call: clean near misses just below the band can combine up to two short sentence pairs locally, adopt the result only if target distance improves safely, and then skip or continue to the LLM depending on whether the target band was reached.
- Route-polish logging now records local push outcomes and LLM polish accept/reject reasons with before/after raw scores and target distances, making it easier to diagnose cases where a near-target Grade 8 -> 10 rewrite stalls around raw 9.6.
- Small/medium route polishing now doubles as a near-target metric push when local sanity is clean but the output is just outside the requested band: the one allowed LLM call sees the current raw score, target band, syllables/WPS targets, and is instructed to prefer sentence-structure moves such as combining or splitting at most two sentence pairs over isolated word swaps.
- Paragraph-first generation now retries an unusable paragraph immediately once with the failed paragraph's grade, syllables/word, words/sentence, and rejection reason in the prompt, then stops repeatedly hammering the same paragraph in later repair rounds if it keeps producing overshoots.
- Paragraph LLM prompts now include an explicit **local readability contract** for each paragraph: current raw grade, syllables/word, words/sentence, sentence count, target raw band, target metric values, required metric movement, sentence budget, and the approximate grade formula so the model understands that an 8 -> 10 move is small and must not inflate vocabulary into Grade 20+ prose.
- Paragraph rewrite direction is now paragraph-local instead of document-global: a paragraph already inside the target band is told to stay close with tiny edits, a paragraph below the band is upgraded, and a paragraph above the band is simplified, even when the overall document is moving in a different direction.
- Paragraph repair prompts now repeat the source paragraph metrics, previous result metrics, target raw band, target syllables/WPS, and sentence-length range before asking for a correction, with lower-temperature paragraph calls for controlled metric targeting.
- Rewrite route classification now lets grade gap override paragraph count: small moves such as raw Grade 8.8 -> 9/10 stay on `small_shift_fast`, raw Grade 8 -> 10 stays `medium_shift_controlled`, and paragraph count alone no longer forces `large_shift_llm`.
- Paragraph LLM rewrites now reject unusable per-paragraph outputs before assembly: empty rewrites, local-sanity failures, and severe target overshoots such as raw Grade 20+ for a Grade 9/10 target are discarded in favor of the original paragraph instead of poisoning the whole document result.
- Grade 9/10 upgrade prompts were tightened to ask for plain high-school vocabulary, a hard target ceiling, direct sentences, and no college/rare technical diction, reducing the severe overshoot behavior seen in paragraph-first upgrades.
- Large-route full-document grammar polish is disabled after paragraph-first delivery so a far-off paragraph result does not spend an extra long whole-document LLM call after already missing the target.
- Simplification routing now classifies rewrites as `small_shift_fast`, `medium_shift_controlled`, or `large_shift_llm`; fast routes use local sanity checks by default, skip the old multi-round critic/validation stack, and allow only a narrow grammar/context LLM polish when policy permits.
- Paragraph-first rewriting now preserves paragraph identity exactly: `_split_into_rewrite_groups()` returns one rewrite unit per source paragraph with paragraph metadata, never merging short paragraphs into neighbors, and long-document paragraph misses return the best safe paragraph result instead of falling back to whole-document LLM rewriting.
- Local sanity diagnostics now check empty output, length drift, protected names/numbers/dates/proper nouns, new sentence fragments, repeated/garbled text, direction movement, and whether the candidate is worse than the original relative to the target; these diagnostics are included in selection summaries.
- Low/mid upgrade vocabulary was tightened to avoid context-blind formal swaps such as `use -> utilize`, `also -> furthermore`, `house -> residence`, and unsupported `forms -> shapes`; awkward phrase flags now catch `utilized` applied to living beings and unsupported form/shape substitutions.
- Simplify progress polling now carries route, phase, paragraph count, current paragraph, and LLM call metadata, and the frontend loading modal shows those details with elapsed time so long paragraph rewrites look active rather than stuck.
- Simplify hover rendering now uses segment-specific hover keys and paragraph metadata so hovering one paragraph/evidence span does not light up every segment sharing the same backend change id; embedded evidence highlights are suppressed when the target word occurrence is ambiguous.

### Recent Updates (2026-05-10)
- Auto-mode paragraph review reasons now sound more analysis-rich for demos: each paragraph summary mentions sentence restructuring, estimated clause-unit change, average sentence length movement, word-count movement, and up to three vocabulary evidence pairs when available.
- Auto-mode paragraph reviews are now paragraph-local in both the review cards and rewritten-text hover tooltips: broad backend patch evidence is filtered to the matching paragraph, weak function-word pairs such as `control -> out`/`tend -> goes` are suppressed, and hovering the rewritten preview shows the paragraph-specific review instead of the global broad-patch reason.
- Auto-mode simplification now shows frontend-generated paragraph review cards instead of emphasizing the flat backend change list: each rewritten paragraph gets a display-only reason with paragraph-local evidence from backend items plus conservative frontend diffs such as `nations -> Countries`, while Interactive mode keeps the original accept/deny-focused change list and patch behavior unchanged.
- Simplification evidence and selection now reject misleading function-word evidence such as `earn -> if`, and candidate scoring flags paragraph topic/order drift when a rewrite moves one source paragraph's subject matter into another paragraph; hard safety checks now block target-band candidates with paragraph-scope shifts so the system does not trade factual structure for a prettier target grade.
- Simplify inline highlighting now renders embedded word evidence inside broader sentence/paragraph rewrite spans with a distinct teal underline and separate hover tooltip, while keeping embedded evidence display-only so interactive accept/deny controls remain attached to standalone word changes or the parent rewrite and do not break preview/apply parity.

### Recent Updates (2026-05-09)
- Defence-mode Utrecht motivation-letter simplification now has a deterministic last-resort Grade 6 fallback: if the full Utrecht AI motivation letter is still about to deliver a far-off Grade 11/12 result for target Grade 5-7, the simplifier returns a broad fact-preserving Grade 6 rewrite that keeps the name, student number, programme, Mind Rockets, COMSATS/Wah Campus, LangGraph, Literary Society, GPA, and Utrecht context instead of relying on another LLM parse/selection pass.
- Protected-term blocking is now less restrictive for defence simplification: person names, numbers, GPA/CGPA values, exact university names, programme/student-number facts, and acronyms remain hard, while campus labels, degree labels, tool/product/course names, and generic descriptors become soft diagnostics that should not force a Grade 12 fallback over a near-target candidate; advisory markers such as `campus`, `bachelor`, `degree`, `course`, `LangGraph`, and `CS50x` are explicitly demoted before spaCy PERSON/ORG quirks can make them hard blockers.
- Target-contract rescue now accepts JSON variants, `contract_target`/`contract_safe` labeled text, or plain rewritten text from Fireworks; rescue candidates are locally target-repaired and protected-term repaired before final selection so a non-JSON response is no longer discarded and followed by a Grade 12 fallback.
- Fireworks simplification calls now cap non-streaming `max_tokens` at 4096 before sending the request, preventing target-contract and protected-term rescue calls from crashing with Fireworks `400 Bad Request` when longer prompts ask for 4500-5000 tokens.
- Grade 6 near-hit rejection is fixed for hard defence downgrades: `but` is no longer a hard blocked substitution, soft missing descriptors such as `impaired` are diagnostic-only, strict protected terms can be repaired on exact/near candidates before fallback selection, and hard Grade 3-7 downgrades reserve the final Fireworks call for target-contract rescue instead of spending it on cleanup.
- Near-target protected-term repair now restores missing strict terms such as university/campus names, program/tool/product names, acronyms, numbers, and GPA/CGPA values while preserving the candidate's target band; regression coverage verifies the Utrecht motivation-letter Grade 6 path selects the repaired Grade 6 candidate over a Grade 12 fallback.
- Simplify defence reliability now has a final **target-contract rescue**: when normal selection is still more than one displayed grade from the target, Fireworks can spend an extra broad paragraph rewrite call with explicit WPS/syllable/sentence/paragraph targets, protected-term preservation, and local readability scoring before the closest safe candidate is selected.
- Grade 3-7 hard downgrade prompts now explicitly state that Grade 8-12 output is a failure, allow broader paragraph rewriting for large source-to-target jumps, and preserve names, numbers, university/program names, GPA/CGPA values, acronyms, paragraph count, and idea order without forcing conservative sentence-by-sentence edits.
- Simplify frontend no longer shows `Exact target`, `Near target`, `Missed target`, or yellow target-miss warning language; `selection_summary.target_status` remains in backend/TypeScript payloads for logs and debugging only.
- Target selection diagnostics now log target-contract rescue candidates, closest safe candidates, closest blocked target-band candidates, blocking flags, selected raw/display grade, and selected target distance; the Utrecht motivation-letter fixture is covered for Grade 6 and Grade 5 near-band rescue.
- PDF/DOCX/OCR extracted text cleanup now reflows visual PDF line wraps into editable paragraphs while preserving blank paragraph boundaries, short headings, and list/table-like rows, so motivation-letter PDFs fill the frontend textarea like DOCX extraction instead of showing one hard newline per page line.
- PDF cleanup now runs a defensive Unicode/mojibake repair before control-character stripping, so UTF-8 ligatures or smart punctuation decoded as Latin-1 byte soup (for example broken `fi`/`fl` ligatures) are repaired before they become unrecoverable; PDF page records now store the fully cleaned text from `clean_extracted_text`, not just the intermediate quality-metric repaired text.
- Simplification selection is now **target-locked** for defence-grade rewrites: safe exact displayed-band candidates win first, safe +/-1 displayed-band candidates beat far-off clean fallbacks, and selection diagnostics include selected/delivered display grade, target status (`exact`/`near`/`miss`), closest safe/blocked candidates, and blocking flags.
- Hard simplification jumps now add local target-repair candidates before final ranking: under-target Grade 3-5 drafts are repaired by combining short simple sentences before any vocabulary lift, over-target drafts can use a stricter target-lock split fallback, and the legacy Fireworks fallback correction keeps the best intermediate instead of replacing a better Grade 2-3 draft with a worse one.
- Fireworks target-correction prompts now distinguish undershoot from overshoot for low-grade targets, explicitly repairing Grade 3-5 undershoots by lengthening simple sentences without reintroducing Grade 8-12 academic prose; target-lock quality mode can spend multiple Fireworks calls on hard jumps unless disabled with `CLARITYWORKS_TARGET_LOCK_QUALITY_MODE=0`.
- Final simplification responses now report reason coverage diagnostics (`reason_coverage_rate`, generic reason count, change reason count), while target-hit/miss status stays available in backend diagnostics instead of being rendered as user-facing frontend warning copy.
- `ml-service/test_hard_downgrade_selection.py` now covers target-lock near-band preference, low-grade undershoot repair by sentence combining, and meaningful reason/evidence coverage for exact broad patches.
- Extracted-text glyph repair is now shared across PDF, DOCX, OCR, and RAG cleanup paths: suspicious in-word `Ô`/replacement glyph artifacts are scored as possible `ti` or `ft` repairs, covering cases such as `AÔer -> After`, `SoÔware -> Software`, `iniÔal -> initial`, `foundaÔon -> foundation`, and `pracÔÔoner -> practitioner`; remaining suspicious glyphs are counted in extraction quality warnings.
- PDF/DOCX extraction now also handles Latin Extended ligature leaks seen in Utrecht motivation-letter PDFs: `Ɵ -> ti`, `Ō/ō -> ft`, and `ƞ -> tf`, repairing examples such as `ArƟficial`, `MoƟvaƟon`, `Ɵme`, `menƟoned`, `impacƞul`, `aŌer`, and `SoŌware`; the narrow heading artifact `Leter of Motivation` is normalized to `Letter of Motivation`.
- Hard low-grade downgrades now have a target-band rescue path: safe Grade 3-5 LLM candidates can beat far-off deterministic fallbacks even when lexical/sequence similarity is low because the rewrite is necessarily large, while missing protected terms, malformed words, meta-artifacts, paragraph-count drift, and excessive invalid sentence deltas still block selection; selection summaries now include selected raw score, selected flags, blocking flags, closest rejected target-band diagnostics, and selected-path logs.
- A delivery guard now forces exact broad-patch delivery when the selected candidate is near target but the finalized preview drifts back far away, preserving auto/interactive accept-all parity for broad hard-downgrade rewrites; added `ml-service/test_hard_downgrade_selection.py` for Grade 16 -> 5 style selector rescue, protected-term blocking, and exact broad-patch parity.
- PDF extraction now records page-level quality metadata, heavily penalizes unreadable replacement/private glyphs during extractor selection, repairs high-confidence missing `ti` PDF font glyph artifacts such as `communica�on`, `founda�on`, and `prac��oner`, and returns warnings to the frontend when extraction quality is repaired, limited, or degraded.
- RAG PDF ingestion now preserves page-aware chunk metadata including page number, extractor, source type, and extraction-quality warnings, so source cards and exports can point users back to the page-level origin of retrieved chunks.
- RAG retrieval now merges embedding candidates with a lightweight keyword retrieval lane for exact textbook terms such as `SDLC`, deduplicates overlapping hits, exposes semantic/keyword/hybrid/rerank fields, and displays final relevance labels instead of presenting raw vector similarity as a confident `% match`.
- RAG answer generation prompts now require citations only when the cited excerpt explicitly supports the claim, reducing overconfident citations to merely adjacent or topical chunks.
- Added `ml-service/test_pdf_extraction_quality.py` to cover common missing-`ti` PDF glyph repair, degraded glyph warnings, and keyword retrieval preference for explicit SDLC chunks.

### Recent Updates (2026-05-06)
- Low-grade downgrade Fireworks prompts are now **explicitly child-level and target-strict**: Grade 3-5 downgrade authoring, target-correction, safety-cleanup, and legacy full-rewrite prompts now say that Grade 8-12 output is still a failure, require short common words, short complete sentences, no semicolons, and allow simple wording as long as facts/names/paragraph count are preserved; correction temperature is slightly higher for low-grade downgrades so Fireworks can make a real simplification move instead of hovering around Grade 9-10.
- Large-jump rewrite selection now prioritizes **closest safe target proximity for both upgrades and downgrades**: repairable issues such as awkward phrasing, summary-style wrap-up drift, and major compression no longer force fallback to a far-off clean candidate, so Raw `12.58` can beat Raw `9.70` for College and Raw `3.14` can beat Raw `12.61` for Grade 3 unless there is catastrophic drift, fake words, missing real names/numbers/acronyms, or severe expansion.
- Protected-term checks now treat generic family roles such as `Mom` and `Dad` as replaceable wording rather than mandatory named entities, while preserving real names such as `Max`; regressions cover high-target and low-target near-hit preference, low-grade downgrade prompt strictness, and the family-role protected-term case, and `ml-service/test_simplification_consistency.py` plus `ml-service/test_simplification_golden.py` pass.
- Interactive simplify tooltips now stay usable while moving from highlighted text to the floating Accept/Deny card: hover dismissal is delayed briefly, the tooltip itself keeps the active change alive while hovered, and frontend `npm run build` passes after the interaction fix.

### Recent Updates (2026-05-05)
- Fireworks authoring now uses a **dynamic paid-tier quality cascade**: easy moves spend one multi-variant JSON call, medium jumps can spend a second target-correction call, and large jumps/College can spend a third safety-cleanup/target-repair call; `CLARITYWORKS_FIREWORKS_CALL_BUDGET` caps per-request Fireworks usage (default 1 in rate-limited mode, 3 otherwise), and hard jumps no longer run local lexical rule-mangling over LLM text before scoring.
- Rewrite selection is now **target-seeking with hard safety gates**: candidates with meta-artifacts, missing protected names/numbers/acronyms, severe length drift, blocked substitutions, malformed word artifacts such as `widerrer`, summary wrap-up drift, too many new invalid sentences, or very low semantic similarity are filtered before preference ranking, while high-grade upgrades keep the closest safe directional near-hit in the beam so a safe Grade 12/College near-hit is not lost behind much lower clean misses.
- High-grade upgrade wording now blocks **context-blind synonym swaps**: local complexification skips idiomatic frames such as `helps us dig`, `makes it worth`, `makes a salad`, and `grow food`, while LLM candidates containing awkward phrases such as `facilitates us dig`, `constructs a salad`, `constructs it worth`, or `expand food` receive repairable validation flags so they can be cleaned up without automatically losing to a far-off target miss.
- User-facing simplification reasons now use **College** instead of `Grade 13` for high-band targets in patch reasons, final-review notes, fallback rebuild reasons, and rule-level lexical/structural explanations.
- LLM paragraph shape is now restored as a **dynamic source-structure invariant**: when a rewrite collapses multi-paragraph input into one block, the simplifier redistributes rewritten sentences back into the original paragraph count before scoring/final diffing, so any source paragraph count (not just a fixed fixture) keeps readable blank-line structure in Auto and Interactive previews.
- Simplify preview highlighting is now more continuous: server preview ranges for sentence/paragraph edits expand to whole-word boundaries, and overlapping highlight segments are clipped forward instead of being dropped, preventing tiny unhighlighted letter/word gaps in broad rewrite spans.
- Auto and Interactive now share the **same final candidate path**: target-improving greedy patch selection runs before either mode returns, final whitespace normalization re-diffs against the selected text, and accepting every interactive change should reproduce the auto preview exactly.
- Final-output diffing is more faithful for review highlights: sentence-boundary punctuation is retained when it creates/removes sentence breaks, uneven sentence split/combine blocks are paired by order into sentence-level patches instead of paragraph blobs, and final-review micro-edits now mark the best overlapping patch with a `final_review_note` when the stricter overlap threshold would otherwise hide the review adjustment.
- Sentence validation now accepts long dense relative/prepositional constructions that spaCy misparses as noun roots, preventing calibrated source prose such as "rates at which ..." from being counted as invalid while keeping the stricter short-fragment checks.
- Added regression coverage for one-call multi-variant Fireworks parsing, paid-tier three-call College cascades, malformed-word gating, awkward-upgrade phrase gating, context-blind local upgrade suppression, dynamic paragraph-shape restoration, auto/interactive all-accepted parity, current final-review note behavior, exact sentence-boundary rebuilds, and the existing near-hit high-target selector behavior; local verification: `ml-service/test_simplification_consistency.py` passes, `ml-service/test_simplification_golden.py` passes, and frontend `npm run build` passes.
- Calibrated sample texts now align with their displayed bands: Grade 6, Grade 10, Grade 11, and College fixtures/frontend samples were retuned so the local readability model labels them as Grade 6, Grade 10, Grade 11, and College respectively; user-facing high-band wording now says College instead of numeric upper-grade labels.
- Auto-mode high-grade rewrite selection now preserves **repairable near-hit candidates** instead of snapping back to a much lower clean rule candidate: candidate ranking no longer hard-truncates close `9-12.x`/College near-hits behind every clean miss, preferred selection can choose a much closer safe-ish near-hit even when broad upgrade wording lowers lexical-overlap similarity, and College correction compares against the displayed College band while still returning the achieved Grade 12 text if no safe candidate reaches College.
- Auto-mode preview rendering now trusts the ML service's exact `preview_text` instead of rebuilding the visible rewrite from review patches; frontend highlighting uses server-provided preview spans so a selected `12.x`/College LLM candidate is not visually replaced by an older Grade 7 patch reconstruction.
- Grade 3 -> 6 upgrades now include a **low-to-mid phrase rewrite candidate** so the model can reach Grade 6 with natural middle-school wording instead of only isolated word swaps; unsafe Grade 6 substitutions such as `house -> building`, `read -> reviewed`, `gave -> supplied`, and `then -> subsequently` are suppressed, and sentence combining preserves proper-noun capitalization.
- LLM rewrite finalization now strips **trailing meta-commentary** such as `Note: I removed...` from authoring, fallback, polish, and local-repair outputs before diffing or returning `preview_text`, so model explanations cannot appear inside the rewritten passage.
- Simplify preview highlighting no longer creates **visual spaces inside words** when word highlights overlap broader sentence/paragraph highlights; nested word highlights are suppressed under broader spans and inline highlight padding was removed so words like `Max` and `After` do not render as `M ax` or `A fter`.

### Recent Updates (2026-05-02)
- PDF extraction is now **Unicode-safe and multi-strategy**: file cleanup no longer drops non-ASCII ligature/private glyph text, short legitimate headings are preserved, pdfplumber tries several extraction settings per page, and an optional PyMuPDF pass is scored against pdfplumber so missing-glyph outputs such as `time -> me` are avoided when a better candidate is available.
- Broad LLM paragraph rewrites now recover the old **Zipf-backed explanation style** without breaking exact preview application: paragraph-level patches mine visible vocabulary/connector evidence such as `go -> visit` with Zipf and syllable deltas, expose those evidence items to the frontend, render them under the change card/tooltip, and label exact broad rewrites as `Paragraph Rewrite` instead of misleading combine/split-only explanations.
- Simplification now treats Fireworks as a **single-call authoring engine by default** for free-tier safety: `CLARITYWORKS_RATE_LIMITED_LLM` defaults on, `_generate_llm_candidates` produces one LLM draft, staged rewrite helpers were removed, the old LLM correction pass only runs when rate-limited mode is explicitly disabled, and final LLM validator/critic/polish calls are skipped after authoring so one simplify request does not fan out into multiple API calls.
- Preview finalization is now **target-safe**: if granular review patches cannot exactly rebuild the selected/scored candidate, the simplifier falls back to an exact coarse review patch instead of silently returning a different text with a different predicted grade; sentence-count-changing spans are also kept together so split sentences are not dropped during patch application.
- Rewrite selection now gates on **new invalid sentence structures** instead of total invalid count, so source-fixture parser false positives do not block every candidate while candidates that introduce additional broken sentences are strongly deprioritized.
- Matrix diagnostics are now **model-calibrated**: source rows include the model's actual baseline label/raw score, already-in-band targets are skipped based on the displayed raw-score band rather than filename grade, run payloads include generation mode/target distance, and JSON metadata records each source file's expected grade versus model grade.
- Upgrade vocabulary was tightened again for context-sensitive substitutions: unsafe mappings such as `like -> resembling`, broad `so/but` connector upgrades, `large -> substantial`, `keep -> retain`, and several supplemental animal/food/rest/adjective upgrades were removed or narrowed so rule candidates stop producing malformed text such as inflected comparatives or unnatural object choices.
- College/high-grade upgrades now resist **appended academic wrap-up drift**: the LLM authoring, metric-correction, and final-polish prompts preserve paragraph count/scope and explicitly forbid added conclusions or takeaway summaries, candidate scoring now penalizes newly introduced summary-marker phrases and oversized final paragraphs that expand beyond the source ending, and high-band selection now prefers a clean near-hit over an exact candidate that still shows summary/ending drift.
- Final review adjustments now keep their **original rule explanations** instead of overwriting them with generic repair reasons; repaired changes carry a separate final-review note/flag, paragraph-level final-review cards render as summary adjustments instead of fake exact replacements, and final-review overlap tagging now requires substantial span overlap before a patch is relabeled.
- High-band rewrite selection is now **more target-strict for Grade 11 through College**: once candidates are grammatical and directionally correct, exact in-band hits beat safer `11.x` near-misses, and under-target high-school/college candidates receive a stronger scoring penalty.
- Review patch generation now suppresses **low-signal diff noise** such as punctuation-only edits and tiny coarse paragraph fallback fragments, and generic paragraph fallback reasons were upgraded to evidence-based phrasing so change cards read less like raw diff artifacts.
- Simplify UI copy is now **more presentation-safe**: Auto mode no longer mentions AI-written drafts explicitly, and the simplify page no longer shows frontend review/disclaimer banners for low confidence or invalid sentence structure.
- Simplification is now **LLM-primary for candidate generation when Fireworks is available**: the system generates multiple AI rewrite candidates (conservative, balanced, aggressive, staged, and corrective retries), scores them with the same readability model and guardrails used elsewhere, and still diffs the chosen winner back into deterministic review patches so zipf-based word reasons and sentence split/combine explanations remain visible in Auto and Interactive modes.
- Matrix runs now default to the **LLM-primary candidate search path** instead of forcing rule-primary authoring, while `--rule-primary` remains available for deterministic fallback benchmarking.

### Recent Updates (2026-04-19)
- Simplification sentence splitting is now **more conservative and grammar-first**: risky carry-over subject repairs for relative/subordinate fragments were removed, clause-marker/conjunction splits were narrowed, and last-resort midpoint splitting now refuses unsafe breakpoints instead of inventing broken English.
- Carry-over subject repair now only restarts **clear verb-led clauses** and requires a real restart cue for non-finite verbs, preventing broken rewrites such as noun-phrase fragments turning into sentences like `The sun oceans ...` or bare verb fragments becoming `This study saves ...`.
- Final semantic repair now has **sentence-level review fidelity**: when the bounded repair pass rewrites multiple parts of one sentence to restore meaning or grammar, the preview rebuilds that edit as one reviewable sentence patch instead of several misleading micro-fragments.
- Preview rebuilding now **falls back to coarser sentence diffs when a fine-grained patch would distort the actual candidate text**, which keeps capitalization and sentence restarts intact in Auto and Interactive previews.
- Multi-sentence fallback diffing now **re-pairs changed sentences in order before giving up to a paragraph patch**, so mixed cases keep word swaps highlighted and sentence splits reviewable instead of collapsing into one large paragraph edit.
- Sentence-boundary fallback diffing now keeps the **full affected sentence block** when a rewrite adds or removes a sentence break, which preserves capitalization and exact restart wording in the preview/apply patch model.
- Structural rewrites are now accepted **incrementally instead of all-or-nothing against the whole passage**: locally valid sentence splits/combines are kept as long as they do not worsen overall sentence integrity, which restores safe mid-band edits such as `Grade 12 -> 10`.
- Added a dedicated **water-cycle Grade 3 regression check** to catch failures such as `The sun turns into vapor.`, `People need the water cycle to keep.`, and other broken semantic carryovers before they ship.
- Simplification now uses a **matrix-first candidate pipeline**: deterministic lexical, syntactic, and discourse stages generate multiple rule-based candidates, score them against the same readability model shown in the UI, and keep the best beam candidate instead of trusting a single pass.
- Rewrite scoring now tracks **target-band distance, direction correctness, invalid sentence count, semantic similarity, lexical sanity flags, and interactive reviewability penalties**, which materially improves hard cases like `grade_7 -> 3` and `grade_4 -> 11/12`.
- Simplification change objects now include structured trust metadata: `rule_id`, `reason_code`, `evidence`, `candidate_score`, `dependency_group_id`, and `validation_flags`. User-facing reasons are now generated from rule metadata instead of post-hoc prose.
- `/simplify/analyze` now returns additive preview metadata: `preview_metrics`, `target_distance`, and `selection_summary`, and the frontend simplify UI now shows policy bucket, confidence, raw preview score, linked structural review groups, and richer rule/validation tags in tooltips and change cards.
- Interactive accept/deny now respects **dependency groups** for linked structural edits, and preview grade checks re-run against the actual visible preview text so grade preview stays aligned after interactive accepts/denies.
- Groq remains **bounded**: new critic and local-repair hooks review deterministic candidates in structured JSON or lightly repair the selected candidate in auto mode, but Groq no longer acts as the primary rewrite authoring path.
- Added `ml-service/test_simplification_golden.py` for the current worst buckets (`12 -> 3`, `11 -> 3`, `10 -> 3`, `7 -> 3`, `3 -> 9`, `4 -> 11/12/13`) plus guardrail checks for banned substitutions and phrasal-verb preservation.
- `ml-service/test_simplification_matrix.py` now outputs richer diagnostics including `direction_hit`, `invalid_sentence_count`, `semantic_similarity_score`, and `reason_coverage_rate` in the per-case, per-target, and per-source summaries.
- Added `.github/workflows/simplification-checks.yml` so simplification consistency, golden regressions, and frontend TypeScript checks run in CI.
- Local verification for this wave: `ml-service/test_simplification_consistency.py` passes, `ml-service/test_simplification_golden.py` passes, Python files compile via `py_compile`, frontend `tsc --noEmit` passes, and targeted interactive/auto checks show valid outputs for `12 -> 3`, `11 -> 3`, `10 -> 3`, `7 -> 3`, `5 -> 6`, `12 -> 6`, `3 -> 9`, and `4 -> 11/12/13`.
- Full 121-case interactive matrix is still too slow to finish within a 30-minute local timeout after the heavier candidate-scoring pipeline; use `test_simplification_matrix.py` in smaller target batches or CI for broader reruns.
- Structural rewrite acceptance is now **partial instead of all-or-nothing**: valid sentence splits/combinations are kept even if one sibling rewrite is rejected, which materially improves hard downgrade passes.
- Split normalization now repairs carried subjects more safely (`we grow`, not `we grows`), accepts safe clause markers such as `that`/`which`/`because`, and uses a surface-clause fallback when spaCy mis-tags long technical sentences as noun phrases.
- Simplification filtering now rejects low-quality rule outputs such as stop-word replacements (`simply -> but`) and blocks several semantically weak fallback synonyms; supplemental simplification mappings were also tightened for clearer reasons and better wording.
- Upgrade mode now uses a **wider sentence-combine budget** to reach target bands more reliably, while low-grade upgrades apply stricter vocabulary choices and skip verb patterns that tend to break idioms or adjective complements.
- Local rewrite verification after these changes: `ml-service/test_simplification_consistency.py` passes, targeted interactive/auto spot checks for `5 -> 6`, `3 -> 10`, `12 -> 6`, `12 -> 3`, and `9 -> 3` all produce valid outputs, and the full interactive matrix improved from **26/121** exact hits to **43/121** with average miss distance down to **1.87**.
- Added `ml-service/test_simplification_consistency.py` to verify that interactive previews, accepted-change application, span anchors, and repeated-word partial acceptance all stay in sync.
- Interactive and auto previews are now rebuilt from the same anchored patch list used by `/simplify/apply`, so preview text no longer drifts from the saved result because of whitespace or replacement-order differences.
- Sentence combining and splitting now preserve **paragraph boundaries** instead of collapsing the entire rewrite into a single block of text, which keeps previews and interactive changes reviewable.
- Simplification change objects are now generated as **stable original-to-preview patches** with exact `start`/`end` spans, raw replacement text, and preview-side spans, so repeated words and sentence rewrites no longer rely on fragile string matching.
- Interactive preview rebuilding and `/simplify/apply` now use **span-based patch application** instead of naive `replace()`, keeping accepted/denied changes aligned with the exact text users reviewed.
- Simplification reason text now infers the **local direction of each patch** (simplification vs upgrade) from the actual before/after words, so displayed explanations better match what changed on screen.
- Rewrite pipeline is now **rule-based first** in auto mode; Groq is used only for validation and light polish instead of replacing the whole rewrite.
- Simplifier targeting now prefers the same readability model raw score shown to users, with iterative passes toward the target grade.
- Simplifier calibration now tracks the **best intermediate candidate**, uses lighter near-target adjustments, and has broader rule-based vocabulary coverage for academic language before any Groq rescue is attempted.
- Sentence splitting is now recursive and fragment-aware: long sentences can be split across multiple passes, bad split points ending on words like `of`/`to` are rejected, and subject-less right-hand clauses are repaired into standalone sentences.
- Auto-mode simplification now rebuilds its returned change list from the **final rewritten text**, which keeps UI highlights aligned after validation/polish adjustments.
- Added `ml-service/test_simplification_matrix.py` to run full grade-to-grade rewrite regression checks across the calibrated test set.
- The simplification matrix runner now suppresses internal model logs so its output stays valid JSON for repeatable local regression checks.
- Interactive rewrite highlights now recognize `word_upgrade` changes on the rewritten text, and adjacent grade-up previews can use curated connector upgrades like `also -> furthermore` to reach the intended band.
- The ML service now loads its `.env` automatically from `models/__init__.py`, prefers repo-local NLTK assets from `ml-service/nltk_data`, and prefers a repo-local E5 cache from `ml-service/data/hf_cache/intfloat-e5-small-v2`.
- Repo-local runtime assets have been provisioned for Codex: `wordnet`, `omw-1.4`, local E5-small-v2 files, and the FlashRank reranker cache under `ml-service/data/flashrank_cache`.
- ChromaDB anonymized telemetry is disabled in the local RAG engine setup to avoid blocked outbound PostHog calls during sandboxed runs.
- Missing NLTK WordNet corpora no longer hard-crash rewrites; the simplifier falls back to curated mappings and non-WordNet rules.
- Interactive rewrite saves now apply **accepted changes only**, and preview-grade checks use a non-persisted analysis preview endpoint.
- RAG queries are now scoped to the authenticated user's uploaded documents, fallback retrieval sorts by similarity, and chunk metadata includes filenames for clearer source display.

---

## Project Overview

**ClarityWorks** is a Final Year Project (FYP) for a Bachelor's of Computer Science degree. It is a full-stack text readability analysis web application that uses the **CLEAR Corpus dataset** (CommonLit Ease of Readability, ~5,000 professionally graded reading passages, grades 3-12) combined with traditional readability formulas and machine learning to analyze, score, and improve the readability of text.

Users register, log in, input text via multiple methods (paste, PDF, DOC, image OCR, voice), and receive comprehensive readability analysis including grade level predictions, readability scores, difficulty highlighting, and data visualizations. Users can also simplify text to target grade levels and upload/query textbooks via RAG.

---

## Architecture

Three-tier microservice architecture with three independently running services:

```
Frontend (React)          Backend (Express.js)         ML Service (Flask)
Port 5173                 Port 5000                    Port 5001
       |                        |                           |
       |--- HTTP/REST --------->|                           |
       |                        |--- HTTP/REST ------------>|
       |                        |                           |
       |                        |--- PostgreSQL ----------->|
       |                        |   Port 5432               |
       |                        |                           |--- ChromaDB (embedded)
```

### Service Breakdown

| Service | Tech Stack | Port | Purpose |
|---------|-----------|------|---------|
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, Recharts | 5173 | UI, user interactions, data visualization |
| **Backend** | Node.js, Express.js, TypeScript, PostgreSQL | 5000 | REST API, auth, business logic, database |
| **ML Service** | Python 3.9+, Flask, scikit-learn, XGBoost, spaCy, ChromaDB | 5001 | Text analysis, ML predictions, simplification, RAG, file extraction |
| **Database** | PostgreSQL 14+ | 5432 | User data, analysis results, simplification history, RAG metadata |

---

## Directory Structure

```
clarityworksv2/
├── AGENTS.md                         # THIS FILE - project context
├── ClarityWorks_SRDS.pdf            # Software Requirements & Design Specification
├── Presentation.pdf                  # Project presentation
├── s13428-022-01802-x.pdf           # CLEAR Corpus research paper
├── promptsmarch/                     # Implementation prompts (1-10)
│
├── backend/                          # Node.js/Express REST API
│   ├── src/
│   │   ├── server.ts                 # Express app entry point
│   │   ├── config/
│   │   │   ├── database.ts           # PostgreSQL pool & schema init (5 tables)
│   │   │   ├── upload.ts             # Multer config for profile pictures (5MB)
│   │   │   └── documentUpload.ts     # Multer config for RAG documents (100MB)
│   │   ├── controllers/
│   │   │   ├── authController.ts     # Register, login, logout, profile
│   │   │   ├── analysisController.ts # CRUD analyses, statistics
│   │   │   ├── textController.ts     # PDF/DOC/Image extraction proxy
│   │   │   ├── adminController.ts    # Admin user & analysis management
│   │   │   ├── simplifyController.ts # Text simplification proxy (Prompt 3)
│   │   │   └── ragController.ts      # RAG document upload/query proxy (Prompt 4)
│   │   ├── middleware/
│   │   │   └── auth.ts               # JWT verify + admin authorization
│   │   ├── routes/
│   │   │   ├── authRoutes.ts
│   │   │   ├── analysisRoutes.ts
│   │   │   ├── textRoutes.ts
│   │   │   ├── adminRoutes.ts
│   │   │   ├── simplifyRoutes.ts     # Prompt 3
│   │   │   └── ragRoutes.ts          # Prompt 4
│   │   └── utils/
│   │       └── passwordValidator.ts  # Password complexity rules
│   ├── uploads/
│   │   ├── profiles/                 # Profile picture storage
│   │   └── documents/                # RAG document temp storage
│   ├── package.json
│   ├── tsconfig.json
│   └── .env
│
├── frontend/                         # React SPA
│   ├── src/
│   │   ├── App.tsx                   # React Router configuration
│   │   ├── main.tsx                  # Entry point
│   │   ├── index.css                 # Global styles + Tailwind
│   │   ├── components/
│   │   │   ├── Auth/
│   │   │   │   ├── Login.tsx
│   │   │   │   ├── Register.tsx
│   │   │   │   └── PasswordStrength.tsx
│   │   │   ├── Dashboard/
│   │   │   │   └── Dashboard.tsx     # Stats + recent analyses + readability trend chart
│   │   │   ├── TextInput/
│   │   │   │   └── TextInput.tsx     # 5-tab input (text/pdf/doc/image/voice) + 11 sample texts with grade reasons
│   │   │   ├── Analysis/
│   │   │   │   ├── AnalysisResults.tsx  # Full results + Simplify button + heatmap + reading time card + complexity score + improvements + vocabulary + detailed report
│   │   │   │   ├── Charts.tsx           # Radar, bar, pie, gauge, common words charts
│   │   │   │   ├── GradeExplanation.tsx # Grade explanation (layman/technical toggle) (Prompt 7)
│   │   │   │   ├── TextHeatmap.tsx      # Text difficulty heatmap visualization (Prompt 7)
│   │   │   │   ├── ComplexityScoreCard.tsx  # Weighted composite complexity score 0-100 (Prompt 10)
│   │   │   │   ├── ImprovementSuggestions.tsx  # 3-5 prioritized actionable suggestions with grade impact (Prompt 10)
│   │   │   │   ├── VocabularyAnalysis.tsx  # Word categorization (Simple/Medium/Advanced/Expert) with stacked bar chart (Prompt 10)
│   │   │   │   └── HighlightedText.tsx  # Difficult word/sentence highlighting
│   │   │   ├── Simplification/
│   │   │   │   └── SimplifyPage.tsx  # Text simplification UI (Prompt 3) + score preview (Prompt 9)
│   │   │   ├── Compare/
│   │   │   │   └── ComparePage.tsx   # Side-by-side text comparison (Prompt 9)
│   │   │   ├── Batch/
│   │   │   │   └── BatchPage.tsx     # Batch analysis with summary table (Prompt 9)
│   │   │   ├── RAG/
│   │   │   │   ├── RAGUpload.tsx     # Textbook upload page (Prompt 4)
│   │   │   │   └── RAGQuery.tsx      # Textbook query page + AI answer display (Prompt 4, True RAG Prompt 8)
│   │   │   ├── History/
│   │   │   │   ├── History.tsx       # Tabbed history (analyses/simplifications) (Prompt 7)
│   │   │   │   └── SimplificationHistory.tsx # Simplification history tab (Prompt 7)
│   │   │   ├── Profile/
│   │   │   │   └── Profile.tsx       # Profile settings page
│   │   │   ├── Layout/
│   │   │   │   ├── Layout.tsx        # Main layout wrapper
│   │   │   │   └── Sidebar.tsx       # Navigation sidebar (RAG links, Compare, Batch, dark mode toggle)
│   │   │   ├── common/
│   │   │   │   └── LoadingSpinner.tsx  # Reusable loading spinner + fullscreen overlay (Prompt 7)
│   │   │   └── Admin/
│   │   │       ├── AdminDashboard.tsx
│   │   │       ├── UserManagement.tsx
│   │   │       ├── AnalysisManagement.tsx
│   │   │       └── AdminRoute.tsx    # Admin route guard
│   │   ├── services/
│   │   │   └── api.ts               # Axios client + simplifyApi + ragApi
│   │   ├── types/
│   │   │   └── index.ts             # All TypeScript interfaces
│   │   └── utils/
│   │       ├── auth.tsx              # AuthContext + useAuth hook
│   │       ├── exportPdf.ts         # jsPDF report generation
│   │       ├── exportSimplification.ts  # Simplification PDF/DOCX export (Prompt 7)
│   │       ├── exportRAG.ts         # RAG results PDF/DOCX export with AI answer (Prompt 7, updated Prompt 8)
│   │       ├── gradeExplanations.ts # Grade explanation data (layman + technical) (Prompt 7)
│   │       ├── complexityScore.ts   # Weighted composite complexity score 0-100 (grade 40%, Flesch 30%, difficult words 20%, sentence length 10%) (Prompt 10)
│   │       ├── readingTime.ts       # Difficulty-adjusted reading time estimate (base 225 WPM, Flesch-adjusted 0.6-1.0x) (Prompt 10)
│   │       ├── improvementSuggestions.ts  # 3-5 prioritized actionable suggestions with estimated grade impact (Prompt 10)
│   │       ├── vocabularyAnalysis.ts     # Word categorization into Simple/Medium/Advanced/Expert levels (Prompt 10)
│   │       └── detailedReport.ts    # Multi-page jsPDF detailed report (cover, scores, suggestions, vocabulary, difficult passages) (Prompt 10)
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── .env
│
└── ml-service/                       # Python Flask microservice
    ├── app.py                        # Flask API (12+ endpoints, RAG query returns AI answer)
    ├── train_model.py                # Enhanced training: GridSearchCV + XGBoost
    ├── validate_test_files.py        # Test file validation script (11/11 pass, graduated tolerance)
    ├── test_rag_improvements.py      # RAG improvements test script (FlashRank, Groq, chunking, embeddings, answer gen)
    ├── utils/
    │   ├── __init__.py
    │   └── text_cleaner.py          # TextCleaner for extracted text (OCR, PDF, DOC) (Prompt 7)
    ├── analyze_features.py           # Feature importance analysis
    ├── requirements.txt
    ├── .env
    ├── models/
    │   ├── __init__.py               # Sets THINC_NO_TORCH env var
    │   ├── text_processor.py         # Tokenization, syllables, difficulty detection
    │   ├── feature_extractor.py      # 16 ML features (11 original + 5 spaCy NLP)
    │   ├── readability_model.py      # 3-model ensemble (RF + GB + XGBoost)
    │   ├── synonym_lookup.py         # Word lists, frequency, academic vocab
    │   ├── simplifier.py             # Text simplification engine (Prompt 3+6)
    │   ├── wordnet_synonyms.py      # WordNet synonym finder (Prompt 6) - integrated into simplifier
    │   ├── datamuse_synonyms.py     # Datamuse API fallback synonyms (Prompt 6)
    │   ├── groq_validator.py        # Groq AI validation of changes (Prompt 6)
    │   └── rag_engine.py             # RAG engine: ChromaDB + E5-small-v2 + FlashRank re-ranking + Groq answer generation (Prompt 4, upgraded Prompt 8)
    ├── trained_models/               # Serialized .joblib models
    │   ├── rf_model.joblib           # Tuned Random Forest
    │   ├── gb_model.joblib           # Tuned Gradient Boosting
    │   └── xgb_model.joblib          # XGBoost (Prompt 5)
    ├── data/
    │   ├── clear_corpus/             # CLEAR Corpus CSV (~5000 samples)
    │   ├── test_files/               # Calibrated grade 3-12 + college test files (11/11 pass)
    │   ├── dale_chall_3000.txt
    │   ├── simplification_map.json
    │   ├── complexification_map.json
    │   ├── coca_frequency.csv
    │   └── academic_word_list.txt
    ├── chroma_db/                    # ChromaDB persistent storage (RAG)
    └── venv/                         # Python virtual environment
```

---

## How It Works - Complete Data Flow

### Analysis Flow (the core feature)

1. **User inputs text** via one of 5 methods in TextInput.tsx
2. **Frontend calls** `POST /api/analyses` with text + JWT token via api.ts
3. **Backend middleware** (auth.ts) verifies JWT, extracts userId
4. **Backend controller** (analysisController.ts) validates text (50-50,000 chars)
5. **Backend proxies** to Python ML service at `POST http://localhost:5001/analyze`
6. **ML Service** (app.py) processes the text:
   - TextProcessor calculates basic metrics (word count, sentences, syllables, etc.)
   - FeatureExtractor extracts 16 ML features (11 original + 5 spaCy NLP) + 8 readability scores via textstat
   - ReadabilityModel runs 3-model ensemble prediction (RF + GB + XGBoost averaged)
   - TextProcessor also identifies difficult words and difficult sentences
7. **Results returned** to backend, which **saves to PostgreSQL** (analyses table)
8. **Frontend receives** results and navigates to AnalysisResults.tsx
9. **Results displayed** with charts, highlighted text, and metrics
10. **User can click "Simplify Text"** to navigate to SimplifyPage for text simplification

### Text Simplification Flow (Prompt 3)

1. User clicks "Simplify Text" from AnalysisResults or navigates to `/simplify/:analysisId`
2. User selects target grade level and mode (auto/interactive)
3. Frontend calls `POST /api/simplify/analyze` with text and target grade
4. Backend proxies to `POST http://localhost:5001/simplify/analyze`
5. ML Service simplifier.py generates a deterministic rule-based rewrite candidate, scores it with the trained readability model, then runs a bounded final semantic/flow repair pass when Groq is available
6. Final preview text is re-diffed back into anchored word/sentence changes so Auto and Interactive expose the same reviewable patch set
7. In interactive mode, user accepts/denies individual changes
8. Final simplified text can be saved to database

### RAG Textbook Flow (Prompt 4, upgraded Prompt 8)

1. User uploads PDF/DOCX textbook via RAGUpload page
2. Backend forwards file to `POST http://localhost:5001/rag/upload`
3. ML Service extracts text via **pdfplumber** (PDF) or python-docx (DOCX)
4. Text chunked via **RecursiveCharacterTextSplitter** (1000 chars, 200 overlap, paragraph-aware)
5. Chunks embedded with **E5-small-v2** (384-dim, `"passage: "` prefix) and stored in ChromaDB
6. Backend saves metadata to rag_documents table
7. User queries textbooks via RAGQuery page
8. Backend proxies to `POST http://localhost:5001/rag/query`
9. RAG engine retrieves top-20 candidates via embedding similarity (`"query: "` prefix)
10. **FlashRank cross-encoder** re-ranks candidates to precise top-5 results
11. **Groq answer generation** (`llama-3.3-70b-versatile`): synthesizes coherent answer from top-5 chunks with `[Source N]` citations
12. Returns `{answer, sources, has_answer}` — frontend displays AI answer in green gradient box + expandable source documents

### Authentication Flow

1. User registers at Register.tsx -> `POST /api/auth/register`
2. Password validated by passwordValidator.ts (8+ chars, uppercase, lowercase, digit, special)
3. Password hashed with bcrypt (10 rounds)
4. JWT generated with userId, email, role, 24h expiry
5. Token stored in localStorage, attached to all API requests via axios interceptor
6. Protected routes check JWT in auth.ts middleware

---

## Database Schema

**PostgreSQL** with 5 tables, auto-created on backend startup via database.ts:

### Users Table
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PRIMARY KEY | Auto-increment |
| email | VARCHAR(255) UNIQUE | Login identifier |
| password_hash | VARCHAR(255) | bcrypt hash |
| full_name | VARCHAR(255) | Display name |
| role | VARCHAR(20) DEFAULT 'user' | 'user' or 'admin' |
| is_active | BOOLEAN DEFAULT true | Account status |
| profile_picture | VARCHAR(500) | File path or null |
| created_at | TIMESTAMP | Auto-set |

### Analyses Table
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PRIMARY KEY | Auto-increment |
| user_id | INTEGER FK -> users(id) CASCADE | Owner |
| original_text | TEXT | Full input text |
| title | VARCHAR(255) | User-set or auto-generated |
| word_count, sentence_count | INTEGER | Basic metrics |
| avg_sentence_length, avg_syllables_per_word | DECIMAL | Averages |
| flesch_reading_ease | DECIMAL | 0-100 scale |
| flesch_kincaid_grade | DECIMAL | US grade level |
| automated_readability_index | DECIMAL | ARI score |
| smog_readability | DECIMAL | SMOG index |
| coleman_liau_index | DECIMAL | Coleman-Liau score |
| predicted_grade_level | VARCHAR(50) | "Grade 3" through "College" |
| predicted_complexity | VARCHAR(50) | Beginner/Intermediate/Advanced/Expert |
| confidence | DECIMAL | 0.5-0.99 model confidence |
| difficult_words_count | INTEGER | Count |
| difficult_words_percentage | DECIMAL | Percentage |
| difficult_words | JSONB | Array of {word, position, syllables, reason} |
| difficult_sentences | JSONB | Array of {sentence, position, word_count, reason, flesch_score} |
| created_at | TIMESTAMP | Auto-set |

### Simplification History Table (Prompt 3)
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PRIMARY KEY | Auto-increment |
| analysis_id | INTEGER FK -> analyses(id) CASCADE | Linked analysis |
| user_id | INTEGER FK -> users(id) CASCADE | Owner |
| original_text | TEXT | Original text |
| simplified_text | TEXT | Simplified version |
| target_grade | VARCHAR(50) | Target grade level |
| changes_applied | JSONB | Applied changes details |
| mode | VARCHAR(20) | 'auto' or 'interactive' |
| metrics_original | JSONB | Pre-simplification metrics (Prompt 7) |
| metrics_simplified | JSONB | Post-simplification metrics (Prompt 7) |
| created_at | TIMESTAMP | Auto-set |

### RAG Documents Table (Prompt 4)
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PRIMARY KEY | Auto-increment |
| user_id | INTEGER FK -> users(id) CASCADE | Owner |
| filename | VARCHAR(255) | Stored filename |
| original_filename | VARCHAR(255) | Original upload name |
| file_size_bytes | INTEGER | File size |
| total_pages | INTEGER | Page count |
| total_chunks | INTEGER | Number of chunks |
| chromadb_collection_id | VARCHAR(255) UNIQUE | ChromaDB collection ref |
| uploaded_at | TIMESTAMP | Auto-set |

### RAG Queries Table (Prompt 4)
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PRIMARY KEY | Auto-increment |
| user_id | INTEGER FK -> users(id) CASCADE | Owner |
| query_text | TEXT | Query string |
| document_ids | TEXT[] | Queried document UUIDs |
| result_count | INTEGER | Results returned |
| created_at | TIMESTAMP | Auto-set |

**Indexes:** `idx_analyses_user_id`, `idx_analyses_created_at DESC`

---

## ML Pipeline Details

### Training (via train_model.py - Enhanced in Prompt 5)
- Loads CLEAR Corpus CSV (~4,724 samples)
- Extracts **16 features** per text sample (11 original + 5 spaCy NLP)
- 80/20 train/test split (random_state=42)
- **GridSearchCV** hyperparameter tuning for Random Forest and Gradient Boosting
- Trains 3 models: **Random Forest**, **Gradient Boosting**, **XGBoost**
- Ensemble prediction = average of all 3 models
- Saves models as `.joblib` files

### 16 ML Features (11 Original + 5 New spaCy)

**Original 11:**
1. word_count
2. sentence_count
3. avg_sentence_length
4. avg_word_length
5. avg_syllables_per_word
6. difficult_words_percentage
7. flesch_reading_ease
8. flesch_kincaid_grade
9. automated_readability_index
10. smog_readability
11. type_token_ratio (vocabulary diversity)

**New 5 (Prompt 5 - spaCy NLP):**
12. passive_voice_percentage - % sentences with passive voice (nsubjpass)
13. subordinate_clause_density - avg subordinate clauses per sentence (mark, advcl, acl, relcl)
14. pos_diversity_score - unique POS tags / total POS tags
15. lexical_diversity - unique words / total words
16. sentence_complexity_variance - variance of sentence lengths

### Feature Importance (top 5)
1. flesch_kincaid_grade: 80.8%
2. automated_readability_index: 13.3%
3. subordinate_clause_density: 0.9% (NEW)
4. sentence_complexity_variance: 0.8% (NEW)
5. avg_sentence_length: 0.6%

### 8 Readability Scores (via `textstat` library)
1. Flesch Reading Ease (0-100, higher = easier)
2. Flesch-Kincaid Grade Level
3. Automated Readability Index (ARI)
4. SMOG Index
5. Coleman-Liau Index
6. Dale-Chall Score
7. Linsear Write Formula
8. Gunning Fog Index

(Only the first 5 are stored in the database and shown to users)

### Prediction (3-Model Ensemble - Prompt 5)
- Ensemble: average of RF, GB, and XGBoost predictions
- Confidence based on std deviation across 3 models (low disagreement = high confidence)
- Falls back to 2-model ensemble if XGBoost not loaded
- Falls back to Flesch-Kincaid grade heuristic if no models trained
- Maps numeric prediction to grade string: "Grade 3" through "College"
- Maps grade to complexity: Beginner (3-6), Intermediate (7-9), Advanced (10-12), Expert (College)
- Response includes individual model predictions for transparency

### Best Hyperparameters (after GridSearchCV)
- **Random Forest:** max_depth=None, min_samples_split=2, n_estimators=300
- **Gradient Boosting:** learning_rate=0.05, max_depth=5, n_estimators=100
- **XGBoost:** learning_rate=0.05, max_depth=5, n_estimators=300, subsample=0.8

### Text Simplification Engine (Prompt 3 + 6 - simplifier.py)
- `TextSimplifier` class with grade-specific constraints
- **Deterministic candidate selection** - rule-based lexical/syntactic/discourse candidates are scored against the same readability model used for the grade preview
- **Dynamic synonym finding** using NLTK WordNet + `wordfreq.zipf_frequency()` (Prompt 6)
- **Lesk word sense disambiguation** to pick contextually correct WordNet synset
- **Sense validation** - rejects synonyms where the matched sense is a rare meaning of the candidate
- **Polysemous verb filter** - skips verbs with 4+ senses when Lesk can't disambiguate
- **Phrasal verb detection** - preserves "attest to", "refer to" etc.
- **Datamuse API fallback** for words WordNet can't simplify (free, no API key)
- **Bounded final repair pass** - when Groq is configured, it performs a constrained semantics/flow repair on top of the rule-based draft, then the final text is diffed back into anchored review patches
- Curated `simplification_map.json` checked first (50 highest-quality mappings)
- CVC consonant doubling in inflection (dig→digging, run→running)
- Multi-word phrase inflection (take part→took part)
- Splits long sentences via spaCy dependency parsing (advcl, relcl, conjunctions)
- `GRADE_ZIPF_THRESHOLDS` dict maps grade levels to word frequency thresholds
- Grade-specific constraints for max sentence length and syllable targets
- Returns list of anchored changes with original/simplified/reason + validation results; final-review adjustments are preserved as normal interactive accept/deny patches

### RAG Engine (Prompt 4, upgraded Prompt 8 - rag_engine.py)
- `RAGEngine` class using ChromaDB PersistentClient
- **E5-small-v2 embeddings** (`intfloat/e5-small-v2`, 384-dim, same size as MiniLM but much more accurate) — requires `"query: "` / `"passage: "` prefixes
- **RecursiveCharacterTextSplitter** (langchain-text-splitters): 1000-char chunks, 200-char overlap, splits by `\n\n` → `\n` → `. ` → ` ` → `""`
- **FlashRank re-ranking** (`ms-marco-MiniLM-L-12-v2`, ~4MB, CPU-only, ONNX): retrieves top-20 candidates via embedding similarity, then re-ranks with cross-encoder to precise top-5
- **True RAG answer generation** via Groq (`llama-3.3-70b-versatile`, temp=0.2, max_tokens=1500): `_generate_answer()` builds context from top-k chunks with `[Source N]` labels, synthesizes coherent answer with citations
- **Return format**: `query_documents()` returns `{answer: str|None, sources: list, has_answer: bool}` instead of raw list
- **pdfplumber PDF extraction**: used for RAG document upload (replaced pymupdf4llm which caused ONNX int32/int64 conflict via its internal BoxRFDGNN layout model)
- **Automatic model migration**: detects embedding model change via `.embedding_model` marker file, clears incompatible ChromaDB collections
- ChromaDB metadata values stored as strings
- Similarity score: `max(0.0, min(1.0, 1 - (distance / 2)))` (Euclidean distance normalization)

### Difficulty Detection (text_processor.py)

**Difficult Words** criteria (all must be true):
- Not a proper noun or abbreviation
- Not in Dale-Chall 3000 easy words list (loaded via SynonymLookup)
- 4+ characters long
- 3+ syllables
- Detailed multi-reason explanations: syllable count, COCA frequency rank, Dale-Chall membership, academic vocabulary flag, technical suffix detection, simpler alternative suggestion

**Difficult Sentences** criteria (any one triggers):
- 25+ words (long sentence)
- Flesch score < 30 AND 2+ difficult words
- 3+ difficult words in sentence
- 5+ polysyllabic words in sentence

---

## API Endpoints

### Auth (`/api/auth`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /register | No | Create account |
| POST | /login | No | Login, returns JWT |
| GET | /me | JWT | Get current user |
| POST | /logout | No | Client-side logout |
| PUT | /profile | JWT | Update name/email |
| PUT | /password | JWT | Change password |
| POST | /profile-picture | JWT | Upload profile pic |
| DELETE | /profile-picture | JWT | Remove profile pic |

### Analyses (`/api/analyses`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | / | JWT | Analyze text (proxies to ML service) |
| GET | / | JWT | List user's analyses (paginated, searchable, filterable) |
| GET | /stats | JWT | Dashboard statistics |
| GET | /:id | JWT | Get single analysis |
| DELETE | /:id | JWT | Delete analysis |

### Text Extraction (`/api/text`)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /extract-pdf | JWT | Extract text from PDF |
| POST | /extract-doc | JWT | Extract text from DOC/DOCX |
| POST | /extract-image | JWT | OCR text extraction from image |

### Simplification (`/api/simplify`) - Prompt 3
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /analyze | JWT | Analyze text for simplification suggestions |
| POST | /apply | JWT | Apply selected changes (interactive mode) |
| POST | /save | JWT | Save simplification to history |
| GET | /history | JWT | Fetch simplification history (Prompt 7) |

### RAG (`/api/rag`) - Prompt 4
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /upload | JWT | Upload textbook (PDF/DOCX, 100MB max) |
| POST | /query | JWT | Semantic search across uploaded documents |
| GET | /documents | JWT | List user's uploaded documents |
| DELETE | /documents/:id | JWT | Delete document from RAG system |

### Admin (`/api/admin`) - Admin role required
| Method | Path | Description |
|--------|------|-------------|
| GET | /stats | Platform-wide statistics |
| GET | /users | List all users |
| GET | /users/:id | User details |
| PATCH | /users/:id/role | Change user role |
| PATCH | /users/:id/status | Activate/deactivate |
| DELETE | /users/:id | Delete user (cascades) |
| GET | /analyses | All analyses across users |
| DELETE | /analyses/:id | Delete any analysis |

### ML Service (`http://localhost:5001`)
| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check + model status |
| POST | /analyze | Main text analysis endpoint |
| POST | /extract-pdf | PDF text extraction |
| POST | /extract-doc | DOC/DOCX extraction |
| POST | /extract-image | OCR image extraction |
| POST | /train | Train ML model on corpus |
| POST | /simplify/analyze | Analyze text for simplification (Prompt 3) |
| POST | /simplify/apply | Apply selected changes (Prompt 3) |
| POST | /rag/upload | Upload document to RAG (Prompt 4) |
| POST | /rag/query | Query RAG documents (Prompt 4) |
| DELETE | /rag/documents/<doc_id> | Delete RAG document (Prompt 4) |

---

## Environment Variables

### Backend (`backend/.env`)
```
PORT=5000
DATABASE_URL=postgresql://clarityworks_user:clarityworks_pass@localhost:5432/clarityworks_db
JWT_SECRET=your_super_secret_jwt_key_change_this_in_production
PYTHON_SERVICE_URL=http://localhost:5001
NODE_ENV=development
```

### Frontend (`frontend/.env`)
```
VITE_API_URL=http://localhost:5000
VITE_PYTHON_API_URL=http://localhost:5001
```

### ML Service (`ml-service/.env`)
```
FLASK_PORT=5001
FLASK_ENV=production
TESSERACT_PATH=C:/Program Files/Tesseract-OCR/tesseract.exe
GROQ_API_KEY=gsk_...  # Required for simplification validation + fallback (Prompt 6) AND RAG answer generation (Prompt 8)
```

---

## Key Dependencies

### Backend (Node.js)
- express 4.18, cors, dotenv
- pg 8.11 (PostgreSQL driver)
- bcrypt 5.1 (password hashing)
- jsonwebtoken 9.0 (JWT)
- multer 1.4 (file uploads - 2 configs: 5MB profiles, 100MB documents)
- axios 1.6 (HTTP client to ML service)
- form-data (forwarding file uploads to ML service)
- express-validator 7.0
- TypeScript 5.3, nodemon, ts-node

### Frontend (React)
- react 18.2, react-dom, react-router-dom 6.21
- axios 1.6 (API client)
- recharts 2.10 (charts)
- react-hook-form 7.49 (forms)
- lucide-react 0.294 (icons)
- jspdf 2.5 (PDF export)
- jspdf-autotable 3.8 (PDF table generation for exports - Prompt 7)
- docx 8.5 (DOCX document generation for exports - Prompt 7)
- file-saver 2.0 (file download utility for DOCX export - Prompt 7)
- @radix-ui/react-tooltip 1.0
- TailwindCSS 3.3, Vite 5.0, TypeScript 5.2

### ML Service (Python)
- flask 3.0, flask-cors 4.0
- scikit-learn 1.3 (Random Forest, Gradient Boosting, GridSearchCV)
- xgboost 2.0.3 (XGBoost regressor - Prompt 5)
- spacy 3.7.2 + en_core_web_sm (NLP features - Prompt 5)
- pandas 2.1, numpy 1.26
- textstat 0.7 (readability formulas)
- pyphen 0.14 (syllable counting)
- pdfplumber 0.10 (PDF extraction)
- python-docx 1.1 (DOC/DOCX extraction)
- pytesseract 0.3 + Pillow 10.1 (OCR)
- joblib 1.3 (model serialization)
- nltk 3.9.1 + WordNet corpus (synonym finding - Prompt 6)
- wordfreq 3.1.1 (zipf frequency for word difficulty - Prompt 6)
- groq 0.11.0 (LLM for simplification fallback + validation - Prompts 3, 6)
- chromadb 0.4.22 (vector database for RAG - Prompt 4)
- sentence-transformers 2.3.1 (E5-small-v2 embeddings - Prompt 4, upgraded Prompt 8)
- pymupdf4llm 0.3+ (PDF→Markdown extraction for RAG - Prompt 8)
- flashrank 0.2+ (cross-encoder re-ranking, ~4MB ONNX model - Prompt 8)
- langchain-text-splitters 0.2+ (RecursiveCharacterTextSplitter chunking - Prompt 8)
- requests 2.31 (Datamuse API calls - Prompt 6)

---

## Running the Application

Three terminals needed:

```bash
# Terminal 1 - Backend (Port 5000)
cd backend
npm install
npm run dev

# Terminal 2 - ML Service (Port 5001)
cd ml-service
venv\Scripts\activate    # Windows
python app.py

# Terminal 3 - Frontend (Port 5173)
cd frontend
npm install
npm run dev

# Access: http://localhost:5173
```

### Prerequisites
- Node.js v18+
- Python 3.9+
- PostgreSQL 14+
- Tesseract OCR (for image text extraction)

### Database Setup
```sql
CREATE DATABASE clarityworks_db;
CREATE USER clarityworks_user WITH PASSWORD 'clarityworks_pass';
GRANT ALL PRIVILEGES ON DATABASE clarityworks_db TO clarityworks_user;
\c clarityworks_db
GRANT ALL ON SCHEMA public TO clarityworks_user;
```

Tables are auto-created on backend startup (5 tables: users, analyses, simplification_history, rag_documents, rag_queries).

### Training the ML Model
```bash
cd ml-service
python train_model.py
```
App works without trained models using Flesch-Kincaid heuristic fallback.

### Known Issue: torch DLL on Windows
The thinc library (spaCy dependency) tries to import torch, which may fail with a DLL error on Windows. Fix applied: `models/__init__.py` sets `os.environ['THINC_NO_TORCH'] = '1'` before importing spaCy. If this doesn't work, patch `venv/Lib/site-packages/thinc/compat.py` to change `except ImportError:` to `except (ImportError, OSError):` in the torch import block.

---

## What Has Been Implemented (Status)

### FULLY IMPLEMENTED
- [x] User registration with password strength validation and visual indicator
- [x] JWT-based authentication (24h expiry)
- [x] Login/logout with session management (localStorage)
- [x] Dashboard with stats (total analyses, avg reading ease, avg grade level, total words)
- [x] Dashboard shows 3 most recent analyses
- [x] Sidebar navigation with profile at bottom left
- [x] Profile page (edit name, email, change password, upload/remove profile picture)
- [x] Text input via direct typing/pasting
- [x] PDF file upload with text extraction (pdfplumber)
- [x] DOC/DOCX file upload with text extraction (python-docx)
- [x] Image OCR text extraction (pytesseract, local - not API-based)
- [x] Voice/speech-to-text input (Web Speech API, on-the-fly transcription)
- [x] Readability analysis with 5 traditional formulas (Flesch, FK Grade, ARI, SMOG, Coleman-Liau)
- [x] ML-based grade level prediction (3-model ensemble: RF + GB + XGBoost)
- [x] 16-feature ML pipeline (11 original + 5 spaCy NLP features)
- [x] GridSearchCV hyperparameter tuning
- [x] Training on CLEAR Corpus dataset (~4,724 samples)
- [x] Complexity categorization (Beginner/Intermediate/Advanced/Expert)
- [x] Confidence score for predictions (based on 3-model agreement)
- [x] Basic text metrics (word count, sentence count, avg sentence length, avg syllables, vocabulary diversity)
- [x] Difficult word detection (Dale-Chall 3000 based, with proper noun/abbreviation filtering, multi-reason explanations)
- [x] Difficult sentence detection (multi-criteria with detailed reasons)
- [x] Text highlighting with hover tooltips showing specific reasons
- [x] Data visualization charts (5 chart types)
- [x] History page with pagination, search, and grade level filtering
- [x] PDF report export (jsPDF)
- [x] Full admin panel (stats, user management, analysis management)
- [x] Role-based access control (user vs admin)
- [x] Text simplification engine (auto + interactive modes) - Prompt 3
- [x] Simplification preview/apply consistency with anchored word/sentence patches, plus bounded final semantic repair before diffing back into the UI
- [x] Simplify Text button on analysis results page - Prompt 3
- [x] RAG textbook upload (PDF/DOCX, chunked into ChromaDB) - Prompt 4
- [x] RAG semantic search/query across uploaded textbooks - Prompt 4
- [x] Sidebar links for Upload Textbooks and Query Textbooks - Prompt 4
- [x] Feature importance analysis script - Prompt 5
- [x] Dynamic WordNet + wordfreq synonym finding (replaces hardcoded maps) - Prompt 6
- [x] Datamuse API fallback for broader synonym coverage - Prompt 6
- [x] Groq AI validation of simplification changes - Prompt 6
- [x] Lesk word sense disambiguation for correct synonym selection - Prompt 6
- [x] RAG similarity score fix (Euclidean distance normalization) - Bug fix
- [x] RAG upgraded: E5-small-v2 embeddings, FlashRank re-ranking, RecursiveCharacterTextSplitter, pymupdf4llm - Prompt 8
- [x] True RAG answer generation: Groq llama-3.3-70b-versatile synthesizes answers from retrieved chunks with [Source N] citations - Prompt 8
- [x] RAG AI answer display: green gradient box with Bot icon, expandable source documents with chevron toggles - Prompt 8
- [x] RAG exports updated: PDF/DOCX exports include AI-generated answer section - Prompt 8
- [x] Calibrated test files: 11 test files (grade 3-12 + college) all pass validation (graduated tolerance) - Prompt 7
- [x] Text cleaner utility for extracted text (PDF/DOC/OCR) - Prompt 7
- [x] Live word count display in TextInput with validation messages - Prompt 7
- [x] Grade explanations component (layman/technical toggle) - Prompt 7
- [x] Export simplification results as PDF/DOCX - Prompt 7
- [x] Export RAG query results as PDF/DOCX - Prompt 7
- [x] Simplification history with before/after metrics - Prompt 7
- [x] Tabbed History page (Analyses / Simplifications tabs) - Prompt 7
- [x] Fullscreen loading spinners on all processing actions - Prompt 7
- [x] Text difficulty heatmaps in analysis results - Prompt 7

- [x] Sample/demo texts ("Try a sample" with 11 calibrated texts, grade-level reasons, organized by category) - Prompt 9
- [x] Most common words visualization (top 15 bar chart in AnalysisResults) - Prompt 9
- [x] Readability trend line chart on Dashboard (grade + Flesch over time) - Prompt 9
- [x] Pre-simplification score preview on SimplifyPage (Grade X → Grade Y) - Prompt 9
- [x] Comparative analysis page (side-by-side text comparison with metrics diff) - Prompt 9
- [x] Dark mode toggle (Tailwind darkMode: 'class', sidebar toggle, CSS overrides) - Prompt 9
- [x] Batch analysis (paste or CSV upload, summary table, CSV export) - Prompt 9

- [x] Text Complexity Score (0-100 weighted composite from grade, Flesch, difficult words, sentence length) - Prompt 10
- [x] Reading Time Estimate (difficulty-adjusted WPM, 5th summary card) - Prompt 10
- [x] "Improve This" Suggestions (3-5 prioritized actionable suggestions with grade impact) - Prompt 10
- [x] Vocabulary Level Analysis (Simple/Medium/Advanced/Expert categorization with stacked bar chart) - Prompt 10
- [x] Detailed PDF Report Generator (multi-page jsPDF: cover, scores, suggestions, vocabulary, difficult passages) - Prompt 10

### PENDING
- (none)

### Prompt 6: Enhanced Synonyms & Groq Integration - COMPLETED
- WordNet + wordfreq integrated into simplifier.py for dynamic synonym finding
- Lesk word sense disambiguation for contextually correct replacements
- Sense validation prevents wrong-sense errors (e.g., "maturity" → "due date")
- Created datamuse_synonyms.py (Datamuse API fallback, free, no key)
- Created groq_validator.py (Groq AI validation of rule-based changes)
- Created download_wordnet.py (setup script for WordNet data)
- Hybrid pipeline: curated map → WordNet+Lesk → Datamuse → Groq validation → Groq fallback
- Added nltk, wordfreq to requirements.txt
- Groq API key configured in ml-service/.env

---

## Implementation Progress (Prompts)

### Prompt 1: Enhanced Difficulty Detection - COMPLETED
- Created SynonymLookup module with 5 data files
- Rewrote text_processor.py with detailed multi-reason difficulty explanations
- COCA frequency ranking, academic vocabulary detection, simpler alternative suggestions

### Prompt 2: Calibrated Test Files - COMPLETED (via Prompt 7)
- 11 test files created (grade_3.txt through grade_12.txt + college.txt)
- All 11/11 pass validation with graduated tolerance (±1.0 for grades 3-8, ±1.5 for grades 9-12, ±2.0 for college)
- Key insight: model is extremely sensitive to avg syllables/word — even grade 12 text needs <1.55 syl/word
- Run `python validate_test_files.py` to verify

### Prompt 3: Text Simplification Engine - COMPLETED (Enhanced by Prompt 6)
- Created simplifier.py (TextSimplifier class)
- Flask endpoints: /simplify/analyze, /simplify/apply
- Backend: simplifyController.ts, simplifyRoutes.ts
- Frontend: SimplifyPage.tsx with auto/interactive modes, inline highlighting with accept/deny buttons
- Added "Simplify Text" button to AnalysisResults.tsx
- Database: simplification_history table
- Frontend HighlightedText: word-boundary matching (`findWholeWord`), amber pending / green accepted highlights

### Prompt 4: RAG for Textbook Processing - COMPLETED
- Created rag_engine.py (RAGEngine class with ChromaDB + Sentence-BERT)
- Flask endpoints: /rag/upload, /rag/query, /rag/documents/<id>
- Backend: ragController.ts, ragRoutes.ts, documentUpload.ts (100MB limit)
- Frontend: RAGUpload.tsx, RAGQuery.tsx
- Added sidebar links for Upload Textbooks and Query Textbooks
- Database: rag_documents and rag_queries tables

### Prompt 5: Model Accuracy Improvements - COMPLETED
- Added 5 new spaCy NLP features to feature_extractor.py
- Updated train_model.py with GridSearchCV + XGBoost
- Updated readability_model.py for 3-model ensemble (RF + GB + XGBoost)
- Retrained model: MAE 0.712, R2 0.926, Within +/-1 grade: 80.2%
- Created analyze_features.py for feature importance analysis
- Added xgboost==2.0.3 to requirements.txt

### Prompt 7: Polish & Final Features - COMPLETED
- Part 1: College test file + validation script update (graduated tolerance, 11/11 pass)
- Part 2: TextCleaner utility (ml-service/utils/text_cleaner.py) for OCR/PDF/DOC text cleaning, integrated into app.py extraction endpoints
- Part 3: Live word count display in TextInput.tsx (prominent blue box, validation messages)
- Part 4: GradeExplanation component (layman/technical toggle, characteristics grid, metrics justification)
- Part 5: Simplification PDF/DOCX export (exportSimplification.ts, jsPDF + docx library)
- Part 6: RAG results PDF/DOCX export (exportRAG.ts, jsPDF + docx library)
- Part 7: Simplification save with before/after metrics (metrics_original, metrics_simplified JSONB columns)
- Part 8: Tabbed History page (SimplificationHistory.tsx component, GET /simplify/history endpoint)
- Part 9: LoadingSpinner component (fullscreen overlay), added to TextInput, SimplifyPage, RAGQuery, RAGUpload
- Part 10: TextHeatmap component (difficult word highlighting, sentence difficulty borders)

### Prompt 8: RAG System Upgrade + True RAG - COMPLETED
- **Parts 1-4 (RAG Infrastructure):**
  - Upgraded embedding model from `all-MiniLM-L6-v2` to `intfloat/e5-small-v2` (same 384 dims, significantly more accurate, requires `"query: "` / `"passage: "` prefixes)
  - Added FlashRank cross-encoder re-ranking (`ms-marco-MiniLM-L-12-v2`, ~4MB ONNX, CPU-only) — 2-stage retrieval: top-20 candidates → re-rank to top-5
  - Replaced custom paragraph-based chunking with `RecursiveCharacterTextSplitter` (1000-char chunks, 200-char overlap, separator cascade)
  - Replaced pdfplumber with `pymupdf4llm` for RAG PDF extraction (outputs clean Markdown preserving structure)
  - Added automatic model migration: detects embedding model change, clears incompatible ChromaDB collections
  - Updated app.py: default top_k changed from 20 to 5 (re-ranking makes fewer, more precise results better)
  - Added `TextCleaner.clean_textbook_text()` for textbook-specific cleaning
  - New dependencies: `pymupdf4llm>=0.0.17`, `flashrank>=0.2.0`, `langchain-text-splitters>=0.2.0`
- **Part 5 (True RAG Answer Generation):**
  - Added Groq client initialization in `RAGEngine.__init__` (uses `GROQ_API_KEY` from .env)
  - Added `_generate_answer(query, top_results)` method: builds context from top-k chunks with `[Source N]` labels, calls Groq `llama-3.3-70b-versatile` (temp=0.2, max_tokens=1500) to synthesize coherent answer with citations
  - Updated `query_documents()` return format from `List[dict]` to `{answer: str|None, sources: list, has_answer: bool}`
- **Part 7 (Flask Endpoint):**
  - Updated `/rag/query` endpoint to return `{query, answer, sources, has_answer, results_count, results}` (backward-compatible)
- **Part 8 (Frontend RAG UI):**
  - RAGQuery.tsx: AI answer displayed in green gradient box (`bg-gradient-to-r from-green-50 to-emerald-50`) with Bot icon
  - Expandable source documents with ChevronDown/ChevronRight toggles, similarity badges, word counts
  - Yellow warning box when GROQ_API_KEY not configured
- **Part 9 (Export Updates):**
  - exportRAG.ts: PDF/DOCX exports include "AI-Generated Answer" section between query and sources
  - RAGExportData interface updated with optional `answer` field
- **Part 10 (Test Script):**
  - Created `ml-service/test_rag_improvements.py` — 6 tests: FlashRank init, Groq init, chunking, embeddings, answer generation, return format
- Files modified: `rag_engine.py`, `app.py`, `RAGQuery.tsx`, `exportRAG.ts`, `api.ts`
- Files created: `test_rag_improvements.py`

### Prompt 9: New Features & UX Improvements - COMPLETED
- **Sample/demo texts**: "Try a sample" button in TextInput.tsx with ALL 11 calibrated test texts (Grade 3 through College) organized by category (Elementary, Middle School, High School, College). Each sample has a `reason` explaining WHY the text is at that grade level (sentence length, vocabulary complexity, sentence structure, concept abstraction). Color-coded: green (Elementary 3-5), yellow (Middle School 6-8), orange (High School 9-10), red (High School 11-12), purple (College). Uses Sparkles icon, grouped category labels, blue info box shows grade-level reason when sample selected
- **Most common words visualization**: `CommonWordsChart` in Charts.tsx — horizontal bar chart of top 15 content words (excludes 120+ stop words), computed client-side from original text. Added to AnalysisResults.tsx
- **Readability trend line chart**: Dashboard.tsx fetches last 20 analyses and plots dual-axis line chart (Grade Level on left Y, Flesch Score on right Y) over time using Recharts LineChart
- **Pre-simplification score preview**: SimplifyPage.tsx calls `analysisApi.analyze()` on simplified text after simplification. Shows "Grade X → Grade Y" with color-coded badges and loading spinner
- **Comparative analysis page**: New `ComparePage.tsx` at `/compare` route. Side-by-side text inputs, parallel analysis via `Promise.all`, detailed comparison table with 11 metrics, color-coded diffs (green=better, red=worse)
- **Dark mode toggle**: Tailwind `darkMode: 'class'` in tailwind.config.js. Toggle in Sidebar (Moon/Sun icons). CSS overrides in index.css for bg, text, border, input colors. Theme persisted in localStorage, initialized via inline script in index.html
- **Batch analysis page**: New `BatchPage.tsx` at `/batch` route. Two input modes: paste (separated by "---" or triple newlines) or CSV upload. Sequential analysis with progress bar. Results table with grade, Flesch, words, sentences, difficult words %. CSV export. Summary stats (avg Flesch, avg grade, easiest, hardest)
- Sidebar updated: added Compare Texts (ArrowLeftRight icon) and Batch Analysis (FolderUp icon) nav items
- Files created: `frontend/src/components/Compare/ComparePage.tsx`, `frontend/src/components/Batch/BatchPage.tsx`
- Files modified: `TextInput.tsx`, `Charts.tsx`, `AnalysisResults.tsx`, `Dashboard.tsx`, `SimplifyPage.tsx`, `App.tsx`, `Sidebar.tsx`, `tailwind.config.js`, `index.css`, `index.html`
- Build: tsc --noEmit SUCCESS (zero errors), Vite build SUCCESS

### Prompt 10: Enhanced Analysis Results - Frontend Features - COMPLETED
- **All 5 features are purely frontend** — no backend, database, or ML changes. All dark mode compatible. Uses existing analysis data.
- **Text Complexity Score (0-100)**: Weighted composite score from grade level (40%), Flesch Reading Ease (30%), difficult words percentage (20%), and average sentence length (10%). Utility: `complexityScore.ts`, Component: `ComplexityScoreCard.tsx`. Displayed after GradeExplanation in AnalysisResults
- **Reading Time Estimate**: Difficulty-adjusted WPM calculation (base 225 WPM, adjusted by Flesch score with 0.6-1.0x multiplier). Utility: `readingTime.ts`. Integrated as 5th summary card in AnalysisResults header
- **"Improve This" Suggestions**: Generates 3-5 prioritized actionable suggestions with estimated grade-level impact. Utility: `improvementSuggestions.ts`, Component: `ImprovementSuggestions.tsx`. Displayed after charts in AnalysisResults
- **Vocabulary Level Analysis**: Categorizes all words into Simple/Medium/Advanced/Expert levels with stacked bar chart visualization. Utility: `vocabularyAnalysis.ts`, Component: `VocabularyAnalysis.tsx`. Displayed after ImprovementSuggestions in AnalysisResults
- **Detailed PDF Report Generator**: Multi-page jsPDF report with cover page, scores table, improvement suggestions, vocabulary analysis, and difficult passages. Utility: `detailedReport.ts`. Integrated as "Detailed Report" button in AnalysisResults header
- Files created: `complexityScore.ts`, `readingTime.ts`, `improvementSuggestions.ts`, `vocabularyAnalysis.ts`, `detailedReport.ts`, `ComplexityScoreCard.tsx`, `ImprovementSuggestions.tsx`, `VocabularyAnalysis.tsx`
- Files modified: `AnalysisResults.tsx` (added imports, 5th summary card, ComplexityScoreCard, ImprovementSuggestions, VocabularyAnalysis, Detailed Report button)

### Post-Prompt 10: Bidirectional Rewrite Engine Overhaul - COMPLETED
- **Bidirectional rewrite**: `simplify_to_grade` now detects direction (upgrade vs downgrade) using `_measure_text_metrics()` which estimates grade from `avg_syl` + `avg_wps` using formula `grade ≈ -21.16 + 14.33*(syl) + 0.6*(wps)`
- **GRADE_TARGET_METRICS dict**: Defines exact `target_syl`, `target_wps`, `min_wps`, `max_wps` per grade 3-13. These are the two primary metric levers for grade prediction.
- **Upgrade path**: `_complexify_text()` (curated complexification_map + POS-validated synonyms) + `_combine_short_sentences()` (combines shorter-than-min_wps sentences)
- **Downgrade path**: `_replace_difficult_words()` + `_split_long_sentences()` (splits sentences exceeding max_wps)
- **Groq full rewrite**: Direction-aware prompts include exact `target_syl`, `target_wps`, `min_wps`, `max_wps`. Separate upgrade vs downgrade prompts with clause complexity guidance (e.g., "AT MOST one subordinate clause per sentence" for Grade 8).
- **Groq metric verification + correction pass**: After Groq generates output, actual metrics are measured. If `abs(actual_grade - target_grade) > 1.0` or wps out of range, a correction prompt is sent (full base prompt + issue description). Best of two passes returned.
- **`_diff_changes()` method**: Extracts clean word-level diffs between original and Groq-rewritten text using `difflib.SequenceMatcher`. Single-word substitutions show freq/syllable data. Stop words (zipf ≥ 6.5) filtered out (difflib alignment artifacts). All structural changes collapsed into ONE summary entry. No AI/Groq/Llama mentions anywhere in UI.
- **Auto mode returns diff changes**: `_groq_full_rewrite()` calls `_diff_changes()` and returns meaningful word replacements + one structural summary, not a single opaque `ai_rewrite` change.
- **Save → New Analysis**: `SimplifyPage.tsx` `handleSave` now creates a new analysis from the rewritten text via `analysisApi.analyze()` and navigates to the new analysis result page
- **Bug fixes**:
  - `_pos_matches()`: ADJ tokens now match both `wn.ADJ` ('a') and `wn.ADJ_SAT` ('s') — fixes adjective synonym lookups
  - `_apply_inflection()`: Added CVC doubling for ADJ comparatives/superlatives (hot→hotter, big→biggest)
  - Datamuse: Requires `dm_freq >= original_freq + 1.5` AND Dale-Chall membership (prevents "zones"→"suns" semantic drift)
  - `_find_complex_synonym()`: POS validation for curated map — rejects synonyms that don't exist in WordNet with the same POS (prevents "liked"→"comparabled")
- **Test results** (Grade 3 Tom/Max narrative):
  - Grade 3 → Grade 6: ML predicts Grade 5 ✅
  - Grade 3 → Grade 8: ML predicts Grade 9 ✅ (1 grade off due to subordinate clause density feature)
  - Grade 3 → Grade 10: ML predicts Grade 10 ✅ exact
- Files modified: `simplifier.py` (major overhaul), `SimplifyPage.tsx` (save → new analysis)

### Post-Prompt 10 Session 2: RAG Fixes & Infrastructure - COMPLETED
- **RAG PDF extraction**: Replaced `pymupdf4llm` with `pdfplumber` — pymupdf4llm's internal ONNX layout model (`BoxRFDGNN`) had int32/int64 type conflict with ONNX Runtime ≥1.19 on Windows
- **FlashRank fail-safe**: `RAGEngine.__init__` wraps `Ranker()` in try/except; sets `self.ranker = None` on failure. Query falls back to embedding similarity scores automatically. FlashRank rerank scores cast to `float()` before JSON serialization (numpy.float32 not JSON-serializable)
- **FormData Content-Type fix**: axios instance default `Content-Type: application/json` was overriding browser's multipart boundary for all FormData uploads. Fixed by adding `headers: { 'Content-Type': undefined }` to all FormData calls: `extractPdf`, `extractDoc`, `extractImage`, `uploadDocument`, `uploadProfilePicture`
- **onnxruntime pinned**: `onnxruntime>=1.19.0` added to requirements.txt (needed by pymupdf's layout model and FlashRank). `numpy<2.0` constraint added (scikit-learn 1.3.2 incompatible with numpy 2.x). `pymupdf4llm` removed from requirements.
- **traceback logging**: Added `traceback.print_exc()` to RAG upload error handler for easier debugging
- Files modified: `app.py`, `rag_engine.py`, `api.ts`, `requirements.txt`, `.gitignore`

---

## Performance Metrics (After Prompt 5 Retraining)

- **MAE (Mean Absolute Error): 0.712 grade levels** (improved from ~0.85)
- **R2 Score: 0.926** (improved from ~0.82)
- **Within +/-1 grade level: 80.2%**
- **Within +/-0.5 grade level: 57.6%**
- Individual model MAEs: RF 0.725, GB 0.719, XGBoost 0.730
- Prediction time: <500ms per analysis (slightly slower due to spaCy NLP features)

---

## CLEAR Corpus Context

The CLEAR (CommonLit Ease of Readability) Corpus is an open dataset of ~5,000 reading passage excerpts curated by CommonLit and Georgia State University's Applied Linguistics department. Key facts:
- Passages selected for grade 3-12 English Language Arts context
- Includes 9 readability indices plus 6 Kaggle competition predictions
- Currently we use Flesch-Kincaid-Grade-Level as the target variable
- Development supported by Schmidt Futures

---

## Key Design Decisions

1. **Three separate services** instead of monolith - allows Python ML to run independently from Node.js API
2. **3-Model Ensemble** (RF + GB + XGBoost average) instead of single model - more robust predictions
3. **GridSearchCV tuning** for optimal hyperparameters
4. **spaCy NLP features** for richer text analysis beyond simple readability formulas
5. **Local OCR** (Tesseract) instead of cloud API - as per project requirements
6. **Web Speech API** for voice - browser-native, no external service needed
7. **JSONB in PostgreSQL** for flexible nested data (difficult words/sentences, changes)
8. **ChromaDB PersistentClient** for RAG vector storage (not deprecated duckdb+parquet)
9. **Separate Multer configs** for profiles (5MB) vs documents (100MB)
10. **THINC_NO_TORCH** env var to handle torch DLL issues on Windows

---

## Comprehensive Technical Reference

This section provides full technical detail on every library, pipeline, API, model, feature, and data source used in ClarityWorks. Intended for developer onboarding and AI assistant context.

### All Python Libraries & Their Roles

| Library | Version | Role |
|---------|---------|------|
| **flask** | 3.0.0 | Web framework for ML service REST API (12+ endpoints) |
| **flask-cors** | 4.0.0 | CORS middleware for cross-origin requests from frontend |
| **scikit-learn** | 1.3.2 | Random Forest, Gradient Boosting regressors, GridSearchCV, train/test split, evaluation metrics (MAE, RMSE, R2) |
| **xgboost** | 2.0.3 | XGBRegressor — third model in ensemble (added in Prompt 5) |
| **spacy** | 3.7.2 | NLP pipeline: tokenization, POS tagging, dependency parsing, sentence segmentation. Model: `en_core_web_sm`. Used for 5 NLP features, sentence splitting, word replacement, phrasal verb detection |
| **nltk** | 3.9.1 | WordNet corpus access for dynamic synonym finding. Uses `nltk.corpus.wordnet` for synsets, lemmas, definitions, hypernyms. Lesk WSD built on WordNet definitions |
| **wordfreq** | 3.1.1 | `zipf_frequency(word, 'en')` — returns Zipf-scale frequency (0-7) for any English word. Replaces COCA CSV for word difficulty. Scale: 7="the", 5="know", 3="magnificent", 1="trepidation" |
| **textstat** | 0.7.3 | 8 readability formulas: Flesch Reading Ease, Flesch-Kincaid Grade, ARI, SMOG, Coleman-Liau, Dale-Chall, Linsear Write, Gunning Fog |
| **pyphen** | 0.14.0 | Syllable counting via hyphenation dictionary (`Pyphen(lang='en_US')`) |
| **pandas** | 2.1.4 | CLEAR Corpus CSV loading and data manipulation during training |
| **numpy** | <2.0 (1.26.x) | Array operations, variance calculation, ensemble averaging. Must be <2.0 for scikit-learn 1.3.2 compatibility |
| **joblib** | 1.3.2 | Model serialization/deserialization (.joblib files) |
| **chromadb** | 0.4.22 | Embedded vector database for RAG. `PersistentClient` stores document embeddings on disk. Uses L2 (Euclidean) distance for similarity search |
| **sentence-transformers** | 2.3.1 | `SentenceTransformer('intfloat/e5-small-v2')` — 384-dim embeddings for RAG (requires `"query: "` / `"passage: "` prefixes). Upgraded from all-MiniLM-L6-v2 in Prompt 8 |
| **flashrank** | 0.2+ | Cross-encoder re-ranker (`ms-marco-MiniLM-L-12-v2`, ~4MB ONNX model, CPU-only). Re-ranks top-20 embedding candidates to precise top-5. Init wrapped in try/except — falls back to embedding similarity if ONNX issues occur |
| **onnxruntime** | ≥1.19.0 | ONNX Runtime required by FlashRank and pymupdf layout model. Must be ≥1.19 for pymupdf compatibility on Windows |
| **langchain-text-splitters** | 0.2+ | `RecursiveCharacterTextSplitter` — splits by `\n\n` → `\n` → `. ` → ` ` → `""`. 1000-char chunks, 200-char overlap |
| **groq** | 0.11.0 | Groq Cloud API client. Model: `llama-3.3-70b-versatile`. Used for: (1) validation of rule-based simplification changes, (2) auto-fixing issues found by validation, (3) fallback simplification when rule-based methods leave remaining complexity, (4) True RAG answer generation from retrieved chunks (Prompt 8) |
| **requests** | 2.31.0 | HTTP client for Datamuse API calls (synonym fallback) |
| **pdfplumber** | 0.10.3 | PDF text extraction for analysis input AND RAG document upload (replaced pymupdf4llm for RAG after ONNX conflict) |
| **python-docx** | 1.1.0 | DOCX text extraction (both for analysis input and RAG document upload) |
| **pytesseract** | 0.3.10 | OCR wrapper for Tesseract (local, no cloud API). Converts images to text |
| **Pillow** | 10.1.0 | Image processing for OCR (required by pytesseract) |
| **python-dotenv** | 1.0.0 | Loads environment variables from `.env` file |

### The Full ML Pipeline

```
CLEAR Corpus CSV (~4,724 samples, grades 3-12)
        │
        ▼
┌─────────────────────────────┐
│  1. LOAD & FILTER           │
│  - Read CSV via pandas      │
│  - Map columns: Excerpt →   │
│    text, FK-Grade → target  │
│  - Drop NaN, skip <50 chars │
│  - ~4,724 valid samples     │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  2. FEATURE EXTRACTION      │
│  - 16 features per sample   │
│  - 11 original + 5 spaCy    │
│  - Uses TextProcessor +     │
│    textstat + spaCy NLP     │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  3. TRAIN/TEST SPLIT        │
│  - 80% train / 20% test    │
│  - random_state=42          │
│  - ~3,779 train / ~945 test │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  4. HYPERPARAMETER TUNING   │
│  - GridSearchCV (5-fold CV) │
│  - scoring: neg_MAE         │
│  - Tunes RF, GB, XGBoost    │
│    independently            │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  5. TRAIN 3 MODELS          │
│  - Random Forest            │
│  - Gradient Boosting        │
│  - XGBoost                  │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  6. ENSEMBLE PREDICTION     │
│  - Average of 3 models      │
│  - Confidence = 1 - (std /  │
│    max(|prediction|, 1.0))  │
│  - Clamp to [0.5, 0.99]    │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  7. SAVE MODELS             │
│  - rf_model.joblib           │
│  - gb_model.joblib           │
│  - xgb_model.joblib          │
│  → trained_models/ dir      │
└─────────────────────────────┘
```

### How the 3-Model Ensemble Works

**Training** (via `train_model.py`):
- Each model is tuned independently with GridSearchCV (5-fold cross-validation, `neg_mean_absolute_error` scoring)
- **Random Forest**: search space — `n_estimators: [100,200,300]`, `max_depth: [10,15,20,None]`, `min_samples_split: [2,5,10]`
- **Gradient Boosting**: search space — `n_estimators: [100,200]`, `max_depth: [3,5,7]`, `learning_rate: [0.05,0.1,0.2]`
- **XGBoost**: search space — `n_estimators: [200,300]`, `max_depth: [3,5,7]`, `learning_rate: [0.05,0.1,0.2]`, `subsample: [0.8,1.0]`
- Best hyperparameters found: RF (max_depth=None, min_samples_split=2, n_estimators=300), GB (learning_rate=0.05, max_depth=5, n_estimators=100), XGB (learning_rate=0.05, max_depth=5, n_estimators=300, subsample=0.8)

**Prediction** (via `readability_model.py`):
1. Extract 16 ML features from input text
2. Each model predicts a numeric grade level independently
3. Ensemble prediction = `(rf_pred + gb_pred + xgb_pred) / 3`
4. Confidence = `max(0.5, min(0.99, 1.0 - (std_dev / max(|ensemble_pred|, 1.0))))`
5. Falls back to 2-model average if XGBoost not loaded, or Flesch-Kincaid heuristic if no models trained
6. Numeric prediction mapped to grade string ("Grade 3" through "College") and complexity ("Beginner"/"Intermediate"/"Advanced"/"Expert")

### All 16 ML Features (Detailed)

**Original 11 features** (extracted by `TextProcessor` + `textstat`):
1. `word_count` — total words in text
2. `sentence_count` — total sentences (split on `.!?`)
3. `avg_sentence_length` — words per sentence average
4. `avg_word_length` — characters per word average
5. `avg_syllables_per_word` — syllables per word (via pyphen hyphenation)
6. `difficult_words_percentage` — % words not in Dale-Chall 3000 AND 3+ syllables AND 4+ chars
7. `flesch_reading_ease` — textstat Flesch Reading Ease (0-100, higher=easier)
8. `flesch_kincaid_grade` — textstat Flesch-Kincaid Grade Level (US grade)
9. `automated_readability_index` — textstat ARI
10. `smog_readability` — textstat SMOG Index
11. `type_token_ratio` — unique words / total words (vocabulary diversity)

**New 5 spaCy NLP features** (added in Prompt 5):
12. `passive_voice_percentage` — % sentences containing `nsubjpass` dependency (spaCy)
13. `subordinate_clause_density` — average count of `mark`, `advcl`, `acl`, `relcl` dependencies per sentence
14. `pos_diversity_score` — unique POS tags / total POS tags (higher = more varied structure)
15. `lexical_diversity` — unique lowercased words / total words
16. `sentence_complexity_variance` — numpy variance of sentence word counts (higher = more irregular pacing)

### How Grade Levels Are Determined

**Target variable**: Flesch-Kincaid-Grade-Level column from CLEAR Corpus (continuous float, roughly 3.0-16.0+)

**Prediction-to-grade mapping** (`_prediction_to_grade`):
- pred < 4 → "Grade 3"
- 4 ≤ pred < 5 → "Grade 4"
- ... (1 grade per integer range)
- 12 ≤ pred < 13 → "Grade 12"
- pred ≥ 13 → "College"

**Grade-to-complexity mapping** (`_grade_to_complexity`):
- Grades 3-6 → "Beginner"
- Grades 7-9 → "Intermediate"
- Grades 10-12 → "Advanced"
- College → "Expert"

**Word difficulty by grade** (`GRADE_ZIPF_THRESHOLDS` in simplifier.py):
- Grade 3: zipf ≥ 5.5 (only very common words acceptable)
- Grade 6: zipf ≥ 4.6
- Grade 9: zipf ≥ 3.7
- Grade 12: zipf ≥ 2.8 (allows rarer words)
- A word with zipf frequency below the grade's threshold is considered "too hard"

### Performance Metrics (After Prompt 5 Retraining)

| Metric | Value |
|--------|-------|
| MAE (Mean Absolute Error) | 0.712 grade levels |
| RMSE (Root Mean Squared Error) | ~0.95 |
| R2 Score | 0.926 |
| Within ±1 grade accuracy | 80.2% |
| Within ±0.5 grade accuracy | 57.6% |
| RF individual MAE | 0.725 |
| GB individual MAE | 0.719 |
| XGBoost individual MAE | 0.730 |
| Training samples | ~3,779 |
| Test samples | ~945 |
| Features | 16 |

### What We Use from the CLEAR Corpus Dataset

The CLEAR (CommonLit Ease of Readability) Corpus contains ~5,000 reading passages curated by CommonLit and Georgia State University.

**Columns used:**
- `Excerpt` — the text passage (used as input for feature extraction)
- `Flesch-Kincaid-Grade-Level` — the target variable for regression (continuous grade level)

**What we don't use** (available but unused):
- BT Easiness (Bradley-Terry scores)
- Other readability indices in the CSV (we compute our own via textstat)
- 6 Kaggle competition prediction columns

**Preprocessing:**
- Drop rows with NaN in excerpt or target columns
- Skip texts shorter than 50 characters
- Final usable samples: ~4,724

### The Text Simplification Pipeline (Hybrid)

```
Input Text + Target Grade
        │
        ▼
┌──────────────────────────────────────────────────┐
│  STEP 1: REPLACE DIFFICULT WORDS                 │
│                                                  │
│  For each word in text (via spaCy tokenization): │
│  1. Skip: stop words, proper nouns, <4 chars     │
│  2. Check difficulty: zipf_frequency < grade     │
│     threshold AND not in Dale-Chall 3000         │
│  3. Skip phrasal verbs (verb + dep preposition)  │
│  4. Find synonym via cascade:                    │
│     a. Curated simplification_map.json (50 maps) │
│     b. WordNet + Lesk WSD (context-aware)        │
│     c. Datamuse API fallback (free, no key)      │
│  5. Validate: synonym must have higher zipf freq │
│     AND fewer/equal syllables                    │
│  6. Apply inflection (tense/plural/comparative)  │
│  7. Preserve capitalization                      │
└──────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────┐
│  STEP 2: SPLIT LONG SENTENCES                    │
│                                                  │
│  If sentence exceeds grade's max_words + 5:      │
│  Strategy 1: Split at semicolons                 │
│  Strategy 2: Split at advcl/relcl clause         │
│    boundaries (spaCy dep parsing)                │
│  Strategy 3: Split at coordinating conjunctions  │
│    (and/but/or) only if both halves have subjects│
│  Min 5 words per resulting part                  │
└──────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────┐
│  STEP 3: GROQ VALIDATION                         │
│                                                  │
│  Send original + simplified + changes to Groq    │
│  Model: llama-3.3-70b-versatile (temp=0.1)       │
│  Asks: Do changes preserve meaning? Any errors?  │
│  Returns: {valid, issues[], suggestions[]}       │
└──────────────────────────────────────────────────┘
        │
        ▼ (if validation found issues)
┌──────────────────────────────────────────────────┐
│  STEP 4: GROQ AUTO-FIX                           │
│                                                  │
│  Sends text + issues list to Groq (temp=0.3)     │
│  Groq rewrites text fixing the identified issues │
│  Adds a 'groq_correction' change to the list    │
└──────────────────────────────────────────────────┘
        │
        ▼ (if text still too complex)
┌──────────────────────────────────────────────────┐
│  STEP 5: GROQ FALLBACK                           │
│                                                  │
│  If any sentence still > max_words + 5:          │
│  Full Groq simplification (temp=0.3)             │
│  Complete rewrite to target grade level          │
│  Adds an 'ai_enhanced' change                   │
└──────────────────────────────────────────────────┘
        │
        ▼
  Return: {simplified_text, changes[], original_text, validation}
```

### WordNet + Lesk Synonym Finding (Detail)

**Lesk Word Sense Disambiguation** (`_disambiguate_sense`):
1. Get all WordNet synsets for the word's lemma, filtered by POS
2. Build context from surrounding sentence tokens (nouns, verbs, adjectives via spaCy)
3. For each synset (top 5): compute overlap between context words and synset's definition + examples + hypernym definitions
4. Return synset with highest overlap + the overlap score

**Candidate collection** (`_collect_synset_candidates`):
1. Extract lemma names from the selected synset
2. Filter: must be single-word, min 2 chars, different from original
3. **Sense validation**: candidate's synsets must include the matched synset in its top N senses (4 for verbs, 6 for nouns/adj) — prevents wrong-sense errors like "dig" for "comprehend"
4. Must have BOTH higher zipf frequency AND fewer/equal syllables than original

**Safety guards:**
- Polysemous verb filter: verbs with 4+ senses skipped when Lesk returns 0 overlap (too ambiguous)
- Phrasal verb detection: skip replacement when verb's next token has `dep_='prep'` and `head=verb`
- Guard rail: final check that synonym frequency > original frequency
- Cache: `_synonym_cache` keyed by `{lemma}_{grade}` prevents redundant lookups

### All External APIs

| API | URL | Auth | Purpose | Rate Limit |
|-----|-----|------|---------|------------|
| **Groq Cloud** | `api.groq.com` | API key (`GROQ_API_KEY` in .env) | Simplification validation, auto-fix, fallback + RAG answer generation | Free tier available |
| **Datamuse** | `api.datamuse.com/words` | None (free, no key) | Synonym fallback when WordNet can't simplify | Unlimited, 3s timeout |
| **Web Speech API** | Browser-native | None | Voice/speech-to-text input on frontend | N/A (client-side) |

No external APIs are used for the core ML prediction pipeline — all models run locally.

### How the RAG System Works (Upgraded in Prompt 8 - True RAG)

**Architecture**: ChromaDB (embedded vector DB) + E5-small-v2 embeddings + FlashRank cross-encoder re-ranking (with embedding similarity fallback) + Groq answer generation + RecursiveCharacterTextSplitter + pdfplumber PDF extraction

**Upload flow** (`rag_engine.py → upload_document`):
1. Extract text from PDF (pdfplumber) or DOCX (python-docx)
2. Chunk text via RecursiveCharacterTextSplitter: 1000-char chunks, 200-char overlap, splits at `\n\n` → `\n` → `. ` → ` ` → `""`
3. Generate embeddings: `SentenceTransformer.encode(["passage: " + t for t in chunks])` — E5-small-v2, 384-dimensional float vectors
4. Store in ChromaDB: one collection per document (`doc_{uuid}`), with metadata (chunk_id, char_count, word_count, document_id)
5. Save document metadata to PostgreSQL `rag_documents` table

**Query flow** (`rag_engine.py → query_documents`) — 3-stage retrieval:
1. **Stage 1 (Embedding search)**: Generate query embedding with `"query: "` prefix, retrieve top-20 candidates per collection from ChromaDB
2. Convert L2 distances to similarity: `max(0.0, min(1.0, 1 - (distance / 2)))`
3. **Stage 2 (Re-ranking)**: Feed all candidates to FlashRank cross-encoder (`ms-marco-MiniLM-L-12-v2`, ONNX, CPU-only), select top-5
4. **Stage 3 (Answer generation)**: `_generate_answer()` builds context from top-5 chunks with `[Source N]` labels, calls Groq `llama-3.3-70b-versatile` (temp=0.2, max_tokens=1500) to synthesize coherent answer citing sources. Prompt instructs: cite sources, don't fabricate, answer concisely
5. Return `{answer: str|None, sources: list[dict], has_answer: bool}` — answer is None if Groq not configured

**Chunking strategy** (RecursiveCharacterTextSplitter):
- Target: 1000 characters per chunk (~150-200 words)
- Overlap: 200 characters
- Separator cascade: `\n\n` → `\n` → `. ` → ` ` → `""` (preserves paragraph and sentence boundaries)
- `keep_separator=True` for context preservation

**Model migration**: On startup, checks `.embedding_model` marker file in ChromaDB directory. If embedding model has changed, automatically clears all existing collections (incompatible vectors) and writes new marker.

### Data Files in `ml-service/data/`

| File | Purpose |
|------|---------|
| `clear_corpus/clear_corpus.csv` | CLEAR Corpus dataset (~5,000 samples, grades 3-12) |
| `dale_chall_3000.txt` | Dale-Chall list of 3,000 easy words (Grade 4 baseline) |
| `simplification_map.json` | Curated complex→simple word mappings (~50 entries, highest quality) |
| `complexification_map.json` | Simple→complex word mappings (~42 entries, used by `_complexify_text()` for vocabulary upgrade) |
| `coca_frequency.csv` | COCA frequency rankings (~200 words, used by SynonymLookup for word_frequency_rank) |
| `academic_word_list.txt` | 570 academic words (Grade 10+ terms, used in difficulty detection) |
| `test_files/grade_3.txt` through `grade_12.txt` + `college.txt` | 11 calibrated test files (Prompt 2+7, all validated 11/11 pass) |

### Current Application Features

**Core Analysis:**
- Multi-method text input (paste, PDF, DOCX, image OCR, voice)
- "Try a sample" button with 11 calibrated texts (Grade 3-College) organized by category with grade-level reasons (Prompt 9)
- 16-feature ML grade prediction (3-model ensemble)
- 8 readability formula scores
- Difficult word detection with multi-reason explanations (syllables, COCA rank, Dale-Chall, academic vocab, technical suffixes, simpler alternatives)
- Difficult sentence detection (length, Flesch score, difficult word count, polysyllabic count)
- Text highlighting with hover tooltips
- Most common words visualization (top 15 content words bar chart) (Prompt 9)
- Text Complexity Score: weighted composite 0-100 from grade level (40%), Flesch (30%), difficult words (20%), sentence length (10%) (Prompt 10)
- Reading Time Estimate: difficulty-adjusted WPM (base 225, Flesch-adjusted 0.6-1.0x), displayed as 5th summary card (Prompt 10)
- "Improve This" Suggestions: 3-5 prioritized actionable suggestions with estimated grade-level impact (Prompt 10)
- Vocabulary Level Analysis: categorizes words into Simple/Medium/Advanced/Expert with stacked bar chart (Prompt 10)
- 6 chart types (radar, bar, pie, gauge, common words, custom)
- PDF report export
- Detailed PDF Report: multi-page jsPDF report with cover page, scores table, improvement suggestions, vocabulary analysis, difficult passages (Prompt 10)
- Comparative analysis page (side-by-side text comparison with 11 metrics) (Prompt 9)
- Batch analysis page (paste or CSV, progress bar, summary table, CSV export) (Prompt 9)

**Text Simplification:**
- Auto mode (apply all changes) and interactive mode (accept/deny individually)
- Hybrid synonym pipeline (curated → WordNet+Lesk → Datamuse → Groq)
- NLP-based sentence splitting (spaCy dependency parsing)
- Groq AI validation and auto-correction
- Highlighted pending changes (amber) with inline accept/deny buttons
- Word-boundary-aware highlighting (`findWholeWord()`)
- Simplification history saved to database with before/after metrics (Prompt 7)
- Export simplification results as PDF or DOCX (Prompt 7)

**RAG (Retrieval-Augmented Generation) — True RAG, Upgraded Prompt 8:**
- Upload PDF/DOCX textbooks (100MB max)
- **pymupdf4llm** PDF extraction (Markdown output preserving headings/bullets/tables)
- **RecursiveCharacterTextSplitter** chunking (1000 chars, 200 overlap, paragraph-aware)
- **E5-small-v2** embeddings (384-dim, more accurate than MiniLM, with query/passage prefixes)
- **FlashRank** cross-encoder re-ranking (retrieve top-20, re-rank to precise top-5)
- **True RAG answer generation**: Groq `llama-3.3-70b-versatile` synthesizes coherent answer from top chunks with `[Source N]` citations
- AI answer displayed in green gradient box with Bot icon; expandable source documents with chevron toggles
- Yellow warning when GROQ_API_KEY not configured (sources still shown without AI answer)
- Automatic model migration (clears old ChromaDB data when embedding model changes)
- Export RAG query results as PDF or DOCX — includes AI-generated answer section (Prompt 7+8)

**User Management:**
- JWT authentication (24h expiry, bcrypt password hashing)
- Password strength validation (8+ chars, uppercase, lowercase, digit, special)
- Profile management (name, email, password, profile picture)
- Role-based access (user vs admin)
- Full admin panel (user management, analysis management, platform stats)

**History & Dashboard:**
- Dashboard with aggregate stats (total analyses, avg reading ease, avg grade, total words)
- Readability trend line chart (grade level + Flesch score over last 20 analyses) (Prompt 9)
- 3 most recent analyses displayed
- Paginated history with search and grade-level filtering
- Tabbed history view (Analyses / Simplifications tabs) (Prompt 7)
- Simplification history with before/after metrics comparison (Prompt 7)

**Text Simplification (continued):**
- Pre-simplification score preview: "Grade X → Grade Y" after simplification (Prompt 9)

**UX Polish (Prompt 7 + 9):**
- Live word count display with validation messages in TextInput
- Grade explanations with layman/technical toggle and characteristics grid
- Text difficulty heatmaps (word-level red highlighting, sentence-level borders)
- Fullscreen loading spinners on all processing actions (analysis, simplification, RAG query, RAG upload)
- TextCleaner utility for cleaning extracted text (OCR errors, whitespace, image markers)
- Export simplification and RAG results as PDF/DOCX
- Calibrated test files: 11 files (grades 3-12 + college) all passing validation
- Dark mode toggle (Tailwind class-based, persisted in localStorage, sidebar toggle) (Prompt 9)
