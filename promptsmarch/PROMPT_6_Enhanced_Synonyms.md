# PROMPT 6: Enhanced Synonym Mapping & Groq Integration

## Context
You've completed Prompts 1-5. The simplification feature works but only has ~50 manual synonym mappings. This prompt adds comprehensive synonym coverage using WordNet + Datamuse API + Groq validation.

## Objective
- Integrate WordNet for 100,000+ synonyms (offline, free)
- Add Datamuse API as fallback (500,000+ words, free, no key)
- Add Groq API for validation and edge cases
- Make rule-based simplification comprehensive

---

## STEP 1: Set Up Groq API (FREE)

### 1.1 Sign Up for Groq

**Go to:** https://console.groq.com/

**Steps:**
1. Click "Sign Up" (top right)
2. Create account (use GitHub or email)
3. Verify email if needed

### 1.2 Create API Key

1. After login, go to: https://console.groq.com/keys
2. Click "Create API Key"
3. Name it: `ClarityWorks`
4. Click "Create"
5. **Copy the key** (starts with `gsk_`)

**IMPORTANT:** Save the key somewhere safe - you can't see it again!

### 1.3 Add API Key to Project

**Open:** `ml-service/.env`

**Add this line:**
```
GROQ_API_KEY=gsk_your_actual_key_here
```

**Example:**
```
FLASK_PORT=5001
FLASK_ENV=production
TESSERACT_PATH=C:/Program Files/Tesseract-OCR/tesseract.exe
GROQ_API_KEY=gsk_abc123xyz456def789
```

### 1.4 Verify Installation

**Check if Groq is installed:**
```bash
cd ml-service
pip show groq
```

**If not installed:**
```bash
pip install groq
```

**Test the API key:**
```bash
python -c "from groq import Groq; import os; client = Groq(api_key=os.getenv('GROQ_API_KEY')); print('✅ Groq API connected!')"
```

You should see: `✅ Groq API connected!`

**If error:** Check your `.env` file and make sure the key is correct.

---

## STEP 2: Install NLTK and Download WordNet

### 2.1 Install NLTK

```bash
cd ml-service
pip install nltk
```

### 2.2 Download WordNet Data

**Create script:** `ml-service/download_wordnet.py`

```python
import nltk
import ssl

# Fix SSL certificate issue (if any)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Download WordNet
print("Downloading WordNet...")
nltk.download('wordnet')
nltk.download('omw-1.4')  # Open Multilingual WordNet
print("✅ WordNet downloaded successfully!")
```

**Run it:**
```bash
python download_wordnet.py
```

This downloads ~10MB of synonym data to your system.

---

## STEP 3: Create WordNet Synonym Finder

**Create file:** `ml-service/models/wordnet_synonyms.py`

