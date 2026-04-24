import contextlib
import io
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from models.readability_model import ReadabilityModel
from models.simplifier import TextSimplifier


def load_test_text(filename: str) -> str:
    path = ROOT / 'data' / 'test_files' / filename
    text = path.read_text(encoding='utf-8')
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#')).strip()


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_reason_coverage(result, label):
    changes = result.get('changes', [])
    for change in changes:
        assert_true(bool(change.get('reason')), f"{label}: missing human-readable reason.")
        assert_true(bool(change.get('rule_id')), f"{label}: missing rule_id.")
        assert_true(bool(change.get('reason_code')), f"{label}: missing reason_code.")
        assert_true(bool(change.get('evidence')), f"{label}: missing evidence.")


def run_golden_case(simplifier, model, filename: str, target_grade: int):
    text = load_test_text(filename)
    original = model.predict(text)['predictions']
    original_raw = float(original['raw_score'])

    result = simplifier.simplify_to_grade(text, target_grade, mode='interactive')
    preview = result.get('preview_metrics') or {}
    final_raw = float(preview.get('raw_score', target_grade))
    original_distance = abs(original_raw - target_grade)
    final_distance = abs(final_raw - target_grade)
    label = f"{filename}->{target_grade}"

    assert_true(
        final_distance <= original_distance,
        f"{label}: rewrite did not move closer to target. {original_distance:.2f} -> {final_distance:.2f}"
    )
    assert_true(
        int(preview.get('invalid_sentence_count', 0)) == 0,
        f"{label}: invalid sentences detected in final preview."
    )
    assert_true(
        bool((result.get('selection_summary') or {}).get('direction_hit')),
        f"{label}: selection summary reports wrong-way movement."
    )
    assert_reason_coverage(result, label)


def run_guardrail_cases(simplifier):
    banned_case = simplifier.simplify_to_grade(
        "It was simply a clear plan that helped the group finish the work.",
        4,
        mode='interactive',
    )
    assert_true(
        all(change.get('simplified', '').strip().lower() != 'but' for change in banned_case['changes']),
        "Guardrail case: banned stop-word substitution returned 'but'."
    )

    phrasal_case = simplifier.simplify_to_grade(
        "Scholars refer to the archive and attest to the finding in formal reports.",
        4,
        mode='interactive',
    )
    forbidden_verbs = {'refer', 'attest'}
    assert_true(
        all(change.get('original', '').strip().lower() not in forbidden_verbs for change in phrasal_case['changes']),
        "Guardrail case: phrasal verb head was rewritten even though it should be preserved."
    )


def run_target_band_case(simplifier, filename: str, target_grade: int):
    text = load_test_text(filename)
    result = simplifier.simplify_to_grade(text, target_grade, mode='interactive')
    preview = result.get('preview_metrics') or {}
    target_distance = float(preview.get('target_distance', 999))
    label = f"{filename}->{target_grade}"

    assert_true(
        target_distance == 0.0,
        f"{label}: expected rewrite to land inside the displayed target band, got distance {target_distance:.2f}",
    )
    assert_true(
        not any(change.get('review_scope') == 'paragraph' for change in result.get('changes', [])),
        f"{label}: expected sentence/word review patches, not paragraph blobs.",
    )


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        model = ReadabilityModel()
        model.load_models()

        simplifier = TextSimplifier(readability_model=model)
        simplifier.groq_validator.client = None
        simplifier.groq_client = None
        simplifier.datamuse_finder.get_simpler_synonym = lambda _word: None

        golden_cases = [
            ('grade_12.txt', 3),
            ('grade_11.txt', 3),
            ('grade_10.txt', 3),
            ('grade_7.txt', 3),
            ('grade_3.txt', 9),
            ('grade_4.txt', 11),
            ('grade_4.txt', 12),
            ('grade_4.txt', 13),
        ]

        for filename, target_grade in golden_cases:
            run_golden_case(simplifier, model, filename, target_grade)

        run_guardrail_cases(simplifier)
        run_target_band_case(simplifier, 'grade_12.txt', 10)

    print("Golden simplification regression checks passed.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
