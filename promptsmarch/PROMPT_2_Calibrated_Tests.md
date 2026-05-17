# PROMPT 2: Calibrated Test Files

## Context
You're working on ClarityWorks FYP. You've already completed **Prompt 1** (Enhanced Difficulty Detection). Now create calibrated test files for demonstration purposes.

## Objective
Create 10 text files (one per grade level 3-12) that produce **exact** grade predictions when analyzed by the ML model. These will be used to demonstrate the model's accuracy during the FYP presentation.

---

## STEP 1: Create Test Files Directory

Create directory structure:
```
ml-service/
├── data/
│   └── test_files/
│       ├── grade_3.txt
│       ├── grade_4.txt
│       ├── grade_5.txt
│       ├── grade_6.txt
│       ├── grade_7.txt
│       ├── grade_8.txt
│       ├── grade_9.txt
│       ├── grade_10.txt
│       ├── grade_11.txt
│       └── grade_12.txt
```

---

## STEP 2: Writing Guidelines Per Grade

Each file should follow these guidelines:

### **Grade 3**
- **Words per sentence:** 8-10
- **Syllables per word:** 1-2 (mostly 1)
- **Vocabulary:** Simple, everyday words (all in Dale-Chall list)
- **Flesch score target:** 85-90
- **Sentence structure:** Simple declarative sentences, present/past tense
- **Example topics:** Animals, family, daily activities

### **Grade 4**
- **Words per sentence:** 10-12
- **Syllables per word:** 1-2 (occasional 3)
- **Vocabulary:** Common words, simple adjectives/adverbs
- **Flesch score target:** 80-85
- **Sentence structure:** Simple + occasional compound (and, but)
- **Example topics:** School, nature, simple science

### **Grade 5**
- **Words per sentence:** 12-15
- **Syllables per word:** Mix of 1-3
- **Vocabulary:** Introduce basic academic words
- **Flesch score target:** 75-80
- **Sentence structure:** Compound sentences common
- **Example topics:** History, geography, basic concepts

### **Grade 6**
- **Words per sentence:** 15-18
- **Syllables per word:** 2-3 common
- **Vocabulary:** Academic vocabulary begins
- **Flesch score target:** 70-75
- **Sentence structure:** Some complex sentences (because, when)
- **Example topics:** Science processes, historical events

### **Grade 7**
- **Words per sentence:** 16-19
- **Syllables per word:** 2-3, some 4
- **Vocabulary:** More academic/technical terms
- **Flesch score target:** 65-70
- **Sentence structure:** Complex sentences with subordinate clauses
- **Example topics:** Scientific concepts, social studies

### **Grade 8**
- **Words per sentence:** 18-22
- **Syllables per word:** 3-4 common
- **Vocabulary:** Academic + some technical terms
- **Flesch score target:** 60-65
- **Sentence structure:** Multiple clause structures
- **Example topics:** Advanced science, literary analysis

### **Grade 9**
- **Words per sentence:** 20-24
- **Syllables per word:** 3-4, occasional 5
- **Vocabulary:** Technical vocabulary, subject-specific terms
- **Flesch score target:** 55-60
- **Sentence structure:** Complex, nested clauses
- **Example topics:** Chemistry, algebra concepts, literature

### **Grade 10**
- **Words per sentence:** 22-26
- **Syllables per word:** 3-5
- **Vocabulary:** Sophisticated academic vocabulary
- **Flesch score target:** 50-55
- **Sentence structure:** Advanced complexity, multiple embedded clauses
- **Example topics:** Historical analysis, scientific processes

### **Grade 11**
- **Words per sentence:** 24-28
- **Syllables per word:** 4-5
- **Vocabulary:** Advanced academic, abstract concepts
- **Flesch score target:** 45-50
- **Sentence structure:** Sophisticated sentence structures
- **Example topics:** Philosophy, advanced science, literary criticism

### **Grade 12 / College**
- **Words per sentence:** 26-30+
- **Syllables per word:** 4-6
- **Vocabulary:** Highly technical, discipline-specific
- **Flesch score target:** 35-45
- **Sentence structure:** Very complex, academic prose
- **Example topics:** Epistemology, theoretical frameworks, research

---

## STEP 3: Create Each Test File

I've already provided examples for Grade 3, 6, 10, and 12 in the test_files directory. Use those as templates.

**For each remaining grade (4, 5, 7, 8, 9, 11), create a text file following this structure:**

```
# Grade [X] Test Text
# Expected: Grade [X], Flesch [target range], [vocabulary level]
# Purpose: Demonstration of accurate Grade [X] prediction

[4-5 paragraphs of text following the guidelines above]
```

**Example for Grade 4:**

