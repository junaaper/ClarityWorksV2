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


def run_single_call_multi_variant_case(simplifier):
    class FakeMessage:
        def __init__(self, content):
            self.content = content

    class FakeChoice:
        def __init__(self, content):
            self.message = FakeMessage(content)

    class FakeResponse:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]

    original_chat = simplifier._llm_chat
    original_client = simplifier.llm_client
    calls = []
    payload = """
    {
      "variants": [
        {"name": "conservative", "text": "Tom had a small brown dog named Max, and they visited the nearby park each morning."},
        {"name": "targeted", "text": "Tom owned a small brown dog named Max, and together they routinely visited the nearby park each morning."},
        {"name": "aggressive", "text": "Tom maintained a daily routine with Max, his small brown dog, by visiting the nearby park each morning."}
      ]
    }
    """

    try:
        simplifier.llm_client = object()
        simplifier._llm_call_budget = 1
        simplifier._llm_calls_made = 0

        def fake_chat(*args, **kwargs):
            simplifier._llm_calls_made += 1
            calls.append((args, kwargs))
            return FakeResponse(payload)

        simplifier._llm_chat = fake_chat
        policy = {
            'beam_width': 3,
            'syllable_weight': 1.0,
            'wps_weight': 1.0,
            'paragraph_penalty': 0.0,
        }
        candidates = simplifier._generate_llm_candidates(
            original_text="Tom had a small brown dog named Max. They went to the park each morning.",
            target_grade=13,
            source_grade=3.2,
            going_up=True,
            mode='auto',
            policy=policy,
            rule_selection={'text': "Tom had a small brown dog named Max. They visited the nearby park each morning."},
        )
    finally:
        simplifier._llm_chat = original_chat
        simplifier.llm_client = original_client
        simplifier._llm_call_budget = None
        simplifier._llm_calls_made = 0

    if len(calls) != 1:
        raise AssertionError(f"Multi-variant case: expected one Fireworks call, got {len(calls)}.")
    if len(candidates) < 3:
        raise AssertionError(f"Multi-variant case: expected three parsed candidates, got {len(candidates)}.")
    if not all('single_call' in ' '.join(candidate.get('rule_history', [])) for candidate in candidates):
        raise AssertionError("Multi-variant case: candidates should be marked as single-call LLM outputs.")


