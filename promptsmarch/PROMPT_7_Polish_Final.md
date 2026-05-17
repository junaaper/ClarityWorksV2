# PROMPT 7: Polish & Final Features for FYP Presentation

## Context
You've completed Prompts 1-6. ClarityWorks is functional but needs polish for the FYP presentation. This prompt adds UI improvements, export features, better explanations, and fixes text extraction issues.

## Objective
- Fix test file validation (all 11 grades including College)
- Improve text extraction (remove whitespace/nonsense, make editable)
- Add clear layman + technical explanations for grades
- Export simplification as PDF/DOCX
- Export RAG results as PDF/DOCX
- Save simplification to history with before/after
- Display simplification history in History page
- Add loading states everywhere
- Add heatmaps to analysis results
- Make word count more visible

---

## PART 1: Test Files - Create College Level & Re-validate All

### Step 1.1: Create College Test File

**Create:** `ml-service/data/test_files/college.txt`

```
# College Test Text
# Expected: College (Grade 13+), Flesch 30-40, Advanced academic vocabulary
# Purpose: Demonstration of accurate College-level prediction

Contemporary epistemological discourse necessitates comprehensive examination of methodological frameworks that undergird empirical investigation and theoretical conceptualization within scientific paradigms. The dialectical relationship between observational phenomena and abstract theoretical constructs remains fundamentally contested among philosophers investigating the nature of scientific knowledge production.

Postmodern critiques of positivist epistemology have problematized traditional assumptions regarding objective truth and universal methodological validity. These philosophical interventions emphasize the inherently contextual and socially constructed dimensions of knowledge claims, thereby challenging foundational premises of scientific realism. Consequently, scholars increasingly recognize that empirical observations are necessarily theory-laden, reflecting particular conceptual frameworks and interpretive assumptions.

Furthermore, the demarcation problem—distinguishing legitimate scientific inquiry from pseudoscientific discourse—continues generating substantive philosophical debates. Karl Popper's falsificationist criterion, despite its influential role in twentieth-century philosophy of science, has encountered significant theoretical challenges. Critics argue that historical examination of actual scientific practice reveals considerably more complex relationships between empirical evidence and theoretical revision than falsificationist accounts suggest.

These epistemological considerations possess profound implications for understanding scientific progress and evaluating competing theoretical frameworks across diverse disciplinary contexts. Sophisticated comprehension of knowledge production mechanisms enables more nuanced appreciation of science's capabilities and limitations, thereby informing contemporary discussions regarding scientific authority and expertise within pluralistic democratic societies.
```

### Step 1.2: Update Validation Script

**Modify:** `testing/ml-service/validate_test_files.py`

Add college to the validation loop:

```python
# Change this line:
for grade in range(3, 13):

# To this:
test_grades = list(range(3, 13)) + ['college']

for grade in test_grades:
    if grade == 'college':
        filename = "college.txt"
        expected_grade = 13.5  # College should predict 13+
    else:
        filename = f"grade_{grade}.txt"
        expected_grade = float(grade)
    
    filepath = os.path.join(test_files_dir, filename)
    
    # ... rest of validation code ...
    
    # Adjust tolerance for college
    tolerance = 0.5 if grade == 'college' else 0.3
    error = abs(predicted_grade - expected_grade)
    
    if error <= tolerance:
        status = "✅ PASS"
    # ... rest of code
```

### Step 1.3: Re-run Validation & Iterate

**Run:**
```bash
cd ml-service
python testing/ml-service/validate_test_files.py
```

**For any FAILING tests:**
- Adjust the text content (add/remove complexity)
- Re-run validation
- Repeat until all 11 pass (Grades 3-12 + College)

**Guidelines:**
- If predicted TOO HIGH: simplify vocabulary, shorten sentences
- If predicted TOO LOW: add complex words, longer sentences, academic terms

---

## PART 2: Fix Text Extraction (Remove Whitespace/Nonsense)

### Step 2.1: Create Text Cleaner Utility

**Create:** `ml-service/utils/text_cleaner.py`

```python
import re

class TextCleaner:
    """Clean extracted text from PDFs/DOCX/OCR"""
    
    @staticmethod
    def clean_extracted_text(text):
        """
        Clean text extracted from files:
        - Remove excessive whitespace
        - Remove nonsensical characters/symbols
        - Fix common OCR errors
        - Preserve paragraph structure
        - Make text editable and readable
        
        Args:
            text: Raw extracted text
        
        Returns:
            str: Cleaned, formatted text
        """
        if not text:
            return ""
        
        # Step 1: Remove null bytes and control characters (except newlines/tabs)
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
        
        # Step 2: Normalize Unicode (fix special characters)
        text = text.encode('ascii', 'ignore').decode('ascii')  # Remove non-ASCII
        
        # Step 3: Remove repeated special characters (e.g., "------", "======")
        text = re.sub(r'([^\w\s])\1{3,}', r'\1\1', text)
        
        # Step 4: Fix excessive whitespace within lines
        text = re.sub(r'[ \t]{2,}', ' ', text)  # Multiple spaces → single space
        
        # Step 5: Fix excessive newlines (preserve paragraph breaks)
        text = re.sub(r'\n{4,}', '\n\n\n', text)  # Max 3 newlines
        
        # Step 6: Remove lines with only whitespace
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        
        # Step 7: Remove nonsensical short lines (likely artifacts)
        # Keep line if: (a) >20 chars, OR (b) contains complete sentence punctuation
        cleaned_lines = []
        for line in lines:
            if len(line) > 20 or re.search(r'[.!?]$', line):
                cleaned_lines.append(line)
            elif len(line) == 0:
                cleaned_lines.append('')  # Preserve paragraph breaks
        
        # Step 8: Rejoin with proper spacing
        text = '\n'.join(cleaned_lines)
        
        # Step 9: Fix common OCR errors
        text = TextCleaner._fix_ocr_errors(text)
        
        # Step 10: Final cleanup - collapse multiple blank lines to max 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Step 11: Trim leading/trailing whitespace
        text = text.strip()
        
        return text
    
    @staticmethod
    def _fix_ocr_errors(text):
        """Fix common OCR misreadings"""
        # Common OCR errors
        replacements = {
            r'\bl\b': 'I',           # lowercase L → capital I (in isolation)
            r'\bO\b': '0',           # capital O → zero (in numbers)
            r'rn': 'm',              # rn → m (common OCR error)
            r'\|': 'I',              # pipe → capital I
            r'~': '-',               # tilde → hyphen
            r'—': '--',              # em dash → double hyphen
            r''': "'",               # smart quote → straight quote
            r''': "'",
            r'"': '"',
            r'"': '"',
        }
        
        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)
        
        return text
    
    @staticmethod
    def remove_images_markers(text):
        """Remove image placeholder text (e.g., [Image], Figure 1, etc.)"""
        # Remove common image markers
        patterns = [
            r'\[Image:?.*?\]',
            r'\[Figure:?.*?\]',
            r'\[Photo:?.*?\]',
            r'Figure \d+:?.*?(?=\n|$)',
            r'Image \d+:?.*?(?=\n|$)',
            r'\[Graphic\]',
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text
    
    @staticmethod
    def ensure_editable(text):
        """
        Ensure text is editable (no read-only artifacts)
        This is mainly for frontend display
        """
        # Remove zero-width characters that might interfere with editing
        text = text.replace('\u200b', '')  # Zero-width space
        text = text.replace('\ufeff', '')  # Zero-width no-break space
        text = text.replace('\u200c', '')  # Zero-width non-joiner
        text = text.replace('\u200d', '')  # Zero-width joiner
        
        return text
```

