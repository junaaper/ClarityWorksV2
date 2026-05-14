import { Response } from 'express';
import axios from 'axios';
import pool from '../config/database';
import { AuthRequest } from '../middleware/auth';

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:5001';

const MIN_TEXT_LENGTH = 50;
const MAX_TEXT_LENGTH = 50000;

const validateAnalysisText = (text: unknown): { text: string | null; error?: string } => {
  if (typeof text !== 'string') {
    return { text: null, error: 'Text must be provided' };
  }

  const trimmed = text.trim();
  if (trimmed.length < MIN_TEXT_LENGTH) {
    return { text: null, error: `Text must be at least ${MIN_TEXT_LENGTH} characters long` };
  }

  if (trimmed.length > MAX_TEXT_LENGTH) {
    return { text: null, error: `Text must be less than ${MAX_TEXT_LENGTH.toLocaleString()} characters` };
  }

  return { text: trimmed };
};

const fetchAnalysisFromPython = async (text: string) => {
  const analysisResponse = await axios.post(`${PYTHON_SERVICE_URL}/analyze`, {
    text,
  });

  return analysisResponse.data.analysis;
};

export const analyzeText = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { text, title } = req.body;
    const userId = req.userId;

    const validation = validateAnalysisText(text);
    if (!validation.text) {
      res.status(400).json({ error: validation.error });
      return;
    }

    const analysis = await fetchAnalysisFromPython(validation.text);

    // Save to database
    const result = await pool.query(
      `INSERT INTO analyses (
        user_id, original_text, title, word_count, sentence_count,
        avg_sentence_length, avg_syllables_per_word, flesch_reading_ease,
        flesch_kincaid_grade, automated_readability_index, smog_readability,
        coleman_liau_index, predicted_grade_level, predicted_complexity,
        confidence, raw_score, model_predictions, model_breakdown,
        difficult_words_count, difficult_words_percentage,
        difficult_words, difficult_sentences
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22)
      RETURNING id, created_at`,
      [
        userId,
        validation.text,
        title || `Analysis ${new Date().toLocaleDateString()}`,
        analysis.basic_metrics.word_count,
        analysis.basic_metrics.sentence_count,
        analysis.basic_metrics.avg_sentence_length,
        analysis.basic_metrics.avg_syllables_per_word,
        analysis.readability_scores.flesch_reading_ease,
        analysis.readability_scores.flesch_kincaid_grade,
        analysis.readability_scores.automated_readability_index,
        analysis.readability_scores.smog_readability,
        analysis.readability_scores.coleman_liau_index,
        analysis.predictions.predicted_grade_level,
        analysis.predictions.predicted_complexity,
        analysis.predictions.confidence,
        analysis.predictions.raw_score ?? null,
        JSON.stringify(analysis.predictions.model_predictions || null),
        JSON.stringify(analysis.predictions.model_breakdown || null),
        analysis.statistics.difficult_words_count,
        analysis.statistics.difficult_words_percentage,
        JSON.stringify(analysis.difficult_elements.difficult_words),
        JSON.stringify(analysis.difficult_elements.difficult_sentences),
      ]
    );

    res.json({
      success: true,
      analysisId: result.rows[0].id,
      createdAt: result.rows[0].created_at,
      analysis,
    });
  } catch (error) {
    console.error('Analysis error:', error);
    if (axios.isAxiosError(error) && error.code === 'ECONNREFUSED') {
      res.status(503).json({ error: 'Analysis service unavailable. Please try again later.' });
    } else {
      res.status(500).json({ error: 'Error analyzing text' });
    }
  }
};

export const analyzeTextPreview = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { text } = req.body;
    const validation = validateAnalysisText(text);

    if (!validation.text) {
      res.status(400).json({ error: validation.error });
      return;
    }

    const analysis = await fetchAnalysisFromPython(validation.text);

    res.json({
      success: true,
      analysis,
    });
  } catch (error) {
    console.error('Analysis preview error:', error);
    if (axios.isAxiosError(error) && error.code === 'ECONNREFUSED') {
      res.status(503).json({ error: 'Analysis service unavailable. Please try again later.' });
    } else {
      res.status(500).json({ error: 'Error analyzing text' });
    }
  }
};

export const getAnalyses = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userId = req.userId;
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 10;
    const offset = (page - 1) * limit;
    const search = req.query.search as string;
    const gradeLevel = req.query.gradeLevel as string;

    let query = `
      SELECT id, title, word_count, sentence_count, flesch_reading_ease,
             predicted_grade_level, predicted_complexity, created_at
      FROM analyses
      WHERE user_id = $1
    `;
    const params: (string | number)[] = [userId!];
    let paramIndex = 2;

    if (search) {
      query += ` AND (title ILIKE $${paramIndex} OR original_text ILIKE $${paramIndex})`;
      params.push(`%${search}%`);
      paramIndex++;
    }

    if (gradeLevel) {
      query += ` AND predicted_grade_level = $${paramIndex}`;
      params.push(gradeLevel);
      paramIndex++;
    }

    query += ` ORDER BY created_at DESC LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`;
    params.push(limit, offset);

    const result = await pool.query(query, params);

    // Get total count (must mirror the same filters as the main query)
    let countQuery = 'SELECT COUNT(*) FROM analyses WHERE user_id = $1';
    const countParams: (string | number)[] = [userId!];
    let countParamIndex = 2;

    if (search) {
      countQuery += ` AND (title ILIKE $${countParamIndex} OR original_text ILIKE $${countParamIndex})`;
      countParams.push(`%${search}%`);
      countParamIndex++;
    }

    if (gradeLevel) {
      countQuery += ` AND predicted_grade_level = $${countParamIndex}`;
      countParams.push(gradeLevel);
      countParamIndex++;
    }

    const countResult = await pool.query(countQuery, countParams);
    const totalCount = parseInt(countResult.rows[0].count);

    res.json({
      analyses: result.rows,
      pagination: {
        page,
        limit,
        totalCount,
        totalPages: Math.ceil(totalCount / limit),
      },
    });
  } catch (error) {
    console.error('Get analyses error:', error);
    res.status(500).json({ error: 'Error fetching analyses' });
  }
};

