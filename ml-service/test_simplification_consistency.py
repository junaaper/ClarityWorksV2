import contextlib
import contextlib
import io
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from models.readability_model import ReadabilityModel
from models.simplifier import TextSimplifier
from utils.change_patches import apply_changes_by_span


def load_test_text(filename: str) -> str:
    path = ROOT / 'data' / 'test_files' / filename
    text = path.read_text(encoding='utf-8')
    return '\n'.join(line for line in text.splitlines() if not line.startswith('#')).strip()


def assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}\nEXPECTED:\n{expected}\n\nACTUAL:\n{actual}")


def run_case(simplifier, label, text, target_grade):
    result = simplifier.simplify_to_grade(text, target_grade, mode='interactive')
    if result['simplified_text'] != text and not result['changes']:
        raise AssertionError(f"{label}: preview text changed but no diff changes were returned.")

    all_ids = [change['id'] for change in result['changes']]
    rebuilt = apply_changes_by_span(text, result['changes'], all_ids)
    assert_equal(
        rebuilt,
        result['simplified_text'],
        f"{label}: applying all accepted changes should reproduce the preview text."
    )

    denied_all = apply_changes_by_span(text, result['changes'], [])
    assert_equal(
        denied_all,
        text,
        f"{label}: denying every change should preserve the original text."
    )

    for change in result['changes']:
        start = change['start']
        end = change['end']
        original_text = change.get('original_text', '')
        if text[start:end] != original_text:
            raise AssertionError(
                f"{label}: change {change['id']} has mismatched original span.\n"
                f"Span text: {text[start:end]!r}\n"
                f"Stored original_text: {original_text!r}"
            )
        if not (change.get('reason') or '').strip():
            raise AssertionError(f"{label}: change {change['id']} is missing a reason.")
        if not change.get('rule_id'):
            raise AssertionError(f"{label}: change {change['id']} is missing rule_id.")
        if not change.get('reason_code'):
            raise AssertionError(f"{label}: change {change['id']} is missing reason_code.")
        if not change.get('evidence'):
            raise AssertionError(f"{label}: change {change['id']} is missing evidence.")
        if 'candidate_score' not in change:
            raise AssertionError(f"{label}: change {change['id']} is missing candidate_score.")

    preview_metrics = result.get('preview_metrics') or {}
    if 'invalid_sentence_count' not in preview_metrics:
        raise AssertionError(f"{label}: preview_metrics.invalid_sentence_count missing.")
    if 'semantic_similarity_score' not in preview_metrics:
        raise AssertionError(f"{label}: preview_metrics.semantic_similarity_score missing.")
    if 'selection_summary' not in result:
        raise AssertionError(f"{label}: selection_summary missing from response.")


def run_partial_acceptance_case(simplifier):
    text = "The concept was complex, and the concept remained difficult because the concept used abstract language."
    result = simplifier.simplify_to_grade(text, 6, mode='interactive')
    target_change = next(
        (
            change for change in result['changes']
            if change.get('type') == 'word_replacement' and
            change.get('original', '').strip().lower() == 'concept' and
            change.get('simplified', '').strip().lower() == 'idea'
        ),
        None,
    )
    if target_change is None:
        raise AssertionError("Repeated-word case: expected at least one exact word replacement for 'concept' -> 'idea'.")

    rebuilt = apply_changes_by_span(text, result['changes'], [target_change['id']])
    if rebuilt.count('idea') != 1 or rebuilt.count('concept') != 2:
        raise AssertionError(
            "Repeated-word case: accepting one anchored word patch should only replace one occurrence.\n"
            f"ACTUAL:\n{rebuilt}"
        )


def run_dependency_group_case(simplifier):
    text = (
        "The comprehensive explanation of the process contained multiple clauses, "
        "and it used terminology that younger readers may not know."
    )
    result = simplifier.simplify_to_grade(text, 4, mode='interactive')
    grouped_changes = [change for change in result['changes'] if change.get('dependency_group_id')]
    if not grouped_changes:
        return

    group_id = grouped_changes[0]['dependency_group_id']
    group_ids = [change['id'] for change in result['changes'] if change.get('dependency_group_id') == group_id]
    rebuilt = apply_changes_by_span(text, result['changes'], group_ids)
    if rebuilt == text:
        raise AssertionError("Dependency-group case: accepting a full linked group should change the text.")


