#!/usr/bin/env python3
"""
Script to train the readability model on CLEAR Corpus dataset.

Usage:
    python train_model.py [path_to_corpus.csv]

If no path is provided, it will look for the file at:
    data/clear_corpus/clear_corpus.csv
"""

import os
os.environ['THINC_NO_TORCH'] = '1'

import sys
import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
from models import ReadabilityModel

def main():
    # Get corpus path from command line or use default
    if len(sys.argv) > 1:
        corpus_path = sys.argv[1]
    else:
        corpus_path = os.path.join(
            os.path.dirname(__file__),
            'data', 'clear_corpus', 'clear_corpus.csv'
        )

    if not os.path.exists(corpus_path):
        print(f"Error: Corpus file not found at {corpus_path}")
        print("\nPlease download the CLEAR Corpus from:")
        print("https://www.commonlit.org/en/research/clear-corpus")
        print(f"\nAnd place it at: {corpus_path}")
        sys.exit(1)

    print("=" * 80)
    print("ClarityWorks ML Model Training (Enhanced)")
    print("=" * 80)
    print(f"\nCorpus path: {corpus_path}")

    # Initialize model (for data loading and feature extraction)
    model = ReadabilityModel()

    try:
        # Load data
        print("\nLoading CLEAR Corpus...")
        df = model.load_clear_corpus(corpus_path)
        print(f"Loaded {len(df)} samples")

        # Prepare training data with 16 features
        print("Preparing training data (16 features)...")
        X, y = model.prepare_training_data(df)
        print(f"Prepared {len(X)} samples with {X.shape[1]} features")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        print(f"Training set: {len(X_train)} samples")
        print(f"Test set: {len(X_test)} samples")

        print("\n" + "=" * 80)
        print("HYPERPARAMETER TUNING")
        print("=" * 80)

        # 1. Random Forest tuning
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

        # 2. Gradient Boosting tuning
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

        # 3. XGBoost tuning
        print("\n3. Tuning XGBoost...")
        xgb_params = {
            'n_estimators': [200, 300],
            'max_depth': [3, 5, 7],
            'learning_rate': [0.05, 0.1, 0.2],
            'subsample': [0.8, 1.0]
        }

        xgb_grid = GridSearchCV(
            xgb.XGBRegressor(random_state=42, n_jobs=-1),
            xgb_params,
            cv=5,
            scoring='neg_mean_absolute_error',
            n_jobs=-1,
            verbose=1
        )

        xgb_grid.fit(X_train, y_train)
        xgb_model = xgb_grid.best_estimator_

        print(f"Best XGB params: {xgb_grid.best_params_}")
        print(f"Best XGB MAE: {-xgb_grid.best_score_:.3f}")

        # Individual model evaluations
        print("\n" + "=" * 80)
        print("INDIVIDUAL MODEL EVALUATION")
        print("=" * 80)

        rf_pred = best_rf.predict(X_test)
        gb_pred = best_gb.predict(X_test)
        xgb_pred = xgb_model.predict(X_test)

        print(f"\nRandom Forest  - MAE: {mean_absolute_error(y_test, rf_pred):.3f}, R2: {r2_score(y_test, rf_pred):.3f}")
        print(f"Gradient Boost - MAE: {mean_absolute_error(y_test, gb_pred):.3f}, R2: {r2_score(y_test, gb_pred):.3f}")
        print(f"XGBoost        - MAE: {mean_absolute_error(y_test, xgb_pred):.3f}, R2: {r2_score(y_test, xgb_pred):.3f}")

        # Ensemble prediction
        ensemble_pred = (rf_pred + gb_pred + xgb_pred) / 3

        print("\n" + "=" * 80)
        print("ENSEMBLE EVALUATION")
        print("=" * 80)

        mae = mean_absolute_error(y_test, ensemble_pred)
        rmse = np.sqrt(mean_squared_error(y_test, ensemble_pred))
        r2 = r2_score(y_test, ensemble_pred)

        # Within +/- 1 grade accuracy
        within_1 = np.mean(np.abs(y_test - ensemble_pred) <= 1.0) * 100

        # Within +/- 0.5 grade accuracy
        within_05 = np.mean(np.abs(y_test - ensemble_pred) <= 0.5) * 100

        print(f"\nMean Absolute Error: {mae:.3f} grades")
        print(f"RMSE: {rmse:.3f} grades")
        print(f"R2 Score: {r2:.3f}")
        print(f"Within +/-1 grade: {within_1:.1f}%")
        print(f"Within +/-0.5 grade: {within_05:.1f}%")

        # Save all models
        models_dir = os.path.join(os.path.dirname(__file__), 'trained_models')
        os.makedirs(models_dir, exist_ok=True)

        print("\nSaving models...")
        joblib.dump(best_rf, os.path.join(models_dir, 'rf_model.joblib'))
        joblib.dump(best_gb, os.path.join(models_dir, 'gb_model.joblib'))
        joblib.dump(xgb_model, os.path.join(models_dir, 'xgb_model.joblib'))

        print(f"Models saved to {models_dir}")

        # Summary
        print("\n" + "=" * 80)
        print("TRAINING COMPLETE!")
        print("=" * 80)
        print(f"\nMetrics:")
        print(f"  - MAE: {mae:.4f} (target < 0.7)")
        print(f"  - RMSE: {rmse:.4f}")
        print(f"  - R2 Score: {r2:.4f}")
        print(f"  - Training samples: {len(X_train)}")
        print(f"  - Test samples: {len(X_test)}")
        print(f"  - Features: {X.shape[1]}")

        if mae < 0.7:
            print(f"\n  TARGET MET: MAE {mae:.3f} < 0.7")
        else:
            print(f"\n  TARGET NOT MET: MAE {mae:.3f} >= 0.7")

    except Exception as e:
        print(f"\nError during training: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
