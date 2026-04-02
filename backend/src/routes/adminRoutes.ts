import { Router } from 'express';
import { authMiddleware, adminMiddleware } from '../middleware/auth';
import {
  getUsers,
  getUserById,
  updateUserRole,
  toggleUserStatus,
  deleteUser,
  getAllAnalyses,
  deleteAnalysis,
  getAdminStats,
} from '../controllers/adminController';

const router = Router();

// All admin routes require authentication and admin role
router.use(authMiddleware);
router.use(adminMiddleware);

// Dashboard statistics
router.get('/stats', getAdminStats);

// User management
router.get('/users', getUsers);
router.get('/users/:id', getUserById);
router.patch('/users/:id/role', updateUserRole);
router.patch('/users/:id/status', toggleUserStatus);
router.delete('/users/:id', deleteUser);

// Analysis management
router.get('/analyses', getAllAnalyses);
router.delete('/analyses/:id', deleteAnalysis);

export default router;
