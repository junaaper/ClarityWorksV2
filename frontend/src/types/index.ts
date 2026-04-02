export interface User {
  id: number;
  email: string;
  fullName: string;
  role: 'user' | 'admin';
  isActive: boolean;
  profilePicture?: string;
  createdAt: string;
}

export interface PasswordRequirements {
  minLength: boolean;
  hasUppercase: boolean;
  hasLowercase: boolean;
  hasNumber: boolean;
  hasSpecialChar: boolean;
}

export interface AdminUser extends User {
  analysisCount: number;
}

export interface AdminAnalysis {
  id: number;
  userId: number;
  userEmail: string;
  userName: string;
  title: string;
  wordCount: number;
  sentenceCount: number;
  fleschReadingEase: number;
  predictedGradeLevel: string;
  predictedComplexity: string;
  createdAt: string;
}

export interface AdminStats {
  users: {
    total: number;
    admins: number;
    active: number;
    inactive: number;
    newThisWeek: number;
    newThisMonth: number;
  };
  analyses: {
    total: number;
    totalWords: number;
    avgReadingEase: number;
    avgGradeLevel: number;
    thisWeek: number;
    thisMonth: number;
  };
  gradeDistribution: {
    gradeLevel: string;
    count: number;
  }[];
  recentActivity: {
    id: number;
    title: string;
    createdAt: string;
    userName: string;
    userEmail: string;
  }[];
  topUsers: {
    id: number;
    fullName: string;
    email: string;
    analysisCount: number;
  }[];
}

export interface AuthResponse {
  message: string;
  user: User;
  token: string;
}

export interface BasicMetrics {
  word_count: number;
  sentence_count: number;
  paragraph_count: number;
  char_count: number;
  avg_word_length: number;
  avg_sentence_length: number;
  avg_syllables_per_word: number;
  total_syllables: number;
  polysyllabic_words: number;
  polysyllabic_percentage: number;
  type_token_ratio: number;
}

export interface ReadabilityScores {
  flesch_reading_ease: number;
  flesch_kincaid_grade: number;
  automated_readability_index: number;
  smog_readability: number;
  coleman_liau_index: number;
}

export interface Predictions {
  predicted_grade_level: string;
  predicted_complexity: string;
  confidence: number;
  raw_score?: number;
}

export interface DifficultWord {
  word: string;
  position: number;
  syllables: number;
  reason: string;
}

export interface DifficultSentence {
  sentence: string;
  position: number;
  word_count: number;
  reason: string;
  flesch_score: number;
}

export interface DifficultElements {
  difficult_words: DifficultWord[];
  difficult_sentences: DifficultSentence[];
}

export interface Statistics {
  difficult_words_count: number;
  difficult_words_percentage: number;
  polysyllabic_words_percentage?: number;
}

export interface Analysis {
  basic_metrics: BasicMetrics;
  readability_scores: ReadabilityScores;
  predictions: Predictions;
  difficult_elements: DifficultElements;
  statistics: Statistics;
}

export interface AnalysisResponse {
  success: boolean;
  analysisId: number;
  createdAt: string;
  analysis: Analysis;
}

export interface SavedAnalysis {
  id: number;
  title: string;
  originalText: string;
  createdAt: string;
  analysis: Analysis;
}

export interface AnalysisListItem {
  id: number;
  title: string;
  word_count: number;
  sentence_count: number;
  flesch_reading_ease: number;
  predicted_grade_level: string;
  predicted_complexity: string;
  created_at: string;
}

export interface Pagination {
  page: number;
  limit: number;
  totalCount: number;
  totalPages: number;
}

export interface StatsResponse {
  stats: {
    totalAnalyses: number;
    avgReadingEase: number;
    avgGradeLevel: number;
    totalWordsAnalyzed: number;
  };
  recentAnalyses: {
    id: number;
    title: string;
    predicted_grade_level: string;
    created_at: string;
  }[];
}
