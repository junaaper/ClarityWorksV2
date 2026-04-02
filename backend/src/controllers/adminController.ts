import { Response } from 'express';
import pool from '../config/database';
import { AuthRequest } from '../middleware/auth';

// Get all users with pagination and search
export const getUsers = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 10;
    const search = req.query.search as string || '';
    const role = req.query.role as string || '';
    const status = req.query.status as string || '';
    const offset = (page - 1) * limit;

    let whereClause = 'WHERE 1=1';
    const params: (string | number | boolean)[] = [];
    let paramIndex = 1;

    if (search) {
      whereClause += ` AND (email ILIKE $${paramIndex} OR full_name ILIKE $${paramIndex})`;
      params.push(`%${search}%`);
      paramIndex++;
    }

    if (role && role !== 'all') {
      whereClause += ` AND role = $${paramIndex}`;
      params.push(role);
      paramIndex++;
    }

    if (status && status !== 'all') {
      whereClause += ` AND is_active = $${paramIndex}`;
      params.push(status === 'active');
      paramIndex++;
    }

    // Get total count
    const countResult = await pool.query(
      `SELECT COUNT(*) FROM users ${whereClause}`,
      params
    );
    const totalCount = parseInt(countResult.rows[0].count);

    // Get users
    const result = await pool.query(
      `SELECT id, email, full_name, role, is_active, created_at
       FROM users
       ${whereClause}
       ORDER BY created_at DESC
       LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`,
      [...params, limit, offset]
    );

    // Get analysis count for each user
    const userIds = result.rows.map(u => u.id);
    let analysisCountMap: Record<number, number> = {};

    if (userIds.length > 0) {
      const analysisCountResult = await pool.query(
        `SELECT user_id, COUNT(*) as count
         FROM analyses
         WHERE user_id = ANY($1)
         GROUP BY user_id`,
        [userIds]
      );
      analysisCountMap = analysisCountResult.rows.reduce((acc, row) => {
        acc[row.user_id] = parseInt(row.count);
        return acc;
      }, {} as Record<number, number>);
    }

    const users = result.rows.map(user => ({
      id: user.id,
      email: user.email,
      fullName: user.full_name,
      role: user.role,
      isActive: user.is_active,
      createdAt: user.created_at,
      analysisCount: analysisCountMap[user.id] || 0,
    }));

    res.json({
      users,
      pagination: {
        page,
        limit,
        totalCount,
        totalPages: Math.ceil(totalCount / limit),
      },
    });
  } catch (error) {
    console.error('Get users error:', error);
    res.status(500).json({ error: 'Failed to fetch users' });
  }
};

// Get single user by ID
export const getUserById = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;

    const result = await pool.query(
      `SELECT id, email, full_name, role, is_active, created_at FROM users WHERE id = $1`,
      [id]
    );

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    const user = result.rows[0];

    // Get user's analysis stats
    const statsResult = await pool.query(
      `SELECT
        COUNT(*) as total_analyses,
        COALESCE(SUM(word_count), 0) as total_words,
        COALESCE(AVG(flesch_reading_ease), 0) as avg_reading_ease
       FROM analyses WHERE user_id = $1`,
      [id]
    );

    res.json({
      user: {
        id: user.id,
        email: user.email,
        fullName: user.full_name,
        role: user.role,
        isActive: user.is_active,
        createdAt: user.created_at,
      },
      stats: {
        totalAnalyses: parseInt(statsResult.rows[0].total_analyses),
        totalWords: parseInt(statsResult.rows[0].total_words),
        avgReadingEase: parseFloat(statsResult.rows[0].avg_reading_ease) || 0,
      },
    });
  } catch (error) {
    console.error('Get user error:', error);
    res.status(500).json({ error: 'Failed to fetch user' });
  }
};

