# PROMPT 1: Enhanced Difficulty Detection & Data Files

## Context
You're working on ClarityWorks, a text readability analysis FYP. Review `CLAUDE.md` for full context.

## Objective
Implement enhanced difficulty detection with detailed, specific reasons for why words and sentences are flagged as difficult.

---

## STEP 1: Copy Data Files

Copy the following data files from the provided outputs to `ml-service/data/`:

1. `dale_chall_3000_subset.txt` → `ml-service/data/dale_chall_3000.txt`
2. `simplification_map.json` → `ml-service/data/simplification_map.json`
3. `complexification_map.json` → `ml-service/data/complexification_map.json`
4. `coca_frequency.csv` → `ml-service/data/coca_frequency.csv`
5. `academic_word_list.txt` → `ml-service/data/academic_word_list.txt`

**NOTE:** The Dale-Chall file provided is a subset (~200 words). You can either:
- Use it as-is for testing, OR
- Download the full 3,000-word list from: https://github.com/words/dale-chall

---

## STEP 2: Create Synonym Lookup Module

Create `ml-service/models/synonym_lookup.py`:

```python
import json
import pandas as pd
import os

class SynonymLookup:
    """Manages word lists and synonym mappings for readability analysis"""
    
    def __init__(self):
        base_path = os.path.join(os.path.dirname(__file__), '..', 'data')
        
        # Load simplification map (complex → simple)
        with open(os.path.join(base_path, 'simplification_map.json'), 'r') as f:
            self.simplification_map = json.load(f)
        
        # Load complexification map (simple → complex)
        with open(os.path.join(base_path, 'complexification_map.json'), 'r') as f:
            self.complexification_map = json.load(f)
        
        # Load Dale-Chall easy words (3,000 common words)
        with open(os.path.join(base_path, 'dale_chall_3000.txt'), 'r') as f:
            self.dale_chall_words = set(
                line.strip().lower() 
                for line in f 
                if line.strip() and not line.startswith('#')
            )
        
        # Load COCA word frequency rankings
        self.word_frequency = pd.read_csv(os.path.join(base_path, 'coca_frequency.csv'))
        self.word_freq_dict = dict(zip(
            self.word_frequency['word'], 
            self.word_frequency['rank']
        ))
        
        # Load Academic Word List (570 academic words)
        with open(os.path.join(base_path, 'academic_word_list.txt'), 'r') as f:
            self.academic_words = set(
                line.strip().lower() 
                for line in f 
                if line.strip() and not line.startswith('#')
            )
    
    def get_word_frequency_rank(self, word):
        """
        Get frequency rank from COCA corpus
        
        Args:
            word: Word to check
        
        Returns:
            int: Rank (1 = most common, 999999 = not found)
        """
        return self.word_freq_dict.get(word.lower(), 999999)
    
    def is_academic_word(self, word):
        """Check if word is in Academic Word List (Grade 10+)"""
        return word.lower() in self.academic_words
    
    def is_easy_word(self, word):
        """Check if word is in Dale-Chall easy words list (Grade 4 baseline)"""
        return word.lower() in self.dale_chall_words
    
    def get_simpler_synonym(self, word):
        """
        Get simpler alternative for a complex word
        
        Args:
            word: Complex word
        
        Returns:
            str or None: Simpler synonym if available
        """
        mapping = self.simplification_map.get(word.lower())
        return mapping['simple'] if mapping else None
    
    def get_complex_synonyms(self, word):
        """
        Get more complex alternatives for upgrading text
        
        Args:
            word: Simple word
        
        Returns:
            list: Complex synonyms
        """
        mapping = self.complexification_map.get(word.lower())
        return mapping['complex'] if mapping else []
    
    def get_word_complexity_level(self, word):
        """
        Categorize word complexity based on frequency
        
        Args:
            word: Word to check
        
        Returns:
            str: 'simple', 'intermediate', 'advanced', or 'expert'
        """
        rank = self.get_word_frequency_rank(word)
        
        if rank <= 5000:
            return 'simple'
        elif rank <= 10000:
            return 'intermediate'
        elif rank <= 20000:
            return 'advanced'
        else:
            return 'expert'
```

---

