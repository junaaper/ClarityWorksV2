# PROMPT 5: Model Accuracy Improvements

## Context
Final step! You've completed Prompts 1-4. Now improve the ML model's accuracy by adding new features and retraining.

## Objective
- Add 5 new NLP features to improve predictions
- Retrain model with hyperparameter tuning
- Target: MAE < 0.7 grades (currently ~0.85)

---

## STEP 1: Install spaCy (if not already installed)

```bash
cd ml-service
pip install spacy
python -m spacy download en_core_web_sm
```

---

## STEP 2: Add New Features to Feature Extractor

Modify `ml-service/models/feature_extractor.py`:

**2.1 Add Import:**

```python
import spacy

nlp = spacy.load('en_core_web_sm')
```

**2.2 Update `extract_features()` method:**

Add these 5 new features to the existing 11:

```python
def extract_features(self, text):
    """
    Extract 16 features for ML model
    
    Original 11:
    - word_count, sentence_count, avg_sentence_length
    - avg_word_length, avg_syllables_per_word
    - difficult_words_percentage
    - flesch_reading_ease, flesch_kincaid_grade
    - automated_readability_index, smog_readability
    - type_token_ratio
    
    NEW 5:
    - passive_voice_percentage
    - subordinate_clause_density
    - pos_diversity_score
    - lexical_diversity
    - sentence_complexity_variance
    """
    
    # Existing features (keep all existing code)
    basic_metrics = self.text_processor.process_text(text)
    
    features = {
        'word_count': basic_metrics['word_count'],
        'sentence_count': basic_metrics['sentence_count'],
        'avg_sentence_length': basic_metrics['avg_sentence_length'],
        'avg_word_length': basic_metrics['avg_word_length'],
        'avg_syllables_per_word': basic_metrics['avg_syllables_per_word'],
        'difficult_words_percentage': basic_metrics['difficult_words_percentage'],
        'flesch_reading_ease': basic_metrics['flesch_reading_ease'],
        'flesch_kincaid_grade': basic_metrics['flesch_kincaid_grade'],
        'automated_readability_index': basic_metrics['automated_readability_index'],
        'smog_readability': basic_metrics['smog_readability'],
        'type_token_ratio': basic_metrics.get('type_token_ratio', 0)
    }
    
    # NEW FEATURE 1: Passive voice percentage
    features['passive_voice_percentage'] = self._calculate_passive_voice_percentage(text)
    
    # NEW FEATURE 2: Subordinate clause density (clauses per sentence)
    features['subordinate_clause_density'] = self._calculate_subordinate_clause_density(text)
    
    # NEW FEATURE 3: POS diversity score
    features['pos_diversity_score'] = self._calculate_pos_diversity(text)
    
    # NEW FEATURE 4: Lexical diversity (unique words / total words)
    words = text.split()
    features['lexical_diversity'] = len(set(w.lower() for w in words)) / len(words) if words else 0
    
    # NEW FEATURE 5: Sentence complexity variance
    features['sentence_complexity_variance'] = self._calculate_sentence_variance(text)
    
    return features

def _calculate_passive_voice_percentage(self, text):
    """Calculate percentage of sentences with passive voice"""
    doc = nlp(text)
    sentences = list(doc.sents)
    
    if not sentences:
        return 0.0
    
    passive_count = 0
    for sent in sentences:
        # Check for passive voice (nsubjpass dependency)
        if any(token.dep_ == 'nsubjpass' for token in sent):
            passive_count += 1
    
    return (passive_count / len(sentences)) * 100

def _calculate_subordinate_clause_density(self, text):
    """Calculate average subordinate clauses per sentence"""
    doc = nlp(text)
    sentences = list(doc.sents)
    
    if not sentences:
        return 0.0
    
    total_clauses = 0
    clause_markers = ['mark', 'advcl', 'acl', 'relcl']
    
    for sent in sentences:
        clause_count = sum(1 for token in sent if token.dep_ in clause_markers)
        total_clauses += clause_count
    
    return total_clauses / len(sentences)

def _calculate_pos_diversity(self, text):
    """
    Calculate diversity of POS tags
    Higher diversity = more varied sentence structures
    """
    doc = nlp(text)
    
    if not doc:
        return 0.0
    
    pos_tags = [token.pos_ for token in doc if token.is_alpha]
    
    if not pos_tags:
        return 0.0
    
    # Count unique POS tags
    unique_pos = len(set(pos_tags))
    total_pos = len(pos_tags)
    
    # Diversity score: unique / total
    return unique_pos / total_pos if total_pos > 0 else 0.0

def _calculate_sentence_variance(self, text):
    """
    Calculate variance in sentence lengths
    Higher variance = more complex writing style
    """
    doc = nlp(text)
    sentences = list(doc.sents)
    
    if len(sentences) < 2:
        return 0.0
    
    # Get word count per sentence
    sentence_lengths = []
    for sent in sentences:
        words = [token for token in sent if token.is_alpha]
        sentence_lengths.append(len(words))
    
    # Calculate variance
    import numpy as np
    variance = np.var(sentence_lengths)
    
    return float(variance)
```

