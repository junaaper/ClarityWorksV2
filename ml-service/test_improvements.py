"""Test script to verify improvements to difficult word and sentence detection."""

import sys
import io

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from models.text_processor import TextProcessor

# Test text with various cases
test_texts = {
    "Proper Nouns": "My name is Junaid and I work at Google in California with Maria.",
    "Abbreviations": "The CLS metric and API integration require HTTPS and SSL certificates.",
    "Common Words": "I need to borrow some money from the club to get the details about the event.",
    "Mixed Difficulty": "The comprehensive implementation necessitates sophisticated architectural considerations while maintaining simplicity.",
    "Long Sentence": "This is a very long sentence that contains many words and clauses, and it goes on and on with multiple ideas, complex structure, and numerous subordinate clauses that make it difficult to read and understand quickly."
}

processor = TextProcessor()

print("=" * 80)
print("DIFFICULT WORD DETECTION TEST")
print("=" * 80)

for test_name, text in test_texts.items():
    print(f"\n\n{test_name}:")
    print(f"Text: {text}")
    print("-" * 80)

    difficult_words = processor.get_difficult_words(text)

    if difficult_words:
        print(f"Found {len(difficult_words)} difficult word(s):")
        for word_info in difficult_words:
            print(f"  • {word_info['word']}: {word_info['syllables']} syllables - {word_info['reason']}")
    else:
        print("  ✓ No difficult words detected")

print("\n\n" + "=" * 80)
print("DIFFICULT SENTENCE DETECTION TEST")
print("=" * 80)

combined_text = " ".join(test_texts.values())
difficult_sentences = processor.get_difficult_sentences(combined_text)

if difficult_sentences:
    print(f"\nFound {len(difficult_sentences)} difficult sentence(s):")
    for sent_info in difficult_sentences:
        print(f"\n  Position: {sent_info['position']}")
        print(f"  Sentence: {sent_info['sentence'][:100]}...")
        print(f"  Word count: {sent_info['word_count']}")
        print(f"  Flesch score: {sent_info['flesch_score']}")
        print(f"  Reason: {sent_info['reason']}")
else:
    print("\n  ✓ No difficult sentences detected")

print("\n\n" + "=" * 80)
print("BASIC METRICS TEST")
print("=" * 80)

metrics = processor.calculate_basic_metrics(combined_text)
print(f"\nWord count: {metrics['word_count']}")
print(f"Sentence count: {metrics['sentence_count']}")
print(f"Avg sentence length: {metrics['avg_sentence_length']}")
print(f"Avg syllables per word: {metrics['avg_syllables_per_word']}")
print(f"Polysyllabic words: {metrics['polysyllabic_words']} ({metrics['polysyllabic_percentage']:.1f}%)")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
