import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / 'ml-service'
sys.path.insert(0, str(ROOT))

from models.simplifier import TextSimplifier
from utils.change_patches import apply_changes_by_span


MOTIVATION_SOURCE = (
    "After this initial exposure, I decided to pursue a Bachelor's degree in Software Engineering at "
    "COMSATS University Islamabad, Wah Campus. Throughout my studies, I developed a strong foundation "
    "in data structures and algorithms, machine learning, software design and architecture, and data science. "
    "Academically, I have maintained a CGPA of 3.92/4.00, which reflects both my commitment to the field "
    "and my ability to engage rigorously with technically demanding coursework."
)

GRADE5_CANDIDATE = (
    "After this first experience, I chose to study Software Engineering at COMSATS University Islamabad, "
    "Wah Campus. I learned data structures and algorithms. I also learned machine learning, software design, "
    "architecture, and data science. I kept a CGPA of 3.92/4.00. This shows that I work hard and can handle "
    "difficult schoolwork."
)

UNDER_TARGET_SOURCE = (
    "After an intensive academic experience, Max decided to study AI at Utrecht University while maintaining "
    "GPA 3.92 and completing demanding coding and mathematics coursework."
)

UNDER_TARGET_CANDIDATE = (
    "Max wanted to study AI. Max joined Utrecht University. Max kept GPA 3.92. Max worked hard. Max liked code."
)

UTRECHT_MOTIVATION_SOURCE = """Name: Junaid Ahsan Malik
Utrecht University student number: 7077424
Master's programme: Artificial Intelligence

Letter of Motivation
The first time I was introduced to the world of programming and computer science was when a good friend of mine mentioned how his brother had launched a company named Mind Rockets, that won an award for their work on a virtual website sign language interpreter for the deaf. Coming from a medical oriented family, this blew my mind. Until that moment, I had thought that the only way to do meaningful, impactful work was in the field of medicine; but being able to make something on a computer that could affect the lives of millions around the world, easing life for the impaired, moved me. Soon after this chance encounter, I went through the CS50x course by Harvard, and it was there I fell in love with computer science and everything this field has to offer.

After this initial exposure, I decided to pursue a Bachelor's degree in Software Engineering at COMSATS University Islamabad, Wah Campus. Throughout my studies, I developed a strong foundation in data structures and algorithms, machine learning, software design and architecture, and data science. Academically, I have maintained a CGPA of 3.92/4.00, which reflects both my commitment to the field and my ability to engage rigorously with technically demanding coursework."""

UTRECHT_GRADE6_RESCUE = """Name: Junaid Ahsan Malik
Utrecht University student number: 7077424
Master's programme: Artificial Intelligence

Letter of Motivation
A good friend first showed me what programming could do. His brother's company was Mind Rockets. It made a sign language interpreter for deaf and impaired people. The interpreter won an award. My family mostly knew medicine. This surprised me. I thought medicine was the main way to help people. Then I saw that code could help too. A computer program could touch many lives around the world. Soon after, I took Harvard's CS50x course. It made me love computer science.

After this first experience, I chose a Bachelor's degree in Software Engineering at COMSATS University Islamabad, Wah Campus. I learned data structures and algorithms. I learned machine learning and software design. I also learned architecture and data science. My CGPA was 3.92/4.00. This shows I work hard. It also shows I can handle demanding coursework."""

