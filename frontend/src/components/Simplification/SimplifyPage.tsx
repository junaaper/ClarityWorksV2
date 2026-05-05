import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Loader2, Save, Wand2, Check, X, Download, FileText, TrendingDown, TrendingUp } from 'lucide-react';
import { analysisApi, simplifyApi } from '../../services/api';
import LoadingSpinner from '../common/LoadingSpinner';
import { exportSimplificationPDF, exportSimplificationDOCX } from '../../utils/exportSimplification';
import type {
  SimplificationChange,
  SimplificationPreviewMetrics,
  SimplificationSelectionSummary,
} from '../../types';

type Change = SimplificationChange & {
  accepted: boolean | null;
};

type ChangeRange = {
  start: number;
  end: number;
};

const computeTargetDistance = (rawScore: number | undefined, targetGrade: number) => {
  if (typeof rawScore !== 'number') return undefined;
  if (targetGrade >= 13) {
    return rawScore >= 13 ? 0 : Number((13 - rawScore).toFixed(2));
  }
  if (rawScore < targetGrade) {
    return Number((targetGrade - rawScore).toFixed(2));
  }
  if (rawScore >= targetGrade + 1) {
    return Number((rawScore - (targetGrade + 1)).toFixed(2));
  }
  return 0;
};

const getScopeLabel = (scope?: Change['review_scope']) => {
  switch (scope) {
    case 'paragraph':
      return 'Paragraph Review';
    case 'sentence':
      return 'Sentence Review';
    case 'word':
      return 'Word Review';
    default:
      return null;
  }
};

const isFinalReviewSummary = (change: Pick<Change, 'final_reviewed' | 'review_scope'>) =>
  Boolean(change.final_reviewed && change.review_scope === 'paragraph');

const isBroadParagraphRewrite = (
  change: Pick<Change, 'type' | 'review_scope' | 'quality_flags' | 'validation_flags' | 'explanation_items'>
) => Boolean(
  change.review_scope === 'paragraph' && (
    change.type === 'phrase_rewrite' ||
    (change.explanation_items?.length ?? 0) > 0 ||
    change.quality_flags?.includes('coarse_review') ||
    change.quality_flags?.includes('forced_exact_rebuild') ||
    change.validation_flags?.includes('exact_preview_rebuild')
  )
);

const shouldHideChangeSnippet = (
  change: Pick<Change, 'type' | 'original' | 'simplified' | 'final_reviewed' | 'review_scope' | 'quality_flags' | 'validation_flags' | 'explanation_items'>
) => isFinalReviewSummary(change) || isBroadParagraphRewrite(change) || (!change.original && !change.simplified);

const getChangeLabel = (
  change: Pick<Change, 'type' | 'review_scope' | 'final_reviewed' | 'quality_flags' | 'validation_flags' | 'explanation_items'>
) => {
  if (isFinalReviewSummary(change)) {
    return 'Final Review Adjustment';
  }

  if (isBroadParagraphRewrite(change)) {
    return 'Paragraph Rewrite';
  }

  if (change.review_scope === 'paragraph') {
    switch (change.type) {
      case 'sentence_split':
        return 'Paragraph Split';
      case 'sentence_combine':
        return 'Paragraph Combine';
      case 'phrase_rewrite':
        return 'Paragraph Rewrite';
      default:
        return 'Paragraph Change';
    }
  }

  switch (change.type) {
    case 'word_replacement':
      return 'Word Replacement';
    case 'word_upgrade':
      return 'Word Upgrade';
    case 'sentence_split':
      return 'Sentence Split';
    case 'sentence_combine':
      return 'Sentence Combine';
    case 'phrase_rewrite':
      return 'Phrase Rewrite';
    case 'flow_polish':
      return 'Flow Polish';
    default:
      return 'Structure';
  }
};

