# ClarityWorks: The Text Simplification Engine (simplifier.py)

**File:** `ml-service/models/simplifier.py` (~5,200 lines — the largest and most complex file in the project)

This document explains every aspect of how ClarityWorks rewrites text to match a target grade level — both simplifying (downgrading) and upgrading (making more complex).

---

## 1. Overview: What Does the Simplifier Do?

Given:
- An original text (e.g., a college-level paragraph)
- A target grade (e.g., Grade 5)

It produces:
- A rewritten text at the target reading level
- A list of individual changes (word replacements, sentence splits/combines) that the user can accept or deny in interactive mode

The system is **bidirectional**: it can both simplify (Grade 12 → Grade 5) and upgrade (Grade 3 → Grade 9).

---

## 2. The Two Modes: Auto vs Interactive

- **Auto Mode**: The system applies all changes automatically and shows the user the result with a diff view. The user sees the final rewritten text with highlighted changes they can review.
- **Interactive Mode**: Each change is presented as a pending suggestion (highlighted in amber). The user clicks Accept or Deny on each one. Only accepted changes are applied.

Both modes use the same underlying rewrite pipeline — they differ only in how changes are presented.

---

## 3. The Rewrite Pipeline: Step by Step

### 3.1 Direction Detection

```python
def _measure_text_metrics(self, text):
    """Returns (estimated_grade, avg_syllables_per_word, avg_words_per_sentence)"""
```

First, the system measures the current text's grade level using the same ML model used for analysis (or a formula fallback: `grade ≈ -21.16 + 14.33 * avg_syl + 0.6 * avg_wps`). This determines the **direction**:

- If `target_grade > source_grade` → **upgrade** (make text harder)
- If `target_grade < source_grade` → **downgrade** (simplify text)
- If equal → no change needed

### 3.2 Policy Selection

The system selects a **policy** based on the target grade range and direction. Policies are defined in `DOWNGRADE_TARGET_BUCKET_POLICIES` and `UPGRADE_TARGET_BUCKET_POLICIES`:

```python
DOWNGRADE_TARGET_BUCKET_POLICIES = {
    '3-5': {   # Elementary school target
        'beam_width': 3,
        'lexical_rounds': 2,    # How many rounds of word replacement
        'lexical_max': 8,       # Max words to replace per round
        'split_rounds': 2,      # How many rounds of sentence splitting
        'combine_rounds': 0,    # No sentence combining when downgrading
        'syllable_weight': 1.4, # How much syllable accuracy matters in scoring
        'wps_weight': 0.22,     # How much words-per-sentence accuracy matters
        'paragraph_penalty': 0.8, # Penalty for rewriting whole paragraphs
    },
    '6-8': {...},  # Middle school
    '9-10': {...}, # High school
    '11-college': {...}, # Upper high school
}
```

Each bucket controls how aggressively the system rewrites. A Grade 3 target gets more lexical rounds, more splits, and higher penalties for using complex words.

### 3.3 Grade Target Metrics

The `GRADE_TARGET_METRICS` dictionary defines precise targets for each grade:

```python
GRADE_TARGET_METRICS = {
    3:  {'target_syl': 1.20, 'target_wps': 8,  'min_wps': 5,  'max_wps': 10},
    5:  {'target_syl': 1.32, 'target_wps': 12, 'min_wps': 8,  'max_wps': 16},
    8:  {'target_syl': 1.41, 'target_wps': 17, 'min_wps': 12, 'max_wps': 22},
    12: {'target_syl': 1.55, 'target_wps': 25, 'min_wps': 18, 'max_wps': 33},
    13: {'target_syl': 1.60, 'target_wps': 28, 'min_wps': 20, 'max_wps': 38},  # College
}
```

These are the two primary levers the ML model uses: **average syllables per word** and **average words per sentence**. These values were empirically calibrated by testing against the model's predictions.

---

## 4. Beam Search: How Candidates Are Generated and Chosen

### 4.1 What Is Beam Search?

Beam search is a search algorithm that explores multiple solution paths simultaneously, keeping only the top-k most promising ones at each step. In ClarityWorks, `k = BEAM_WIDTH = 3`.

Instead of committing to a single rewrite path, the system generates **3 candidate rewrites in parallel**, scores each one, and keeps the best. This is like editing a document three different ways and picking the best version.

### 4.2 The Candidate Generation Pipeline

The `_select_authoring_candidate()` method orchestrates the entire selection:

```
Original Text
      │
      ▼
┌──────────────────────────────────────────┐
│  1. Generate RULE-BASED candidates       │
│     _select_rewrite_candidate()          │
│     - Word replacement (synonyms)        │
│     - Sentence splitting/combining       │
│     - Discourse marker adjustment        │
│     Produces: 3 rule candidates          │
└──────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────┐
│  2. Generate LLM candidates              │
│     _generate_llm_candidates()           │
│     - Fireworks AI (Llama 3.3 70B)       │
│     - Direction-aware prompt             │
│     - Grade profile description          │
│     Produces: 1-2 LLM candidates         │
└──────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────┐
│  3. Target lock repair candidates        │
│     _target_lock_repair_candidates()     │
│     - Takes near-miss candidates         │
│     - LLM polishes them toward target    │
│     Produces: 0-4 repair candidates      │
└──────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────┐
│  4. RANK all candidates                  │
│     _rank_candidates()                   │
│     - Score each with _score_candidate() │
│     - Sort by score (lower = better)     │
│     - Apply validation flags             │
└──────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────┐
│  5. SELECT preferred candidate           │
│     _select_preferred_candidate()        │
│     - Pick lowest-scoring candidate      │
│     - Unless it has blocking flags       │
│     - Then try the next one              │
└──────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────────┐
│  6. Post-selection repair                │
│     - Target contract rescue             │
│     - Defence target fallback            │
│     - LLM validation + critic review     │
│     - LLM local repair pass              │
└──────────────────────────────────────────┘
      │
      ▼
  Final Rewritten Text + Changes List
```

### 4.3 How Candidates Are Scored

The `_score_candidate()` method computes a single score (lower = better) from ~15 dimensions:

```python
score = target_distance * 6.0                           # How far from target grade
score += abs(avg_syl - target_syl) * syllable_weight    # Syllable accuracy
score += abs(avg_wps - target_wps) * wps_weight         # Sentence length accuracy
score += invalid_sentence_delta * 24.0                  # New broken sentences (HEAVY penalty)
score += max(0, 0.88 - semantic_similarity) * 6.0       # Meaning drift
score += len(lexical_flags) * 3.5                       # Blocked/bad word substitutions
score += len(artifact_flags) * 20.0                     # LLM artifacts (headers, meta-commentary)
score += len(word_artifact_flags) * 18.0                # Unnatural word insertions
score += len(awkward_phrase_flags) * 14.0                # Awkward phrasing
score += len(protected_term_flags) * 18.0               # Missing names/proper nouns
score += len(summary_wrapup_flags) * 4.5                # LLM adding conclusions
score += paragraph_rewrites * paragraph_penalty          # Too many paragraph-level rewrites
```

Key insights:
- **Broken sentences** are penalised most heavily (24.0 per new invalid sentence) because they make text unreadable
- **Protected terms** (names, places) must be preserved — missing them costs 18.0 per term
- **Meaning drift** is measured by comparing lemma sets (spaCy) + sequence similarity (difflib)
- **LLM artifacts** like "Here is the rewritten text:" are heavily penalised

### 4.4 Semantic Similarity Scoring

```python
def _semantic_similarity_score(self, original_text, candidate_text):
    score = 0.45 * lemma_overlap + 0.35 * sequence_ratio + 0.20 * length_ratio
```

Three components:
1. **Lemma overlap (45%)**: Using spaCy, extract content-word lemmas from both texts, compute Jaccard similarity. "ran" and "running" both lemmatise to "run"
2. **Sequence ratio (35%)**: `difflib.SequenceMatcher` — measures character-level similarity
3. **Length ratio (20%)**: Shorter output / longer output — penalises large length changes

---

## 5. The Synonym Finding Pipeline

### 5.1 How We Find Simpler Words

When downgrading, the system needs to replace hard words with simpler ones. It uses a **cascade** — try each source in order, stop when one works:

```
For each difficult word in the text:
    │
    ▼
┌───────────────────────────────────────────────┐
│ 1. SUPPLEMENTAL_SIMPLIFICATIONS (curated map) │
│    ~80 high-quality hand-picked mappings       │
│    e.g., "methodology" → "way"                 │
│    e.g., "significant" → "big"                 │
└───────────────────────────────────────────────┘
    │ (not found?)
    ▼
┌───────────────────────────────────────────────┐
│ 2. simplification_map.json (curated file)     │
│    50 complex → simple mappings                │
│    Checked first, with POS validation          │
└───────────────────────────────────────────────┘
    │ (not found?)
    ▼
┌───────────────────────────────────────────────┐
│ 3. NLTK WordNet + Lesk WSD                    │
│    Dynamic synonym finding:                    │
│    a. Get all synsets for the word's POS        │
│    b. Lesk disambiguates the correct sense     │
│    c. Extract lemma names from that synset     │
│    d. Filter: must have higher Zipf frequency  │
│       AND fewer/equal syllables                │
│    e. Sense validation: reject if synonym's    │
│       top senses don't include the matched one │
└───────────────────────────────────────────────┘
    │ (not found?)
    ▼
┌───────────────────────────────────────────────┐
│ 4. Datamuse API (free, no key)                │
│    GET api.datamuse.com/words?ml=word&md=f    │
│    Returns similar words with frequency data   │
│    Filter: must be shorter + have freq data    │
│    Guard: must have Zipf >= original + 1.5     │
│           AND be in Dale-Chall list            │
└───────────────────────────────────────────────┘
    │ (not found?)
    ▼
  Skip this word (leave unchanged)
```