UTRECHT_FULL_MOTIVATION_SOURCE = """Name: Junaid Ahsan Malik
Utrecht University student number: 7077424
Master's programme: Artificial Intelligence

Letter of Motivation
The first time I was introduced to the world of programming and computer science was when a good friend of mine mentioned how his brother had launched a company named Mind Rockets, that won an award for their work on a virtual website sign language interpreter for the deaf. Coming from a medical oriented family, this blew my mind. Until that moment, I had thought that the only way to do meaningful, impactful work was in the field of medicine; but being able to make something on a computer that could affect the lives of millions around the world, easing life for the impaired, moved me. Soon after this chance encounter, I went through the CS50x course by Harvard, and it was there I fell in love with computer science and everything this field has to offer.

After this initial exposure, I decided to pursue a Bachelor's degree in Software Engineering at COMSATS University Islamabad, Wah Campus. Throughout my studies, I developed a strong foundation in data structures and algorithms, machine learning, software design and architecture, and data science. Academically, I have maintained a CGPA of 3.92/4.00, which reflects both my commitment to the field and my ability to engage rigorously with technically demanding coursework.

As my studies progressed, I found myself increasingly drawn to artificial intelligence, not merely as a subfield of computer science, but as a discipline with the power to reshape how we understand and interact with the world. I have worked on projects ranging from NLP-based text readability analysis using retrieval-augmented generation, to multi-agent research orchestration systems built with LangGraph and large language models. These experiences gave me hands-on exposure to the full pipeline of applied AI development, from data preprocessing and model selection to system integration and evaluation. They also made clear to me that I want to go deeper; to understand not just how to apply AI tools, but how to reason about them formally, design them responsibly, and fully understand the underlying workings.

Within AI, I am most drawn to the areas of machine learning theory, natural language processing, and intelligent agent systems. I am also deeply interested in the ethical and societal dimensions of AI, particularly how intelligent systems can be built to be fair, transparent, and accountable. I find the question of how machines can acquire, represent, and reason about knowledge genuinely compelling, and I want to explore these topics at a level of depth and rigor that I feel is possible at Utrecht University.

Utrecht University's Master's in Artificial Intelligence stands out for its combination of research rigour and genuine intellectual breadth. The compulsory grounding in Philosophy of AI and research methods signals that Utrecht trains practitioners who can think critically about what they build, not just how to build it. Within the elective offerings, I am particularly drawn to Natural Language Processing, Explainable AI, and Multi-Agent Systems, all of which connect directly to my existing work and the directions I want to pursue further. The research component, with the option to carry out thesis work at an external company or abroad, tells me that Utrecht prepares graduates for meaningful real-world contributions, which aligns directly with my own ambitions.

In terms of the qualities this programme requires, I believe my background demonstrates both the technical preparation and the intellectual curiosity necessary to succeed. My working with AI systems as well as my academic ability demonstrate the adaptability and problem-solving mindset that graduate-level AI research demands. I am comfortable working with ambiguity, iterating on ideas, and collaborating with people from diverse backgrounds.

Beyond academics, I served as President of the COMSATS Literary Society for almost three semesters, where I organized multiple university-level events, mentored students, and built a community from the ground up. This experience strengthened my leadership, communication, and organizational skills, and taught me how to work effectively with people from a wide range of disciplines and interests.

My long-term ambition is to contribute to AI research and development in ways that are both technically meaningful and socially responsible. Whether that takes the form of academic research, or building systems that address real human needs, I want my work to matter. Utrecht's Master's in AI, with its strong research culture and rigorous academic foundation, is the environment where I believe I can best develop into the kind of AI practitioner and thinker I aspire to be."""


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class ContractRescueSimplifier(TextSimplifier):
    def __init__(self, rescue_text):
        super().__init__()
        self.llm_client = object()
        self.rescue_text = rescue_text
        self.last_prompt = ""

    def _llm_chat(self, messages, temperature=0, max_tokens=4000, max_retries=3):
        if self._llm_call_budget is not None and self._llm_calls_made >= self._llm_call_budget:
            return None
        self._llm_calls_made += 1
        self.last_prompt = messages[-1]["content"]
        return FakeResponse(
            '{"variants":[{"name":"contract_target","text":' +
            json_escape(self.rescue_text) +
            '}]}'
        )


class TextResponseSimplifier(ContractRescueSimplifier):
    def _llm_chat(self, messages, temperature=0, max_tokens=4000, max_retries=3):
        if self._llm_call_budget is not None and self._llm_calls_made >= self._llm_call_budget:
            return None
        self._llm_calls_made += 1
        self.last_prompt = messages[-1]["content"]
        return FakeResponse(self.rescue_text)


def json_escape(text):
    import json

    return json.dumps(text)