## STEP 3: Update Text Processor with Enhanced Reasons

Modify `ml-service/models/text_processor.py`:

**3.1 Add Import:**

```python
from models.synonym_lookup import SynonymLookup
```

**3.2 Update `__init__` method:**

```python
class TextProcessor:
    def __init__(self):
        # Existing initialization code...
        
        # ADD THIS LINE:
        self.synonym_lookup = SynonymLookup()
```

**3.3 Replace `get_word_difficulty_reason()` method:**

```python
def get_word_difficulty_reason(self, word, syllable_count):
    """
    Generate detailed, specific reason for word difficulty
    
    Args:
        word: The difficult word
        syllable_count: Number of syllables
    
    Returns:
        str: Detailed explanation of why word is difficult
    """
    reasons = []
    
    # 1. Syllable complexity
    if syllable_count >= 4:
        reasons.append(f"{syllable_count} syllables (very complex)")
    elif syllable_count == 3:
        reasons.append(f"{syllable_count} syllables (moderately complex)")
    
    # 2. Word frequency check
    word_rank = self.synonym_lookup.get_word_frequency_rank(word)
    if word_rank > 20000:
        reasons.append(f"extremely rare word (rank #{word_rank:,})")
    elif word_rank > 10000:
        reasons.append(f"rare word (rank #{word_rank:,})")
    elif word_rank > 5000:
        reasons.append(f"uncommon word (rank #{word_rank:,})")
    
    # 3. Dale-Chall easy words check
    if not self.synonym_lookup.is_easy_word(word):
        reasons.append("not in Dale-Chall easy words (Grade 4 baseline)")
    
    # 4. Academic vocabulary check
    if self.synonym_lookup.is_academic_word(word):
        reasons.append("academic vocabulary (Grade 10+ term)")
    
    # 5. Technical suffix detection
    technical_suffixes = [
        ('-ology', 'study of'), 
        ('-ism', 'belief/system'), 
        ('-tion', 'action/process'),
        ('-sion', 'action/process'),
        ('-ment', 'result/action'),
        ('-ance', 'state/quality'),
        ('-ence', 'state/quality'),
        ('-ity', 'state/quality'),
        ('-ness', 'state/quality')
    ]
    
    for suffix, meaning in technical_suffixes:
        if word.lower().endswith(suffix):
            reasons.append(f"technical term ({suffix} = {meaning})")
            break
    
    # 6. Suggest simpler alternative
    simpler = self.synonym_lookup.get_simpler_synonym(word)
    if simpler:
        reasons.append(f"simpler alternative: '{simpler}'")
    
    # Return combined reasons or fallback
    return " | ".join(reasons) if reasons else "flagged as difficult word"
```

**3.4 Replace `get_sentence_difficulty_reason()` method:**

```python
def get_sentence_difficulty_reason(self, sentence, metrics):
    """
    Generate specific, backed-up reason for sentence difficulty
    
    Args:
        sentence: The sentence text
        metrics: Dict with difficulty metrics
    
    Returns:
        str: Detailed explanation
    """
    reasons = []
    
    # 1. Sentence length check
    word_count = metrics.get('word_count', 0)
    if word_count >= 30:
        reasons.append(f"very long sentence ({word_count} words, target <20)")
    elif word_count >= 25:
        reasons.append(f"long sentence ({word_count} words, target <20)")
    
    # 2. Readability score check
    flesch_score = metrics.get('flesch_score', 100)
    if flesch_score < 30:
        reasons.append(f"very low readability ({flesch_score:.1f}/100, target >60)")
    elif flesch_score < 50:
        reasons.append(f"low readability ({flesch_score:.1f}/100, target >60)")
    
    # 3. Difficult words with examples
    difficult_words_count = metrics.get('difficult_words_count', 0)
    difficult_words = metrics.get('difficult_words', [])
    
    if difficult_words_count >= 5:
        examples = ", ".join(difficult_words[:3])
        reasons.append(f"{difficult_words_count} difficult words (e.g., {examples})")
    elif difficult_words_count >= 3:
        examples = ", ".join(difficult_words[:3])
        reasons.append(f"{difficult_words_count} difficult words ({examples})")
    
    # 4. Polysyllabic word count
    polysyllabic_count = metrics.get('polysyllabic_count', 0)
    if polysyllabic_count >= 7:
        reasons.append(f"{polysyllabic_count} complex words (3+ syllables)")
    elif polysyllabic_count >= 5:
        reasons.append(f"{polysyllabic_count} moderately complex words (3+ syllables)")
    
    # 5. Passive voice detection
    has_passive = metrics.get('has_passive_voice', False)
    if has_passive:
        reasons.append("passive voice detected (less direct)")
    
    # 6. Subordinate clauses
    subordinate_clauses = metrics.get('subordinate_clauses', 0)
    if subordinate_clauses >= 3:
        reasons.append(f"{subordinate_clauses} embedded clauses (complex structure)")
    elif subordinate_clauses >= 2:
        reasons.append(f"{subordinate_clauses} embedded clauses")
    
    # Return combined reasons or fallback
    return " | ".join(reasons) if reasons else "complex sentence structure"
```

