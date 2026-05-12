# ClarityWorks: Complete Project Reference for Bachelor's Defence

**Author:** Junaid Ahsan Malik
**Programme:** Bachelor's of Computer Science
**Document Purpose:** Full technical reference for FYP oral defence

---

## 1. What Is ClarityWorks?

ClarityWorks is a full-stack web application that analyses how difficult a piece of text is to read, predicts which school grade level can understand it, and can automatically rewrite the text to make it easier or harder. It also lets users upload textbooks and ask natural-language questions about their content.

The system combines **traditional readability formulas** (well-established mathematical equations used since the 1940s-1970s) with **machine learning** (a 3-model ensemble trained on ~5,000 professionally graded reading passages) and **large language model augmentation** (Llama 3.3 70B via Fireworks AI for text rewriting and answer generation).

### The Problem It Solves

A teacher, editor, or content creator often needs to know: "Is this text appropriate for my audience?" Existing tools give a single readability score. ClarityWorks goes further:

1. **Analyses** text across 8 readability formulas and 16 ML features simultaneously
2. **Predicts** a specific US grade level (Grade 3-12 or College) with a confidence score
3. **Explains** why the text is at that level (difficult words, long sentences, passive voice, subordinate clauses)
4. **Rewrites** text to any target grade level — both simplifying and upgrading — using a hybrid rule-based + LLM pipeline
5. **Answers questions** about uploaded textbooks using Retrieval-Augmented Generation (RAG)
6. **Visualises** the concept prerequisite graph of a text — what a reader needs to know before the text makes sense

---

## 2. Architecture: Three-Tier Microservice Design

```
 User's Browser (React SPA)           Node.js REST API              Python ML Service
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━          ━━━━━━━━━━━━━━━━━              ━━━━━━━━━━━━━━━━━━
 React 18 + TypeScript                 Express.js + TS               Flask + scikit-learn
 Vite dev server                       JWT auth                      spaCy NLP
 TailwindCSS                           PostgreSQL driver             XGBoost
 Recharts                              File upload (Multer)          ChromaDB
 ReactFlow (concept graphs)            Axios → ML Service            Sentence-Transformers
 Port 5173                             Port 5000                     FlashRank (ONNX)
                                                                     Fireworks AI (LLM)
        │                                    │                             Port 5001
        │──── HTTP/REST ────────────────────>│                               │
        │                                    │──── HTTP/REST ───────────────>│
        │                                    │                               │
        │                                    │──── PostgreSQL ──────────────>│
        │                                    │     Port 5432                 │
        │                                    │                               │──── ChromaDB (embedded)
```

### Why Three Separate Services?

1. **Separation of concerns**: Python's ML ecosystem (scikit-learn, spaCy, XGBoost) is incompatible with Node.js. Running them as separate processes avoids language interop complexity.
2. **Independent scaling**: The ML service is CPU-intensive (model inference, NLP parsing). It can be scaled independently.
3. **Independent deployment**: A bug in the ML model doesn't crash the auth/database layer.
4. **Technology fit**: Node.js handles high-concurrency HTTP well (auth, file routing). Python handles numerical computation and NLP well.

### The Database

PostgreSQL 14 with 5 tables: `users`, `analyses`, `simplification_history`, `rag_documents`, `rag_queries`. Tables are auto-created on backend startup. The analyses table stores results as JSONB columns for flexible nested data (arrays of difficult words/sentences).

---

## 3. The ML Pipeline: How We Predict Grade Level

### 3.1 The Dataset: CLEAR Corpus

The **CLEAR (CommonLit Ease of Readability) Corpus** is an open dataset of ~5,000 reading passage excerpts curated by CommonLit and Georgia State University. Each passage is a real text excerpt used in grades 3-12 English Language Arts classrooms, with a professionally assessed **Flesch-Kincaid Grade Level** score.

We use:
- `Excerpt` column as input text
- `Flesch-Kincaid-Grade-Level` column as the regression target (continuous float, roughly 3.0-16.0+)

After filtering (dropping NaN, skipping texts <50 characters), we have ~4,724 usable samples.

### 3.2 Feature Extraction: 16 Features

