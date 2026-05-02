import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeftRight, Loader2, BarChart3, ExternalLink } from 'lucide-react';
import { analysisApi } from '../../services/api';
import type { Analysis } from '../../types';
import LoadingSpinner from '../common/LoadingSpinner';

const ComparePage: React.FC = () => {
  const [textA, setTextA] = useState('');
  const [textB, setTextB] = useState('');
  const [resultA, setResultA] = useState<Analysis | null>(null);
  const [resultB, setResultB] = useState<Analysis | null>(null);
  const [analysisIdA, setAnalysisIdA] = useState<number | null>(null);
  const [analysisIdB, setAnalysisIdB] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async () => {
    if (textA.trim().length < 50 || textB.trim().length < 50) {
      setError('Both texts must be at least 50 characters');
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const [resA, resB] = await Promise.all([
        analysisApi.analyze(textA, 'Compare - Text A'),
        analysisApi.analyze(textB, 'Compare - Text B'),
      ]);
      setResultA(resA.analysis);
      setResultB(resB.analysis);
      setAnalysisIdA(resA.analysisId);
      setAnalysisIdB(resB.analysisId);
    } catch (err) {
      setError('Failed to analyze texts. Make sure the backend is running.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const getColor = (a: number, b: number, lowerBetter = false): string => {
    if (a === b) return 'var(--text-2)';
    if (lowerBetter) return a < b ? 'var(--ok-500)' : 'var(--err-500)';
    return a > b ? 'var(--ok-500)' : 'var(--err-500)';
  };

  const MetricRow = ({ label, valA, valB, lowerBetter = false, suffix = '' }: {
    label: string;
    valA: number;
    valB: number;
    lowerBetter?: boolean;
    suffix?: string;
  }) => {
    const diff = valB - valA;
    const diffStr = diff > 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1);
    const diffColor =
      diff === 0
        ? 'var(--text-4)'
        : lowerBetter
          ? (diff < 0 ? 'var(--ok-500)' : 'var(--err-500)')
          : (diff > 0 ? 'var(--ok-500)' : 'var(--err-500)');
    return (
      <tr>
        <td style={{ color: 'var(--text-2)', fontWeight: 600, fontSize: 12.5 }}>{label}</td>
        <td style={{
          textAlign: 'center',
          fontFamily: 'var(--font-mono)',
          color: getColor(valA, valB, lowerBetter),
          fontSize: 12.5,
        }}>
          {valA.toFixed(1)}{suffix}
        </td>
        <td style={{
          textAlign: 'center',
          fontFamily: 'var(--font-mono)',
          color: getColor(valB, valA, lowerBetter),
          fontSize: 12.5,
        }}>
          {valB.toFixed(1)}{suffix}
        </td>
        <td style={{
          textAlign: 'center',
          fontFamily: 'var(--font-mono)',
          fontSize: 11.5,
          color: diffColor,
        }}>
          {diff === 0 ? '—' : diffStr}{suffix}
        </td>
      </tr>
    );
  };

  const wordsA = textA.trim().split(/\s+/).filter(Boolean).length;
  const wordsB = textB.trim().split(/\s+/).filter(Boolean).length;

  return (
    <div>
      {loading && <LoadingSpinner message="Analyzing both texts..." fullScreen />}

      <div className="mb-8">
        <div className="cw-eyebrow mb-2">Workspace</div>
        <h1 className="cw-hero flex items-center gap-3" style={{ fontSize: 28 }}>
          <ArrowLeftRight className="w-7 h-7" style={{ color: 'var(--p-700)' }} />
          Compare Texts
        </h1>
        <p className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
          Analyze two texts side by side to compare readability metrics.
        </p>
      </div>

      {error && (
        <div
          className="mb-5 rounded-md"
          style={{
            padding: '12px 16px',
            background: 'var(--err-50)',
            border: '1px solid color-mix(in srgb, var(--err-500) 22%, transparent)',
            color: 'var(--err-700)',
            fontSize: 12.5,
          }}
        >
          {error}
        </div>
      )}

      {/* Input Area */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        <div className="cw-card cw-card-pad">
          <div className="flex items-center justify-between mb-2">
            <label className="cw-eyebrow" style={{ marginBottom: 0 }}>Text A</label>
            <span style={{ fontSize: 11, color: 'var(--text-4)', fontFamily: 'var(--font-mono)' }}>
              {wordsA} words
            </span>
          </div>
          <textarea
            value={textA}
            onChange={(e) => setTextA(e.target.value)}
            placeholder="Paste or type the first text here… (min 50 characters)"
            className="cw-textarea"
            style={{ height: 200, resize: 'vertical' }}
          />
        </div>
        <div className="cw-card cw-card-pad">
          <div className="flex items-center justify-between mb-2">
            <label className="cw-eyebrow" style={{ marginBottom: 0 }}>Text B</label>
            <span style={{ fontSize: 11, color: 'var(--text-4)', fontFamily: 'var(--font-mono)' }}>
              {wordsB} words
            </span>
          </div>
          <textarea
            value={textB}
            onChange={(e) => setTextB(e.target.value)}
            placeholder="Paste or type the second text here… (min 50 characters)"
            className="cw-textarea"
            style={{ height: 200, resize: 'vertical' }}
          />
        </div>
      </div>

      <button
        onClick={handleCompare}
        disabled={loading || textA.trim().length < 50 || textB.trim().length < 50}
        className="cw-btn cw-btn-primary cw-btn-lg w-full mb-8"
      >
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Comparing…
          </>
        ) : (
          <>
            <ArrowLeftRight className="w-4 h-4" />
            Compare
          </>
        )}
      </button>

      {/* Results */}
      {resultA && resultB && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
            <div
              className="cw-card cw-card-pad-lg text-center"
              style={{
                background: 'color-mix(in srgb, var(--p-500) 6%, var(--surface-raised))',
                border: '1px solid color-mix(in srgb, var(--p-500) 20%, transparent)',
              }}
            >
              <div className="cw-eyebrow mb-2" style={{ color: 'var(--p-700)' }}>Text A</div>
              <p style={{
                fontFamily: 'var(--font-display)',
                fontSize: 26,
                fontWeight: 700,
                color: 'var(--p-900)',
                lineHeight: 1.2,
              }}>
                {resultA.predictions.predicted_grade_level}
              </p>
              <p className="mt-1" style={{ color: 'var(--p-700)', fontSize: 12 }}>
                {resultA.predictions.predicted_complexity}
              </p>
              {analysisIdA && (
                <Link
                  to={`/analysis/${analysisIdA}`}
                  className="mt-3 inline-flex items-center gap-1.5 hover:underline"
                  style={{ color: 'var(--p-700)', fontSize: 11.5, fontWeight: 600 }}
                >
                  View Full Analysis <ExternalLink className="w-3 h-3" />
                </Link>
              )}
            </div>
            <div
              className="cw-card cw-card-pad-lg text-center"
              style={{
                background: 'color-mix(in srgb, var(--s-500) 7%, var(--surface-raised))',
                border: '1px solid color-mix(in srgb, var(--s-500) 24%, transparent)',
              }}
            >
              <div className="cw-eyebrow mb-2" style={{ color: 'var(--s-700)' }}>Text B</div>
              <p style={{
                fontFamily: 'var(--font-display)',
                fontSize: 26,
                fontWeight: 700,
                color: 'var(--s-700)',
                lineHeight: 1.2,
              }}>
                {resultB.predictions.predicted_grade_level}
              </p>
              <p className="mt-1" style={{ color: 'var(--s-700)', fontSize: 12 }}>
                {resultB.predictions.predicted_complexity}
              </p>
              {analysisIdB && (
                <Link
                  to={`/analysis/${analysisIdB}`}
                  className="mt-3 inline-flex items-center gap-1.5 hover:underline"
                  style={{ color: 'var(--s-700)', fontSize: 11.5, fontWeight: 600 }}
                >
                  View Full Analysis <ExternalLink className="w-3 h-3" />
                </Link>
              )}
            </div>
          </div>

          {/* Detailed Comparison Table */}
          <div className="cw-card cw-card-pad-lg">
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 className="w-4 h-4" style={{ color: 'var(--p-700)' }} />
              <h3 className="cw-section-title">Detailed Comparison</h3>
            </div>
            <div className="cw-scroll-x">
              <table className="cw-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th style={{ textAlign: 'center', color: 'var(--p-700)' }}>Text A</th>
                    <th style={{ textAlign: 'center', color: 'var(--s-700)' }}>Text B</th>
                    <th style={{ textAlign: 'center' }}>Diff</th>
                  </tr>
                </thead>
                <tbody>
                  <MetricRow label="Flesch Reading Ease" valA={resultA.readability_scores.flesch_reading_ease} valB={resultB.readability_scores.flesch_reading_ease} />
                  <MetricRow label="Flesch-Kincaid Grade" valA={resultA.readability_scores.flesch_kincaid_grade} valB={resultB.readability_scores.flesch_kincaid_grade} lowerBetter />
                  <MetricRow label="ARI" valA={resultA.readability_scores.automated_readability_index} valB={resultB.readability_scores.automated_readability_index} lowerBetter />
                  <MetricRow label="SMOG Index" valA={resultA.readability_scores.smog_readability} valB={resultB.readability_scores.smog_readability} lowerBetter />
                  <MetricRow label="Coleman-Liau" valA={resultA.readability_scores.coleman_liau_index} valB={resultB.readability_scores.coleman_liau_index} lowerBetter />
                  <MetricRow label="Word Count" valA={resultA.basic_metrics.word_count} valB={resultB.basic_metrics.word_count} />
                  <MetricRow label="Sentence Count" valA={resultA.basic_metrics.sentence_count} valB={resultB.basic_metrics.sentence_count} />
                  <MetricRow label="Avg Sentence Length" valA={resultA.basic_metrics.avg_sentence_length} valB={resultB.basic_metrics.avg_sentence_length} lowerBetter />
                  <MetricRow label="Avg Syllables/Word" valA={resultA.basic_metrics.avg_syllables_per_word} valB={resultB.basic_metrics.avg_syllables_per_word} lowerBetter />
                  <MetricRow label="Difficult Words" valA={resultA.statistics.difficult_words_count} valB={resultB.statistics.difficult_words_count} lowerBetter />
                  <MetricRow label="Difficult Words %" valA={resultA.statistics.difficult_words_percentage} valB={resultB.statistics.difficult_words_percentage} lowerBetter suffix="%" />
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ComparePage;