export const getAnalysisById = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const userId = req.userId;
    const userRole = req.userRole;

    // Admin can view any analysis, regular users can only view their own
    let result;
    if (userRole === 'admin') {
      result = await pool.query('SELECT * FROM analyses WHERE id = $1', [id]);
    } else {
      result = await pool.query('SELECT * FROM analyses WHERE id = $1 AND user_id = $2', [id, userId]);
    }

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'Analysis not found' });
      return;
    }

    const row = result.rows[0];
    res.json({
      id: row.id,
      title: row.title,
      originalText: row.original_text,
      createdAt: row.created_at,
      conceptGraph: row.concept_graph || null,
      analysis: {
        basic_metrics: {
          word_count: row.word_count,
          sentence_count: row.sentence_count,
          avg_sentence_length: parseFloat(row.avg_sentence_length),
          avg_syllables_per_word: parseFloat(row.avg_syllables_per_word),
        },
        readability_scores: {
          flesch_reading_ease: parseFloat(row.flesch_reading_ease),
          flesch_kincaid_grade: parseFloat(row.flesch_kincaid_grade),
          automated_readability_index: parseFloat(row.automated_readability_index),
          smog_readability: parseFloat(row.smog_readability),
          coleman_liau_index: parseFloat(row.coleman_liau_index),
        },
        predictions: {
          predicted_grade_level: row.predicted_grade_level,
          predicted_complexity: row.predicted_complexity,
          confidence: parseFloat(row.confidence),
          raw_score: row.raw_score == null ? undefined : parseFloat(row.raw_score),
          model_predictions: row.model_predictions || undefined,
          model_breakdown: row.model_breakdown || undefined,
        },
        statistics: {
          difficult_words_count: row.difficult_words_count,
          difficult_words_percentage: parseFloat(row.difficult_words_percentage),
        },
        difficult_elements: {
          difficult_words: row.difficult_words,
          difficult_sentences: row.difficult_sentences,
        },
      },
    });
  } catch (error) {
    console.error('Get analysis error:', error);
    res.status(500).json({ error: 'Error fetching analysis' });
  }
};

export const generateConceptGraph = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const userId = req.userId;
    const userRole = req.userRole;

    let result;
    if (userRole === 'admin') {
      result = await pool.query('SELECT id, original_text FROM analyses WHERE id = $1', [id]);
    } else {
      result = await pool.query('SELECT id, original_text FROM analyses WHERE id = $1 AND user_id = $2', [id, userId]);
    }

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'Analysis not found' });
      return;
    }

    const originalText = result.rows[0].original_text;

    const conceptResponse = await axios.post(`${PYTHON_SERVICE_URL}/concepts/extract`, {
      text: originalText,
    });

    const conceptGraph = conceptResponse.data.concept_graph || null;

    await pool.query(
      'UPDATE analyses SET concept_graph = $1 WHERE id = $2',
      [JSON.stringify(conceptGraph), id]
    );

    res.json({ success: true, conceptGraph });
  } catch (error) {
    console.error('Concept graph generation error:', error);
    if (axios.isAxiosError(error) && error.code === 'ECONNREFUSED') {
      res.status(503).json({ error: 'Analysis service unavailable. Please try again later.' });
    } else {
      res.status(500).json({ error: 'Error generating concept graph' });
    }
  }
};

export const deleteAnalysis = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const userId = req.userId;

    const result = await pool.query(
      'DELETE FROM analyses WHERE id = $1 AND user_id = $2 RETURNING id',
      [id, userId]
    );

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'Analysis not found' });
      return;
    }

    res.json({ message: 'Analysis deleted successfully' });
  } catch (error) {
    console.error('Delete analysis error:', error);
    res.status(500).json({ error: 'Error deleting analysis' });
  }
};

export const getStats = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const userId = req.userId;

    const result = await pool.query(
      `SELECT
        COUNT(*) as total_analyses,
        AVG(flesch_reading_ease) as avg_reading_ease,
        AVG(flesch_kincaid_grade) as avg_grade_level,
        SUM(word_count) as total_words_analyzed
      FROM analyses
      WHERE user_id = $1`,
      [userId]
    );

    const recentResult = await pool.query(
      `SELECT id, title, predicted_grade_level, created_at
       FROM analyses
       WHERE user_id = $1
       ORDER BY created_at DESC
       LIMIT 3`,
      [userId]
    );

    res.json({
      stats: {
        totalAnalyses: parseInt(result.rows[0].total_analyses) || 0,
        avgReadingEase: parseFloat(result.rows[0].avg_reading_ease) || 0,
        avgGradeLevel: parseFloat(result.rows[0].avg_grade_level) || 0,
        totalWordsAnalyzed: parseInt(result.rows[0].total_words_analyzed) || 0,
      },
      recentAnalyses: recentResult.rows,
    });
  } catch (error) {
    console.error('Get stats error:', error);
    res.status(500).json({ error: 'Error fetching stats' });
  }
};