### Step 2.2: Integrate Text Cleaner into Extraction

**Modify:** `ml-service/app.py`

Add import at top:
```python
from utils.text_cleaner import TextCleaner
```

Update all extraction endpoints:

```python
@app.route('/extract-pdf', methods=['POST'])
def extract_pdf():
    """Extract text from PDF with cleaning"""
    try:
        file = request.files['file']
        
        # Existing extraction code
        pdf = pdfplumber.open(file)
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
        pdf.close()
        
        # NEW: Clean the extracted text
        text = TextCleaner.remove_images_markers(text)
        text = TextCleaner.clean_extracted_text(text)
        text = TextCleaner.ensure_editable(text)
        
        return jsonify({'text': text})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/extract-doc', methods=['POST'])
def extract_doc():
    """Extract text from DOCX with cleaning"""
    try:
        file = request.files['file']
        
        # Existing extraction code
        doc = Document(file)
        text = "\n\n".join([para.text for para in doc.paragraphs])
        
        # NEW: Clean the extracted text
        text = TextCleaner.remove_images_markers(text)
        text = TextCleaner.clean_extracted_text(text)
        text = TextCleaner.ensure_editable(text)
        
        return jsonify({'text': text})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/extract-image', methods=['POST'])
def extract_image():
    """Extract text from image with cleaning"""
    try:
        file = request.files['file']
        
        # Existing OCR code
        image = Image.open(file)
        text = pytesseract.image_to_string(image)
        
        # NEW: Clean the OCR text (especially important for OCR)
        text = TextCleaner.remove_images_markers(text)
        text = TextCleaner.clean_extracted_text(text)
        text = TextCleaner.ensure_editable(text)
        
        return jsonify({'text': text})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

**Also update RAG upload** (same cleaning):

```python
@app.route('/rag/upload', methods=['POST'])
def upload_rag_document():
    """Upload and process textbook for RAG with cleaning"""
    try:
        file = request.files['file']
        user_id = request.form.get('user_id')
        
        # Extract text
        if file.filename.endswith('.pdf'):
            text = extract_text_from_pdf(file)
        elif file.filename.endswith(('.docx', '.doc')):
            text = extract_text_from_docx(file)
        else:
            return jsonify({'error': 'Unsupported file type'}), 400
        
        # NEW: Clean the text before RAG processing
        text = TextCleaner.remove_images_markers(text)
        text = TextCleaner.clean_extracted_text(text)
        
        if not text or len(text) < 100:
            return jsonify({'error': 'Could not extract sufficient text'}), 400
        
        # ... rest of RAG upload code
```

---

## PART 3: Make Word Count More Visible

### Step 3.1: Add Live Word Count to TextInput

**Modify:** `frontend/src/components/TextInput/TextInput.tsx`

Add word count display at the top:

```tsx
const TextInput = () => {
  const [text, setText] = useState('');
  const [wordCount, setWordCount] = useState(0);
  
  // Update word count whenever text changes
  useEffect(() => {
    const words = text.trim().split(/\s+/).filter(word => word.length > 0);
    setWordCount(words.length);
  }, [text]);
  
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Text Analysis</h1>
      
      {/* NEW: Word Count Display */}
      <div className="bg-blue-50 border-2 border-blue-200 rounded-lg p-4 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">Current Word Count</p>
            <p className="text-3xl font-bold text-blue-600">{wordCount.toLocaleString()}</p>
          </div>
          <div className="text-sm text-gray-600">
            {wordCount < 50 && <span className="text-red-600">⚠️ Minimum 50 words required</span>}
            {wordCount >= 50 && wordCount <= 50000 && <span className="text-green-600">✓ Valid length</span>}
            {wordCount > 50000 && <span className="text-red-600">⚠️ Maximum 50,000 words</span>}
          </div>
        </div>
      </div>
      
      {/* Existing tabs */}
      <Tabs ...>
        {/* Tab 1: Direct Input */}
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="w-full h-96 ..."
        />
      </Tabs>
    </div>
  );
};
```

---

## PART 4: Add Grade Explanations (Layman + Technical)

### Step 4.1: Create Grade Explanation Utility

**Create:** `frontend/src/utils/gradeExplanations.ts`

```typescript
export interface GradeExplanation {
  layman: string;
  technical: string;
  characteristics: {
    vocabulary: string;
    sentenceLength: string;
    structure: string;
    audience: string;
  };
}

