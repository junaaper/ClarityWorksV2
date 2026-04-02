import pandas as pd
import numpy as np
from models.readability_model import ReadabilityModel
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def test_model_accuracy(corpus_path='data/clear_corpus/clear_corpus.csv', sample_size=100):
    """Test model on sample of CLEAR Corpus."""

    # Load model
    model = ReadabilityModel()
    if not model.load_models():
        print("❌ No trained models found. Please train first.")
        return

    # Load corpus
    df = pd.read_csv(corpus_path)

    # Use standard column names
    if 'Excerpt' in df.columns:
        df = df.rename(columns={'Excerpt': 'text'})
    if 'Flesch-Kincaid-Grade-Level' in df.columns:
        df = df.rename(columns={'Flesch-Kincaid-Grade-Level': 'actual_grade'})

    # Sample random texts
    df_sample = df.sample(n=min(sample_size, len(df)), random_state=42)

    predictions = []
    actuals = []

    print(f"\nTesting on {len(df_sample)} samples...")
    print("=" * 80)

    for idx, row in df_sample.iterrows():
        text = str(row['text'])
        actual_grade = row['actual_grade']

        # Get prediction
        result = model.predict(text)
        predicted_grade_num = result['predictions']['raw_score']

        predictions.append(predicted_grade_num)
        actuals.append(actual_grade)

        # Show first 5 examples
        if len(predictions) <= 5:
            print(f"\nExample {len(predictions)}:")
            print(f"  Text: {text[:100]}...")
            print(f"  Actual Grade: {actual_grade:.1f}")
            print(f"  Predicted Grade: {predicted_grade_num:.1f}")
            print(f"  Difference: {abs(predicted_grade_num - actual_grade):.1f}")

    # Calculate metrics
    predictions = np.array(predictions)
    actuals = np.array(actuals)

    mae = mean_absolute_error(actuals, predictions)
    rmse = np.sqrt(mean_squared_error(actuals, predictions))
    r2 = r2_score(actuals, predictions)

    # Calculate accuracy within ±1 grade
    within_1_grade = np.sum(np.abs(predictions - actuals) <= 1.0) / len(predictions) * 100
    within_2_grades = np.sum(np.abs(predictions - actuals) <= 2.0) / len(predictions) * 100

    print("\n" + "=" * 80)
    print("ACCURACY METRICS")
    print("=" * 80)
    print(f"\n📊 Overall Performance:")
    print(f"  • Mean Absolute Error (MAE):     {mae:.2f} grade levels")
    print(f"  • Root Mean Squared Error (RMSE): {rmse:.2f} grade levels")
    print(f"  • R² Score:                       {r2:.3f} (closer to 1.0 is better)")

    print(f"\n🎯 Accuracy Rates:")
    print(f"  • Within ±1 grade level:  {within_1_grade:.1f}%")
    print(f"  • Within ±2 grade levels: {within_2_grades:.1f}%")

    print(f"\n📈 Interpretation:")
    if mae < 1.0:
        print("  ✅ EXCELLENT - Predictions very close to actual grades")
    elif mae < 1.5:
        print("  ✅ GOOD - Predictions reasonably accurate")
    elif mae < 2.0:
        print("  ⚠️  FAIR - Predictions somewhat accurate")
    else:
        print("  ❌ NEEDS IMPROVEMENT - Large prediction errors")

    if r2 > 0.8:
        print("  ✅ EXCELLENT model fit (R² > 0.8)")
    elif r2 > 0.6:
        print("  ✅ GOOD model fit (R² > 0.6)")
    else:
        print("  ⚠️  Model fit could be improved")

    return {
        'mae': mae,
        'rmse': rmse,
        'r2': r2,
        'within_1_grade': within_1_grade,
        'within_2_grades': within_2_grades
    }

if __name__ == "__main__":
    test_model_accuracy(sample_size=100)