def run_paid_tier_cascade_case(simplifier):
    class FakeMessage:
        def __init__(self, content):
            self.content = content

    class FakeChoice:
        def __init__(self, content):
            self.message = FakeMessage(content)

    class FakeResponse:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]

    original_chat = simplifier._llm_chat
    original_client = simplifier.llm_client
    original_score = simplifier._score_candidate
    calls = []
    first_payload = """
    {"variants":[
      {"name":"conservative","text":"low college attempt"},
      {"name":"targeted","text":"medium college attempt"},
      {"name":"aggressive","text":"aggressive college attempt"}
    ]}
    """
    responses = [
        first_payload,
        "corrected college attempt",
        "repaired college attempt",
    ]
    score_map = {
        'low college attempt': {
            'candidate_score': 50.0,
            'raw_score': 9.4,
            'target_distance': 3.6,
            'direction_hit': True,
            'invalid_sentence_count': 0,
            'invalid_sentence_delta': 0,
            'semantic_similarity_score': 0.95,
            'validation_flags': [],
            'paragraph_rewrite_count': 0,
        },
        'medium college attempt': {
            'candidate_score': 45.0,
            'raw_score': 10.4,
            'target_distance': 2.6,
            'direction_hit': True,
            'invalid_sentence_count': 0,
            'invalid_sentence_delta': 0,
            'semantic_similarity_score': 0.95,
            'validation_flags': [],
            'paragraph_rewrite_count': 0,
        },
        'aggressive college attempt': {
            'candidate_score': 40.0,
            'raw_score': 10.8,
            'target_distance': 2.2,
            'direction_hit': True,
            'invalid_sentence_count': 0,
            'invalid_sentence_delta': 0,
            'semantic_similarity_score': 0.93,
            'validation_flags': [],
            'paragraph_rewrite_count': 0,
        },
        'corrected college attempt': {
            'candidate_score': 25.0,
            'raw_score': 12.4,
            'target_distance': 0.6,
            'direction_hit': True,
            'invalid_sentence_count': 0,
            'invalid_sentence_delta': 0,
            'semantic_similarity_score': 0.92,
            'validation_flags': [],
            'paragraph_rewrite_count': 0,
        },
        'repaired college attempt': {
            'candidate_score': 10.0,
            'raw_score': 13.1,
            'target_distance': 0.0,
            'direction_hit': True,
            'invalid_sentence_count': 0,
            'invalid_sentence_delta': 0,
            'semantic_similarity_score': 0.91,
            'validation_flags': [],
            'paragraph_rewrite_count': 0,
        },
    }

    try:
        simplifier.llm_client = object()
        simplifier._llm_call_budget = 3
        simplifier._llm_calls_made = 0

        def fake_chat(*args, **kwargs):
            simplifier._llm_calls_made += 1
            calls.append((args, kwargs))
            return FakeResponse(responses[len(calls) - 1])

        simplifier._llm_chat = fake_chat
        simplifier._score_candidate = (
            lambda original_text, candidate_text, target_grade, mode, source_grade, policy:
            score_map[candidate_text]
        )

        policy = {
            'beam_width': 3,
            'syllable_weight': 1.0,
            'wps_weight': 1.0,
            'paragraph_penalty': 0.0,
        }
        candidates = simplifier._generate_llm_candidates(
            original_text="Tom had a small brown dog named Max. They went to the park each morning.",
            target_grade=13,
            source_grade=3.2,
            going_up=True,
            mode='auto',
            policy=policy,
            rule_selection={'text': "Tom had a small brown dog named Max. They visited the nearby park each morning."},
        )
    finally:
        simplifier._llm_chat = original_chat
        simplifier.llm_client = original_client
        simplifier._score_candidate = original_score
        simplifier._llm_call_budget = None
        simplifier._llm_calls_made = 0

    if len(calls) != 3:
        raise AssertionError(f"Paid-tier cascade case: expected three Fireworks calls for hard College jump, got {len(calls)}.")
    if not any(candidate['text'] == 'corrected college attempt' for candidate in candidates):
        raise AssertionError("Paid-tier cascade case: expected target-correction candidate to be added.")
    if not any(candidate['text'] == 'repaired college attempt' for candidate in candidates):
        raise AssertionError("Paid-tier cascade case: expected safety-cleanup candidate to be added.")


def run_word_artifact_gate_case(simplifier):
    metrics = simplifier._score_candidate(
        original_text="Markets use a broader trading system.",
        candidate_text="Markets use a widerrer trading system.",
        target_grade=7,
        mode='interactive',
        source_grade=10.0,
        policy={'syllable_weight': 1.0, 'wps_weight': 1.0, 'paragraph_penalty': 0.0},
    )
    if not any(flag.startswith('word_artifact:widerrer') for flag in metrics.get('validation_flags', [])):
        raise AssertionError("Word-artifact case: expected 'widerrer' to be blocked as a malformed word.")


def run_awkward_upgrade_phrase_gate_case(simplifier):
    original = (
        "He helps us dig rows in the soft dirt. "
        "Mom makes a fresh salad from the food we grow. "
        "Growing food takes care but the fresh taste makes it all worth the work."
    )
    candidate = (
        "He facilitates us dig rows in the soft dirt. "
        "Mom constructs a fresh salad from the food we expand. "
        "Expanding food takes care but the fresh taste constructs it all worth the work."
    )
    metrics = simplifier._score_candidate(
        original_text=original,
        candidate_text=candidate,
        target_grade=13,
        mode='auto',
        source_grade=4.0,
        policy={'syllable_weight': 1.0, 'wps_weight': 1.0, 'paragraph_penalty': 0.0},
    )
    flags = metrics.get('validation_flags', [])
    expected_prefixes = [
        'awkward_phrase:facilitate_bare_verb',
        'awkward_phrase:construct_food',
        'awkward_phrase:construct_worth',
        'awkward_phrase:expand_food',
    ]
    missing = [prefix for prefix in expected_prefixes if prefix not in flags]
    if missing:
        raise AssertionError(f"Awkward phrase gate case: missing flags {missing}; got {flags}")
    if simplifier._candidate_has_hard_safety_failure(metrics):
        raise AssertionError("Awkward phrase gate case: awkward phrasing should be repairable, not a hard safety block.")


