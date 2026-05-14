"""Direct Fireworks API test — check what the response actually looks like."""
import os, json
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

client = OpenAI(
    base_url="https://api.fireworks.ai/inference/v1",
    api_key=os.getenv('FIREWORKS_API_KEY'),
)

models = [
    "accounts/fireworks/models/qwen3p6-plus",
    "accounts/fireworks/models/gpt-oss-120b",
]

prompt = """Rewrite the following text at exactly Grade 5 reading level.
Use simple common words (mostly 1 syllable). Every sentence must be 8-16 words.

TEXT: The process of photosynthesis represents one of the most fundamental biochemical mechanisms in the natural world.

SIMPLIFIED TEXT:"""

for model in models:
    print(f"\n{'='*60}")
    print(f"Model: {model}")
    print(f"{'='*60}")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500,
        )
        choice = resp.choices[0]
        print(f"finish_reason: {choice.finish_reason}")
        print(f"content type: {type(choice.message.content)}")
        print(f"content: {repr(choice.message.content)}")
        if hasattr(choice.message, 'refusal'):
            print(f"refusal: {choice.message.refusal}")
        # Check for thinking/reasoning content (Qwen3 specific)
        raw = choice.message.model_dump()
        print(f"Full message keys: {list(raw.keys())}")
        if 'reasoning_content' in raw:
            print(f"reasoning_content: {raw['reasoning_content'][:200]}...")
    except Exception as e:
        print(f"ERROR: {e}")