---

## STEP 3: Update Model Training Script

Modify `ml-service/train_model.py`:

**3.1 Add GridSearchCV for hyperparameter tuning:**

```python
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
import xgboost as xgb

# ... existing code to load data ...

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("=" * 80)
print("HYPERPARAMETER TUNING")
print("=" * 80)

# Random Forest tuning
print("\n1. Tuning Random Forest...")
rf_params = {
    'n_estimators': [100, 200, 300],
    'max_depth': [10, 15, 20, None],
    'min_samples_split': [2, 5, 10]
}

rf_grid = GridSearchCV(
    RandomForestRegressor(random_state=42),
    rf_params,
    cv=5,
    scoring='neg_mean_absolute_error',
    n_jobs=-1,
    verbose=1
)

rf_grid.fit(X_train, y_train)
best_rf = rf_grid.best_estimator_

print(f"Best RF params: {rf_grid.best_params_}")
print(f"Best RF MAE: {-rf_grid.best_score_:.3f}")

# Gradient Boosting tuning
print("\n2. Tuning Gradient Boosting...")
gb_params = {
    'n_estimators': [100, 200],
    'max_depth': [3, 5, 7],
    'learning_rate': [0.05, 0.1, 0.2]
}

gb_grid = GridSearchCV(
    GradientBoostingRegressor(random_state=42),
    gb_params,
    cv=5,
    scoring='neg_mean_absolute_error',
    n_jobs=-1,
    verbose=1
)

gb_grid.fit(X_train, y_train)
best_gb = gb_grid.best_estimator_

print(f"Best GB params: {gb_grid.best_params_}")
print(f"Best GB MAE: {-gb_grid.best_score_:.3f}")

# Try XGBoost
print("\n3. Training XGBoost...")
xgb_model = xgb.XGBRegressor(
    n_estimators=200,
    max_depth=5,
    learning_rate=0.1,
    random_state=42,
    n_jobs=-1
)

xgb_model.fit(X_train, y_train)

# Ensemble prediction function
def ensemble_predict(X):
    """Average predictions from all 3 models"""
    rf_pred = best_rf.predict(X)
    gb_pred = best_gb.predict(X)
    xgb_pred = xgb_model.predict(X)
    return (rf_pred + gb_pred + xgb_pred) / 3

# Evaluate ensemble
print("\n" + "=" * 80)
print("ENSEMBLE EVALUATION")
print("=" * 80)

y_pred = ensemble_predict(X_test)

from sklearn.metrics import mean_absolute_error, r2_score

mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

# Within ±1 grade accuracy
within_1 = np.mean(np.abs(y_test - y_pred) <= 1.0) * 100

# Within ±0.5 grade accuracy
within_05 = np.mean(np.abs(y_test - y_pred) <= 0.5) * 100

print(f"\nMean Absolute Error: {mae:.3f} grades")
print(f"R² Score: {r2:.3f}")
print(f"Within ±1 grade: {within_1:.1f}%")
print(f"Within ±0.5 grade: {within_05:.1f}%")

# Save all models
print("\nSaving models...")
joblib.dump(best_rf, 'trained_models/rf_model.joblib')
joblib.dump(best_gb, 'trained_models/gb_model.joblib')
joblib.dump(xgb_model, 'trained_models/xgb_model.joblib')

print("✅ Models saved successfully!")
```

**3.2 Add XGBoost to requirements:**

Add to `ml-service/requirements.txt`:

```
xgboost==2.0.3
```

