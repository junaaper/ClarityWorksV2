import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Users, FileText, TrendingUp, Activity, BarChart3, Clock
} from 'lucide-react';
import { adminApi } from '../../services/api';
import type { AdminStats } from '../../types';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';

const AdminDashboard: React.FC = () => {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await adminApi.getStats();
        setStats(data);
      } catch (err) {
        setError('Failed to load admin statistics');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div
          className="animate-spin rounded-full h-10 w-10 border-b-2"
          style={{ borderColor: 'var(--p-700)' }}
        />
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="text-center py-12">
        <p style={{ color: 'var(--err-500)', fontSize: 13 }}>{error || 'Failed to load statistics'}</p>
      </div>
    );
  }

  const MetricCard: React.FC<{
    icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
    tint: string;
    label: string;
    value: string;
    hint?: React.ReactNode;
  }> = ({ icon: Icon, tint, label, value, hint }) => (
    <div className="cw-card cw-card-pad">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4" style={{ color: tint }} />
        <span className="cw-eyebrow" style={{ marginBottom: 0 }}>{label}</span>
      </div>
      <p style={{
        fontFamily: 'var(--font-display)',
        fontSize: 28,
        fontWeight: 700,
        color: 'var(--text-1)',
        lineHeight: 1.1,
      }}>
        {value}
      </p>
      {hint && (
        <div className="mt-2" style={{ fontSize: 11, color: 'var(--text-3)' }}>
          {hint}
        </div>
      )}
    </div>
  );

  return (
    <div>
      <div className="mb-8">
        <div className="cw-eyebrow mb-2">Administration</div>
        <h1 className="cw-hero" style={{ fontSize: 28 }}>Admin Dashboard</h1>
        <p className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
          Overview of platform statistics and management.
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard
          icon={Users}
          tint="var(--p-700)"
          label="Total Users"
          value={String(stats.users.total)}
          hint={
            <span>
              <span style={{ color: 'var(--ok-500)' }}>+{stats.users.newThisWeek}</span> this week · {stats.users.active} active
            </span>
          }
        />
        <MetricCard
          icon={FileText}
          tint="var(--s-700)"
          label="Total Analyses"
          value={String(stats.analyses.total)}
          hint={
            <span>
              <span style={{ color: 'var(--ok-500)' }}>+{stats.analyses.thisWeek}</span> this week · {stats.analyses.thisMonth} this month
            </span>
          }
        />
        <MetricCard
          icon={TrendingUp}
          tint="var(--ok-500)"
          label="Avg Reading Ease"
          value={stats.analyses.avgReadingEase.toFixed(1)}
          hint="Flesch Reading Ease score"
        />
        <MetricCard
          icon={BarChart3}
          tint="var(--warn-500)"
          label="Words Analyzed"
          value={stats.analyses.totalWords.toLocaleString()}
          hint="Total words processed"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Grade Distribution */}
        <div className="cw-card cw-card-pad-lg">
          <h3 className="cw-section-title mb-4">Grade Level Distribution</h3>
          {stats.gradeDistribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={stats.gradeDistribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="gradeLevel" tick={{ fontSize: 11, fill: 'var(--text-3)' }} />
                <YAxis tick={{ fontSize: 11, fill: 'var(--text-3)' }} />
                <Tooltip
                  contentStyle={{
                    background: 'var(--surface-raised)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="count" fill="var(--p-700)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48" style={{ color: 'var(--text-4)', fontSize: 12 }}>
              No data available
            </div>
          )}
        </div>

        {/* User Stats Pie */}
        <div className="cw-card cw-card-pad-lg">
          <h3 className="cw-section-title mb-4">User Status</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={[
                  { name: 'Active', value: stats.users.active },
                  { name: 'Inactive', value: stats.users.inactive },
                ]}
                cx="50%"
                cy="50%"
                innerRadius={58}
                outerRadius={78}
                paddingAngle={4}
                dataKey="value"
                label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
                style={{ fontSize: 11 }}
              >
                <Cell fill="var(--ok-500)" />
                <Cell fill="var(--err-500)" />
              </Pie>
              <Tooltip
                contentStyle={{
                  background: 'var(--surface-raised)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent Activity */}
        <div className="cw-card cw-card-pad-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="cw-section-title flex items-center gap-2">
              <Activity className="w-4 h-4" style={{ color: 'var(--p-700)' }} />
              Recent Activity
            </h3>
            <Link
              to="/admin/analyses"
              style={{ color: 'var(--p-700)', fontSize: 11.5, fontWeight: 600 }}
              className="hover:underline"
            >
              View all →
            </Link>
          </div>
          <div>
            {stats.recentActivity.slice(0, 5).map((activity, idx, arr) => (
              <div
                key={activity.id}
                className="flex items-center justify-between py-2.5"
                style={{
                  borderBottom: idx === arr.length - 1 ? 'none' : '1px solid var(--border)',
                }}
              >
                <div>
                  <p style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-1)' }}>
                    {activity.title || 'Untitled Analysis'}
                  </p>
                  <p className="mt-0.5" style={{ fontSize: 11, color: 'var(--text-3)' }}>
                    by {activity.userName}
                  </p>
                </div>
                <div className="flex items-center gap-1" style={{ fontSize: 11, color: 'var(--text-4)' }}>
                  <Clock className="w-3 h-3" />
                  {new Date(activity.createdAt).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top Users */}
        <div className="cw-card cw-card-pad-lg">
          <div className="flex items-center justify-between mb-4">
            <h3 className="cw-section-title flex items-center gap-2">
              <Users className="w-4 h-4" style={{ color: 'var(--s-700)' }} />
              Top Users
            </h3>
            <Link
              to="/admin/users"
              style={{ color: 'var(--p-700)', fontSize: 11.5, fontWeight: 600 }}
              className="hover:underline"
            >
              View all →
            </Link>
          </div>
          <div>
            {stats.topUsers.map((user, index, arr) => (
              <div
                key={user.id}
                className="flex items-center justify-between py-2.5"
                style={{
                  borderBottom: index === arr.length - 1 ? 'none' : '1px solid var(--border)',
                }}
              >
                <div className="flex items-center gap-3">
                  <span
                    className="flex items-center justify-center rounded-full"
                    style={{
                      width: 24,
                      height: 24,
                      background: 'var(--p-50)',
                      color: 'var(--p-700)',
                      fontSize: 11,
                      fontFamily: 'var(--font-mono)',
                      fontWeight: 600,
                    }}
                  >
                    {index + 1}
                  </span>
                  <div>
                    <p style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-1)' }}>
                      {user.fullName}
                    </p>
                    <p style={{ fontSize: 11, color: 'var(--text-3)' }}>
                      {user.email}
                    </p>
                  </div>
                </div>
                <span style={{
                  fontSize: 11.5,
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-2)',
                }}>
                  {user.analysisCount} analyses
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
