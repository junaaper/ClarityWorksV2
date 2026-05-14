"""Quick test: does gpt-oss-120b follow our simplifier's metric targets?"""
import os, sys, time
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from models.simplifier import TextSimplifier, GRADE_TARGET_METRICS

simplifier = TextSimplifier()

if not simplifier.llm_client:
    print("ERROR: No Fireworks API key configured. Set FIREWORKS_API_KEY in .env")
    sys.exit(1)

test_text = """The process of photosynthesis represents one of the most fundamental biochemical mechanisms
in the natural world. Through this intricate process, plants and other photosynthetic organisms convert
light energy into chemical energy, which is subsequently stored in glucose molecules. The chloroplasts
within plant cells contain chlorophyll, the pigment responsible for absorbing light energy predominantly
from the blue and red portions of the electromagnetic spectrum. This absorbed energy facilitates the
conversion of carbon dioxide and water into glucose and oxygen through a series of complex enzymatic
reactions. The significance of photosynthesis extends beyond mere plant nutrition, as it fundamentally
sustains virtually all life on Earth by producing the oxygen we breathe and forming the base of most
food chains."""

scenarios = [
    ("Grade 5 downgrade", 5),
    ("Grade 10 upgrade", 10),
    ("Grade 3 extreme downgrade", 3),
]

source_grade, source_syl, source_wps = simplifier._measure_text_metrics(test_text)
print(f"Source text: grade={source_grade:.1f}, syl={source_syl:.2f}, wps={source_wps:.1f}")
print(f"{'='*70}\n")

for label, target in scenarios:
    print(f"--- {label} (target: Grade {target}) ---")
    metrics = GRADE_TARGET_METRICS.get(target, GRADE_TARGET_METRICS[8])
    print(f"Target metrics: syl={metrics['target_syl']:.2f}, wps={metrics['target_wps']}, range={metrics['min_wps']}-{metrics['max_wps']}")

    start = time.time()
    try:
        result = simplifier.simplify_to_grade(test_text, target, mode='auto')
        elapsed = time.time() - start

        rewritten = result['simplified_text']
        grade, syl, wps = simplifier._measure_text_metrics(rewritten)
        distance = simplifier._distance_to_target_band(grade, target)

        print(f"Result: grade={grade:.1f}, syl={syl:.2f}, wps={wps:.1f}")
        print(f"Target distance: {distance:.2f} {'HIT' if distance == 0 else 'MISS'}")
        print(f"Time: {elapsed:.1f}s")
        print(f"Changes: {len(result.get('changes', []))}")
        print(f"Preview: {rewritten[:150]}...")
    except Exception as e:
        elapsed = time.time() - start
        print(f"ERROR after {elapsed:.1f}s: {e}")

    print()