const getChangeSummaryText = (change: Change) => {
  if (isBroadParagraphRewrite(change)) {
    const evidenceCount = change.explanation_items?.length ?? 0;
    return evidenceCount
      ? `Paragraph rewrite with ${evidenceCount} evidence-backed change${evidenceCount === 1 ? '' : 's'}.`
      : 'Paragraph rewrite kept as one exact preview patch.';
  }
  if (change.review_scope === 'paragraph') {
    return 'Paragraph adjusted during the final meaning check.';
  }
  if (change.review_scope === 'sentence') {
    return change.reason || 'Sentence structure adjusted.';
  }
  return 'Wording adjusted during the final meaning check.';
};

type ExplanationItem = NonNullable<Change['explanation_items']>[number];

const getEvidenceLabel = (item: ExplanationItem) => {
  switch (item.kind) {
    case 'word_upgrade':
      return 'Word Upgrade';
    case 'word_replacement':
      return 'Word Replacement';
    case 'connector_added':
      return 'Connector';
    default:
      return 'Evidence';
  }
};

const getEvidenceAccent = (item: ExplanationItem) =>
  item.kind === 'word_replacement' ? 'var(--err-500)' : 'var(--s-500)';

const EvidenceItems: React.FC<{
  items?: Change['explanation_items'];
  limit?: number;
  compact?: boolean;
}> = ({ items, limit = 5, compact = false }) => {
  const visibleItems = (items ?? []).slice(0, limit);
  if (!visibleItems.length) return null;

  return (
    <div className={compact ? 'space-y-1' : 'mt-2 space-y-1.5'}>
      {visibleItems.map((item, index) => {
        const accent = getEvidenceAccent(item);
        const hasWordPair = Boolean(item.before && item.after);
        return (
          <div
            key={`evidence-${index}-${item.before ?? item.after ?? item.kind}`}
            className="rounded-sm"
            style={{
              borderLeft: `2px solid color-mix(in srgb, ${accent} 42%, transparent)`,
              background: compact ? 'transparent' : 'color-mix(in srgb, var(--surface-sunk) 46%, transparent)',
              padding: compact ? '2px 0 2px 8px' : '6px 8px',
            }}
          >
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="cw-badge cw-badge-neutral">{getEvidenceLabel(item)}</span>
              {hasWordPair ? (
                <>
                  <span style={{ fontSize: 11.5, color: 'var(--err-700)', textDecoration: 'line-through' }}>
                    {item.before}
                  </span>
                  <span style={{ color: 'var(--text-4)', fontSize: 11.5 }}>→</span>
                  <span style={{ fontSize: 11.5, color: 'var(--s-700)', fontWeight: 700 }}>
                    {item.after}
                  </span>
                  {typeof item.frequency_before === 'number' && typeof item.frequency_after === 'number' && (
                    <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                      Zipf {item.frequency_before.toFixed(1)} → {item.frequency_after.toFixed(1)}
                    </span>
                  )}
                  {typeof item.syllables_before === 'number' && typeof item.syllables_after === 'number' && (
                    <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                      {item.syllables_before} → {item.syllables_after} syll.
                    </span>
                  )}
                </>
              ) : (
                <span style={{ fontSize: 11.5, color: 'var(--text-2)' }}>{item.text}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const getReplacementPatchText = (change: Change) =>
  change.replacement_text ?? change.simplified ?? '';

const normalizeChange = (
  change: SimplificationChange,
  mode: 'auto' | 'interactive'
): Change => {
  const start = change.start ?? change.position ?? 0;
  const originalPatchText = change.original_text ?? change.original ?? '';
  const inferredEnd = start + originalPatchText.length;

  return {
    ...change,
    position: change.position ?? start,
    start,
    end: change.end ?? inferredEnd,
    accepted: mode === 'auto' ? true : null,
  };
};

const buildPreviewState = (
  sourceText: string,
  updatedChanges: Change[],
  mode: 'auto' | 'interactive'
): { text: string; ranges: Record<number, ChangeRange> } => {
  const includedChanges = updatedChanges
    .filter((change) => {
      if (mode === 'auto') {
        return change.accepted === true;
      }
      return change.accepted !== false;
    })
    .sort((a, b) => {
      if (a.start !== b.start) return a.start - b.start;
      if (a.end !== b.end) return b.end - a.end;
      return a.id - b.id;
    });

  if (includedChanges.length === 0) {
    return { text: sourceText, ranges: {} };
  }

  let cursor = 0;
  let previewText = '';
  const ranges: Record<number, ChangeRange> = {};

  for (const change of includedChanges) {
    const start = Math.max(0, Math.min(sourceText.length, change.start));
    const end = Math.max(start, Math.min(sourceText.length, change.end));

    if (start < cursor) {
      continue;
    }

    previewText += sourceText.slice(cursor, start);

    const replacementText = getReplacementPatchText(change);
    const appliedStart = previewText.length;
    previewText += replacementText;

    const visibleLeading = replacementText.length - replacementText.trimStart().length;
    const visibleTrailing = replacementText.length - replacementText.trimEnd().length;
    const visibleStart = appliedStart + visibleLeading;
    const visibleEnd = Math.max(visibleStart, appliedStart + replacementText.length - visibleTrailing);

    ranges[change.id] = { start: visibleStart, end: visibleEnd };
    cursor = end;
  }

  previewText += sourceText.slice(cursor);
  return { text: previewText, ranges };
};

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
  const [renderedRanges, setRenderedRanges] = useState<Record<number, ChangeRange>>({});
  const [previewMetrics, setPreviewMetrics] = useState<SimplificationPreviewMetrics | null>(null);
  const [selectionSummary, setSelectionSummary] = useState<SimplificationSelectionSummary | null>(null);

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

  useEffect(() => {
    if (!simplifiedText || simplifiedText.length < 50) {
      setSimplifiedGrade(null);
      return;
    }

    let cancelled = false;
    const timeoutId = window.setTimeout(async () => {
      setGradeLoading(true);
      try {
        const gradeResult = await analysisApi.preview(simplifiedText);
        if (cancelled) return;

        const rawScore = gradeResult.analysis.predictions.raw_score;
        setSimplifiedGrade(gradeResult.analysis.predictions.predicted_grade_level);
        setPreviewMetrics((current) => ({
          raw_score: typeof rawScore === 'number' ? rawScore : current?.raw_score ?? targetGrade,
          predicted_grade_level: gradeResult.analysis.predictions.predicted_grade_level,
          predicted_complexity: gradeResult.analysis.predictions.predicted_complexity,
          avg_syllables_per_word: current?.avg_syllables_per_word ?? 0,
          avg_words_per_sentence: current?.avg_words_per_sentence ?? 0,
          invalid_sentence_count: current?.invalid_sentence_count ?? 0,
          semantic_similarity_score: current?.semantic_similarity_score ?? 0,
          target_distance: computeTargetDistance(rawScore, targetGrade) ?? current?.target_distance ?? 0,
        }));
      } catch {
        if (!cancelled) {
          setSimplifiedGrade(null);
        }
      } finally {
        if (!cancelled) {
          setGradeLoading(false);
        }
      }
    }, 200);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [simplifiedText, targetGrade]);

  const handleSimplify = async () => {
    if (!analysisId) return;
    setLoading(true);
    try {
      const response = await simplifyApi.analyze({
        analysisId: parseInt(analysisId),
        targetGrade,
        mode,
      });

      const sourceText = response.original_text || originalText;
      const newChanges: Change[] = (response.suggested_changes || []).map((change) =>
        normalizeChange(change, mode)
      );

      const previewState = buildPreviewState(sourceText, newChanges, mode);
      const previewText = newChanges.length > 0 ? previewState.text : (response.preview_text || sourceText);
      const ranges = previewState.ranges;

      setChanges(newChanges);
      setRenderedRanges(ranges);
      setSimplifiedText(previewText);
      setPreviewMetrics(response.preview_metrics ?? null);
      setSelectionSummary(response.selection_summary ?? null);
      setSimplifiedGrade(response.preview_metrics?.predicted_grade_level ?? null);
    } catch (error) {
      console.error('Simplification error:', error);
      alert('Failed to simplify text. Make sure the ML service is running.');
    }
    setLoading(false);
  };

  const getLinkedChangeIds = (changeId: number) => {
    const selectedChange = changes.find((change) => change.id === changeId);
    if (!selectedChange) {
      return [changeId];
    }
    const isLinkedStructuralChange =
      selectedChange.type === 'sentence_split' ||
      selectedChange.type === 'sentence_combine';
    if (!selectedChange.dependency_group_id || !isLinkedStructuralChange) {
      return [changeId];
    }
    return changes
      .filter(
        (change) =>
          change.dependency_group_id === selectedChange.dependency_group_id &&
          (change.type === 'sentence_split' || change.type === 'sentence_combine')
      )
      .map((change) => change.id);
  };

  const handleAccept = (changeId: number) => {
    const linkedIds = new Set(getLinkedChangeIds(changeId));
    const newChanges = changes.map((c) =>
      linkedIds.has(c.id) ? { ...c, accepted: true } : c
    );
    setChanges(newChanges);
    rebuildText(newChanges);
  };

  const handleDeny = (changeId: number) => {
    const linkedIds = new Set(getLinkedChangeIds(changeId));
    const newChanges = changes.map((c) =>
      linkedIds.has(c.id) ? { ...c, accepted: false } : c
    );
    setChanges(newChanges);
    rebuildText(newChanges);
  };

  const rebuildText = (updatedChanges: Change[]) => {
    const previewState = buildPreviewState(originalText, updatedChanges, mode);
    setRenderedRanges(previewState.ranges);
    setSimplifiedText(previewState.text);
  };

  const handleSave = async () => {
    if (!analysisId || !simplifiedText) return;
    setSaving(true);
    try {
      const acceptedChanges = changes.filter((c) => c.accepted === true);
      let finalText = simplifiedText;

      if (mode === 'interactive') {
        const applyResult = await simplifyApi.apply({
          text: originalText,
          acceptedChanges: acceptedChanges.map((c) => c.id),
          allChanges: changes,
        });
        finalText = applyResult.simplified_text || originalText;
      }

      // Save to simplification history
      await simplifyApi.save({
        analysisId: parseInt(analysisId),
        simplifiedText: finalText,
        targetGrade,
        changes: acceptedChanges,
        mode,
      });

      // Create a new analysis from the rewritten text so the user can see the new grade
      const gradeLabel = targetGrade === 13 ? 'College' : `Grade ${targetGrade}`;
      const newResult = await analysisApi.analyze(
        finalText,
        `Rewritten to ${gradeLabel}`
      );

      // Navigate to the newly created analysis
      navigate(`/analysis/${newResult.analysisId}`, {
        state: { analysis: newResult, originalText: finalText },
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
  const displayedPreviewGrade = previewMetrics?.predicted_grade_level ?? simplifiedGrade;
  const linkedGroupCount = new Set(
    changes
      .map((change) => change.dependency_group_id)
      .filter((groupId): groupId is string => Boolean(groupId))
  ).size;
  if (loadingText) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    );
  }

  const upgrading = targetGrade >= 13 || (selectionSummary && selectionSummary.target_grade > selectionSummary.source_grade);

  return (
    <div>
      {loading && <LoadingSpinner message="Rewriting text..." fullScreen />}

      {/* Header */}
      <Link
        to={`/analysis/${analysisId}`}
        className="inline-flex items-center gap-1.5 mb-4"
        style={{ color: 'var(--text-3)', fontSize: 12, fontWeight: 500 }}
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Back to Analysis
      </Link>

      <div className="mb-6">
        <div className="cw-eyebrow mb-2">Rewrite Workbench</div>
        <h1 className="cw-hero" style={{ fontSize: 28 }}>Text Rewrite</h1>
      </div>

      {/* Controls */}
      <div className="cw-card cw-card-pad-lg mb-5">
        <div className="flex flex-wrap gap-5 items-end">
          <div>
            <label className="cw-eyebrow block mb-1.5">Target Grade</label>
            <select
              value={targetGrade}
              onChange={(e) => setTargetGrade(+e.target.value)}
              className="cw-select"
              style={{ minWidth: 160 }}
            >
              {[3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13].map((g) => (
                <option key={g} value={g}>
                  {g === 13 ? 'College' : `Grade ${g}`}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="cw-eyebrow block mb-1.5">Mode</label>
            <div
              className="inline-flex p-0.5 rounded-md"
              style={{ background: 'var(--surface-sunk)', border: '1px solid var(--border)' }}
            >
              <button
                onClick={() => setMode('auto')}
                className="px-3.5 py-1.5 rounded text-[12px] font-semibold transition-colors"
                style={{
                  background: mode === 'auto' ? 'var(--surface-raised)' : 'transparent',
                  color: mode === 'auto' ? 'var(--p-900)' : 'var(--text-2)',
                  boxShadow: mode === 'auto' ? 'var(--sh-1)' : 'none',
                }}
              >
                Auto
              </button>
              <button
                onClick={() => setMode('interactive')}
                className="px-3.5 py-1.5 rounded text-[12px] font-semibold transition-colors"
                style={{
                  background: mode === 'interactive' ? 'var(--surface-raised)' : 'transparent',
                  color: mode === 'interactive' ? 'var(--p-900)' : 'var(--text-2)',
                  boxShadow: mode === 'interactive' ? 'var(--sh-1)' : 'none',
                }}
              >
                Interactive
              </button>
            </div>
          </div>

          <div className="ml-auto flex gap-2 flex-wrap">
            <button
              onClick={handleSimplify}
              disabled={loading || !originalText}
              className="cw-btn cw-btn-primary"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
              {loading ? 'Processing…' : 'Rewrite'}
            </button>

            {simplifiedText && (
              <>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="cw-btn cw-btn-teal"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {saving ? 'Saving…' : 'Save'}
                </button>
                <button
                  onClick={() => exportSimplificationPDF({
                    originalText,
                    simplifiedText,
                    targetGrade,
                    changes: changes.filter(c => c.accepted === true),
                  })}
                  className="cw-btn cw-btn-secondary"
                >
                  <Download className="w-4 h-4" />
                  PDF
                </button>
                <button
                  onClick={() => exportSimplificationDOCX({
                    originalText,
                    simplifiedText,
                    targetGrade,
                    changes: changes.filter(c => c.accepted === true),
                  })}
                  className="cw-btn cw-btn-secondary"
                >
                  <FileText className="w-4 h-4" />
                  DOCX
                </button>
              </>
            )}
          </div>
        </div>

        <p className="mt-4" style={{ color: 'var(--text-3)', fontSize: 12, lineHeight: 1.55 }}>
          {mode === 'auto'
            ? 'Auto Mode — the system tries multiple rewrite candidates, keeps the closest valid version, and shows reviewable change reasons.'
            : 'Interactive Mode — hover any highlight for the reason, then Accept or Deny each change before saving.'}
        </p>
      </div>

      {/* Stats bar */}
      {changes.length > 0 && (
        <div className="cw-card cw-card-pad mb-5">
          <div className="flex items-center gap-3 flex-wrap" style={{ fontSize: 12 }}>
            <span className="cw-badge cw-badge-neutral">
              {changes.length} change{changes.length !== 1 ? 's' : ''}
            </span>
            <span className="cw-badge cw-badge-ok">{acceptedCount} accepted</span>
            <span className="cw-badge cw-badge-err">{deniedCount} denied</span>
            {pendingCount > 0 && (
              <span className="cw-badge cw-badge-warn">{pendingCount} pending</span>
            )}
            {linkedGroupCount > 0 && (
              <span className="cw-badge cw-badge-info">
                {linkedGroupCount} linked group{linkedGroupCount !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Score Preview */}
      {(originalGrade || displayedPreviewGrade) && simplifiedText && (
        <div className="cw-card cw-card-pad mb-5">
          <div className="flex items-center gap-3 flex-wrap">
            {upgrading
              ? <TrendingUp className="w-4 h-4" style={{ color: 'var(--s-500)' }} />
              : <TrendingDown className="w-4 h-4" style={{ color: 'var(--p-700)' }} />
            }
            <span className="cw-eyebrow">Grade Preview</span>
            <span className="cw-badge cw-badge-err">{originalGrade || '…'}</span>
            <span style={{ color: 'var(--text-4)', fontSize: 14 }}>→</span>
            {gradeLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--p-700)' }} />
            ) : (
              <span className="cw-badge cw-badge-ok">{displayedPreviewGrade || '…'}</span>
            )}
            {originalGrade && displayedPreviewGrade && !gradeLoading && (
              <span style={{ fontSize: 11, color: 'var(--text-3)' }}>
                (Target: {targetGrade === 13 ? 'College' : `Grade ${targetGrade}`})
              </span>
            )}
            {previewMetrics && (
              <span style={{ fontSize: 11, color: 'var(--text-4)', fontFamily: 'var(--font-mono)' }}>
                Raw {previewMetrics.raw_score.toFixed(2)}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Original */}
        <div
          className="cw-card-flush p-6"
          style={{
            background: 'color-mix(in srgb, var(--err-500) 5%, var(--surface-raised))',
            border: '1px solid color-mix(in srgb, var(--err-500) 18%, transparent)',
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="cw-eyebrow" style={{ color: 'var(--err-700)' }}>Original</span>
          </div>
          <div
            className="whitespace-pre-wrap"
            style={{ color: 'var(--text-1)', fontSize: 13.5, lineHeight: 1.65, fontFamily: 'var(--font-serif)' }}
          >
            {originalText || (
              <span style={{ color: 'var(--text-4)', fontStyle: 'italic' }}>No text loaded</span>
            )}
          </div>
        </div>

        {/* Simplified */}
        <div
          className="cw-card-flush p-6"
          style={{
            background: 'color-mix(in srgb, var(--s-500) 6%, var(--surface-raised))',
            border: '1px solid color-mix(in srgb, var(--s-500) 22%, transparent)',
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="cw-eyebrow" style={{ color: 'var(--s-700)' }}>
              Rewritten · {targetGrade === 13 ? 'College' : `Grade ${targetGrade}`}
            </span>
          </div>
          {simplifiedText ? (
            <div
              style={{ color: 'var(--text-1)', fontSize: 13.5, lineHeight: 1.65, fontFamily: 'var(--font-serif)' }}
            >
              <HighlightedText
                text={simplifiedText}
                changes={changes}
                ranges={renderedRanges}
                mode={mode}
                hoveredChange={hoveredChange}
                onHover={handleChangeHover}
                onAccept={handleAccept}
                onDeny={handleDeny}
              />
            </div>
          ) : (
            <p style={{ color: 'var(--text-4)', fontStyle: 'italic', fontSize: 13 }}>
              Click "Rewrite" to generate a rewritten version…
            </p>
          )}
        </div>
      </div>

      {/* Tooltip */}
      {hoveredChangeData && (
        <div
          className="fixed z-50 p-4 max-w-sm cw-card"
          style={{
            left: Math.min(tooltipPos.x + 10, window.innerWidth - 400),
            top: Math.min(tooltipPos.y + 10, window.innerHeight - 200),
            boxShadow: 'var(--sh-3)',
          }}
        >
          <div className="flex items-center gap-1.5 mb-2 flex-wrap">
            <span className="cw-badge cw-badge-primary">{getChangeLabel(hoveredChangeData)}</span>
            {getScopeLabel(hoveredChangeData.review_scope) && (
              <span className="cw-badge cw-badge-neutral">{getScopeLabel(hoveredChangeData.review_scope)}</span>
            )}
            {hoveredChangeData.final_reviewed && (
              <span className="cw-badge cw-badge-info">Final Review</span>
            )}
          </div>
          <p style={{ color: 'var(--text-2)', fontSize: 12.5, marginBottom: 10, lineHeight: 1.5 }}>
            {hoveredChangeData.reason}
          </p>
          <EvidenceItems items={hoveredChangeData.explanation_items} limit={4} compact />
          {hoveredChangeData.final_reviewed && hoveredChangeData.final_review_note && (
            <p style={{ color: 'var(--text-3)', fontSize: 11.5, marginBottom: 10, lineHeight: 1.5 }}>
              {hoveredChangeData.final_review_note}
            </p>
          )}

          {mode === 'interactive' && hoveredChangeData.accepted === null && (
            <div className="flex gap-2">
              <button
                onClick={() => handleAccept(hoveredChangeData.id)}
                className="cw-btn cw-btn-sm cw-btn-teal"
              >
                <Check className="w-3 h-3" /> Accept
              </button>
              <button
                onClick={() => handleDeny(hoveredChangeData.id)}
                className="cw-btn cw-btn-sm cw-btn-danger"
              >
                <X className="w-3 h-3" /> Deny
              </button>
            </div>
          )}
          {hoveredChangeData.accepted === true && (
            <span className="cw-badge cw-badge-ok">Accepted</span>
          )}
          {hoveredChangeData.accepted === false && (
            <span className="cw-badge cw-badge-err">Denied</span>
          )}
        </div>
      )}

      {/* Changes List */}
      {changes.length > 0 && (
        <div className="cw-card cw-card-pad-lg mt-5">
          <h3 className="cw-section-title mb-4">All Changes</h3>
          <div className="space-y-2.5">
            {changes.map((change) => {
              const accentColor =
                change.accepted === true ? 'var(--ok-500)' :
                change.accepted === false ? 'var(--err-500)' :
                'var(--warn-500)';
              const bgTint =
                change.accepted === true ? 'var(--ok-50)' :
                change.accepted === false ? 'var(--err-50)' :
                'var(--warn-50)';
              return (
                <div
                  key={change.id}
                  className="p-3.5 rounded-md"
                  style={{
                    background: `color-mix(in srgb, ${bgTint} 60%, var(--surface-raised))`,
                    borderLeft: `3px solid ${accentColor}`,
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
                        <span className="cw-badge cw-badge-neutral">{getChangeLabel(change)}</span>
                        {getScopeLabel(change.review_scope) && (
                          <span className="cw-badge cw-badge-neutral">{getScopeLabel(change.review_scope)}</span>
                        )}
                        {change.final_reviewed && (
                          <span className="cw-badge cw-badge-info">Final Review</span>
                        )}
                        {change.dependency_group_id && (
                          <span className="cw-badge cw-badge-info">Linked</span>
                        )}
                        {shouldHideChangeSnippet(change) ? (
                          <span style={{ fontSize: 12, color: 'var(--text-3)', fontStyle: 'italic' }}>
                            {getChangeSummaryText(change)}
                          </span>
                        ) : (
                          <>
                            <span style={{ fontSize: 12, color: 'var(--err-700)', textDecoration: 'line-through' }}>
                              {change.original}
                            </span>
                            <span style={{ color: 'var(--text-4)', fontSize: 12 }}>→</span>
                            <span style={{ fontSize: 12, color: 'var(--s-700)', fontWeight: 600 }}>
                              {change.simplified}
                            </span>
                          </>
                        )}
                      </div>
                      <p style={{ fontSize: 11.5, color: 'var(--text-3)', lineHeight: 1.5 }}>
                        {change.reason}
                      </p>
                      <EvidenceItems items={change.explanation_items} limit={5} />
                      {change.final_reviewed && change.final_review_note && (
                        <p style={{ fontSize: 11.5, color: 'var(--text-4)', lineHeight: 1.5, marginTop: 4 }}>
                          {change.final_review_note}
                        </p>
                      )}
                    </div>

                    {mode === 'interactive' && (
                      <div className="flex gap-1.5 flex-shrink-0">
                        <button
                          onClick={() => handleAccept(change.id)}
                          className="p-1.5 rounded transition-colors"
                          style={{
                            background: change.accepted === true ? 'var(--ok-500)' : 'var(--surface-sunk)',
                            color: change.accepted === true ? '#fff' : 'var(--text-2)',
                          }}
                          title="Accept"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeny(change.id)}
                          className="p-1.5 rounded transition-colors"
                          style={{
                            background: change.accepted === false ? 'var(--err-500)' : 'var(--surface-sunk)',
                            color: change.accepted === false ? '#fff' : 'var(--text-2)',
                          }}
                          title="Deny"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
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
  ranges: Record<number, ChangeRange>;
  mode: 'auto' | 'interactive';
  hoveredChange: number | null;
  onHover: (id: number | null, event?: React.MouseEvent) => void;
  onAccept: (id: number) => void;
  onDeny: (id: number) => void;
}

const HighlightedText: React.FC<HighlightedTextProps> = ({
  text,
  changes,
  ranges,
  mode,
  hoveredChange,
  onHover,
  onAccept,
  onDeny,
}) => {
  const accepted = changes.filter((change) => {
    if (change.accepted === false) return false;
    if (mode === 'auto') return change.accepted === true;
    return true;
  });

  const wordHighlights = accepted
    .filter((c) => c.review_scope === 'word' || !c.review_scope)
    .map((c) => { const r = ranges[c.id]; return r ? { start: Math.max(0, Math.min(text.length, r.start)), end: Math.max(0, Math.min(text.length, r.end)), change: c, scope: 'word' as const } : null; })
    .filter((h): h is NonNullable<typeof h> => Boolean(h && h.end > h.start))
    .sort((a, b) => a.start - b.start);

  const sentenceHighlights = accepted
    .filter((c) => c.review_scope === 'sentence' || c.review_scope === 'paragraph')
    .map((c) => { const r = ranges[c.id]; return r ? { start: Math.max(0, Math.min(text.length, r.start)), end: Math.max(0, Math.min(text.length, r.end)), change: c, scope: 'sentence' as const } : null; })
    .filter((h): h is NonNullable<typeof h> => Boolean(h && h.end > h.start))
    .sort((a, b) => a.start - b.start);

  type Segment = { start: number; end: number; change: Change; scope: 'word' | 'sentence' };
  const segments: Segment[] = [...wordHighlights];

  for (const sh of sentenceHighlights) {
    let cursor = sh.start;
    const overlapping = wordHighlights.filter((w) => w.start < sh.end && w.end > sh.start);
    for (const w of overlapping) {
      if (w.start > cursor) {
        segments.push({ start: cursor, end: w.start, change: sh.change, scope: 'sentence' });
      }
      cursor = Math.max(cursor, w.end);
    }
    if (cursor < sh.end) {
      segments.push({ start: cursor, end: sh.end, change: sh.change, scope: 'sentence' });
    }
  }

  segments.sort((a, b) => a.start !== b.start ? a.start - b.start : a.change.id - b.change.id);

  if (segments.length === 0) {
    return <span className="text-gray-800 whitespace-pre-wrap">{text}</span>;
  }

  const parts: React.ReactNode[] = [];
  let key = 0;
  let pos = 0;

  for (const seg of segments) {
    if (seg.start < pos) continue;
    if (seg.start > pos) {
      parts.push(
        <span key={key++} className="text-gray-800">
          {text.slice(pos, seg.start)}
        </span>
      );
    }

    const isPending = seg.change.accepted === null;
    const isWord = seg.scope === 'word';

    let highlightClass = 'px-0.5 rounded cursor-help transition-colors ';
    if (hoveredChange === seg.change.id) {
      highlightClass += isPending
        ? 'bg-amber-400 text-amber-900'
        : isWord ? 'bg-green-400 text-green-900' : 'bg-blue-300 text-blue-900';
    } else {
      highlightClass += isPending
        ? 'bg-amber-100 text-amber-800 border-b-2 border-amber-400'
        : isWord ? 'bg-green-200 text-green-800' : 'bg-blue-100 text-blue-800';
    }

    parts.push(
      <span
        key={key++}
        className={highlightClass}
        onMouseEnter={(e) => onHover(seg.change.id, e)}
        onMouseLeave={() => onHover(null)}
      >
        {text.slice(seg.start, seg.end)}
        {mode === 'interactive' && isPending && isWord && (
          <span className="inline-flex ml-1 gap-0.5 align-middle">
            <button
              onClick={(e) => { e.stopPropagation(); onAccept(seg.change.id); }}
              className="inline-flex items-center justify-center w-4 h-4 bg-green-500 text-white rounded-full text-xs hover:bg-green-700 leading-none"
              title="Accept"
            >
              &#10003;
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDeny(seg.change.id); }}
              className="inline-flex items-center justify-center w-4 h-4 bg-red-500 text-white rounded-full text-xs hover:bg-red-700 leading-none"
              title="Deny"
            >
              &#10005;
            </button>
          </span>
        )}
      </span>
    );
    pos = seg.end;
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