Install:

```bash
pip install xgboost
```

---

## STEP 4: Update Readability Model to Use Ensemble

Modify `ml-service/models/readability_model.py`:

**4.1 Load all 3 models:**

```python
import joblib
import os

class ReadabilityModel:
    def __init__(self):
        model_dir = os.path.join(os.path.dirname(__file__), '..', 'trained_models')
        
        # Load all 3 models
        self.rf_model = None
        self.gb_model = None
        self.xgb_model = None
        
        try:
            self.rf_model = joblib.load(os.path.join(model_dir, 'rf_model.joblib'))
            self.gb_model = joblib.load(os.path.join(model_dir, 'gb_model.joblib'))
            self.xgb_model = joblib.load(os.path.join(model_dir, 'xgb_model.joblib'))
            print("✅ All 3 models loaded successfully")
        except Exception as e:
            print(f"⚠️  Could not load models: {e}")
            print("⚠️  Using fallback Flesch-Kincaid heuristic")
```

**4.2 Update prediction method:**

```python
def predict_grade_level(self, features):
    """
    Predict grade level using ensemble of 3 models
    Falls back to Flesch-Kincaid if models not loaded
    """
    
    # If models not loaded, use fallback
    if not self.rf_model or not self.gb_model or not self.xgb_model:
        return self._flesch_kincaid_fallback(features)
    
    try:
        # Convert features to array (make sure all 16 features are present)
        feature_array = self._features_to_array(features)
        
        # Get predictions from all 3 models
        rf_pred = self.rf_model.predict([feature_array])[0]
        gb_pred = self.gb_model.predict([feature_array])[0]
        xgb_pred = self.xgb_model.predict([feature_array])[0]
        
        # Ensemble: average of 3 predictions
        ensemble_pred = (rf_pred + gb_pred + xgb_pred) / 3
        
        # Calculate confidence based on agreement
        predictions = [rf_pred, gb_pred, xgb_pred]
        std_dev = np.std(predictions)
        
        # Confidence inversely proportional to disagreement
        # High agreement (low std) = high confidence
        confidence = max(0.5, min(0.99, 1.0 - (std_dev / max(abs(ensemble_pred), 1.0))))
        
        # Map numeric prediction to grade string
        grade_string = self._numeric_to_grade_string(ensemble_pred)
        
        # Map to complexity
        complexity = self._grade_to_complexity(ensemble_pred)
        
        return {
            'grade_numeric': round(ensemble_pred, 2),
            'grade_string': grade_string,
            'complexity': complexity,
            'confidence': round(confidence, 2),
            'model_predictions': {
                'random_forest': round(rf_pred, 2),
                'gradient_boosting': round(gb_pred, 2),
                'xgboost': round(xgb_pred, 2)
            }
        }
    
    except Exception as e:
        print(f"Prediction error: {e}")
        return self._flesch_kincaid_fallback(features)

def _features_to_array(self, features):
    """
    Convert feature dict to ordered array for model
    MUST match the order used during training!
    """
    return [
        features.get('word_count', 0),
        features.get('sentence_count', 0),
        features.get('avg_sentence_length', 0),
        features.get('avg_word_length', 0),
        features.get('avg_syllables_per_word', 0),
        features.get('difficult_words_percentage', 0),
        features.get('flesch_reading_ease', 0),
        features.get('flesch_kincaid_grade', 0),
        features.get('automated_readability_index', 0),
        features.get('smog_readability', 0),
        features.get('type_token_ratio', 0),
        # NEW 5 FEATURES:
        features.get('passive_voice_percentage', 0),
        features.get('subordinate_clause_density', 0),
        features.get('pos_diversity_score', 0),
        features.get('lexical_diversity', 0),
        features.get('sentence_complexity_variance', 0)
    ]
```

---

## STEP 5: Retrain the Model

**5.1 Run training:**

```bash
cd ml-service
python train_model.py
```

This will:
- Load CLEAR Corpus
- Extract 16 features (11 old + 5 new)
- Tune hyperparameters via GridSearchCV
- Train RF, GB, and XGBoost
- Evaluate ensemble performance
- Save all 3 models

**Expected output:**