export const GRADE_EXPLANATIONS: Record<string, GradeExplanation> = {
  "Grade 3": {
    layman: "This text is very simple and easy to read, suitable for early elementary school students (8-9 years old). It uses basic everyday words and short, simple sentences.",
    technical: "Grade 3 texts typically feature high-frequency vocabulary (Zipf ≥5.5), short declarative sentences (8-10 words average), minimal subordinate clauses, and Flesch Reading Ease scores of 80-90.",
    characteristics: {
      vocabulary: "Simple, everyday words (1-2 syllables)",
      sentenceLength: "8-10 words per sentence",
      structure: "Simple sentences with basic subject-verb-object",
      audience: "Early elementary students (ages 8-9)"
    }
  },
  
  "Grade 4": {
    layman: "This text is simple and suitable for elementary school students (9-10 years old). It uses common words and mostly straightforward sentences with occasional complexity.",
    technical: "Grade 4 texts feature common vocabulary with some multi-syllabic words, sentences averaging 10-12 words, occasional compound sentences, and Flesch scores of 75-85.",
    characteristics: {
      vocabulary: "Common words, some 3-syllable words",
      sentenceLength: "10-12 words per sentence",
      structure: "Simple + occasional compound sentences (and/but)",
      audience: "Elementary students (ages 9-10)"
    }
  },
  
  "Grade 5": {
    layman: "This text is moderately easy, appropriate for upper elementary students (10-11 years old). It uses familiar words with some academic vocabulary beginning to appear.",
    technical: "Grade 5 texts introduce basic academic vocabulary, average 12-15 words per sentence, more frequent compound sentences, and Flesch scores of 70-80.",
    characteristics: {
      vocabulary: "Mix of common and some academic words",
      sentenceLength: "12-15 words per sentence",
      structure: "Compound sentences common, some complex",
      audience: "Upper elementary students (ages 10-11)"
    }
  },
  
  "Grade 6": {
    layman: "This text is moderately complex, suitable for middle school students (11-12 years old). It includes academic vocabulary and sentences with multiple ideas connected together.",
    technical: "Grade 6 texts feature emerging academic vocabulary (Zipf ≥4.6), sentences of 15-18 words with subordinate clauses beginning to appear regularly, and Flesch scores of 65-75.",
    characteristics: {
      vocabulary: "Academic vocabulary begins (3-4 syllables)",
      sentenceLength: "15-18 words per sentence",
      structure: "Complex sentences with subordinate clauses",
      audience: "Middle school students (ages 11-12)"
    }
  },
  
  "Grade 7": {
    layman: "This text is moderately challenging, appropriate for middle school students (12-13 years old). It uses academic language and sentences with embedded clauses and multiple ideas.",
    technical: "Grade 7 texts display increased academic vocabulary, 16-19 words per sentence on average, higher subordinate clause density (1.5+ per sentence), and Flesch scores of 60-70.",
    characteristics: {
      vocabulary: "Academic/technical terms common",
      sentenceLength: "16-19 words per sentence",
      structure: "Complex with multiple embedded clauses",
      audience: "Middle school students (ages 12-13)"
    }
  },
  
  "Grade 8": {
    layman: "This text is challenging, suitable for advanced middle school students (13-14 years old). It features sophisticated vocabulary and complex sentence structures with multiple layers of meaning.",
    technical: "Grade 8 texts contain substantial academic vocabulary, sentences averaging 18-22 words, frequent use of passive voice and subordinate clauses, and Flesch scores of 55-65.",
    characteristics: {
      vocabulary: "Sophisticated academic vocabulary",
      sentenceLength: "18-22 words per sentence",
      structure: "Multiple clause structures, passive voice",
      audience: "Advanced middle school (ages 13-14)"
    }
  },
  
  "Grade 9": {
    layman: "This text is quite difficult, appropriate for high school freshmen (14-15 years old). It uses advanced vocabulary and intricate sentence structures requiring careful reading.",
    technical: "Grade 9 texts feature advanced vocabulary (Zipf ≥3.7), 20-24 words per sentence, high clause complexity, increased passive constructions, and Flesch scores of 50-60.",
    characteristics: {
      vocabulary: "Advanced, subject-specific terms",
      sentenceLength: "20-24 words per sentence",
      structure: "Intricate, nested clause structures",
      audience: "High school freshmen (ages 14-15)"
    }
  },
  
  "Grade 10": {
    layman: "This text is very difficult, suitable for high school sophomores (15-16 years old). It demands strong reading skills with sophisticated vocabulary and complex argumentation.",
    technical: "Grade 10 texts display sophisticated academic vocabulary, sentences of 22-26 words, high syntactic complexity with multiple embedded clauses, and Flesch scores of 45-55.",
    characteristics: {
      vocabulary: "Sophisticated, discipline-specific",
      sentenceLength: "22-26 words per sentence",
      structure: "Advanced complexity, abstract concepts",
      audience: "High school sophomores (ages 15-16)"
    }
  },
  
  "Grade 11": {
    layman: "This text is highly challenging, appropriate for advanced high school juniors (16-17 years old). It requires mature reading comprehension with abstract concepts and dense prose.",
    technical: "Grade 11 texts contain highly specialized vocabulary, 24-28 words per sentence, sophisticated syntactic structures, frequent nominalization and abstraction, Flesch scores of 40-50.",
    characteristics: {
      vocabulary: "Highly specialized, abstract terms",
      sentenceLength: "24-28 words per sentence",
      structure: "Sophisticated, dense prose",
      audience: "High school juniors (ages 16-17)"
    }
  },
  
  "Grade 12": {
    layman: "This text is very advanced, suitable for high school seniors (17-18 years old) preparing for college. It features college-level vocabulary and argumentation requiring critical analysis.",
    technical: "Grade 12 texts approach college-level complexity with specialized terminology (Zipf ≥2.8), sentences averaging 26-30+ words, high abstraction and nominalization, Flesch scores of 35-45.",
    characteristics: {
      vocabulary: "College-preparatory, specialized",
      sentenceLength: "26-30+ words per sentence",
      structure: "College-level complexity and abstraction",
      audience: "High school seniors (ages 17-18)"
    }
  },
  
  "College": {
    layman: "This text is extremely challenging, written at college level or higher. It requires advanced critical thinking, specialized knowledge, and comfort with abstract academic discourse.",
    technical: "College-level texts feature highly specialized disciplinary vocabulary, sentences often exceeding 30 words, sophisticated rhetorical structures, extensive use of nominalization and passive voice, Flesch scores typically below 40.",
    characteristics: {
      vocabulary: "Highly specialized, disciplinary jargon",
      sentenceLength: "30+ words per sentence",
      structure: "Sophisticated academic discourse",
      audience: "College students and academic researchers"
    }
  }
};

