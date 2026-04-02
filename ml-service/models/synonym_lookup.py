import json
import pandas as pd
import os

class SynonymLookup:
    """Manages word lists and synonym mappings for readability analysis"""

    def __init__(self):
        base_path = os.path.join(os.path.dirname(__file__), '..', 'data')

        # Load simplification map (complex -> simple)
        with open(os.path.join(base_path, 'simplification_map.json'), 'r') as f:
            self.simplification_map = json.load(f)

        # Load complexification map (simple -> complex)
        with open(os.path.join(base_path, 'complexification_map.json'), 'r') as f:
            self.complexification_map = json.load(f)

        # Load Dale-Chall easy words (3,000 common words)
        with open(os.path.join(base_path, 'dale_chall_3000.txt'), 'r') as f:
            self.dale_chall_words = set(
                line.strip().lower()
                for line in f
                if line.strip() and not line.startswith('#')
            )

        # Load COCA word frequency rankings
        self.word_frequency = pd.read_csv(os.path.join(base_path, 'coca_frequency.csv'))
        self.word_freq_dict = dict(zip(
            self.word_frequency['word'],
            self.word_frequency['rank']
        ))

        # Load Academic Word List (570 academic words)
        with open(os.path.join(base_path, 'academic_word_list.txt'), 'r') as f:
            self.academic_words = set(
                line.strip().lower()
                for line in f
                if line.strip() and not line.startswith('#')
            )

    def get_word_frequency_rank(self, word):
        """
        Get frequency rank from COCA corpus

        Args:
            word: Word to check

        Returns:
            int: Rank (1 = most common, 999999 = not found)
        """
        return self.word_freq_dict.get(word.lower(), 999999)

    def is_academic_word(self, word):
        """Check if word is in Academic Word List (Grade 10+)"""
        return word.lower() in self.academic_words

    def is_easy_word(self, word):
        """Check if word is in Dale-Chall easy words list (Grade 4 baseline)"""
        return word.lower() in self.dale_chall_words

    def get_simpler_synonym(self, word):
        """
        Get simpler alternative for a complex word

        Args:
            word: Complex word

        Returns:
            str or None: Simpler synonym if available
        """
        mapping = self.simplification_map.get(word.lower())
        return mapping['simple'] if mapping else None

    def get_complex_synonyms(self, word):
        """
        Get more complex alternatives for upgrading text

        Args:
            word: Simple word

        Returns:
            list: Complex synonyms
        """
        mapping = self.complexification_map.get(word.lower())
        return mapping['complex'] if mapping else []

    def get_word_complexity_level(self, word):
        """
        Categorize word complexity based on frequency

        Args:
            word: Word to check

        Returns:
            str: 'simple', 'intermediate', 'advanced', or 'expert'
        """
        rank = self.get_word_frequency_rank(word)

        if rank <= 5000:
            return 'simple'
        elif rank <= 10000:
            return 'intermediate'
        elif rank <= 20000:
            return 'advanced'
        else:
            return 'expert'
