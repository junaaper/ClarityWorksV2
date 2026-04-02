# PROMPT 4: RAG for Textbook Processing

## Context
You've completed Prompts 1-3. Now implement RAG (Retrieval-Augmented Generation) to handle large textbooks (100s-1000s of pages).

## Objective
Allow users to:
- Upload multiple textbooks (PDF/DOCX)
- Query: "Retrieve all content about the heart"
- Get relevant paragraphs from across all uploaded textbooks
- Export results as PDF/DOCX/TXT

---

## STEP 1: Install Dependencies

**1.1 Add to `ml-service/requirements.txt`:**

```
chromadb==0.4.22
sentence-transformers==2.3.1
```

**1.2 Install:**

```bash
cd ml-service
pip install chromadb sentence-transformers
```

**Note:** `sentence-transformers` will download the `all-MiniLM-L6-v2` model (~80MB) on first use.

---

## STEP 2: Database Schema

Add to `backend/src/config/database.ts`:

```typescript
await pool.query(`
  CREATE TABLE IF NOT EXISTS rag_documents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size_bytes INTEGER,
    total_pages INTEGER,
    total_chunks INTEGER,
    chromadb_collection_id VARCHAR(255) NOT NULL UNIQUE,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS rag_queries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    document_ids INTEGER[],
    result_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE INDEX IF NOT EXISTS idx_rag_docs_user ON rag_documents(user_id);
  CREATE INDEX IF NOT EXISTS idx_rag_queries_user ON rag_queries(user_id);
`);
```

---

## STEP 3: Create RAG Engine

Create `ml-service/models/rag_engine.py`:

```python
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import os

class RAGEngine:
    """
    Retrieval-Augmented Generation engine for textbook processing
    Uses ChromaDB (local vector database) + Sentence-BERT embeddings
    """
    
    def __init__(self):
        # Initialize ChromaDB with persistent storage
        persist_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'chromadb')
        os.makedirs(persist_dir, exist_ok=True)
        
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_dir
        ))
        
        # Load embedding model (80MB, runs locally, no API needed)
        print("Loading embedding model...")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("Embedding model loaded!")
    
    def upload_document(self, document_id, text, metadata):
        """
        Chunk document, generate embeddings, store in ChromaDB
        
        Args:
            document_id: Unique ID (UUID)
            text: Full extracted text
            metadata: {'filename', 'user_id', 'total_pages'}
        
        Returns:
            {'chunks_created', 'collection_id'}
        """
        print(f"Processing document {document_id}...")
        
        # Smart chunking
        chunks = self.chunk_text(text, chunk_size=500, overlap=50)
        print(f"Created {len(chunks)} chunks")
        
        # Create collection for this document
        collection_name = f"doc_{document_id}"
        collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata=metadata
        )
        
        # Generate embeddings (this takes a few seconds for large docs)
        print("Generating embeddings...")
        chunk_texts = [chunk['text'] for chunk in chunks]
        embeddings = self.embedding_model.encode(chunk_texts, show_progress_bar=True)
        
        # Store in ChromaDB
        print("Storing in vector database...")
        collection.add(
            embeddings=embeddings.tolist(),
            documents=chunk_texts,
            metadatas=[{
                'chunk_id': i,
                'page_number': chunk.get('page', 0),
                'word_count': chunk['word_count'],
                'document_id': document_id
            } for i, chunk in enumerate(chunks)],
            ids=[f"chunk_{i}" for i in range(len(chunks))]
        )
        
        # Persist to disk
        self.client.persist()
        
        print(f"✅ Document uploaded: {len(chunks)} chunks stored")
        
        return {
            'chunks_created': len(chunks),
            'collection_id': collection_name
        }
    
    def query_documents(self, query_text, document_ids=None, top_k=20):
        """
        Semantic search across one or multiple documents
        
        Args:
            query_text: Natural language query (e.g., "content about the heart")
            document_ids: List of doc IDs to search (None = all documents)
            top_k: Number of results to return
        
        Returns:
            List of {text, metadata, similarity_score, collection}
        """
        print(f"Querying: '{query_text}'")
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query_text])[0]
        
        # Determine which collections to search
        if document_ids:
            collection_names = [f"doc_{doc_id}" for doc_id in document_ids]
        else:
            # Search all collections
            all_collections = self.client.list_collections()
            collection_names = [c.name for c in all_collections]
        
        print(f"Searching {len(collection_names)} document(s)...")
        
        # Query each collection
        all_results = []
        for coll_name in collection_names:
            try:
                collection = self.client.get_collection(coll_name)
                
                results = collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    n_results=min(top_k, 10),  # Max 10 per collection
                    include=['documents', 'metadatas', 'distances']
                )
                
                # Convert to unified format
                for i, doc in enumerate(results['documents'][0]):
                    similarity = 1 - results['distances'][0][i]  # Convert distance to similarity
                    
                    all_results.append({
                        'text': doc,
                        'metadata': results['metadatas'][0][i],
                        'similarity_score': similarity,
                        'collection': coll_name
                    })
            
            except Exception as e:
                print(f"Error querying collection {coll_name}: {e}")
                continue
        
        # Sort by similarity (highest first)
        all_results.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        # Take top K
        top_results = all_results[:top_k]
        
        print(f"✅ Found {len(top_results)} relevant chunks")
        
        return top_results
    
    def chunk_text(self, text, chunk_size=500, overlap=50):
        """
        Smart chunking: preserve paragraph boundaries, add overlap
        
        Args:
            text: Full document text
            chunk_size: Target words per chunk
            overlap: Overlapping words between chunks
        
        Returns:
            List of {'text', 'word_count'} dicts
        """
        # Split by paragraphs
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = []
        current_word_count = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_words = para.split()
            para_word_count = len(para_words)
            
            # If adding this paragraph keeps us under chunk_size, add it
            if current_word_count + para_word_count < chunk_size:
                current_chunk.append(para)
                current_word_count += para_word_count
            else:
                # Save current chunk
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append({
                        'text': chunk_text,
                        'word_count': current_word_count
                    })
                
                # Start new chunk with overlap from previous
                if current_chunk:
                    last_para = current_chunk[-1]
                    overlap_words = last_para.split()[-overlap:]
                    overlap_text = ' '.join(overlap_words)
                    current_chunk = [overlap_text, para]
                    current_word_count = len(overlap_words) + para_word_count
                else:
                    current_chunk = [para]
                    current_word_count = para_word_count
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append({
                'text': chunk_text,
                'word_count': current_word_count
            })
        
        return chunks
    
    def delete_document(self, document_id):
        """Delete document collection from ChromaDB"""
        try:
            collection_name = f"doc_{document_id}"
            self.client.delete_collection(collection_name)
            self.client.persist()
            print(f"✅ Deleted document collection: {collection_name}")
        except Exception as e:
            print(f"Error deleting collection: {e}")
    
    def get_all_collections(self):
        """Get list of all document collections"""
        return self.client.list_collections()
```