---

## STEP 4: Update Difficult Sentence Detection

In `ml-service/models/text_processor.py`, find the `identify_difficult_sentences()` method and update it to calculate the additional metrics needed for detailed reasons:

```python
def identify_difficult_sentences(self, text, sentences):
    """
    Identify sentences that are difficult to read
    
    Args:
        text: Full text
        sentences: List of sentences
    
    Returns:
        list: Difficult sentence objects with detailed reasons
    """
    difficult_sentences = []
    
    for i, sentence in enumerate(sentences):
        sentence_text = sentence.strip()
        if not sentence_text:
            continue
        
        words = sentence_text.split()
        word_count = len(words)
        
        # Calculate Flesch score for this sentence
        flesch_score = self.calculate_flesch_score_for_sentence(sentence_text)
        
        # Count difficult words in sentence
        difficult_words_in_sentence = []
        polysyllabic_count = 0
        
        for word in words:
            clean_word = word.strip('.,!?;:"()[]{}').lower()
            if not clean_word:
                continue
            
            syllables = self.count_syllables(clean_word)
            if syllables >= 3:
                polysyllabic_count += 1
            
            # Check if word is difficult
            if (len(clean_word) >= 4 and 
                syllables >= 3 and 
                not self.synonym_lookup.is_easy_word(clean_word) and
                not self.is_proper_noun_or_abbreviation(word)):
                difficult_words_in_sentence.append(clean_word)
        
        difficult_words_count = len(difficult_words_in_sentence)
        
        # Detect passive voice (simple heuristic)
        has_passive_voice = self.detect_passive_voice(sentence_text)
        
        # Count subordinate clauses (simple heuristic)
        subordinate_clauses = self.count_subordinate_clauses(sentence_text)
        
        # Determine if sentence is difficult (multiple criteria)
        is_difficult = False
        
        # Criteria 1: Long sentence
        if word_count >= 25:
            is_difficult = True
        
        # Criteria 2: Low Flesch score with difficult words
        if flesch_score < 30 and difficult_words_count >= 2:
            is_difficult = True
        
        # Criteria 3: Many difficult words
        if difficult_words_count >= 3:
            is_difficult = True
        
        # Criteria 4: Many polysyllabic words
        if polysyllabic_count >= 5:
            is_difficult = True
        
        if is_difficult:
            metrics = {
                'word_count': word_count,
                'flesch_score': flesch_score,
                'difficult_words_count': difficult_words_count,
                'difficult_words': difficult_words_in_sentence,
                'polysyllabic_count': polysyllabic_count,
                'has_passive_voice': has_passive_voice,
                'subordinate_clauses': subordinate_clauses
            }
            
            reason = self.get_sentence_difficulty_reason(sentence_text, metrics)
            
            difficult_sentences.append({
                'sentence': sentence_text,
                'position': i,
                'word_count': word_count,
                'reason': reason,
                'flesch_score': round(flesch_score, 1)
            })
    
    return difficult_sentences

def calculate_flesch_score_for_sentence(self, sentence):
    """Calculate Flesch Reading Ease for a single sentence"""
    words = sentence.split()
    word_count = len(words)
    
    if word_count == 0:
        return 100.0
    
    syllable_count = sum(self.count_syllables(word.strip('.,!?;:"()[]{}')) for word in words)
    
    # Flesch formula: 206.835 - 1.015(words/sentences) - 84.6(syllables/words)
    avg_syllables_per_word = syllable_count / word_count if word_count > 0 else 0
    score = 206.835 - 1.015 * word_count - 84.6 * avg_syllables_per_word
    
    # Clamp to 0-100
    return max(0, min(100, score))

def detect_passive_voice(self, sentence):
    """
    Simple heuristic to detect passive voice
    Looks for: "was/were/is/are/been + past participle"
    """
    passive_indicators = [
        'was ', 'were ', 'is ', 'are ', 'been ',
        'was not', 'were not', 'is not', 'are not'
    ]
    
    sentence_lower = sentence.lower()
    for indicator in passive_indicators:
        if indicator in sentence_lower:
            return True
    
    return False

def count_subordinate_clauses(self, sentence):
    """
    Simple heuristic to count subordinate clauses
    Looks for: which, that, because, although, when, while, etc.
    """
    clause_markers = [
        'which', 'that', 'because', 'although', 'though',
        'when', 'while', 'where', 'who', 'whom', 'whose',
        'if', 'unless', 'until', 'since', 'after', 'before'
    ]
    
    words = sentence.lower().split()
    count = 0
    
    for marker in clause_markers:
        if marker in words:
            count += 1
    
    return count
```