def run_mixed_granularity_diff_case(simplifier):
    original = (
        "What we know about the natural world grows through a careful process of forming ideas "
        "about how things work and then testing those ideas against the hard facts gathered from planned study."
    )
    rewritten = (
        "What we know about the natural world grows through a careful way of forming ideas "
        "about how things work. Then, we test those ideas against the hard facts gathered from planned study."
    )
    changes = simplifier._diff_change_block(
        original,
        rewritten,
        target_grade=10,
        going_up=False,
    )

    if not any(
        change.get('type') == 'word_replacement' and
        change.get('original', '').strip().lower() == 'process' and
        change.get('simplified', '').strip().lower() == 'way'
        for change in changes
    ):
        raise AssertionError("Mixed diff case: expected a word-level 'process' -> 'way' replacement.")

    if not any(
        change.get('type') == 'sentence_split' and change.get('review_scope') == 'sentence'
        for change in changes
    ):
        raise AssertionError("Mixed diff case: expected a sentence-level split patch.")

    if any(change.get('review_scope') == 'paragraph' for change in changes):
        raise AssertionError("Mixed diff case: paragraph-level fallback should not be returned.")


def run_grade_12_to_10_case(simplifier):
    text = load_test_text('grade_12.txt')
    interactive = simplifier.simplify_to_grade(text, 10, mode='interactive')
    auto = simplifier.simplify_to_grade(text, 10, mode='auto')

    assert_equal(
        interactive['simplified_text'],
        auto['simplified_text'],
        "grade_12_to_10: auto and interactive previews should stay in sync.",
    )

    preview = interactive.get('preview_metrics') or {}
    target_distance = float(preview.get('target_distance', 999))
    if target_distance > 0.0:
        raise AssertionError(
            f"grade_12_to_10: expected preview to land in the Grade 10 band, got distance {target_distance:.2f}."
        )

    if any(change.get('review_scope') == 'paragraph' for change in interactive['changes']):
        raise AssertionError("grade_12_to_10: expected sentence/word review patches, not paragraph blobs.")

    grouped_ids = [change['id'] for change in interactive['changes'] if change.get('dependency_group_id')]
    if grouped_ids:
        raise AssertionError(
            f"grade_12_to_10: expected independent patches, but found linked group ids on changes {grouped_ids}."
        )


def run_near_hit_candidate_selection_case(simplifier):
    original_score_candidate = simplifier._score_candidate
    try:
        score_map = {
            'clean low candidate 1': {
                'candidate_score': 55.0,
                'raw_score': 7.6,
                'target_distance': 5.4,
                'direction_hit': True,
                'invalid_sentence_count': 0,
                'invalid_sentence_delta': 0,
                'semantic_similarity_score': 0.94,
                'validation_flags': [],
                'paragraph_rewrite_count': 0,
            },
            'clean low candidate 2': {
                'candidate_score': 56.0,
                'raw_score': 7.4,
                'target_distance': 5.6,
                'direction_hit': True,
                'invalid_sentence_count': 0,
                'invalid_sentence_delta': 0,
                'semantic_similarity_score': 0.94,
                'validation_flags': [],
                'paragraph_rewrite_count': 0,
            },
            'clean low candidate 3': {
                'candidate_score': 57.0,
                'raw_score': 7.2,
                'target_distance': 5.8,
                'direction_hit': True,
                'invalid_sentence_count': 0,
                'invalid_sentence_delta': 0,
                'semantic_similarity_score': 0.94,
                'validation_flags': [],
                'paragraph_rewrite_count': 0,
            },
            'near college candidate': {
                'candidate_score': 92.0,
                'raw_score': 12.3,
                'target_distance': 0.7,
                'direction_hit': True,
                'invalid_sentence_count': 3,
                'invalid_sentence_delta': 3,
                'semantic_similarity_score': 0.36,
                'validation_flags': [
                    'new_invalid_sentence_structure',
                    'meaning_drift_risk',
                    'final_paragraph_expanded',
                    'inherited_invalid_sentence_structure',
                ],
                'paragraph_rewrite_count': 1,
            },
        }

        simplifier._score_candidate = (
            lambda original_text, candidate_text, target_grade, mode, source_grade, policy:
            score_map[candidate_text]
        )
        ranked = simplifier._rank_candidates(
            original_text='source',
            candidates=[
                {'text': 'clean low candidate 1', 'rule_history': ['rule.1']},
                {'text': 'clean low candidate 2', 'rule_history': ['rule.2']},
                {'text': 'clean low candidate 3', 'rule_history': ['rule.3']},
                {'text': 'near college candidate', 'rule_history': ['llm.rule_seeded']},
            ],
            target_grade=13,
            mode='auto',
            source_grade=3.1,
            policy={'beam_width': 3},
        )
        if not any(candidate['text'] == 'near college candidate' for candidate in ranked):
            raise AssertionError(
                "Near-hit selection case: a repairable Grade 12 candidate should stay in the beam "
                "instead of being truncated behind clean Grade 7 candidates."
            )

        selected = simplifier._select_preferred_candidate(ranked, target_grade=13)
        if selected['text'] != 'near college candidate':
            raise AssertionError(
                "Near-hit selection case: expected the repairable Grade 12 near-hit to beat "
                "a much lower clean Grade 7 candidate."
            )
    finally:
        simplifier._score_candidate = original_score_candidate


