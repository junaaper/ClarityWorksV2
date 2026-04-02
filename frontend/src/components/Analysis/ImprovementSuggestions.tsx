import React, { useState } from 'react';
import { generateImprovementSuggestions, Suggestion, SuggestionInput } from '../../utils/improvementSuggestions';
import { ChevronDown, ChevronRight, Lightbulb } from 'lucide-react';

interface Props {
  analysis: SuggestionInput;
}

const ImprovementSuggestions: React.FC<Props> = ({ analysis }) => {
  const [expandedIds, setExpandedIds] = useState<string[]>([]);

  const suggestions = generateImprovementSuggestions(analysis);

  const toggleExpanded = (id: string) => {
    setExpandedIds(prev =>
      prev.includes(id)
        ? prev.filter(i => i !== id)
        : [...prev, id]
    );
  };

  const getPriorityColor = (priority: Suggestion['priority']) => {
    switch (priority) {
      case 'high': return 'border-red-500 bg-red-50 dark:bg-red-900/20';
      case 'medium': return 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20';
      case 'low': return 'border-blue-500 bg-blue-50 dark:bg-blue-900/20';
    }
  };

  const getPriorityBadge = (priority: Suggestion['priority']) => {
    switch (priority) {
      case 'high': return <span className="text-xs px-2 py-1 bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 rounded">High Impact</span>;
      case 'medium': return <span className="text-xs px-2 py-1 bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300 rounded">Medium Impact</span>;
      case 'low': return <span className="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded">Low Impact</span>;
    }
  };

  if (suggestions.length === 0) {
    return (
      <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-6 text-center">
        <Lightbulb size={48} className="mx-auto text-green-600 dark:text-green-400 mb-3" />
        <p className="text-lg font-semibold text-green-800 dark:text-green-200">
          Excellent! Your text is already well-optimized for readability.
        </p>
        <p className="text-sm text-green-600 dark:text-green-400 mt-2">
          No major improvements needed at this time.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Lightbulb size={24} className="text-yellow-500" />
        <h3 className="text-xl font-bold text-gray-800 dark:text-gray-200">
          Improve This Text
        </h3>
      </div>

      <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
        Here are {suggestions.length} actionable suggestions to improve your text's readability,
        ordered by potential impact:
      </p>

      {/* Suggestions List */}
      <div className="space-y-3">
        {suggestions.map((suggestion, index) => {
          const isExpanded = expandedIds.includes(suggestion.id);

          return (
            <div
              key={suggestion.id}
              className={`border-l-4 ${getPriorityColor(suggestion.priority)} rounded-r-lg overflow-hidden transition-all`}
            >
              {/* Suggestion Header (Clickable) */}
              <button
                onClick={() => toggleExpanded(suggestion.id)}
                className="w-full px-4 py-3 flex items-start gap-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
              >
                {/* Icon & Number */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className="text-2xl">{suggestion.icon}</span>
                  <span className="text-sm font-bold text-gray-400">#{index + 1}</span>
                </div>

                {/* Content */}
                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-semibold text-gray-800 dark:text-gray-200">
                      {suggestion.title}
                    </h4>
                    {getPriorityBadge(suggestion.priority)}
                  </div>

                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {suggestion.description}
                  </p>

                  <p className="text-xs text-blue-600 dark:text-blue-400 mt-2 font-medium">
                    Estimated impact: {suggestion.estimatedImpact}
                  </p>
                </div>

                {/* Expand Icon */}
                <div className="flex-shrink-0">
                  {isExpanded ? (
                    <ChevronDown size={20} className="text-gray-400" />
                  ) : (
                    <ChevronRight size={20} className="text-gray-400" />
                  )}
                </div>
              </button>

              {/* Expanded Details */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-2 border-t dark:border-gray-700 bg-white dark:bg-gray-800">
                  <div className="bg-blue-50 dark:bg-blue-900/20 rounded p-3 mb-3">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Action to Take:
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {suggestion.action}
                    </p>
                  </div>

                  {suggestion.details && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 italic">
                      {suggestion.details}
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer Tip */}
      <div className="mt-6 pt-6 border-t dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400 italic">
          Tip: Start with high-impact suggestions first for the biggest improvement
          in readability. Use the Simplify feature to automatically apply word replacements.
        </p>
      </div>
    </div>
  );
};

export default ImprovementSuggestions;
