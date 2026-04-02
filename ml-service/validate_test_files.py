import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from models.text_processor import TextProcessor
from models.feature_extractor import FeatureExtractor
from models.readability_model import ReadabilityModel

processor = TextProcessor()
feature_extractor = FeatureExtractor()
model = ReadabilityModel()
model.load_models()

test_files_dir = os.path.join(os.path.dirname(__file__), 'data', 'test_files')

print("=" * 80)
print("VALIDATING CALIBRATED TEST FILES")
print("=" * 80)

results = []

test_grades = list(range(3, 13)) + ['college']

for grade in test_grades:
    if grade == 'college':
        filename = "college.txt"
        expected_grade = 13.5
    else:
        filename = f"grade_{grade}.txt"
        expected_grade = float(grade)

    filepath = os.path.join(test_files_dir, filename)

    if not os.path.exists(filepath):
        print(f"\n--- {filename} - FILE NOT FOUND ---")
        results.append((grade, None, None))
        continue

    # Read file
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
        # Remove comment lines
        text = '\n'.join(line for line in text.split('\n') if not line.startswith('#'))
        text = text.strip()

    if len(text) < 50:
        print(f"\n--- {filename} - TEXT TOO SHORT ({len(text)} chars) ---")
        results.append((grade, None, None))
        continue

    # Get prediction using model.predict()
    prediction = model.predict(text)

    raw_score = prediction['predictions']['raw_score']
    predicted_grade = prediction['predictions']['predicted_grade_level']
    confidence = prediction['predictions']['confidence']
    flesch_score = prediction['readability_scores']['flesch_reading_ease']
    fk_grade = prediction['readability_scores']['flesch_kincaid_grade']
    basic = prediction['basic_metrics']

    # Parse numeric grade from predicted_grade_level string
    predicted_numeric = raw_score

    # Graduated tolerance reflecting model's inherent MAE (~0.5-0.7)
    if grade == 'college':
        tolerance = 2.0
    elif isinstance(grade, int) and grade >= 9:
        tolerance = 1.5
    else:
        tolerance = 1.0
    error = abs(predicted_numeric - expected_grade)

    if error <= tolerance:
        status = "PASS"
    elif error <= tolerance + 0.5:
        status = "CLOSE"
    else:
        status = "FAIL"

    results.append((grade, predicted_numeric, error))

    grade_label = "College" if grade == 'college' else f"Grade {grade}"
    print(f"\n{'[' + status + ']'} {grade_label}")
    print(f"   Expected: {expected_grade:.1f}")
    print(f"   Predicted: {predicted_numeric:.2f} ({predicted_grade})")
    print(f"   Error: {error:.2f} grades (tolerance: {tolerance})")
    print(f"   Confidence: {confidence}")
    print(f"   Flesch Reading Ease: {flesch_score:.1f}")
    print(f"   Flesch-Kincaid Grade: {fk_grade:.1f}")
    print(f"   Words: {basic['word_count']}")
    print(f"   Sentences: {basic['sentence_count']}")
    print(f"   Avg words/sentence: {basic['avg_sentence_length']:.1f}")
    print(f"   Avg syllables/word: {basic['avg_syllables_per_word']:.2f}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total = len(test_grades)
def get_tolerance(g):
    if g == 'college': return 2.0
    if isinstance(g, int) and g >= 9: return 1.5
    return 1.0

passed = sum(1 for g, p, e in results if e is not None and e <= get_tolerance(g))
close = sum(1 for g, p, e in results if e is not None and e > get_tolerance(g) and e <= get_tolerance(g) + 0.5)
failed = sum(1 for g, p, e in results if e is not None and e > get_tolerance(g) + 0.5)
missing = sum(1 for g, p, e in results if p is None)

print(f"PASS:    {passed}/{total}")
print(f"CLOSE:   {close}/{total}")
print(f"FAIL:    {failed}/{total}")
print(f"MISSING: {missing}/{total}")
