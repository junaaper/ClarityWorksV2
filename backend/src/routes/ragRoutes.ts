import { Router } from 'express';
import { authMiddleware } from '../middleware/auth';
import { documentUpload } from '../config/documentUpload';
import {
  uploadDocument,
  queryDocuments,
  getDocuments,
  deleteDocument,
  generateDocumentConceptGraph,
  getDocumentConceptGraph,
} from '../controllers/ragController';

const router = Router();

router.use(authMiddleware);

router.post('/upload', documentUpload.single('file'), uploadDocument);
router.post('/query', queryDocuments);
router.get('/documents', getDocuments);
router.post('/documents/:id/concepts', generateDocumentConceptGraph);
router.get('/documents/:id/concepts', getDocumentConceptGraph);
router.delete('/documents/:id', deleteDocument);

export default router;
