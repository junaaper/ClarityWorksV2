import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from models.readability_model import ReadabilityModel

model = ReadabilityModel()
model.load_models()

# Test texts at various complexity levels to understand model behavior
test_texts = {
    "very_simple": """Dogs are fun pets. They like to run and play. A dog can be big or small. Some dogs have long hair. Some have short hair. Dogs eat food from a bowl. They need clean water too. Dogs like to go for walks. They wag their tails when they are happy. A dog is a good friend to have at home.""",

    "simple": """Many children enjoy going to the park after school. They play on the swings and slides with their friends. Some children like to kick a ball around the big green field. The park has tall trees that give shade on hot summer days. Birds sing in the branches while kids run and laugh below. When it starts to get dark outside, the children walk home for dinner.""",

    "moderate_easy": """The water cycle is an important process in nature. Water from oceans and lakes evaporates into the atmosphere when heated by the sun. This water vapor rises and forms clouds through condensation. When the clouds become heavy with moisture, precipitation falls as rain or snow. The water then flows through streams and rivers back to the ocean. This continuous cycle helps maintain fresh water supplies around the world.""",

    "moderate": """The American Revolution began as a conflict between thirteen colonies and the British government over issues of taxation and representation. Colonial leaders argued that Parliament had no right to impose taxes without elected colonial representatives present. The famous phrase no taxation without representation became a rallying cry for those seeking independence. After years of increasing tensions, armed conflict erupted at Lexington and Concord in April of seventeen seventy-five.""",

    "moderate_hard": """Photosynthesis represents one of the most fundamental biological processes on Earth, converting solar energy into chemical energy that sustains virtually all terrestrial ecosystems. During the light-dependent reactions occurring within chloroplast thylakoid membranes, photons excite electrons in chlorophyll molecules, initiating an electron transport chain that generates ATP and NADPH. These energy-carrying molecules subsequently drive the Calvin cycle, where carbon dioxide molecules are progressively reduced to form glyceraldehyde three-phosphate.""",

    "hard": """The epistemological implications of quantum mechanical indeterminacy have profoundly challenged traditional philosophical assumptions regarding the fundamental nature of physical reality and the possibility of objective scientific knowledge. Werner Heisenberg's uncertainty principle demonstrates that complementary physical properties cannot simultaneously possess precisely determined values, suggesting inherent limitations to empirical observation that transcend mere technological constraints. This philosophical reorientation necessitates reconsidering established frameworks for understanding the relationship between observational methodology and ontological characterization of subatomic phenomena.""",
}

print("MODEL DIAGNOSTIC - Understanding prediction range")
print("=" * 80)

for name, text in test_texts.items():
    prediction = model.predict(text)
    raw = prediction['predictions']['raw_score']
    grade = prediction['predictions']['predicted_grade_level']
    fk = prediction['readability_scores']['flesch_kincaid_grade']
    flesch = prediction['readability_scores']['flesch_reading_ease']
    basic = prediction['basic_metrics']

    print(f"\n[{name}]")
    print(f"  Raw score: {raw:.2f} -> {grade}")
    print(f"  FK Grade: {fk:.1f}, Flesch: {flesch:.1f}")
    print(f"  Avg sentence length: {basic['avg_sentence_length']:.1f}")
    print(f"  Avg syllables/word: {basic['avg_syllables_per_word']:.2f}")
    print(f"  Word count: {basic['word_count']}, Sentences: {basic['sentence_count']}")
    print(f"  Difficult words %: {prediction['statistics']['difficult_words_percentage']:.1f}%")