```
==========================================
HYPERPARAMETER TUNING
==========================================

1. Tuning Random Forest...
Fitting 5 folds for each of 36 candidates, totalling 180 fits
Best RF params: {...}
Best RF MAE: 0.68

2. Tuning Gradient Boosting...
Fitting 5 folds for each of 18 candidates, totalling 90 fits
Best GB params: {...}
Best GB MAE: 0.71

3. Training XGBoost...

==========================================
ENSEMBLE EVALUATION
==========================================

Mean Absolute Error: 0.65 grades
R² Score: 0.84
Within ±1 grade: 87.3%
Within ±0.5 grade: 64.2%

✅ Models saved successfully!
```

**Target:** MAE < 0.7 grades

---

## STEP 6: Test Improved Model

**6.1 Test with calibrated files:**

```bash
python testing/ml-service/validate_test_files.py
```

All 10 files should now predict even more accurately (error < 0.2 grades).

**6.2 Test via API:**

```bash
# Start ML service
python app.py

# In another terminal, test:
curl -X POST http://localhost:5001/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "The cat sat on the mat. She was happy."}'
```

---

## STEP 7: Feature Importance Analysis (Optional)

Create `ml-service/analyze_features.py`:

```python
import joblib
import numpy as np
import matplotlib.pyplot as plt

# Load models
rf = joblib.load('trained_models/rf_model.joblib')
gb = joblib.load('trained_models/gb_model.joblib')

# Feature names (in order)
feature_names = [
    'word_count',
    'sentence_count',
    'avg_sentence_length',
    'avg_word_length',
    'avg_syllables_per_word',
    'difficult_words_percentage',
    'flesch_reading_ease',
    'flesch_kincaid_grade',
    'automated_readability_index',
    'smog_readability',
    'type_token_ratio',
    'passive_voice_percentage',      # NEW
    'subordinate_clause_density',   # NEW
    'pos_diversity_score',          # NEW
    'lexical_diversity',            # NEW
    'sentence_complexity_variance'  # NEW
]

# Get feature importances
rf_importance = rf.feature_importances_
gb_importance = gb.feature_importances_

# Average importance
avg_importance = (rf_importance + gb_importance) / 2

# Sort
indices = np.argsort(avg_importance)[::-1]

print("=" * 60)
print("FEATURE IMPORTANCE RANKING")
print("=" * 60)

for i, idx in enumerate(indices):
    print(f"{i+1:2d}. {feature_names[idx]:35s} {avg_importance[idx]:.4f}")

# Plot
plt.figure(figsize=(10, 6))
plt.barh(range(len(feature_names)), avg_importance[indices])
plt.yticks(range(len(feature_names)), [feature_names[i] for i in indices])
plt.xlabel('Importance')
plt.title('Feature Importance for Grade Level Prediction')
plt.tight_layout()
plt.savefig('feature_importance.png')
print("\n✅ Chart saved: feature_importance.png")
```

Run:

```bash
python analyze_features.py
```

This shows which features contribute most to accurate predictions.

---

## DELIVERABLES

1. ✅ 5 new features added to feature extractor
2. ✅ XGBoost installed
3. ✅ GridSearchCV hyperparameter tuning
4. ✅ Ensemble of 3 models (RF + GB + XGBoost)
5. ✅ Model retrained on 16 features
6. ✅ MAE improved to < 0.7 grades
7. ✅ Feature importance analysis

---

## SUCCESS CRITERIA

After retraining:

- ✅ MAE < 0.7 grades (improved from ~0.85)
- ✅ Within ±1 grade accuracy > 85% (improved from ~78%)
- ✅ R² score > 0.82 (improved from ~0.80)
- ✅ Calibrated test files still predict accurately
- ✅ All 3 models loaded and ensemble working

---

## FINAL VERIFICATION

**Test the complete system:**

1. ✅ Upload text via any input method
2. ✅ Get analysis with improved grade prediction
3. ✅ Verify difficult words have detailed reasons
4. ✅ Simplify text to target grade
5. ✅ Upload textbook to RAG
6. ✅ Query textbook for specific content
7. ✅ All 10 calibrated test files predict within ±0.3 grades

---

**🎉 CONGRATULATIONS! All 5 features implemented!**

Your FYP is now complete with:
- Enhanced difficulty detection
- Calibrated test files for demo
- Text simplification (auto + interactive modes)
- RAG for large textbook processing
- Improved ML model accuracy

Ready for presentation! 🚀
