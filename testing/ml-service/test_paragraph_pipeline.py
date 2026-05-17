"""Test the paragraph-first rewrite pipeline end-to-end."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'ml-service'
sys.path.insert(0, str(ROOT))
os.environ.setdefault('THINC_NO_TORCH', '1')

from dotenv import load_dotenv
load_dotenv(dotenv_path=ROOT / '.env')

from models.simplifier import TextSimplifier

TEST_TEXT = """The process of photosynthesis represents one of the most fundamental biochemical mechanisms in the natural world. Through this intricate process, plants and other photosynthetic organisms convert light energy, primarily from the sun, into chemical energy stored in glucose molecules. This remarkable transformation occurs within specialized cellular structures called chloroplasts, which contain the pigment chlorophyll responsible for absorbing light energy.

The photosynthetic process can be divided into two major stages: the light-dependent reactions and the light-independent reactions, commonly known as the Calvin cycle. During the light-dependent reactions, which take place in the thylakoid membranes of the chloroplasts, water molecules are split through a process called photolysis. This splitting of water releases oxygen as a byproduct, which is essential for aerobic life on Earth, while also generating ATP and NADPH, two energy-carrying molecules crucial for the subsequent stage.

The Calvin cycle, occurring in the stroma of the chloroplasts, utilizes the ATP and NADPH produced during the light-dependent reactions to fix atmospheric carbon dioxide into organic molecules through a series of enzyme-catalyzed reactions. The key enzyme in this process, RuBisCO (ribulose-1,5-bisphosphate carboxylase/oxygenase), is considered the most abundant protein on Earth, highlighting the global significance of photosynthesis. Through these coordinated biochemical pathways, photosynthetic organisms not only sustain themselves but also form the foundation of virtually all food chains and are responsible for maintaining the atmospheric oxygen levels that support complex life."""


def test_pipeline():
    simplifier = TextSimplifier()

    words = len(TEST_TEXT.split())
    paras = len([p for p in TEST_TEXT.split('\n\n') if p.strip()])
    print(f"Test text: {words} words, {paras} paragraphs")
    print(f"Should use paragraph pipeline: {simplifier._should_use_paragraph_pipeline(TEST_TEXT)}")

    groups = simplifier._split_into_rewrite_groups(TEST_TEXT)
    print(f"Rewrite groups: {len(groups)}")
    for i, g in enumerate(groups):
        print(f"  Group {i}: {g['word_count']} words, indices={g['group_indices']}")

    print()
    scenarios = [
        (5, "Grade 5 downgrade"),
        (10, "Grade 10 moderate"),
    ]

    for target, label in scenarios:
        print("=" * 70)
        print(f"--- {label} (target: Grade {target}) ---")
        print("=" * 70)
        start = time.time()
        result = simplifier.simplify_to_grade(TEST_TEXT, target, mode='auto')
        elapsed = time.time() - start

        print(f"\nResult grade: {result['preview_metrics']['raw_score']:.1f}")
        print(f"Target distance: {result['target_distance']:.2f}")
        print(f"Time: {elapsed:.1f}s")
        print(f"Changes: {len(result['changes'])}")
        gen_mode = result.get('selection_summary', {}).get('generation_mode', 'unknown')
        print(f"Generation mode: {gen_mode}")
        print(f"Preview: {result['simplified_text'][:200]}...")
        print()


if __name__ == '__main__':
    test_pipeline()