For each text, we extract **16 numerical features** that capture different aspects of reading difficulty. These are defined in `feature_extractor.py` and `text_processor.py`.

#### Original 11 Features (computed by TextProcessor + textstat)

| # | Feature | How It's Calculated | What It Captures |
|---|---------|---------------------|------------------|
| 1 | `word_count` | Count words in text | Length of text |
| 2 | `sentence_count` | Split on `.!?` and count | Number of sentences |
| 3 | `avg_sentence_length` | words / sentences | How long sentences are (strong predictor) |
| 4 | `avg_word_length` | sum(chars per word) / words | Character-level complexity |
| 5 | `avg_syllables_per_word` | pyphen hyphenation dictionary | Polysyllabic words = harder (strongest predictor) |
| 6 | `difficult_words_percentage` | % words NOT in Dale-Chall 3000 AND 3+ syllables AND 4+ chars | Vocabulary difficulty |
| 7 | `flesch_reading_ease` | 206.835 - 1.015(words/sentences) - 84.6(syllables/words) | Overall readability 0-100 |
| 8 | `flesch_kincaid_grade` | 0.39(words/sentences) + 11.8(syllables/words) - 15.59 | Grade level estimate |
| 9 | `automated_readability_index` | 4.71(chars/words) + 0.5(words/sentences) - 21.43 | Characters + sentence length |
| 10 | `smog_readability` | 3 + sqrt(polysyllabic words * (30/sentences)) | Polysyllabic word density |
| 11 | `type_token_ratio` | unique words / total words | Vocabulary diversity |

#### New 5 NLP Features (computed by spaCy)

| # | Feature | How It's Calculated | What It Captures |
|---|---------|---------------------|------------------|
| 12 | `passive_voice_percentage` | % sentences containing `nsubjpass` dependency | Writing directness |
| 13 | `subordinate_clause_density` | avg count of `mark`, `advcl`, `acl`, `relcl` deps per sentence | Clause nesting complexity |
| 14 | `pos_diversity_score` | unique POS tags / total POS tags | Structural variety |
| 15 | `lexical_diversity` | unique lowercased words / total words | Vocabulary range |
| 16 | `sentence_complexity_variance` | numpy variance of sentence word counts | Pacing irregularity |

**Why spaCy?** spaCy is a production NLP library that builds a dependency parse tree for each sentence. This lets us identify syntactic structures (passive voice, subordinate clauses) that readability formulas from the 1940s-1970s couldn't detect. The model is `en_core_web_sm` — a small English model (~12MB) optimised for CPU inference.

### 3.3 What Is Ensemble Learning?

**Ensemble learning** is a machine learning technique where multiple models are trained independently and their predictions are combined (averaged, voted, etc.) to produce a final prediction. The core insight is that different models make different errors. By averaging their outputs, individual errors cancel out, producing a more accurate and stable result.

#### Analogy
Imagine asking three experienced teachers to estimate a text's grade level. Each teacher has a slightly different perspective. One emphasises sentence length, another focuses on vocabulary, a third looks at overall structure. Averaging their estimates gives a better answer than any single teacher.

#### Our Ensemble: Random Forest + Gradient Boosting + XGBoost

We use three tree-based regression models:

**1. Random Forest (RF)**
- Builds 300 decision trees, each trained on a random subset of the data and a random subset of features
- Each tree "votes" independently; the final prediction is the average
- Resistant to overfitting because each tree sees different data
- Best hyperparameters (found by GridSearchCV): `max_depth=None, min_samples_split=2, n_estimators=300`

**2. Gradient Boosting (GB)**
- Builds trees sequentially: each new tree corrects the errors of the previous trees
- Uses a "gradient descent" approach — each tree fits the residual (error) of the ensemble so far
- More accurate than RF on structured data but more prone to overfitting
- Best hyperparameters: `learning_rate=0.05, max_depth=5, n_estimators=100`

**3. XGBoost (eXtreme Gradient Boosting)**
- An optimised implementation of gradient boosting with regularisation (L1/L2 penalties)
- Adds subsampling (only uses 80% of data per tree) for additional robustness
- Generally the most accurate single model for tabular data
- Best hyperparameters: `learning_rate=0.05, max_depth=5, n_estimators=300, subsample=0.8`

