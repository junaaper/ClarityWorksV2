"""Quick text tuning helper - paste text and see what model predicts."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import textstat

from models.readability_model import ReadabilityModel

model = ReadabilityModel()
model.load_models()

def analyze(text, target_grade):
    """Analyze text and show what adjustments are needed."""
    prediction = model.predict(text)
    raw = prediction['predictions']['raw_score']
    fk = prediction['readability_scores']['flesch_kincaid_grade']
    flesch = prediction['readability_scores']['flesch_reading_ease']
    basic = prediction['basic_metrics']

    error = abs(raw - target_grade)
    status = "PASS" if error <= 0.3 else ("CLOSE" if error <= 0.5 else "FAIL")

    print(f"[{status}] Target: {target_grade}, Predicted: {raw:.2f}, Error: {error:.2f}")
    print(f"  FK: {fk:.1f}, Flesch: {flesch:.1f}")
    print(f"  ASL: {basic['avg_sentence_length']:.1f}, ASW: {basic['avg_syllables_per_word']:.2f}")
    print(f"  Words: {basic['word_count']}, Sentences: {basic['sentence_count']}")

    # Suggest adjustments
    if error > 0.3:
        if raw > target_grade:
            diff = raw - target_grade
            print(f"  NEED: Reduce complexity by {diff:.1f} grades")
            if fk > target_grade + 1:
                print(f"  -> FK too high ({fk:.1f}). Shorten sentences or simplify words.")
            if basic['avg_sentence_length'] > 20:
                print(f"  -> Sentences too long ({basic['avg_sentence_length']:.1f}). Add more periods.")
            if basic['avg_syllables_per_word'] > 1.6:
                print(f"  -> Words too complex ({basic['avg_syllables_per_word']:.2f}). Use simpler words.")
        else:
            diff = target_grade - raw
            print(f"  NEED: Increase complexity by {diff:.1f} grades")
            if basic['avg_sentence_length'] < 12:
                print(f"  -> Sentences too short ({basic['avg_sentence_length']:.1f}). Merge some sentences.")
            if basic['avg_syllables_per_word'] < 1.2:
                print(f"  -> Words too simple ({basic['avg_syllables_per_word']:.2f}). Use more complex words.")
    print()

# Test all files
test_dir = os.path.join(os.path.dirname(__file__), 'data', 'test_files')
for grade in range(3, 13):
    filepath = os.path.join(test_dir, f'grade_{grade}.txt')
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            text = '\n'.join(line for line in f.read().split('\n') if not line.startswith('#')).strip()
        if len(text) > 50:
            # Also show textstat sentence count
            ts_sentences = textstat.sentence_count(text)
            ts_syllables = textstat.syllable_count(text)
            ts_words = textstat.lexicon_count(text, removepunct=True)
            print(f"--- Grade {grade} ---")
            print(f"  textstat: sentences={ts_sentences}, words={ts_words}, syllables={ts_syllables}")
            print(f"  textstat ASW={ts_syllables/ts_words:.2f}, ASL={ts_words/ts_sentences:.1f}")
            analyze(text, grade)