```python
from nltk.corpus import wordnet
from models.synonym_lookup import SynonymLookup
import nltk

# Ensure WordNet is available
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    print("WordNet not found. Run: python download_wordnet.py")

class WordNetSynonymFinder:
    """Find simpler synonyms using WordNet (117,000 word senses)"""
    
    def __init__(self):
        self.synonym_lookup = SynonymLookup()
    
    def get_simpler_synonym(self, word, target_grade=6):
        """
        Get simpler synonym using WordNet
        
        Args:
            word: Complex word to simplify
            target_grade: Target grade level (not used yet, for future)
        
        Returns:
            str or None: Simpler synonym if found
        """
        
        # Get all WordNet synonyms
        synonyms = self._get_wordnet_synonyms(word)
        
        if not synonyms:
            return None
        
        # Find the simplest one
        return self._find_simplest_synonym(word, synonyms)
    
    def _get_wordnet_synonyms(self, word):
        """Get all synonyms from WordNet"""
        synonyms = set()
        
        # Get all synsets (synonym sets) for this word
        for synset in wordnet.synsets(word):
            # Get all lemmas (word forms) in this synset
            for lemma in synset.lemmas():
                # Get the word (replace underscores with spaces)
                synonym = lemma.name().replace('_', ' ')
                
                # Skip the original word
                if synonym.lower() != word.lower():
                    synonyms.add(synonym)
        
        return list(synonyms)
    
    def _find_simplest_synonym(self, original_word, synonyms):
        """
        Find simplest synonym based on:
        1. Word frequency (more common = simpler)
        2. Word length (shorter = simpler)
        3. Syllable count (fewer = simpler)
        """
        
        scored_synonyms = []
        
        for synonym in synonyms:
            # Skip if longer than original
            if len(synonym) > len(original_word):
                continue
            
            # Get frequency rank from COCA
            freq_rank = self.synonym_lookup.get_word_frequency_rank(synonym)
            
            # Calculate score (lower is better)
            # Prioritize frequency, then length
            score = freq_rank + (len(synonym) * 100)
            
            scored_synonyms.append({
                'word': synonym,
                'score': score,
                'freq_rank': freq_rank,
                'length': len(synonym)
            })
        
        if not scored_synonyms:
            return None
        
        # Sort by score (lower = better)
        scored_synonyms.sort(key=lambda x: x['score'])
        
        # Get best synonym
        best = scored_synonyms[0]
        
        # Only return if it's actually common (rank < 10,000)
        # This filters out obscure synonyms
        if best['freq_rank'] < 10000:
            return best['word']
        
        return None


# Test function
def test_wordnet():
    """Test WordNet synonym finder"""
    finder = WordNetSynonymFinder()
    
    test_words = [
        "utilize",
        "commence",
        "purchase",
        "assistance",
        "demonstrate",
        "comprehensive",
        "facilitate",
        "photosynthesis"  # Should return None (no simpler synonym)
    ]
    
    print("=" * 60)
    print("TESTING WORDNET SYNONYM FINDER")
    print("=" * 60)
    
    for word in test_words:
        synonym = finder.get_simpler_synonym(word)
        if synonym:
            print(f"✓ {word:20s} → {synonym}")
        else:
            print(f"✗ {word:20s} → (no simpler synonym)")

if __name__ == "__main__":
    test_wordnet()
```

**Test it:**
```bash
python -m models.wordnet_synonyms
```

**Expected output:**
```
✓ utilize              → use
✓ commence             → start
✓ purchase             → buy
✓ assistance           → help
✓ demonstrate          → show
✓ comprehensive        → complete
✓ facilitate           → help
✗ photosynthesis       → (no simpler synonym)
```

---

## STEP 4: Create Datamuse API Fallback

**Create file:** `ml-service/models/datamuse_synonyms.py`

```python
import requests

class DatamuseSynonymFinder:
    """
    Find simpler synonyms using Datamuse API
    API: Free, unlimited, no key required
    Docs: https://www.datamuse.com/api/
    """
    
    def __init__(self):
        self.base_url = "https://api.datamuse.com/words"
    
    def get_simpler_synonym(self, word):
        """
        Query Datamuse API for simpler synonyms
        
        Args:
            word: Complex word to simplify
        
        Returns:
            str or None: Simpler synonym if found
        """
        try:
            # Query for words with similar meaning
            # ml = means like
            # md=f = include frequency data
            params = {
                'ml': word,
                'md': 'f',  # Include frequency
                'max': 20   # Top 20 results
            }
            
            response = requests.get(
                self.base_url,
                params=params,
                timeout=3  # 3 second timeout
            )
            
            if response.status_code != 200:
                return None
            
            results = response.json()
            
            # Find simplest synonym
            return self._find_simplest(word, results)
        
        except Exception as e:
            print(f"Datamuse API error: {e}")
            return None
    
    def _find_simplest(self, original_word, results):
        """Find simplest synonym from Datamuse results"""
        
        for result in results:
            synonym = result.get('word', '')
            tags = result.get('tags', [])
            
            # Skip if no word
            if not synonym:
                continue
            
            # Skip if same as original
            if synonym.lower() == original_word.lower():
                continue
            
            # Skip if longer than original
            if len(synonym) > len(original_word):
                continue
            
            # Check if it has frequency data
            has_freq = any('f:' in str(tag) for tag in tags)
            
            if has_freq:
                return synonym
        
        return None


# Test function
def test_datamuse():
    """Test Datamuse API"""
    finder = DatamuseSynonymFinder()
    
    test_words = [
        "utilize",
        "commence",
        "purchase",
        "assistance",
        "demonstrate",
        "methodology"
    ]
    
    print("=" * 60)
    print("TESTING DATAMUSE API")
    print("=" * 60)
    
    for word in test_words:
        synonym = finder.get_simpler_synonym(word)
        if synonym:
            print(f"✓ {word:20s} → {synonym}")
        else:
            print(f"✗ {word:20s} → (no result)")

if __name__ == "__main__":
    test_datamuse()
```

