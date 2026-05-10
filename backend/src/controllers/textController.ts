import { Request, Response } from 'express';
import axios from 'axios';
import multer from 'multer';
import path from 'path';
import fs from 'fs';

const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:5001';

// Configure multer for file uploads
const storage = multer.diskStorage({
  destination: (_req, _file, cb) => {
    const uploadDir = path.join(__dirname, '../../uploads');
    if (!fs.existsSync(uploadDir)) {
      fs.mkdirSync(uploadDir, { recursive: true });
    }
    cb(null, uploadDir);
  },
  filename: (_req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
    cb(null, uniqueSuffix + path.extname(file.originalname));
  },
});

const fileFilter = (_req: Request, file: Express.Multer.File, cb: multer.FileFilterCallback) => {
  const allowedMimes = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/jpeg',
    'image/png',
    'image/jpg',
  ];

  if (allowedMimes.includes(file.mimetype)) {
    cb(null, true);
  } else {
    cb(new Error('Invalid file type'));
  }
};

export const upload = multer({
  storage,
  fileFilter,
  limits: {
    fileSize: 10 * 1024 * 1024, // 10MB max
  },
});

export const extractPdf = async (req: Request, res: Response): Promise<void> => {
  try {
    if (!req.file) {
      res.status(400).json({ error: 'No file uploaded' });
      return;
    }

    const filePath = req.file.path;

    // Send to Python service for extraction
    const formData = new FormData();
    const fileBuffer = fs.readFileSync(filePath);
    const blob = new Blob([fileBuffer], { type: 'application/pdf' });
    formData.append('file', blob, req.file.originalname);

    const response = await axios.post(`${PYTHON_SERVICE_URL}/extract-pdf`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    // Clean up uploaded file
    fs.unlinkSync(filePath);

    res.json({
      success: true,
      text: response.data.text,
      pageCount: response.data.page_count,
      quality: response.data.quality,
      warnings: response.data.warnings || [],
    });
  } catch (error) {
    console.error('PDF extraction error:', error);
    if (req.file) {
      try {
        fs.unlinkSync(req.file.path);
      } catch {}
    }
    res.status(500).json({ error: 'Error extracting text from PDF' });
  }
};

export const extractDoc = async (req: Request, res: Response): Promise<void> => {
  try {
    if (!req.file) {
      res.status(400).json({ error: 'No file uploaded' });
      return;
    }

    const filePath = req.file.path;

    // Send to Python service for extraction
    const formData = new FormData();
    const fileBuffer = fs.readFileSync(filePath);
    const blob = new Blob([fileBuffer], { type: req.file.mimetype });
    formData.append('file', blob, req.file.originalname);

    const response = await axios.post(`${PYTHON_SERVICE_URL}/extract-doc`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    // Clean up uploaded file
    fs.unlinkSync(filePath);

    res.json({
      success: true,
      text: response.data.text,
    });
  } catch (error) {
    console.error('DOC extraction error:', error);
    if (req.file) {
      try {
        fs.unlinkSync(req.file.path);
      } catch {}
    }
    res.status(500).json({ error: 'Error extracting text from document' });
  }
};

export const extractImage = async (req: Request, res: Response): Promise<void> => {
  try {
    if (!req.file) {
      res.status(400).json({ error: 'No file uploaded' });
      return;
    }

    const filePath = req.file.path;

    // Send to Python service for OCR
    const formData = new FormData();
    const fileBuffer = fs.readFileSync(filePath);
    const blob = new Blob([fileBuffer], { type: req.file.mimetype });
    formData.append('file', blob, req.file.originalname);

    const response = await axios.post(`${PYTHON_SERVICE_URL}/extract-image`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    // Clean up uploaded file
    fs.unlinkSync(filePath);

    res.json({
      success: true,
      text: response.data.text,
      confidence: response.data.confidence,
    });
  } catch (error) {
    console.error('Image extraction error:', error);
    if (req.file) {
      try {
        fs.unlinkSync(req.file.path);
      } catch {}
    }
    res.status(500).json({ error: 'Error extracting text from image' });
  }
};