export function getGradeExplanation(gradeLevel: string): GradeExplanation {
  return GRADE_EXPLANATIONS[gradeLevel] || GRADE_EXPLANATIONS["Grade 6"];
}
```

### Step 4.2: Add Explanation Component

**Create:** `frontend/src/components/Analysis/GradeExplanation.tsx`

```tsx
import React, { useState } from 'react';
import { getGradeExplanation } from '../../utils/gradeExplanations';

interface Props {
  gradeLevel: string;
  metrics: {
    avgSentenceLength: number;
    avgSyllablesPerWord: number;
    difficultWordsPercentage: number;
    fleschReadingEase: number;
  };
}

const GradeExplanation: React.FC<Props> = ({ gradeLevel, metrics }) => {
  const [showTechnical, setShowTechnical] = useState(false);
  const explanation = getGradeExplanation(gradeLevel);
  
  return (
    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-lg p-6 mb-6">
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-xl font-bold text-gray-800">
          Why {gradeLevel}?
        </h3>
        
        <button
          onClick={() => setShowTechnical(!showTechnical)}
          className="text-sm px-3 py-1 bg-white border border-gray-300 rounded hover:bg-gray-50"
        >
          {showTechnical ? '📖 Simple' : '🔬 Technical'}
        </button>
      </div>
      
      {/* Explanation Text */}
      <div className="mb-4">
        <p className="text-gray-700 leading-relaxed">
          {showTechnical ? explanation.technical : explanation.layman}
        </p>
      </div>
      
      {/* Characteristics Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="bg-white rounded p-3 border border-gray-200">
          <p className="text-xs text-gray-600 mb-1">Vocabulary Level</p>
          <p className="text-sm font-semibold">{explanation.characteristics.vocabulary}</p>
        </div>
        
        <div className="bg-white rounded p-3 border border-gray-200">
          <p className="text-xs text-gray-600 mb-1">Sentence Length</p>
          <p className="text-sm font-semibold">{explanation.characteristics.sentenceLength}</p>
          <p className="text-xs text-gray-500">Yours: {metrics.avgSentenceLength.toFixed(1)} words</p>
        </div>
        
        <div className="bg-white rounded p-3 border border-gray-200">
          <p className="text-xs text-gray-600 mb-1">Structure</p>
          <p className="text-sm font-semibold">{explanation.characteristics.structure}</p>
        </div>
        
        <div className="bg-white rounded p-3 border border-gray-200">
          <p className="text-xs text-gray-600 mb-1">Target Audience</p>
          <p className="text-sm font-semibold">{explanation.characteristics.audience}</p>
        </div>
      </div>
      
      {/* Metrics Justification */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <p className="text-sm font-semibold text-gray-700 mb-2">Your Text Analysis:</p>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>• Average {metrics.avgSentenceLength.toFixed(1)} words per sentence</li>
          <li>• Average {metrics.avgSyllablesPerWord.toFixed(2)} syllables per word</li>
          <li>• {metrics.difficultWordsPercentage.toFixed(1)}% difficult words</li>
          <li>• Flesch Reading Ease: {metrics.fleschReadingEase.toFixed(1)} / 100</li>
        </ul>
      </div>
    </div>
  );
};

export default GradeExplanation;
```

### Step 4.3: Add to Analysis Results

**Modify:** `frontend/src/components/Analysis/AnalysisResults.tsx`

Add import:
```tsx
import GradeExplanation from './GradeExplanation';
```

Add after the grade display:
```tsx
{/* Grade Explanation */}
<GradeExplanation
  gradeLevel={analysis.predicted_grade_level}
  metrics={{
    avgSentenceLength: analysis.avg_sentence_length,
    avgSyllablesPerWord: analysis.avg_syllables_per_word,
    difficultWordsPercentage: analysis.difficult_words_percentage,
    fleschReadingEase: analysis.flesch_reading_ease
  }}
/>
```

### Step 4.4: Add to Simplification Page (Both Sides)

**Modify:** `frontend/src/components/Simplification/SimplifyPage.tsx`

Add explanations for both original and simplified:

```tsx
{/* Split View */}
<div className="grid grid-cols-2 gap-6">
  {/* Left: Original */}
  <div className="border rounded p-6">
    <h3 className="text-lg font-bold mb-4">Original Text</h3>
    
    {/* NEW: Original Grade Explanation */}
    {originalMetrics && (
      <GradeExplanation
        gradeLevel={originalMetrics.grade}
        metrics={originalMetrics}
      />
    )}
    
    <div className="prose">{originalText}</div>
  </div>
  
  {/* Right: Simplified */}
  <div className="border rounded p-6">
    <h3 className="text-lg font-bold mb-4">Simplified (Grade {targetGrade})</h3>
    
    {/* NEW: Simplified Grade Explanation */}
    {simplifiedMetrics && (
      <GradeExplanation
        gradeLevel={`Grade ${targetGrade}`}
        metrics={simplifiedMetrics}
      />
    )}
    
    <div className="prose">{/* highlighted changes */}</div>
  </div>
</div>
```

You'll need to fetch metrics for both original and simplified text.

---

## PART 5: Export Simplification as PDF/DOCX

### Step 5.1: Add jsPDF-AutoTable for Better PDFs

**Install:**
```bash
cd frontend
npm install jspdf-autotable
```

### Step 5.2: Create Simplification Export Utility

**Create:** `frontend/src/utils/exportSimplification.ts`

```typescript
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import { Document, Paragraph, TextRun, HeadingLevel, AlignmentType, Packer } from 'docx';
import { saveAs } from 'file-saver';

interface SimplificationData {
  originalText: string;
  simplifiedText: string;
  targetGrade: number;
  changes: Array<{
    type: string;
    original: string;
    simplified: string;
    reason: string;
  }>;
  metricsOriginal: any;
  metricsSimplified: any;
}

export async function exportSimplificationPDF(data: SimplificationData) {
  const doc = new jsPDF();
  let yPos = 20;
  
  // Title
  doc.setFontSize(20);
  doc.setFont('helvetica', 'bold');
  doc.text('ClarityWorks - Text Simplification Report', 105, yPos, { align: 'center' });
  yPos += 15;
  
  // Subtitle
  doc.setFontSize(12);
  doc.setFont('helvetica', 'normal');
  doc.text(`Target Grade Level: Grade ${data.targetGrade}`, 105, yPos, { align: 'center' });
  yPos += 15;
  
  // Original Text Section
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('Original Text', 20, yPos);
  yPos += 8;
  
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  const originalLines = doc.splitTextToSize(data.originalText, 170);
  doc.text(originalLines, 20, yPos);
  yPos += (originalLines.length * 5) + 10;
  
  // Check if need new page
  if (yPos > 250) {
    doc.addPage();
    yPos = 20;
  }
  
  // Simplified Text Section
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('Simplified Text', 20, yPos);
  yPos += 8;
  
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  const simplifiedLines = doc.splitTextToSize(data.simplifiedText, 170);
  doc.text(simplifiedLines, 20, yPos);
  yPos += (simplifiedLines.length * 5) + 10;
  
  if (yPos > 250) {
    doc.addPage();
    yPos = 20;
  }
  
  // Changes Table
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('Changes Applied', 20, yPos);
  yPos += 10;
  
  const changesData = data.changes.map(c => [
    c.type.replace('_', ' ').toUpperCase(),
    c.original,
    c.simplified,
    c.reason
  ]);
  
  autoTable(doc, {
    head: [['Type', 'Original', 'Simplified', 'Reason']],
    body: changesData,
    startY: yPos,
    styles: { fontSize: 8 },
    headStyles: { fillColor: [59, 130, 246] }
  });
  
  // Save
  doc.save(`simplification-grade-${data.targetGrade}.pdf`);
}

export async function exportSimplificationDOCX(data: SimplificationData) {
  const doc = new Document({
    sections: [{
      properties: {},
      children: [
        // Title
        new Paragraph({
          text: 'ClarityWorks - Text Simplification Report',
          heading: HeadingLevel.HEADING_1,
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 }
        }),
        
        new Paragraph({
          text: `Target Grade Level: Grade ${data.targetGrade}`,
          alignment: AlignmentType.CENTER,
          spacing: { after: 400 }
        }),
        
        // Original Text
        new Paragraph({
          text: 'Original Text',
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 200, after: 100 }
        }),
        
        new Paragraph({
          text: data.originalText,
          spacing: { after: 400 }
        }),
        
        // Simplified Text
        new Paragraph({
          text: 'Simplified Text',
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 200, after: 100 }
        }),
        
        new Paragraph({
          text: data.simplifiedText,
          spacing: { after: 400 }
        }),
        
        // Changes
        new Paragraph({
          text: 'Changes Applied',
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 200, after: 100 }
        }),
        
        ...data.changes.flatMap(change => [
          new Paragraph({
            children: [
              new TextRun({
                text: `${change.type.replace('_', ' ').toUpperCase()}: `,
                bold: true
              }),
              new TextRun({
                text: `"${change.original}" → "${change.simplified}"`
              })
            ]
          }),
          new Paragraph({
            text: `Reason: ${change.reason}`,
            spacing: { after: 100 }
          })
        ])
      ]
    }]
  });
  
  const blob = await Packer.toBlob(doc);
  saveAs(blob, `simplification-grade-${data.targetGrade}.docx`);
}
```

### Step 5.3: Add Export Buttons to SimplifyPage

**Modify:** `frontend/src/components/Simplification/SimplifyPage.tsx`

Add export buttons:

```tsx
{simplifiedText && (
  <div className="flex gap-2">
    <button
      onClick={handleSave}
      className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
    >
      Save to History
    </button>
    
    {/* NEW: Export Buttons */}
    <button
      onClick={() => exportSimplificationPDF({
        originalText,
        simplifiedText,
        targetGrade,
        changes,
        metricsOriginal,
        metricsSimplified
      })}
      className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
    >
      📄 Export PDF
    </button>
    
    <button
      onClick={() => exportSimplificationDOCX({
        originalText,
        simplifiedText,
        targetGrade,
        changes,
        metricsOriginal,
        metricsSimplified
      })}
      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
    >
      📝 Export DOCX
    </button>
  </div>
)}
```

---

## PART 6: Export RAG Results as PDF/DOCX

### Step 6.1: Create RAG Export Utility

**Create:** `frontend/src/utils/exportRAG.ts`

```typescript
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import { Document, Paragraph, HeadingLevel, AlignmentType, Packer } from 'docx';
import { saveAs } from 'file-saver';

