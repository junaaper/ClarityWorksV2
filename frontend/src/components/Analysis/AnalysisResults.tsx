import React, { useEffect, useState } from 'react';
import { useParams, useLocation, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, BarChart3, FileText, AlertTriangle, Target, Wand2, Clock, Info,
  ChevronDown, ChevronUp,
} from 'lucide-react';
import { analysisApi } from '../../services/api';
import type { SavedAnalysis, Analysis } from '../../types';
import {
  ReadabilityRadarChart,
  TextStatsBarChart,
  GradeLevelGauge,
  WordDifficultyPieChart,
  DifficultWordsChart,
  CommonWordsChart,
} from './Charts';
import HighlightedText from './HighlightedText';
import GradeExplanation from './GradeExplanation';
import ComplexityScoreCard from './ComplexityScoreCard';
import VocabularyAnalysis from './VocabularyAnalysis';
import ConceptGraphSection from './ConceptGraph';
import { calculateReadingTime, getReadingPaceDescription } from '../../utils/readingTime';
import { generateDetailedReport } from '../../utils/detailedReport';

type IconType = React.ComponentType<{ className?: string; style?: React.CSSProperties }>;

const InfoHint: React.FC<{ title: string; body: string }> = ({ title, body }) => (
  <span className="relative inline-flex group">
    <Info className="w-3.5 h-3.5 cursor-help" style={{ color: 'var(--text-4)' }} />
    <span
      className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 text-[11px] rounded-md px-3 py-2 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-opacity z-30 pointer-events-none leading-snug"
      style={{
        background: 'var(--ink-800)',
        color: '#fff',
        boxShadow: 'var(--sh-3)',
      }}
    >
      <span className="block font-semibold mb-1">{title}</span>
      <span className="block font-normal" style={{ color: '#d0d8e0' }}>{body}</span>
    </span>
  </span>
);

const MetricCard: React.FC<{
  icon: IconType;
  label: string;
  value: string;
  sub?: React.ReactNode;
  tone?: 'default' | 'teal' | 'err' | 'primary';
  hint?: { title: string; body: string };
}> = ({ icon: Icon, label, value, sub, tone = 'default', hint }) => {
  const iconColor =
    tone === 'primary' ? 'var(--p-700)' :
    tone === 'teal' ? 'var(--s-500)' :
    tone === 'err' ? 'var(--err-500)' :
    'var(--text-3)';
  const valueColor =
    tone === 'err' ? 'var(--err-500)' :
    tone === 'teal' ? 'var(--s-700)' :
    'var(--text-1)';
  return (
    <div className="cw-card cw-card-pad">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className="w-[15px] h-[15px]" style={{ color: iconColor }} />
          <span className="cw-eyebrow" style={{ letterSpacing: '0.1em' }}>{label}</span>
        </div>
        {hint && <InfoHint title={hint.title} body={hint.body} />}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 24,
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: valueColor,
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
      {sub && (
        <div className="mt-2" style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
          {sub}
        </div>
      )}
    </div>
  );
};

