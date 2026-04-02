/**
 * Improvement Suggestions Generator
 *
 * Analyzes text metrics and generates prioritized, actionable suggestions
 * for improving readability.
 *
 * Research basis:
 * - Hattie & Timperley (2007): Effective feedback is specific and actionable
 * - Miller's Law (1956): 7+-2 items for cognitive load
 * - Goal-Setting Theory (Locke & Latham, 1990): Specific goals increase motivation
 */

export interface SuggestionInput {
  predicted_grade_level: string;
  flesch_reading_ease: number;
  avg_sentence_length: number;
  avg_syllables_per_word: number;
  difficult_words_count: number;
  difficult_words_percentage: number;
  difficult_sentences: Array<{ sentence: string; word_count: number }>;
  sentence_count: number;
  word_count: number;
}

export interface Suggestion {
  id: string;
  priority: 'high' | 'medium' | 'low';
  icon: string;  // Emoji icon
  title: string;
  description: string;
  action: string;
  estimatedImpact: string;  // "Grade 9 -> Grade 7"
  details?: string;
}

/**
 * Generate prioritized improvement suggestions
 *
 * Returns 3-5 suggestions ordered by impact:
 * 1. High priority: Biggest wins (sentence splitting, word replacement)
 * 2. Medium priority: Structural improvements (passive voice, subordinate clauses)
 * 3. Low priority: Polish (vocabulary diversity, formatting)
 */
