import { Router } from 'express';
import { extractPdf, extractDoc, extractImage, upload } from '../controllers/textController';
import { authMiddleware } from '../middleware/auth';

const router = Router();

router.use(authMiddleware);

router.post('/extract-pdf', upload.single('file'), extractPdf);
router.post('/extract-doc', upload.single('file'), extractDoc);
router.post('/extract-image', upload.single('file'), extractImage);

export default router;