def candidate(raw, distance, similarity, flags=None, path=None, score=10.0):
    return {
        "text": GRADE5_CANDIDATE if raw < 8 else MOTIVATION_SOURCE,
        "candidate_score": score,
        "raw_score": raw,
        "target_distance": distance,
        "direction_hit": True,
        "invalid_sentence_count": 0,
        "invalid_sentence_delta": 0,
        "semantic_similarity_score": similarity,
        "avg_syllables_per_word": 1.3,
        "avg_words_per_sentence": 12.0,
        "validation_flags": flags or [],
        "paragraph_rewrite_count": 1,
        "rule_history": path or [],
    }


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_low_grade_rescue_prefers_target_candidate_over_grade12_fallback():
    rule_fallback = candidate(
        raw=12.2,
        distance=6.2,
        similarity=0.93,
        path=["selection.legacy_iterative"],
        score=18.0,
    )
    target_llm = candidate(
        raw=5.88,
        distance=0.0,
        similarity=0.22,
        flags=["meaning_drift_risk"],
        path=["llm.author", "llm.target_correction", "llm.safety_cleanup"],
        score=12.0,
    )

    selected = TextSimplifier._select_preferred_candidate(
        [rule_fallback, target_llm],
        target_grade=5,
    )

    assert_true(selected is target_llm, "Expected the safe Grade 5 LLM candidate to beat Grade 12 fallback.")
    assert_true(selected["raw_score"] <= 6.5, f"Expected near Grade 5 raw score, got {selected['raw_score']}")


def test_low_grade_rescue_still_rejects_missing_protected_terms():
    rule_fallback = candidate(raw=12.2, distance=6.2, similarity=0.93, score=18.0)
    unsafe_llm = candidate(
        raw=5.1,
        distance=0.0,
        similarity=0.24,
        flags=["meaning_drift_risk", "missing_protected_term:comsats"],
        path=["llm.target_correction"],
        score=8.0,
    )

    selected = TextSimplifier._select_preferred_candidate(
        [rule_fallback, unsafe_llm],
        target_grade=5,
    )

    assert_true(selected is rule_fallback, "Missing protected terms must still block low-grade rescue.")


def test_but_substitution_is_not_a_hard_blocker():
    target_candidate = candidate(
        raw=6.4,
        distance=0.0,
        similarity=0.5,
        flags=["blocked_substitution:but"],
        path=["llm.target_correction"],
        score=8.0,
    )

    assert_true(
        TextSimplifier._candidate_blocking_flags(target_candidate) == [],
        "'but' should not hard-block a near-target simplification candidate.",
    )


def test_soft_missing_protected_terms_are_diagnostic_only():
    target_candidate = candidate(
        raw=6.4,
        distance=0.0,
        similarity=0.5,
        flags=["missing_soft_protected_term:impaired"],
        path=["llm.target_correction"],
        score=8.0,
    )

    assert_true(
        TextSimplifier._candidate_blocking_flags(target_candidate) == [],
        "Soft protected terms should not be hard blockers.",
    )
    assert_true(
        not TextSimplifier._candidate_has_hard_safety_failure(target_candidate, target_grade=6),
        "Soft protected terms should not force hard safety rejection.",
    )


def test_campus_degree_and_tool_terms_are_soft_for_demo_selection():
    simplifier = TextSimplifier()
    text = (
        "Junaid Ahsan Malik studies Artificial Intelligence at Utrecht University. "
        "He completed a Bachelor's degree at COMSATS University Islamabad, Wah Campus, "
        "used LangGraph, and kept a CGPA of 3.92/4.00."
    )
    candidate_text = (
        "Junaid Ahsan Malik studies Artificial Intelligence at Utrecht University. "
        "He completed a degree at COMSATS University Islamabad, used graph tools, "
        "and kept a CGPA of 3.92/4.00."
    )
    flags = simplifier._protected_term_flags(text, candidate_text)

    assert_true(
        "missing_soft_protected_term:wah_campus" in flags,
        f"Expected Wah Campus to be soft, got {flags}.",
    )
    assert_true(
        "missing_soft_protected_term:langgraph" in flags,
        f"Expected LangGraph to be soft, got {flags}.",
    )
    assert_true(
        not any(flag.startswith("missing_protected_term:wah_campus") for flag in flags),
        f"Wah Campus should not be a hard blocker: {flags}.",
    )
    assert_true(
        not any(flag.startswith("missing_protected_term:langgraph") for flag in flags),
        f"LangGraph should not be a hard blocker: {flags}.",
    )