// Update user role
export const updateUserRole = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;
    const { role } = req.body;

    if (!['user', 'admin'].includes(role)) {
      res.status(400).json({ error: 'Invalid role. Must be "user" or "admin"' });
      return;
    }

    // Prevent self-demotion
    if (parseInt(id) === req.userId && role !== 'admin') {
      res.status(400).json({ error: 'Cannot change your own role' });
      return;
    }

    const result = await pool.query(
      `UPDATE users SET role = $1 WHERE id = $2 RETURNING id, email, full_name, role, is_active, created_at`,
      [role, id]
    );

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    const user = result.rows[0];
    res.json({
      message: 'User role updated successfully',
      user: {
        id: user.id,
        email: user.email,
        fullName: user.full_name,
        role: user.role,
        isActive: user.is_active,
        createdAt: user.created_at,
      },
    });
  } catch (error) {
    console.error('Update user role error:', error);
    res.status(500).json({ error: 'Failed to update user role' });
  }
};

// Toggle user active status
export const toggleUserStatus = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;

    // Prevent self-deactivation
    if (parseInt(id) === req.userId) {
      res.status(400).json({ error: 'Cannot deactivate your own account' });
      return;
    }

    const result = await pool.query(
      `UPDATE users SET is_active = NOT is_active WHERE id = $1 RETURNING id, email, full_name, role, is_active, created_at`,
      [id]
    );

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    const user = result.rows[0];
    res.json({
      message: `User ${user.is_active ? 'activated' : 'deactivated'} successfully`,
      user: {
        id: user.id,
        email: user.email,
        fullName: user.full_name,
        role: user.role,
        isActive: user.is_active,
        createdAt: user.created_at,
      },
    });
  } catch (error) {
    console.error('Toggle user status error:', error);
    res.status(500).json({ error: 'Failed to toggle user status' });
  }
};

// Delete user
export const deleteUser = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;

    // Prevent self-deletion
    if (parseInt(id) === req.userId) {
      res.status(400).json({ error: 'Cannot delete your own account' });
      return;
    }

    const result = await pool.query(
      `DELETE FROM users WHERE id = $1 RETURNING id`,
      [id]
    );

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'User not found' });
      return;
    }

    res.json({ message: 'User deleted successfully' });
  } catch (error) {
    console.error('Delete user error:', error);
    res.status(500).json({ error: 'Failed to delete user' });
  }
};

// Get all analyses (admin view)
export const getAllAnalyses = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 10;
    const search = req.query.search as string || '';
    const userId = req.query.userId as string || '';
    const offset = (page - 1) * limit;

    let whereClause = 'WHERE 1=1';
    const params: (string | number)[] = [];
    let paramIndex = 1;

    if (search) {
      whereClause += ` AND (a.title ILIKE $${paramIndex} OR a.original_text ILIKE $${paramIndex})`;
      params.push(`%${search}%`);
      paramIndex++;
    }

    if (userId) {
      whereClause += ` AND a.user_id = $${paramIndex}`;
      params.push(parseInt(userId));
      paramIndex++;
    }

    // Get total count
    const countResult = await pool.query(
      `SELECT COUNT(*) FROM analyses a ${whereClause}`,
      params
    );
    const totalCount = parseInt(countResult.rows[0].count);

    // Get analyses with user info
    const result = await pool.query(
      `SELECT a.id, a.user_id, a.title, a.word_count, a.sentence_count,
              a.flesch_reading_ease, a.predicted_grade_level, a.predicted_complexity,
              a.created_at, u.email as user_email, u.full_name as user_name
       FROM analyses a
       JOIN users u ON a.user_id = u.id
       ${whereClause}
       ORDER BY a.created_at DESC
       LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`,
      [...params, limit, offset]
    );

    const analyses = result.rows.map(row => ({
      id: row.id,
      userId: row.user_id,
      userEmail: row.user_email,
      userName: row.user_name,
      title: row.title,
      wordCount: row.word_count,
      sentenceCount: row.sentence_count,
      fleschReadingEase: parseFloat(row.flesch_reading_ease),
      predictedGradeLevel: row.predicted_grade_level,
      predictedComplexity: row.predicted_complexity,
      createdAt: row.created_at,
    }));

    res.json({
      analyses,
      pagination: {
        page,
        limit,
        totalCount,
        totalPages: Math.ceil(totalCount / limit),
      },
    });
  } catch (error) {
    console.error('Get all analyses error:', error);
    res.status(500).json({ error: 'Failed to fetch analyses' });
  }
};

