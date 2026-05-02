import React, { useState } from 'react';
import type { DifficultWord, DifficultSentence } from '../../types';

interface HighlightedTextProps {
  text: string;
  difficultWords: DifficultWord[];
  difficultSentences: DifficultSentence[];
}

interface TooltipData {
  content: string;
  x: number;
  y: number;
}

const HighlightedText: React.FC<HighlightedTextProps> = ({
  text,
  difficultWords,
  difficultSentences,
}) => {
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);

  // Create maps for difficult word/sentence lookup by key
  const difficultWordDetails = new Map(
    difficultWords.map((w) => [w.word.toLowerCase(), w])
  );
  const difficultSentenceDetails = new Map(
    difficultSentences.map((s) => [s.position, s])
  );

  // Split text into sentences
  const sentences = text.split(/([.!?]+)/).reduce((acc: string[], part, i, arr) => {
    if (i % 2 === 0) {
      const sentence = part + (arr[i + 1] || '');
      if (sentence.trim()) {
        acc.push(sentence);
      }
    }
    return acc;
  }, []);

  const handleMouseEnter = (
    event: React.MouseEvent,
    content: string
  ) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltip({
      content,
      x: rect.left + rect.width / 2,
      y: rect.top - 8,
    });
  };

  const handleMouseLeave = () => {
    setTooltip(null);
  };

  const renderWord = (word: string, wordKey: string) => {
    const cleanWord = word.replace(/[.,!?;:'"()[\]{}]/g, '').toLowerCase();
    const details = difficultWordDetails.get(cleanWord);

    if (details) {
      return (
        <span
          key={wordKey}
          className="text-red-600 font-medium cursor-help underline decoration-wavy decoration-red-400 underline-offset-2 hover:bg-red-100 rounded px-0.5 transition-colors"
          onMouseEnter={(e) =>
            handleMouseEnter(
              e,
              `Why "${details.word}" is flagged:\n${details.reason}`
            )
          }
          onMouseLeave={handleMouseLeave}
        >
          {word}
        </span>
      );
    }

    return <span key={wordKey}>{word}</span>;
  };

  const renderSentence = (sentence: string, sentenceIndex: number) => {
    const details = difficultSentenceDetails.get(sentenceIndex);
    const words = sentence.split(/(\s+)/);

    const content = words.map((word, wordIndex) => {
      if (/^\s+$/.test(word)) {
        return <span key={`space-${wordIndex}`}>{word}</span>;
      }
      return renderWord(word, `word-${sentenceIndex}-${wordIndex}`);
    });

    if (details) {
      return (
        <span
          key={`sentence-${sentenceIndex}`}
          className="bg-red-50 border-l-2 border-red-400 pl-1 inline cursor-help hover:bg-red-100 transition-colors"
          onMouseEnter={(e) =>
            handleMouseEnter(
              e,
              `Why this sentence is difficult:\n${details.reason}\n• ${details.word_count} words\n• Flesch score: ${details.flesch_score} (lower = harder)`
            )
          }
          onMouseLeave={handleMouseLeave}
        >
          {content}
        </span>
      );
    }

    return <span key={`sentence-${sentenceIndex}`}>{content}</span>;
  };

  return (
    <div className="relative">
      <div className="p-4 bg-gray-50 rounded-lg border border-gray-200 leading-relaxed text-gray-800">
        {sentences.map((sentence, index) => renderSentence(sentence, index))}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 bg-gray-900 text-white text-sm px-3 py-2 rounded-lg shadow-xl max-w-sm whitespace-pre-line pointer-events-none leading-snug"
          style={{
            left: Math.max(8, Math.min(tooltip.x - 160, window.innerWidth - 336)),
            top: tooltip.y,
            transform: 'translateY(-100%)',
          }}
        >
          {tooltip.content}
        </div>
      )}

      {/* Legend */}
      <div className="mt-4 flex gap-6 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-4 h-4 bg-red-600 rounded"></span>
          <span className="text-gray-600">Difficult Word</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-4 h-4 bg-red-50 border-l-2 border-red-400"></span>
          <span className="text-gray-600">Difficult Sentence</span>
        </div>
      </div>
    </div>
  );
};

export default HighlightedText;