interface RAGResult {
  text: string;
  metadata: {
    chunk_id: number;
    page_number?: number;
    word_count: number;
  };
  similarity_score: number;
  collection: string;
}

interface RAGExportData {
  query: string;
  results: RAGResult[];
  documentNames: string[];
}

export async function exportRAGResultsPDF(data: RAGExportData) {
  const doc = new jsPDF();
  let yPos = 20;
  
  // Title
  doc.setFontSize(20);
  doc.setFont('helvetica', 'bold');
  doc.text('ClarityWorks - RAG Query Results', 105, yPos, { align: 'center' });
  yPos += 15;
  
  // Query
  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.text('Query:', 20, yPos);
  yPos += 7;
  
  doc.setFont('helvetica', 'italic');
  doc.setFontSize(11);
  const queryLines = doc.splitTextToSize(`"${data.query}"`, 170);
  doc.text(queryLines, 20, yPos);
  yPos += (queryLines.length * 5) + 10;
  
  // Documents Searched
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.text(`Documents searched: ${data.documentNames.join(', ')}`, 20, yPos);
  yPos += 10;
  
  doc.text(`Results found: ${data.results.length}`, 20, yPos);
  yPos += 15;
  
  // Results
  data.results.forEach((result, index) => {
    if (yPos > 250) {
      doc.addPage();
      yPos = 20;
    }
    
    // Result header
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.text(`Result ${index + 1}`, 20, yPos);
    yPos += 7;
    
    // Metadata
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.text(
      `Page: ${result.metadata.page_number || 'N/A'} | Similarity: ${(result.similarity_score * 100).toFixed(1)}% | Words: ${result.metadata.word_count}`,
      20,
      yPos
    );
    yPos += 7;
    
    // Text
    doc.setFontSize(10);
    const textLines = doc.splitTextToSize(result.text, 170);
    doc.text(textLines, 20, yPos);
    yPos += (textLines.length * 5) + 10;
  });
  
  doc.save('rag-query-results.pdf');
}

