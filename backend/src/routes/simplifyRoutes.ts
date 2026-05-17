import { Router } from 'express';
import { authMiddleware } from '../middleware/auth';
import {
  analyzeForSimplification,
  analyzeAsync,
  getSimplifyProgress,
  applyChanges,
  saveSimplification,
  getSimplificationHistory,
} from '../controllers/simplifyController';

const router = Router();

router.use(authMiddleware);

router.post('/analyze', analyzeForSimplification);
router.post('/analyze-async', analyzeAsync);
router.get('/progress/:taskId', getSimplifyProgress);
router.post('/apply', applyChanges);
router.post('/save', saveSimplification);
router.get('/history', getSimplificationHistory);

export default router;