def test_core_identity_terms_remain_hard_protected():
    simplifier = TextSimplifier()
    text = (
        "Junaid Ahsan Malik studies Artificial Intelligence at Utrecht University. "
        "His student number is 7077424 and his CGPA is 3.92/4.00."
    )
    candidate_text = "He studies AI at a university and has strong grades."
    flags = simplifier._protected_term_flags(text, candidate_text)

    expected_hard = {
        "missing_protected_term:junaid_ahsan_malik",
        "missing_protected_term:utrecht_university",
        "missing_protected_term:7077424",
        "missing_protected_term:3_92_4_00",
    }
    missing = expected_hard.difference(flags)
    assert_true(not missing, f"Expected hard protected flags missing: {missing}; got {flags}.")


def test_target_lock_prefers_near_band_candidate_over_far_clean_fallback():
    rule_fallback = candidate(
        raw=12.5,
        distance=6.5,
        similarity=0.94,
        path=["selection.legacy_iterative"],
        score=9.0,
    )
    near_candidate = candidate(
        raw=4.4,
        distance=0.6,
        similarity=0.44,
        flags=["meaning_drift_risk"],
        path=["llm.undershoot", "target_lock.repair"],
        score=18.0,
    )

    selected = TextSimplifier._select_preferred_candidate(
        [rule_fallback, near_candidate],
        target_grade=5,
    )

    assert_true(selected is near_candidate, "A safe +/-1 band candidate should beat a far-off clean fallback.")


def test_low_grade_undershoot_repair_combines_short_sentences():
    simplifier = TextSimplifier()
    source_grade = 16.0
    target_grade = 5
    policy = simplifier._get_target_policy(target_grade, going_up=False, source_grade=source_grade)
    initial = simplifier._score_candidate(
        original_text=UNDER_TARGET_SOURCE,
        candidate_text=UNDER_TARGET_CANDIDATE,
        target_grade=target_grade,
        mode="auto",
        source_grade=source_grade,
        policy=policy,
    )

    repaired = simplifier._target_lock_repair_candidate(
        original_text=UNDER_TARGET_SOURCE,
        candidate={"text": UNDER_TARGET_CANDIDATE, "rule_history": ["llm.undershoot"]},
        target_grade=target_grade,
        source_grade=source_grade,
        going_up=False,
        mode="auto",
        policy=policy,
    )

    assert_true(repaired is not None, "Expected a repair candidate for the Grade 5 undershoot.")
    final = simplifier._score_candidate(
        original_text=UNDER_TARGET_SOURCE,
        candidate_text=repaired["text"],
        target_grade=target_grade,
        mode="auto",
        source_grade=source_grade,
        policy=policy,
    )

    assert_true(
        final["target_distance"] <= initial["target_distance"],
        f"Expected repair to move closer to Grade 5, got {initial['target_distance']} -> {final['target_distance']}.",
    )
    assert_true(
        final["avg_words_per_sentence"] >= initial["avg_words_per_sentence"],
        "Low-grade undershoot repair should raise WPS by combining short sentences.",
    )
    for protected in ("Max", "Utrecht University", "3.92"):
        assert_true(protected in repaired["text"], f"Expected protected term to remain: {protected}")


def test_exact_broad_patch_accept_all_matches_preview():
    change = {
        "id": 0,
        "start": 0,
        "end": len(MOTIVATION_SOURCE),
        "original_text": MOTIVATION_SOURCE,
        "replacement_text": GRADE5_CANDIDATE,
    }

    rebuilt = apply_changes_by_span(MOTIVATION_SOURCE, [change], [0])
    denied = apply_changes_by_span(MOTIVATION_SOURCE, [change], [])

    assert_true(rebuilt == GRADE5_CANDIDATE, "Accepting the exact broad patch should match preview text.")
    assert_true(denied == MOTIVATION_SOURCE, "Denying the exact broad patch should preserve original text.")


def test_exact_broad_patch_has_meaningful_reason_coverage():
    simplifier = TextSimplifier()
    simplifier._selection_context = {"candidate_score": 1.0}
    change = simplifier._build_exact_rebuild_change(
        MOTIVATION_SOURCE,
        GRADE5_CANDIDATE,
        target_grade=5,
        going_up=False,
    )
    summary = simplifier._reason_coverage_summary([change])

    assert_true(change.get("reason_code"), "Exact broad patch should include a reason code.")
    assert_true(change.get("evidence"), "Exact broad patch should include structured evidence.")
    assert_true(summary["reason_coverage_rate"] >= 1.0, "Expected full reason coverage for exact broad patch.")


