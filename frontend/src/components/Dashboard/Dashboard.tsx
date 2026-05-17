import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  PlusCircle, BookOpen, ArrowRight, TrendingUp, ArrowUpRight,
  FileText, Hash, Gauge, BarChart3,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
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

        const trend = historyData.analyses
          .slice()
          .reverse()
          .map((a: AnalysisListItem) => {
            const gradeStr = a.predicted_grade_level.replace('Grade ', '');
            const grade = gradeStr === 'College' ? 13 : parseInt(gradeStr) || 0;
            return {
              date: new Date(a.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
              grade,
              flesch: Math.round(Math.max(0, Math.min(100, a.flesch_reading_ease))),
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

  const readabilityLabel = (score: number): string => {
    if (score >= 70) return 'Easy';
    if (score >= 50) return 'Moderate';
    return 'Difficult';
  };

  const formatDate = (d: string) =>
    new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="cw-skeleton h-8 w-72" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="cw-skeleton h-24" />
          ))}
        </div>
        <div className="cw-skeleton h-64" />
      </div>
    );
  }

  const totalAnalyses = stats?.stats.totalAnalyses || 0;
  const avgFlesch = stats?.stats.avgReadingEase || 0;
  const avgGrade = stats?.stats.avgGradeLevel || 0;
  const totalWords = stats?.stats.totalWordsAnalyzed || 0;

  return (
    <div className="space-y-8">
      {/* Hero */}
      <section>
        <span className="cw-eyebrow">Dashboard</span>
        <h1 className="cw-hero mt-2">
          Welcome back, {user?.fullName?.split(' ')[0]}
        </h1>
        <p className="mt-2" style={{ color: 'var(--text-2)', fontSize: 13 }}>
          Your linguistics models are synchronized. Analyze, compare, and refine with precision.
        </p>
      </section>

      {/* Metric strip */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total Analyses"
          icon={FileText}
          value={totalAnalyses.toLocaleString()}
          sub={`${stats?.recentAnalyses?.length || 0} in recent activity`}
          accent
        />
        <MetricCard
          label="Average Flesch"
          icon={Gauge}
          value={avgFlesch.toFixed(1)}
          sub={readabilityLabel(avgFlesch) + ' reading level'}
        />
        <MetricCard
          label="Average Grade"
          icon={BarChart3}
          value={avgGrade.toFixed(1)}
          sub="US grade level"
        />
        <MetricCard
          label="Words Analyzed"
          icon={Hash}
          value={totalWords.toLocaleString()}
          sub="Across all texts"
          tonal
        />
      </section>

      {/* Action row */}
      <section>
        <Link
          to="/analyze"
          className="relative overflow-hidden rounded-lg p-7 group block"
          style={{ background: 'var(--g-scholar)', color: '#fff', minHeight: 130 }}
        >
          <div className="absolute -right-4 -bottom-4 opacity-10 group-hover:opacity-20 transition-opacity pointer-events-none">
            <BookOpen className="w-36 h-36" />
          </div>
          <div className="relative">
            <span
              className="cw-eyebrow"
              style={{ color: 'rgba(255,255,255,0.7)' }}
            >
              Quick Action
            </span>
            <h3
              className="mt-2"
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 26,
                fontWeight: 800,
                letterSpacing: '-0.02em',
                color: '#fff',
                lineHeight: 1.1,
              }}
            >
              Start a New Analysis
            </h3>
            <p className="mt-2 max-w-lg" style={{ fontSize: 14, color: 'rgba(255,255,255,0.82)', lineHeight: 1.5 }}>
              Upload raw text or academic PDFs for instant linguistic decomposition and readability scoring.
            </p>
            <div
              className="mt-4 inline-flex items-center gap-2 px-3.5 h-9 rounded-md group-hover:translate-x-1 transition-transform"
              style={{ background: '#fff', color: 'var(--p-900)', fontSize: 13.5, fontWeight: 700 }}
            >
              <PlusCircle className="w-4 h-4" />
              Launch Tool
              <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </div>
        </Link>
      </section>

      {/* Trend chart */}
      {trendData.length >= 2 && (
        <section className="cw-card cw-card-pad-lg">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4" style={{ color: 'var(--p-700)' }} />
              <h3 className="cw-section-title">Readability Trend</h3>
            </div>
            <span className="cw-eyebrow">Last 20 · Grade & Flesch</span>
          </div>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData} margin={{ top: 8, right: 10, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10.5, fill: 'var(--text-3)' }}
                  axisLine={{ stroke: 'var(--border)' }}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="grade"
                  domain={[0, 14]}
                  tick={{ fontSize: 10.5, fill: 'var(--text-3)' }}
                  axisLine={false}
                  tickLine={false}
                  width={30}
                />
                <YAxis
                  yAxisId="flesch"
                  orientation="right"
                  domain={[0, 100]}
                  tick={{ fontSize: 10.5, fill: 'var(--text-3)' }}
                  axisLine={false}
                  tickLine={false}
                  width={30}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--surface-raised)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    fontSize: 11.5,
                    boxShadow: 'var(--sh-2)',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                <Line yAxisId="grade" type="monotone" dataKey="grade" stroke="var(--p-700)" strokeWidth={2} name="Grade" dot={{ r: 3, fill: 'var(--p-700)' }} />
                <Line yAxisId="flesch" type="monotone" dataKey="flesch" stroke="var(--s-500)" strokeWidth={2} name="Flesch" dot={{ r: 3, fill: 'var(--s-500)' }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Recent analyses table */}
      <section className="cw-card cw-card-pad-lg">
        <div className="flex items-center justify-between mb-4">
          <h3 className="cw-section-title">Recent Analyses</h3>
          <Link
            to="/history"
            className="cw-btn cw-btn-ghost cw-btn-sm"
          >
            View all
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {stats?.recentAnalyses && stats.recentAnalyses.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="cw-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th className="text-center">Grade Level</th>
                  <th className="text-right">Date</th>
                </tr>
              </thead>
              <tbody>
                {stats.recentAnalyses.map((a) => {
                  const gradeNum = (() => {
                    const s = a.predicted_grade_level.replace('Grade ', '');
                    return s === 'College' ? 13 : parseInt(s) || 0;
                  })();
                  return (
                    <tr key={a.id}>
                      <td>
                        <Link
                          to={`/analysis/${a.id}`}
                          className="flex flex-col hover:underline"
                          style={{ color: 'var(--text-1)' }}
                        >
                          <span style={{ fontWeight: 600, fontSize: 12.5 }}>{a.title}</span>
                          <span style={{ fontSize: 10.5, color: 'var(--text-4)', marginTop: 1 }}>
                            {a.predicted_grade_level}
                          </span>
                        </Link>
                      </td>
                      <td className="text-center">
                        <span
                          className="cw-badge cw-badge-primary"
                          style={{ fontFamily: 'var(--font-mono)' }}
                        >
                          {gradeNum ? `Grade ${gradeNum}` : a.predicted_grade_level}
                        </span>
                      </td>
                      <td className="text-right" style={{ color: 'var(--text-3)', fontSize: 11.5 }}>
                        {formatDate(a.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12">
            <BookOpen className="w-10 h-10 mx-auto mb-3" style={{ color: 'var(--text-4)' }} />
            <p style={{ color: 'var(--text-3)', fontSize: 13 }}>No analyses yet.</p>
            <Link to="/analyze" className="cw-btn cw-btn-primary cw-btn-sm mt-4 inline-flex">
              <PlusCircle className="w-3.5 h-3.5" />
              Start your first analysis
            </Link>
          </div>
        )}
      </section>
    </div>
  );
};

type MetricProps = {
  label: string;
  value: string;
  sub: string;
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
  accent?: boolean;
  tonal?: boolean;
};

const MetricCard: React.FC<MetricProps> = ({ label, value, sub, icon: Icon, accent, tonal }) => {
  const base: React.CSSProperties = {
    background: tonal ? 'var(--s-200)' : 'var(--surface-raised)',
    borderRadius: 'var(--r-lg)',
    padding: '16px 18px',
    borderLeft: accent ? '3px solid var(--p-900)' : 'none',
    boxShadow: 'var(--sh-1)',
    border: tonal ? 'none' : '1px solid var(--border)',
    minHeight: 112,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
  };
  const valueColor = tonal ? 'var(--s-900)' : 'var(--p-900)';
  const labelColor = tonal ? 'var(--s-700)' : 'var(--text-3)';
  const subColor = tonal ? 'var(--s-700)' : 'var(--text-3)';

  return (
    <div style={base}>
      <div className="flex items-start justify-between">
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: labelColor,
          }}
        >
          {label}
        </span>
        <Icon className="w-4 h-4" style={{ color: labelColor }} />
      </div>
      <div>
        <div
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 28,
            fontWeight: 800,
            letterSpacing: '-0.02em',
            color: valueColor,
            lineHeight: 1.1,
          }}
        >
          {value}
        </div>
        <div style={{ fontSize: 11, color: subColor, marginTop: 4 }}>{sub}</div>
      </div>
    </div>
  );
};

export default Dashboard;
