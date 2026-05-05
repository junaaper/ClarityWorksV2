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

export interface SimplificationExplanationItem {
  kind: string;
  before?: string;
  after?: string;
  frequency_before?: number;
  frequency_after?: number;
  syllables_before?: number;
  syllables_after?: number;
  text: string;
}

export interface SimplificationChange {
  type: string;
  original: string;
  simplified: string;
  reason: string;
  id: number;
  position: number;
  start: number;
  end: number;
  accepted?: boolean | null;
  original_text?: string;
  replacement_text?: string;
  preview_start?: number;
  preview_end?: number;
  review_scope?: 'word' | 'sentence' | 'paragraph';
  direction?: 'up' | 'down';
  quality_score?: number;
  quality_flags?: string[];
  rule_id?: string;
  reason_code?: string;
  evidence?: Record<string, unknown>;
  explanation_items?: SimplificationExplanationItem[];
  candidate_score?: number;
  dependency_group_id?: string;
  validation_flags?: string[];
  change_origin?: 'rule' | 'final_review' | 'rule+final_review';
  final_reviewed?: boolean;
  final_review_note?: string | null;
}

export interface SimplificationPreviewMetrics {
  raw_score: number;
  predicted_grade_level: string;
  predicted_complexity: string;
  avg_syllables_per_word: number;
  avg_words_per_sentence: number;
  invalid_sentence_count: number;
  semantic_similarity_score: number;
  target_distance: number;
}

export interface SimplificationSelectionCandidate {
  index: number;
  score: number;
  raw_score: number;
  target_distance: number;
  direction_hit: boolean;
  invalid_sentence_count: number;
  semantic_similarity_score: number;
  selection_path: string[];
  validation_flags: string[];
}

export interface SimplificationSelectionSummary {
  policy_bucket: string;
  beam_width: number;
  source_grade: number;
  target_grade: number;
  selected_score: number;
  selected_path: string[];
  direction_hit: boolean;
  target_distance: number;
  invalid_sentence_count: number;
  semantic_similarity_score: number;
  confidence_label?: string;
  final_review_applied?: boolean;
  review_adjusted_change_count?: number;
  top_candidates: SimplificationSelectionCandidate[];
}

export interface SimplifyAnalyzeResponse {
  original_text: string;
  suggested_changes: SimplificationChange[];
  preview_text: string;
  preview_metrics?: SimplificationPreviewMetrics;
  target_distance?: number;
  selection_summary?: SimplificationSelectionSummary;
}

export interface ConceptNode {
  id: string;
  label: string;
  tier: 'prerequisite' | 'intermediate' | 'target';
  description: string;
}

export interface ConceptEdge {
  from: string;
  to: string;
  relationship: string;
}

export interface ConceptGraph {
  concepts: ConceptNode[];
  edges: ConceptEdge[];
}

export interface SavedAnalysis {
  id: number;
  title: string;
  originalText: string;
  createdAt: string;
  conceptGraph?: ConceptGraph | null;
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