const AnalysisResults: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState<SavedAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conceptLoading, setConceptLoading] = useState(false);
  const [showModelDetails, setShowModelDetails] = useState(false);

  const freshAnalysis = location.state?.analysis as { analysis: Analysis; analysisId: number } | undefined;
  const freshOriginalText = (location.state?.originalText as string | undefined) || '';

  useEffect(() => {
    const fetchAnalysis = async () => {
      if (!id) return;
      try {
        const result = await analysisApi.getAnalysis(parseInt(id));
        setData(result);
      } catch (err) {
        setError('Failed to load analysis');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    if (freshAnalysis && id === String(freshAnalysis.analysisId)) {
      setData({
        id: freshAnalysis.analysisId,
        title: `Analysis ${new Date().toLocaleDateString()}`,
        originalText: freshOriginalText,
        createdAt: new Date().toISOString(),
        analysis: freshAnalysis.analysis,
      });
      setIsLoading(false);
    } else {
      fetchAnalysis();
    }
  }, [id, freshAnalysis]);

  const handleGenerateConceptGraph = async () => {
    if (!data?.id) return;
    setConceptLoading(true);
    try {
      const result = await analysisApi.generateConceptGraph(data.id);
      setData((prev) => prev ? { ...prev, conceptGraph: result.conceptGraph } : prev);
    } catch (err) {
      console.error('Failed to generate concept graph:', err);
    } finally {
      setConceptLoading(false);
    }
  };

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

  if (error || !data) {
    return (
      <div className="cw-card cw-card-pad-lg text-center" style={{ padding: '48px 24px' }}>
        <AlertTriangle className="w-10 h-10 mx-auto mb-3" style={{ color: 'var(--err-500)' }} />
        <p style={{ color: 'var(--err-700)', fontSize: 14, fontWeight: 600 }}>
          {error || 'Analysis not found'}
        </p>
        <Link to="/history" className="cw-btn cw-btn-secondary cw-btn-sm mt-4 inline-flex">
          Back to History
        </Link>
      </div>
    );
  }

  const { analysis } = data;

  const clampFlesch = (v: number) => Math.max(0, Math.min(100, v));

  const fleschTone = (score: number): 'ok' | 'warn' | 'err' =>
    score >= 70 ? 'ok' : score >= 50 ? 'warn' : 'err';

  const complexityBadgeClass = (complexity: string): string => {
    const c = complexity.toLowerCase();
    if (c === 'elementary' || c === 'beginner') return 'cw-badge cw-badge-ok';
    if (c === 'intermediate') return 'cw-badge cw-badge-warn';
    if (c === 'advanced') return 'cw-badge cw-badge-err';
    if (c === 'expert') return 'cw-badge cw-badge-err';
    return 'cw-badge cw-badge-neutral';
  };

  const readingTime = calculateReadingTime({
    word_count: analysis.basic_metrics.word_count,
    flesch_reading_ease: analysis.readability_scores.flesch_reading_ease,
  });
  const paceDesc = getReadingPaceDescription(readingTime.wordsPerMinute);
  const modelBreakdown = analysis.predictions.model_breakdown;
  const modelRows = modelBreakdown?.models ?? (
    analysis.predictions.model_predictions
      ? Object.entries(analysis.predictions.model_predictions).map(([id, rawScore]) => ({
          id,
          label: id
            .split('_')
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(' '),
          raw_score: rawScore,
          weight: 0,
        }))
      : []
  );
  const hasModelDetails = modelRows.length > 0;
  const fTone = fleschTone(analysis.readability_scores.flesch_reading_ease);

  return (
    <div>
      {/* Header */}
      <Link
        to="/history"
        className="inline-flex items-center gap-1.5 mb-4"
        style={{ color: 'var(--text-3)', fontSize: 12, fontWeight: 500 }}
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Back to History
      </Link>

      <div className="flex items-start justify-between gap-6 mb-8 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="cw-eyebrow mb-2">Analysis Result</div>
          <h1 className="cw-hero truncate" style={{ fontSize: 28 }}>{data.title}</h1>
          <p className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12 }}>
            {new Date(data.createdAt).toLocaleString()}
          </p>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <button
            onClick={() => navigate(`/simplify/${id}`)}
            className="cw-btn cw-btn-teal"
          >
            <Wand2 className="w-4 h-4" />
            Rewrite Text
          </button>
          <button
            onClick={() => generateDetailedReport({
              title: data.title,
              created_at: data.createdAt,
              predicted_grade_level: analysis.predictions.predicted_grade_level,
              predicted_complexity: analysis.predictions.predicted_complexity,
              confidence: analysis.predictions.confidence,
              flesch_reading_ease: analysis.readability_scores.flesch_reading_ease,
              flesch_kincaid_grade: analysis.readability_scores.flesch_kincaid_grade,
              automated_readability_index: analysis.readability_scores.automated_readability_index,
              smog_readability: analysis.readability_scores.smog_readability,
              coleman_liau_index: analysis.readability_scores.coleman_liau_index,
              word_count: analysis.basic_metrics.word_count,
              sentence_count: analysis.basic_metrics.sentence_count,
              avg_sentence_length: analysis.basic_metrics.avg_sentence_length,
              avg_word_length: analysis.basic_metrics.avg_word_length,
              avg_syllables_per_word: analysis.basic_metrics.avg_syllables_per_word,
              difficult_words_count: analysis.statistics.difficult_words_count,
              difficult_words_percentage: analysis.statistics.difficult_words_percentage,
              difficult_words: analysis.difficult_elements.difficult_words,
              difficult_sentences: analysis.difficult_elements.difficult_sentences,
              original_text: data.originalText,
              conceptGraph: data.conceptGraph,
            })}
            className="cw-btn cw-btn-primary"
          >
            <FileText className="w-4 h-4" />
            Detailed Report
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
        <MetricCard
          icon={Target}
          label="Grade Level"
          value={analysis.predictions.predicted_grade_level}
          tone="primary"
          sub={
            <span className={complexityBadgeClass(analysis.predictions.predicted_complexity)}>
              {analysis.predictions.predicted_complexity}
            </span>
          }
        />
        <MetricCard
          icon={BarChart3}
          label="Flesch Ease"
          value={clampFlesch(analysis.readability_scores.flesch_reading_ease).toFixed(1)}
          tone={fTone === 'ok' ? 'teal' : fTone === 'err' ? 'err' : 'default'}
          hint={{
            title: 'Flesch Reading Ease (0–100)',
            body: "A surface-level score based on sentence length and syllables per word. 90+ very easy, 70–80 fairly easy, 50–60 fairly difficult, <30 very confusing. It doesn't capture clause complexity, so a text can score 'fairly easy' and still be graded Advanced.",
          }}
          sub={
            analysis.readability_scores.flesch_reading_ease >= 70
              ? 'Easy to read'
              : analysis.readability_scores.flesch_reading_ease >= 50
              ? 'Fairly easy'
              : 'Difficult'
          }
        />
        <MetricCard
          icon={FileText}
          label="Word Count"
          value={analysis.basic_metrics.word_count.toLocaleString()}
          sub={`${analysis.basic_metrics.sentence_count} sentences`}
        />
        <MetricCard
          icon={AlertTriangle}
          label="Difficult Words"
          value={String(analysis.statistics.difficult_words_count)}
          tone="err"
          hint={{
            title: "What counts as 'difficult'?",
            body: "4+ characters, 3+ syllables, not a proper noun, and not in the Dale-Chall 3,000-word list. Hover any highlight in the text below to see the exact reason.",
          }}
          sub={`${analysis.statistics.difficult_words_percentage.toFixed(1)}% of total`}
        />
        <MetricCard
          icon={Clock}
          label="Reading Time"
          value={readingTime.displayText}
          tone="teal"
          sub={`${paceDesc} · ${readingTime.wordsPerMinute} WPM`}
        />
      </div>

      {hasModelDetails && (
        <div className="cw-card cw-card-pad-lg mb-6">
          <button
            type="button"
            onClick={() => setShowModelDetails((value) => !value)}
            className="w-full flex items-center justify-between gap-4"
            style={{
              background: 'transparent',
              border: 'none',
              padding: 0,
              color: 'var(--text-1)',
              cursor: 'pointer',
              textAlign: 'left',
            }}
          >
            <div>
              <div className="cw-section-title">Advanced Model Details</div>
              <p className="mt-1" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
                Show each model's raw grade estimate and the ensemble calculation.
              </p>
            </div>
            {showModelDetails ? (
              <ChevronUp className="w-5 h-5" style={{ color: 'var(--text-3)' }} />
            ) : (
              <ChevronDown className="w-5 h-5" style={{ color: 'var(--text-3)' }} />
            )}
          </button>

          {showModelDetails && (
            <div className="mt-5">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {modelRows.map((model) => (
                  <div
                    key={model.id}
                    className="rounded-lg"
                    style={{
                      border: '1px solid var(--border)',
                      background: 'var(--surface)',
                      padding: '14px 16px',
                    }}
                  >
                    <div className="cw-eyebrow mb-2">{model.label}</div>
                    <div
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 22,
                        fontWeight: 800,
                        color: 'var(--text-1)',
                      }}
                    >
                      {model.raw_score.toFixed(2)}
                    </div>
                    {model.weight > 0 && (
                      <div className="mt-1" style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
                        Weight {(model.weight * 100).toFixed(1)}%
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div
                className="mt-4 rounded-lg"
                style={{
                  border: '1px solid color-mix(in srgb, var(--p-700) 18%, var(--border))',
                  background: 'color-mix(in srgb, var(--p-50) 65%, var(--surface))',
                  padding: '14px 16px',
                }}
              >
                <div className="cw-eyebrow mb-2">Final Ensemble</div>
                <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-1)', fontSize: 13 }}>
                  {modelBreakdown?.calculation ?? (
                    `${modelRows.map((model) => model.raw_score.toFixed(2)).join(' + ')} / ${modelRows.length} = ${
                      (analysis.predictions.raw_score ?? 0).toFixed(2)
                    }`
                  )}
                </div>
                <div className="mt-2" style={{ color: 'var(--text-3)', fontSize: 12.5 }}>
                  Final raw score {(
                    modelBreakdown?.final_raw_score ??
                    analysis.predictions.raw_score ??
                    modelRows.reduce((sum, model) => sum + model.raw_score, 0) / Math.max(1, modelRows.length)
                  ).toFixed(2)} maps to {analysis.predictions.predicted_grade_level}; confidence is {(analysis.predictions.confidence * 100).toFixed(0)}%.
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Grade Explanation */}
      <div className="mb-6">
        <GradeExplanation
          gradeLevel={analysis.predictions.predicted_grade_level}
          metrics={{
            avgSentenceLength: analysis.basic_metrics.avg_sentence_length,
            avgSyllablesPerWord: analysis.basic_metrics.avg_syllables_per_word,
            difficultWordsPercentage: analysis.statistics.difficult_words_percentage,
            fleschReadingEase: analysis.readability_scores.flesch_reading_ease,
          }}
        />
      </div>

      {/* Complexity Score */}
      <div className="mb-6">
        <ComplexityScoreCard
          analysis={{
            predicted_grade_level: analysis.predictions.predicted_grade_level,
            flesch_reading_ease: analysis.readability_scores.flesch_reading_ease,
            difficult_words_percentage: analysis.statistics.difficult_words_percentage,
            avg_sentence_length: analysis.basic_metrics.avg_sentence_length,
          }}
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-6">
        <div className="cw-card cw-card-pad-lg">
          <h3 className="cw-section-title mb-4">Readability Scores</h3>
          <ReadabilityRadarChart scores={analysis.readability_scores} />
        </div>

        <div className="cw-card cw-card-pad-lg">
          <h3 className="cw-section-title mb-4">Grade Level</h3>
          <GradeLevelGauge gradeLevel={analysis.predictions.predicted_grade_level} />
        </div>

        <div className="cw-card cw-card-pad-lg">
          <h3 className="cw-section-title mb-4">Text Statistics</h3>
          <TextStatsBarChart
            metrics={analysis.basic_metrics}
            statistics={analysis.statistics}
          />
        </div>

        <div className="cw-card cw-card-pad-lg">
          <h3 className="cw-section-title mb-4">Word Difficulty</h3>
          <WordDifficultyPieChart
            statistics={analysis.statistics}
            wordCount={analysis.basic_metrics.word_count}
          />
        </div>
      </div>

      {/* Difficult Words Chart */}
      {analysis.difficult_elements.difficult_words.length > 0 && (
        <div className="cw-card cw-card-pad-lg mb-6">
          <h3 className="cw-section-title mb-4">Top Difficult Words by Syllables</h3>
          <DifficultWordsChart words={analysis.difficult_elements.difficult_words} />
        </div>
      )}

      {/* Most Common Words */}
      {data.originalText && (
        <div className="cw-card cw-card-pad-lg mb-6">
          <h3 className="cw-section-title mb-4">Most Common Words</h3>
          <CommonWordsChart text={data.originalText} />
        </div>
      )}

      {/* Vocabulary Level Analysis */}
      {data.originalText && (
        <div className="mb-6">
          <VocabularyAnalysis
            analysis={{
              original_text: data.originalText,
              difficult_words: analysis.difficult_elements.difficult_words,
              predicted_grade_level: analysis.predictions.predicted_grade_level,
            }}
          />
        </div>
      )}

      {/* Concept Prerequisite Graph */}
      <div className="mb-6">
        <ConceptGraphSection
          conceptGraph={data.conceptGraph}
          onGenerate={handleGenerateConceptGraph}
          loading={conceptLoading}
        />
      </div>

      {/* Readability Metrics Table */}
      <div className="cw-card cw-card-pad-lg mb-6">
        <h3 className="cw-section-title mb-4">Detailed Readability Metrics</h3>
        <div className="cw-scroll-x">
          <table className="cw-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Score</th>
                <th>Interpretation</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Flesch Reading Ease</td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {clampFlesch(analysis.readability_scores.flesch_reading_ease).toFixed(2)}
                </td>
                <td style={{ color: 'var(--text-3)' }}>0–100 scale, higher = easier</td>
              </tr>
              <tr>
                <td>Flesch-Kincaid Grade</td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {analysis.readability_scores.flesch_kincaid_grade.toFixed(2)}
                </td>
                <td style={{ color: 'var(--text-3)' }}>US grade level needed</td>
              </tr>
              <tr>
                <td>Automated Readability Index</td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {analysis.readability_scores.automated_readability_index.toFixed(2)}
                </td>
                <td style={{ color: 'var(--text-3)' }}>US grade level estimate</td>
              </tr>
              <tr>
                <td>SMOG Index</td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {analysis.readability_scores.smog_readability.toFixed(2)}
                </td>
                <td style={{ color: 'var(--text-3)' }}>Years of education needed</td>
              </tr>
              <tr>
                <td>Coleman-Liau Index</td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>
                  {analysis.readability_scores.coleman_liau_index.toFixed(2)}
                </td>
                <td style={{ color: 'var(--text-3)' }}>US grade level estimate</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Original Text with Highlighting */}
      {data.originalText && (
        <div className="cw-card cw-card-pad-lg mb-6">
          <div className="flex items-baseline justify-between gap-3 mb-4 flex-wrap">
            <h3 className="cw-section-title">Original Text</h3>
            <span className="cw-eyebrow" style={{ color: 'var(--text-3)' }}>
              Hover any highlight for the reason
            </span>
          </div>
          <HighlightedText
            text={data.originalText}
            difficultWords={analysis.difficult_elements.difficult_words}
            difficultSentences={analysis.difficult_elements.difficult_sentences}
          />
        </div>
      )}

      {/* Difficult Sentences List */}
      {analysis.difficult_elements.difficult_sentences.length > 0 && (
        <div className="cw-card cw-card-pad-lg">
          <h3 className="cw-section-title mb-4">Difficult Sentences</h3>
          <div className="space-y-3">
            {analysis.difficult_elements.difficult_sentences.map((sentence, index) => (
              <div
                key={index}
                className="p-4 rounded-md"
                style={{
                  background: 'color-mix(in srgb, var(--err-500) 6%, var(--surface-raised))',
                  borderLeft: '3px solid var(--err-500)',
                }}
              >
                <p style={{ color: 'var(--text-1)', fontSize: 13, lineHeight: 1.55, marginBottom: 8 }}>
                  {sentence.sentence}
                </p>
                <div className="flex gap-4 flex-wrap" style={{ fontSize: 11.5, color: 'var(--text-3)' }}>
                  <span><strong style={{ color: 'var(--text-2)' }}>Reason:</strong> {sentence.reason}</span>
                  <span><strong style={{ color: 'var(--text-2)' }}>Flesch:</strong> {sentence.flesch_score}</span>
                  <span><strong style={{ color: 'var(--text-2)' }}>Words:</strong> {sentence.word_count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisResults;
