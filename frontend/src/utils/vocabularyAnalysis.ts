/**
 * Vocabulary Level Analysis
 *
 * Categorizes words by grade-level complexity and generates
 * distribution statistics.
 *
 * Research basis:
 * - Stenner et al. (2006): Lexile Framework word difficulty bands
 * - Nation (2001): Vocabulary knowledge and reading comprehension
 * - Zipf (1949): Word frequency follows power law distribution
 */

export interface VocabularyAnalysisInput {
  original_text: string;
  difficult_words: Array<{ word: string }>;
}

export interface VocabularyLevel {
  level: string;           // "Simple", "Medium", "Advanced", "Expert"
  gradeRange: string;      // "Grades 1-3", "Grades 4-8", etc.
  count: number;           // Number of words at this level
  percentage: number;      // Percentage of total words
  examples: string[];      // Sample words at this level (max 5)
  color: string;           // Display color
}

export interface VocabularyAnalysisResult {
  levels: VocabularyLevel[];
  totalWords: number;
  uniqueWords: number;
  vocabularyDiversity: number;  // 0-1 (unique/total)
}

/**
 * Analyze vocabulary distribution
 *
 * Categorizes words into 4 levels:
 * - Simple (Grades 1-3): Very common words, Zipf >= 5.5
 * - Medium (Grades 4-8): Common words, Zipf 4.0-5.5
 * - Advanced (Grades 9-12): Less common, Zipf 2.5-4.0
 * - Expert (College+): Rare/technical, Zipf < 2.5
 */
export function analyzeVocabulary(input: VocabularyAnalysisInput): VocabularyAnalysisResult {
  // Extract all words from text (alphabetic only, lowercase)
  const words = input.original_text
    .toLowerCase()
    .match(/\b[a-z]+\b/g) || [];

  const totalWords = words.length;
  const uniqueWords = new Set(words).size;

  // Convert difficult_words array to Set for O(1) lookup
  const difficultWordsSet = new Set(
    input.difficult_words.map(dw => dw.word.toLowerCase())
  );

  // Categorize words
  const simple: string[] = [];
  const medium: string[] = [];
  const advanced: string[] = [];
  const expert: string[] = [];

  // Common stop words to exclude from examples (for cleaner display)
  const stopWords = new Set([
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
    'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
    'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
    'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what'
  ]);

  for (const word of words) {
    // Skip very short words and stop words for categorization
    if (word.length < 3 || stopWords.has(word)) {
      simple.push(word);
      continue;
    }

    // Categorize based on difficulty
    // Note: We don't have zipf scores on frontend, so we use difficult_words as proxy
    if (difficultWordsSet.has(word)) {
      // Difficult words are Advanced or Expert
      // Use word length as secondary indicator (longer = more expert)
      if (word.length >= 10) {
        expert.push(word);
      } else {
        advanced.push(word);
      }
    } else {
      // Non-difficult words are Simple or Medium
      // Use word length as indicator (longer = medium)
      if (word.length >= 7) {
        medium.push(word);
      } else {
        simple.push(word);
      }
    }
  }

  // Get unique examples for each level
  const getUniqueExamples = (wordList: string[], max: number = 5): string[] => {
    const unique = Array.from(new Set(wordList))
      .filter(w => !stopWords.has(w))  // Filter stop words from examples
      .sort((a, b) => b.length - a.length);  // Sort by length (longer first)
    return unique.slice(0, max);
  };

  const levels: VocabularyLevel[] = [
    {
      level: 'Simple',
      gradeRange: 'Grades 1-3',
      count: simple.length,
      percentage: totalWords > 0 ? (simple.length / totalWords) * 100 : 0,
      examples: getUniqueExamples(simple),
      color: 'bg-green-500'
    },
    {
      level: 'Medium',
      gradeRange: 'Grades 4-8',
      count: medium.length,
      percentage: totalWords > 0 ? (medium.length / totalWords) * 100 : 0,
      examples: getUniqueExamples(medium),
      color: 'bg-blue-500'
    },
    {
      level: 'Advanced',
      gradeRange: 'Grades 9-12',
      count: advanced.length,
      percentage: totalWords > 0 ? (advanced.length / totalWords) * 100 : 0,
      examples: getUniqueExamples(advanced),
      color: 'bg-orange-500'
    },
    {
      level: 'Expert',
      gradeRange: 'College+',
      count: expert.length,
      percentage: totalWords > 0 ? (expert.length / totalWords) * 100 : 0,
      examples: getUniqueExamples(expert),
      color: 'bg-red-500'
    }
  ];

  return {
    levels,
    totalWords,
    uniqueWords,
    vocabularyDiversity: totalWords > 0 ? uniqueWords / totalWords : 0
  };
}