def run_high_target_awkward_near_hit_preferred_case(_simplifier):
    clean_low = {
        'text': 'clean low candidate',
        'candidate_score': 18.0,
        'raw_score': 9.70,
        'target_distance': 3.30,
        'direction_hit': True,
        'invalid_sentence_count': 0,
        'invalid_sentence_delta': 0,
        'semantic_similarity_score': 0.96,
        'paragraph_rewrite_count': 0,
        'validation_flags': [],
    }
    awkward_near_hit = {
        'text': 'awkward near target candidate',
        'candidate_score': 35.0,
        'raw_score': 12.58,
        'target_distance': 0.42,
        'direction_hit': True,
        'invalid_sentence_count': 0,
        'invalid_sentence_delta': 0,
        'semantic_similarity_score': 0.88,
        'paragraph_rewrite_count': 1,
        'validation_flags': [
            'awkward_phrase:facilitate_bare_verb',
            'summary_wrapup:value_of',
        ],
    }

    selected = TextSimplifier._select_preferred_candidate(
        [clean_low, awkward_near_hit],
        target_grade=13,
    )
    if selected is not awkward_near_hit:
        raise AssertionError(
            "High-target near-hit case: expected a repairable Raw 12.58 candidate "
            "to beat a cleaner Raw 9.70 candidate for College."
        )


def run_low_target_near_hit_preferred_case(_simplifier):
    clean_high = {
        'text': 'clean high candidate',
        'candidate_score': 18.0,
        'raw_score': 12.61,
        'target_distance': 8.61,
        'direction_hit': True,
        'invalid_sentence_count': 0,
        'invalid_sentence_delta': 0,
        'semantic_similarity_score': 0.94,
        'paragraph_rewrite_count': 0,
        'validation_flags': [],
    }
    close_low = {
        'text': 'close grade three candidate',
        'candidate_score': 42.0,
        'raw_score': 3.14,
        'target_distance': 0.0,
        'direction_hit': True,
        'invalid_sentence_count': 2,
        'invalid_sentence_delta': 2,
        'semantic_similarity_score': 0.58,
        'paragraph_rewrite_count': 1,
        'validation_flags': ['major_length_compression'],
    }

    selected = TextSimplifier._select_preferred_candidate(
        [clean_high, close_low],
        target_grade=3,
    )
    if selected is not close_low:
        raise AssertionError(
            "Low-target near-hit case: expected a repairable Raw 3.14 candidate "
            "to beat a clean Raw 12.61 candidate for Grade 3."
        )


def run_low_grade_downgrade_prompt_contract_case(simplifier):
    instructions = simplifier._low_grade_downgrade_instructions(
        target_grade=4,
        source_grade=14.4,
    )
    required_fragments = [
        'Grade 4 text for a child',
        'Grade 8-12 is still a failure',
        'Do not use semicolons',
        'It is acceptable to sound simple',
    ]
    missing = [fragment for fragment in required_fragments if fragment not in instructions]
    if missing:
        raise AssertionError(f"Low-grade downgrade prompt contract: missing fragments {missing}")


def run_family_role_protected_term_case(simplifier):
    flags = simplifier._protected_term_flags(
        original_text="Mom makes a fresh salad. Dad helps Max water the garden.",
        candidate_text="My mother prepares a fresh salad. My father helps Max water the garden.",
    )
    if any(flag in {'missing_protected_term:mom', 'missing_protected_term:dad'} for flag in flags):
        raise AssertionError(f"Family-role protected term case: Mom/Dad should be replaceable family roles, got {flags}")
    if any(flag.startswith('missing_protected_term:max') for flag in flags):
        raise AssertionError(f"Family-role protected term case: preserved name Max should not be flagged, got {flags}")


def run_context_blind_upgrade_guard_case(simplifier):
    text = (
        "He helps us dig rows in the soft dirt. "
        "Mom makes a fresh salad from the food we grow. "
        "Growing food makes it all worth the hard work."
    )
    upgraded, _changes = simplifier._complexify_text(text, 13)
    lowered = upgraded.lower()
    blocked_fragments = [
        'assists us dig',
        'aids us dig',
        'supports us dig',
        'produces a fresh salad',
        'generates a fresh salad',
        'constructs a fresh salad',
        'expand fresh food',
        'expanding food',
        'produces it all worth',
        'generates it all worth',
        'constructs it all worth',
    ]
    for fragment in blocked_fragments:
        if fragment in lowered:
            raise AssertionError(
                "Context-blind upgrade guard case: local complexification produced awkward wording.\n"
                f"Fragment: {fragment}\n\nACTUAL:\n{upgraded}"
            )


