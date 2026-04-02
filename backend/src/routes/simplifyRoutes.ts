import { Router } from 'express';
import { authMiddleware } from '../middleware/auth';
import {
  analyzeForSimplification,
  applyChanges,
  saveSimplification,
  getSimplificationHistory,
} from '../controllers/simplifyController';

const router = Router();

router.use(authMiddleware);

router.post('/analyze', analyzeForSimplification);
router.post('/apply', applyChanges);
router.post('/save', saveSimplification);
router.get('/history', getSimplificationHistory);

export default router;
