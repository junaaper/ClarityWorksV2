# PROMPT 3: Text Simplification Engine

## Context
You've completed **Prompt 1** (Enhanced Difficulty Detection) and **Prompt 2** (Calibrated Test Files). Now implement the text simplification feature.

## Objective
Allow users to simplify (or complexify) text to a target grade level. Two modes:
- **Auto Mode:** Apply all changes automatically, show before/after with hover explanations
- **Interactive Mode:** User hovers on each change, sees reasoning, clicks Accept/Deny in real-time

---

## STEP 1: Database Schema Update

Add new table to `backend/src/config/database.ts`:

Find the existing `CREATE TABLE` statements and add this one:

```typescript
await pool.query(`
  CREATE TABLE IF NOT EXISTS simplification_history (
    id SERIAL PRIMARY KEY,
    analysis_id INTEGER REFERENCES analyses(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    original_text TEXT NOT NULL,
    simplified_text TEXT NOT NULL,
    target_grade VARCHAR(50) NOT NULL,
    changes_applied JSONB NOT NULL,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('auto', 'interactive')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE INDEX IF NOT EXISTS idx_simplification_user ON simplification_history(user_id);
  CREATE INDEX IF NOT EXISTS idx_simplification_analysis ON simplification_history(analysis_id);
`);
```

---

## STEP 2: Install Groq SDK (Optional but Recommended)

**2.1 Add to `ml-service/requirements.txt`:**

```
groq==0.11.0
```

**2.2 Install:**

```bash
cd ml-service
pip install groq
```

**2.3 Get Free API Key:**

1. Go to: https://console.groq.com/
2. Sign up (free)
3. Create API key
4. Add to `ml-service/.env`:

```
GROQ_API_KEY=gsk_your_api_key_here
```

**Note:** Groq is free and very fast. It's used as a fallback for complex sentences that rule-based can't handle well.

---

## STEP 3: Create Text Simplifier Engine

Create `ml-service/models/simplifier.py`:

```python
import spacy
from models.synonym_lookup import SynonymLookup
import os

# Try to import Groq, but don't fail if not available
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("Warning: Groq not installed. Advanced simplification will be limited.")

nlp = spacy.load('en_core_web_sm')

class TextSimplifier:
    """Simplify or complexify text to target grade level"""
    
    def __init__(self):
        self.synonym_lookup = SynonymLookup()
        
        # Initialize Groq client if available
        self.groq_client = None
        if GROQ_AVAILABLE and os.getenv('GROQ_API_KEY'):
            self.groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        
        # Grade-specific constraints
        self.grade_constraints = {
            3: {'max_words': 10, 'max_syllables': 2},
            4: {'max_words': 12, 'max_syllables': 2},
            5: {'max_words': 15, 'max_syllables': 2},
            6: {'max_words': 18, 'max_syllables': 3},
            7: {'max_words': 20, 'max_syllables': 3},
            8: {'max_words': 20, 'max_syllables': 3},
            9: {'max_words': 22, 'max_syllables': 3},
            10: {'max_words': 25, 'max_syllables': 4},
            11: {'max_words': 28, 'max_syllables': 4},
            12: {'max_words': 30, 'max_syllables': 4}
        }
    
    def simplify_to_grade(self, text, target_grade):
        """
        Main simplification function
        
        Args:
            text: Original text
            target_grade: Target grade level (3-12)
        
        Returns:
            {
                'simplified_text': str,
                'changes': [array of change objects],
                'original_text': str
            }
        """
        changes = []
        current_text = text
        
        # Rule 1: Replace difficult words with simpler synonyms
        current_text, word_changes = self.replace_difficult_words(current_text, target_grade)
        changes.extend(word_changes)
        
        # Rule 2: Split long sentences
        current_text, split_changes = self.split_long_sentences(current_text, target_grade)
        changes.extend(split_changes)
        
        # Rule 3: Convert passive to active voice
        current_text, voice_changes = self.convert_passive_to_active(current_text)
        changes.extend(voice_changes)
        
        # Optional: Groq API fallback for complex cases
        if self._needs_groq_help(current_text, target_grade):
            current_text, api_changes = self.groq_fallback(current_text, target_grade)
            changes.extend(api_changes)
        
        return {
            'simplified_text': current_text,
            'changes': changes,
            'original_text': text
        }
    
    def replace_difficult_words(self, text, target_grade):
        """Replace difficult words with simpler synonyms"""
        changes = []
        doc = nlp(text)
        new_text = text
        offset = 0
        
        for token in doc:
            if not token.is_alpha or token.is_stop:
                continue
            
            word_lower = token.text.lower()
            
            # Check if we have a simpler alternative
            if word_lower in self.synonym_lookup.simplification_map:
                mapping = self.synonym_lookup.simplification_map[word_lower]
                
                # Only replace if simpler word fits target grade
                if mapping['grade'] <= target_grade:
                    simple_word = mapping['simple']
                    
                    # Preserve capitalization
                    if token.text[0].isupper():
                        simple_word = simple_word.capitalize()
                    
                    # Replace in text
                    start = token.idx + offset
                    end = start + len(token.text)
                    new_text = new_text[:start] + simple_word + new_text[end:]
                    offset += len(simple_word) - len(token.text)
                    
                    changes.append({
                        'type': 'word_replacement',
                        'original': token.text,
                        'simplified': simple_word,
                        'position': token.idx,
                        'reason': f"'{token.text}' ({mapping['syllables_before']} syllables, {self._get_complexity_label(word_lower)}) → '{simple_word}' ({mapping['syllables_after']} syllables, simpler). {mapping['reason']}",
                        'id': len(changes)
                    })
        
        return new_text, changes
    
    def split_long_sentences(self, text, target_grade):
        """Split sentences that are too long for target grade"""
        constraints = self.grade_constraints.get(target_grade, {'max_words': 20})
        max_words = constraints['max_words']
        
        changes = []
        doc = nlp(text)
        new_sentences = []
        
        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            word_count = len(words)
            
            if word_count > max_words + 3:  # Give 3-word buffer
                # Try to split at conjunction
                split_result = self._split_at_conjunction(sent.text)
                
                if split_result['success']:
                    new_sentences.extend(split_result['sentences'])
                    changes.append({
                        'type': 'sentence_split',
                        'original': sent.text,
                        'simplified': ' '.join(split_result['sentences']),
                        'position': sent.start_char,
                        'reason': f"Split long sentence ({word_count} words) into {len(split_result['sentences'])} shorter sentences. Target for Grade {target_grade}: ≤{max_words} words per sentence.",
                        'id': len(changes)
                    })
                else:
                    new_sentences.append(sent.text)
            else:
                new_sentences.append(sent.text)
        
        return ' '.join(new_sentences), changes
    
    def _split_at_conjunction(self, sentence):
        """Split sentence at coordinating conjunction"""
        # Look for: and, but, or (with comma before them ideally)
        for conj in [', and ', ', but ', ', or ', ' and ', ' but ', ' or ']:
            if conj in sentence:
                parts = sentence.split(conj, 1)
                if len(parts) == 2:
                    before = parts[0].strip()
                    after = parts[1].strip()
                    
                    # Capitalize second sentence
                    if after:
                        after = after[0].upper() + after[1:]
                    
                    # Add period to first if missing
                    if before and before[-1] not in '.!?':
                        before += '.'
                    
                    return {
                        'success': True,
                        'sentences': [before, after]
                    }
        
        return {'success': False}
    
    def convert_passive_to_active(self, text):
        """Convert passive voice to active (simplified approach)"""
        changes = []
        
        # This is a placeholder - full implementation would use spaCy dependency parsing
        # For now, just detect passive and suggest manual review
        doc = nlp(text)
        
        for sent in doc.sents:
            # Simple passive detection
            if any(token.dep_ == 'nsubjpass' for token in sent):
                # In production, implement actual conversion
                # For now, just flag it
                pass
        
        return text, changes
    
    def _needs_groq_help(self, text, target_grade):
        """Check if text still needs AI assistance after rule-based simplification"""
        if not self.groq_client:
            return False
        
        doc = nlp(text)
        constraints = self.grade_constraints.get(target_grade, {'max_words': 20})
        
        # Check if any sentences are still too complex
        for sent in doc.sents:
            words = [t for t in sent if t.is_alpha]
            if len(words) > constraints['max_words'] + 5:
                return True
        
        return False
    
    def groq_fallback(self, text, target_grade):
        """Use Groq API for remaining complex sentences"""
        if not self.groq_client:
            return text, []
        
        try:
            prompt = f"""Simplify this text to Grade {target_grade} reading level. 
Rules:
- Use shorter sentences (max {self.grade_constraints[target_grade]['max_words']} words)
- Replace difficult words with simpler alternatives
- Maintain the original meaning
- Be natural and clear

Text:
{text}

Simplified version:"""
            
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            
            simplified = response.choices[0].message.content.strip()
            
            return simplified, [{
                'type': 'ai_enhanced',
                'original': text,
                'simplified': simplified,
                'position': 0,
                'reason': 'Complex sentence structure required AI assistance (Groq Llama 3.3 70B). Applied advanced simplification beyond rule-based capabilities.',
                'id': 999
            }]
        
        except Exception as e:
            print(f"Groq API error: {e}")
            return text, []
    
    def _get_complexity_label(self, word):
        """Get complexity label for a word"""
        rank = self.synonym_lookup.get_word_frequency_rank(word)
        
        if rank <= 5000:
            return "common"
        elif rank <= 10000:
            return "uncommon"
        elif rank <= 20000:
            return "rare"
        else:
            return "very rare"
```

---

## STEP 4: Add Flask Endpoints

Add to `ml-service/app.py`:

```python
from models.simplifier import TextSimplifier

# Initialize simplifier
simplifier = TextSimplifier()

@app.route('/simplify/analyze', methods=['POST'])
def analyze_for_simplification():
    """
    Analyze text and return suggested changes
    Used for both auto and interactive modes
    """
    try:
        data = request.json
        text = data['text']
        target_grade = int(data['target_grade'])
        
        result = simplifier.simplify_to_grade(text, target_grade)
        
        return jsonify({
            'original_text': text,
            'suggested_changes': result['changes'],
            'preview_text': result['simplified_text']
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/simplify/apply', methods=['POST'])
def apply_selected_changes():
    """
    Apply only accepted changes (for interactive mode)
    """
    try:
        data = request.json
        text = data['text']
        accepted_change_ids = data['accepted_changes']  # List of IDs
        all_changes = data['all_changes']
        
        # Apply only accepted changes
        final_text = text
        for change in all_changes:
            if change['id'] in accepted_change_ids:
                final_text = final_text.replace(change['original'], change['simplified'], 1)
        
        return jsonify({'simplified_text': final_text})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## STEP 5: Backend Controller

Create `backend/src/controllers/simplifyController.ts`:

```typescript
import { Request, Response } from 'express';
import axios from 'axios';
import pool from '../config/database';

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:5001';

export const analyzeForSimplification = async (req: Request, res: Response) => {
  try {
    const { analysisId, targetGrade } = req.body;
    
    // Get original text
    const analysis = await pool.query(
      'SELECT original_text FROM analyses WHERE id = $1 AND user_id = $2',
      [analysisId, (req as any).user.userId]
    );
    
    if (analysis.rows.length === 0) {
      return res.status(404).json({ error: 'Analysis not found' });
    }
    
    // Call Python ML service
    const response = await axios.post(`${PYTHON_SERVICE_URL}/simplify/analyze`, {
      text: analysis.rows[0].original_text,
      target_grade: targetGrade
    });
    
    res.json(response.data);
  } catch (error: any) {
    console.error('Simplification analysis error:', error);
    res.status(500).json({ error: 'Failed to analyze for simplification' });
  }
};

export const saveSimplification = async (req: Request, res: Response) => {
  try {
    const { analysisId, simplifiedText, targetGrade, changes, mode } = req.body;
    
    // Get original text
    const analysis = await pool.query(
      'SELECT original_text FROM analyses WHERE id = $1',
      [analysisId]
    );
    
    if (analysis.rows.length === 0) {
      return res.status(404).json({ error: 'Analysis not found' });
    }
    
    // Save to simplification_history
    const result = await pool.query(
      `INSERT INTO simplification_history 
       (analysis_id, user_id, original_text, simplified_text, target_grade, changes_applied, mode) 
       VALUES ($1, $2, $3, $4, $5, $6, $7) 
       RETURNING *`,
      [
        analysisId,
        (req as any).user.userId,
        analysis.rows[0].original_text,
        simplifiedText,
        `Grade ${targetGrade}`,
        JSON.stringify(changes),
        mode
      ]
    );
    
    res.json(result.rows[0]);
  } catch (error: any) {
    console.error('Save simplification error:', error);
    res.status(500).json({ error: 'Failed to save simplification' });
  }
};
```

---

## STEP 6: Backend Routes

Create `backend/src/routes/simplifyRoutes.ts`:

```typescript
import express from 'express';
import { authMiddleware } from '../middleware/auth';
import { analyzeForSimplification, saveSimplification } from '../controllers/simplifyController';

const router = express.Router();

router.post('/analyze', authMiddleware, analyzeForSimplification);
router.post('/save', authMiddleware, saveSimplification);

export default router;
```

Add to `backend/src/server.ts`:

```typescript
import simplifyRoutes from './routes/simplifyRoutes';

// ... other imports

app.use('/api/simplify', simplifyRoutes);
```

---

## STEP 7: Frontend - Simplify Page

Create `frontend/src/components/Simplification/SimplifyPage.tsx`:

```tsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../services/api';

interface Change {
  type: string;
  original: string;
  simplified: string;
  position: number;
  reason: string;
  id: number;
  accepted?: boolean | null;
}

const SimplifyPage: React.FC = () => {
  const { analysisId } = useParams<{ analysisId: string }>();
  const navigate = useNavigate();
  
  const [mode, setMode] = useState<'auto' | 'interactive'>('auto');
  const [originalText, setOriginalText] = useState('');
  const [simplifiedText, setSimplifiedText] = useState('');
  const [changes, setChanges] = useState<Change[]>([]);
  const [targetGrade, setTargetGrade] = useState(6);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    // Load analysis
    const fetchAnalysis = async () => {
      try {
        const response = await api.get(`/analyses/${analysisId}`);
        setOriginalText(response.data.original_text);
      } catch (error) {
        console.error('Failed to load analysis:', error);
      }
    };
    fetchAnalysis();
  }, [analysisId]);
  
  const handleSimplify = async () => {
    setLoading(true);
    try {
      const response = await api.post('/simplify/analyze', {
        analysisId,
        targetGrade
      });
      
      const newChanges = response.data.suggested_changes.map((c: Change) => ({
        ...c,
        accepted: mode === 'auto' ? true : null
      }));
      
      setChanges(newChanges);
      setSimplifiedText(response.data.preview_text);
    } catch (error) {
      console.error('Simplification error:', error);
      alert('Failed to simplify text');
    }
    setLoading(false);
  };
  
  const handleAccept = (changeId: number) => {
    const newChanges = changes.map(c => 
      c.id === changeId ? { ...c, accepted: true } : c
    );
    setChanges(newChanges);
    updateTextWithAcceptedChanges(newChanges);
  };
  
  const handleDeny = (changeId: number) => {
    const newChanges = changes.map(c => 
      c.id === changeId ? { ...c, accepted: false } : c
    );
    setChanges(newChanges);
    updateTextWithAcceptedChanges(newChanges);
  };
  
  const updateTextWithAcceptedChanges = (updatedChanges: Change[]) => {
    let text = originalText;
    updatedChanges
      .filter(c => c.accepted === true)
      .forEach(change => {
        text = text.replace(change.original, change.simplified);
      });
    setSimplifiedText(text);
  };
  
  const handleSave = async () => {
    try {
      const acceptedChanges = changes.filter(c => c.accepted === true);
      
      await api.post('/simplify/save', {
        analysisId,
        simplifiedText,
        targetGrade,
        changes: acceptedChanges,
        mode
      });
      
      alert('Simplification saved successfully!');
      navigate(`/analysis/${analysisId}`);
    } catch (error) {
      console.error('Save error:', error);
      alert('Failed to save simplification');
    }
  };
  
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Text Simplification</h1>
      
      {/* Controls */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex gap-6 items-end">
          <div>
            <label className="block text-sm font-medium mb-2">Target Grade Level</label>
            <select 
              value={targetGrade}
              onChange={(e) => setTargetGrade(+e.target.value)}
              className="border rounded px-4 py-2"
            >
              {[3, 4, 5, 6, 7, 8, 9, 10, 11, 12].map(g => (
                <option key={g} value={g}>Grade {g}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2">Mode</label>
            <div className="flex gap-2">
              <button
                onClick={() => setMode('auto')}
                className={`px-4 py-2 rounded ${
                  mode === 'auto' 
                    ? 'bg-blue-500 text-white' 
                    : 'bg-gray-200 text-gray-700'
                }`}
              >
                Auto Mode
              </button>
              <button
                onClick={() => setMode('interactive')}
                className={`px-4 py-2 rounded ${
                  mode === 'interactive' 
                    ? 'bg-blue-500 text-white' 
                    : 'bg-gray-200 text-gray-700'
                }`}
              >
                Interactive Mode
              </button>
            </div>
          </div>
          
          <div className="ml-auto flex gap-2">
            <button
              onClick={handleSimplify}
              disabled={loading}
              className="px-6 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
            >
              {loading ? 'Processing...' : 'Simplify'}
            </button>
            
            {simplifiedText && (
              <button
                onClick={handleSave}
                className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                Save
              </button>
            )}
          </div>
        </div>
        
        <p className="text-sm text-gray-600 mt-4">
          {mode === 'auto' 
            ? 'Auto Mode: All changes applied automatically. Hover to see reasons.' 
            : 'Interactive Mode: Hover on changes to see reasons and Accept/Deny each one.'}
        </p>
      </div>
      
      {/* Split View */}
      <div className="grid grid-cols-2 gap-6">
        {/* Original */}
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h3 className="text-lg font-bold mb-4 text-red-800">Original Text</h3>
          <div className="prose max-w-none whitespace-pre-wrap">
            {originalText}
          </div>
        </div>
        
        {/* Simplified */}
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <h3 className="text-lg font-bold mb-4 text-green-800">
            Simplified Text (Grade {targetGrade})
          </h3>
          {simplifiedText ? (
            <div className="prose max-w-none">
              <HighlightedChanges 
                text={simplifiedText}
                changes={changes}
                mode={mode}
                onAccept={handleAccept}
                onDeny={handleDeny}
              />
            </div>
          ) : (
            <p className="text-gray-500 italic">
              Click "Simplify" to see simplified version...
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

// Component to highlight changes
interface HighlightedChangesProps {
  text: string;
  changes: Change[];
  mode: 'auto' | 'interactive';
  onAccept: (id: number) => void;
  onDeny: (id: number) => void;
}

const HighlightedChanges: React.FC<HighlightedChangesProps> = ({
  text,
  changes,
  mode,
  onAccept,
  onDeny
}) => {
  const [hoveredChange, setHoveredChange] = useState<number | null>(null);
  
  // Split text and highlight changes
  let highlightedText = text;
  
  changes.forEach((change) => {
    if (change.accepted !== false) {
      const highlighted = `<span class="change-highlight" data-change-id="${change.id}">${change.simplified}</span>`;
      highlightedText = highlightedText.replace(change.simplified, highlighted);
    }
  });
  
  return (
    <div className="relative">
      <div dangerouslySetInnerHTML={{ __html: highlightedText }} />
      
      <style>{`
        .change-highlight {
          background-color: #86efac;
          padding: 2px 4px;
          border-radius: 3px;
          cursor: help;
          position: relative;
        }
        .change-highlight:hover {
          background-color: #4ade80;
        }
      `}</style>
    </div>
  );
};

export default SimplifyPage;
```

Note: The above is a simplified version. For production, you'd want to use proper hover tooltips with change details and Accept/Deny buttons for interactive mode.

---

## STEP 8: Add Route

In `frontend/src/App.tsx`, add:

```tsx
import SimplifyPage from './components/Simplification/SimplifyPage';

// In routes:
<Route path="/simplify/:analysisId" element={<SimplifyPage />} />
```

---

## STEP 9: Add "Simplify" Button to Analysis Results

In `frontend/src/components/Analysis/AnalysisResults.tsx`, add button:

```tsx
<button
  onClick={() => navigate(`/simplify/${analysisId}`)}
  className="px-6 py-2 bg-purple-500 text-white rounded hover:bg-purple-600 flex items-center gap-2"
>
  <span>✏️</span>
  Simplify Text
</button>
```

---

## DELIVERABLES

1. ✅ Database table `simplification_history` created
2. ✅ Groq API installed and configured (optional but recommended)
3. ✅ `simplifier.py` with rule-based + Groq fallback
4. ✅ Flask endpoints `/simplify/analyze` and `/simplify/apply`
5. ✅ Backend controller and routes
6. ✅ Frontend SimplifyPage with auto/interactive modes
7. ✅ "Simplify" button added to analysis results

---

## SUCCESS CRITERIA

Test the feature:

1. ✅ Navigate to an analysis
2. ✅ Click "Simplify Text"
3. ✅ Select target grade (e.g., Grade 6)
4. ✅ Click "Simplify" - changes appear
5. ✅ **Auto mode:** All changes highlighted in green, hover shows reasons
6. ✅ **Interactive mode:** Hover shows reasons + Accept/Deny buttons
7. ✅ Click "Save" - simplification saved to database

---

**After completing this prompt, proceed to PROMPT_4_RAG.md**
