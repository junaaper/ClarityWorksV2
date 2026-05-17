"""Test fixes: Qwen thinking disabled + gpt-oss-120b with higher max_tokens."""
import os
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=os.getenv('FIREWORKS_API_KEY'),
)

long_prompt = """Rewrite the following text at exactly Grade 5 reading level.

THIS IS A SIMPLIFICATION — make it EASIER than the original.

STRICT METRIC TARGETS (the ML model grade is determined ONLY by these two numbers):
  - Average words per sentence: 12  (HARD LIMIT: each sentence must be 8-16 words)
  - Average syllables per word: 1.32  (use short, common words)
  - Sentence count: approximately 8 sentences

RULES:
1. REWRITE SHAPE: Keep the same paragraph order and overall idea order. Prefer local edits first, but you may fully rewrite an individual sentence when needed to hit the target naturally.
2. SENTENCE LENGTH: Write approximately 8 sentences. Every sentence must be 8-16 words. Split any longer sentence into two shorter ones. Use a period, not a semicolon.
3. VOCABULARY: Use simple common words (mostly 1 syllable), no jargon. Replace difficult words with simpler ones that mean THE SAME THING.
4. CONTEXTUAL FIT: Every word replacement MUST make sense in the sentence's context.
5. SYLLABLE COUNT: Aim for avg 1.32 syllables/word. Prefer short words.
6. PARAGRAPH SHAPE: Keep the SAME number of paragraphs as the original.
7. PRESERVE MEANING: Keep ALL facts. Do not skip any paragraphs.
8. NAMES & ACRONYMS: Keep all proper nouns and abbreviations exactly as written.
9. OUTPUT: Write ONLY the simplified text. No labels or commentary.

TEXT TO REWRITE:
The process of photosynthesis represents one of the most fundamental biochemical mechanisms in the natural world. Through this intricate process, plants and other photosynthetic organisms convert light energy into chemical energy, which is subsequently stored in glucose molecules. The chloroplasts within plant cells contain chlorophyll, the pigment responsible for absorbing light energy predominantly from the blue and red portions of the electromagnetic spectrum. This absorbed energy facilitates the conversion of carbon dioxide and water into glucose and oxygen through a series of complex enzymatic reactions. The significance of photosynthesis extends beyond mere plant nutrition, as it fundamentally sustains virtually all life on Earth by producing the oxygen we breathe and forming the base of most food chains.

SIMPLIFIED TEXT (Grade 5):"""

tests = [
    ("gpt-oss-120b (4096 tokens)", "accounts/fireworks/models/gpt-oss-120b", 4096, {}),
    ("gpt-oss-120b (8192 tokens)", "accounts/fireworks/models/gpt-oss-120b", 8192, {}),
    ("qwen3p6-plus (thinking OFF)", "accounts/fireworks/models/qwen3p6-plus", 4096,
     {"chat_template_kwargs": {"enable_thinking": False}}),
    ("qwen3p6-plus (16k tokens, thinking ON)", "accounts/fireworks/models/qwen3p6-plus", 16384, {}),
]

for label, model, max_tok, extra in tests:
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"{'='*60}")
    try:
        kwargs = dict(
            model=model,
            messages=[{"role": "user", "content": long_prompt}],
            temperature=0.2,
            max_tokens=max_tok,
        )
        if extra:
            kwargs["extra_body"] = extra
        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        print(f"finish_reason: {choice.finish_reason}")
        content = choice.message.content
        print(f"content type: {type(content)}")
        if content:
            print(f"content ({len(content)} chars): {content[:300]}...")
        else:
            print(f"content: None")
            raw = choice.message.model_dump()
            if raw.get('reasoning_content'):
                print(f"reasoning tokens used (first 150): {raw['reasoning_content'][:150]}...")
    except Exception as e:
        print(f"ERROR: {e}")