def test_target_contract_rescue_scores_utrecht_fixture_for_grade6_and_grade5():
    for target_grade in (6, 5):
        simplifier = ContractRescueSimplifier(UTRECHT_GRADE6_RESCUE)
        simplifier._llm_call_budget = 1
        simplifier._llm_calls_made = 0
        source_grade = simplifier._measure_text_metrics(UTRECHT_MOTIVATION_SOURCE)[0]
        policy = simplifier._get_target_policy(target_grade, going_up=False, source_grade=source_grade)
        far_metrics = simplifier._score_candidate(
            original_text=UTRECHT_MOTIVATION_SOURCE,
            candidate_text=UTRECHT_MOTIVATION_SOURCE,
            target_grade=target_grade,
            mode="auto",
            source_grade=source_grade,
            policy=policy,
        )
        far_candidate = {
            "text": UTRECHT_MOTIVATION_SOURCE,
            "rule_history": ["selection.legacy_iterative"],
            **far_metrics,
        }

        rescues = simplifier._target_contract_rescue_candidates(
            original_text=UTRECHT_MOTIVATION_SOURCE,
            selected_candidate=far_candidate,
            top_candidates=[far_candidate],
            target_grade=target_grade,
            source_grade=source_grade,
            going_up=False,
            mode="auto",
            policy=policy,
        )
        ranked = simplifier._rank_candidates(
            original_text=UTRECHT_MOTIVATION_SOURCE,
            candidates=[far_candidate] + rescues,
            target_grade=target_grade,
            mode="auto",
            source_grade=source_grade,
            policy=policy,
        )
        selected = simplifier._select_preferred_candidate(ranked, target_grade=target_grade)

        assert_true(rescues, f"Expected a target-contract rescue candidate for Grade {target_grade}.")
        assert_true(
            "llm.target_contract_rescue" in selected.get("rule_history", []),
            f"Expected Grade {target_grade} to select the rescue candidate.",
        )
        assert_true(
            simplifier._candidate_display_delta(selected, target_grade) <= 1,
            f"Expected Grade {target_grade} rescue within +/-1 band, got raw {selected['raw_score']}.",
        )
        for protected in ("Junaid Ahsan Malik", "7077424", "Artificial Intelligence", "Mind Rockets", "3.92/4.00"):
            assert_true(protected in selected["text"], f"Expected protected term to remain: {protected}")
        assert_true(
            "Grade 8-12 output is a failure" in simplifier.last_prompt,
            "Expected hard downgrade prompt to call Grade 8-12 output a failure.",
        )


def test_target_contract_rescue_accepts_plain_text_response():
    simplifier = TextResponseSimplifier(UTRECHT_GRADE6_RESCUE)
    simplifier._llm_call_budget = 1
    simplifier._llm_calls_made = 0
    source_grade = simplifier._measure_text_metrics(UTRECHT_MOTIVATION_SOURCE)[0]
    policy = simplifier._get_target_policy(6, going_up=False, source_grade=source_grade)
    far_metrics = simplifier._score_candidate(
        original_text=UTRECHT_MOTIVATION_SOURCE,
        candidate_text=UTRECHT_MOTIVATION_SOURCE,
        target_grade=6,
        mode="auto",
        source_grade=source_grade,
        policy=policy,
    )
    far_candidate = {
        "text": UTRECHT_MOTIVATION_SOURCE,
        "rule_history": ["selection.legacy_iterative"],
        **far_metrics,
    }

    rescues = simplifier._target_contract_rescue_candidates(
        original_text=UTRECHT_MOTIVATION_SOURCE,
        selected_candidate=far_candidate,
        top_candidates=[far_candidate],
        target_grade=6,
        source_grade=source_grade,
        going_up=False,
        mode="auto",
        policy=policy,
    )

    assert_true(rescues, "Plain-text target rescue response should be scored as a candidate.")
    assert_true(
        rescues[0]["rule_history"] == ["llm.target_contract_rescue", "variant.contract_plain"],
        f"Expected plain response to be tagged as contract_plain, got {rescues[0]['rule_history']}.",
    )


def test_contract_label_response_parses_as_variant():
    simplifier = TextSimplifier()
    parsed = simplifier._parse_llm_variant_response(
        "contract_target:\n" + UTRECHT_GRADE6_RESCUE
    )

    assert_true(parsed, "Expected contract_target label to parse.")
    assert_true(parsed[0]["name"].lower() == "contract_target", "Expected contract_target variant name.")


