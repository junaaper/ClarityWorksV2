import React from 'react';

interface Props {
  text: string;
  difficultWords: Array<{ word: string; position?: number }>;
  difficultSentences: Array<{ sentence: string; position?: number }>;
}

const TextHeatmap: React.FC<Props> = ({ text, difficultWords, difficultSentences }) => {
  const getWordColor = (word: string) => {
    const cleanWord = word.replace(/[^a-zA-Z]/g, '').toLowerCase();
    const isDifficult = difficultWords.some(dw => dw.word.toLowerCase() === cleanWord);
    if (isDifficult) return 'bg-red-300 rounded px-0.5';
    return '';
  };

  const getSentenceColor = (sentence: string) => {
    const trimmed = sentence.trim();
    const isDifficult = difficultSentences.some(ds => {
      const dsTrimmed = ds.sentence.trim();
      return trimmed.includes(dsTrimmed) || dsTrimmed.includes(trimmed);
    });
    if (isDifficult) return 'border-l-4 border-red-500 bg-red-50';
    return 'border-l-4 border-green-500 bg-green-50';
  };

  const sentences = text.split(/(?<=[.!?])\s+/).filter(s => s.trim());

  return (
    <div className="bg-white border rounded-lg p-6">
      <h3 className="text-lg font-bold mb-4">Text Difficulty Heatmap</h3>

      <div className="space-y-2">
        {sentences.map((sentence, idx) => (
          <div key={idx} className={`p-3 rounded ${getSentenceColor(sentence)}`}>
            {sentence.split(/\s+/).map((word, widx) => (
              <span key={widx} className={getWordColor(word)}>
                {word}{' '}
              </span>
            ))}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="mt-6 flex gap-6 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-red-300 rounded"></div>
          <span>Difficult Words</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-l-4 border-red-500 bg-red-50"></div>
          <span>Difficult Sentences</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 border-l-4 border-green-500 bg-green-50"></div>
          <span>Easy Sentences</span>
        </div>
      </div>
    </div>
  );
};

export default TextHeatmap;