export function generateImprovementSuggestions(input: SuggestionInput): Suggestion[] {
  const suggestions: Suggestion[] = [];

  // Parse current grade
  const currentGrade = parseGradeToNumber(input.predicted_grade_level);

  // Suggestion 1: Long Sentences (HIGH PRIORITY if avg > 20 words)
  if (input.avg_sentence_length > 20) {
    const longestSentences = input.difficult_sentences
      .sort((a, b) => b.word_count - a.word_count)
      .slice(0, 3);

    const longestLength = longestSentences[0]?.word_count || input.avg_sentence_length;
    const targetLength = getTargetSentenceLength(currentGrade - 2);
    const estimatedGradeChange = Math.max(1, Math.floor((input.avg_sentence_length - targetLength) / 5));

    suggestions.push({
      id: 'long-sentences',
      priority: 'high',
      icon: '\u2702\uFE0F',
      title: 'Split Long Sentences',
      description: `Your longest sentence has ${Math.round(longestLength)} words. This makes comprehension difficult.`,
      action: `Break sentences longer than ${targetLength} words into 2-3 shorter sentences. Use periods, not semicolons.`,
      estimatedImpact: `Grade ${currentGrade} \u2192 Grade ${currentGrade - estimatedGradeChange}`,
      details: `Target: ${targetLength} words per sentence (currently ${Math.round(input.avg_sentence_length)})`
    });
  }

  // Suggestion 2: Difficult Words (HIGH PRIORITY if > 15%)
  if (input.difficult_words_percentage > 15) {
    const wordsToReplace = Math.min(input.difficult_words_count, 10);
    const estimatedGradeChange = Math.max(1, Math.floor(input.difficult_words_percentage / 10));

    suggestions.push({
      id: 'difficult-words',
      priority: 'high',
      icon: '\uD83D\uDCDD',
      title: 'Replace Difficult Words',
      description: `${input.difficult_words_percentage.toFixed(1)}% of your words are considered difficult (${input.difficult_words_count} total).`,
      action: `Replace ${wordsToReplace} difficult words with simpler synonyms. Use the Simplify feature to get suggestions.`,
      estimatedImpact: `Grade ${currentGrade} \u2192 Grade ${currentGrade - estimatedGradeChange}`,
      details: 'Hover over highlighted words in your text to see simpler alternatives.'
    });
  }

  // Suggestion 3: Low Flesch Score (HIGH PRIORITY if < 50)
  if (input.flesch_reading_ease < 50) {
    const targetFlesch = getTargetFleschScore(currentGrade - 2);
    const estimatedGradeChange = Math.max(1, Math.floor((targetFlesch - input.flesch_reading_ease) / 15));

    suggestions.push({
      id: 'low-flesch',
      priority: 'high',
      icon: '\uD83D\uDCCA',
      title: 'Improve Overall Readability',
      description: `Flesch Reading Ease score is ${input.flesch_reading_ease.toFixed(1)}/100. This indicates difficult text.`,
      action: `Combine shorter sentences with simpler words. Target Flesch score: ${targetFlesch}+`,
      estimatedImpact: `Grade ${currentGrade} \u2192 Grade ${currentGrade - estimatedGradeChange}`,
      details: 'Higher Flesch scores indicate easier reading. Aim for 60+ for general audiences.'
    });
  }

  // Suggestion 4: High Syllable Count (MEDIUM PRIORITY if > 1.6)
  if (input.avg_syllables_per_word > 1.6) {
    suggestions.push({
      id: 'syllables',
      priority: 'medium',
      icon: '\uD83D\uDD24',
      title: 'Reduce Word Complexity',
      description: `Average ${input.avg_syllables_per_word.toFixed(2)} syllables per word. Simpler words are easier to read.`,
      action: 'Replace multi-syllable words with 1-2 syllable alternatives where possible.',
      estimatedImpact: `Minor improvement (0.5-1 grade)`,
      details: 'Example: "utilize" (3 syl) \u2192 "use" (1 syl)'
    });
  }

  // Suggestion 5: Very Long Text (MEDIUM PRIORITY if > 2000 words)
  if (input.word_count > 2000) {
    suggestions.push({
      id: 'text-length',
      priority: 'medium',
      icon: '\uD83D\uDCC4',
      title: 'Consider Breaking Into Sections',
      description: `Your text has ${input.word_count.toLocaleString()} words. Long texts can overwhelm readers.`,
      action: 'Add headings, bullet points, or split into multiple shorter documents.',
      estimatedImpact: 'Improves engagement and comprehension',
      details: 'Readers prefer digestible chunks. Aim for 500-1000 word sections.'
    });
  }

  // Suggestion 6: Too Many Short Sentences (LOW PRIORITY if avg < 10)
  if (input.avg_sentence_length < 10 && input.sentence_count > 5) {
    suggestions.push({
      id: 'short-sentences',
      priority: 'low',
      icon: '\uD83D\uDD17',
      title: 'Vary Sentence Length',
      description: `Average sentence is only ${input.avg_sentence_length.toFixed(1)} words. Text may feel choppy.`,
      action: 'Combine some short sentences using conjunctions (and, but, because).',
      estimatedImpact: 'Improves flow and readability',
      details: 'Mix short (5-10 words) and medium (15-20 words) sentences for rhythm.'
    });
  }

  // Suggestion 7: General Advice (LOW PRIORITY, always include)
  if (suggestions.length < 3) {
    suggestions.push({
      id: 'general-tips',
      priority: 'low',
      icon: '\uD83D\uDCA1',
      title: 'Use Active Voice',
      description: 'Passive voice makes sentences longer and harder to understand.',
      action: 'Convert passive constructions to active. Example: "was written by" \u2192 "wrote"',
      estimatedImpact: 'Minor improvement',
      details: 'Active voice is more direct and engaging.'
    });
  }

  // Sort by priority (high -> medium -> low)
  const priorityOrder = { high: 0, medium: 1, low: 2 };
  suggestions.sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);

  // Return top 5 suggestions
  return suggestions.slice(0, 5);
}

/**
 * Helper: Parse grade string to number
 */
function parseGradeToNumber(grade: string): number {
  if (grade === 'College') return 13;
  const match = grade.match(/\d+/);
  return match ? parseInt(match[0]) : 6;
}

/**
 * Helper: Get target sentence length for grade level
 */
function getTargetSentenceLength(targetGrade: number): number {
  if (targetGrade <= 3) return 8;
  if (targetGrade <= 6) return 12;
  if (targetGrade <= 9) return 18;
  if (targetGrade <= 12) return 22;
  return 25;
}

/**
 * Helper: Get target Flesch score for grade level
 */
function getTargetFleschScore(targetGrade: number): number {
  if (targetGrade <= 3) return 90;
  if (targetGrade <= 6) return 70;
  if (targetGrade <= 9) return 60;
  if (targetGrade <= 12) return 50;
  return 40;
}
