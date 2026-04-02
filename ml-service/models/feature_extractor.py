import textstat
import numpy as np
import spacy
from typing import Dict
from .text_processor import TextProcessor

nlp = spacy.load('en_core_web_sm')

class FeatureExtractor:
    def __init__(self):
        self.processor = TextProcessor()

    def extract_features(self, text: str) -> Dict:
        """Extract all features from text for ML model."""
        basic_metrics = self.processor.calculate_basic_metrics(text)

        # Get readability scores using textstat
        readability_scores = {
            "flesch_reading_ease": textstat.flesch_reading_ease(text),
            "flesch_kincaid_grade": textstat.flesch_kincaid_grade(text),
            "automated_readability_index": textstat.automated_readability_index(text),
            "smog_readability": textstat.smog_index(text),
            "coleman_liau_index": textstat.coleman_liau_index(text),
            "dale_chall_score": textstat.dale_chall_readability_score(text),
            "linsear_write": textstat.linsear_write_formula(text),
            "gunning_fog": textstat.gunning_fog(text)
        }

        # Get difficult elements
        difficult_words = self.processor.get_difficult_words(text)
        difficult_sentences = self.processor.get_difficult_sentences(text)

        words = self.processor.get_words(text)
        word_count = len(words)

        statistics = {
            "difficult_words_count": len(difficult_words),
            "difficult_words_percentage": round(len(difficult_words) / word_count * 100, 2) if word_count > 0 else 0,
            "polysyllabic_words_percentage": basic_metrics["polysyllabic_percentage"]
        }

        return {
            "basic_metrics": basic_metrics,
            "readability_scores": readability_scores,
            "difficult_elements": {
                "difficult_words": difficult_words[:50],  # Limit to top 50
                "difficult_sentences": difficult_sentences[:20]  # Limit to top 20
            },
            "statistics": statistics
        }

    def get_ml_features(self, text: str) -> list:
        """
        Extract 16 features for ML model prediction.

        Original 11:
        - word_count, sentence_count, avg_sentence_length
        - avg_word_length, avg_syllables_per_word
        - difficult_words_percentage
        - flesch_reading_ease, flesch_kincaid_grade
        - automated_readability_index, smog_readability
        - type_token_ratio

        New 5:
        - passive_voice_percentage
        - subordinate_clause_density
        - pos_diversity_score
        - lexical_diversity
        - sentence_complexity_variance
        """
        features = self.extract_features(text)

        # Original 11 features
        ml_features = [
            features["basic_metrics"]["word_count"],
            features["basic_metrics"]["sentence_count"],
            features["basic_metrics"]["avg_sentence_length"],
            features["basic_metrics"]["avg_word_length"],
            features["basic_metrics"]["avg_syllables_per_word"],
            features["statistics"]["difficult_words_percentage"],
            features["readability_scores"]["flesch_reading_ease"],
            features["readability_scores"]["flesch_kincaid_grade"],
            features["readability_scores"]["automated_readability_index"],
            features["readability_scores"]["smog_readability"],
            features["basic_metrics"]["type_token_ratio"],
        ]

        # New 5 NLP features
        ml_features.append(self._calculate_passive_voice_percentage(text))
        ml_features.append(self._calculate_subordinate_clause_density(text))
        ml_features.append(self._calculate_pos_diversity(text))
        ml_features.append(self._calculate_lexical_diversity(text))
        ml_features.append(self._calculate_sentence_variance(text))

        return ml_features

    def get_feature_names(self) -> list:
        """Get names of all 16 ML features."""
        return [
            'word_count',
            'sentence_count',
            'avg_sentence_length',
            'avg_word_length',
            'avg_syllables_per_word',
            'difficult_words_percentage',
            'flesch_reading_ease',
            'flesch_kincaid_grade',
            'automated_readability_index',
            'smog_readability',
            'type_token_ratio',
            'passive_voice_percentage',
            'subordinate_clause_density',
            'pos_diversity_score',
            'lexical_diversity',
            'sentence_complexity_variance'
        ]

    def _calculate_passive_voice_percentage(self, text: str) -> float:
        """Calculate percentage of sentences with passive voice."""
        doc = nlp(text)
        sentences = list(doc.sents)

        if not sentences:
            return 0.0

        passive_count = 0
        for sent in sentences:
            if any(token.dep_ == 'nsubjpass' for token in sent):
                passive_count += 1

        return (passive_count / len(sentences)) * 100

    def _calculate_subordinate_clause_density(self, text: str) -> float:
        """Calculate average subordinate clauses per sentence."""
        doc = nlp(text)
        sentences = list(doc.sents)

        if not sentences:
            return 0.0

        total_clauses = 0
        clause_markers = ['mark', 'advcl', 'acl', 'relcl']

        for sent in sentences:
            clause_count = sum(1 for token in sent if token.dep_ in clause_markers)
            total_clauses += clause_count

        return total_clauses / len(sentences)

    def _calculate_pos_diversity(self, text: str) -> float:
        """
        Calculate diversity of POS tags.
        Higher diversity = more varied sentence structures.
        """
        doc = nlp(text)

        pos_tags = [token.pos_ for token in doc if token.is_alpha]

        if not pos_tags:
            return 0.0

        unique_pos = len(set(pos_tags))
        total_pos = len(pos_tags)

        return unique_pos / total_pos if total_pos > 0 else 0.0

    def _calculate_lexical_diversity(self, text: str) -> float:
        """Calculate lexical diversity (unique words / total words)."""
        words = text.split()
        if not words:
            return 0.0
        return len(set(w.lower() for w in words)) / len(words)

    def _calculate_sentence_variance(self, text: str) -> float:
        """
        Calculate variance in sentence lengths.
        Higher variance = more complex writing style.
        """
        doc = nlp(text)
        sentences = list(doc.sents)

        if len(sentences) < 2:
            return 0.0

        sentence_lengths = []
        for sent in sentences:
            words = [token for token in sent if token.is_alpha]
            sentence_lengths.append(len(words))

        variance = np.var(sentence_lengths)
        return float(variance)
