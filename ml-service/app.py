import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import pdfplumber
from docx import Document
from PIL import Image
import pytesseract
import tempfile

import uuid

from models import ReadabilityModel
from models.simplifier import TextSimplifier
from models.rag_engine import RAGEngine
from utils.change_patches import apply_changes_by_span
from utils.text_cleaner import TextCleaner

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Tesseract path for Windows
tesseract_path = os.getenv('TESSERACT_PATH')
if tesseract_path and os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

# Initialize model
model = ReadabilityModel()
model.load_models()

# Initialize simplifier
simplifier = TextSimplifier(readability_model=model)

# Initialize RAG engine
rag_engine = RAGEngine()

# If models not found, they will use heuristic fallback
if not model.is_trained:
    print("Warning: No trained models found. Using heuristic predictions.")
    print("Run train_model.py with CLEAR Corpus to train ML models.")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'model_trained': model.is_trained,
        'wordnet_available': simplifier.wordnet_available,
        'rag_answer_generation': rag_engine.groq_client is not None,
        'rag_reranker': rag_engine.ranker is not None
    })

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        text = data.get('text', '')

        if not text or len(text.strip()) < 50:
            return jsonify({'error': 'Text must be at least 50 characters'}), 400

        analysis = model.predict(text)

        return jsonify({
            'success': True,
            'analysis': analysis
        })
    except Exception as e:
        print(f"Analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/extract-pdf', methods=['POST'])
def extract_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        text_parts = []
        page_count = 0

        try:
            with pdfplumber.open(tmp_path) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
        finally:
            os.unlink(tmp_path)

        full_text = '\n\n'.join(text_parts)

        # Clean the extracted text
        full_text = TextCleaner.remove_images_markers(full_text)
        full_text = TextCleaner.clean_extracted_text(full_text)
        full_text = TextCleaner.ensure_editable(full_text)

        return jsonify({
            'success': True,
            'text': full_text,
            'page_count': page_count
        })
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/extract-doc', methods=['POST'])
def extract_doc():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        filename = file.filename.lower()

        if filename.endswith('.docx'):
            suffix = '.docx'
        else:
            suffix = '.doc'

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            doc = Document(tmp_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            full_text = '\n\n'.join(paragraphs)
        finally:
            os.unlink(tmp_path)

        # Clean the extracted text
        full_text = TextCleaner.remove_images_markers(full_text)
        full_text = TextCleaner.clean_extracted_text(full_text)
        full_text = TextCleaner.ensure_editable(full_text)

        return jsonify({
            'success': True,
            'text': full_text
        })
    except Exception as e:
        print(f"DOC extraction error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/extract-image', methods=['POST'])
def extract_image():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']

        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            # Open and preprocess image
            image = Image.open(tmp_path)

            # Convert to grayscale for better OCR
            if image.mode != 'L':
                image = image.convert('L')

            # Perform OCR
            text = pytesseract.image_to_string(image)

            # Get confidence data
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            confidences = [int(c) for c in data['conf'] if int(c) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        finally:
            os.unlink(tmp_path)

        # Clean the OCR text
        cleaned_text = TextCleaner.remove_images_markers(text)
        cleaned_text = TextCleaner.clean_extracted_text(cleaned_text)
        cleaned_text = TextCleaner.ensure_editable(cleaned_text)

        return jsonify({
            'success': True,
            'text': cleaned_text.strip(),
            'confidence': round(avg_confidence, 2)
        })
    except Exception as e:
        print(f"Image extraction error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/train', methods=['POST'])
def train_model():
    try:
        data = request.get_json()
        corpus_path = data.get('corpus_path')

        if not corpus_path:
            corpus_path = os.path.join(
                os.path.dirname(__file__),
                'data', 'clear_corpus', 'clear_corpus.csv'
            )

        if not os.path.exists(corpus_path):
            return jsonify({
                'error': f'Corpus not found at {corpus_path}'
            }), 404

        metrics = model.train(corpus_path)

        return jsonify({
            'success': True,
            'metrics': metrics
        })
    except Exception as e:
        print(f"Training error: {e}")
        return jsonify({'error': str(e)}), 500

def extract_text_from_pdf(file):
    """Extract text from a PDF file using pdfplumber."""
    import gc, time
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    try:
        with pdfplumber.open(tmp_path) as pdf:
            pages = [page.extract_text() or '' for page in pdf.pages]
        return '\n\n'.join(p for p in pages if p.strip())
    finally:
        gc.collect()
        for _ in range(5):
            try:
                os.unlink(tmp_path)
                break
            except OSError:
                time.sleep(0.2)


def extract_text_from_docx(file):
    """Extract text from a DOCX file object"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        doc = Document(tmp_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return '\n\n'.join(paragraphs)
    finally:
        os.unlink(tmp_path)
@app.route('/rag/upload', methods=['POST'])
def upload_rag_document():
    """Upload and process textbook for RAG"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        user_id = request.form.get('user_id', '')

        print(f"Uploading RAG document: {file.filename}")

        # Extract text based on file type
        filename = file.filename.lower()
        if filename.endswith('.pdf'):
            text = extract_text_from_pdf(file)
        elif filename.endswith(('.docx', '.doc')):
            text = extract_text_from_docx(file)
        else:
            return jsonify({'error': 'Unsupported file type. Use PDF or DOCX.'}), 400

        # Clean the text before RAG processing
        text = TextCleaner.remove_images_markers(text)
        text = TextCleaner.clean_textbook_text(text)
        text = TextCleaner.clean_extracted_text(text)

        if not text or len(text) < 100:
            return jsonify({'error': 'Could not extract sufficient text from file'}), 400

        # Generate unique document ID
        doc_id = str(uuid.uuid4())

        # Upload to RAG engine
        result = rag_engine.upload_document(
            document_id=doc_id,
            text=text,
            metadata={
                'filename': file.filename,
                'user_id': user_id
            }
        )

        return jsonify({
            'document_id': doc_id,
            'chunks_created': result['chunks_created'],
            'collection_id': result['collection_id']
        })

    except Exception as e:
        import traceback
        print(f"RAG upload error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/rag/query', methods=['POST'])
def query_rag_documents():
    """Query across uploaded textbooks with True RAG answer generation"""
    try:
        data = request.get_json()
        query_text = data['query']
        document_ids = data.get('document_ids')
        top_k = data.get('top_k', 5)

        result = rag_engine.query_documents(query_text, document_ids, top_k)

        return jsonify({
            'query': query_text,
            'answer': result['answer'],
            'sources': result['sources'],
            'has_answer': result['has_answer'],
            'results_count': len(result['sources']),
            'results': result['sources']
        })

    except Exception as e:
        print(f"RAG query error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/rag/documents/<doc_id>', methods=['DELETE'])
def delete_rag_document(doc_id):
    """Delete textbook from RAG system"""
    try:
        rag_engine.delete_document(doc_id)
        return jsonify({'status': 'deleted', 'document_id': doc_id})

    except Exception as e:
        print(f"RAG delete error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/simplify/analyze', methods=['POST'])
def analyze_for_simplification():
    """Analyze text and return suggested changes"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        target_grade = int(data.get('target_grade', 6))
        mode = data.get('mode', 'auto')  # 'auto' or 'interactive'

        if not text or len(text.strip()) < 10:
            return jsonify({'error': 'Text must be at least 10 characters'}), 400

        result = simplifier.simplify_to_grade(text, target_grade, mode=mode)

        return jsonify({
            'original_text': text,
            'suggested_changes': result['changes'],
            'preview_text': result['simplified_text'],
            'preview_metrics': result.get('preview_metrics'),
            'target_distance': result.get('target_distance'),
            'selection_summary': result.get('selection_summary'),
        })

    except Exception as e:
        print(f"Simplification error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/simplify/apply', methods=['POST'])
def apply_selected_changes():
    """Apply only accepted changes (for interactive mode)"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        accepted_change_ids = data.get('accepted_changes', [])
        all_changes = data.get('all_changes', [])

        final_text = apply_changes_by_span(text, all_changes, accepted_change_ids)

        return jsonify({'simplified_text': final_text})

    except Exception as e:
        print(f"Apply changes error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5001))
    debug = os.getenv('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
