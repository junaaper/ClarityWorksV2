import axios from 'axios';
import type { AuthResponse, AnalysisResponse, SavedAnalysis, AnalysisListItem, Pagination, StatsResponse, AdminUser, AdminAnalysis, AdminStats } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Only redirect to login for 401 errors on protected routes (not login/register attempts)
    const isAuthRoute = error.config?.url?.includes('/api/auth/login') ||
                        error.config?.url?.includes('/api/auth/register');

    if (error.response?.status === 401 && !isAuthRoute) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  register: async (email: string, password: string, fullName: string): Promise<AuthResponse> => {
    const response = await api.post('/api/auth/register', { email, password, fullName });
    return response.data;
  },

  login: async (email: string, password: string): Promise<AuthResponse> => {
    const response = await api.post('/api/auth/login', { email, password });
    return response.data;
  },

  getMe: async (): Promise<{ user: AuthResponse['user'] }> => {
    const response = await api.get('/api/auth/me');
    return response.data;
  },

  logout: async (): Promise<void> => {
    await api.post('/api/auth/logout');
  },

  updateProfile: async (fullName: string, email: string): Promise<{ message: string; user: AuthResponse['user'] }> => {
    const response = await api.put('/api/auth/profile', { fullName, email });
    return response.data;
  },

  updatePassword: async (currentPassword: string, newPassword: string): Promise<{ message: string }> => {
    const response = await api.put('/api/auth/password', { currentPassword, newPassword });
    return response.data;
  },

  uploadProfilePicture: async (file: File): Promise<{ message: string; user: AuthResponse['user'] }> => {
    const formData = new FormData();
    formData.append('profilePicture', file);
    const response = await api.post('/api/auth/profile-picture', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  deleteProfilePicture: async (): Promise<{ message: string; user: AuthResponse['user'] }> => {
    const response = await api.delete('/api/auth/profile-picture');
    return response.data;
  },
};

// Analysis API
export const analysisApi = {
  analyze: async (text: string, title?: string): Promise<AnalysisResponse> => {
    const response = await api.post('/api/analyses', { text, title });
    return response.data;
  },

  getAnalyses: async (params: {
    page?: number;
    limit?: number;
    search?: string;
    gradeLevel?: string;
  }): Promise<{ analyses: AnalysisListItem[]; pagination: Pagination }> => {
    const response = await api.get('/api/analyses', { params });
    return response.data;
  },

  getAnalysis: async (id: number): Promise<SavedAnalysis> => {
    const response = await api.get(`/api/analyses/${id}`);
    return response.data;
  },

  deleteAnalysis: async (id: number): Promise<void> => {
    await api.delete(`/api/analyses/${id}`);
  },

  getStats: async (): Promise<StatsResponse> => {
    const response = await api.get('/api/analyses/stats');
    return response.data;
  },
};

// Text extraction API
export const textApi = {
  extractPdf: async (file: File): Promise<{ text: string; pageCount: number }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/text/extract-pdf', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  extractDoc: async (file: File): Promise<{ text: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/text/extract-doc', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  extractImage: async (file: File): Promise<{ text: string; confidence: number }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/text/extract-image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
};

// Simplification API
export const simplifyApi = {
  analyze: async (data: { analysisId?: number; targetGrade: number; text?: string }): Promise<{
    original_text: string;
    suggested_changes: any[];
    preview_text: string;
  }> => {
    const response = await api.post('/api/simplify/analyze', data);
    return response.data;
  },

  apply: async (data: { text: string; acceptedChanges: number[]; allChanges: any[] }): Promise<{ simplified_text: string }> => {
    const response = await api.post('/api/simplify/apply', data);
    return response.data;
  },

  save: async (data: {
    analysisId: number;
    simplifiedText: string;
    targetGrade: number;
    changes: any[];
    mode: 'auto' | 'interactive';
  }): Promise<any> => {
    const response = await api.post('/api/simplify/save', data);
    return response.data;
  },
};

// RAG API
export const ragApi = {
  uploadDocument: async (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/rag/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    });
    return response.data;
  },

  queryDocuments: async (query: string, documentIds?: string[]): Promise<{
    query: string;
    answer?: string | null;
    sources?: any[];
    has_answer?: boolean;
    results_count: number;
    results: any[];
  }> => {
    const response = await api.post('/api/rag/query', { query, documentIds });
    return response.data;
  },

  getDocuments: async (): Promise<any[]> => {
    const response = await api.get('/api/rag/documents');
    return response.data;
  },

  deleteDocument: async (id: number): Promise<void> => {
    await api.delete(`/api/rag/documents/${id}`);
  },
};

// Admin API
export const adminApi = {
  // Dashboard stats
  getStats: async (): Promise<AdminStats> => {
    const response = await api.get('/api/admin/stats');
    return response.data;
  },

  // User management
  getUsers: async (params: {
    page?: number;
    limit?: number;
    search?: string;
    role?: string;
    status?: string;
  }): Promise<{ users: AdminUser[]; pagination: Pagination }> => {
    const response = await api.get('/api/admin/users', { params });
    return response.data;
  },

  getUser: async (id: number): Promise<{ user: AdminUser; stats: { totalAnalyses: number; totalWords: number; avgReadingEase: number } }> => {
    const response = await api.get(`/api/admin/users/${id}`);
    return response.data;
  },

  updateUserRole: async (id: number, role: 'user' | 'admin'): Promise<{ message: string; user: AdminUser }> => {
    const response = await api.patch(`/api/admin/users/${id}/role`, { role });
    return response.data;
  },

  toggleUserStatus: async (id: number): Promise<{ message: string; user: AdminUser }> => {
    const response = await api.patch(`/api/admin/users/${id}/status`);
    return response.data;
  },

  deleteUser: async (id: number): Promise<{ message: string }> => {
    const response = await api.delete(`/api/admin/users/${id}`);
    return response.data;
  },

  // Analysis management
  getAnalyses: async (params: {
    page?: number;
    limit?: number;
    search?: string;
    userId?: number;
  }): Promise<{ analyses: AdminAnalysis[]; pagination: Pagination }> => {
    const response = await api.get('/api/admin/analyses', { params });
    return response.data;
  },

  deleteAnalysis: async (id: number): Promise<{ message: string }> => {
    const response = await api.delete(`/api/admin/analyses/${id}`);
    return response.data;
  },
};

export default api;
