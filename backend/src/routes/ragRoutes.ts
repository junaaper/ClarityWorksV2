import { Router } from 'express';
import { authMiddleware } from '../middleware/auth';
import { documentUpload } from '../config/documentUpload';
import {
  uploadDocument,
  queryDocuments,
  getDocuments,
  deleteDocument,
} from '../controllers/ragController';

const router = Router();

router.use(authMiddleware);

router.post('/upload', documentUpload.single('file'), uploadDocument);
router.post('/query', queryDocuments);
router.get('/documents', getDocuments);
router.delete('/documents/:id', deleteDocument);

export default router;