**Ensemble prediction** = `(RF_prediction + GB_prediction + XGBoost_prediction) / 3`

#### Why Ensemble Instead of a Single Model?

| Approach | MAE (grade levels) | R2 |
|----------|--------------------|----|
| Random Forest alone | 0.725 | ~0.91 |
| Gradient Boosting alone | 0.719 | ~0.92 |
| XGBoost alone | 0.730 | ~0.91 |
| **3-Model Ensemble** | **0.712** | **0.926** |

The ensemble achieves the lowest error because each model's weaknesses are compensated by the others.

### 3.4 Hyperparameter Tuning: GridSearchCV

We don't guess the best parameters — we systematically search. **GridSearchCV** (from scikit-learn) tries every combination of hyperparameters using 5-fold cross-validation:

1. Split training data into 5 equal "folds"
2. For each parameter combination, train on 4 folds, evaluate on the 5th
3. Repeat 5 times (each fold gets a turn as the test set)
4. Average the 5 scores → this is the cross-validated score
5. Pick the combination with the lowest Mean Absolute Error

This is defined in `train_model.py`, which is run once to produce the `.joblib` model files.

### 3.5 Confidence Score

The confidence score measures how much the three models agree:

```python
confidence = max(0.5, min(0.99, 1.0 - (std_dev / max(|ensemble_pred|, 1.0))))
```

If all three models predict nearly the same grade, standard deviation is low, and confidence is high (close to 0.99). If they disagree (one says Grade 5, another says Grade 8), confidence drops toward 0.5.

### 3.6 Performance Metrics

| Metric | Value | What It Means |
|--------|-------|---------------|
| MAE | 0.712 | On average, our prediction is off by 0.7 grade levels |
| R2 | 0.926 | Our model explains 92.6% of the variance in grade levels |
| Within +-1 grade | 80.2% | 4 out of 5 predictions are within 1 grade of the true answer |
| Within +-0.5 grade | 57.6% | More than half are within half a grade |

### 3.7 Feature Importance

From `analyze_features.py`, the most important features for the ensemble:

1. `flesch_kincaid_grade`: **80.8%** — dominates because it directly encodes sentence length and syllable count
2. `automated_readability_index`: **13.3%** — adds character-level information
3. `subordinate_clause_density`: **0.9%** — our new spaCy feature, captures clause nesting
4. `sentence_complexity_variance`: **0.8%** — pacing irregularity
5. `avg_sentence_length`: **0.6%**

The heavy reliance on `flesch_kincaid_grade` makes sense: it's the same formula used to create the CLEAR Corpus target labels. The spaCy features add signal for texts where traditional formulas are insufficient.

---

## 4. Difficult Word Detection

Defined in `text_processor.py`. A word is flagged as "difficult" if ALL of these are true:

1. Not a proper noun or abbreviation (checked via capitalisation heuristics)
2. Not in the **Dale-Chall list of 3,000 easy words** (a curated list of words that a typical 4th grader knows)
3. 4+ characters long
4. 3+ syllables (counted by **pyphen**, a hyphenation library)

Each difficult word gets a detailed multi-reason explanation using:
- **Zipf frequency** (`wordfreq` library): a scale from 0-7 where 7="the", 5="know", 3="magnificent", 1="trepidation". Words below 2.5 are "rare/specialist"
- **Dale-Chall membership**: whether the word is in the 3,000 most common English words
- **Academic Word List**: 570 words identified as academic vocabulary (Grade 10+ terms)
- **Technical suffix detection**: suffixes like `-ology`, `-tion`, `-ment` indicate formal/technical vocabulary
- **Simpler alternative**: suggests a replacement from the curated simplification map

---

## 5. Readability Formulas: The 8 Scores (With Full Formulas)

All computed by the `textstat` Python library in `feature_extractor.py`. ClarityWorks computes all 8 but stores and displays the first 5 in the database and analysis results.

### 5.1 Flesch Reading Ease (1948)

**Formula:**

```
FRE = 206.835 − 1.015 × (total words / total sentences) − 84.6 × (total syllables / total words)
```

