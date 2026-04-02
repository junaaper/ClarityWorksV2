import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PlusCircle, Clock, BarChart3, FileText, TrendingUp, BookOpen } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { analysisApi } from '../../services/api';
import type { StatsResponse, AnalysisListItem } from '../../types';
import { useAuth } from '../../utils/auth';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [trendData, setTrendData] = useState<{ date: string; grade: number; flesch: number }[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, historyData] = await Promise.all([
          analysisApi.getStats(),
          analysisApi.getAnalyses({ limit: 20 }),
        ]);
        setStats(statsData);

        // Build trend data from history (oldest first)
        const trend = historyData.analyses
          .slice()
          .reverse()
          .map((a: AnalysisListItem) => {
            const gradeStr = a.predicted_grade_level.replace('Grade ', '');
            const grade = gradeStr === 'College' ? 13 : parseInt(gradeStr) || 0;
            return {
              date: new Date(a.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
              grade,
              flesch: Math.round(a.flesch_reading_ease),
            };
          });
        setTrendData(trend);
      } catch (error) {
        console.error('Error fetching stats:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  const getReadabilityLabel = (score: number): string => {
    if (score >= 70) return 'Easy to read';
    if (score >= 50) return 'Moderate';
    return 'Difficult';
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800">
          Welcome back, {user?.fullName?.split(' ')[0]}!
        </h1>
        <p className="text-gray-600 mt-2">
          Analyze text readability and improve your writing
        </p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <Link
          to="/analyze"
          className="bg-gradient-to-r from-primary-500 to-primary-600 text-white rounded-xl p-6 hover:from-primary-600 hover:to-primary-700 transition-all shadow-lg group"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-white/20 rounded-lg group-hover:scale-110 transition-transform">
              <PlusCircle className="w-8 h-8" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">Start New Analysis</h2>
              <p className="text-white/80 mt-1">
                Analyze text from various sources
              </p>
            </div>
          </div>
        </Link>

        <Link
          to="/history"
          className="bg-white rounded-xl p-6 hover:shadow-lg transition-all border border-gray-200 group"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-primary-50 rounded-lg group-hover:scale-110 transition-transform">
              <Clock className="w-8 h-8 text-primary-600" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-800">View History</h2>
              <p className="text-gray-600 mt-1">
                Access your past analyses
              </p>
            </div>
          </div>
        </Link>
      </div>

      {/* Statistics Overview */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
        <h2 className="text-xl font-semibold text-gray-800 mb-6 flex items-center gap-2">
          <BarChart3 className="w-6 h-6 text-primary-600" />
          Statistics Overview
        </h2>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-3xl font-bold text-primary-600">
              {stats?.stats.totalAnalyses || 0}
            </div>
            <div className="text-sm text-gray-600 mt-1">Total Analyses</div>
          </div>

          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-3xl font-bold text-green-600">
              {stats?.stats.avgReadingEase?.toFixed(1) || '0'}
            </div>
            <div className="text-sm text-gray-600 mt-1">
              Avg. Flesch Score
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {getReadabilityLabel(stats?.stats.avgReadingEase || 0)}
            </div>
          </div>

          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-3xl font-bold text-blue-600">
              {stats?.stats.avgGradeLevel?.toFixed(1) || '0'}
            </div>
            <div className="text-sm text-gray-600 mt-1">Avg. Grade Level</div>
          </div>

          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-3xl font-bold text-purple-600">
              {(stats?.stats.totalWordsAnalyzed || 0).toLocaleString()}
            </div>
            <div className="text-sm text-gray-600 mt-1">Words Analyzed</div>
          </div>
        </div>
      </div>

      {/* Readability Trend Chart */}
      {trendData.length >= 2 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6 flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-primary-600" />
            Readability Trend
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis yAxisId="grade" domain={[0, 14]} label={{ value: 'Grade', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }} />
              <YAxis yAxisId="flesch" orientation="right" domain={[0, 100]} label={{ value: 'Flesch', angle: 90, position: 'insideRight', style: { fontSize: 12 } }} />
              <Tooltip />
              <Legend />
              <Line yAxisId="grade" type="monotone" dataKey="grade" stroke="#3b82f6" strokeWidth={2} name="Grade Level" dot={{ r: 4 }} />
              <Line yAxisId="flesch" type="monotone" dataKey="flesch" stroke="#10b981" strokeWidth={2} name="Flesch Score" dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Recent Analyses */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-6 flex items-center gap-2">
          <TrendingUp className="w-6 h-6 text-primary-600" />
          Recent Analyses
        </h2>

        {stats?.recentAnalyses && stats.recentAnalyses.length > 0 ? (
          <div className="space-y-4">
            {stats.recentAnalyses.map((analysis) => (
              <Link
                key={analysis.id}
                to={`/analysis/${analysis.id}`}
                className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-white rounded-lg">
                    <FileText className="w-5 h-5 text-gray-600" />
                  </div>
                  <div>
                    <h3 className="font-medium text-gray-800">{analysis.title}</h3>
                    <p className="text-sm text-gray-500">
                      {formatDate(analysis.created_at)}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <span className="inline-block px-3 py-1 bg-primary-100 text-primary-700 text-sm font-medium rounded-full">
                    {analysis.predicted_grade_level}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No analyses yet</p>
            <Link
              to="/analyze"
              className="text-primary-600 hover:underline font-medium mt-2 inline-block"
            >
              Start your first analysis
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
