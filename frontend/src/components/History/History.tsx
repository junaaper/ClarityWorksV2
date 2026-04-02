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

  const getReadabilityColor = (score: number | string | null | undefined): string => {
    if (score == null) return 'text-gray-600 bg-gray-50';
    const numScore = typeof score === 'string' ? parseFloat(score) : score;
    if (isNaN(numScore)) return 'text-gray-600 bg-gray-50';
    if (numScore >= 70) return 'text-green-600 bg-green-50';
    if (numScore >= 50) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const formatScore = (score: number | string | null | undefined): string => {
    if (score == null) return 'N/A';
    const numScore = typeof score === 'string' ? parseFloat(score) : score;
    return isNaN(numScore) ? 'N/A' : numScore.toFixed(1);
  };

  const gradeOptions = [
    'Grade 3', 'Grade 4', 'Grade 5', 'Grade 6', 'Grade 7', 'Grade 8',
    'Grade 9', 'Grade 10', 'Grade 11', 'Grade 12', 'College'
  ];

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800">History</h1>
        <p className="text-gray-600 mt-2">
          View and manage your past analyses and simplifications
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab('analyses')}
          className={`px-6 py-2 rounded-lg font-medium transition-colors ${
            activeTab === 'analyses'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          Analyses
        </button>
        <button
          onClick={() => setActiveTab('simplifications')}
          className={`px-6 py-2 rounded-lg font-medium transition-colors ${
            activeTab === 'simplifications'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          Simplifications
        </button>
      </div>

      {activeTab === 'simplifications' ? (
        <SimplificationHistory />
      ) : (
      <>
      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by title or content..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
            />
          </div>
          <select
            value={gradeFilter}
            onChange={(e) => setGradeFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
          >
            <option value="">All Grade Levels</option>
            {gradeOptions.map((grade) => (
              <option key={grade} value={grade}>
                {grade}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      ) : analyses.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-4">No analyses found</p>
          <Link
            to="/analyze"
            className="text-primary-600 hover:underline font-medium"
          >
            Start your first analysis
          </Link>
        </div>
      ) : (
        <>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left py-4 px-6 font-medium text-gray-600">
                    Title
                  </th>
                  <th className="text-left py-4 px-6 font-medium text-gray-600">
                    Date
                  </th>
                  <th className="text-left py-4 px-6 font-medium text-gray-600">
                    Words
                  </th>
                  <th className="text-left py-4 px-6 font-medium text-gray-600">
                    Flesch Score
                  </th>
                  <th className="text-left py-4 px-6 font-medium text-gray-600">
                    Grade Level
                  </th>
                  <th className="text-right py-4 px-6 font-medium text-gray-600">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {analyses.map((analysis) => (
                  <tr
                    key={analysis.id}
                    className="border-b last:border-b-0 hover:bg-gray-50"
                  >
                    <td className="py-4 px-6">
                      <Link
                        to={`/analysis/${analysis.id}`}
                        className="text-gray-800 hover:text-primary-600 font-medium"
                      >
                        {analysis.title || `Analysis #${analysis.id}`}
                      </Link>
                    </td>
                    <td className="py-4 px-6 text-gray-600 text-sm">
                      {formatDate(analysis.created_at)}
                    </td>
                    <td className="py-4 px-6 text-gray-600">
                      {analysis.word_count?.toLocaleString()}
                    </td>
                    <td className="py-4 px-6">
                      <span
                        className={`inline-block px-2 py-1 rounded text-sm font-medium ${getReadabilityColor(
                          analysis.flesch_reading_ease
                        )}`}
                      >
                        {formatScore(analysis.flesch_reading_ease)}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      <span className="inline-block px-2 py-1 bg-primary-50 text-primary-700 rounded text-sm font-medium">
                        {analysis.predicted_grade_level}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/analysis/${analysis.id}`}
                          className="p-2 text-gray-600 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                          title="View"
                        >
                          <Eye className="w-5 h-5" />
                        </Link>
                        <button
                          onClick={() => setDeleteId(analysis.id)}
                          className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-5 h-5" />
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
            <div className="flex items-center justify-between mt-6">
              <p className="text-sm text-gray-600">
                Showing {(pagination.page - 1) * pagination.limit + 1} to{' '}
                {Math.min(pagination.page * pagination.limit, pagination.totalCount)} of{' '}
                {pagination.totalCount} results
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => fetchAnalyses(pagination.page - 1)}
                  disabled={pagination.page === 1}
                  className="p-2 border rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <span className="px-4 py-2 text-sm">
                  Page {pagination.page} of {pagination.totalPages}
                </span>
                <button
                  onClick={() => fetchAnalyses(pagination.page + 1)}
                  disabled={pagination.page === pagination.totalPages}
                  className="p-2 border rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronRight className="w-5 h-5" />
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
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-100 rounded-full">
                <AlertCircle className="w-6 h-6 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-800">
                Delete Analysis
              </h3>
            </div>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete this analysis? This action cannot
              be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteId(null)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteId)}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
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