export async function exportRAGResultsDOCX(data: RAGExportData) {
  const doc = new Document({
    sections: [{
      properties: {},
      children: [
        // Title
        new Paragraph({
          text: 'ClarityWorks - RAG Query Results',
          heading: HeadingLevel.HEADING_1,
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 }
        }),
        
        // Query
        new Paragraph({
          text: 'Query',
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 200, after: 100 }
        }),
        
        new Paragraph({
          text: `"${data.query}"`,
          italics: true,
          spacing: { after: 200 }
        }),
        
        // Metadata
        new Paragraph({
          text: `Documents searched: ${data.documentNames.join(', ')}`,
          spacing: { after: 100 }
        }),
        
        new Paragraph({
          text: `Results found: ${data.results.length}`,
          spacing: { after: 400 }
        }),
        
        // Results
        ...data.results.flatMap((result, index) => [
          new Paragraph({
            text: `Result ${index + 1}`,
            heading: HeadingLevel.HEADING_3,
            spacing: { before: 300, after: 100 }
          }),
          
          new Paragraph({
            text: `Page: ${result.metadata.page_number || 'N/A'} | Similarity: ${(result.similarity_score * 100).toFixed(1)}% | Words: ${result.metadata.word_count}`,
            spacing: { after: 100 }
          }),
          
          new Paragraph({
            text: result.text,
            spacing: { after: 200 }
          })
        ])
      ]
    }]
  });
  
  const blob = await Packer.toBlob(doc);
  saveAs(blob, 'rag-query-results.docx');
}
```

### Step 6.2: Add Export Buttons to RAGQuery

**Modify:** `frontend/src/components/RAG/RAGQuery.tsx`

Update export buttons section:

```tsx
{results.length > 0 && (
  <div className="flex gap-2 mb-4">
    <button
      onClick={() => exportRAGResultsPDF({
        query,
        results,
        documentNames: selectedDocs.map(id => 
          documents.find(d => d.chromadb_collection_id === id)?.original_filename || 'Unknown'
        )
      })}
      className="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600"
    >
      📄 Export PDF
    </button>
    
    <button
      onClick={() => exportRAGResultsDOCX({
        query,
        results,
        documentNames: selectedDocs.map(id => 
          documents.find(d => d.chromadb_collection_id === id)?.original_filename || 'Unknown'
        )
      })}
      className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
    >
      📝 Export DOCX
    </button>
    
    <button
      onClick={() => {/* existing TXT export */}}
      className="px-3 py-1 bg-gray-200 rounded hover:bg-gray-300"
    >
      📋 Export TXT
    </button>
    
    <button
      onClick={() => navigator.clipboard.writeText(results.map(r => r.text).join('\n\n---\n\n'))}
      className="px-3 py-1 bg-gray-200 rounded hover:bg-gray-300"
    >
      📋 Copy All
    </button>
  </div>
)}
```

---

## PART 7: Save Simplification to History (Before/After)

### Step 7.1: Update Save Function

**Modify:** `frontend/src/components/Simplification/SimplifyPage.tsx`

Update the `handleSave` function to include both versions:

```typescript
const handleSave = async () => {
  try {
    const acceptedChanges = changes.filter(c => c.accepted === true);
    
    await api.post('/simplify/save', {
      analysisId,
      originalText,            // Include original
      simplifiedText,
      targetGrade,
      changes: acceptedChanges,
      mode,
      // NEW: Include metrics for both
      metricsOriginal: {
        grade: originalGrade,
        avgSentenceLength: originalMetrics.avgSentenceLength,
        avgSyllablesPerWord: originalMetrics.avgSyllablesPerWord,
        fleschReadingEase: originalMetrics.fleschReadingEase,
        difficultWordsPercentage: originalMetrics.difficultWordsPercentage
      },
      metricsSimplified: {
        grade: targetGrade,
        avgSentenceLength: simplifiedMetrics.avgSentenceLength,
        avgSyllablesPerWord: simplifiedMetrics.avgSyllablesPerWord,
        fleschReadingEase: simplifiedMetrics.fleschReadingEase,
        difficultWordsPercentage: simplifiedMetrics.difficultWordsPercentage
      }
    });
    
    alert('Simplification saved to history!');
    navigate('/history');
  } catch (error) {
    console.error('Save error:', error);
    alert('Failed to save simplification');
  }
};
```

### Step 7.2: Update Backend to Store Metrics

**Modify:** `backend/src/controllers/simplifyController.ts`

Update `saveSimplification`:

```typescript
export const saveSimplification = async (req: Request, res: Response) => {
  try {
    const { 
      analysisId, 
      originalText,
      simplifiedText, 
      targetGrade, 
      changes, 
      mode,
      metricsOriginal,
      metricsSimplified
    } = req.body;
    
    // Save to simplification_history table
    const result = await pool.query(
      `INSERT INTO simplification_history 
       (analysis_id, user_id, original_text, simplified_text, target_grade, changes_applied, mode, metrics_original, metrics_simplified) 
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) 
       RETURNING *`,
      [
        analysisId,
        (req as any).user.userId,
        originalText,
        simplifiedText,
        `Grade ${targetGrade}`,
        JSON.stringify(changes),
        mode,
        JSON.stringify(metricsOriginal),
        JSON.stringify(metricsSimplified)
      ]
    );
    
    res.json(result.rows[0]);
  } catch (error: any) {
    console.error('Save simplification error:', error);
    res.status(500).json({ error: 'Failed to save simplification' });
  }
};
```

### Step 7.3: Update Database Schema

**Modify:** `backend/src/config/database.ts`

Update simplification_history table:

```typescript
await pool.query(`
  ALTER TABLE simplification_history 
  ADD COLUMN IF NOT EXISTS metrics_original JSONB,
  ADD COLUMN IF NOT EXISTS metrics_simplified JSONB;
`);
```

---

## PART 8: Show Simplification History in History Page

### Step 8.1: Create Simplification History Component

**Create:** `frontend/src/components/History/SimplificationHistory.tsx`

```tsx
import React, { useState, useEffect } from 'react';
import api from '../../services/api';

