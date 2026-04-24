import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import joblib
from typing import Tuple, Dict, Optional
from .feature_extractor import FeatureExtractor

class ReadabilityModel:
    def __init__(self):
        self.rf_model = None
        self.gb_model = None
        self.xgb_model = None
        self.feature_extractor = FeatureExtractor()
        self.models_dir = os.path.join(os.path.dirname(__file__), '..', 'trained_models')
        self.is_trained = False

    def load_clear_corpus(self, file_path: str) -> pd.DataFrame:
        """Load CLEAR Corpus dataset."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"CLEAR Corpus not found at {file_path}")

        df = pd.read_csv(file_path)

        # Map possible column names to standard names
        column_mappings = {
            'text_col': ['Excerpt', 'excerpt', 'text', 'Text'],
            'target_col': ['Flesch-Kincaid-Grade-Level', 'target', 'Target', 'BT Easiness']
        }

        # Find text column
        text_col = None
        for col in column_mappings['text_col']:
            if col in df.columns:
                text_col = col
                break

        # Find target column
        target_col = None
        for col in column_mappings['target_col']:
            if col in df.columns:
                target_col = col
                break

        if text_col is None:
            raise ValueError(f"No text column found. Available columns: {df.columns.tolist()}")
        if target_col is None:
            raise ValueError(f"No target column found. Available columns: {df.columns.tolist()}")

        # Rename to standard names
        df = df.rename(columns={text_col: 'excerpt', target_col: 'target'})

        # Drop rows with missing values in required columns
        df = df.dropna(subset=['excerpt', 'target'])

        print(f"Using '{text_col}' as text column and '{target_col}' as target column")

        return df

    def prepare_training_data(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features and targets for training."""
        X = []
        y = []
        total = len(df)

        for i, (_, row) in enumerate(df.iterrows()):
            try:
                text = str(row['excerpt'])
                if len(text) < 50:
                    continue

                features = self.feature_extractor.get_ml_features(text)
                X.append(features)
                y.append(row['target'])

                if (i + 1) % 100 == 0:
                    print(f"  Processed {i + 1}/{total} samples...")
            except Exception as e:
                print(f"Error processing row {i}: {e}")
                continue

        return np.array(X), np.array(y)

    def train(self, corpus_path: str) -> Dict:
        """Train the ensemble model."""
        print("Loading CLEAR Corpus...")
        df = self.load_clear_corpus(corpus_path)
        print(f"Loaded {len(df)} samples")

        print("Preparing training data...")
        X, y = self.prepare_training_data(df)
        print(f"Prepared {len(X)} samples with {X.shape[1]} features")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Train Random Forest
        print("Training Random Forest...")
        self.rf_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        self.rf_model.fit(X_train, y_train)

        # Train Gradient Boosting
        print("Training Gradient Boosting...")
        self.gb_model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        self.gb_model.fit(X_train, y_train)

        # Evaluate ensemble
        rf_pred = self.rf_model.predict(X_test)
        gb_pred = self.gb_model.predict(X_test)
        ensemble_pred = (rf_pred + gb_pred) / 2

        rmse = np.sqrt(mean_squared_error(y_test, ensemble_pred))
        r2 = r2_score(y_test, ensemble_pred)

        print(f"Ensemble RMSE: {rmse:.4f}")
        print(f"Ensemble R2: {r2:.4f}")

        # Save models
        self.save_models()
        self.is_trained = True

        return {
            "rmse": rmse,
            "r2": r2,
            "samples_trained": len(X_train),
            "samples_tested": len(X_test)
        }

    def save_models(self):
        """Save trained models to disk."""
        os.makedirs(self.models_dir, exist_ok=True)

        if self.rf_model:
            joblib.dump(self.rf_model, os.path.join(self.models_dir, 'rf_model.joblib'))
        if self.gb_model:
            joblib.dump(self.gb_model, os.path.join(self.models_dir, 'gb_model.joblib'))
        if self.xgb_model:
            joblib.dump(self.xgb_model, os.path.join(self.models_dir, 'xgb_model.joblib'))

        print(f"Models saved to {self.models_dir}")

    def load_models(self) -> bool:
        """Load trained models from disk."""
        rf_path = os.path.join(self.models_dir, 'rf_model.joblib')
        gb_path = os.path.join(self.models_dir, 'gb_model.joblib')
        xgb_path = os.path.join(self.models_dir, 'xgb_model.joblib')

        if os.path.exists(rf_path) and os.path.exists(gb_path):
            self.rf_model = joblib.load(rf_path)
            self.gb_model = joblib.load(gb_path)
            self.is_trained = True
            print("RF and GB models loaded successfully")

            # Load XGBoost if available
            if os.path.exists(xgb_path):
                self.xgb_model = joblib.load(xgb_path)
                print("XGBoost model loaded successfully")
                print("All 3 models loaded - ensemble mode active")
            else:
                print("XGBoost model not found - using 2-model ensemble")

            return True

        print("No trained models found")
        return False

    def predict(self, text: str) -> Dict:
        """Predict readability for given text."""
        # Extract all features
        full_features = self.feature_extractor.extract_features(text)
        ml_features = np.array([self.feature_extractor.get_ml_features(text)])

        # Get predictions
        if self.is_trained and self.rf_model and self.gb_model:
            rf_pred = self.rf_model.predict(ml_features)[0]
            gb_pred = self.gb_model.predict(ml_features)[0]

            model_predictions = {
                'random_forest': round(float(rf_pred), 2),
                'gradient_boosting': round(float(gb_pred), 2)
            }

            if self.xgb_model:
                # 3-model ensemble
                xgb_pred = self.xgb_model.predict(ml_features)[0]
                ensemble_pred = (rf_pred + gb_pred + xgb_pred) / 3
                model_predictions['xgboost'] = round(float(xgb_pred), 2)

                # Confidence based on agreement between 3 models
                predictions = [rf_pred, gb_pred, xgb_pred]
                std_dev = np.std(predictions)
                confidence = max(0.5, min(0.99, 1.0 - (std_dev / max(abs(ensemble_pred), 1.0))))
            else:
                # 2-model ensemble fallback
                ensemble_pred = (rf_pred + gb_pred) / 2
                confidence = 1 - abs(rf_pred - gb_pred) / max(abs(rf_pred), abs(gb_pred), 0.01)
                confidence = max(0.5, min(0.99, confidence))
        else:
            # Fallback to heuristic prediction based on Flesch-Kincaid
            fk_grade = full_features["readability_scores"]["flesch_kincaid_grade"]
            ensemble_pred = fk_grade
            confidence = 0.7
            model_predictions = {}

        # Convert prediction to grade level
        grade_level = self._prediction_to_grade(ensemble_pred)
        complexity = self._grade_to_complexity(grade_level)

        result = {
            "basic_metrics": full_features["basic_metrics"],
            "readability_scores": {
                "flesch_reading_ease": round(max(0, min(100, full_features["readability_scores"]["flesch_reading_ease"])), 2),
                "flesch_kincaid_grade": round(full_features["readability_scores"]["flesch_kincaid_grade"], 2),
                "automated_readability_index": round(full_features["readability_scores"]["automated_readability_index"], 2),
                "smog_readability": round(full_features["readability_scores"]["smog_readability"], 2),
                "coleman_liau_index": round(full_features["readability_scores"]["coleman_liau_index"], 2),
            },
            "predictions": {
                "predicted_grade_level": grade_level,
                "predicted_complexity": complexity,
                "confidence": round(float(confidence), 2),
                "raw_score": round(float(ensemble_pred), 2)
            },
            "difficult_elements": full_features["difficult_elements"],
            "statistics": full_features["statistics"]
        }

        if model_predictions:
            result["predictions"]["model_predictions"] = model_predictions

        return result

    def _prediction_to_grade(self, pred: float) -> str:
        """Convert numeric prediction to grade level string."""
        if pred < 0:
            return "Grade 3"
        elif pred < 4:
            return "Grade 3"
        elif pred < 5:
            return "Grade 4"
        elif pred < 6:
            return "Grade 5"
        elif pred < 7:
            return "Grade 6"
        elif pred < 8:
            return "Grade 7"
        elif pred < 9:
            return "Grade 8"
        elif pred < 10:
            return "Grade 9"
        elif pred < 11:
            return "Grade 10"
        elif pred < 12:
            return "Grade 11"
        elif pred < 13:
            return "Grade 12"
        else:
            return "College"

    def _grade_to_complexity(self, grade: str) -> str:
        """Convert grade level to complexity category."""
        grade_num = grade.replace("Grade ", "")
        if grade_num == "College":
            return "Expert"

        try:
            num = int(grade_num)
            if num <= 6:
                return "Beginner"
            elif num <= 9:
                return "Intermediate"
            elif num <= 12:
                return "Advanced"
            else:
                return "Expert"
        except ValueError:
            return "Intermediate"
