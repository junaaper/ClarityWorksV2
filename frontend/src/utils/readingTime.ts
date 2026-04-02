/**
 * Reading Time Calculator
 *
 * Estimates reading time based on word count and text difficulty.
 * Adjusts for Flesch Reading Ease score (easier text = faster reading).
 *
 * Research basis:
 * - Carver (1990): Average adult reading speed 200-250 WPM
 * - Just & Carpenter (1987): Difficult text reduces speed by 20-40%
 * - Rayner et al. (2016): Speed-comprehension trade-off
 */

export interface ReadingTimeInputs {
  word_count: number;
  flesch_reading_ease: number;  // 0-100 (higher = easier)
}

export interface ReadingTimeResult {
  minutes: number;           // Total minutes (can be decimal)
  displayText: string;       // "3 min 45 sec" or "2 min read"
  wordsPerMinute: number;    // Adjusted WPM based on difficulty
  baseWPM: number;           // Unadjusted base speed (225)
}

/**
 * Calculate reading time with difficulty adjustment
 *
 * Formula:
 * 1. Base speed: 225 WPM (average adult)
 * 2. Difficulty multiplier: 0.6 to 1.0 based on Flesch score
 *    - Flesch 100 (easiest): 1.0x speed (225 WPM)
 *    - Flesch 50 (moderate): 0.8x speed (180 WPM)
 *    - Flesch 0 (hardest): 0.6x speed (135 WPM)
 * 3. Time = words / adjusted_wpm
 */
export function calculateReadingTime(inputs: ReadingTimeInputs): ReadingTimeResult {
  const BASE_WPM = 225;  // Average adult reading speed
  const MIN_SPEED_MULTIPLIER = 0.6;  // Slowest reading (difficult text)
  const MAX_SPEED_MULTIPLIER = 1.0;  // Fastest reading (easy text)

  // Normalize Flesch score (0-100) to speed multiplier (0.6-1.0)
  const fleschNormalized = Math.max(0, Math.min(100, inputs.flesch_reading_ease)) / 100;
  const speedMultiplier = MIN_SPEED_MULTIPLIER + (fleschNormalized * (MAX_SPEED_MULTIPLIER - MIN_SPEED_MULTIPLIER));

  // Calculate adjusted WPM
  const adjustedWPM = Math.round(BASE_WPM * speedMultiplier);

  // Calculate total minutes
  const totalMinutes = inputs.word_count / adjustedWPM;

  // Ensure minimum 1 minute for psychological perception
  const finalMinutes = Math.max(1, totalMinutes);

  // Format display text
  const displayText = formatReadingTime(finalMinutes);

  return {
    minutes: finalMinutes,
    displayText,
    wordsPerMinute: adjustedWPM,
    baseWPM: BASE_WPM
  };
}

/**
 * Format reading time for display
 *
 * Examples:
 * - 1.2 minutes -> "1 min read"
 * - 3.75 minutes -> "4 min read"
 * - 7.5 minutes -> "7 min 30 sec"
 * - 15.25 minutes -> "15 min read"
 */
function formatReadingTime(minutes: number): string {
  const wholeMinutes = Math.floor(minutes);
  const seconds = Math.round((minutes - wholeMinutes) * 60);

  // For very short reads, show seconds
  if (wholeMinutes === 0) {
    return `${seconds} sec read`;
  }

  // For reads under 10 minutes, show minutes and seconds if seconds >= 30
  if (wholeMinutes < 10 && seconds >= 30) {
    return `${wholeMinutes} min ${seconds} sec`;
  }

  // For longer reads, round to nearest minute
  const roundedMinutes = seconds >= 30 ? wholeMinutes + 1 : wholeMinutes;
  return `${roundedMinutes} min read`;
}

/**
 * Get reading pace description
 */
export function getReadingPaceDescription(wpm: number): string {
  if (wpm >= 250) return 'Fast reading pace';
  if (wpm >= 200) return 'Average reading pace';
  if (wpm >= 150) return 'Moderate reading pace';
  return 'Careful reading pace';
}

/**
 * Get reading time color (visual indicator)
 */
export function getReadingTimeColor(minutes: number): string {
  if (minutes < 3) return 'text-green-600';
  if (minutes < 10) return 'text-blue-600';
  if (minutes < 20) return 'text-yellow-600';
  return 'text-orange-600';
}