def run_paragraph_shape_restore_case(simplifier):
    original = (
        "My dad keeps a small garden behind our house. We plant tiny seeds. Then we water each row.\n\n"
        "After two weeks green shoots come up. We pull weeds so plants can grow.\n\n"
        "By summer we pick food from the garden. We share extra food with neighbors.\n\n"
        "Growing food takes care, but the fresh taste is worth the work."
    )
    collapsed = (
        "My father oversees a modest garden behind our house, where we plant tiny seeds. "
        "Then we administer water to each row. After two weeks, green shoots emerge from the soil. "
        "We remove weeds so the plants can continue developing. By summer, we harvest food from the garden. "
        "We share surplus food with neighbors. Growing food requires care, but the fresh taste makes the work worthwhile."
    )
    restored = simplifier._restore_paragraph_shape(original, collapsed)
    if len(simplifier._extract_paragraph_chunks(restored)) != 4:
        raise AssertionError(f"Paragraph restore case: expected 4 paragraphs, got:\n{restored}")
    if restored == collapsed or '\n\n' not in restored:
        raise AssertionError("Paragraph restore case: collapsed rewrite should receive blank lines.")

    result_text, changes, _metrics = simplifier._finalize_preview_candidate(
        original_text=original,
        candidate_text=collapsed,
        target_grade=13,
        going_up=True,
    )
    if len(simplifier._extract_paragraph_chunks(result_text)) != 4:
        raise AssertionError("Paragraph restore case: final preview should preserve original paragraph count.")
    rebuilt = apply_changes_by_span(original, changes, [change['id'] for change in changes])
    assert_equal(
        rebuilt,
        result_text,
        "Paragraph restore case: accepted patches should rebuild the paragraph-restored preview.",
    )


def run_auto_interactive_parity_with_greedy_case(simplifier):
    original_select = simplifier._select_authoring_candidate
    original_greedy = simplifier._greedy_select_changes_for_target
    calls = {'count': 0}
    source = "Tom ran to the park. Max barked at the gate."
    candidate = "Tom ran to the park while Max barked at the gate."

    try:
        simplifier._select_authoring_candidate = (
            lambda text, target_grade, mode, prefer_rule_based=False: {
                'text': candidate,
                'score': 1.0,
                'going_up': True,
                'selection_summary': {
                    'policy_bucket': 'test',
                    'beam_width': 1,
                    'source_grade': 3.0,
                    'target_grade': target_grade,
                    'direction_hit': True,
                    'top_candidates': [],
                },
                'top_candidates': [],
            }
        )

        def fake_greedy(original_text, changes, target_grade, going_up):
            calls['count'] += 1
            rebuilt = apply_changes_by_span(original_text, changes, [change['id'] for change in changes])
            metrics = simplifier._measure_preview_metrics(rebuilt)
            metrics['target_distance'] = 0.0
            return changes, rebuilt, metrics

        simplifier._greedy_select_changes_for_target = fake_greedy
        interactive = simplifier.simplify_to_grade(source, 13, mode='interactive')
        auto = simplifier.simplify_to_grade(source, 13, mode='auto')
    finally:
        simplifier._select_authoring_candidate = original_select
        simplifier._greedy_select_changes_for_target = original_greedy

    if calls['count'] != 2:
        raise AssertionError("Auto/interactive parity case: target repair should run for both modes.")
    assert_equal(
        interactive['simplified_text'],
        auto['simplified_text'],
        "Auto/interactive parity case: all-accepted interactive preview must equal auto preview.",
    )


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


def run_paragraph_exact_group_case(simplifier):
    text = (
        "Tiny first paragraph.\n\n"
        "A very short second paragraph.\n\n"
        "This third paragraph is intentionally longer, but it must still remain its own rewrite unit."
    )
    groups = simplifier._split_into_rewrite_groups(text)
    if len(groups) != 3:
        raise AssertionError(f"Expected exactly three paragraph groups, got {groups!r}")
    for index, group in enumerate(groups):
        if group.get('paragraph_index') != index or group.get('group_indices') != [index]:
            raise AssertionError(f"Paragraph group {index} lost exact paragraph identity: {group!r}")