**Test it:**
```bash
python -m models.datamuse_synonyms
```

---

## STEP 5: Create Groq Validator

**Create file:** `ml-service/models/groq_validator.py`

```python
from groq import Groq
import os
import json

class GroqValidator:
    """Use Groq to validate rule-based simplification changes"""
    
    def __init__(self):
        api_key = os.getenv('GROQ_API_KEY')
        
        if not api_key:
            print("⚠️  GROQ_API_KEY not found in .env")
            print("⚠️  Groq validation will be disabled")
            self.client = None
        else:
            self.client = Groq(api_key=api_key)
            print("✅ Groq API initialized")
    
    def validate_changes(self, original_text, simplified_text, changes):
        """
        Ask Groq: Are these simplification changes correct?
        
        Args:
            original_text: Original text
            simplified_text: Simplified text
            changes: List of change objects
        
        Returns:
            {
                'valid': bool,
                'issues': [list of issues],
                'suggestions': [list of suggestions]
            }
        """
        
        if not self.client:
            # No Groq API, assume valid
            return {
                'valid': True,
                'issues': [],
                'suggestions': []
            }
        
        try:
            # Format changes for prompt
            changes_summary = "\n".join([
                f"- Changed '{c['original']}' to '{c['simplified']}': {c['reason']}"
                for c in changes[:10]  # Show first 10 changes
            ])
            
            prompt = f"""You are a text simplification validator. Review these changes.

ORIGINAL TEXT:
{original_text[:500]}

SIMPLIFIED TEXT:
{simplified_text[:500]}

CHANGES MADE:
{changes_summary}

TASK:
1. Do the changes preserve the original meaning?
2. Are the word replacements appropriate?
3. Are there any errors or awkward phrasings?

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "valid": true or false,
  "issues": ["issue1", "issue2"],
  "suggestions": ["suggestion1", "suggestion2"]
}}"""
            
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            # Parse response
            content = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            
            result = json.loads(content)
            
            return {
                'valid': result.get('valid', True),
                'issues': result.get('issues', []),
                'suggestions': result.get('suggestions', [])
            }
        
        except Exception as e:
            print(f"Groq validation error: {e}")
            # On error, assume valid (don't block simplification)
            return {
                'valid': True,
                'issues': [],
                'suggestions': []
            }
    
    def fix_with_groq(self, text, target_grade, issues):
        """
        Let Groq fix the simplification if validation found issues
        
        Args:
            text: Current simplified text (with issues)
            target_grade: Target grade level
            issues: List of issues from validation
        
        Returns:
            str: Improved simplified text
        """
        
        if not self.client:
            return text
        
        try:
            issues_text = "\n".join([f"- {issue}" for issue in issues])
            
            prompt = f"""Simplify this text to Grade {target_grade} level.

CURRENT TEXT:
{text}

ISSUES TO FIX:
{issues_text}

RULES:
- Fix the issues mentioned above
- Use simple words and short sentences
- Preserve the original meaning
- Target: Grade {target_grade} reading level

Respond with ONLY the improved text (no explanations):"""
            
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"Groq fix error: {e}")
            return text


# Test function
def test_groq_validator():
    """Test Groq validator"""
    validator = GroqValidator()
    
    if not validator.client:
        print("❌ Groq API not configured. Add GROQ_API_KEY to .env")
        return
    
    original = "The comprehensive implementation of this methodology necessitates careful consideration."
    simplified = "The complete use of this method needs careful thought."
    changes = [
        {
            'original': 'comprehensive',
            'simplified': 'complete',
            'reason': 'Simpler word'
        },
        {
            'original': 'implementation',
            'simplified': 'use',
            'reason': 'More direct'
        }
    ]
    
    print("=" * 60)
    print("TESTING GROQ VALIDATOR")
    print("=" * 60)
    
    result = validator.validate_changes(original, simplified, changes)
    
    print(f"\nValid: {result['valid']}")
    print(f"Issues: {result['issues']}")
    print(f"Suggestions: {result['suggestions']}")

if __name__ == "__main__":
    test_groq_validator()
```

