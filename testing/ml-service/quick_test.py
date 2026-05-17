"""Quick inline text tester - reads from stdin, shows metrics."""
import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'ml-service'
sys.path.insert(0, str(ROOT))
import textstat
from models.readability_model import ReadabilityModel

model = ReadabilityModel()
model.load_models()

text = sys.stdin.read().strip()
text = '\n'.join(line for line in text.split('\n') if not line.startswith('#')).strip()

ts_sentences = textstat.sentence_count(text)
ts_words = textstat.lexicon_count(text, removepunct=True)
ts_syllables = textstat.syllable_count(text)
prediction = model.predict(text)
raw = prediction['predictions']['raw_score']
fk = prediction['readability_scores']['flesch_kincaid_grade']
flesch = prediction['readability_scores']['flesch_reading_ease']

target = int(sys.argv[1]) if len(sys.argv) > 1 else 0
error = abs(raw - target) if target else 0
status = "PASS" if error <= 0.3 else ("CLOSE" if error <= 0.5 else "FAIL")

print(f"Words={ts_words} Sents={ts_sentences} Sylls={ts_syllables}")
print(f"ASL={ts_words/ts_sentences:.1f} ASW={ts_syllables/ts_words:.2f}")
print(f"FK={fk:.1f} Flesch={flesch:.1f} Raw={raw:.2f}")
if target:
    print(f"[{status}] Target={target} Error={error:.2f}")
