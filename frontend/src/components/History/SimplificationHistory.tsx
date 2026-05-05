import React, { useState, useEffect } from 'react';
import api from '../../services/api';

interface SimplificationRecord {
  id: number;
  original_text: string;
  simplified_text: string;
  target_grade: string;
  changes_applied: string | unknown[];
  mode: string;
  metrics_original: string | Record<string, unknown> | null;
  metrics_simplified: string | Record<string, unknown> | null;
  created_at: string;
}

const SimplificationHistory: React.FC = () => {
  const [simplifications, setSimplifications] = useState<SimplificationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    fetchSimplifications();
  }, []);

  const fetchSimplifications = async () => {
    try {
      const response = await api.get('/api/simplify/history');
      setSimplifications(response.data);
    } catch (error) {
      console.error('Failed to fetch simplification history:', error);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <div
          className="animate-spin rounded-full h-8 w-8 border-b-2"
          style={{ borderColor: 'var(--p-700)' }}
        />
      </div>
    );
  }

  return (
    <div className="mt-4">
      {simplifications.length === 0 ? (
        <p
          className="text-center py-10"
          style={{ color: 'var(--text-4)', fontStyle: 'italic', fontSize: 12.5 }}
        >
          No simplifications saved yet.
        </p>
      ) : (
        <div className="space-y-4">
          {simplifications.map((simp) => {
            const changes = typeof simp.changes_applied === 'string' ? JSON.parse(simp.changes_applied || '[]') : (simp.changes_applied || []);
            const metricsOrig = simp.metrics_original ? (typeof simp.metrics_original === 'string' ? JSON.parse(simp.metrics_original) : simp.metrics_original) : null;
            const metricsSimp = simp.metrics_simplified ? (typeof simp.metrics_simplified === 'string' ? JSON.parse(simp.metrics_simplified) : simp.metrics_simplified) : null;
            const isExpanded = expandedId === simp.id;

            return (
              <div key={simp.id} className="cw-card cw-card-pad-lg">
                <div className="flex justify-between items-start mb-4 gap-3 flex-wrap">
                  <div>
                    <div className="cw-eyebrow mb-1">
                      {new Date(simp.created_at).toLocaleString()}
                    </div>
                    <p style={{ fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 700, color: 'var(--text-1)' }}>
                      Rewritten to {simp.target_grade}
                    </p>
                    <div className="mt-2 flex items-center gap-2 flex-wrap">
                      <span className="cw-badge cw-badge-neutral">{simp.mode}</span>
                      <span className="cw-badge cw-badge-primary">
                        {changes.length} change{changes.length !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div
                    className="rounded-md p-4"
                    style={{
                      background: 'color-mix(in srgb, var(--err-500) 5%, var(--surface-raised))',
                      border: '1px solid color-mix(in srgb, var(--err-500) 18%, transparent)',
                    }}
                  >
                    <div className="cw-eyebrow mb-2" style={{ color: 'var(--err-700)' }}>Original</div>
                    {metricsOrig && (
                      <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>
                        Grade: {metricsOrig.grade} · Flesch: {metricsOrig.fleschReadingEase?.toFixed(1) || 'N/A'}
                      </div>
                    )}
                    <p
                      className={isExpanded ? '' : 'line-clamp-4'}
                      style={{ fontSize: 12.5, color: 'var(--text-1)', lineHeight: 1.55, fontFamily: 'var(--font-serif)' }}
                    >
                      {simp.original_text}
                    </p>
                  </div>

                  <div
                    className="rounded-md p-4"
                    style={{
                      background: 'color-mix(in srgb, var(--s-500) 6%, var(--surface-raised))',
                      border: '1px solid color-mix(in srgb, var(--s-500) 22%, transparent)',
                    }}
                  >
                    <div className="cw-eyebrow mb-2" style={{ color: 'var(--s-700)' }}>Rewritten</div>
                    {metricsSimp && (
                      <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 6, fontFamily: 'var(--font-mono)' }}>
                        Grade: {metricsSimp.grade} · Flesch: {metricsSimp.fleschReadingEase?.toFixed(1) || 'N/A'}
                      </div>
                    )}
                    <p
                      className={isExpanded ? '' : 'line-clamp-4'}
                      style={{ fontSize: 12.5, color: 'var(--text-1)', lineHeight: 1.55, fontFamily: 'var(--font-serif)' }}
                    >
                      {simp.simplified_text}
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => setExpandedId(isExpanded ? null : simp.id)}
                  className="mt-4 hover:underline"
                  style={{ color: 'var(--p-700)', fontSize: 12, fontWeight: 500 }}
                >
                  {isExpanded ? 'Show less' : 'View full details'}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default SimplificationHistory;