**Test it:**
```bash
python -m models.groq_validator
```

---

## STEP 6: Update Simplifier with Hybrid Approach

**Modify:** `ml-service/models/simplifier.py`

**Add imports at top:**
```python
from models.wordnet_synonyms import WordNetSynonymFinder
from models.datamuse_synonyms import DatamuseSynonymFinder
from models.groq_validator import GroqValidator
```

**Update `__init__` method:**
```python
def __init__(self):
    self.synonym_lookup = SynonymLookup()  # Manual mappings
    self.wordnet_finder = WordNetSynonymFinder()  # WordNet
    self.datamuse_finder = DatamuseSynonymFinder()  # Datamuse API
    self.groq_validator = GroqValidator()  # Groq validation
    
    # Initialize Groq client (if available)
    self.groq_client = None
    if os.getenv('GROQ_API_KEY'):
        try:
            from groq import Groq
            self.groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
            print("✅ Groq client initialized for simplification")
        except Exception as e:
            print(f"⚠️  Groq initialization failed: {e}")
    
    # Grade constraints (existing code)
    self.grade_constraints = { ... }
```

**Add new method `_get_simpler_synonym_hybrid`:**
```python
def _get_simpler_synonym_hybrid(self, word):
    """
    Try multiple methods to find simpler synonym:
    1. Manual mapping (fastest, most accurate)
    2. WordNet (comprehensive, offline)
    3. Datamuse API (fallback, online)
    
    Args:
        word: Complex word to simplify
    
    Returns:
        str or None: Simpler synonym
    """
    
    # Method 1: Manual mapping
    result = self.synonym_lookup.get_simpler_synonym(word)
    if result:
        return result
    
    # Method 2: WordNet
    result = self.wordnet_finder.get_simpler_synonym(word)
    if result:
        return result
    
    # Method 3: Datamuse API (slower, use as last resort)
    result = self.datamuse_finder.get_simpler_synonym(word)
    if result:
        return result
    
    return None
```

**Update `replace_difficult_words` method:**

Replace the existing method with this enhanced version:

```python
def replace_difficult_words(self, text, target_grade):
    """Replace difficult words with simpler synonyms (ENHANCED)"""
    changes = []
    doc = nlp(text)
    new_text = text
    offset = 0
    
    for token in doc:
        if not token.is_alpha or token.is_stop:
            continue
        
        word_lower = token.text.lower()
        
        # Try hybrid synonym finder
        simple_word = self._get_simpler_synonym_hybrid(word_lower)
        
        if simple_word:
            # Preserve capitalization
            if token.text[0].isupper():
                simple_word = simple_word.capitalize()
            
            # Replace in text
            start = token.idx + offset
            end = start + len(token.text)
            new_text = new_text[:start] + simple_word + new_text[end:]
            offset += len(simple_word) - len(token.text)
            
            # Get metadata for change
            original_rank = self.synonym_lookup.get_word_frequency_rank(word_lower)
            simple_rank = self.synonym_lookup.get_word_frequency_rank(simple_word)
            
            changes.append({
                'type': 'word_replacement',
                'original': token.text,
                'simplified': simple_word,
                'position': token.idx,
                'reason': f"'{token.text}' (rank #{original_rank:,}) → '{simple_word}' (rank #{simple_rank:,}): More common and simpler word",
                'id': len(changes)
            })
    
    return new_text, changes
```

**Update `simplify_to_grade` method to include validation:**

Replace the existing method:

