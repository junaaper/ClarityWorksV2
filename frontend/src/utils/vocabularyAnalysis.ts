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
 * Get interpretation of vocabulary distribution
 */
export function getVocabularyInterpretation(result: VocabularyAnalysisResult): string {
  const simplePercent = result.levels[0].percentage;
  const expertPercent = result.levels[3].percentage;

  if (simplePercent > 70) {
    return 'Your vocabulary is very accessible, suitable for elementary-level readers.';
  }
  if (simplePercent > 50) {
    return 'Your vocabulary is balanced and appropriate for general audiences.';
  }
  if (expertPercent > 15) {
    return 'Your vocabulary is advanced, requiring college-level reading skills.';
  }
  if (expertPercent > 5) {
    return 'Your vocabulary is sophisticated, suitable for high school or college readers.';
  }
  return 'Your vocabulary has good variety appropriate for your target audience.';
}