def run_grade_3_to_6_upgrade_case(simplifier):
    text = load_test_text('grade_3.txt')
    original_client = simplifier.llm_validator.client
    simplifier.llm_validator.client = None
    try:
        result = simplifier.simplify_to_grade(
            text,
            6,
            mode='auto',
            prefer_rule_based=True,
        )
    finally:
        simplifier.llm_validator.client = original_client
    metrics = result.get('preview_metrics') or {}
    raw_score = metrics.get('raw_score', 0)
    if not (6.0 <= raw_score < 7.0):
        raise AssertionError(
            f"Grade 3 -> 6 upgrade case: expected Grade 6 preview, got raw {raw_score}."
        )

    rewritten = result.get('simplified_text', '')
    blocked_fragments = [
        'their building',
        'reviewed a new book',
        'subsequently',
        'supplied Max some food',
    ]
    for fragment in blocked_fragments:
        if fragment in rewritten:
            raise AssertionError(
                f"Grade 3 -> 6 upgrade case: found awkward low-mid upgrade fragment {fragment!r}."
            )

    expected_fragments = [
        'enjoyed running and playing throughout the entire day',
        'usually visited the large park located near their home',
        'provided Max with food',
    ]
    for fragment in expected_fragments:
        if fragment not in rewritten:
            raise AssertionError(
                f"Grade 3 -> 6 upgrade case: missing expected phrase-level upgrade {fragment!r}."
            )


def run_llm_meta_commentary_strip_case(simplifier):
    text = (
        "Tom had a small brown dog named Max.\n\n"
        "Note: I removed extra sentences that were not present in the original text."
    )
    stripped = simplifier._strip_llm_meta_commentary(text)
    expected = "Tom had a small brown dog named Max."
    if stripped != expected:
        raise AssertionError(
            "LLM meta-commentary strip case: trailing Note text should not be delivered "
            f"as rewritten content. Got: {stripped!r}"
        )


def run_final_review_reflection_case(simplifier):
    text = load_test_text('grade_12.txt')
    original_client = simplifier.llm_validator.client
    original_validate = simplifier.llm_validator.validate_changes
    original_critic = simplifier.llm_validator.critic_candidates
    original_polish = simplifier.llm_validator.polish_text
    original_local_repair = simplifier.llm_validator.local_repair

    try:
        simplifier.llm_validator.client = object()
        simplifier.llm_validator.validate_changes = (
            lambda original_text, simplified_text, changes: {
                'valid': True,
                'issues': ["Keep the meaning exact."],
                'suggestions': [],
            }
        )
        simplifier.llm_validator.critic_candidates = (
            lambda original_text, target_grade, candidates: {
                'preferred_index': 0,
                'reviews': [],
            }
        )
        simplifier.llm_validator.polish_text = (
            lambda original_text, rewritten_text, target_grade, issues=None, going_up=False:
            rewritten_text.replace('planned study', 'planned research', 1)
        )
        simplifier.llm_validator.local_repair = (
            lambda original_text, candidate_text, target_grade, issues: candidate_text
        )

        result = simplifier.simplify_to_grade(text, 10, mode='interactive')
        if 'planned research' not in result['simplified_text']:
            raise AssertionError("Final review case: expected repaired wording to appear in the preview text.")

        reviewed_changes = [change for change in result['changes'] if change.get('final_reviewed')]
        if not reviewed_changes:
            raise AssertionError("Final review case: expected at least one anchored change to be marked as final-reviewed.")

        if not any('meaning check' in (change.get('reason') or '').lower() for change in reviewed_changes):
            raise AssertionError("Final review case: expected reviewed changes to get the final meaning-check reason.")
    finally:
        simplifier.llm_validator.client = original_client
        simplifier.llm_validator.validate_changes = original_validate
        simplifier.llm_validator.critic_candidates = original_critic
        simplifier.llm_validator.polish_text = original_polish
        simplifier.llm_validator.local_repair = original_local_repair