def test_near_target_protected_repair_selects_grade6_over_far_fallback():
    simplifier = TextResponseSimplifier(UTRECHT_GRADE6_RESCUE)
    simplifier._llm_call_budget = 1
    simplifier._llm_calls_made = 0
    source_grade = simplifier._measure_text_metrics(UTRECHT_MOTIVATION_SOURCE)[0]
    policy = simplifier._get_target_policy(6, going_up=False, source_grade=source_grade)
    damaged_text = (
        UTRECHT_GRADE6_RESCUE
        .replace("Wah Campus", "the campus")
        .replace("3.92/4.00", "3.92")
    )
    damaged = {
        "text": damaged_text,
        "candidate_score": 8.0,
        "raw_score": 6.56,
        "target_distance": 0.0,
        "direction_hit": True,
        "invalid_sentence_count": 0,
        "invalid_sentence_delta": 0,
        "semantic_similarity_score": 0.55,
        "avg_syllables_per_word": 1.35,
        "avg_words_per_sentence": 14.0,
        "validation_flags": [
            "missing_protected_term:wah_campus",
            "missing_protected_term:3_92_4_00",
        ],
        "paragraph_rewrite_count": 1,
        "rule_history": ["llm.target_correction"],
    }
    far = candidate(raw=12.55, distance=5.55, similarity=0.95, path=["selection.legacy_iterative"], score=9.0)

    repairs = simplifier._near_target_guardrail_repair_candidates(
        original_text=UTRECHT_MOTIVATION_SOURCE,
        ranked_candidates=[far, damaged],
        target_grade=6,
        source_grade=source_grade,
        going_up=False,
        mode="auto",
        policy=policy,
    )
    ranked = simplifier._rank_candidates(
        original_text=UTRECHT_MOTIVATION_SOURCE,
        candidates=[far, damaged] + repairs,
        target_grade=6,
        mode="auto",
        source_grade=source_grade,
        policy=policy,
    )
    selected = simplifier._select_preferred_candidate(ranked, target_grade=6)

    assert_true(repairs, "Expected a protected-term repair candidate.")
    assert_true(
        "llm.near_target_protected_repair" in selected.get("rule_history", []),
        "Expected protected repair to win over Grade 12 fallback.",
    )
    assert_true(
        simplifier._candidate_display_delta(selected, 6) <= 1,
        f"Expected repaired candidate within +/-1 band, got raw {selected['raw_score']}.",
    )
    for protected in ("Wah Campus", "3.92/4.00"):
        assert_true(protected in selected["text"], f"Expected repaired protected term: {protected}")


def test_soft_protected_misses_do_not_block_grade6_over_far_fallback():
    far = candidate(raw=12.55, distance=5.55, similarity=0.95, path=["selection.legacy_iterative"], score=9.0)
    near = candidate(
        raw=6.8,
        distance=0.0,
        similarity=0.48,
        flags=[
            "missing_soft_protected_term:wah_campus",
            "missing_soft_protected_term:langgraph",
            "meaning_drift_risk",
        ],
        path=["llm.target_contract_rescue"],
        score=12.0,
    )

    selected = TextSimplifier._select_preferred_candidate([far, near], target_grade=6)

    assert_true(selected is near, "Soft protected misses should not force Grade 12 fallback.")


def test_target_contract_call_is_reserved_after_correction():
    simplifier = TextSimplifier()
    simplifier._llm_call_budget = 3
    simplifier._llm_calls_made = 2

    assert_true(
        simplifier._llm_calls_remaining(),
        "Expected one ordinary LLM call to remain.",
    )
    assert_true(
        not simplifier._llm_calls_remaining(reserve=1),
        "Expected cleanup-style calls to preserve one target-contract rescue call.",
    )


def test_defence_target_fallback_for_full_utrecht_letter_hits_grade6():
    simplifier = TextSimplifier()
    fallback = simplifier._build_defence_target_fallback(UTRECHT_FULL_MOTIVATION_SOURCE, target_grade=6)
    raw_score = simplifier._measure_text_metrics(fallback)[0]

    assert_true(
        simplifier._display_grade_number_from_score(raw_score) == 6,
        f"Expected defence fallback to display Grade 6, got raw {raw_score}.",
    )
    for protected in (
        "Junaid Ahsan Malik",
        "7077424",
        "Artificial Intelligence",
        "Mind Rockets",
        "COMSATS University Islamabad",
        "Wah Campus",
        "LangGraph",
        "COMSATS Literary Society",
        "3.92/4.00",
    ):
        assert_true(protected in fallback, f"Expected fallback to preserve context term: {protected}")


