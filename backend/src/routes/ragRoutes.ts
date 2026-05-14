import { Router } from 'express';
import { authMiddleware } from '../middleware/auth';
import { documentUpload } from '../config/documentUpload';
import {
  uploadDocument,
  uploadDocumentAsync,
  getRagUploadProgress,
  queryDocuments,
  getDocuments,
  deleteDocument,
  generateDocumentConceptGraph,
  getDocumentConceptGraph,
} from '../controllers/ragController';

const router = Router();

router.use(authMiddleware);

router.post('/upload', documentUpload.single('file'), uploadDocument);
router.post('/upload-async', documentUpload.single('file'), uploadDocumentAsync);
router.get('/upload-progress/:taskId', getRagUploadProgress);
router.post('/query', queryDocuments);
router.get('/documents', getDocuments);
router.post('/documents/:id/concepts', generateDocumentConceptGraph);
router.get('/documents/:id/concepts', getDocumentConceptGraph);
router.delete('/documents/:id', deleteDocument);

export default router;