def run_water_cycle_grade_3_case(simplifier):
    text = (
        "Water moves through nature in a pattern called the water cycle. "
        "The sun heats lakes and oceans until some of the water turns into vapor. "
        "This vapor rises into the sky and forms clouds high above. "
        "When the clouds hold enough water it falls back down as rain or snow.\n\n"
        "Rain water flows into streams and rivers that carry it to the ocean. "
        "Some water soaks into the ground between rocks and layers of soil. "
        "Plants use this water through their roots to grow and stay healthy. "
        "Animals also drink from streams and ponds along the way.\n\n"
        "People need the water cycle to keep working for clean drinking water. "
        "Farmers depend on regular rainfall to keep their crops growing each year. "
        "Towns build holding ponds to collect and store water for their residents. "
        "Without enough rain the crops can fail and people may run short.\n\n"
        "Scientists study the water cycle to predict when storms or dry spells might come. "
        "They look at how dry spells affect different parts of the country. "
        "This research helps communities plan ahead and save water when it is needed."
    )
    result = simplifier.simplify_to_grade(text, 3, mode='interactive')
    simplified_text = result['simplified_text']
    preview_metrics = result.get('preview_metrics') or {}

    banned_fragments = [
        "The sun turns into vapor.",
        "People need the water cycle to keep.",
        "People work for clean drinking water.",
        "people may. The crops",
        "fail. people",
        "storms. dry spells",
        "This study plans ahead.",
        "This study saves water when it is needed.",
    ]
    for fragment in banned_fragments:
        if fragment in simplified_text:
            raise AssertionError(
                "Water-cycle case: simplification still produced a broken semantic fragment.\n"
                f"Fragment: {fragment}\n\n"
                f"ACTUAL:\n{simplified_text}"
            )

    if int(preview_metrics.get('invalid_sentence_count', 0)) != 0:
        raise AssertionError(
            "Water-cycle case: expected zero invalid sentences in preview metrics.\n"
            f"ACTUAL METRICS:\n{preview_metrics}"
        )

    if any(change.get('review_scope') == 'paragraph' for change in result['changes']):
        raise AssertionError(
            "Water-cycle case: expected word/sentence review patches, not paragraph-sized fallback patches.\n"
            f"ACTUAL CHANGES:\n{result['changes']}"
        )


def main() -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        model = ReadabilityModel()
        model.load_models()

        simplifier = TextSimplifier(readability_model=model)
        simplifier.llm_validator.client = None
        simplifier.llm_client = None
        simplifier.datamuse_finder.get_simpler_synonym = lambda _word: None

        run_case(simplifier, 'grade_12_to_6', load_test_text('grade_12.txt'), 6)
        run_case(simplifier, 'grade_5_to_6', load_test_text('grade_5.txt'), 6)
        run_case(simplifier, 'grade_8_to_4', load_test_text('grade_8.txt'), 4)
        run_partial_acceptance_case(simplifier)
        run_dependency_group_case(simplifier)
        run_mixed_granularity_diff_case(simplifier)
        run_grade_12_to_10_case(simplifier)
        run_near_hit_candidate_selection_case(simplifier)
        run_grade_3_to_6_upgrade_case(simplifier)
        run_llm_meta_commentary_strip_case(simplifier)
        run_final_review_reflection_case(simplifier)
        run_water_cycle_grade_3_case(simplifier)

    print("Simplification preview/apply consistency checks passed.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
