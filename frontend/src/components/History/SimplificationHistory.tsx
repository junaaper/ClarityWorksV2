import React, { useState, useEffect } from 'react';
import api from '../../services/api';

interface SimplificationRecord {
  id: number;
  original_text: string;
  simplified_text: string;
  target_grade: string;
  changes_applied: string;
  mode: string;
  metrics_original: string | null;
  metrics_simplified: string | null;
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
      const response = await api.get('/simplify/history');
      setSimplifications(response.data);
    } catch (error) {
      console.error('Failed to fetch simplification history:', error);
    }
    setLoading(false);
  };

  if (loading) return <div className="text-center py-8 text-gray-500">Loading simplification history...</div>;

  return (
    <div className="mt-4">
      {simplifications.length === 0 ? (
        <p className="text-gray-500 italic text-center py-8">No simplifications saved yet.</p>
      ) : (
        <div className="space-y-6">
          {simplifications.map((simp) => {
            const changes = JSON.parse(simp.changes_applied || '[]');
            const metricsOrig = simp.metrics_original ? JSON.parse(simp.metrics_original) : null;
            const metricsSimp = simp.metrics_simplified ? JSON.parse(simp.metrics_simplified) : null;
            const isExpanded = expandedId === simp.id;

            return (
              <div key={simp.id} className="bg-white border rounded-lg p-6 shadow-sm">
                {/* Header */}
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <p className="text-sm text-gray-600">
                      {new Date(simp.created_at).toLocaleDateString()} {new Date(simp.created_at).toLocaleTimeString()}
                    </p>
                    <p className="text-lg font-semibold">
                      Simplified to {simp.target_grade}
                    </p>
                    <p className="text-sm text-gray-500">
                      Mode: {simp.mode} | {changes.length} changes applied
                    </p>
                  </div>
                </div>

                {/* Before/After Comparison */}
                <div className="grid grid-cols-2 gap-4">
                  {/* Original */}
                  <div className="bg-red-50 border border-red-200 rounded p-4">
                    <p className="font-semibold text-red-800 mb-2">Original</p>
                    {metricsOrig && (
                      <div className="text-xs text-gray-600 mb-2">
                        Grade: {metricsOrig.grade} |
                        Flesch: {metricsOrig.fleschReadingEase?.toFixed(1) || 'N/A'}
                      </div>
                    )}
                    <p className={`text-sm text-gray-700 ${isExpanded ? '' : 'line-clamp-4'}`}>
                      {simp.original_text}
                    </p>
                  </div>

                  {/* Simplified */}
                  <div className="bg-green-50 border border-green-200 rounded p-4">
                    <p className="font-semibold text-green-800 mb-2">Simplified</p>
                    {metricsSimp && (
                      <div className="text-xs text-gray-600 mb-2">
                        Grade: {metricsSimp.grade} |
                        Flesch: {metricsSimp.fleschReadingEase?.toFixed(1) || 'N/A'}
                      </div>
                    )}
                    <p className={`text-sm text-gray-700 ${isExpanded ? '' : 'line-clamp-4'}`}>
                      {simp.simplified_text}
                    </p>
                  </div>
                </div>

                {/* View Details Button */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : simp.id)}
                  className="mt-4 text-blue-600 hover:underline text-sm"
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
