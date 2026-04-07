import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Loader2, Save, Wand2, Check, X, Download, FileText, TrendingDown, TrendingUp } from 'lucide-react';
import { analysisApi, simplifyApi } from '../../services/api';
import LoadingSpinner from '../common/LoadingSpinner';
import { exportSimplificationPDF, exportSimplificationDOCX } from '../../utils/exportSimplification';

interface Change {
  type: string;
  original: string;
  simplified: string;
  position: number;
  reason: string;
  id: number;
  accepted: boolean | null;
}

const SimplifyPage: React.FC = () => {
  const { analysisId } = useParams<{ analysisId: string }>();
  const navigate = useNavigate();

  const [mode, setMode] = useState<'auto' | 'interactive'>('auto');
  const [originalText, setOriginalText] = useState('');
  const [simplifiedText, setSimplifiedText] = useState('');
  const [changes, setChanges] = useState<Change[]>([]);
  const [targetGrade, setTargetGrade] = useState(6);
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hoveredChange, setHoveredChange] = useState<number | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [originalGrade, setOriginalGrade] = useState<string | null>(null);
  const [simplifiedGrade, setSimplifiedGrade] = useState<string | null>(null);
  const [gradeLoading, setGradeLoading] = useState(false);

  useEffect(() => {
    const fetchAnalysis = async () => {
      if (!analysisId) return;
      try {
        const result = await analysisApi.getAnalysis(parseInt(analysisId));
        setOriginalText(result.originalText || '');
        setOriginalGrade(result.analysis.predictions.predicted_grade_level);
      } catch (error) {
        console.error('Failed to load analysis:', error);
      } finally {
        setLoadingText(false);
      }
    };
    fetchAnalysis();
  }, [analysisId]);

  const handleSimplify = async () => {
    if (!analysisId) return;
    setLoading(true);
    try {
      const response = await simplifyApi.analyze({
        analysisId: parseInt(analysisId),
        targetGrade,
        mode,
      });

      const newChanges: Change[] = (response.suggested_changes || []).map((c: any) => ({
        ...c,
        accepted: mode === 'auto' ? true : null,
      }));

      setChanges(newChanges);
      setSimplifiedText(response.preview_text || '');

      // Compute predicted grade of simplified text
      if (response.preview_text && response.preview_text.length >= 50) {
        setGradeLoading(true);
        try {
          const gradeResult = await analysisApi.analyze(response.preview_text, 'Simplification Preview');
          setSimplifiedGrade(gradeResult.analysis.predictions.predicted_grade_level);
        } catch {
          // Non-critical — just skip the preview
        } finally {
          setGradeLoading(false);
        }
      }
    } catch (error) {
      console.error('Simplification error:', error);
      alert('Failed to simplify text. Make sure the ML service is running.');
    }
    setLoading(false);
  };

  const handleAccept = (changeId: number) => {
    const newChanges = changes.map((c) =>
      c.id === changeId ? { ...c, accepted: true } : c
    );
    setChanges(newChanges);
    rebuildText(newChanges);
  };

  const handleDeny = (changeId: number) => {
    const newChanges = changes.map((c) =>
      c.id === changeId ? { ...c, accepted: false } : c
    );
    setChanges(newChanges);
    rebuildText(newChanges);
  };

  const rebuildText = (updatedChanges: Change[]) => {
    let text = originalText;
    // Apply all changes that are NOT denied (accepted + pending)
    // This ensures pending changes are visible in the text for highlighting
    updatedChanges
      .filter((c) => c.accepted !== false)
      .forEach((change) => {
        text = text.replace(change.original, change.simplified);
      });
    setSimplifiedText(text);
  };

  const handleSave = async () => {
    if (!analysisId || !simplifiedText) return;
    setSaving(true);
    try {
      const acceptedChanges = changes.filter((c) => c.accepted === true);

      // Save to simplification history
      await simplifyApi.save({
        analysisId: parseInt(analysisId),
        simplifiedText,
        targetGrade,
        changes: acceptedChanges,
        mode,
      });

      // Create a new analysis from the rewritten text so the user can see the new grade
      const gradeLabel = targetGrade === 13 ? 'College' : `Grade ${targetGrade}`;
      const newResult = await analysisApi.analyze(
        simplifiedText,
        `Rewritten to ${gradeLabel}`
      );

      // Navigate to the newly created analysis
      navigate(`/analysis/${newResult.analysisId}`, {
        state: { analysis: newResult, originalText: simplifiedText },
      });
    } catch (error) {
      console.error('Save error:', error);
      alert('Failed to save. Please try again.');
    }
    setSaving(false);
  };

  const handleChangeHover = (changeId: number | null, event?: React.MouseEvent) => {
    setHoveredChange(changeId);
    if (event && changeId !== null) {
      setTooltipPos({ x: event.clientX, y: event.clientY });
    }
  };

  const hoveredChangeData = changes.find((c) => c.id === hoveredChange);

  const acceptedCount = changes.filter((c) => c.accepted === true).length;
  const deniedCount = changes.filter((c) => c.accepted === false).length;
  const pendingCount = changes.filter((c) => c.accepted === null).length;

  if (loadingText) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      {loading && <LoadingSpinner message="Rewriting text..." fullScreen />}
      {/* Header */}
      <div className="mb-6">
        <Link
          to={`/analysis/${analysisId}`}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-800 mb-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Analysis
        </Link>
        <h1 className="text-3xl font-bold text-gray-800">Text Rewrite</h1>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex flex-wrap gap-6 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Target Grade Level
            </label>
            <select
              value={targetGrade}
              onChange={(e) => setTargetGrade(+e.target.value)}
              className="border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              {[3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13].map((g) => (
                <option key={g} value={g}>
                  {g === 13 ? 'College' : `Grade ${g}`}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Mode</label>
            <div className="flex gap-2">
              <button
                onClick={() => setMode('auto')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  mode === 'auto'
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Auto Mode
              </button>
              <button
                onClick={() => setMode('interactive')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  mode === 'interactive'
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                Interactive Mode
              </button>
            </div>
          </div>

          <div className="ml-auto flex gap-3">
            <button
              onClick={handleSimplify}
              disabled={loading || !originalText}
              className="flex items-center gap-2 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Wand2 className="w-4 h-4" />
              )}
              {loading ? 'Processing...' : 'Rewrite'}
            </button>

            {simplifiedText && (
              <>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-2 px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={() => exportSimplificationPDF({
                    originalText,
                    simplifiedText,
                    targetGrade,
                    changes: changes.filter(c => c.accepted === true),
                  })}
                  className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
                >
                  <Download className="w-4 h-4" />
                  Export PDF
                </button>
                <button
                  onClick={() => exportSimplificationDOCX({
                    originalText,
                    simplifiedText,
                    targetGrade,
                    changes: changes.filter(c => c.accepted === true),
                  })}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  <FileText className="w-4 h-4" />
                  Export DOCX
                </button>
              </>
            )}
          </div>
        </div>

        <p className="text-sm text-gray-500 mt-4">
          {mode === 'auto'
            ? 'Auto Mode: AI rewrites the text to the target grade. Rule-based changes are listed below for reference.'
            : 'Interactive Mode: Rule-based changes only — hover over highlighted words to see the reason, then Accept or Deny each change.'}
        </p>
      </div>

      {/* Stats bar */}
      {changes.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
          <div className="flex items-center gap-6 text-sm">
            <span className="font-medium text-gray-700">
              {changes.length} change{changes.length !== 1 ? 's' : ''} suggested
            </span>
            <span className="text-green-600">
              {acceptedCount} accepted
            </span>
            <span className="text-red-600">
              {deniedCount} denied
            </span>
            {pendingCount > 0 && (
              <span className="text-yellow-600">
                {pendingCount} pending
              </span>
            )}
          </div>
        </div>
      )}

      {/* Score Preview */}
      {(originalGrade || simplifiedGrade) && simplifiedText && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
          <div className="flex items-center gap-4">
            {targetGrade >= 13 || (originalGrade && simplifiedGrade && simplifiedGrade > originalGrade)
              ? <TrendingUp className="w-5 h-5 text-purple-600" />
              : <TrendingDown className="w-5 h-5 text-primary-600" />
            }
            <span className="text-sm font-medium text-gray-700">Grade Preview:</span>
            <span className="px-3 py-1 bg-red-100 text-red-700 rounded-full text-sm font-semibold">
              {originalGrade || '...'}
            </span>
            <span className="text-gray-400 text-lg">&rarr;</span>
            {gradeLoading ? (
              <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
            ) : (
              <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-semibold">
                {simplifiedGrade || '...'}
              </span>
            )}
            {originalGrade && simplifiedGrade && !gradeLoading && (
              <span className="text-xs text-gray-500 ml-2">
                (Target: {targetGrade === 13 ? 'College' : `Grade ${targetGrade}`})
              </span>
            )}
          </div>
        </div>
      )}

      {/* Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Original */}
        <div className="bg-red-50 border border-red-200 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-red-800 mb-4">Original Text</h3>
          <div className="prose max-w-none text-gray-800 whitespace-pre-wrap leading-relaxed">
            {originalText || (
              <span className="text-gray-400 italic">No text loaded</span>
            )}
          </div>
        </div>

        {/* Simplified */}
        <div className="bg-green-50 border border-green-200 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-green-800 mb-4">
            Rewritten Text ({targetGrade === 13 ? 'College' : `Grade ${targetGrade}`})
          </h3>
          {simplifiedText ? (
            <div className="prose max-w-none leading-relaxed">
              <HighlightedText
                text={simplifiedText}
                changes={changes}
                mode={mode}
                hoveredChange={hoveredChange}
                onHover={handleChangeHover}
                onAccept={handleAccept}
                onDeny={handleDeny}
              />
            </div>
          ) : (
            <p className="text-gray-400 italic">
              Click "Rewrite" to generate a rewritten version...
            </p>
          )}
        </div>
      </div>

      {/* Tooltip */}
      {hoveredChangeData && (
        <div
          className="fixed z-50 bg-white rounded-lg shadow-xl border border-gray-200 p-4 max-w-sm"
          style={{
            left: Math.min(tooltipPos.x + 10, window.innerWidth - 400),
            top: Math.min(tooltipPos.y + 10, window.innerHeight - 200),
          }}
        >
          <div className="text-sm">
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs font-medium">
                {hoveredChangeData.type === 'word_replacement'
                  ? 'Word Replacement'
                  : hoveredChangeData.type === 'sentence_split'
                  ? 'Sentence Split'
                  : 'AI Enhanced'}
              </span>
            </div>
            <p className="text-gray-700 mb-3">{hoveredChangeData.reason}</p>

            {mode === 'interactive' && hoveredChangeData.accepted === null && (
              <div className="flex gap-2">
                <button
                  onClick={() => handleAccept(hoveredChangeData.id)}
                  className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white rounded text-xs font-medium hover:bg-green-700"
                >
                  <Check className="w-3 h-3" /> Accept
                </button>
                <button
                  onClick={() => handleDeny(hoveredChangeData.id)}
                  className="flex items-center gap-1 px-3 py-1.5 bg-red-600 text-white rounded text-xs font-medium hover:bg-red-700"
                >
                  <X className="w-3 h-3" /> Deny
                </button>
              </div>
            )}

            {hoveredChangeData.accepted === true && (
              <span className="text-green-600 text-xs font-medium">Accepted</span>
            )}
            {hoveredChangeData.accepted === false && (
              <span className="text-red-600 text-xs font-medium">Denied</span>
            )}
          </div>
        </div>
      )}

      {/* Changes List */}
      {changes.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mt-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">All Changes</h3>
          <div className="space-y-3">
            {changes.map((change) => (
              <div
                key={change.id}
                className={`p-4 rounded-lg border-l-4 ${
                  change.accepted === true
                    ? 'bg-green-50 border-green-400'
                    : change.accepted === false
                    ? 'bg-red-50 border-red-400'
                    : 'bg-yellow-50 border-yellow-400'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-medium">
                        {change.type === 'word_replacement'
                          ? 'Word'
                          : change.type === 'sentence_split' || change.type === 'sentence_combine'
                          ? 'Sentence'
                          : 'Structure'}
                      </span>
                      <span className="text-sm text-red-600 line-through">
                        {change.original}
                      </span>
                      <span className="text-gray-400">-&gt;</span>
                      <span className="text-sm text-green-600 font-medium">
                        {change.simplified}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">{change.reason}</p>
                  </div>

                  {mode === 'interactive' && (
                    <div className="flex gap-2 ml-4">
                      <button
                        onClick={() => handleAccept(change.id)}
                        className={`p-1.5 rounded transition-colors ${
                          change.accepted === true
                            ? 'bg-green-600 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-green-100 hover:text-green-700'
                        }`}
                        title="Accept"
                      >
                        <Check className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDeny(change.id)}
                        className={`p-1.5 rounded transition-colors ${
                          change.accepted === false
                            ? 'bg-red-600 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-red-100 hover:text-red-700'
                        }`}
                        title="Deny"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// Component to highlight changes inline
interface HighlightedTextProps {
  text: string;
  changes: Change[];
  mode: 'auto' | 'interactive';
  hoveredChange: number | null;
  onHover: (id: number | null, event?: React.MouseEvent) => void;
  onAccept: (id: number) => void;
  onDeny: (id: number) => void;
}

const HighlightedText: React.FC<HighlightedTextProps> = ({
  text,
  changes,
  mode,
  hoveredChange,
  onHover,
  onAccept,
  onDeny,
}) => {
  // In auto mode: highlight accepted changes (green)
  // In interactive mode: highlight accepted (green) AND pending (yellow/orange)
  const relevantChanges = changes.filter((c) => {
    if (c.accepted === false) return false; // skip denied
    if (mode === 'auto') return c.accepted === true;
    return true; // interactive: show accepted + pending
  });

  // For word replacements, find them in the simplified text
  const wordChanges = relevantChanges.filter((c) => c.type === 'word_replacement');

  // For sentence splits/combines, we also need to highlight them
  const sentenceChanges = relevantChanges.filter(
    (c) => c.type === 'sentence_split' || c.type === 'sentence_combine'
  );

  if (wordChanges.length === 0 && sentenceChanges.length === 0) {
    return <span className="text-gray-800 whitespace-pre-wrap">{text}</span>;
  }

  // Build highlight regions
  const highlights: { start: number; end: number; change: Change }[] = [];

  // Track used positions to prevent overlapping highlights
  const usedRanges: { start: number; end: number }[] = [];

  const isOverlapping = (start: number, end: number) => {
    return usedRanges.some(
      (r) => (start >= r.start && start < r.end) || (end > r.start && end <= r.end)
    );
  };

  // Helper: check if a character is a word boundary (non-alphanumeric)
  const isWordBoundary = (ch: string | undefined) =>
    !ch || /[^a-zA-Z0-9]/.test(ch);

  // Helper: find a word/phrase at a word boundary, searching from startFrom
  const findWholeWord = (haystack: string, needle: string, startFrom: number = 0): number => {
    let searchPos = startFrom;
    while (searchPos < haystack.length) {
      const idx = haystack.indexOf(needle, searchPos);
      if (idx === -1) return -1;
      // Check word boundaries
      const before = idx > 0 ? haystack[idx - 1] : undefined;
      const after = haystack[idx + needle.length];
      if (isWordBoundary(before) && isWordBoundary(after)) {
        return idx;
      }
      searchPos = idx + 1;
    }
    return -1;
  };

  // Word replacement highlights - find simplified words at word boundaries
  // Sort by position to search text in order
  const sortedWordChanges = [...wordChanges].sort((a, b) => a.position - b.position);
  for (const change of sortedWordChanges) {
    const idx = findWholeWord(text, change.simplified);
    if (idx !== -1 && !isOverlapping(idx, idx + change.simplified.length)) {
      highlights.push({
        start: idx,
        end: idx + change.simplified.length,
        change,
      });
      usedRanges.push({ start: idx, end: idx + change.simplified.length });
    }
  }

  // Sentence split highlights - find simplified sentence text
  for (const change of sentenceChanges) {
    const idx = text.indexOf(change.simplified);
    if (idx !== -1 && !isOverlapping(idx, idx + change.simplified.length)) {
      highlights.push({
        start: idx,
        end: idx + change.simplified.length,
        change,
      });
      usedRanges.push({ start: idx, end: idx + change.simplified.length });
    }
  }

  // Sort by position
  highlights.sort((a, b) => a.start - b.start);

  const parts: React.ReactNode[] = [];
  let key = 0;
  let pos = 0;

  for (const h of highlights) {
    if (h.start > pos) {
      parts.push(
        <span key={key++} className="text-gray-800">
          {text.slice(pos, h.start)}
        </span>
      );
    }

    const isPending = h.change.accepted === null;

    // Different styles for pending vs accepted
    let highlightClass = 'px-0.5 rounded cursor-help transition-colors ';
    if (hoveredChange === h.change.id) {
      highlightClass += isPending
        ? 'bg-amber-400 text-amber-900'
        : 'bg-green-400 text-green-900';
    } else {
      highlightClass += isPending
        ? 'bg-amber-100 text-amber-800 border-b-2 border-amber-400'
        : 'bg-green-200 text-green-800';
    }

    parts.push(
      <span
        key={key++}
        className={highlightClass}
        onMouseEnter={(e) => onHover(h.change.id, e)}
        onMouseLeave={() => onHover(null)}
      >
        {text.slice(h.start, h.end)}
        {mode === 'interactive' && isPending && (
          <span className="inline-flex ml-1 gap-0.5 align-middle">
            <button
              onClick={(e) => { e.stopPropagation(); onAccept(h.change.id); }}
              className="inline-flex items-center justify-center w-4 h-4 bg-green-500 text-white rounded-full text-xs hover:bg-green-700 leading-none"
              title="Accept"
            >
              &#10003;
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDeny(h.change.id); }}
              className="inline-flex items-center justify-center w-4 h-4 bg-red-500 text-white rounded-full text-xs hover:bg-red-700 leading-none"
              title="Deny"
            >
              &#10005;
            </button>
          </span>
        )}
      </span>
    );
    pos = h.end;
  }

  if (pos < text.length) {
    parts.push(
      <span key={key++} className="text-gray-800">
        {text.slice(pos)}
      </span>
    );
  }

  return <span className="whitespace-pre-wrap">{parts}</span>;
};

export default SimplifyPage;