---

## STEP 5: Test the Implementation

**5.1 Create Test Script**

Create `ml-service/test_enhanced_reasons.py`:

```python
from models.text_processor import TextProcessor

processor = TextProcessor()

# Test text with difficult words and sentences
test_text = """
The comprehensive implementation of this methodology necessitates careful consideration. 
Students utilize various approaches to facilitate understanding.
The cat sat on the mat. She was happy.
Photosynthesis is the process by which plants convert sunlight into energy through complex biochemical reactions.
"""

# Process text
result = processor.process_text(test_text)

print("=== DIFFICULT WORDS ===")
for word in result['difficult_words']:
    print(f"\nWord: {word['word']}")
    print(f"Reason: {word['reason']}")

print("\n\n=== DIFFICULT SENTENCES ===")
for sent in result['difficult_sentences']:
    print(f"\nSentence: {sent['sentence']}")
    print(f"Reason: {sent['reason']}")
```

**5.2 Run Test:**

```bash
cd ml-service
python test_enhanced_reasons.py
```

**Expected Output:**

```
=== DIFFICULT WORDS ===

Word: comprehensive
Reason: 4 syllables (very complex) | uncommon word (rank #10,500) | not in Dale-Chall easy words (Grade 4 baseline) | simpler alternative: 'complete'

Word: implementation
Reason: 5 syllables (very complex) | uncommon word (rank #8,200) | not in Dale-Chall easy words (Grade 4 baseline)

Word: methodology
Reason: 5 syllables (very complex) | uncommon word (rank #12,000) | not in Dale-Chall easy words (Grade 4 baseline) | technical term (-ology = study of) | simpler alternative: 'method'

...
```

---

## DELIVERABLES

1. ✅ All 5 data files copied to `ml-service/data/`
2. ✅ `synonym_lookup.py` module created
3. ✅ Enhanced `get_word_difficulty_reason()` with 6 checks
4. ✅ Enhanced `get_sentence_difficulty_reason()` with 6 checks
5. ✅ Updated `identify_difficult_sentences()` with detailed metrics
6. ✅ Added helper methods: `calculate_flesch_score_for_sentence()`, `detect_passive_voice()`, `count_subordinate_clauses()`
7. ✅ Test script to verify enhanced reasons

---

## SUCCESS CRITERIA

Run the test script. You should see:
- ✅ Difficult words have **multiple specific reasons** (syllables, frequency rank, Dale-Chall, academic, technical suffix, simpler alternative)
- ✅ Difficult sentences have **specific reasons** (word count, Flesch score, difficult word examples, polysyllabic count, passive voice, subordinate clauses)
- ✅ No generic "complex word" or "long sentence" messages

---

**After completing this prompt, proceed to PROMPT_2_Calibrated_Tests.md**
