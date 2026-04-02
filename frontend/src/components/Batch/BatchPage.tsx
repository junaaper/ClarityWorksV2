import React, { useState, useRef } from 'react';
import { FolderUp, Loader2, Upload, FileText, Download, AlertCircle, CheckCircle } from 'lucide-react';
import { analysisApi } from '../../services/api';
import type { Analysis } from '../../types';

interface BatchResult {
  index: number;
  title: string;
  text: string;
  analysis: Analysis | null;
  error?: string;
}

const BatchPage: React.FC = () => {
  const [results, setResults] = useState<BatchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [inputMode, setInputMode] = useState<'paste' | 'csv'>('paste');
  const [bulkText, setBulkText] = useState('');

  const parseCSV = (csvText: string): { title: string; text: string }[] => {
    const lines = csvText.split('\n').filter((l) => l.trim());
    if (lines.length === 0) return [];

    // Check if first line is a header
    const firstLine = lines[0].toLowerCase();
    const hasHeader = firstLine.includes('title') || firstLine.includes('text');
    const dataLines = hasHeader ? lines.slice(1) : lines;

    return dataLines.map((line, i) => {
      // Handle CSV with commas inside quotes
      const match = line.match(/^"?([^"]*)"?,\s*"?([\s\S]*?)"?\s*$/);
      if (match) {
        return { title: match[1].trim() || `Text ${i + 1}`, text: match[2].trim() };
      }
      // Fallback: treat entire line as text
      return { title: `Text ${i + 1}`, text: line.trim() };
    }).filter((item) => item.text.length >= 50);
  };

  const parseBulkText = (raw: string): { title: string; text: string }[] => {
    // Split by "---" separator or double newlines
    const blocks = raw.includes('---')
      ? raw.split(/---+/).map((b) => b.trim()).filter(Boolean)
      : raw.split(/\n{3,}/).map((b) => b.trim()).filter(Boolean);

    return blocks
      .filter((b) => b.length >= 50)
      .map((block, i) => ({
        title: `Text ${i + 1}`,
        text: block,
      }));
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const text = await file.text();
    const items = parseCSV(text);

    if (items.length === 0) {
      setError('No valid texts found in CSV. Each text must be at least 50 characters. Expected format: title,text');
      return;
    }

    await runBatchAnalysis(items);
  };

  const handleBulkAnalyze = async () => {
    const items = parseBulkText(bulkText);
    if (items.length === 0) {
      setError('No valid text blocks found. Separate texts with "---" or triple newlines. Each must be at least 50 characters.');
      return;
    }
    await runBatchAnalysis(items);
  };

  const runBatchAnalysis = async (items: { title: string; text: string }[]) => {
    setError(null);
    setLoading(true);
    setTotal(items.length);
    setProgress(0);
    setResults([]);

    const batchResults: BatchResult[] = [];

    for (let i = 0; i < items.length; i++) {
      try {
        const res = await analysisApi.analyze(items[i].text, items[i].title);
        batchResults.push({
          index: i + 1,
          title: items[i].title,
          text: items[i].text.substring(0, 100) + (items[i].text.length > 100 ? '...' : ''),
          analysis: res.analysis,
        });
      } catch (err) {
        batchResults.push({
          index: i + 1,
          title: items[i].title,
          text: items[i].text.substring(0, 100) + '...',
          analysis: null,
          error: 'Analysis failed',
        });
      }
      setProgress(i + 1);
      setResults([...batchResults]);
    }

    setLoading(false);
  };

  const exportCSV = () => {
    const headers = ['#', 'Title', 'Grade Level', 'Complexity', 'Flesch Score', 'FK Grade', 'ARI', 'SMOG', 'Words', 'Sentences', 'Difficult Words %'];
    const rows = results.map((r) => {
      if (!r.analysis) return [r.index, r.title, 'Error', '', '', '', '', '', '', '', ''];
      const a = r.analysis;
      return [
        r.index,
        r.title,
        a.predictions.predicted_grade_level,
        a.predictions.predicted_complexity,
        a.readability_scores.flesch_reading_ease.toFixed(1),
        a.readability_scores.flesch_kincaid_grade.toFixed(1),
        a.readability_scores.automated_readability_index.toFixed(1),
        a.readability_scores.smog_readability.toFixed(1),
        a.basic_metrics.word_count,
        a.basic_metrics.sentence_count,
        a.statistics.difficult_words_percentage.toFixed(1),
      ];
    });

    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'batch_analysis_results.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const getGradeColor = (grade: string) => {
    const num = grade === 'College' ? 13 : parseInt(grade.replace('Grade ', '')) || 0;
    if (num <= 5) return 'bg-green-100 text-green-700';
    if (num <= 8) return 'bg-yellow-100 text-yellow-700';
    if (num <= 10) return 'bg-orange-100 text-orange-700';
    return 'bg-red-100 text-red-700';
  };

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
          <FolderUp className="w-8 h-8 text-primary-600" />
          Batch Analysis
        </h1>
        <p className="text-gray-600 mt-2">
          Analyze multiple texts at once and get a summary table
        </p>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Mode Selection */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex gap-3 mb-4">
          <button
            onClick={() => setInputMode('paste')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              inputMode === 'paste'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <FileText className="w-4 h-4 inline mr-2" />
            Paste Texts
          </button>
          <button
            onClick={() => setInputMode('csv')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              inputMode === 'csv'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <Upload className="w-4 h-4 inline mr-2" />
            Upload CSV
          </button>
        </div>

        {inputMode === 'paste' ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Paste multiple texts separated by "---" or triple newlines
            </label>
            <textarea
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              placeholder={"First text goes here. It should be at least 50 characters long.\n\n---\n\nSecond text goes here. It should also be at least 50 characters long.\n\n---\n\nThird text..."}
              className="w-full h-48 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none resize-none font-mono text-sm"
            />
            <button
              onClick={handleBulkAnalyze}
              disabled={loading || bulkText.trim().length < 50}
              className="mt-3 px-6 py-2 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderUp className="w-4 h-4" />}
              {loading ? `Analyzing ${progress}/${total}...` : 'Analyze All'}
            </button>
          </div>
        ) : (
          <div>
            <p className="text-sm text-gray-600 mb-3">
              Upload a CSV file with columns: <code className="bg-gray-100 px-1 rounded">title,text</code>
            </p>
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-primary-400 hover:bg-primary-50 transition-colors"
            >
              <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
              <p className="text-gray-600 font-medium">Click to upload CSV</p>
              <p className="text-sm text-gray-500 mt-1">Each row will be analyzed separately</p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.txt"
              onChange={handleFileUpload}
              className="hidden"
            />
          </div>
        )}
      </div>

      {/* Progress Bar */}
      {loading && (
        <div className="mb-6">
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>Analyzing texts...</span>
            <span>{progress} / {total}</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-primary-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(progress / total) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Results Table */}
      {results.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-600" />
              Results ({results.filter((r) => r.analysis).length}/{results.length} successful)
            </h3>
            <button
              onClick={exportCSV}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b-2 border-gray-200">
                  <th className="py-2 px-3 font-semibold text-gray-600">#</th>
                  <th className="py-2 px-3 font-semibold text-gray-600">Title</th>
                  <th className="py-2 px-3 font-semibold text-gray-600">Grade</th>
                  <th className="py-2 px-3 font-semibold text-gray-600">Flesch</th>
                  <th className="py-2 px-3 font-semibold text-gray-600">Words</th>
                  <th className="py-2 px-3 font-semibold text-gray-600">Sentences</th>
                  <th className="py-2 px-3 font-semibold text-gray-600">Diff. Words %</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.index} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-3 text-gray-500">{r.index}</td>
                    <td className="py-2 px-3 font-medium text-gray-700 max-w-xs truncate">{r.title}</td>
                    {r.analysis ? (
                      <>
                        <td className="py-2 px-3">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${getGradeColor(r.analysis.predictions.predicted_grade_level)}`}>
                            {r.analysis.predictions.predicted_grade_level}
                          </span>
                        </td>
                        <td className="py-2 px-3 font-mono">{r.analysis.readability_scores.flesch_reading_ease.toFixed(1)}</td>
                        <td className="py-2 px-3 font-mono">{r.analysis.basic_metrics.word_count}</td>
                        <td className="py-2 px-3 font-mono">{r.analysis.basic_metrics.sentence_count}</td>
                        <td className="py-2 px-3 font-mono">{r.analysis.statistics.difficult_words_percentage.toFixed(1)}%</td>
                      </>
                    ) : (
                      <td colSpan={5} className="py-2 px-3 text-red-500">{r.error}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Summary Stats */}
          {results.filter((r) => r.analysis).length > 1 && (
            <div className="mt-6 pt-4 border-t border-gray-200">
              <h4 className="text-sm font-semibold text-gray-600 mb-3">Summary</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                {(() => {
                  const valid = results.filter((r) => r.analysis).map((r) => r.analysis!);
                  const avgFlesch = valid.reduce((s, a) => s + a.readability_scores.flesch_reading_ease, 0) / valid.length;
                  const grades = valid.map((a) => {
                    const g = a.predictions.predicted_grade_level.replace('Grade ', '');
                    return g === 'College' ? 13 : parseInt(g) || 0;
                  });
                  const avgGrade = grades.reduce((s, g) => s + g, 0) / grades.length;
                  const minGrade = Math.min(...grades);
                  const maxGrade = Math.max(...grades);
                  return (
                    <>
                      <div className="p-3 bg-gray-50 rounded-lg">
                        <p className="text-2xl font-bold text-primary-600">{avgFlesch.toFixed(1)}</p>
                        <p className="text-xs text-gray-500">Avg Flesch Score</p>
                      </div>
                      <div className="p-3 bg-gray-50 rounded-lg">
                        <p className="text-2xl font-bold text-blue-600">{avgGrade.toFixed(1)}</p>
                        <p className="text-xs text-gray-500">Avg Grade Level</p>
                      </div>
                      <div className="p-3 bg-gray-50 rounded-lg">
                        <p className="text-2xl font-bold text-green-600">Grade {minGrade}</p>
                        <p className="text-xs text-gray-500">Easiest</p>
                      </div>
                      <div className="p-3 bg-gray-50 rounded-lg">
                        <p className="text-2xl font-bold text-red-600">{maxGrade >= 13 ? 'College' : `Grade ${maxGrade}`}</p>
                        <p className="text-xs text-gray-500">Hardest</p>
                      </div>
                    </>
                  );
                })()}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default BatchPage;