- **Variables**: ASL (Average Sentence Length = words ÷ sentences) and ASW (Average Syllables per Word = syllables ÷ words)
- **Scale**: 0–100, where **higher = easier** to read
- **Interpretation**: 90–100 = Grade 5 (very easy), 60–70 = Grade 8–9 (standard), 30–50 = College, 0–30 = College graduate
- **Origin**: Rudolf Flesch developed this for the US Navy to assess readability of technical manuals
- **Why it works**: Longer sentences demand more working memory; polysyllabic words tend to be less frequent and more abstract

### 5.2 Flesch-Kincaid Grade Level (1975)

**Formula:**

```
FK Grade = 0.39 × (total words / total sentences) + 11.8 × (total syllables / total words) − 15.59
```

- **Same inputs** as Flesch Reading Ease (sentence length + syllables), but **outputs a US school grade level** instead of 0–100
- **Scale**: Numeric grade level (e.g., 8.2 = 8th grade, 2nd month)
- **Origin**: J. Peter Kincaid adapted Flesch's formula under a US Department of Defense contract for military document assessment
- **Relationship to FRE**: Algebraically derived from the same variables but with different coefficients — a text with FRE 60 corresponds to roughly FK Grade 8
- **In our system**: This is also the **target variable** for our ML model (the CLEAR Corpus provides FK Grade Level as the professionally assessed label). It is also used as ML **feature #8**, which explains why it has 80.8% feature importance — the model learns to correct the formula's prediction using the other 15 features

### 5.3 Automated Readability Index (ARI, 1967)

**Formula:**

```
ARI = 4.71 × (total characters / total words) + 0.5 × (total words / total sentences) − 21.43
```

- **Key difference from FK**: Uses **characters per word** instead of syllables per word — this avoids the need for syllable counting (which can be error-prone for unusual words)
- **Scale**: US grade level (same as FK)
- **Variables**: Character count is a proxy for word complexity — longer words tend to be more technical ("photosynthesis" vs. "plant")
- **Origin**: Developed by Smith & Senter for the US Air Force, specifically for automated assessment by computer (hence "Automated")

### 5.4 SMOG Index (Simple Measure of Gobbledygook, 1969)

**Formula:**

```
SMOG = 3 + √(polysyllabic words × (30 / total sentences))
```

- **Polysyllabic words**: Words with 3 or more syllables
- **Scale**: US grade level
- **Key insight**: Focuses entirely on **hard words** (polysyllabic count) rather than average word difficulty — a text with a few very hard words in otherwise simple sentences will score higher on SMOG than on FK
- **Origin**: G. Harry McLaughlin created this specifically for healthcare documents — his research showed polysyllabic word count was the single best predictor of reading difficulty in medical texts
- **Requires 30+ sentences** for accuracy; `textstat` estimates for shorter texts

### 5.5 Coleman-Liau Index (1975)

**Formula:**

```
CLI = 0.0588 × L − 0.296 × S − 15.8
```

Where:
- **L** = average number of letters per 100 words
- **S** = average number of sentences per 100 words

- **Scale**: US grade level
- **Key difference**: Entirely **character-based** — no syllable counting at all. This makes it language-agnostic and deterministic (no dictionary lookup needed)
- **Origin**: Meri Coleman and T. L. Liau designed it for mechanical assessment using only character counts, making it suitable for optical character recognition (OCR) systems

### 5.6 Dale-Chall Readability Score (1948, revised 1995)

**Formula:**

```
DC = 0.1579 × (difficult words / total words × 100) + 0.0496 × (total words / total sentences)
If difficult word percentage > 5%, add 3.6365 to the score
```

- **Difficult word**: Any word NOT in the **Dale-Chall list of 3,000 easy words** — a curated list of words that 80% of 4th graders can understand
- **Scale**: Approximate grade level (1–16)
- **Key insight**: Uses a **word list** rather than syllable count — "idea" (3 syllables) is on the easy list, while "vex" (1 syllable) is not. This captures vocabulary difficulty more accurately than syllable-based formulas
- **In our system**: We also use the Dale-Chall word list for our difficult word detection (Section 4)

### 5.7 Linsear Write Formula

**Formula:**

