#!/usr/bin/env python3
"""
Feature Importance Analysis for ClarityWorks ML Model.
Shows which features contribute most to grade level prediction.
"""

import os
os.environ['THINC_NO_TORCH'] = '1'

import joblib
import numpy as np

# Load models
models_dir = os.path.join(os.path.dirname(__file__), 'trained_models')
rf = joblib.load(os.path.join(models_dir, 'rf_model.joblib'))
gb = joblib.load(os.path.join(models_dir, 'gb_model.joblib'))

# Feature names (in order, must match training)
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
    'passive_voice_percentage',
    'subordinate_clause_density',
    'pos_diversity_score',
    'lexical_diversity',
    'sentence_complexity_variance'
]

# Get feature importances
rf_importance = rf.feature_importances_
gb_importance = gb.feature_importances_

# Average importance across RF and GB
avg_importance = (rf_importance + gb_importance) / 2

# Sort by importance (descending)
indices = np.argsort(avg_importance)[::-1]

print("=" * 60)
print("FEATURE IMPORTANCE RANKING")
print("=" * 60)

for i, idx in enumerate(indices):
    marker = " (NEW)" if feature_names[idx] in [
        'passive_voice_percentage',
        'subordinate_clause_density',
        'pos_diversity_score',
        'lexical_diversity',
        'sentence_complexity_variance'
    ] else ""
    print(f"{i+1:2d}. {feature_names[idx]:35s} {avg_importance[idx]:.4f}{marker}")

# Summary of new features
print("\n" + "=" * 60)
print("NEW FEATURE CONTRIBUTIONS")
print("=" * 60)

new_features = [
    'passive_voice_percentage',
    'subordinate_clause_density',
    'pos_diversity_score',
    'lexical_diversity',
    'sentence_complexity_variance'
]

total_importance = sum(avg_importance)
new_importance = sum(avg_importance[feature_names.index(f)] for f in new_features)

print(f"\nNew features total importance: {new_importance:.4f} ({new_importance/total_importance*100:.1f}%)")
print(f"Original features importance:  {total_importance - new_importance:.4f} ({(total_importance - new_importance)/total_importance*100:.1f}%)")

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 6))
    colors = ['#e74c3c' if feature_names[i] in new_features else '#3498db' for i in indices]
    plt.barh(range(len(feature_names)), avg_importance[indices], color=colors)
    plt.yticks(range(len(feature_names)), [feature_names[i] for i in indices])
    plt.xlabel('Importance')
    plt.title('Feature Importance for Grade Level Prediction')
    plt.legend(['New Features (red)', 'Original Features (blue)'])
    plt.tight_layout()
    plt.savefig(os.path.join(os.path.dirname(__file__), 'feature_importance.png'))
    print("\nChart saved: feature_importance.png")
except ImportError:
    print("\nMatplotlib not available - skipping chart generation")
