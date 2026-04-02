import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from models.text_processor import TextProcessor

processor = TextProcessor()

# Test text with difficult words and sentences
test_text = """
The comprehensive implementation of this methodology necessitates careful consideration.
Students utilize various approaches to facilitate understanding.
The cat sat on the mat. She was happy.
Photosynthesis is the process by which plants convert sunlight into energy through complex biochemical reactions that were discovered by scientists who studied the phenomenon extensively over many decades of rigorous experimentation and observation.
The epistemological foundations of contemporary philosophical discourse remain fundamentally intertwined with sociolinguistic paradigms.
"""

# Test difficult words
print("=== DIFFICULT WORDS ===")
difficult_words = processor.get_difficult_words(test_text)
for word_info in difficult_words:
    print(f"\nWord: {word_info['word']}")
    print(f"  Syllables: {word_info['syllables']}")
    print(f"  Reason: {word_info['reason']}")

print(f"\nTotal difficult words found: {len(difficult_words)}")

# Verify no generic reasons
generic_reasons = ["complex word", "long word", "difficult word"]
has_generic = False
for word_info in difficult_words:
    reason = word_info['reason'].lower()
    if reason in generic_reasons or reason == "flagged as difficult word":
        print(f"  WARNING: Generic reason found for '{word_info['word']}': {word_info['reason']}")
        has_generic = True

if not has_generic and difficult_words:
    print("\nAll word reasons are specific and detailed!")

# Test difficult sentences
print("\n\n=== DIFFICULT SENTENCES ===")
difficult_sentences = processor.get_difficult_sentences(test_text)
for sent_info in difficult_sentences:
    print(f"\nSentence: {sent_info['sentence'][:100]}...")
    print(f"  Word Count: {sent_info['word_count']}")
    print(f"  Flesch Score: {sent_info['flesch_score']}")
    print(f"  Reason: {sent_info['reason']}")

print(f"\nTotal difficult sentences found: {len(difficult_sentences)}")

# Verify no generic sentence reasons
generic_sent_reasons = ["complex sentence", "long sentence"]
has_generic_sent = False
for sent_info in difficult_sentences:
    reason = sent_info['reason'].lower()
    if reason in generic_sent_reasons or reason == "complex sentence structure":
        print(f"  WARNING: Generic reason found: {sent_info['reason']}")
        has_generic_sent = True

if not has_generic_sent and difficult_sentences:
    print("\nAll sentence reasons are specific and detailed!")

# Summary
print("\n\n=== SUMMARY ===")
print(f"Difficult words: {len(difficult_words)}")
print(f"Difficult sentences: {len(difficult_sentences)}")
print(f"All reasons specific (no generic): {not has_generic and not has_generic_sent}")
