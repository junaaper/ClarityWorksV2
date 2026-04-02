import requests


class DatamuseSynonymFinder:
    """
    Find simpler synonyms using Datamuse API
    API: Free, unlimited, no key required
    Docs: https://www.datamuse.com/api/
    """

    def __init__(self):
        self.base_url = "https://api.datamuse.com/words"

    def get_simpler_synonym(self, word):
        """
        Query Datamuse API for simpler synonyms

        Args:
            word: Complex word to simplify

        Returns:
            str or None: Simpler synonym if found
        """
        try:
            # Query for words with similar meaning
            # ml = means like
            # md=f = include frequency data
            params = {
                'ml': word,
                'md': 'f',
                'max': 20
            }

            response = requests.get(
                self.base_url,
                params=params,
                timeout=3
            )

            if response.status_code != 200:
                return None

            results = response.json()

            return self._find_simplest(word, results)

        except Exception as e:
            print(f"Datamuse API error: {e}")
            return None

    def _find_simplest(self, original_word, results):
        """Find simplest synonym from Datamuse results"""

        for result in results:
            synonym = result.get('word', '')
            tags = result.get('tags', [])

            if not synonym:
                continue

            if synonym.lower() == original_word.lower():
                continue

            # Skip if longer than original
            if len(synonym) > len(original_word):
                continue

            # Skip multi-word phrases
            if ' ' in synonym:
                continue

            # Check if it has frequency data
            has_freq = any('f:' in str(tag) for tag in tags)

            if has_freq:
                return synonym

        return None


def test_datamuse():
    """Test Datamuse API"""
    finder = DatamuseSynonymFinder()

    test_words = [
        "utilize",
        "commence",
        "purchase",
        "assistance",
        "demonstrate",
        "methodology"
    ]

    print("=" * 60)
    print("TESTING DATAMUSE API")
    print("=" * 60)

    for word in test_words:
        synonym = finder.get_simpler_synonym(word)
        if synonym:
            print(f"  {word:20s} -> {synonym}")
        else:
            print(f"  {word:20s} -> (no result)")

if __name__ == "__main__":
    test_datamuse()