---

## STEP 4: Flask Endpoints

Add to `ml-service/app.py`:

```python
from models.rag_engine import RAGEngine
import uuid

# Initialize RAG engine
rag_engine = RAGEngine()

@app.route('/rag/upload', methods=['POST'])
def upload_rag_document():
    """Upload and process textbook for RAG"""
    try:
        file = request.files['file']
        user_id = request.form.get('user_id')
        
        print(f"Uploading RAG document: {file.filename}")
        
        # Extract text based on file type
        if file.filename.endswith('.pdf'):
            text = extract_text_from_pdf(file)
        elif file.filename.endswith(('.docx', '.doc')):
            text = extract_text_from_docx(file)
        else:
            return jsonify({'error': 'Unsupported file type. Use PDF or DOCX.'}), 400
        
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
        print(f"RAG upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/rag/query', methods=['POST'])
def query_rag_documents():
    """Query across uploaded textbooks"""
    try:
        data = request.json
        query_text = data['query']
        document_ids = data.get('document_ids')  # None = search all
        top_k = data.get('top_k', 20)
        
        results = rag_engine.query_documents(query_text, document_ids, top_k)
        
        return jsonify({
            'query': query_text,
            'results_count': len(results),
            'results': results
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
```

---

## STEP 5: Backend Controller

Create `backend/src/controllers/ragController.ts`:

```typescript
import { Request, Response } from 'express';
import axios from 'axios';
import pool from '../config/database';
import FormData from 'form-data';
import fs from 'fs';

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:5001';

export const uploadDocument = async (req: Request, res: Response) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }
    
    const userId = (req as any).user.userId;
    
    // Create form data for Python service
    const formData = new FormData();
    formData.append('file', fs.createReadStream(req.file.path));
    formData.append('user_id', userId.toString());
    
    // Call Python service
    const response = await axios.post(
      `${PYTHON_SERVICE_URL}/rag/upload`,
      formData,
      { headers: formData.getHeaders() }
    );
    
    // Save to database
    const result = await pool.query(
      `INSERT INTO rag_documents 
       (user_id, filename, original_filename, file_size_bytes, total_chunks, chromadb_collection_id) 
       VALUES ($1, $2, $3, $4, $5, $6) 
       RETURNING *`,
      [
        userId,
        req.file.filename,
        req.file.originalname,
        req.file.size,
        response.data.chunks_created,
        response.data.collection_id
      ]
    );
    
    // Clean up uploaded file
    fs.unlinkSync(req.file.path);
    
    res.json(result.rows[0]);
  } catch (error: any) {
    console.error('RAG upload error:', error);
    res.status(500).json({ error: 'Failed to upload document' });
  }
};

export const queryDocuments = async (req: Request, res: Response) => {
  try {
    const { query, documentIds } = req.body;
    const userId = (req as any).user.userId;
    
    // Call Python service
    const response = await axios.post(`${PYTHON_SERVICE_URL}/rag/query`, {
      query,
      document_ids: documentIds
    });
    
    // Save query to history
    await pool.query(
      `INSERT INTO rag_queries (user_id, query_text, document_ids, result_count) 
       VALUES ($1, $2, $3, $4)`,
      [userId, query, documentIds || [], response.data.results_count]
    );
    
    res.json(response.data);
  } catch (error: any) {
    console.error('RAG query error:', error);
    res.status(500).json({ error: 'Failed to query documents' });
  }
};

export const getDocuments = async (req: Request, res: Response) => {
  try {
    const userId = (req as any).user.userId;
    
    const result = await pool.query(
      'SELECT * FROM rag_documents WHERE user_id = $1 ORDER BY uploaded_at DESC',
      [userId]
    );
    
    res.json(result.rows);
  } catch (error: any) {
    console.error('Get documents error:', error);
    res.status(500).json({ error: 'Failed to get documents' });
  }
};

export const deleteDocument = async (req: Request, res: Response) => {
  try {
    const { id } = req.params;
    const userId = (req as any).user.userId;
    
    // Get document info
    const doc = await pool.query(
      'SELECT chromadb_collection_id FROM rag_documents WHERE id = $1 AND user_id = $2',
      [id, userId]
    );
    
    if (doc.rows.length === 0) {
      return res.status(404).json({ error: 'Document not found' });
    }
    
    // Extract document_id from collection_id (format: "doc_UUID")
    const collectionId = doc.rows[0].chromadb_collection_id;
    const documentId = collectionId.replace('doc_', '');
    
    // Delete from ChromaDB
    await axios.delete(`${PYTHON_SERVICE_URL}/rag/documents/${documentId}`);
    
    // Delete from database
    await pool.query('DELETE FROM rag_documents WHERE id = $1', [id]);
    
    res.json({ status: 'deleted' });
  } catch (error: any) {
    console.error('Delete document error:', error);
    res.status(500).json({ error: 'Failed to delete document' });
  }
};
```

---

## STEP 6: Backend Routes

Create `backend/src/routes/ragRoutes.ts`:

```typescript
import express from 'express';
import { authMiddleware } from '../middleware/auth';
import { upload } from '../config/upload';
import { 
  uploadDocument, 
  queryDocuments, 
  getDocuments, 
  deleteDocument 
} from '../controllers/ragController';

const router = express.Router();

router.post('/upload', authMiddleware, upload.single('file'), uploadDocument);
router.post('/query', authMiddleware, queryDocuments);
router.get('/documents', authMiddleware, getDocuments);
router.delete('/documents/:id', authMiddleware, deleteDocument);

export default router;
```

Add to `backend/src/server.ts`:

```typescript
import ragRoutes from './routes/ragRoutes';

app.use('/api/rag', ragRoutes);
```

---

## STEP 7: Frontend - RAG Upload Page

Create `frontend/src/components/RAG/RAGUpload.tsx`:

