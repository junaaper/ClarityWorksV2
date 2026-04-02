import React, { useState } from 'react';
import {
  calculateComplexityScore,
  getComplexityBgColor,
  getComplexityExplanation,
  ComplexityScoreInputs
} from '../../utils/complexityScore';
import { Info } from 'lucide-react';

interface Props {
  analysis: ComplexityScoreInputs;
}

const ComplexityScoreCard: React.FC<Props> = ({ analysis }) => {
  const [showBreakdown, setShowBreakdown] = useState(false);

  const result = calculateComplexityScore(analysis);
  const bgColor = getComplexityBgColor(result.score);
  const explanation = getComplexityExplanation(result.score);

  return (
    <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-200">
          Text Complexity Score
        </h3>
        <button
          onClick={() => setShowBreakdown(!showBreakdown)}
          className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
        >
          <Info size={16} />
          {showBreakdown ? 'Hide' : 'Show'} Breakdown
        </button>
      </div>

      {/* Main Score Display */}
      <div className="text-center mb-6">
        <div className={`text-7xl font-bold ${result.color} dark:opacity-90`}>
          {result.score}
          <span className="text-3xl text-gray-400 dark:text-gray-500">/100</span>
        </div>
        <p className="text-xl mt-2 text-gray-700 dark:text-gray-300 font-medium">
          {result.label}
        </p>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-4 mb-4 overflow-hidden">
        <div
          className={`h-4 rounded-full ${bgColor} transition-all duration-500 ease-out`}
          style={{ width: `${result.score}%` }}
        />
      </div>

      {/* Explanation */}
      <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
        {explanation}
      </p>

      {/* Breakdown (Collapsible) */}
      {showBreakdown && (
        <div className="mt-6 pt-6 border-t dark:border-gray-700">
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
            Score Breakdown
          </h4>

          <div className="space-y-3">
            {/* Grade Level */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600 dark:text-gray-400">
                  Grade Level (40% weight)
                </span>
                <span className="font-medium text-gray-800 dark:text-gray-200">
                  {result.breakdown.gradeContribution}/40
                </span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className="h-2 rounded-full bg-blue-500"
                  style={{ width: `${(result.breakdown.gradeContribution / 40) * 100}%` }}
                />
              </div>
            </div>

            {/* Flesch Score */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600 dark:text-gray-400">
                  Flesch Reading Ease (30% weight)
                </span>
                <span className="font-medium text-gray-800 dark:text-gray-200">
                  {result.breakdown.fleschContribution}/30
                </span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className="h-2 rounded-full bg-green-500"
                  style={{ width: `${(result.breakdown.fleschContribution / 30) * 100}%` }}
                />
              </div>
            </div>

            {/* Difficult Words */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600 dark:text-gray-400">
                  Difficult Words (20% weight)
                </span>
                <span className="font-medium text-gray-800 dark:text-gray-200">
                  {result.breakdown.wordsContribution}/20
                </span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className="h-2 rounded-full bg-yellow-500"
                  style={{ width: `${(result.breakdown.wordsContribution / 20) * 100}%` }}
                />
              </div>
            </div>

            {/* Sentence Length */}
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600 dark:text-gray-400">
                  Sentence Length (10% weight)
                </span>
                <span className="font-medium text-gray-800 dark:text-gray-200">
                  {result.breakdown.sentenceContribution}/10
                </span>
              </div>
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div
                  className="h-2 rounded-full bg-orange-500"
                  style={{ width: `${(result.breakdown.sentenceContribution / 10) * 100}%` }}
                />
              </div>
            </div>
          </div>

          <p className="text-xs text-gray-500 dark:text-gray-400 mt-4 italic">
            This score combines multiple readability factors into a single 0-100 metric.
            Higher scores indicate more complex text requiring advanced reading skills.
          </p>
        </div>
      )}
    </div>
  );
};

export default ComplexityScoreCard;
