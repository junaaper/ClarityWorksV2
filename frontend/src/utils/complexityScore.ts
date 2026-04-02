/**
 * Text Complexity Score Calculator
 *
 * Generates a unified 0-100 complexity score from readability metrics.
 * Based on weighted composite of grade level, Flesch score, vocabulary difficulty,
 * and sentence structure complexity.
 *
 * Research basis:
 * - Flesch Reading Ease (1948): Sentence length + syllables per word
 * - Dale-Chall (1948): Percentage of unfamiliar words
 * - Kincaid et al. (1975): Grade level as primary readability indicator
 * - Gunning Fog (1952): Sentence length impact on comprehension
 */

export interface ComplexityScoreInputs {
  predicted_grade_level: string;  // "Grade 3" through "College"
  flesch_reading_ease: number;    // 0-100 (higher = easier)
  difficult_words_percentage: number;  // 0-100
  avg_sentence_length: number;    // words per sentence
}

export interface ComplexityScoreResult {
  score: number;              // 0-100 (higher = more complex)
  label: string;              // "Very Easy" through "Very Difficult"
  color: string;              // Tailwind color class
  breakdown: {
    gradeContribution: number;
    fleschContribution: number;
    wordsContribution: number;
    sentenceContribution: number;
  };
}

/**
 * Calculate unified complexity score (0-100)
 *
 * Formula:
 * score = (grade/13 * 40) + ((100-flesch)/100 * 30) + (diffWords/100 * 20) + (min(sentLen/30, 1) * 10)
 *
 * Score ranges:
 * 0-20:   Very Easy (elementary school)
 * 21-40:  Easy (middle school)
 * 41-60:  Moderate (high school)
 * 61-80:  Difficult (advanced high school)
 * 81-100: Very Difficult (college/academic)
 */
export function calculateComplexityScore(inputs: ComplexityScoreInputs): ComplexityScoreResult {
  // Parse grade level to numeric (3-13)
  let gradeNumeric = 0;

  if (inputs.predicted_grade_level === 'College') {
    gradeNumeric = 13;
  } else {
    // Extract number from "Grade X"
    const match = inputs.predicted_grade_level.match(/\d+/);
    gradeNumeric = match ? parseInt(match[0]) : 6; // Default to Grade 6 if parsing fails
  }

  // Normalize each component to 0-1, then apply weight

  // Component 1: Grade Level (40% weight)
  // Normalize: Grade 3 = 0, College (Grade 13) = 1
  const gradeNormalized = Math.max(0, Math.min(1, (gradeNumeric - 3) / 10));
  const gradeContribution = gradeNormalized * 40;

  // Component 2: Flesch Score (30% weight)
  // Invert: Flesch 100 (easiest) = 0, Flesch 0 (hardest) = 1
  const fleschNormalized = Math.max(0, Math.min(1, (100 - inputs.flesch_reading_ease) / 100));
  const fleschContribution = fleschNormalized * 30;

  // Component 3: Difficult Words Percentage (20% weight)
  // Already 0-100, normalize to 0-1
  const wordsNormalized = Math.max(0, Math.min(1, inputs.difficult_words_percentage / 100));
  const wordsContribution = wordsNormalized * 20;

  // Component 4: Sentence Length (10% weight)
  // Normalize: 30+ words = 1 (very complex), <10 words = 0 (simple)
  const sentenceNormalized = Math.max(0, Math.min(1, inputs.avg_sentence_length / 30));
  const sentenceContribution = sentenceNormalized * 10;

  // Calculate total score
  const totalScore = Math.round(
    gradeContribution + fleschContribution + wordsContribution + sentenceContribution
  );

  // Determine label and color
  const label = getComplexityLabel(totalScore);
  const color = getComplexityColor(totalScore);

  return {
    score: totalScore,
    label,
    color,
    breakdown: {
      gradeContribution: Math.round(gradeContribution),
      fleschContribution: Math.round(fleschContribution),
      wordsContribution: Math.round(wordsContribution),
      sentenceContribution: Math.round(sentenceContribution)
    }
  };
}

/**
 * Get human-readable label for complexity score
 */
export function getComplexityLabel(score: number): string {
  if (score < 20) return 'Very Easy';
  if (score < 40) return 'Easy';
  if (score < 60) return 'Moderate';
  if (score < 80) return 'Difficult';
  return 'Very Difficult';
}

/**
 * Get Tailwind color class for complexity score
 */
export function getComplexityColor(score: number): string {
  if (score < 20) return 'text-green-600';
  if (score < 40) return 'text-green-500';
  if (score < 60) return 'text-yellow-500';
  if (score < 80) return 'text-orange-500';
  return 'text-red-600';
}

/**
 * Get background color class (for progress bars, badges)
 */
export function getComplexityBgColor(score: number): string {
  if (score < 20) return 'bg-green-600';
  if (score < 40) return 'bg-green-500';
  if (score < 60) return 'bg-yellow-500';
  if (score < 80) return 'bg-orange-500';
  return 'bg-red-600';
}

/**
 * Get detailed explanation of complexity score
 */
export function getComplexityExplanation(score: number): string {
  if (score < 20) {
    return 'This text is very easy to read, suitable for elementary school students (Grades 3-5). Most readers will comprehend it quickly with minimal effort.';
  }
  if (score < 40) {
    return 'This text is easy to read, appropriate for middle school students (Grades 6-8). General audiences can understand it without difficulty.';
  }
  if (score < 60) {
    return 'This text has moderate complexity, suitable for high school students (Grades 9-10). Requires focused reading but is accessible to most educated adults.';
  }
  if (score < 80) {
    return 'This text is difficult, appropriate for advanced high school or early college level (Grades 11-12). Requires strong reading skills and concentration.';
  }
  return 'This text is very difficult, written at college or academic level. Requires advanced education and sustained concentration to comprehend.';
}
