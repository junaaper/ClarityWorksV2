import React, { useEffect, useState } from 'react';
import { useParams, useLocation, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, BarChart3, FileText, AlertTriangle, Target, Wand2, Clock
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
import TextHeatmap from './TextHeatmap';
import ComplexityScoreCard from './ComplexityScoreCard';
import VocabularyAnalysis from './VocabularyAnalysis';
import { calculateReadingTime, getReadingTimeColor, getReadingPaceDescription } from '../../utils/readingTime';
import { generateDetailedReport } from '../../utils/detailedReport';

const AnalysisResults: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState<SavedAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check if we have fresh analysis data from navigation
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
      // Use fresh data if available
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <p className="text-red-600">{error || 'Analysis not found'}</p>
        <Link to="/history" className="text-primary-600 hover:underline mt-4 inline-block">
          Back to History
        </Link>
      </div>
    );
  }

  const { analysis } = data;

  const getReadabilityColor = (score: number): string => {
    if (score >= 70) return 'text-green-600';
    if (score >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getComplexityColor = (complexity: string): string => {
    switch (complexity) {
      case 'Elementary':
        return 'bg-green-100 text-green-800';
      case 'Intermediate':
        return 'bg-yellow-100 text-yellow-800';
      case 'Advanced':
        return 'bg-orange-100 text-orange-800';
      case 'Expert':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <Link
            to="/history"
            className="flex items-center gap-2 text-gray-600 hover:text-gray-800 mb-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to History
          </Link>
          <h1 className="text-3xl font-bold text-gray-800">{data.title}</h1>
          <p className="text-gray-600 mt-1">
            {new Date(data.createdAt).toLocaleString()}
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => navigate(`/simplify/${id}`)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            <Wand2 className="w-5 h-5" />
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
            })}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:from-purple-700 hover:to-indigo-700 transition-all shadow-md hover:shadow-lg"
          >
            <FileText className="w-5 h-5" />
            Detailed Report (PDF)
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center gap-3 mb-2">
            <Target className="w-5 h-5 text-primary-600" />
            <span className="text-sm text-gray-600">Grade Level</span>
          </div>
          <p className="text-2xl font-bold text-gray-800">
            {analysis.predictions.predicted_grade_level}
          </p>
          <span
            className={`inline-block mt-2 px-2 py-1 text-xs font-medium rounded-full ${getComplexityColor(
              analysis.predictions.predicted_complexity
            )}`}
          >
            {analysis.predictions.predicted_complexity}
          </span>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center gap-3 mb-2">
            <BarChart3 className="w-5 h-5 text-green-600" />
            <span className="text-sm text-gray-600">Flesch Ease</span>
          </div>
          <p
            className={`text-2xl font-bold ${getReadabilityColor(
              analysis.readability_scores.flesch_reading_ease
            )}`}
          >
            {analysis.readability_scores.flesch_reading_ease.toFixed(1)}
          </p>
          <p className="text-xs text-gray-500 mt-2">
            {analysis.readability_scores.flesch_reading_ease >= 70
              ? 'Easy to read'
              : analysis.readability_scores.flesch_reading_ease >= 50
              ? 'Fairly easy'
              : 'Difficult'}
          </p>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center gap-3 mb-2">
            <FileText className="w-5 h-5 text-blue-600" />
            <span className="text-sm text-gray-600">Word Count</span>
          </div>
          <p className="text-2xl font-bold text-gray-800">
            {analysis.basic_metrics.word_count.toLocaleString()}
          </p>
          <p className="text-xs text-gray-500 mt-2">
            {analysis.basic_metrics.sentence_count} sentences
          </p>
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            <span className="text-sm text-gray-600">Difficult Words</span>
          </div>
          <p className="text-2xl font-bold text-red-600">
            {analysis.statistics.difficult_words_count}
          </p>
          <p className="text-xs text-gray-500 mt-2">
            {analysis.statistics.difficult_words_percentage.toFixed(1)}% of total
          </p>
        </div>

        {/* Reading Time Card */}
        {(() => {
          const readingTime = calculateReadingTime({
            word_count: analysis.basic_metrics.word_count,
            flesch_reading_ease: analysis.readability_scores.flesch_reading_ease
          });
          const timeColor = getReadingTimeColor(readingTime.minutes);
          const paceDesc = getReadingPaceDescription(readingTime.wordsPerMinute);

          return (
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <div className="flex items-center gap-3 mb-2">
                <Clock className="w-5 h-5 text-blue-600" />
                <span className="text-sm text-gray-600">Reading Time</span>
              </div>
              <p className={`text-2xl font-bold ${timeColor}`}>
                {readingTime.displayText}
              </p>
              <p className="text-xs text-gray-500 mt-2">
                {paceDesc} ({readingTime.wordsPerMinute} WPM)
              </p>
            </div>
          );
        })()}
      </div>

      {/* Grade Explanation */}
      <GradeExplanation
        gradeLevel={analysis.predictions.predicted_grade_level}
        metrics={{
          avgSentenceLength: analysis.basic_metrics.avg_sentence_length,
          avgSyllablesPerWord: analysis.basic_metrics.avg_syllables_per_word,
          difficultWordsPercentage: analysis.statistics.difficult_words_percentage,
          fleschReadingEase: analysis.readability_scores.flesch_reading_ease
        }}
      />

      {/* Complexity Score Card */}
      <div className="mb-8">
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
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">
            Readability Scores
          </h3>
          <ReadabilityRadarChart scores={analysis.readability_scores} />
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">
            Grade Level
          </h3>
          <GradeLevelGauge gradeLevel={analysis.predictions.predicted_grade_level} />
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">
            Text Statistics
          </h3>
          <TextStatsBarChart
            metrics={analysis.basic_metrics}
            statistics={analysis.statistics}
          />
        </div>

        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">
            Word Difficulty
          </h3>
          <WordDifficultyPieChart
            statistics={analysis.statistics}
            wordCount={analysis.basic_metrics.word_count}
          />
        </div>
      </div>

      {/* Difficult Words Chart */}
      {analysis.difficult_elements.difficult_words.length > 0 && (
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">
            Top Difficult Words by Syllables
          </h3>
          <DifficultWordsChart words={analysis.difficult_elements.difficult_words} />
        </div>
      )}

      {/* Most Common Words */}
      {data.originalText && (
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">
            Most Common Words
          </h3>
          <CommonWordsChart text={data.originalText} />
        </div>
      )}

      {/* Vocabulary Level Analysis */}
      {data.originalText && (
        <div className="mb-8">
          <VocabularyAnalysis
            analysis={{
              original_text: data.originalText,
              difficult_words: analysis.difficult_elements.difficult_words,
            }}
          />
        </div>
      )}

      {/* Readability Metrics Table */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 mb-8">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">
          Detailed Readability Metrics
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b">
                <th className="py-3 px-4 font-medium text-gray-600">Metric</th>
                <th className="py-3 px-4 font-medium text-gray-600">Score</th>
                <th className="py-3 px-4 font-medium text-gray-600">Interpretation</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b">
                <td className="py-3 px-4">Flesch Reading Ease</td>
                <td className="py-3 px-4 font-mono">
                  {analysis.readability_scores.flesch_reading_ease.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-sm text-gray-600">
                  0-100 scale, higher = easier
                </td>
              </tr>
              <tr className="border-b">
                <td className="py-3 px-4">Flesch-Kincaid Grade</td>
                <td className="py-3 px-4 font-mono">
                  {analysis.readability_scores.flesch_kincaid_grade.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-sm text-gray-600">
                  US grade level needed
                </td>
              </tr>
              <tr className="border-b">
                <td className="py-3 px-4">Automated Readability Index</td>
                <td className="py-3 px-4 font-mono">
                  {analysis.readability_scores.automated_readability_index.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-sm text-gray-600">
                  US grade level estimate
                </td>
              </tr>
              <tr className="border-b">
                <td className="py-3 px-4">SMOG Index</td>
                <td className="py-3 px-4 font-mono">
                  {analysis.readability_scores.smog_readability.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-sm text-gray-600">
                  Years of education needed
                </td>
              </tr>
              <tr>
                <td className="py-3 px-4">Coleman-Liau Index</td>
                <td className="py-3 px-4 font-mono">
                  {analysis.readability_scores.coleman_liau_index.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-sm text-gray-600">
                  US grade level estimate
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Original Text with Highlighting */}
      {data.originalText && (
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200 mb-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">
            Original Text (with highlights)
          </h3>
          <HighlightedText
            text={data.originalText}
            difficultWords={analysis.difficult_elements.difficult_words}
            difficultSentences={analysis.difficult_elements.difficult_sentences}
          />
        </div>
      )}

      {/* Text Difficulty Heatmap */}
      {data.originalText && (
        <div className="mb-8">
          <TextHeatmap
            text={data.originalText}
            difficultWords={analysis.difficult_elements.difficult_words}
            difficultSentences={analysis.difficult_elements.difficult_sentences}
          />
        </div>
      )}

      {/* Difficult Sentences List */}
      {analysis.difficult_elements.difficult_sentences.length > 0 && (
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">
            Difficult Sentences
          </h3>
          <div className="space-y-4">
            {analysis.difficult_elements.difficult_sentences.map((sentence, index) => (
              <div
                key={index}
                className="p-4 bg-red-50 rounded-lg border-l-4 border-red-400"
              >
                <p className="text-gray-800 mb-2">{sentence.sentence}</p>
                <div className="flex gap-4 text-sm text-gray-600">
                  <span>Reason: {sentence.reason}</span>
                  <span>Flesch Score: {sentence.flesch_score}</span>
                  <span>Words: {sentence.word_count}</span>
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
