import { Router } from 'express';
import { register, login, getMe, logout, updateProfile, updatePassword, uploadProfilePicture, deleteProfilePicture } from '../controllers/authController';
import { authMiddleware } from '../middleware/auth';
import { uploadProfilePicture as upload } from '../config/upload';

const router = Router();

router.post('/register', register);
router.post('/login', login);
router.get('/me', authMiddleware, getMe);
router.post('/logout', logout);
router.put('/profile', authMiddleware, updateProfile);
router.put('/password', authMiddleware, updatePassword);
router.post('/profile-picture', authMiddleware, upload.single('profilePicture'), uploadProfilePicture);
router.delete('/profile-picture', authMiddleware, deleteProfilePicture);

export default router;