```python
def simplify_to_grade(self, text, target_grade):
    """
    Main simplification function (ENHANCED WITH VALIDATION)
    
    Args:
        text: Original text
        target_grade: Target grade level (3-12)
    
    Returns:
        {
            'simplified_text': str,
            'changes': [list of change objects],
            'original_text': str,
            'validation': {validation results}
        }
    """
    original_text = text
    changes = []
    
    # STEP 1: Rule-based word replacement (with hybrid synonym finder)
    text, word_changes = self.replace_difficult_words(text, target_grade)
    changes.extend(word_changes)
    
    # STEP 2: Sentence splitting
    text, split_changes = self.split_long_sentences(text, target_grade)
    changes.extend(split_changes)
    
    # STEP 3: Passive to active voice
    text, voice_changes = self.convert_passive_to_active(text)
    changes.extend(voice_changes)
    
    # STEP 4: Groq validation (sanity check)
    validation = self.groq_validator.validate_changes(
        original_text,
        text,
        changes
    )
    
    # STEP 5: If validation found issues, let Groq fix them
    if not validation['valid'] and validation['issues']:
        print(f"⚠️  Validation found issues: {validation['issues']}")
        print("🔄 Applying Groq corrections...")
        
        fixed_text = self.groq_validator.fix_with_groq(
            text,
            target_grade,
            validation['issues']
        )
        
        if fixed_text != text:
            changes.append({
                'type': 'groq_correction',
                'original': text,
                'simplified': fixed_text,
                'position': 0,
                'reason': f"Groq AI corrected issues: {', '.join(validation['issues'])}",
                'id': len(changes)
            })
            text = fixed_text
    
    # STEP 6: Final Groq fallback for remaining complexity
    if self._needs_groq_help(text, target_grade):
        text, groq_changes = self.groq_fallback(text, target_grade)
        changes.extend(groq_changes)
    
    return {
        'simplified_text': text,
        'changes': changes,
        'original_text': original_text,
        'validation': validation
    }
```

---

## STEP 7: Test the Enhanced Simplifier

**Create test script:** `testing/ml-service/test_enhanced_simplifier.py`

```python
from models.simplifier import TextSimplifier

simplifier = TextSimplifier()

# Test text with difficult words
test_text = """
The comprehensive implementation of this innovative methodology necessitates 
meticulous consideration of numerous variables. Researchers endeavor to 
demonstrate the efficacy of their approach through rigorous experimentation.
"""

print("=" * 80)
print("ENHANCED SIMPLIFICATION TEST")
print("=" * 80)

print("\nORIGINAL TEXT:")
print(test_text)

# Simplify to Grade 6
result = simplifier.simplify_to_grade(test_text, target_grade=6)

print("\n" + "=" * 80)
print("SIMPLIFIED TEXT (Grade 6):")
print("=" * 80)
print(result['simplified_text'])

print("\n" + "=" * 80)
print(f"CHANGES APPLIED ({len(result['changes'])} total):")
print("=" * 80)

for i, change in enumerate(result['changes'], 1):
    print(f"\n{i}. {change['type'].upper()}")
    print(f"   Original: {change['original']}")
    print(f"   Simplified: {change['simplified']}")
    print(f"   Reason: {change['reason']}")

print("\n" + "=" * 80)
print("VALIDATION RESULTS:")
print("=" * 80)
print(f"Valid: {result['validation']['valid']}")
print(f"Issues: {result['validation']['issues']}")
print(f"Suggestions: {result['validation']['suggestions']}")
```

**Run it:**
```bash
python testing/ml-service/test_enhanced_simplifier.py
```

**Expected output:**
```
===============================================================================
ENHANCED SIMPLIFICATION TEST
===============================================================================

ORIGINAL TEXT:
The comprehensive implementation of this innovative methodology necessitates 
meticulous consideration of numerous variables. Researchers endeavor to 
demonstrate the efficacy of their approach through rigorous experimentation.

===============================================================================
SIMPLIFIED TEXT (Grade 6):
===============================================================================
The complete use of this new method needs careful thought of many things. 
Researchers try to show how well their way works through careful tests.

===============================================================================
CHANGES APPLIED (8 total):
===============================================================================

1. WORD_REPLACEMENT
   Original: comprehensive
   Simplified: complete
   Reason: 'comprehensive' (rank #10,500) → 'complete' (rank #2,340): More common and simpler word

2. WORD_REPLACEMENT
   Original: implementation
   Simplified: use
   Reason: 'implementation' (rank #8,200) → 'use' (rank #87): More common and simpler word

[... more changes ...]

===============================================================================
VALIDATION RESULTS:
===============================================================================
Valid: True
Issues: []
Suggestions: []
```