```
1. Count easy words (≤2 syllables) and hard words (≥3 syllables) in a 100-word sample
2. Raw = (easy words × 1 + hard words × 3) / number of sentences
3. If Raw > 20: Grade = Raw / 2
4. If Raw ≤ 20: Grade = (Raw − 1) / 2
```

- **Scale**: US grade level
- **Key feature**: Hard words are weighted **3×** compared to easy words, heavily penalising polysyllabic vocabulary

### 5.8 Gunning Fog Index (1952)

**Formula:**

```
Fog = 0.4 × ((total words / total sentences) + 100 × (complex words / total words))
```

- **Complex word**: A word with 3+ syllables, excluding proper nouns, familiar jargon, and compound words
- **Scale**: Years of formal education needed (12 = high school senior, 16 = college graduate)
- **Origin**: Robert Gunning created this for newspaper editors — his "fog index" measures how much intellectual "fog" a text creates
- **Key difference from SMOG**: Fog combines sentence length WITH complex word percentage (multiplicative), while SMOG uses only complex word count

### Why Multiple Formulas?

Each formula captures a different aspect of reading difficulty:

| Aspect | Formulas That Measure It |
|--------|--------------------------|
| Sentence length (syntax complexity) | All 8 formulas include this |
| Syllable count (phonological complexity) | Flesch, FK, SMOG, Linsear, Gunning Fog |
| Character count (orthographic complexity) | ARI, Coleman-Liau |
| Word list (vocabulary familiarity) | Dale-Chall |

A text could score "easy" on FK (short sentences, few syllables) but "hard" on Dale-Chall (uses uncommon vocabulary with short words like "wry", "bane", "vex"). Showing multiple scores gives users a more nuanced, multi-dimensional picture of readability.

### How textstat Computes These in Our Code

In `feature_extractor.py`, all 8 are computed in one call:

```python
readability_scores = {
    "flesch_reading_ease": textstat.flesch_reading_ease(text),
    "flesch_kincaid_grade": textstat.flesch_kincaid_grade(text),
    "automated_readability_index": textstat.automated_readability_index(text),
    "smog_readability": textstat.smog_index(text),
    "coleman_liau_index": textstat.coleman_liau_index(text),
    "dale_chall_score": textstat.dale_chall_readability_score(text),
    "linsear_write": textstat.linsear_write_formula(text),
    "gunning_fog": textstat.gunning_fog(text)
}
```

The `textstat` library handles all tokenisation, syllable counting (using the CMU Pronouncing Dictionary + fallback heuristics), and formula computation internally. We use it as a black box — feed in raw text, get back scores.

---

## 6. The Training Pipeline: How We Built the Model

**File**: `train_model.py` — run once to produce the `.joblib` model files that the live system loads on startup.

### 6.1 Step-by-Step Training Flow

