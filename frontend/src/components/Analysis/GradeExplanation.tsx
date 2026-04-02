import React, { useState } from 'react';
import { getGradeExplanation } from '../../utils/gradeExplanations';

interface Props {
  gradeLevel: string;
  metrics: {
    avgSentenceLength: number;
    avgSyllablesPerWord: number;
    difficultWordsPercentage: number;
    fleschReadingEase: number;
  };
}

const GradeExplanation: React.FC<Props> = ({ gradeLevel, metrics }) => {
  const [showTechnical, setShowTechnical] = useState(false);
  const explanation = getGradeExplanation(gradeLevel);

  return (
    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-lg p-6 mb-6">
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-xl font-bold text-gray-800">
          Why {gradeLevel}?
        </h3>

        <button
          onClick={() => setShowTechnical(!showTechnical)}
          className="text-sm px-3 py-1 bg-white border border-gray-300 rounded hover:bg-gray-50"
        >
          {showTechnical ? 'Simple' : 'Technical'}
        </button>
      </div>

      {/* Explanation Text */}
      <div className="mb-4">
        <p className="text-gray-700 leading-relaxed">
          {showTechnical ? explanation.technical : explanation.layman}
        </p>
      </div>

      {/* Characteristics Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="bg-white rounded p-3 border border-gray-200">
          <p className="text-xs text-gray-600 mb-1">Vocabulary Level</p>
          <p className="text-sm font-semibold">{explanation.characteristics.vocabulary}</p>
        </div>

        <div className="bg-white rounded p-3 border border-gray-200">
          <p className="text-xs text-gray-600 mb-1">Sentence Length</p>
          <p className="text-sm font-semibold">{explanation.characteristics.sentenceLength}</p>
          <p className="text-xs text-gray-500">Yours: {metrics.avgSentenceLength.toFixed(1)} words</p>
        </div>

        <div className="bg-white rounded p-3 border border-gray-200">
          <p className="text-xs text-gray-600 mb-1">Structure</p>
          <p className="text-sm font-semibold">{explanation.characteristics.structure}</p>
        </div>

        <div className="bg-white rounded p-3 border border-gray-200">
          <p className="text-xs text-gray-600 mb-1">Target Audience</p>
          <p className="text-sm font-semibold">{explanation.characteristics.audience}</p>
        </div>
      </div>

      {/* Metrics Justification */}
      <div className="bg-white rounded-lg p-4 border border-gray-200">
        <p className="text-sm font-semibold text-gray-700 mb-2">Your Text Analysis:</p>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>Average {metrics.avgSentenceLength.toFixed(1)} words per sentence</li>
          <li>Average {metrics.avgSyllablesPerWord.toFixed(2)} syllables per word</li>
          <li>{metrics.difficultWordsPercentage.toFixed(1)}% difficult words</li>
          <li>Flesch Reading Ease: {metrics.fleschReadingEase.toFixed(1)} / 100</li>
        </ul>
      </div>
    </div>
  );
};

export default GradeExplanation;