// Delete analysis (admin)
export const deleteAnalysis = async (req: AuthRequest, res: Response): Promise<void> => {
  try {
    const { id } = req.params;

    const result = await pool.query(
      `DELETE FROM analyses WHERE id = $1 RETURNING id`,
      [id]
    );

    if (result.rows.length === 0) {
      res.status(404).json({ error: 'Analysis not found' });
      return;
    }

    res.json({ message: 'Analysis deleted successfully' });
  } catch (error) {
    console.error('Delete analysis error:', error);
    res.status(500).json({ error: 'Failed to delete analysis' });
  }
};

// Get admin dashboard statistics
export const getAdminStats = async (_req: AuthRequest, res: Response): Promise<void> => {
  try {
    // Get user statistics
    const userStats = await pool.query(`
      SELECT
        COUNT(*) as total_users,
        COUNT(CASE WHEN role = 'admin' THEN 1 END) as admin_count,
        COUNT(CASE WHEN is_active = true THEN 1 END) as active_users,
        COUNT(CASE WHEN is_active = false THEN 1 END) as inactive_users,
        COUNT(CASE WHEN created_at > NOW() - INTERVAL '7 days' THEN 1 END) as new_users_week,
        COUNT(CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 1 END) as new_users_month
      FROM users
    `);

    // Get analysis statistics
    const analysisStats = await pool.query(`
      SELECT
        COUNT(*) as total_analyses,
        COALESCE(SUM(word_count), 0) as total_words,
        COALESCE(AVG(flesch_reading_ease), 0) as avg_reading_ease,
        COALESCE(AVG(flesch_kincaid_grade), 0) as avg_grade_level,
        COUNT(CASE WHEN created_at > NOW() - INTERVAL '7 days' THEN 1 END) as analyses_week,
        COUNT(CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 1 END) as analyses_month
      FROM analyses
    `);

    // Get grade level distribution
    const gradeDistribution = await pool.query(`
      SELECT predicted_grade_level, COUNT(*) as count
      FROM analyses
      WHERE predicted_grade_level IS NOT NULL
      GROUP BY predicted_grade_level
      ORDER BY count DESC
    `);

    // Get recent activity (last 10 analyses)
    const recentActivity = await pool.query(`
      SELECT a.id, a.title, a.created_at, u.full_name as user_name, u.email as user_email
      FROM analyses a
      JOIN users u ON a.user_id = u.id
      ORDER BY a.created_at DESC
      LIMIT 10
    `);

    // Get top users by analysis count
    const topUsers = await pool.query(`
      SELECT u.id, u.full_name, u.email, COUNT(a.id) as analysis_count
      FROM users u
      LEFT JOIN analyses a ON u.id = a.user_id
      GROUP BY u.id, u.full_name, u.email
      ORDER BY analysis_count DESC
      LIMIT 5
    `);

    res.json({
      users: {
        total: parseInt(userStats.rows[0].total_users),
        admins: parseInt(userStats.rows[0].admin_count),
        active: parseInt(userStats.rows[0].active_users),
        inactive: parseInt(userStats.rows[0].inactive_users),
        newThisWeek: parseInt(userStats.rows[0].new_users_week),
        newThisMonth: parseInt(userStats.rows[0].new_users_month),
      },
      analyses: {
        total: parseInt(analysisStats.rows[0].total_analyses),
        totalWords: parseInt(analysisStats.rows[0].total_words),
        avgReadingEase: parseFloat(analysisStats.rows[0].avg_reading_ease) || 0,
        avgGradeLevel: parseFloat(analysisStats.rows[0].avg_grade_level) || 0,
        thisWeek: parseInt(analysisStats.rows[0].analyses_week),
        thisMonth: parseInt(analysisStats.rows[0].analyses_month),
      },
      gradeDistribution: gradeDistribution.rows.map(row => ({
        gradeLevel: row.predicted_grade_level,
        count: parseInt(row.count),
      })),
      recentActivity: recentActivity.rows.map(row => ({
        id: row.id,
        title: row.title,
        createdAt: row.created_at,
        userName: row.user_name,
        userEmail: row.user_email,
      })),
      topUsers: topUsers.rows.map(row => ({
        id: row.id,
        fullName: row.full_name,
        email: row.email,
        analysisCount: parseInt(row.analysis_count),
      })),
    });
  } catch (error) {
    console.error('Get admin stats error:', error);
    res.status(500).json({ error: 'Failed to fetch admin statistics' });
  }
};