### 5.2 WordNet and Lesk — In Detail

**WordNet** is a large lexical database of English. Words are organised into **synsets** (sets of synonyms). For example, the word "big" belongs to synsets like {big, large} (adjective meaning "of considerable size") and {big, grown-up} (adjective meaning "adult").

**Lesk Word Sense Disambiguation** picks the *correct* synset for a word based on its sentence context:

1. Get all synsets for the word (filtered by POS: noun, verb, adjective, adverb)
2. For each synset, extract its definition + example sentences + hypernym definitions
3. Build a "context" from the surrounding sentence (nouns, verbs, adjectives via spaCy)
4. Count word overlap between context and each synset's definitions
5. The synset with the highest overlap is the correct sense

**Example:** The word "bank" in "I walked along the river bank":
- Synset 1: {bank} = "financial institution" — definition has "money", "deposit", "financial"
- Synset 2: {bank} = "sloping land beside water" — definition has "river", "water", "shore"
- Context words from sentence: "walked", "river"
- Synset 2 wins because "river" overlaps

### 5.3 Candidate Validation Guards

Every synonym candidate must pass several guards:

1. **Frequency guard**: Candidate must have Zipf frequency >= original + `MIN_FREQ_IMPROVEMENT` (0.8). Prevents replacing a word with an equally rare one.
2. **Syllable guard**: Candidate must have fewer or equal syllables. "demonstrate" (4 syl) → "show" (1 syl) is good; "demonstrate" → "illustrate" (3 syl) is rejected when targeting low grades.
3. **Sense validation**: The candidate's WordNet synsets must include the matched synset in their top N senses (4 for verbs, 6 for nouns/adj). Prevents "dig" being offered for "comprehend" because they share a rare synset.
4. **Polysemous verb filter**: Verbs with 4+ senses are skipped when Lesk returns 0 overlap (too ambiguous without context).
5. **Phrasal verb detection**: If the verb is followed by a preposition with `dep_='prep'` and `head=verb` (e.g., "attest to"), skip it — the preposition is part of the verb's meaning.
6. **Blocked synonyms list**: A hardcoded set of words that must never appear as synonyms (vulgar terms, semantically wrong common replacements like "dick" for "detective").

### 5.4 How We Find More Complex Words (Upgrade)

When upgrading, the reverse cascade applies:

1. **SUPPLEMENTAL_COMPLEXIFICATIONS** (curated): e.g., "show" → "demonstrate", "change" → "transform"
2. **complexification_map.json** (curated file): e.g., "use" → "utilize", "help" → "facilitate"
3. **Reverse curated map**: Automatically built by reversing `simplification_map.json`
4. **WordNet + POS validation**: Find synonyms with *lower* Zipf frequency but matching POS

---

## 6. Sentence Structural Changes

### 6.1 Sentence Splitting (Downgrade)

Long sentences are split at natural break points using spaCy's dependency parse:

1. **Semicolons**: Split at `;` (the easiest split)
2. **Adverbial/relative clauses**: Split at `advcl` or `relcl` dependency boundaries
3. **Coordinating conjunctions**: Split at "and", "but", "or" — but only if both halves contain a subject (verified by checking for `nsubj` dependency)
4. Minimum 5 words per resulting fragment (no choppy fragments)

### 6.2 Sentence Combining (Upgrade)

Short sentences are combined to increase average words-per-sentence:

- Join consecutive sentences that are shorter than `min_wps` for the target grade
- Use conjunctions or relative pronouns ("which", "who")
- Only combine if the result stays under `max_wps`

### 6.3 Discourse Marker Adjustment

Discourse markers (transition words) are swapped to match the target grade:

**Downgrade map:** `"consequently" → "so"`, `"furthermore" → "also"`, `"nevertheless" → "still"`

**Upgrade map:** `"also" → "furthermore"`, `"still" → "nevertheless"`, `"about" → "regarding"`

---

## 7. LLM Integration: Fireworks AI (Llama 3.3 70B)

### 7.1 When the LLM Is Used

The LLM is NOT used for every rewrite. It's used as:

1. **A candidate generator**: Produces 1-2 LLM-authored rewrites alongside 3 rule-based candidates
2. **A repair tool**: When rule-based candidates are off-target, the LLM gets one repair attempt
3. **A validator**: Reviews the final rewrite for meaning drift and issues
4. **A critic**: Ranks the top candidates and flags any that change meaning

### 7.2 The LLM Prompt Structure

