import React, { useState } from 'react';
import { ArrowLeftRight, Loader2, BarChart3 } from 'lucide-react';
import { analysisApi } from '../../services/api';
import type { Analysis } from '../../types';
import LoadingSpinner from '../common/LoadingSpinner';

const ComparePage: React.FC = () => {
  const [textA, setTextA] = useState('');
  const [textB, setTextB] = useState('');
  const [resultA, setResultA] = useState<Analysis | null>(null);
  const [resultB, setResultB] = useState<Analysis | null>(null);
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
    } catch (err) {
      setError('Failed to analyze texts. Make sure the backend is running.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const getColor = (a: number, b: number, lowerBetter = false) => {
    if (a === b) return 'text-gray-700';
    if (lowerBetter) return a < b ? 'text-green-600' : 'text-red-600';
    return a > b ? 'text-green-600' : 'text-red-600';
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
    return (
      <tr className="border-b border-gray-100">
        <td className="py-3 px-4 font-medium text-gray-700">{label}</td>
        <td className={`py-3 px-4 text-center font-mono ${getColor(valA, valB, lowerBetter)}`}>
          {valA.toFixed(1)}{suffix}
        </td>
        <td className={`py-3 px-4 text-center font-mono ${getColor(valB, valA, lowerBetter)}`}>
          {valB.toFixed(1)}{suffix}
        </td>
        <td className={`py-3 px-4 text-center font-mono text-sm ${
          diff === 0 ? 'text-gray-400' : (lowerBetter ? (diff < 0 ? 'text-green-600' : 'text-red-600') : (diff > 0 ? 'text-green-600' : 'text-red-600'))
        }`}>
          {diff === 0 ? '-' : diffStr}{suffix}
        </td>
      </tr>
    );
  };

  return (
    <div className="max-w-6xl mx-auto">
      {loading && <LoadingSpinner message="Analyzing both texts..." fullScreen />}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
          <ArrowLeftRight className="w-8 h-8 text-primary-600" />
          Compare Texts
        </h1>
        <p className="text-gray-600 mt-2">
          Analyze two texts side by side to compare readability metrics
        </p>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* Input Area */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Text A</label>
          <textarea
            value={textA}
            onChange={(e) => setTextA(e.target.value)}
            placeholder="Paste or type the first text here... (min 50 characters)"
            className="w-full h-48 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none resize-none"
          />
          <p className="text-xs text-gray-500 mt-1">
            {textA.trim().split(/\s+/).filter(Boolean).length} words
          </p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Text B</label>
          <textarea
            value={textB}
            onChange={(e) => setTextB(e.target.value)}
            placeholder="Paste or type the second text here... (min 50 characters)"
            className="w-full h-48 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none resize-none"
          />
          <p className="text-xs text-gray-500 mt-1">
            {textB.trim().split(/\s+/).filter(Boolean).length} words
          </p>
        </div>
      </div>

      <button
        onClick={handleCompare}
        disabled={loading || textA.trim().length < 50 || textB.trim().length < 50}
        className="w-full py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mb-8"
      >
        {loading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Comparing...
          </>
        ) : (
          <>
            <ArrowLeftRight className="w-5 h-5" />
            Compare
          </>
        )}
      </button>

      {/* Results */}
      {resultA && resultB && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 text-center">
              <h3 className="text-lg font-semibold text-blue-800 mb-2">Text A</h3>
              <p className="text-3xl font-bold text-blue-600">
                {resultA.predictions.predicted_grade_level}
              </p>
              <p className="text-sm text-blue-600 mt-1">
                {resultA.predictions.predicted_complexity}
              </p>
            </div>
            <div className="bg-purple-50 border border-purple-200 rounded-xl p-6 text-center">
              <h3 className="text-lg font-semibold text-purple-800 mb-2">Text B</h3>
              <p className="text-3xl font-bold text-purple-600">
                {resultB.predictions.predicted_grade_level}
              </p>
              <p className="text-sm text-purple-600 mt-1">
                {resultB.predictions.predicted_complexity}
              </p>
            </div>
          </div>

          {/* Detailed Comparison Table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary-600" />
              Detailed Comparison
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b-2 border-gray-200">
                    <th className="py-3 px-4 font-semibold text-gray-600">Metric</th>
                    <th className="py-3 px-4 text-center font-semibold text-blue-600">Text A</th>
                    <th className="py-3 px-4 text-center font-semibold text-purple-600">Text B</th>
                    <th className="py-3 px-4 text-center font-semibold text-gray-600">Diff</th>
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