const SimplificationHistory: React.FC = () => {
  const [simplifications, setSimplifications] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchSimplifications();
  }, []);
  
  const fetchSimplifications = async () => {
    try {
      const response = await api.get('/simplify/history');
      setSimplifications(response.data);
    } catch (error) {
      console.error('Failed to fetch simplification history:', error);
    }
    setLoading(false);
  };
  
  if (loading) return <div>Loading simplification history...</div>;
  
  return (
    <div className="mt-8">
      <h2 className="text-2xl font-bold mb-4">Simplification History</h2>
      
      {simplifications.length === 0 ? (
        <p className="text-gray-500 italic">No simplifications saved yet.</p>
      ) : (
        <div className="space-y-6">
          {simplifications.map((simp: any) => (
            <div key={simp.id} className="bg-white border rounded-lg p-6">
              {/* Header */}
              <div className="flex justify-between items-start mb-4">
                <div>
                  <p className="text-sm text-gray-600">
                    {new Date(simp.created_at).toLocaleDateString()}
                  </p>
                  <p className="text-lg font-semibold">
                    Simplified to {simp.target_grade}
                  </p>
                  <p className="text-sm text-gray-500">
                    Mode: {simp.mode} | {JSON.parse(simp.changes_applied).length} changes applied
                  </p>
                </div>
              </div>
              
              {/* Before/After Comparison */}
              <div className="grid grid-cols-2 gap-4">
                {/* Original */}
                <div className="bg-red-50 border border-red-200 rounded p-4">
                  <p className="font-semibold text-red-800 mb-2">Original</p>
                  {simp.metrics_original && (
                    <div className="text-xs text-gray-600 mb-2">
                      Grade: {JSON.parse(simp.metrics_original).grade} | 
                      Flesch: {JSON.parse(simp.metrics_original).fleschReadingEase.toFixed(1)}
                    </div>
                  )}
                  <p className="text-sm text-gray-700 line-clamp-4">
                    {simp.original_text}
                  </p>
                </div>
                
                {/* Simplified */}
                <div className="bg-green-50 border border-green-200 rounded p-4">
                  <p className="font-semibold text-green-800 mb-2">Simplified</p>
                  {simp.metrics_simplified && (
                    <div className="text-xs text-gray-600 mb-2">
                      Grade: {JSON.parse(simp.metrics_simplified).grade} | 
                      Flesch: {JSON.parse(simp.metrics_simplified).fleschReadingEase.toFixed(1)}
                    </div>
                  )}
                  <p className="text-sm text-gray-700 line-clamp-4">
                    {simp.simplified_text}
                  </p>
                </div>
              </div>
              
              {/* View Details Button */}
              <button
                onClick={() => {/* Navigate to detail view or expand */}}
                className="mt-4 text-blue-600 hover:underline text-sm"
              >
                View full details →
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default SimplificationHistory;
```

### Step 8.2: Add to History Page

**Modify:** `frontend/src/components/History/History.tsx`

Add tab for simplifications:

```tsx
<Tabs defaultValue="analyses" className="w-full">
  <TabsList>
    <TabsTrigger value="analyses">Analyses</TabsTrigger>
    <TabsTrigger value="simplifications">Simplifications</TabsTrigger>
  </TabsList>
  
  <TabsContent value="analyses">
    {/* Existing analyses history */}
  </TabsContent>
  
  <TabsContent value="simplifications">
    <SimplificationHistory />
  </TabsContent>
</Tabs>
```

### Step 8.3: Add Backend Endpoint

**Modify:** `backend/src/routes/simplifyRoutes.ts`

Add history endpoint:

```typescript
router.get('/history', authMiddleware, async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user.userId;
    
    const result = await pool.query(
      `SELECT * FROM simplification_history 
       WHERE user_id = $1 
       ORDER BY created_at DESC 
       LIMIT 50`,
      [userId]
    );
    
    res.json(result.rows);
  } catch (error: any) {
    console.error('Fetch simplification history error:', error);
    res.status(500).json({ error: 'Failed to fetch simplification history' });
  }
});
```

---

## PART 9: Add Loading States

### Step 9.1: Add Loading Component

**Create:** `frontend/src/components/common/LoadingSpinner.tsx`

```tsx
import React from 'react';

interface Props {
  message?: string;
  fullScreen?: boolean;
}

const LoadingSpinner: React.FC<Props> = ({ message = 'Processing...', fullScreen = false }) => {
  const containerClass = fullScreen 
    ? 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50'
    : 'flex flex-col items-center justify-center p-8';
  
  return (
    <div className={containerClass}>
      <div className="bg-white rounded-lg p-8 shadow-xl">
        <div className="flex flex-col items-center">
          {/* Spinner */}
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-500"></div>
          
          {/* Message */}
          <p className="mt-4 text-gray-700 font-medium">{message}</p>
          
          {/* Sub-message */}
          <p className="mt-2 text-sm text-gray-500">This may take a few moments...</p>
        </div>
      </div>
    </div>
  );
};

export default LoadingSpinner;
```

### Step 9.2: Add to All Processing Points

**Analysis submission:**
```tsx
{loading && <LoadingSpinner message="Analyzing text..." fullScreen />}
```

**Simplification:**
```tsx
{loading && <LoadingSpinner message="Simplifying text..." fullScreen />}
```

**RAG upload:**
```tsx
{uploading && <LoadingSpinner message="Uploading and processing textbook..." fullScreen />}
```

**RAG query:**
```tsx
{querying && <LoadingSpinner message="Searching documents..." fullScreen />}
```

---

## PART 10: Add Heatmaps to Analysis

### Step 10.1: Create Heatmap Component

**Create:** `frontend/src/components/Analysis/TextHeatmap.tsx`

```tsx
import React from 'react';

interface Props {
  text: string;
  difficultWords: Array<{ word: string; position: number }>;
  difficultSentences: Array<{ sentence: string; position: number }>;
}

const TextHeatmap: React.FC<Props> = ({ text, difficultWords, difficultSentences }) => {
  // Color intensity based on difficulty
  const getWordColor = (word: string) => {
    const isDifficult = difficultWords.some(dw => dw.word.toLowerCase() === word.toLowerCase());
    if (isDifficult) return 'bg-red-300';
    return 'bg-transparent';
  };
  
  const getSentenceColor = (sentence: string) => {
    const isDifficult = difficultSentences.some(ds => ds.sentence === sentence);
    if (isDifficult) return 'border-l-4 border-red-500 bg-red-50';
    return 'border-l-4 border-green-500 bg-green-50';
  };
  
  const sentences = text.split(/[.!?]+/).filter(s => s.trim());
  
  return (
    <div className="bg-white border rounded-lg p-6">
      <h3 className="text-lg font-bold mb-4">Text Difficulty Heatmap</h3>
      
      <div className="space-y-2">
        {sentences.map((sentence, idx) => (
          <div key={idx} className={`p-3 rounded ${getSentenceColor(sentence)}`}>
            {sentence.split(/\s+/).map((word, widx) => (
              <span key={widx} className={`${getWordColor(word)} px-1 rounded`}>
                {word}{' '}
              </span>
            ))}
          </div>
        ))}
      </div>
      
      {/* Legend */}
      <div className="mt-6 flex gap-6 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-red-300 rounded"></div>
          <span>Difficult Words</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-l-4 border-red-500 bg-red-50"></div>
          <span>Difficult Sentences</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-l-4 border-green-500 bg-green-50"></div>
          <span>Easy Sentences</span>
        </div>
      </div>
    </div>
  );
};

export default TextHeatmap;
```

### Step 10.2: Add to Analysis Results

**Modify:** `frontend/src/components/Analysis/AnalysisResults.tsx`

Add heatmap after charts:

```tsx
{/* Heatmap Section */}
<div className="mt-8">
  <TextHeatmap
    text={analysis.original_text}
    difficultWords={analysis.difficult_words}
    difficultSentences={analysis.difficult_sentences}
  />
</div>
```

---

## DELIVERABLES

1. ✅ College test file created + all 11 tests passing
2. ✅ Text extraction cleaned (whitespace, nonsense removed)
3. ✅ Live word count visible and prominent
4. ✅ Grade explanations (layman + technical) on analysis page
5. ✅ Grade explanations on both sides of simplification page
6. ✅ Simplification export as PDF/DOCX
7. ✅ RAG results export as PDF/DOCX
8. ✅ Simplification saved to history with before/after metrics
9. ✅ Simplification history displayed in History page
10. ✅ Loading states on all processing actions
11. ✅ Heatmaps showing text difficulty visually

---

## TESTING CHECKLIST

### Test 1: Calibrated Files
```bash
python testing/ml-service/validate_test_files.py
```
All 11 should show ✅ PASS (Grades 3-12 + College)

### Test 2: Text Extraction
- Upload a messy PDF with images/whitespace
- Verify extracted text is clean and editable
- Check no image markers like [Figure 1]

### Test 3: Word Count
- Navigate to TextInput
- Type text and verify live count updates
- Check validation messages (min 50, max 50,000)

### Test 4: Grade Explanations
- Analyze any text
- Verify layman explanation shows
- Click "Technical" button, verify technical explanation shows
- Check metrics justification at bottom

### Test 5: Simplification Export
- Simplify text
- Click "Export PDF" - verify PDF downloads with before/after
- Click "Export DOCX" - verify DOCX downloads

### Test 6: RAG Export
- Query RAG documents
- Click "Export PDF" - verify results in PDF
- Click "Export DOCX" - verify results in DOCX

### Test 7: Simplification History
- Save a simplification
- Navigate to History page
- Click "Simplifications" tab
- Verify before/after comparison shows

### Test 8: Loading States
- Submit analysis - verify loading spinner
- Simplify text - verify loading spinner
- Upload RAG doc - verify loading spinner

### Test 9: Heatmap
- View analysis results
- Scroll to heatmap section
- Verify difficult words highlighted in red
- Verify difficult sentences have red border

---

## SUCCESS CRITERIA

Run through this checklist:

- ✅ All 11 test files predict within ±0.3 grades (or ±0.5 for College)
- ✅ Text extraction produces clean, editable text
- ✅ Word count is prominently displayed and updates live
- ✅ Every analysis shows "Why Grade X?" explanation (layman + technical toggle)
- ✅ Simplification page shows explanations for both original and simplified
- ✅ Can export simplification as PDF and DOCX
- ✅ Can export RAG results as PDF and DOCX
- ✅ Simplification saves to history with metrics
- ✅ History page has "Simplifications" tab showing before/after
- ✅ Loading spinners appear during all processing
- ✅ Heatmap visualizes difficulty at word and sentence level

---

**This is the final polish for your FYP presentation. After completing this prompt, ClarityWorks will be production-ready!** 🎉
