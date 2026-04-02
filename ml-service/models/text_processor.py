import re
import pyphen
from typing import List, Dict, Tuple
from models.synonym_lookup import SynonymLookup


class TextProcessor:
    def __init__(self):
        self.dic = pyphen.Pyphen(lang='en_US')
        self.synonym_lookup = SynonymLookup()

    def count_syllables(self, word: str) -> int:
        """Count syllables in a word using pyphen."""
        word = word.lower().strip()
        if not word:
            return 0

        # Handle special cases
        if len(word) <= 3:
            return 1

        hyphenated = self.dic.inserted(word)
        syllables = len(hyphenated.split('-'))
        return max(1, syllables)

    def get_words(self, text: str) -> List[str]:
        """Extract words from text."""
        # Remove punctuation except apostrophes within words
        text = re.sub(r"[^\w\s']", ' ', text)
        words = text.split()
        return [w.strip("'") for w in words if w.strip("'")]

    def get_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Split on sentence-ending punctuation
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def get_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]

    def is_proper_noun_or_abbreviation(self, word: str) -> bool:
        """Check if word is likely a proper noun or abbreviation."""
        if not word:
            return False

        # Proper nouns: capitalized words (except at sentence start)
        if word[0].isupper() and len(word) > 1:
            return True

        # Abbreviations: all caps, 2-5 letters
        if word.isupper() and 2 <= len(word) <= 5:
            return True

        # Words with multiple caps (e.g., iPhone, JavaScript)
        if sum(1 for c in word if c.isupper()) >= 2:
            return True

        return False

    def is_difficult_word(self, word: str) -> bool:
        """Check if a word is difficult (not in Dale-Chall list and not proper noun/abbreviation)."""
        # Skip proper nouns and abbreviations
        if self.is_proper_noun_or_abbreviation(word):
            return False

        word_lower = word.lower().strip()

        # Skip very short words
        if len(word_lower) < 4:
            return False

        # Remove common suffixes for checking
        base_word = re.sub(r'(ing|ed|es|s|ly|er|est|ment|ness|tion|sion|ful|less|ity)$', '', word_lower)

        # Check if word or its base form is in the Dale-Chall easy words list
        if self.synonym_lookup.is_easy_word(word_lower) or self.synonym_lookup.is_easy_word(base_word):
            return False

        # Must have 3+ syllables to be considered difficult
        if self.count_syllables(word_lower) < 3:
            return False

        return True

    def get_word_difficulty_reason(self, word: str, syllable_count: int) -> str:
        """
        Generate detailed, specific reason for word difficulty.

        Args:
            word: The difficult word
            syllable_count: Number of syllables

        Returns:
            str: Detailed explanation of why word is difficult
        """
        reasons = []

        # 1. Syllable complexity
        if syllable_count >= 4:
            reasons.append(f"{syllable_count} syllables (very complex)")
        elif syllable_count == 3:
            reasons.append(f"{syllable_count} syllables (moderately complex)")

        # 2. Word frequency check
        word_rank = self.synonym_lookup.get_word_frequency_rank(word)
        if word_rank > 20000:
            reasons.append(f"extremely rare word (rank #{word_rank:,})")
        elif word_rank > 10000:
            reasons.append(f"rare word (rank #{word_rank:,})")
        elif word_rank > 5000:
            reasons.append(f"uncommon word (rank #{word_rank:,})")

        # 3. Dale-Chall easy words check
        if not self.synonym_lookup.is_easy_word(word):
            reasons.append("not in Dale-Chall easy words (Grade 4 baseline)")

        # 4. Academic vocabulary check
        if self.synonym_lookup.is_academic_word(word):
            reasons.append("academic vocabulary (Grade 10+ term)")

        # 5. Technical suffix detection
        technical_suffixes = [
            ('-ology', 'study of'),
            ('-ism', 'belief/system'),
            ('-tion', 'action/process'),
            ('-sion', 'action/process'),
            ('-ment', 'result/action'),
            ('-ance', 'state/quality'),
            ('-ence', 'state/quality'),
            ('-ity', 'state/quality'),
            ('-ness', 'state/quality')
        ]

        for suffix, meaning in technical_suffixes:
            if word.lower().endswith(suffix):
                reasons.append(f"technical term ({suffix} = {meaning})")
                break

        # 6. Suggest simpler alternative
        simpler = self.synonym_lookup.get_simpler_synonym(word)
        if simpler:
            reasons.append(f"simpler alternative: '{simpler}'")

        # Return combined reasons or fallback
        return " | ".join(reasons) if reasons else "flagged as difficult word"

    def get_sentence_difficulty_reason(self, sentence: str, metrics: Dict) -> str:
        """
        Generate specific, backed-up reason for sentence difficulty.

        Args:
            sentence: The sentence text
            metrics: Dict with difficulty metrics

        Returns:
            str: Detailed explanation
        """
        reasons = []

        # 1. Sentence length check
        word_count = metrics.get('word_count', 0)
        if word_count >= 30:
            reasons.append(f"very long sentence ({word_count} words, target <20)")
        elif word_count >= 25:
            reasons.append(f"long sentence ({word_count} words, target <20)")

        # 2. Readability score check
        flesch_score = metrics.get('flesch_score', 100)
        if flesch_score < 30:
            reasons.append(f"very low readability ({flesch_score:.1f}/100, target >60)")
        elif flesch_score < 50:
            reasons.append(f"low readability ({flesch_score:.1f}/100, target >60)")

        # 3. Difficult words with examples
        difficult_words_count = metrics.get('difficult_words_count', 0)
        difficult_words = metrics.get('difficult_words', [])

        if difficult_words_count >= 5:
            examples = ", ".join(difficult_words[:3])
            reasons.append(f"{difficult_words_count} difficult words (e.g., {examples})")
        elif difficult_words_count >= 3:
            examples = ", ".join(difficult_words[:3])
            reasons.append(f"{difficult_words_count} difficult words ({examples})")

        # 4. Polysyllabic word count
        polysyllabic_count = metrics.get('polysyllabic_count', 0)
        if polysyllabic_count >= 7:
            reasons.append(f"{polysyllabic_count} complex words (3+ syllables)")
        elif polysyllabic_count >= 5:
            reasons.append(f"{polysyllabic_count} moderately complex words (3+ syllables)")

        # 5. Passive voice detection
        has_passive = metrics.get('has_passive_voice', False)
        if has_passive:
            reasons.append("passive voice detected (less direct)")

        # 6. Subordinate clauses
        subordinate_clauses = metrics.get('subordinate_clauses', 0)
        if subordinate_clauses >= 3:
            reasons.append(f"{subordinate_clauses} embedded clauses (complex structure)")
        elif subordinate_clauses >= 2:
            reasons.append(f"{subordinate_clauses} embedded clauses")

        # Return combined reasons or fallback
        return " | ".join(reasons) if reasons else "complex sentence structure"

    def get_difficult_words(self, text: str) -> List[Dict]:
        """Find all difficult words in text with their positions and detailed reasons."""
        words = self.get_words(text)
        difficult_words = []
        seen_words = set()  # Avoid duplicates

        for i, word in enumerate(words):
            word_lower = word.lower()

            # Skip if already added (case-insensitive)
            if word_lower in seen_words:
                continue

            if self.is_difficult_word(word):
                syllables = self.count_syllables(word)
                reason = self.get_word_difficulty_reason(word_lower, syllables)

                difficult_words.append({
                    "word": word,
                    "position": i,
                    "syllables": syllables,
                    "reason": reason
                })

                seen_words.add(word_lower)

        return difficult_words

    def get_difficult_sentences(self, text: str) -> List[Dict]:
        """Find difficult sentences in text with detailed reasons."""
        sentences = self.get_sentences(text)
        difficult_sentences = []

        for i, sentence in enumerate(sentences):
            sentence_text = sentence.strip()
            if not sentence_text:
                continue

            words = self.get_words(sentence_text)
            word_count = len(words)

            # Skip very short sentences
            if word_count < 5:
                continue

            # Calculate Flesch score for this sentence
            flesch_score = self.calculate_flesch_score_for_sentence(sentence_text)

            # Count difficult words in sentence
            difficult_words_in_sentence = []
            polysyllabic_count = 0

            for word in words:
                clean_word = word.strip('.,!?;:"()[]{}').lower()
                if not clean_word:
                    continue

                syllables = self.count_syllables(clean_word)
                if syllables >= 3:
                    polysyllabic_count += 1

                # Check if word is difficult
                if (len(clean_word) >= 4 and
                    syllables >= 3 and
                    not self.synonym_lookup.is_easy_word(clean_word) and
                    not self.is_proper_noun_or_abbreviation(word)):
                    difficult_words_in_sentence.append(clean_word)

            difficult_words_count = len(difficult_words_in_sentence)

            # Detect passive voice (simple heuristic)
            has_passive_voice = self.detect_passive_voice(sentence_text)

            # Count subordinate clauses (simple heuristic)
            subordinate_clauses = self.count_subordinate_clauses(sentence_text)

            # Determine if sentence is difficult (multiple criteria)
            is_difficult = False

            # Criteria 1: Long sentence
            if word_count >= 25:
                is_difficult = True

            # Criteria 2: Low Flesch score with difficult words
            if flesch_score < 30 and difficult_words_count >= 2:
                is_difficult = True

            # Criteria 3: Many difficult words
            if difficult_words_count >= 3:
                is_difficult = True

            # Criteria 4: Many polysyllabic words
            if polysyllabic_count >= 5:
                is_difficult = True

            if is_difficult:
                metrics = {
                    'word_count': word_count,
                    'flesch_score': flesch_score,
                    'difficult_words_count': difficult_words_count,
                    'difficult_words': difficult_words_in_sentence,
                    'polysyllabic_count': polysyllabic_count,
                    'has_passive_voice': has_passive_voice,
                    'subordinate_clauses': subordinate_clauses
                }

                reason = self.get_sentence_difficulty_reason(sentence_text, metrics)

                difficult_sentences.append({
                    'sentence': sentence_text[:200] + ("..." if len(sentence_text) > 200 else ""),
                    'position': i,
                    'word_count': word_count,
                    'reason': reason,
                    'flesch_score': round(flesch_score, 1)
                })

        return difficult_sentences

    def calculate_flesch_score_for_sentence(self, sentence: str) -> float:
        """Calculate Flesch Reading Ease for a single sentence."""
        words = sentence.split()
        word_count = len(words)

        if word_count == 0:
            return 100.0

        syllable_count = sum(self.count_syllables(word.strip('.,!?;:"()[]{}')) for word in words)

        # Flesch formula: 206.835 - 1.015(words/sentences) - 84.6(syllables/words)
        avg_syllables_per_word = syllable_count / word_count if word_count > 0 else 0
        score = 206.835 - 1.015 * word_count - 84.6 * avg_syllables_per_word

        # Clamp to 0-100
        return max(0, min(100, score))

    def detect_passive_voice(self, sentence: str) -> bool:
        """
        Simple heuristic to detect passive voice.
        Looks for: "was/were/is/are/been + past participle"
        """
        passive_indicators = [
            'was ', 'were ', 'is ', 'are ', 'been ',
            'was not', 'were not', 'is not', 'are not'
        ]

        sentence_lower = sentence.lower()
        for indicator in passive_indicators:
            if indicator in sentence_lower:
                return True

        return False

    def count_subordinate_clauses(self, sentence: str) -> int:
        """
        Simple heuristic to count subordinate clauses.
        Looks for: which, that, because, although, when, while, etc.
        """
        clause_markers = [
            'which', 'that', 'because', 'although', 'though',
            'when', 'while', 'where', 'who', 'whom', 'whose',
            'if', 'unless', 'until', 'since', 'after', 'before'
        ]

        words = sentence.lower().split()
        count = 0

        for marker in clause_markers:
            if marker in words:
                count += 1

        return count

    def calculate_basic_metrics(self, text: str) -> Dict:
        """Calculate basic text metrics."""
        words = self.get_words(text)
        sentences = self.get_sentences(text)
        paragraphs = self.get_paragraphs(text)

        word_count = len(words)
        sentence_count = len(sentences)
        paragraph_count = len(paragraphs)
        char_count = len(text.replace(' ', ''))

        avg_word_length = sum(len(w) for w in words) / word_count if word_count > 0 else 0
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0

        total_syllables = sum(self.count_syllables(w) for w in words)
        avg_syllables_per_word = total_syllables / word_count if word_count > 0 else 0

        polysyllabic_words = sum(1 for w in words if self.count_syllables(w) >= 3)
        polysyllabic_percentage = (polysyllabic_words / word_count * 100) if word_count > 0 else 0

        # Type-Token Ratio
        unique_words = set(w.lower() for w in words)
        type_token_ratio = len(unique_words) / word_count if word_count > 0 else 0

        return {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "paragraph_count": paragraph_count,
            "char_count": char_count,
            "avg_word_length": round(avg_word_length, 2),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "avg_syllables_per_word": round(avg_syllables_per_word, 2),
            "total_syllables": total_syllables,
            "polysyllabic_words": polysyllabic_words,
            "polysyllabic_percentage": round(polysyllabic_percentage, 2),
            "type_token_ratio": round(type_token_ratio, 4)
        }