def run_route_gap_beats_paragraph_count_case(simplifier):
    text = (
        "Video games have grown into a major form of entertainment with goals, stories, and repeated challenges.\n\n"
        "Players make choices, solve problems, and react to events while the game world changes around them.\n\n"
        "Games can also support learning because they ask players to plan, communicate, and pay attention.\n\n"
        "They should still be balanced with sleep, exercise, school work, and time with other people."
    )
    route_grade_9 = simplifier._classify_rewrite_route(text, 8.8, 9)
    route_grade_10 = simplifier._classify_rewrite_route(text, 8.8, 10)
    route_raw_8_to_10 = simplifier._classify_rewrite_route(text, 8.0, 10)
    if route_grade_9 != 'small_shift_fast':
        raise AssertionError(f"Grade 8.8 -> 9 should stay small_shift_fast, got {route_grade_9}")
    if route_grade_10 != 'small_shift_fast':
        raise AssertionError(f"Grade 8.8 -> 10 should stay small_shift_fast, got {route_grade_10}")
    if route_raw_8_to_10 != 'medium_shift_controlled':
        raise AssertionError(f"Raw 8.0 -> 10 should stay medium_shift_controlled, got {route_raw_8_to_10}")


def run_paragraph_prompt_metric_contract_case(simplifier):
    text = (
        "Video games can support learning because players solve problems, make plans, "
        "and work with other players during difficult challenges."
    )
    prompt = simplifier._build_paragraph_prompt(
        text,
        target_grade=10,
        going_up=True,
        glossary={},
        para_index=0,
        total_paras=1,
    )
    required_fragments = [
        "LOCAL READABILITY CONTRACT:",
        "Current paragraph: raw grade",
        "Target paragraph band: Grade 10 raw [10.0, 11.0)",
        "Required movement:",
        "grade = -21.16 + 14.33*(avg syllables/word) + 0.60*(avg words/sentence)",
        "Do not overshoot this",
    ]
    for fragment in required_fragments:
        if fragment not in prompt:
            raise AssertionError(f"Paragraph prompt is missing metric contract fragment: {fragment}")


def run_no_whole_doc_fallback_after_paragraph_failure_case(simplifier):
    text = (
        "Paragraph one has enough information to count as a document paragraph for this routing test.\n\n"
        "Paragraph two stays separate and should not be merged with paragraph one.\n\n"
        "Paragraph three forces the large paragraph route without allowing whole document LLM fallback."
    )
    original_llm_client = simplifier.llm_client
    original_paragraph_pipeline = simplifier._paragraph_pipeline
    original_select = simplifier._select_authoring_candidate
    captured = {}

    try:
        simplifier.llm_client = object()
        simplifier._paragraph_pipeline = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("forced paragraph failure"))

        def fake_select(*args, **kwargs):
            captured['prefer_rule_based'] = kwargs.get('prefer_rule_based')
            captured['called'] = True
            source_grade, _, _ = simplifier._measure_text_metrics(text)
            return {
                'text': text,
                'score': 0.0,
                'going_up': 7 > source_grade,
                'selection_summary': {
                    'generation_mode': 'rule_primary',
                    'source_grade': source_grade,
                    'target_grade': 7,
                    'selected_score': 0.0,
                    'selected_path': ['test.rule'],
                    'direction_hit': True,
                    'target_distance': 0.0,
                    'invalid_sentence_count': 0,
                    'semantic_similarity_score': 1.0,
                    'top_candidates': [],
                },
                'top_candidates': [],
            }

        simplifier._select_authoring_candidate = fake_select
        result = simplifier.simplify_to_grade(text, 7, mode='auto')
        if not captured.get('called') or captured.get('prefer_rule_based') is not True:
            raise AssertionError("Paragraph failure should fall back only to rule-primary selection.")
        summary = result.get('selection_summary') or {}
        if summary.get('generation_mode') != 'rule_primary_after_paragraph_pipeline_failure':
            raise AssertionError(f"Expected rule fallback summary, got {summary}")
    finally:
        simplifier.llm_client = original_llm_client
        simplifier._paragraph_pipeline = original_paragraph_pipeline
        simplifier._select_authoring_candidate = original_select


