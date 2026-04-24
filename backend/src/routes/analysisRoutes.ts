import { Router } from 'express';
import {
  analyzeText,
  analyzeTextPreview,
  getAnalyses,
  getAnalysisById,
  deleteAnalysis,
  getStats,
} from '../controllers/analysisController';
import { authMiddleware } from '../middleware/auth';

const router = Router();

router.use(authMiddleware);

router.post('/', analyzeText);
router.post('/preview', analyzeTextPreview);
router.get('/', getAnalyses);
router.get('/stats', getStats);
router.get('/:id', getAnalysisById);
router.delete('/:id', deleteAnalysis);

export default router;