---

## STEP 8: Update Requirements

Add to `ml-service/requirements.txt`:

```
nltk==3.8.1
groq==0.11.0
requests==2.31.0
```

**Install:**
```bash
pip install nltk groq requests
```

---

## DELIVERABLES

1. ✅ Groq API key added to `.env`
2. ✅ NLTK installed and WordNet downloaded
3. ✅ `wordnet_synonyms.py` - 100,000+ synonyms offline
4. ✅ `datamuse_synonyms.py` - 500,000+ synonyms online
5. ✅ `groq_validator.py` - AI validation of changes
6. ✅ Enhanced `simplifier.py` with hybrid approach
7. ✅ Test script confirms everything works

---

## SUCCESS CRITERIA

Run the test script and verify:

1. ✅ **WordNet finds synonyms** for common words
2. ✅ **Datamuse API works** (internet connection needed)
3. ✅ **Groq validates changes** and flags issues
4. ✅ **Groq fixes issues** when validation fails
5. ✅ **Comprehensive coverage** - rarely shows "no synonym found"
6. ✅ **Manual mappings take priority** (fastest + most accurate)

---

## VERIFICATION CHECKLIST

### Test 1: WordNet Coverage
```bash
python -m models.wordnet_synonyms
```
Should find synonyms for most test words.

### Test 2: Datamuse API
```bash
python -m models.datamuse_synonyms
```
Should connect to API and return synonyms.

### Test 3: Groq Validation
```bash
python -m models.groq_validator
```
Should validate changes and provide feedback.

### Test 4: Full Simplification
```bash
python testing/ml-service/test_enhanced_simplifier.py
```
Should simplify text with detailed change tracking.

### Test 5: Frontend Integration
1. Start all services (backend, ML, frontend)
2. Navigate to analysis
3. Click "Simplify Text"
4. Verify changes show detailed reasons
5. Verify Groq validation results (if enabled)

---

## TROUBLESHOOTING

### Issue: "WordNet not found"
**Solution:**
```bash
python download_wordnet.py
```

### Issue: "Groq API key not found"
**Solution:** Check `ml-service/.env` has:
```
GROQ_API_KEY=gsk_your_key_here
```

### Issue: "Datamuse API timeout"
**Solution:** 
- Check internet connection
- API might be temporarily down (rare)
- Fallback to WordNet/manual mappings

### Issue: "No synonyms found"
**Solution:**
- Check that all 3 methods are initialized
- Verify COCA frequency file has enough words
- Some technical terms genuinely have no simpler synonyms

---

## PERFORMANCE NOTES

**Speed Comparison:**

| Method | Speed | Coverage |
|--------|-------|----------|
| Manual mapping | 0.001s | 50 words |
| WordNet | 0.01s | 100k words |
| Datamuse API | 1-2s | 500k words |
| Groq validation | 2-3s | ∞ |

**Total simplification time:**
- Small text (100 words): ~1-2 seconds
- Medium text (500 words): ~3-5 seconds
- Large text (2000 words): ~10-15 seconds

**Note:** Most time is spent on Groq API calls. You can disable validation for faster processing by not calling `validate_changes()`.

---

## OPTIONAL: Disable Groq Validation for Speed

If you want faster simplification without validation:

In `simplifier.py`, comment out validation:

```python
# STEP 4: Groq validation (DISABLED FOR SPEED)
# validation = self.groq_validator.validate_changes(...)
validation = {'valid': True, 'issues': [], 'suggestions': []}
```

This makes simplification ~5x faster but removes the sanity check.

---

**After completing this prompt, you'll have comprehensive synonym coverage with 500,000+ words instead of just 50!** 🎉