Each LLM call includes:
- The original text
- The target grade level with a **grade profile** (a human-readable description of what that grade reads like)
- Precise numeric targets: `target_syl`, `target_wps`, `min_wps`, `max_wps`
- Direction-specific instructions (e.g., "AT MOST one subordinate clause per sentence" for Grade 8)
- Explicit rules: preserve names, don't add conclusions, don't change who did what

### 7.3 Rate Limiting and Budget

The system budgets LLM calls per request:
- **Small grade jumps (1-2 grades)**: 2 LLM calls max
- **Medium jumps (3-5 grades)**: 3 calls max
- **Large jumps (6+ grades) or downgrading to Grade 3-7**: 5 calls max

This prevents excessive API costs while ensuring difficult rewrites get enough LLM help.

### 7.4 LLM Artifact Stripping

LLMs often add unwanted prefixes ("Here is the rewritten text:") or postfixes ("Note: I changed X because Y"). The `_strip_llm_meta_commentary()` method removes these.

The system also detects and penalises **summary wrap-ups** — a common LLM failure where the model adds a concluding paragraph that wasn't in the original text. This is caught by matching against `SUMMARY_WRAPUP_PHRASES` like "Through this experience, we learn..." or "This shows the importance of...".

---

## 8. The Diff Engine: From Candidate Text to Change List

After selecting the best candidate, the system must produce a list of anchored changes that map to specific positions in the original text. This is how interactive mode knows which part of the original text each change corresponds to.

The `_diff_changes()` method uses `difflib.SequenceMatcher` to find word-level differences:

1. Tokenise both original and candidate text
2. Run SequenceMatcher to identify replaced, inserted, and deleted spans
3. For single-word substitutions, include Zipf frequency and syllable data
4. For structural changes (sentence splits, paragraph rewrites), collapse into summary entries
5. Filter out stop-word changes (Zipf >= 6.5) that are alignment artifacts, not real edits

Each change object includes:
- `id`, `start`, `end` (character positions in original text)
- `original` / `simplified` (before/after text)
- `reason` (human-readable explanation)
- `reason_code` (machine-readable code for UI rendering)
- `evidence` (frequency/syllable data)
- `explanation_items` (structured before/after metadata for the UI)
- `dependency_group_id` (groups changes that must be accepted together)

### 8.1 Change Application: apply_changes_by_span

The `apply_changes_by_span()` function in `utils/change_patches.py` applies selected changes to the original text using position tracking:

1. Sort changes by start position
2. Filter out overlapping spans (keep the first one encountered)
3. Walk through the original text, copying unchanged portions and inserting replacements
4. Return the final text

---

## 9. The LLM Validator (llm_validator.py)

The `LLMValidator` class provides four operations:

1. **`validate_changes()`**: Sends original + simplified + change list to the LLM. Asks: "Do these changes preserve meaning? Any incomplete sentences? Any subject/object swaps?" Returns `{valid, issues[], suggestions[]}`

2. **`critic_candidates()`**: Reviews the top 3 deterministic candidates. Returns which candidate to prefer and per-candidate reviews flagging meaning drift, awkward phrases, or wrong grade level.

3. **`local_repair()`**: Given a candidate with issues, asks the LLM to fix only the affected sentences/paragraphs without rewriting from scratch.

4. **`polish_text()`**: Final bounded repair pass. Can rewrite affected sentences but must preserve facts, paragraph count, and scope.

---

## 10. Greedy Change Selection

After producing the full change list, the system runs `_greedy_select_changes_for_target()`:

1. Start with no changes applied
2. For each change, temporarily apply it and measure the resulting grade
3. If the grade moves closer to the target, keep the change
4. If it moves away, discard it
5. Repeat up to `AUTO_GREEDY_MAX_MEASUREMENTS` (40) iterations

This ensures that even if the LLM overshoots, the system can back off to the closest-to-target subset of changes.

---

## 11. Key Data Structures in simplifier.py

### Grade Profiles (GRADE_PROFILES)

Human-readable descriptions of what each grade level "reads like":

- **Grade 3**: "Very short sentences (5-10 words). Only common 1-syllable words. Simple subject-verb-object structure."
- **Grade 8**: "Medium-long sentences (12-22 words). Academic vocabulary. One subordinate clause per sentence is typical."
- **College**: "Very long sentences (20-38 words). Professional academic vocabulary with discipline-specific terminology."

These are included in LLM prompts so the model understands the target style.

### Blocked Synonyms (BLOCKED_SYNONYMS)

Words that must never be used as replacements regardless of frequency: vulgar terms, semantically wrong common replacements like "dick" (which WordNet maps from "detective"), "frame-up", "stool".

### Leading/Mid-Sentence Split Markers

Sets of conjunctions and adverbs that signal valid sentence split points. The system checks that both resulting fragments have subjects before splitting.