```
train_model.py
     │
     ▼
1. LOAD CLEAR CORPUS CSV
   ReadabilityModel.load_clear_corpus()
   - Read CSV via pandas
   - Find 'Excerpt' column → input text
   - Find 'Flesch-Kincaid-Grade-Level' column → regression target
   - Drop rows with NaN values
   - Result: ~4,724 usable samples
     │
     ▼
2. EXTRACT 16 FEATURES PER SAMPLE
   ReadabilityModel.prepare_training_data()
   - For each of ~4,724 texts:
     - Skip if text < 50 characters
     - Call FeatureExtractor.get_ml_features(text)
       - TextProcessor computes basic metrics (word count, syllables, etc.)
       - textstat computes readability formulas
       - spaCy computes NLP features (passive voice, clause density, etc.)
     - Append 16-element feature vector to X array
     - Append FK grade level to y array
   - Result: X = numpy array shape (4724, 16), y = numpy array shape (4724,)
     │
     ▼
3. TRAIN/TEST SPLIT
   sklearn.model_selection.train_test_split(X, y, test_size=0.2, random_state=42)
   - 80% training: ~3,779 samples
   - 20% testing: ~945 samples (held out, never seen during training)
   - random_state=42 ensures reproducible split
     │
     ▼
4. HYPERPARAMETER TUNING WITH GridSearchCV
   For EACH of the 3 models independently:
   
   a) Random Forest — search 3×4×3 = 36 combinations:
      n_estimators: [100, 200, 300]
      max_depth: [10, 15, 20, None]
      min_samples_split: [2, 5, 10]
      → Best: n_estimators=300, max_depth=None, min_samples_split=2
   
   b) Gradient Boosting — search 2×3×3 = 18 combinations:
      n_estimators: [100, 200]
      max_depth: [3, 5, 7]
      learning_rate: [0.05, 0.1, 0.2]
      → Best: n_estimators=100, max_depth=5, learning_rate=0.05
   
   c) XGBoost — search 2×3×3×2 = 36 combinations:
      n_estimators: [200, 300]
      max_depth: [3, 5, 7]
      learning_rate: [0.05, 0.1, 0.2]
      subsample: [0.8, 1.0]
      → Best: n_estimators=300, max_depth=5, learning_rate=0.05, subsample=0.8
   
   Each combination is evaluated with 5-fold cross-validation:
   - Split training data into 5 folds
   - Train on 4 folds, evaluate on the 5th
   - Repeat 5 times (each fold takes a turn as validation)
   - Average the 5 MAE scores
   - Pick combination with lowest average MAE
   
   Total model fits: (36 + 18 + 36) × 5 folds = 450 model trainings
     │
     ▼
5. EVALUATE INDIVIDUAL MODELS ON HELD-OUT TEST SET
   Each model predicts on the 945 test samples it has never seen:
   - Random Forest:      MAE = 0.725, R² ≈ 0.91
   - Gradient Boosting:  MAE = 0.719, R² ≈ 0.92
   - XGBoost:            MAE = 0.730, R² ≈ 0.91
     │
     ▼
6. COMPUTE ENSEMBLE PREDICTION
   ensemble_pred = (rf_pred + gb_pred + xgb_pred) / 3
   - Simple average of all 3 models
   - Result: MAE = 0.712, R² = 0.926, Within ±1 grade = 80.2%
     │
     ▼
7. SAVE MODELS TO DISK
   joblib.dump(best_rf, 'trained_models/rf_model.joblib')
   joblib.dump(best_gb, 'trained_models/gb_model.joblib')
   joblib.dump(xgb_model, 'trained_models/xgb_model.joblib')
   - .joblib files contain the fully trained model objects
   - These are loaded by readability_model.py on application startup
```

### 6.2 How the Trained Model Makes Predictions at Runtime

When a user submits text for analysis, `readability_model.py` → `predict()` runs:

```python
def predict(self, text: str) -> Dict:
    # 1. Extract all features (same 16 features used during training)
    ml_features = np.array([self.feature_extractor.get_ml_features(text)])
    
    # 2. Each model predicts independently
    rf_pred = self.rf_model.predict(ml_features)[0]     # e.g., 7.3
    gb_pred = self.gb_model.predict(ml_features)[0]     # e.g., 7.5
    xgb_pred = self.xgb_model.predict(ml_features)[0]   # e.g., 7.1
    
    # 3. Average = ensemble prediction
    ensemble_pred = (rf_pred + gb_pred + xgb_pred) / 3   # e.g., 7.3
    
    # 4. Confidence from inter-model agreement
    std_dev = np.std([rf_pred, gb_pred, xgb_pred])        # e.g., 0.16
    confidence = max(0.5, min(0.99, 1.0 - (std_dev / max(abs(ensemble_pred), 1.0))))
    # e.g., 1.0 - (0.16 / 7.3) = 0.978
    
    # 5. Map numeric prediction to grade string
    # 7.3 → "Grade 7" (because 7 ≤ 7.3 < 8)
    grade_level = self._prediction_to_grade(ensemble_pred)
    
    # 6. Map grade to complexity category
    # Grade 7 → "Intermediate" (grades 7-9)
    complexity = self._grade_to_complexity(grade_level)
```

### 6.3 Fallback Chain

If models aren't available, the system degrades gracefully:

1. **All 3 models loaded** → 3-model ensemble (best accuracy)
2. **Only RF + GB loaded** (no XGBoost) → 2-model ensemble average
3. **No models loaded** → Falls back to the raw Flesch-Kincaid Grade formula output from `textstat` with a fixed confidence of 0.7