def run_small_shift_polish_fragment_case(simplifier):
    original_client = simplifier.llm_client
    original_polish = simplifier._minimal_llm_grammar_polish
    try:
        simplifier.llm_client = object()
        original = "Max then went to the store."
        candidate = "Max then went. To the store."
        metrics = simplifier._measure_candidate_preview_metrics(original, candidate, 4)
        sanity = simplifier._run_local_sanity_check(original, candidate, 4, final_metrics=metrics)
        simplifier._minimal_llm_grammar_polish = (
            lambda **_kwargs: "Max then went to the store."
        )
        polished, _changes, polished_metrics, polished_sanity, summary = simplifier._maybe_apply_route_polish(
            original_text=original,
            current_text=candidate,
            target_grade=4,
            going_up=False,
            rewrite_route='small_shift_fast',
            changes=[],
            final_metrics=metrics,
            sanity=sanity,
        )
        if summary.get('route_polish_applied') is not True:
            raise AssertionError(f"Expected small-shift polish to apply, got {summary}")
        if polished != original:
            raise AssertionError(f"Expected fragment to be repaired, got {polished!r}")
        if polished_metrics['target_distance'] > metrics['target_distance'] + 0.05:
            raise AssertionError("Small-shift polish should not damage target accuracy.")
        if polished_sanity.get('severe_flags'):
            raise AssertionError(f"Polish should clear severe sanity flags, got {polished_sanity}")
    finally:
        simplifier.llm_client = original_client
        simplifier._minimal_llm_grammar_polish = original_polish


def run_max_grade7_no_utilized_case(simplifier):
    text = (
        "Tom had a small brown dog named Max who liked to run and play all day. "
        "Every day after lunch Tom and Max would go to the big park near their house. "
        "Tom threw a red ball far across the green grass for Max to fetch. "
        "Max would run as fast as he could to bring the ball back to Tom.\n\n"
        "One warm day they took a long walk down to the old pond near the farm. "
        "They saw some fat ducks on the clear blue water by the tall grass. "
        "Max barked at the ducks but they did not seem to care at all about him. "
        "Tom held Max back so he would not jump in the cold water after them.\n\n"
        "After their walk they went home and Tom gave Max some food and cool water. "
        "Max ate all of his food and then lay down on his soft warm bed to rest. "
        "That night Tom sat next to Max and read a new book about ships and the deep blue sea. "
        "Max slept on the rug near his feet while the fire kept them warm."
    )
    result = simplifier.simplify_to_grade(text, 7, mode='auto')
    lowered = result['simplified_text'].lower()
    if 'utilized a small brown dog' in lowered or 'utilized' in lowered:
        raise AssertionError(f"Grade 7 Max rewrite should avoid stiff utilize wording:\n{result['simplified_text']}")


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
        summary = result.get('selection_summary') or {}
        if summary.get('final_review_applied'):
            raise AssertionError("Fast rewrite routes should skip the multi-round final LLM review stack.")
        if 'planned research' in result['simplified_text']:
            raise AssertionError("Final review polish should not run during fast route delivery.")
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
        run_single_call_multi_variant_case(simplifier)
        run_paid_tier_cascade_case(simplifier)
        run_word_artifact_gate_case(simplifier)
        run_awkward_upgrade_phrase_gate_case(simplifier)
        run_high_target_awkward_near_hit_preferred_case(simplifier)
        run_low_target_near_hit_preferred_case(simplifier)
        run_low_grade_downgrade_prompt_contract_case(simplifier)
        run_family_role_protected_term_case(simplifier)
        run_context_blind_upgrade_guard_case(simplifier)
        run_paragraph_shape_restore_case(simplifier)
        run_auto_interactive_parity_with_greedy_case(simplifier)
        run_grade_3_to_6_upgrade_case(simplifier)
        run_llm_meta_commentary_strip_case(simplifier)
        run_paragraph_exact_group_case(simplifier)
        run_route_gap_beats_paragraph_count_case(simplifier)
        run_paragraph_prompt_metric_contract_case(simplifier)
        run_no_whole_doc_fallback_after_paragraph_failure_case(simplifier)
        run_small_shift_polish_fragment_case(simplifier)
        run_max_grade7_no_utilized_case(simplifier)
        run_final_review_reflection_case(simplifier)
        run_water_cycle_grade_3_case(simplifier)

    print("Simplification preview/apply consistency checks passed.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
