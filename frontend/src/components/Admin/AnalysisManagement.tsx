import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Search, Trash2, AlertCircle, ChevronLeft, ChevronRight, Eye
} from 'lucide-react';
import { adminApi } from '../../services/api';
import type { AdminAnalysis, Pagination } from '../../types';

const AnalysisManagement: React.FC = () => {
  const [analyses, setAnalyses] = useState<AdminAnalysis[]>([]);
  const [pagination, setPagination] = useState<Pagination>({ page: 1, limit: 10, totalCount: 0, totalPages: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const fetchAnalyses = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await adminApi.getAnalyses({
        page: pagination.page,
        limit: pagination.limit,
        search,
      });
      setAnalyses(data.analyses);
      setPagination(data.pagination);
    } catch (err) {
      setError('Failed to load analyses');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [pagination.page, pagination.limit, search]);

  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      fetchAnalyses();
    }, 300);
    return () => clearTimeout(debounceTimer);
  }, [fetchAnalyses]);

  const handleDelete = async (analysisId: number) => {
    try {
      setActionLoading(analysisId);
      await adminApi.deleteAnalysis(analysisId);
      setAnalyses(analyses.filter(a => a.id !== analysisId));
      setDeleteConfirm(null);
    } catch (err) {
      console.error(err);
      alert('Failed to delete analysis');
    } finally {
      setActionLoading(null);
    }
  };

  const getComplexityBadge = (complexity: string): string => {
    switch (complexity) {
      case 'Elementary':
      case 'Beginner':
        return 'cw-badge cw-badge-ok';
      case 'Intermediate':
        return 'cw-badge cw-badge-warn';
      case 'Advanced':
        return 'cw-badge cw-badge-primary';
      case 'Expert':
        return 'cw-badge cw-badge-err';
      default:
        return 'cw-badge cw-badge-neutral';
    }
  };

  const iconBtnStyle = (hoverBg: string, hoverColor: string) => ({
    onMouseEnter: (e: React.MouseEvent<HTMLElement>) => {
      e.currentTarget.style.background = hoverBg;
      e.currentTarget.style.color = hoverColor;
    },
    onMouseLeave: (e: React.MouseEvent<HTMLElement>) => {
      e.currentTarget.style.background = 'transparent';
      e.currentTarget.style.color = 'var(--text-3)';
    },
  });

  return (
    <div>
      <div className="mb-8">
        <div className="cw-eyebrow mb-2">Administration</div>
        <h1 className="cw-hero" style={{ fontSize: 28 }}>Analysis Management</h1>
        <p className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
          View and manage all text analyses across the platform.
        </p>
      </div>

      {/* Search */}
      <div className="cw-card cw-card-pad mb-5">
        <div className="relative max-w-md">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
            style={{ color: 'var(--text-4)' }}
          />
          <input
            type="text"
            placeholder="Search by title or content…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPagination(p => ({ ...p, page: 1 }));
            }}
            className="cw-input"
            style={{ paddingLeft: 36 }}
          />
        </div>
      </div>

      {error && (
        <div
          className="mb-4 rounded-md flex items-center gap-2"
          style={{
            padding: '10px 14px',
            background: 'var(--err-50)',
            border: '1px solid color-mix(in srgb, var(--err-500) 22%, transparent)',
            color: 'var(--err-700)',
            fontSize: 12.5,
          }}
        >
          <AlertCircle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}

      {/* Analyses Table */}
      <div className="cw-card overflow-hidden">
        <div className="cw-scroll-x">
          <table className="cw-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>User</th>
                <th>Grade</th>
                <th>Complexity</th>
                <th>Words</th>
                <th>Flesch</th>
                <th>Created</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="text-center py-12">
                    <div
                      className="animate-spin rounded-full h-8 w-8 border-b-2 mx-auto"
                      style={{ borderColor: 'var(--p-700)' }}
                    />
                  </td>
                </tr>
              ) : analyses.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12" style={{ color: 'var(--text-4)', fontSize: 12.5 }}>
                    No analyses found
                  </td>
                </tr>
              ) : (
                analyses.map((analysis) => (
                  <tr key={analysis.id}>
                    <td style={{ maxWidth: 260 }}>
                      <div className="truncate" style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-1)' }}>
                        {analysis.title || 'Untitled'}
                      </div>
                    </td>
                    <td>
                      <p style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-1)' }}>
                        {analysis.userName}
                      </p>
                      <p style={{ fontSize: 11, color: 'var(--text-3)' }}>{analysis.userEmail}</p>
                    </td>
                    <td>
                      <span className="cw-badge cw-badge-primary">
                        {analysis.predictedGradeLevel}
                      </span>
                    </td>
                    <td>
                      <span className={getComplexityBadge(analysis.predictedComplexity)}>
                        {analysis.predictedComplexity}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                      {analysis.wordCount?.toLocaleString()}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                      {analysis.fleschReadingEase?.toFixed(1)}
                    </td>
                    <td style={{ color: 'var(--text-3)', fontSize: 11.5 }}>
                      {new Date(analysis.createdAt).toLocaleDateString()}
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        <Link
                          to={`/analysis/${analysis.id}`}
                          className="p-1.5 rounded transition-colors"
                          style={{ color: 'var(--text-3)' }}
                          {...iconBtnStyle('var(--p-50)', 'var(--p-700)')}
                          title="View analysis"
                        >
                          <Eye className="w-4 h-4" />
                        </Link>
                        <button
                          onClick={() => setDeleteConfirm(analysis.id)}
                          disabled={actionLoading === analysis.id}
                          className="p-1.5 rounded transition-colors"
                          style={{ color: 'var(--text-3)' }}
                          {...iconBtnStyle('var(--err-50)', 'var(--err-500)')}
                          title="Delete analysis"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pagination.totalPages > 1 && (
          <div
            className="flex items-center justify-between px-5 py-3"
            style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-sunk)' }}
          >
            <p style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
              Showing {(pagination.page - 1) * pagination.limit + 1} to {Math.min(pagination.page * pagination.limit, pagination.totalCount)} of {pagination.totalCount} analyses
            </p>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setPagination(p => ({ ...p, page: p.page - 1 }))}
                disabled={pagination.page === 1}
                className="cw-btn cw-btn-sm cw-btn-secondary"
                style={{ padding: '0 8px' }}
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span
                className="px-3"
                style={{ fontSize: 11.5, color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}
              >
                {pagination.page} / {pagination.totalPages}
              </span>
              <button
                onClick={() => setPagination(p => ({ ...p, page: p.page + 1 }))}
                disabled={pagination.page === pagination.totalPages}
                className="cw-btn cw-btn-sm cw-btn-secondary"
                style={{ padding: '0 8px' }}
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div
          className="fixed inset-0 flex items-center justify-center z-50"
          style={{ background: 'color-mix(in srgb, var(--ink-900) 55%, transparent)' }}
        >
          <div className="cw-card cw-card-pad-lg max-w-md w-full mx-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-full" style={{ background: 'var(--err-50)' }}>
                <AlertCircle className="w-5 h-5" style={{ color: 'var(--err-500)' }} />
              </div>
              <h3 className="cw-section-title">Delete Analysis</h3>
            </div>
            <p style={{ color: 'var(--text-2)', fontSize: 13, marginBottom: 20, lineHeight: 1.55 }}>
              Are you sure you want to delete this analysis? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setDeleteConfirm(null)} className="cw-btn cw-btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                disabled={actionLoading === deleteConfirm}
                className="cw-btn cw-btn-danger"
              >
                {actionLoading === deleteConfirm ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisManagement;
