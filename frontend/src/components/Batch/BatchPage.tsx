import React, { useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { FolderUp, Loader2, Upload, FileText, Download, AlertCircle, CheckCircle } from 'lucide-react';
import { analysisApi } from '../../services/api';
import type { Analysis } from '../../types';

interface BatchResult {
  index: number;
  title: string;
  text: string;
  analysis: Analysis | null;
  analysisId?: number;
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

    const firstLine = lines[0].toLowerCase();
    const hasHeader = firstLine.includes('title') || firstLine.includes('text');
    const dataLines = hasHeader ? lines.slice(1) : lines;

    return dataLines.map((line, i) => {
      const match = line.match(/^"?([^"]*)"?,\s*"?([\s\S]*?)"?\s*$/);
      if (match) {
        return { title: match[1].trim() || `Text ${i + 1}`, text: match[2].trim() };
      }
      return { title: `Text ${i + 1}`, text: line.trim() };
    }).filter((item) => item.text.length >= 50);
  };

  const parseBulkText = (raw: string): { title: string; text: string }[] => {
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
          analysisId: res.analysisId,
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
        Math.max(0, Math.min(100, a.readability_scores.flesch_reading_ease)).toFixed(1),
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

  const getGradeBadge = (grade: string): string => {
    const num = grade === 'College' ? 13 : parseInt(grade.replace('Grade ', '')) || 0;
    if (num <= 5) return 'cw-badge cw-badge-ok';
    if (num <= 8) return 'cw-badge cw-badge-warn';
    if (num <= 10) return 'cw-badge cw-badge-primary';
    return 'cw-badge cw-badge-err';
  };

  const ModeTab: React.FC<{ active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }> = ({ active, onClick, icon, children }) => (
    <button
      onClick={onClick}
      className="px-3 py-2 rounded-md text-[12.5px] inline-flex items-center gap-2 transition-colors"
      style={{
        background: active ? 'var(--surface-raised)' : 'transparent',
        color: active ? 'var(--p-900)' : 'var(--text-2)',
        fontWeight: active ? 600 : 500,
        boxShadow: active ? 'var(--sh-1)' : 'none',
      }}
    >
      {icon}
      {children}
    </button>
  );

  return (
    <div>
      <div className="mb-8">
        <div className="cw-eyebrow mb-2">Workspace</div>
        <h1 className="cw-hero flex items-center gap-3" style={{ fontSize: 28 }}>
          <FolderUp className="w-7 h-7" style={{ color: 'var(--p-700)' }} />
          Batch Analysis
        </h1>
        <p className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
          Analyze multiple texts at once and get a summary table.
        </p>
      </div>

      {error && (
        <div
          className="mb-5 rounded-md flex items-center gap-2"
          style={{
            padding: '12px 16px',
            background: 'var(--err-50)',
            border: '1px solid color-mix(in srgb, var(--err-500) 22%, transparent)',
            color: 'var(--err-700)',
            fontSize: 12.5,
          }}
        >
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Mode Selection */}
      <div className="cw-card cw-card-pad-lg mb-5">
        <div className="cw-eyebrow mb-3">Input Source</div>
        <div
          className="inline-flex p-1 mb-4 rounded-md"
          style={{ background: 'var(--surface-sunk)', border: '1px solid var(--border)' }}
        >
          <ModeTab
            active={inputMode === 'paste'}
            onClick={() => setInputMode('paste')}
            icon={<FileText className="w-3.5 h-3.5" />}
          >
            Paste Texts
          </ModeTab>
          <ModeTab
            active={inputMode === 'csv'}
            onClick={() => setInputMode('csv')}
            icon={<Upload className="w-3.5 h-3.5" />}
          >
            Upload CSV
          </ModeTab>
        </div>

        {inputMode === 'paste' ? (
          <div>
            <label className="block mb-2" style={{ fontSize: 12, color: 'var(--text-2)', fontWeight: 500 }}>
              Paste multiple texts separated by "---" or triple newlines
            </label>
            <textarea
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              placeholder={"First text goes here. It should be at least 50 characters long.\n\n---\n\nSecond text goes here. It should also be at least 50 characters long.\n\n---\n\nThird text..."}
              className="cw-textarea"
              style={{ height: 200, fontFamily: 'var(--font-mono)', fontSize: 12 }}
            />
            <button
              onClick={handleBulkAnalyze}
              disabled={loading || bulkText.trim().length < 50}
              className="cw-btn cw-btn-primary mt-4"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <FolderUp className="w-4 h-4" />}
              {loading ? `Analyzing ${progress}/${total}…` : 'Analyze All'}
            </button>
          </div>
        ) : (
          <div>
            <p className="mb-3" style={{ fontSize: 12, color: 'var(--text-3)' }}>
              Upload a CSV file with columns:{' '}
              <code style={{
                background: 'var(--surface-sunk)',
                padding: '2px 6px',
                borderRadius: 4,
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--text-2)',
              }}>title,text</code>
            </p>
            <div
              onClick={() => fileInputRef.current?.click()}
              className="rounded-lg p-10 text-center cursor-pointer transition-colors"
              style={{
                border: '2px dashed var(--border-strong)',
                background: 'var(--surface-sunk)',
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--p-500)';
                (e.currentTarget as HTMLDivElement).style.background = 'color-mix(in srgb, var(--p-50) 50%, var(--surface-sunk))';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLDivElement).style.borderColor = 'var(--border-strong)';
                (e.currentTarget as HTMLDivElement).style.background = 'var(--surface-sunk)';
              }}
            >
              <Upload className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--text-4)' }} />
              <p style={{ color: 'var(--text-2)', fontWeight: 600, fontSize: 13 }}>Click to upload CSV</p>
              <p className="mt-1" style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
                Each row will be analyzed separately
              </p>
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
        <div className="cw-card cw-card-pad mb-5">
          <div className="flex justify-between mb-2" style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
            <span>Analyzing texts…</span>
            <span style={{ fontFamily: 'var(--font-mono)' }}>{progress} / {total}</span>
          </div>
          <div
            className="w-full rounded-full"
            style={{ height: 6, background: 'var(--surface-sunk)' }}
          >
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{
                width: `${(progress / total) * 100}%`,
                background: 'linear-gradient(90deg, var(--p-700), var(--p-500))',
              }}
            />
          </div>
        </div>
      )}

      {/* Results Table */}
      {results.length > 0 && (
        <div className="cw-card cw-card-pad-lg">
          <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4" style={{ color: 'var(--ok-500)' }} />
              <h3 className="cw-section-title">
                Results ({results.filter((r) => r.analysis).length}/{results.length} successful)
              </h3>
            </div>
            <button onClick={exportCSV} className="cw-btn cw-btn-sm cw-btn-teal">
              <Download className="w-3.5 h-3.5" />
              Export CSV
            </button>
          </div>

          <div className="cw-scroll-x">
            <table className="cw-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Title</th>
                  <th>Grade</th>
                  <th>Flesch</th>
                  <th>Words</th>
                  <th>Sentences</th>
                  <th>Diff. Words %</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.index}>
                    <td style={{ color: 'var(--text-4)', fontFamily: 'var(--font-mono)' }}>{r.index}</td>
                    <td style={{ maxWidth: 280 }}>
                      {r.analysisId ? (
                        <Link
                          to={`/analysis/${r.analysisId}`}
                          className="truncate block hover:underline"
                          style={{ color: 'var(--text-1)', fontWeight: 600, fontSize: 12.5 }}
                        >
                          {r.title}
                        </Link>
                      ) : (
                        <div className="truncate" style={{ color: 'var(--text-1)', fontWeight: 600, fontSize: 12.5 }}>{r.title}</div>
                      )}
                    </td>
                    {r.analysis ? (
                      <>
                        <td>
                          <span className={getGradeBadge(r.analysis.predictions.predicted_grade_level)}>
                            {r.analysis.predictions.predicted_grade_level}
                          </span>
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                          {Math.max(0, Math.min(100, r.analysis.readability_scores.flesch_reading_ease)).toFixed(1)}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                          {r.analysis.basic_metrics.word_count}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                          {r.analysis.basic_metrics.sentence_count}
                        </td>
                        <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                          {r.analysis.statistics.difficult_words_percentage.toFixed(1)}%
                        </td>
                      </>
                    ) : (
                      <td colSpan={5} style={{ color: 'var(--err-500)', fontSize: 12 }}>{r.error}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Summary Stats */}
          {results.filter((r) => r.analysis).length > 1 && (
            <div className="mt-6 pt-4" style={{ borderTop: '1px solid var(--border)' }}>
              <div className="cw-eyebrow mb-3">Summary</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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
                  const statCard = (value: string, label: string, color: string) => (
                    <div
                      className="rounded-md p-3 text-center"
                      style={{
                        background: 'var(--surface-sunk)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <p style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 22,
                        fontWeight: 700,
                        color,
                        lineHeight: 1.2,
                      }}>
                        {value}
                      </p>
                      <p className="mt-1" style={{ fontSize: 11, color: 'var(--text-3)' }}>{label}</p>
                    </div>
                  );
                  return (
                    <>
                      {statCard(avgFlesch.toFixed(1), 'Avg Flesch Score', 'var(--p-700)')}
                      {statCard(avgGrade.toFixed(1), 'Avg Grade Level', 'var(--s-700)')}
                      {statCard(minGrade >= 13 ? 'College' : `Grade ${minGrade}`, 'Easiest', 'var(--ok-500)')}
                      {statCard(maxGrade >= 13 ? 'College' : `Grade ${maxGrade}`, 'Hardest', 'var(--err-500)')}
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
