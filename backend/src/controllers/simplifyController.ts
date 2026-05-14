import { Response } from 'express';
import axios from 'axios';
import pool from '../config/database';
import { AuthRequest } from '../middleware/auth';

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:5001';

export const analyzeForSimplification = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { analysisId, targetGrade, text, mode } = req.body;

    let originalText = text;

    // If analysisId provided, fetch text from database
    if (analysisId && !originalText) {
      const analysis = await pool.query(
        'SELECT original_text FROM analyses WHERE id = $1 AND user_id = $2',
        [analysisId, req.userId]
      );

      if (analysis.rows.length === 0) {
        res.status(404).json({ error: 'Analysis not found' });
        return;
      }

      originalText = analysis.rows[0].original_text;
    }

    if (!originalText) {
      res.status(400).json({ error: 'No text provided' });
      return;
    }

    // Call Python ML service
    const response = await axios.post(`${PYTHON_SERVICE_URL}/simplify/analyze`, {
      text: originalText,
      target_grade: targetGrade,
      mode: mode || 'auto'
    });

    res.json(response.data);
  } catch (error: any) {
    console.error('Simplification analysis error:', error.message);
    res.status(500).json({ error: 'Failed to analyze for simplification' });
  }
};

export const applyChanges = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { text, acceptedChanges, allChanges } = req.body;

    const response = await axios.post(`${PYTHON_SERVICE_URL}/simplify/apply`, {
      text,
      accepted_changes: acceptedChanges,
      all_changes: allChanges
    });

    res.json(response.data);
  } catch (error: any) {
    console.error('Apply changes error:', error.message);
    res.status(500).json({ error: 'Failed to apply changes' });
  }
};

export const saveSimplification = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { analysisId, simplifiedText, targetGrade, changes, mode, metricsOriginal, metricsSimplified } = req.body;
    const targetLabel = targetGrade >= 13 ? 'College' : `Grade ${targetGrade}`;

    // Get original text
    const analysis = await pool.query(
      'SELECT original_text FROM analyses WHERE id = $1 AND user_id = $2',
      [analysisId, req.userId]
    );

    if (analysis.rows.length === 0) {
      res.status(404).json({ error: 'Analysis not found' });
      return;
    }

    // Save to simplification_history
    const result = await pool.query(
      `INSERT INTO simplification_history
       (analysis_id, user_id, original_text, simplified_text, target_grade, changes_applied, mode, metrics_original, metrics_simplified)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
       RETURNING *`,
      [
        analysisId,
        req.userId,
        analysis.rows[0].original_text,
        simplifiedText,
        targetLabel,
        JSON.stringify(changes),
        mode,
        metricsOriginal ? JSON.stringify(metricsOriginal) : null,
        metricsSimplified ? JSON.stringify(metricsSimplified) : null
      ]
    );

    res.json({ success: true, simplification: result.rows[0] });
  } catch (error: any) {
    console.error('Save simplification error:', error.message);
    res.status(500).json({ error: 'Failed to save simplification' });
  }
};

export const analyzeAsync = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { analysisId, targetGrade, text, mode } = req.body;

    let originalText = text;

    if (analysisId && !originalText) {
      const analysis = await pool.query(
        'SELECT original_text FROM analyses WHERE id = $1 AND user_id = $2',
        [analysisId, req.userId]
      );
      if (analysis.rows.length === 0) {
        res.status(404).json({ error: 'Analysis not found' });
        return;
      }
      originalText = analysis.rows[0].original_text;
    }

    if (!originalText) {
      res.status(400).json({ error: 'No text provided' });
      return;
    }

    const response = await axios.post(`${PYTHON_SERVICE_URL}/simplify/analyze-async`, {
      text: originalText,
      target_grade: targetGrade,
      mode: mode || 'auto'
    });

    res.status(202).json(response.data);
  } catch (error: any) {
    console.error('Async simplification error:', error.message);
    res.status(500).json({ error: 'Failed to start simplification' });
  }
};

export const getSimplifyProgress = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { taskId } = req.params;
    const response = await axios.get(`${PYTHON_SERVICE_URL}/simplify/progress/${taskId}`);
    res.json(response.data);
  } catch (error: any) {
    if (error.response?.status === 404) {
      res.status(404).json({ error: 'Unknown task' });
      return;
    }
    if (error.response?.status === 500) {
      res.json(error.response.data);
      return;
    }
    console.error('Progress polling error:', error.message);
    res.status(500).json({ error: 'Failed to get progress' });
  }
};

export const getSimplificationHistory = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const result = await pool.query(
      `SELECT * FROM simplification_history
       WHERE user_id = $1
       ORDER BY created_at DESC
       LIMIT 50`,
      [req.userId]
    );

    res.json(result.rows);
  } catch (error: any) {
    console.error('Fetch simplification history error:', error.message);
    res.status(500).json({ error: 'Failed to fetch simplification history' });
  }
};
