import React, { useState } from 'react';
import { analyzeVocabulary, getVocabularyInterpretation } from '../../utils/vocabularyAnalysis';
import { BookOpen, ChevronDown, ChevronRight } from 'lucide-react';

interface Props {
  analysis: {
    original_text: string;
    difficult_words: Array<{ word: string }>;
  };
}

const VocabularyAnalysis: React.FC<Props> = ({ analysis }) => {
  const [expandedLevel, setExpandedLevel] = useState<string | null>(null);

  const result = analyzeVocabulary(analysis);
  const interpretation = getVocabularyInterpretation(result);

  return (
    <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <BookOpen size={24} className="text-purple-600 dark:text-purple-400" />
        <h3 className="text-xl font-bold text-gray-800 dark:text-gray-200">
          Vocabulary Level Distribution
        </h3>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-800 dark:text-gray-200">
            {result.totalWords.toLocaleString()}
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400">Total Words</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-800 dark:text-gray-200">
            {result.uniqueWords.toLocaleString()}
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400">Unique Words</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-gray-800 dark:text-gray-200">
            {(result.vocabularyDiversity * 100).toFixed(0)}%
          </p>
          <p className="text-xs text-gray-600 dark:text-gray-400">Diversity</p>
        </div>
      </div>

      {/* Stacked Bar Chart */}
      <div className="mb-6">
        <div className="w-full h-12 flex rounded-lg overflow-hidden">
          {result.levels.map((level) => (
            level.percentage > 0 && (
              <div
                key={level.level}
                className={`${level.color} dark:opacity-80 flex items-center justify-center text-white text-xs font-semibold transition-all hover:opacity-90 cursor-pointer`}
                style={{ width: `${level.percentage}%` }}
                onClick={() => setExpandedLevel(expandedLevel === level.level ? null : level.level)}
                title={`${level.level}: ${level.percentage.toFixed(1)}%`}
              >
                {level.percentage >= 10 && (
                  <span>{level.percentage.toFixed(0)}%</span>
                )}
              </div>
            )
          ))}
        </div>
      </div>

      {/* Legend & Details */}
      <div className="space-y-2">
        {result.levels.map((level) => {
          const isExpanded = expandedLevel === level.level;

          return (
            <div
              key={level.level}
              className="border dark:border-gray-700 rounded-lg overflow-hidden"
            >
              {/* Level Header */}
              <button
                onClick={() => setExpandedLevel(isExpanded ? null : level.level)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`w-4 h-4 ${level.color} dark:opacity-80 rounded`} />
                  <div className="text-left">
                    <p className="font-semibold text-gray-800 dark:text-gray-200">
                      {level.level} <span className="text-sm text-gray-500 dark:text-gray-400">({level.gradeRange})</span>
                    </p>
                    <p className="text-xs text-gray-600 dark:text-gray-400">
                      {level.count.toLocaleString()} words ({level.percentage.toFixed(1)}%)
                    </p>
                  </div>
                </div>

                {isExpanded ? (
                  <ChevronDown size={20} className="text-gray-400" />
                ) : (
                  <ChevronRight size={20} className="text-gray-400" />
                )}
              </button>

              {/* Expanded Examples */}
              {isExpanded && level.examples.length > 0 && (
                <div className="px-4 pb-3 bg-gray-50 dark:bg-gray-700/30">
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                    Example words:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {level.examples.map((word, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded text-sm text-gray-700 dark:text-gray-300"
                      >
                        {word}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Interpretation */}
      <div className="mt-6 pt-6 border-t dark:border-gray-700">
        <p className="text-sm text-gray-600 dark:text-gray-400 italic">
          {interpretation}
        </p>
      </div>
    </div>
  );
};

export default VocabularyAnalysis;