def test_full_utrecht_letter_qualifies_for_defence_fallback_when_far_off():
    simplifier = TextSimplifier()
    should_apply = simplifier._should_apply_defence_target_fallback(
        original_text=UTRECHT_FULL_MOTIVATION_SOURCE,
        target_grade=6,
        going_up=False,
        final_metrics={"raw_score": 12.55},
    )

    assert_true(
        should_apply,
        "Expected full Utrecht letter to qualify for defence fallback when delivered grade is far off.",
    )


def test_explanation_items_reject_function_word_replacements():
    simplifier = TextSimplifier()
    items = simplifier._extract_explanation_items(
        "Workers earn money when customers buy goods.",
        "Workers work if customers buy goods and pay them.",
        going_up=False,
        max_items=10,
    )

    bad_pairs = {
        (item.get("before", "").lower(), item.get("after", "").lower())
        for item in items
    }
    assert_true(
        ("earn", "if") not in bad_pairs,
        f"Function-word evidence should be suppressed, got {bad_pairs}.",
    )
    assert_true(
        all(after != "if" for _before, after in bad_pairs),
        f"Connector words should not be presented as vocabulary replacements: {bad_pairs}.",
    )


def test_paragraph_topic_shift_is_a_hard_safety_flag():
    simplifier = TextSimplifier()
    original = (
        "Markets use supply and demand to decide prices. When demand rises and supply stays low, prices rise.\n\n"
        "Governments can shape markets with taxes and public spending. Central banks can adjust lending rates.\n\n"
        "Countries trade with each other across borders. Trade deals can lower barriers and move goods smoothly."
    )
    shifted = (
        "Markets have simple rules. Demand can make prices rise, and supply can make prices fall.\n\n"
        "Countries trade with each other. Trade deals help countries move goods across borders.\n\n"
        "Governments make tax choices. Central banks can change lending rates."
    )

    flags = simplifier._paragraph_topic_drift_flags(original, shifted)
    assert_true(
        any(flag.startswith("paragraph_scope_shift:") for flag in flags),
        f"Expected paragraph topic shift flag, got {flags}.",
    )

    unsafe = candidate(
        raw=6.2,
        distance=0.0,
        similarity=0.65,
        flags=flags,
        path=["llm.target_contract_rescue"],
        score=8.0,
    )
    assert_true(
        TextSimplifier._candidate_has_hard_safety_failure(unsafe, target_grade=6),
        "Paragraph topic shifts should block an otherwise target-band candidate.",
    )


if __name__ == "__main__":
    test_low_grade_rescue_prefers_target_candidate_over_grade12_fallback()
    test_low_grade_rescue_still_rejects_missing_protected_terms()
    test_but_substitution_is_not_a_hard_blocker()
    test_soft_missing_protected_terms_are_diagnostic_only()
    test_campus_degree_and_tool_terms_are_soft_for_demo_selection()
    test_core_identity_terms_remain_hard_protected()
    test_target_lock_prefers_near_band_candidate_over_far_clean_fallback()
    test_low_grade_undershoot_repair_combines_short_sentences()
    test_exact_broad_patch_accept_all_matches_preview()
    test_exact_broad_patch_has_meaningful_reason_coverage()
    test_target_contract_rescue_scores_utrecht_fixture_for_grade6_and_grade5()
    test_target_contract_rescue_accepts_plain_text_response()
    test_contract_label_response_parses_as_variant()
    test_near_target_protected_repair_selects_grade6_over_far_fallback()
    test_soft_protected_misses_do_not_block_grade6_over_far_fallback()
    test_target_contract_call_is_reserved_after_correction()
    test_defence_target_fallback_for_full_utrecht_letter_hits_grade6()
    test_full_utrecht_letter_qualifies_for_defence_fallback_when_far_off()
    test_explanation_items_reject_function_word_replacements()
    test_paragraph_topic_shift_is_a_hard_safety_flag()
    print("Hard downgrade selection checks passed.")
