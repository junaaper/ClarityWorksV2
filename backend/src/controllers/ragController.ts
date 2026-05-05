import { Response } from 'express';
import axios from 'axios';
import pool from '../config/database';
import FormData from 'form-data';
import fs from 'fs';
import { AuthRequest } from '../middleware/auth';

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:5001';

export const uploadDocument = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    if (!req.file) {
      res.status(400).json({ error: 'No file uploaded' });
      return;
    }

    const userId = req.userId;

    // Create form data for Python service
    const formData = new FormData();
    formData.append('file', fs.createReadStream(req.file.path), {
      filename: req.file.originalname,
    });
    formData.append('user_id', String(userId));

    // Call Python service
    const response = await axios.post(
      `${PYTHON_SERVICE_URL}/rag/upload`,
      formData,
      {
        headers: formData.getHeaders(),
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
        timeout: 300000, // 5 minute timeout for large files
      }
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
    console.error('RAG upload error:', error.message);
    // Clean up file on error
    if (req.file?.path && fs.existsSync(req.file.path)) {
      fs.unlinkSync(req.file.path);
    }
    res.status(500).json({ error: 'Failed to upload document' });
  }
};

export const queryDocuments = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { query, documentIds } = req.body;
    const userId = req.userId;
    const requestedIds = Array.isArray(documentIds)
      ? [...new Set(documentIds.filter((id): id is string => typeof id === 'string' && id.trim().length > 0))]
      : [];

    let docsQuery = 'SELECT chromadb_collection_id FROM rag_documents WHERE user_id = $1';
    const docsParams: Array<number | string[]> = [userId!];

    if (requestedIds.length > 0) {
      docsQuery += ' AND chromadb_collection_id = ANY($2)';
      docsParams.push(requestedIds.map((id) => `doc_${id}`));
    }

    const docsResult = await pool.query(docsQuery, docsParams);

    if (docsResult.rows.length === 0) {
      res.status(404).json({ error: 'No accessible RAG documents found for this query' });
      return;
    }

    if (requestedIds.length > 0 && docsResult.rows.length !== requestedIds.length) {
      res.status(403).json({ error: 'One or more selected documents are unavailable' });
      return;
    }

    const scopedDocumentIds = docsResult.rows.map((row) =>
      String(row.chromadb_collection_id).replace(/^doc_/, '')
    );

    // Call Python service
    const response = await axios.post(`${PYTHON_SERVICE_URL}/rag/query`, {
      query,
      document_ids: scopedDocumentIds
    });

    // Save query to history
    await pool.query(
      `INSERT INTO rag_queries (user_id, query_text, document_ids, result_count)
       VALUES ($1, $2, $3, $4)`,
      [userId, query, scopedDocumentIds, response.data.results_count]
    );

    res.json(response.data);
  } catch (error: any) {
    console.error('RAG query error:', error.message);
    res.status(500).json({ error: 'Failed to query documents' });
  }
};

export const getDocuments = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userId = req.userId;

    const result = await pool.query(
      'SELECT * FROM rag_documents WHERE user_id = $1 ORDER BY uploaded_at DESC',
      [userId]
    );

    res.json(result.rows);
  } catch (error: any) {
    console.error('Get documents error:', error.message);
    res.status(500).json({ error: 'Failed to get documents' });
  }
};

export const generateDocumentConceptGraph = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const userId = req.userId;

    const doc = await pool.query(
      'SELECT id, chromadb_collection_id FROM rag_documents WHERE id = $1 AND user_id = $2',
      [id, userId]
    );

    if (doc.rows.length === 0) {
      res.status(404).json({ error: 'Document not found' });
      return;
    }

    const collectionId = doc.rows[0].chromadb_collection_id;
    const documentId = collectionId.replace('doc_', '');

    const chunksResponse = await axios.get(
      `${PYTHON_SERVICE_URL}/rag/documents/${documentId}/chunks`
    );
    const chunks = chunksResponse.data.chunks || [];

    if (chunks.length === 0) {
      res.status(400).json({ error: 'No text chunks found for this document' });
      return;
    }

    const conceptResponse = await axios.post(`${PYTHON_SERVICE_URL}/concepts/extract`, {
      chunks,
    });

    const conceptGraph = conceptResponse.data.concept_graph || null;

    await pool.query(
      'UPDATE rag_documents SET concept_graph = $1 WHERE id = $2',
      [JSON.stringify(conceptGraph), id]
    );

    res.json({ success: true, conceptGraph });
  } catch (error: any) {
    console.error('RAG concept graph error:', error.message);
    if (axios.isAxiosError(error) && error.code === 'ECONNREFUSED') {
      res.status(503).json({ error: 'Analysis service unavailable' });
    } else {
      res.status(500).json({ error: 'Failed to generate concept graph' });
    }
  }
};

export const getDocumentConceptGraph = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const userId = req.userId;

    const result = await pool.query(
      'SELECT concept_graph FROM rag_documents WHERE id = $1 AND user_id = $2',
      [id, userId]
    );

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'Document not found' });
      return;
    }

    res.json({ conceptGraph: result.rows[0].concept_graph || null });
  } catch (error: any) {
    console.error('Get concept graph error:', error.message);
    res.status(500).json({ error: 'Failed to get concept graph' });
  }
};

export const deleteDocument = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const userId = req.userId;

    // Get document info
    const doc = await pool.query(
      'SELECT chromadb_collection_id FROM rag_documents WHERE id = $1 AND user_id = $2',
      [id, userId]
    );

    if (doc.rows.length === 0) {
      res.status(404).json({ error: 'Document not found' });
      return;
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
    console.error('Delete document error:', error.message);
    res.status(500).json({ error: 'Failed to delete document' });
  }
};