/**
 * Get interpretation of vocabulary distribution, reconciled with the overall grade prediction
 * so vocab doesn't claim "elementary" while the text is actually graded Grade 11.
 */
export function getVocabularyInterpretation(
  result: VocabularyAnalysisResult,
  predictedGradeLevel?: string,
): string {
  const simplePercent = result.levels[0].percentage;
  const mediumPercent = result.levels[1].percentage;
  const advancedPercent = result.levels[2].percentage;
  const expertPercent = result.levels[3].percentage;
  const hardPercent = advancedPercent + expertPercent;

  const gradeNum = (() => {
    if (!predictedGradeLevel) return null;
    if (/college/i.test(predictedGradeLevel)) return 13;
    const m = predictedGradeLevel.match(/\d+/);
    return m ? parseInt(m[0], 10) : null;
  })();

  const grade = gradeNum ?? 0;

  // Reconcile: vocabulary profile vs. overall grade prediction
  if (grade >= 10 && simplePercent > 65 && hardPercent < 10) {
    return `Most words here are everyday vocabulary, yet the text is graded ${predictedGradeLevel}. That's structural — longer sentences, more subordinate clauses and denser ideas push the grade up even though the words themselves stay common.`;
  }
  if (grade <= 6 && hardPercent > 20) {
    return `Vocabulary leans advanced, but short sentences and simple structure keep the overall grade at ${predictedGradeLevel}.`;
  }
  if (grade >= 11 && expertPercent > 10) {
    return `Both the vocabulary and the structure sit at ${predictedGradeLevel}. Many low-frequency or specialist words combined with dense sentences.`;
  }

  // Generic fallbacks when grade isn't available or profile matches expectation
  if (simplePercent > 70) {
    return 'Most words are common, everyday vocabulary. Sentence structure likely does most of the work for difficulty.';
  }
  if (simplePercent > 50 && mediumPercent > 20) {
    return 'A balanced mix of everyday and mid-range words — appropriate for a general audience.';
  }
  if (expertPercent > 15) {
    return 'Heavy use of rare or specialist words — readers need strong vocabulary to keep up.';
  }
  if (expertPercent > 5 || advancedPercent > 15) {
    return 'A noticeable share of advanced words — suits high-school-and-above readers.';
  }
  return 'Vocabulary mix is varied without leaning heavily on rare words.';
}

/**
 * Human-readable criteria behind each level, shown as info popovers in the UI.
 */
export function getLevelCriteria(level: string): string {
  switch (level) {
    case 'Simple':
      return 'Everyday, high-frequency words: stop words (the, and, is…), short words (under 7 letters) that aren\'t flagged as difficult. These are words an elementary reader would already know.';
    case 'Medium':
      return 'Longer everyday words (7+ letters) that are not flagged as difficult — still within a typical middle-schooler\'s vocabulary.';
    case 'Advanced':
      return 'Words flagged as difficult: 3+ syllables, 4+ letters, not a proper noun, and not in the Dale-Chall list of 3,000 common words. High-school-level vocabulary.';
    case 'Expert':
      return 'The hardest slice of the flagged difficult words: same criteria as Advanced, plus 10+ letters — a proxy for rare, technical or specialist vocabulary you\'d expect at college level.';
    default:
      return '';
  }
}