```
# Grade 4 Test Text
# Expected: Grade 4, Flesch 80-85, Simple vocabulary with basic adjectives
# Purpose: Demonstration of accurate Grade 4 prediction

The big brown dog lived on a small farm. Every morning, he would wake up early and run through the green fields. The dog loved to play with the other animals.

One sunny day, the dog found a red ball near the old barn. He picked it up and brought it to his favorite spot under the tall oak tree. The dog was very happy with his new toy.

The farmer saw the dog playing and smiled. He knew that the dog worked hard every day to help on the farm. The farmer decided to give the dog a special treat for being such a good helper.

At the end of the day, the tired dog went back to his cozy house. He fell asleep quickly, dreaming about the fun he would have tomorrow.
```

---

## STEP 4: Validation Process

After creating each file, validate it:

**4.1 Create Validation Script**

Create `testing/ml-service/validate_test_files.py`:

```python
from models.text_processor import TextProcessor
from models.feature_extractor import FeatureExtractor
from models.readability_model import ReadabilityModel
import os

processor = TextProcessor()
feature_extractor = FeatureExtractor()
model = ReadabilityModel()

test_files_dir = 'data/test_files'

print("=" * 80)
print("VALIDATING CALIBRATED TEST FILES")
print("=" * 80)

for grade in range(3, 13):
    filename = f"grade_{grade}.txt"
    filepath = os.path.join(test_files_dir, filename)
    
    if not os.path.exists(filepath):
        print(f"\n❌ {filename} - FILE NOT FOUND")
        continue
    
    # Read file
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
        # Remove comment lines
        text = '\n'.join(line for line in text.split('\n') if not line.startswith('#'))
    
    # Process
    basic_metrics = processor.process_text(text)
    features = feature_extractor.extract_features(text)
    
    # Predict
    prediction = model.predict_grade_level(features)
    predicted_grade = prediction['grade_numeric']
    flesch_score = features.get('flesch_reading_ease', 0)
    
    # Check accuracy (±0.3 tolerance)
    error = abs(predicted_grade - grade)
    
    if error <= 0.3:
        status = "✅ PASS"
    elif error <= 0.5:
        status = "⚠️  CLOSE"
    else:
        status = "❌ FAIL"
    
    print(f"\n{status} Grade {grade}")
    print(f"   Predicted: {predicted_grade:.2f}")
    print(f"   Error: {error:.2f} grades")
    print(f"   Flesch: {flesch_score:.1f}")
    print(f"   Words: {basic_metrics['word_count']}")
    print(f"   Sentences: {basic_metrics['sentence_count']}")
    print(f"   Avg words/sentence: {basic_metrics['avg_sentence_length']:.1f}")

print("\n" + "=" * 80)
```

**4.2 Run Validation:**

```bash
cd ml-service
python testing/ml-service/validate_test_files.py
```

**4.3 Iterate Until All Pass:**

For any file that FAILS (error > 0.3 grades):

**If predicted TOO HIGH (e.g., Grade 4 text predicted as 5.8):**
- Make sentences shorter
- Use simpler words (fewer syllables)
- Remove academic vocabulary
- Simplify sentence structures

**If predicted TOO LOW (e.g., Grade 8 text predicted as 6.5):**
- Make sentences longer
- Add more complex words (more syllables)
- Use academic/technical vocabulary
- Add subordinate clauses

Adjust and re-run validation until all 10 files show ✅ PASS.

---

## STEP 5: Document Final Metrics

Once all files pass validation, update the comment header in each file with actual metrics:

```
# Grade [X] Test Text
# Validated Prediction: Grade [X.XX]
# Flesch Score: [XX.X]
# Avg Words/Sentence: [XX.X]
# Purpose: Demonstration file for FYP presentation
```

---

## DELIVERABLES

1. ✅ 10 test files created (grade_3.txt through grade_12.txt)
2. ✅ Each file produces prediction within ±0.3 grades of target
3. ✅ Validation script confirms all files pass
4. ✅ File headers updated with validated metrics

---

## SUCCESS CRITERIA

Run `python testing/ml-service/validate_test_files.py` and see:

```
✅ PASS Grade 3
   Predicted: 3.12
   Error: 0.12 grades
   ...

✅ PASS Grade 4
   Predicted: 4.08
   Error: 0.08 grades
   ...

[All 10 grades show ✅ PASS]
```

---

## TIPS FOR WRITING

1. **Use real content** - Don't write nonsense. Use actual educational topics appropriate for each grade.

2. **Vary sentence length** - Don't make every sentence exactly the same length. Have variation but keep average within target.

3. **Natural flow** - Text should read naturally, not forced. Imagine it's from a real textbook.

4. **Check syllables** - When in doubt, count syllables manually. "Computer" = 3, "Technology" = 4.

5. **Test incrementally** - Write Grade 4, validate, then Grade 5, validate, etc. Don't write all 10 before testing.

---

**After completing this prompt, proceed to PROMPT_3_Simplification.md**