This means the application always returns a grade prediction — even without trained models — using the FK formula as a heuristic baseline.

### 6.4 What Are Decision Trees? (The Building Block)

All three of our models are built from **decision trees**. A decision tree is a flowchart-like structure that makes predictions by asking a series of yes/no questions about the features:

```
Is avg_syllables_per_word > 1.52?
├── YES → Is flesch_kincaid_grade > 9.8?
│         ├── YES → Predict Grade 11.2
│         └── NO  → Predict Grade 8.1
└── NO  → Is avg_sentence_length > 18.5?
          ├── YES → Predict Grade 7.4
          └── NO  → Predict Grade 5.3
```

A single tree is easy to overfit (it memorises the training data). Our three models each handle this differently:

- **Random Forest**: Builds 300 trees on random subsets of data and features, then averages them (bagging). Reduces variance.
- **Gradient Boosting**: Builds 100 trees sequentially — each new tree learns from the errors of the previous trees (boosting). Reduces bias.
- **XGBoost**: Optimised gradient boosting with L1/L2 regularisation penalties that prevent individual trees from becoming too complex. Also subsamples 80% of data per tree.

---

## 7. The Frontend: React Application

### Key Technologies

- **React 18** with TypeScript: component-based UI framework
- **Vite**: fast development server with hot module replacement
- **TailwindCSS**: utility-first CSS framework for rapid styling
- **Recharts**: chart library (radar, bar, pie, gauge, line charts)
- **ReactFlow**: interactive node-edge graph rendering (for concept graphs)
- **dagre**: automatic graph layout algorithm (positions nodes in a hierarchy)
- **Axios**: HTTP client with JWT interceptors
- **jsPDF**: client-side PDF generation for reports
- **docx**: client-side DOCX generation for exports

### Component Map

| Component | File | Purpose |
|-----------|------|---------|
| `TextInput.tsx` | 5-tab input | Text paste, PDF upload, DOC upload, Image OCR, Voice input |
| `AnalysisResults.tsx` | Main results | Displays all metrics, charts, highlighted text, complexity score |
| `Charts.tsx` | Visualisations | Radar, bar, pie, gauge, common words charts |
| `HighlightedText.tsx` | Text display | Highlights difficult words/sentences with hover tooltips |
| `GradeExplanation.tsx` | Grade detail | Layman/technical toggle explaining what the grade means |
| `ComplexityScoreCard.tsx` | Score card | Animated 0-100 complexity gauge |
| `ImprovementSuggestions.tsx` | Suggestions | 3-5 prioritised actionable tips |
| `VocabularyAnalysis.tsx` | Vocab levels | Simple/Medium/Advanced/Expert word distribution |
| `ConceptGraph.tsx` | Knowledge graph | Interactive prerequisite concept visualisation |
| `SimplifyPage.tsx` | Rewrite UI | Auto/interactive mode, accept/deny changes |
| `ComparePage.tsx` | Comparison | Side-by-side text analysis |
| `BatchPage.tsx` | Batch mode | Multiple texts at once |
| `RAGUpload.tsx` | Textbook upload | File upload for RAG system |
| `RAGQuery.tsx` | Textbook query | Natural language Q&A over uploaded books |
| `Dashboard.tsx` | Home screen | Stats, recent analyses, readability trend chart |

### Frontend-Only Analysis Features

These features run entirely in the browser with no backend calls:

1. **Complexity Score (0-100)**: Weighted composite — `(grade/13)*40 + ((100-flesch)/100)*30 + (difficultWords%/100)*20 + (min(sentenceLength/30,1))*10`
2. **Reading Time**: Base 225 WPM adjusted by Flesch score (0.6x for hard text, 1.0x for easy)
3. **Improvement Suggestions**: Rule-based generator that analyses metrics and produces 3-5 prioritised tips
4. **Vocabulary Level Analysis**: Categorises words into Simple/Medium/Advanced/Expert using the difficult-words list as a proxy for Zipf frequency

---

*Continued in CW_SIMPLIFIER.md, CW_RAG.md, and CW_CONCEPTS_AND_FRONTEND.md*