```tsx
import React, { useState, useEffect } from 'react';
import api from '../../services/api';

interface RagDocument {
  id: number;
  original_filename: string;
  file_size_bytes: number;
  total_chunks: number;
  uploaded_at: string;
}

const RAGUpload: React.FC = () => {
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  
  useEffect(() => {
    fetchDocuments();
  }, []);
  
  const fetchDocuments = async () => {
    try {
      const response = await api.get('/rag/documents');
      setDocuments(response.data);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    }
  };
  
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Check file type
    if (!file.name.endsWith('.pdf') && !file.name.endsWith('.docx')) {
      alert('Please upload PDF or DOCX files only');
      return;
    }
    
    setUploading(true);
    setUploadProgress('Uploading file...');
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      setUploadProgress('Processing and chunking document...');
      const response = await api.post('/rag/upload', formData);
      
      setUploadProgress(`✅ Success! Created ${response.data.total_chunks} chunks`);
      
      // Refresh list
      fetchDocuments();
      
      setTimeout(() => {
        setUploadProgress('');
        setUploading(false);
      }, 2000);
      
    } catch (error: any) {
      console.error('Upload error:', error);
      setUploadProgress('❌ Upload failed: ' + (error.response?.data?.error || 'Unknown error'));
      setUploading(false);
    }
  };
  
  const handleDelete = async (id: number) => {
    if (!confirm('Delete this textbook? This cannot be undone.')) return;
    
    try {
      await api.delete(`/rag/documents/${id}`);
      fetchDocuments();
    } catch (error) {
      console.error('Delete error:', error);
      alert('Failed to delete document');
    }
  };
  
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">RAG Textbook Upload</h1>
      
      {/* Upload Area */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-bold mb-4">Upload Textbook</h2>
        
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileUpload}
            disabled={uploading}
            className="hidden"
            id="rag-file-upload"
          />
          <label
            htmlFor="rag-file-upload"
            className="cursor-pointer inline-block px-6 py-3 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            {uploading ? 'Processing...' : 'Choose PDF or DOCX File'}
          </label>
          
          {uploadProgress && (
            <p className="mt-4 text-sm text-gray-700">{uploadProgress}</p>
          )}
        </div>
        
        <p className="text-sm text-gray-600 mt-4">
          Supports large textbooks (100s-1000s of pages). Processing may take a few minutes.
        </p>
      </div>
      
      {/* Document List */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4">Uploaded Textbooks ({documents.length})</h2>
        
        {documents.length === 0 ? (
          <p className="text-gray-500 italic">No textbooks uploaded yet.</p>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2">Filename</th>
                <th className="text-left py-2">Size</th>
                <th className="text-left py-2">Chunks</th>
                <th className="text-left py-2">Uploaded</th>
                <th className="text-left py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map(doc => (
                <tr key={doc.id} className="border-b">
                  <td className="py-3">{doc.original_filename}</td>
                  <td>{(doc.file_size_bytes / 1024 / 1024).toFixed(2)} MB</td>
                  <td>{doc.total_chunks}</td>
                  <td>{new Date(doc.uploaded_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="text-red-600 hover:text-red-800"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default RAGUpload;
```

---

## STEP 8: Frontend - RAG Query Page

Create `frontend/src/components/RAG/RAGQuery.tsx`:

```tsx
import React, { useState, useEffect } from 'react';
import api from '../../services/api';

interface RagDocument {
  id: number;
  original_filename: string;
  chromadb_collection_id: string;
}

interface QueryResult {
  text: string;
  metadata: {
    chunk_id: number;
    page_number: number;
    word_count: number;
  };
  similarity_score: number;
  collection: string;
}

const RAGQuery: React.FC = () => {
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<QueryResult[]>([]);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    fetchDocuments();
  }, []);
  
  const fetchDocuments = async () => {
    try {
      const response = await api.get('/rag/documents');
      setDocuments(response.data);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    }
  };
  
  const handleQuery = async () => {
    if (!query.trim()) {
      alert('Please enter a query');
      return;
    }
    
    setLoading(true);
    
    try {
      // Extract document IDs from collection IDs
      const documentIds = selectedDocs.length > 0
        ? selectedDocs.map(coll => coll.replace('doc_', ''))
        : null;
      
      const response = await api.post('/rag/query', {
        query,
        documentIds
      });
      
      setResults(response.data.results);
    } catch (error) {
      console.error('Query error:', error);
      alert('Failed to query documents');
    }
    
    setLoading(false);
  };
  
  const toggleDocument = (collectionId: string) => {
    setSelectedDocs(prev =>
      prev.includes(collectionId)
        ? prev.filter(id => id !== collectionId)
        : [...prev, collectionId]
    );
  };
  
  const exportResults = (format: 'txt' | 'pdf' | 'docx') => {
    // Simple text export for now
    const text = results.map((r, i) => 
      `[Result ${i + 1}] (Similarity: ${(r.similarity_score * 100).toFixed(1)}%)\n${r.text}\n\n`
    ).join('---\n\n');
    
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rag_query_results.${format}`;
    a.click();
  };
  
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Query Textbooks</h1>
      
      <div className="grid grid-cols-3 gap-6">
        {/* Document Selection */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="font-bold mb-4">Select Textbooks</h3>
          
          {documents.length === 0 ? (
            <p className="text-gray-500 italic text-sm">No textbooks uploaded</p>
          ) : (
            <div className="space-y-2">
              {documents.map(doc => (
                <label key={doc.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedDocs.includes(doc.chromadb_collection_id)}
                    onChange={() => toggleDocument(doc.chromadb_collection_id)}
                  />
                  <span className="text-sm">{doc.original_filename}</span>
                </label>
              ))}
              
              <button
                onClick={() => setSelectedDocs([])}
                className="text-sm text-blue-600 hover:underline mt-2"
              >
                Search All Documents
              </button>
            </div>
          )}
        </div>
        
        {/* Query & Results */}
        <div className="col-span-2 bg-white rounded-lg shadow p-6">
          <h3 className="font-bold mb-4">Query</h3>
          
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., Retrieve all content about the heart"
            className="w-full h-24 border rounded p-3 mb-4"
          />
          
          <button
            onClick={handleQuery}
            disabled={loading}
            className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
          
          {/* Results */}
          {results.length > 0 && (
            <div className="mt-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="font-bold">{results.length} Results Found</h3>
                
                <div className="flex gap-2">
                  <button
                    onClick={() => exportResults('txt')}
                    className="px-3 py-1 bg-gray-200 rounded text-sm hover:bg-gray-300"
                  >
                    Export TXT
                  </button>
                  <button
                    onClick={() => navigator.clipboard.writeText(results.map(r => r.text).join('\n\n---\n\n'))}
                    className="px-3 py-1 bg-gray-200 rounded text-sm hover:bg-gray-300"
                  >
                    Copy All
                  </button>
                </div>
              </div>
              
              <div className="space-y-4">
                {results.map((result, i) => (
                  <div key={i} className="border rounded p-4">
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-sm text-gray-600">
                        Result #{i + 1} | Similarity: {(result.similarity_score * 100).toFixed(1)}%
                      </span>
                      <span className="text-xs text-gray-500">
                        {result.metadata.word_count} words
                      </span>
                    </div>
                    
                    <p className="text-sm leading-relaxed">{result.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RAGQuery;
```

---

## STEP 9: Add Routes

In `frontend/src/App.tsx`:

```tsx
import RAGUpload from './components/RAG/RAGUpload';
import RAGQuery from './components/RAG/RAGQuery';

// Add routes:
<Route path="/rag/upload" element={<RAGUpload />} />
<Route path="/rag/query" element={<RAGQuery />} />
```

Add to sidebar navigation:

```tsx
<Link to="/rag/upload">Upload Textbooks</Link>
<Link to="/rag/query">Query Textbooks</Link>
```

---

## DELIVERABLES

1. ✅ ChromaDB + Sentence-BERT installed
2. ✅ Database tables created
3. ✅ `rag_engine.py` with chunking, embedding, querying
4. ✅ Flask endpoints for upload/query/delete
5. ✅ Backend controller and routes
6. ✅ Frontend upload page
7. ✅ Frontend query page with multi-document search

---

## SUCCESS CRITERIA

Test RAG:

1. ✅ Upload a PDF textbook (processing takes 1-5 min depending on size)
2. ✅ See chunks created
3. ✅ Navigate to Query page
4. ✅ Enter query: "Retrieve content about [topic from textbook]"
5. ✅ See relevant paragraphs returned with similarity scores
6. ✅ Export results as TXT

---

**After completing this prompt, proceed to PROMPT_5_Model_Improvements.md**
