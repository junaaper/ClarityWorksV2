import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Search, Trash2, Eye, ChevronLeft, ChevronRight, FileText, AlertCircle
} from 'lucide-react';
import { analysisApi } from '../../services/api';
import type { AnalysisListItem, Pagination } from '../../types';
import SimplificationHistory from './SimplificationHistory';

const History: React.FC = () => {
  const [analyses, setAnalyses] = useState<AnalysisListItem[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [gradeFilter, setGradeFilter] = useState('');
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<'analyses' | 'simplifications'>('analyses');

  const fetchAnalyses = useCallback(async (page = 1) => {
    setIsLoading(true);
    try {
      const result = await analysisApi.getAnalyses({
        page,
        limit: 10,
        search: search || undefined,
        gradeLevel: gradeFilter || undefined,
      });
      setAnalyses(result.analyses);
      setPagination(result.pagination);
    } catch (error) {
      console.error('Error fetching analyses:', error);
    } finally {
      setIsLoading(false);
    }
  }, [search, gradeFilter]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      fetchAnalyses(1);
    }, 300);

    return () => clearTimeout(debounce);
  }, [fetchAnalyses]);

  const handleDelete = async (id: number) => {
    try {
      await analysisApi.deleteAnalysis(id);
      setAnalyses((prev) => prev.filter((a) => a.id !== id));
      setDeleteId(null);
    } catch (error) {
      console.error('Error deleting analysis:', error);
    }
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getFleschBadge = (score: number | string | null | undefined): string => {
    if (score == null) return 'cw-badge cw-badge-neutral';
    const numScore = typeof score === 'string' ? parseFloat(score) : score;
    if (isNaN(numScore)) return 'cw-badge cw-badge-neutral';
    if (numScore >= 70) return 'cw-badge cw-badge-ok';
    if (numScore >= 50) return 'cw-badge cw-badge-warn';
    return 'cw-badge cw-badge-err';
  };

  const formatScore = (score: number | string | null | undefined): string => {
    if (score == null) return 'N/A';
    const numScore = typeof score === 'string' ? parseFloat(score) : score;
    return isNaN(numScore) ? 'N/A' : numScore.toFixed(1);
  };

  const gradeOptions = [
    'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8',
    'Grade 9', 'Grade 10', 'Grade 11', 'Grade 12', 'College',
  ];

  const TabButton: React.FC<{ active: boolean; onClick: () => void; children: React.ReactNode }> = ({ active, onClick, children }) => (
    <button
      onClick={onClick}
      className="px-4 py-2 rounded-md text-[12.5px] transition-colors"
      style={{
        background: active ? 'var(--surface-raised)' : 'transparent',
        color: active ? 'var(--p-900)' : 'var(--text-2)',
        fontWeight: active ? 600 : 500,
        boxShadow: active ? 'var(--sh-1)' : 'none',
      }}
    >
      {children}
    </button>
  );

  return (
    <div>
      <div className="mb-8">
        <div className="cw-eyebrow mb-2">Workspace</div>
        <h1 className="cw-hero" style={{ fontSize: 28 }}>History</h1>
        <p className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
          Browse past analyses and rewrites.
        </p>
      </div>

      {/* Tabs */}
      <div
        className="inline-flex p-1 mb-6 rounded-md"
        style={{ background: 'var(--surface-sunk)', border: '1px solid var(--border)' }}
      >
        <TabButton active={activeTab === 'analyses'} onClick={() => setActiveTab('analyses')}>Analyses</TabButton>
        <TabButton active={activeTab === 'simplifications'} onClick={() => setActiveTab('simplifications')}>Rewrites</TabButton>
      </div>

      {activeTab === 'simplifications' ? (
        <SimplificationHistory />
      ) : (
        <>
          {/* Filters */}
          <div className="cw-card cw-card-pad mb-5">
            <div className="flex flex-col md:flex-row gap-3">
              <div className="flex-1 relative">
                <Search
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                  style={{ color: 'var(--text-4)' }}
                />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by title or content…"
                  className="cw-input"
                  style={{ paddingLeft: 36 }}
                />
              </div>
              <select
                value={gradeFilter}
                onChange={(e) => setGradeFilter(e.target.value)}
                className="cw-select"
                style={{ maxWidth: 200 }}
              >
                <option value="">All Grade Levels</option>
                {gradeOptions.map((grade) => (
                  <option key={grade} value={grade}>{grade}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Results */}
          {isLoading ? (
            <div className="flex items-center justify-center h-48">
              <div
                className="animate-spin rounded-full h-10 w-10 border-b-2"
                style={{ borderColor: 'var(--p-700)' }}
              />
            </div>
          ) : analyses.length === 0 ? (
            <div
              className="cw-card cw-card-pad-lg text-center"
              style={{ padding: '48px 24px' }}
            >
              <FileText className="w-10 h-10 mx-auto mb-3" style={{ color: 'var(--text-4)' }} />
              <p className="mb-4" style={{ color: 'var(--text-3)', fontSize: 13 }}>No analyses found</p>
              <Link to="/analyze" className="cw-btn cw-btn-primary cw-btn-sm inline-flex">
                Start your first analysis
              </Link>
            </div>
          ) : (
            <>
              <div className="cw-card overflow-hidden">
                <table className="cw-table">
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Date</th>
                      <th>Words</th>
                      <th>Flesch</th>
                      <th>Grade</th>
                      <th style={{ textAlign: 'right' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analyses.map((analysis) => (
                      <tr key={analysis.id}>
                        <td>
                          <Link
                            to={`/analysis/${analysis.id}`}
                            style={{ color: 'var(--text-1)', fontWeight: 600, fontSize: 12.5 }}
                            className="hover:underline"
                          >
                            {analysis.title || `Analysis #${analysis.id}`}
                          </Link>
                        </td>
                        <td style={{ color: 'var(--text-3)', fontSize: 11.5 }}>
                          {formatDate(analysis.created_at)}
                        </td>
                        <td style={{ color: 'var(--text-2)', fontFamily: 'var(--font-mono)' }}>
                          {analysis.word_count?.toLocaleString()}
                        </td>
                        <td>
                          <span className={getFleschBadge(analysis.flesch_reading_ease)}>
                            {formatScore(analysis.flesch_reading_ease != null ? Math.max(0, Math.min(100, Number(analysis.flesch_reading_ease))) : analysis.flesch_reading_ease)}
                          </span>
                        </td>
                        <td>
                          <span className="cw-badge cw-badge-primary">
                            {analysis.predicted_grade_level}
                          </span>
                        </td>
                        <td>
                          <div className="flex items-center justify-end gap-1">
                            <Link
                              to={`/analysis/${analysis.id}`}
                              className="p-1.5 rounded transition-colors"
                              style={{ color: 'var(--text-3)' }}
                              onMouseEnter={(e) => {
                                (e.currentTarget as HTMLAnchorElement).style.background = 'var(--p-50)';
                                (e.currentTarget as HTMLAnchorElement).style.color = 'var(--p-700)';
                              }}
                              onMouseLeave={(e) => {
                                (e.currentTarget as HTMLAnchorElement).style.background = 'transparent';
                                (e.currentTarget as HTMLAnchorElement).style.color = 'var(--text-3)';
                              }}
                              title="View"
                            >
                              <Eye className="w-4 h-4" />
                            </Link>
                            <button
                              onClick={() => setDeleteId(analysis.id)}
                              className="p-1.5 rounded transition-colors"
                              style={{ color: 'var(--text-3)' }}
                              onMouseEnter={(e) => {
                                (e.currentTarget as HTMLButtonElement).style.background = 'var(--err-50)';
                                (e.currentTarget as HTMLButtonElement).style.color = 'var(--err-500)';
                              }}
                              onMouseLeave={(e) => {
                                (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                                (e.currentTarget as HTMLButtonElement).style.color = 'var(--text-3)';
                              }}
                              title="Delete"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {pagination && pagination.totalPages > 1 && (
                <div className="flex items-center justify-between mt-5 flex-wrap gap-3">
                  <p style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
                    Showing {(pagination.page - 1) * pagination.limit + 1} to{' '}
                    {Math.min(pagination.page * pagination.limit, pagination.totalCount)} of{' '}
                    {pagination.totalCount} results
                  </p>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => fetchAnalyses(pagination.page - 1)}
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
                      onClick={() => fetchAnalyses(pagination.page + 1)}
                      disabled={pagination.page === pagination.totalPages}
                      className="cw-btn cw-btn-sm cw-btn-secondary"
                      style={{ padding: '0 8px' }}
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* Delete Confirmation Modal */}
      {deleteId && (
        <div
          className="fixed inset-0 flex items-center justify-center z-50"
          style={{ background: 'color-mix(in srgb, var(--ink-900) 55%, transparent)' }}
        >
          <div className="cw-card cw-card-pad-lg max-w-md w-full mx-4">
            <div className="flex items-center gap-3 mb-4">
              <div
                className="p-2 rounded-full"
                style={{ background: 'var(--err-50)' }}
              >
                <AlertCircle className="w-5 h-5" style={{ color: 'var(--err-500)' }} />
              </div>
              <h3 className="cw-section-title">Delete Analysis</h3>
            </div>
            <p style={{ color: 'var(--text-2)', fontSize: 13, marginBottom: 20, lineHeight: 1.55 }}>
              Are you sure you want to delete this analysis? This action cannot be undone.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteId(null)} className="cw-btn cw-btn-secondary">
                Cancel
              </button>
              <button onClick={() => handleDelete(deleteId)} className="cw-btn cw-btn-danger">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default History;
