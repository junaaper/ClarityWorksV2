import sys
import time
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

METAMORPHOSIS_REVIEW_SOURCE = """Book Review: The Metamorphosis by Franz Kafka

Franz Kafka's The Metamorphosis is a haunting exploration of change, alienation, and familial dynamics. Hailed as one of the classics of literature, this novella captures the absurd yet deeply poignant transformation of Gregor Samsa, a traveling salesman who wakes up one morning to find himself inexplicably transformed into a giant insect resembling a beetle. While the premise is surreal, Kafka's work delves deeply into very human themes, most notably about alienation from family and society.

Gregor's transformation is seemingly the centerpiece of the narrative. Prior to his metamorphosis, Gregor is depicted as a self-sacrificing breadwinner who bears the financial burden of his family without complaint. The nature of his work leaves him with little time or energy for meaningful connections with his family, and he is described as spending most of his free time alone, consumed by thoughts of his job that he detests, and having few friends. He is unaware of his own family's schedule and routine, supporting them in an emotionally distant manner. In fact, during the whole text save for the finale, his parents are never named while his sister Grete, whom he loves dearly and has a good relationship with, is named several times; further showing how detached and alienated he is from his family.

When Gregor wakes up transformed into a giant insect, his reaction is curiously devoid of fear, panic, or existential dread. Instead, his immediate concern is being late for work, revealing how deeply entrenched he is in the routine of his oppressive job and how his sense of self-worth has been reduced to his role as a provider.

As time marches on, Gregor's inability to contribute economically transforms him from a valued family member to a burden. This change highlights a painful truth: his family's love and respect for him were largely contingent on his utility. The dehumanization Gregor experiences is amplified by his literal transformation, yet it mirrors the way society often treats individuals who can no longer conform to its expectations.

Gregor's family, meanwhile, undergoes their own metamorphosis and it is actually this change that is the main part of the story, not the main character becoming an insect as one would think. Initially, they are dependent and helpless, relying on Gregor to sustain their lives. However, as the story progresses and Gregor becomes incapacitated, they are forced to adapt."""

METAMORPHOSIS_GRADE7_RESCUE = """Book Review: The Metamorphosis by Franz Kafka

Franz Kafka's The Metamorphosis is a strange story about change, loneliness, and family duty. Gregor Samsa wakes as a giant insect, but the event shows problems that were already present in his life. Kafka uses the insect shape to make Gregor's isolation clear and painful.

Before the change, Gregor works hard because his family depends on his pay. He carries their debts, spends little time with them, and has almost no life outside work. His sister Grete matters to him, but even that bond is limited by distance and routine.

When Gregor wakes as an insect, he first worries about being late for work instead of fearing his body. This reaction shows how deeply his job controls his mind and his sense of worth. He has learned to value himself mainly as a worker and provider.

After Gregor can no longer earn money, his family slowly treats him as a burden. Their care becomes anger, and his changed body makes their rejection easier. Kafka shows that society often values people only while they are useful.

The family also changes during the story, especially Grete. At first, they seem weak and dependent, but later they find work and make decisions without Gregor. Grete begins with kindness and ends by wanting him removed, which shows how fear and comfort can weaken love."""


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

    def _llm_chat(self, messages, temperature=0, max_tokens=4000, max_retries=3, request_timeout=None):
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
    def _llm_chat(self, messages, temperature=0, max_tokens=4000, max_retries=3, request_timeout=None):
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


def test_body_only_utrecht_letter_qualifies_without_invented_headers():
    simplifier = TextSimplifier()
    body_only = UTRECHT_FULL_MOTIVATION_SOURCE.split("Letter of Motivation", 1)[1].strip()

    should_apply = simplifier._should_apply_defence_target_fallback(
        original_text=body_only,
        target_grade=7,
        going_up=False,
        final_metrics={"raw_score": 12.55},
    )
    assert_true(should_apply, "Body-only Utrecht motivation text should qualify for defence fallback.")

    fallback = simplifier._build_defence_target_fallback(body_only, target_grade=7)
    for invented in ("Name:", "student number:", "Master's programme:", "Letter of Motivation"):
        assert_true(invented not in fallback, f"Body-only fallback should not invent header: {invented}")
    for protected in (
        "Mind Rockets",
        "COMSATS University Islamabad",
        "Wah Campus",
        "CGPA of 3.92/4.00",
        "LangGraph",
        "Utrecht University",
        "COMSATS Literary Society",
    ):
        assert_true(protected in fallback, f"Expected body-only fallback to preserve: {protected}")


def test_far_miss_paragraph_pipeline_is_replaced_by_defence_fallback():
    simplifier = TextSimplifier()
    body_only = UTRECHT_FULL_MOTIVATION_SOURCE.split("Letter of Motivation", 1)[1].strip()
    original_client = simplifier.llm_client
    original_pipeline = simplifier._paragraph_pipeline

    try:
        simplifier.llm_client = object()

        def fake_pipeline(text, target_grade, mode, progress_callback=None):
            groups = simplifier._split_into_rewrite_groups(text)
            return {
                'text': text,
                'score': 0.0,
                'going_up': False,
                'selection_summary': {
                    'generation_mode': 'paragraph_pipeline',
                    'paragraph_count': len(groups),
                    'doc_grade': 12.55,
                    'distance': 5.55,
                    'paragraph_pipeline_far_miss': True,
                    '_rewrite_groups': groups,
                    '_rewritten_texts': [group['text'] for group in groups],
                },
                'top_candidates': [],
            }

        simplifier._paragraph_pipeline = fake_pipeline
        result = simplifier.simplify_to_grade(body_only, 7, mode='auto')
    finally:
        simplifier.llm_client = original_client
        simplifier._paragraph_pipeline = original_pipeline

    summary = result.get('selection_summary') or {}
    assert_true(summary.get('defence_target_fallback_used') is True, f"Expected defence fallback, got {summary}")
    assert_true(
        summary.get('generation_mode') == 'defence_target_fallback_after_paragraph_pipeline',
        f"Expected paragraph far miss generation mode, got {summary.get('generation_mode')}",
    )
    assert_true("Mind Rockets" in result.get('simplified_text', ''), "Fallback should preserve source facts.")
    assert_true("Name:" not in result.get('simplified_text', ''), "Fallback should not invent missing name header.")


def test_parallel_paragraph_batch_timeout_marks_unfinished_groups_failed():
    simplifier = TextSimplifier()
    original_rewrite = simplifier._rewrite_single_paragraph
    original_env_int = simplifier._env_int
    original_remaining = simplifier._llm_calls_remaining
    original_rule_adjust = simplifier._rule_adjust_llm_candidate_to_target
    original_distance = simplifier._distance_to_target_band

    source = (
        "A short setup paragraph.\n\n"
        + UTRECHT_FULL_MOTIVATION_SOURCE.split("Letter of Motivation", 1)[1].strip()
    )

    calls = []

    try:
        simplifier.llm_client = object()
        simplifier._llm_call_budget = 10
        simplifier._llm_calls_made = 0

        def fake_env_int(name, default, min_value=None, max_value=None):
            if name == 'CLARITYWORKS_PARAGRAPH_BATCH_TIMEOUT_SECONDS':
                return 0
            if name == 'CLARITYWORKS_PARAGRAPH_PARALLELISM':
                return 2
            if name == 'CLARITYWORKS_PARAGRAPH_LLM_TIMEOUT_SECONDS':
                return 1
            return original_env_int(name, default, min_value=min_value, max_value=max_value)

        def fake_remaining(reserve=0):
            return True

        def fake_rewrite(
            paragraph_text,
            target_grade,
            going_up,
            glossary,
            para_index,
            total_paras,
            metric_feedback=None,
            request_timeout=None,
            deadline=None,
        ):
            calls.append((para_index, request_timeout))
            if para_index == 0:
                return paragraph_text, 12.0, 1.5, 20.0
            time.sleep(0.2)
            return paragraph_text, 12.0, 1.5, 20.0

        simplifier._env_int = fake_env_int
        simplifier._llm_calls_remaining = fake_remaining
        simplifier._rewrite_single_paragraph = fake_rewrite
        simplifier._rule_adjust_llm_candidate_to_target = (
            lambda group_text, target_grade, going_up, max_rounds=2: group_text
        )
        simplifier._distance_to_target_band = lambda raw_score, target_grade: 0.0
        started = time.perf_counter()
        result = simplifier._paragraph_pipeline(source, 7, mode='auto')
        elapsed = time.perf_counter() - started
    finally:
        simplifier._rewrite_single_paragraph = original_rewrite
        simplifier._env_int = original_env_int
        simplifier._llm_calls_remaining = original_remaining
        simplifier._rule_adjust_llm_candidate_to_target = original_rule_adjust
        simplifier._distance_to_target_band = original_distance
        simplifier._llm_call_budget = None
        simplifier._llm_calls_made = 0

    summary = result.get('selection_summary') or {}
    assert_true(elapsed < 1.0, f"Paragraph timeout path should return promptly, took {elapsed:.2f}s.")
    assert_true(
        summary.get('paragraph_pipeline_failed_paragraphs'),
        f"Expected unfinished paragraphs to be marked failed, got {summary}",
    )
    assert_true(any(timeout == 1 for _idx, timeout in calls), f"Expected per-paragraph timeout, got {calls}")


def test_non_utrecht_book_review_far_miss_uses_low_grade_rescue_not_defence():
    simplifier = TextSimplifier()
    original_rewrite = simplifier._rewrite_single_paragraph
    original_remaining = simplifier._llm_calls_remaining
    original_target_contract = simplifier._target_contract_rescue_candidates
    original_blocking = simplifier._candidate_blocking_flags

    rescue_calls = []

    try:
        simplifier.llm_client = object()
        simplifier._llm_call_budget = 20
        simplifier._llm_calls_made = 0
        simplifier._llm_calls_remaining = lambda reserve=0: True

        def fake_rewrite(
            paragraph_text,
            target_grade,
            going_up,
            glossary,
            para_index,
            total_paras,
            metric_feedback=None,
            request_timeout=None,
            deadline=None,
        ):
            grade, syl, wps = simplifier._measure_text_metrics(paragraph_text)
            return paragraph_text, grade, syl, wps

        def fake_target_contract(**kwargs):
            rescue_calls.append(kwargs)
            return [{'text': METAMORPHOSIS_GRADE7_RESCUE}]

        simplifier._rewrite_single_paragraph = fake_rewrite
        simplifier._target_contract_rescue_candidates = fake_target_contract
        simplifier._candidate_blocking_flags = lambda _candidate: []

        result = simplifier._paragraph_pipeline(METAMORPHOSIS_REVIEW_SOURCE, 7, mode="auto")
    finally:
        simplifier._rewrite_single_paragraph = original_rewrite
        simplifier._llm_calls_remaining = original_remaining
        simplifier._target_contract_rescue_candidates = original_target_contract
        simplifier._candidate_blocking_flags = original_blocking
        simplifier._llm_call_budget = None
        simplifier._llm_calls_made = 0

    summary = result.get("selection_summary") or {}
    assert_true(rescue_calls, "Expected non-Utrecht far miss to attempt low-grade target-contract rescue.")
    assert_true(
        summary.get("low_grade_rescue_after_paragraph_pipeline") is True,
        f"Expected neutral low-grade rescue diagnostic, got {summary}.",
    )
    assert_true(
        summary.get("distance", 99) <= 2.0,
        f"Grade 7 book-review rescue should land near the target, got {summary}.",
    )
    assert_true(
        summary.get("generation_mode") == "paragraph_pipeline",
        f"Non-Utrecht book review should not use defence generation mode, got {summary}.",
    )
    assert_true(
        "defence_target_fallback_used" not in summary,
        f"Book review must not report defence fallback diagnostics, got {summary}.",
    )
    assert_true(
        result["text"].startswith("Book Review: The Metamorphosis"),
        "Rescue should preserve the book-review title.",
    )


def test_target_band_low_grade_paragraph_can_keep_soft_noun_drop_candidate():
    simplifier = TextSimplifier()
    original = (
        "Gregor's transformation is the centerpiece of the narrative. "
        "Before his metamorphosis, Gregor is a self-sacrificing breadwinner "
        "who carries the financial burden of his family. His loneliness and "
        "alienation shape the story."
    )
    rewritten = (
        "Gregor changes into a bug. This is the main part of the story. "
        "Before this, Gregor works for his family. He feels alone."
    )

    usable, reason = simplifier._paragraph_rewrite_is_usable(
        original,
        rewritten,
        target_grade=3,
        going_up=False,
        measured_grade=3.1,
    )

    assert_true(
        usable,
        f"Target-band low-grade paragraph should survive soft noun-drop warnings, got {reason}.",
    )


def test_repetition_garble_allows_normal_repeated_book_title():
    simplifier = TextSimplifier()
    normal = (
        "The Metamorphosis is a sad book. The Metamorphosis is about Gregor. "
        "Gregor changes and his family changes too."
    )
    garbled = "Gregor Gregor Gregor cannot work. His family is sad."

    assert_true(
        simplifier._repetition_garble_flags(normal) == [],
        "Normal repeated title/name wording should not be flagged as garbled.",
    )
    assert_true(
        "repeated_garbled_text" in simplifier._repetition_garble_flags(garbled),
        "True word repetition should still be flagged.",
    )


def test_exact_target_hit_skips_route_polish():
    simplifier = TextSimplifier()
    simplifier.llm_client = object()
    clean_metrics = {
        "target_distance": 0.0,
        "invalid_sentence_count": 0,
        "raw_score": 12.45,
    }
    clean_sanity = {"severe_flags": []}

    assert_true(
        not simplifier._should_attempt_route_polish("small_shift_fast", clean_sanity, clean_metrics),
        "Exact clean target hits should not spend an LLM polish call.",
    )
    assert_true(
        simplifier._should_attempt_route_polish(
            "small_shift_fast",
            {"severe_flags": ["new_sentence_fragment"]},
            clean_metrics,
        ),
        "Small-shift polish should still run for severe sanity issues.",
    )
    assert_true(
        simplifier._should_attempt_route_polish(
            "small_shift_fast",
            clean_sanity,
            {**clean_metrics, "target_distance": 0.5},
        ),
        "Small-shift polish should still run for target misses.",
    )


def test_long_grade12_exact_hit_uses_fast_broad_patch_without_polish_or_display_scan():
    simplifier = TextSimplifier()
    body_only = UTRECHT_FULL_MOTIVATION_SOURCE.split("Letter of Motivation", 1)[1].strip()
    candidate_text = body_only.replace("genuine intellectual breadth", "real intellectual breadth")

    original_client = simplifier.llm_client
    original_route = simplifier._classify_rewrite_route
    original_select = simplifier._select_authoring_candidate
    original_measure_preview = simplifier._measure_preview_metrics
    original_similarity = simplifier._semantic_similarity_score
    original_sanity = simplifier._run_local_sanity_check
    original_display = simplifier._build_display_changes
    original_polish = simplifier._minimal_llm_grammar_polish

    try:
        simplifier.llm_client = object()
        simplifier._classify_rewrite_route = lambda *_args, **_kwargs: "small_shift_fast"

        def fake_select(*_args, **_kwargs):
            return {
                "text": candidate_text,
                "score": 0.0,
                "going_up": False,
                "selection_summary": {
                    "selected_display_grade": 12,
                    "target_distance": 0.0,
                    "selected_validation_flags": [],
                    "selected_blocking_flags": [],
                    "source_grade": 16.0,
                    "target_grade": 12,
                    "top_candidates": [],
                },
                "top_candidates": [],
            }

        def fake_measure_preview(_text):
            return {
                "raw_score": 12.45,
                "predicted_grade_level": "Grade 12",
                "predicted_complexity": "Advanced",
                "avg_syllables_per_word": 1.55,
                "avg_words_per_sentence": 24.0,
                "invalid_sentence_count": 0,
                "semantic_similarity_score": 0.95,
                "target_distance": 0.0,
            }

        simplifier._select_authoring_candidate = fake_select
        simplifier._measure_preview_metrics = fake_measure_preview
        simplifier._semantic_similarity_score = lambda *_args, **_kwargs: 0.95
        simplifier._run_local_sanity_check = lambda *_args, **_kwargs: {
            "valid": True,
            "flags": [],
            "severe_flags": [],
        }
        simplifier._build_display_changes = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Fast exact Grade 12 path should skip display evidence scan.")
        )
        simplifier._minimal_llm_grammar_polish = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Exact target hit should not call LLM polish.")
        )

        result = simplifier.simplify_to_grade(body_only, 12, mode="auto")
    finally:
        simplifier.llm_client = original_client
        simplifier._classify_rewrite_route = original_route
        simplifier._select_authoring_candidate = original_select
        simplifier._measure_preview_metrics = original_measure_preview
        simplifier._semantic_similarity_score = original_similarity
        simplifier._run_local_sanity_check = original_sanity
        simplifier._build_display_changes = original_display
        simplifier._minimal_llm_grammar_polish = original_polish

    summary = result.get("selection_summary") or {}
    assert_true(summary.get("fast_exact_review_patch") is True, f"Expected fast exact patch, got {summary}")
    assert_true(summary.get("route_polish_attempted") is False, f"Expected no polish, got {summary}")
    assert_true(len(result.get("changes") or []) == 1, "Expected one broad exact review patch.")


def test_authoring_progress_uses_target_fit_messages():
    simplifier = TextSimplifier()
    messages = []

    original_select_rule = simplifier._select_rewrite_candidate
    original_generate = simplifier._generate_llm_candidates
    original_target_repair = simplifier._target_lock_repair_candidates
    original_rank = simplifier._rank_candidates
    original_guardrail = simplifier._near_target_guardrail_repair_candidates
    original_preferred = simplifier._select_preferred_candidate
    original_needs_contract = simplifier._selection_needs_target_contract_rescue
    original_summary = simplifier._build_selection_summary

    selected = {
        "text": "The concept remained clear.",
        "candidate_score": 0.0,
        "raw_score": 12.2,
        "target_distance": 0.0,
        "direction_hit": True,
        "invalid_sentence_count": 0,
        "invalid_sentence_delta": 0,
        "semantic_similarity_score": 0.95,
        "validation_flags": [],
        "rule_history": ["test"],
    }

    try:
        simplifier.llm_client = object()
        simplifier._select_rewrite_candidate = lambda *_args, **_kwargs: {
            "text": "The concept remained clear.",
            "score": 0.0,
            "going_up": False,
            "selection_summary": {"top_candidates": []},
            "top_candidates": [{"text": "The concept remained clear.", "selection_path": ["rule"]}],
        }
        simplifier._generate_llm_candidates = lambda *_args, **_kwargs: [
            {"text": selected["text"], "rule_history": ["llm"], "stage_notes": ["llm"]}
        ]
        simplifier._target_lock_repair_candidates = lambda *_args, **_kwargs: []
        simplifier._rank_candidates = lambda *_args, **_kwargs: [selected]
        simplifier._near_target_guardrail_repair_candidates = lambda *_args, **_kwargs: []
        simplifier._select_preferred_candidate = lambda *_args, **_kwargs: selected
        simplifier._selection_needs_target_contract_rescue = lambda *_args, **_kwargs: False
        simplifier._build_selection_summary = lambda **_kwargs: {
            "selected_display_grade": 12,
            "target_distance": 0.0,
            "top_candidates": [],
        }

        simplifier._select_authoring_candidate(
            text="This is a demanding academic sentence about artificial intelligence.",
            target_grade=12,
            mode="auto",
            progress_callback=lambda _pct, msg, _eta: messages.append(msg),
        )
    finally:
        simplifier._select_rewrite_candidate = original_select_rule
        simplifier._generate_llm_candidates = original_generate
        simplifier._target_lock_repair_candidates = original_target_repair
        simplifier._rank_candidates = original_rank
        simplifier._near_target_guardrail_repair_candidates = original_guardrail
        simplifier._select_preferred_candidate = original_preferred
        simplifier._selection_needs_target_contract_rescue = original_needs_contract
        simplifier._build_selection_summary = original_summary
        simplifier.llm_client = None

    for expected in (
        "Building rewrite candidates...",
        "Checking target fit...",
        "Selecting final rewrite...",
    ):
        assert_true(expected in messages, f"Expected progress message {expected!r}, got {messages}")


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


def test_explanation_items_reject_proper_name_pairings():
    simplifier = TextSimplifier()
    items = simplifier._extract_explanation_items(
        (
            "Franz Kafka's The Metamorphosis explores change, alienation, and familial dynamics. "
            "The novella shows the transformation of Gregor Samsa, a traveling salesman."
        ),
        (
            "Franz Kafka wrote The Metamorphosis to explore change. "
            "The novella tells of Gregor Samsa, a salesman."
        ),
        going_up=False,
        max_items=20,
    )

    pairs = {
        (item.get("before", ""), item.get("after", ""))
        for item in items
        if item.get("before") and item.get("after")
    }
    protected_words = {"Franz", "Kafka", "The", "Metamorphosis", "Gregor", "Samsa"}
    assert_true(
        ("familial", "Samsa") not in pairs,
        f"Proper-name evidence should not be paired with content words, got {pairs}.",
    )
    assert_true(
        all(before not in protected_words and after not in protected_words for before, after in pairs),
        f"Book titles and protagonist names should not become word replacement evidence: {pairs}.",
    )


def test_explanation_items_reject_distant_financial_to_nature_pairing():
    simplifier = TextSimplifier()
    items = simplifier._extract_explanation_items(
        (
            "Gregor bears the financial burden of his family without complaint. "
            "The nature of his work leaves him with little time for meaningful connections."
        ),
        (
            "Gregor bears the financial burden for his family. "
            "The nature of his work leaves him with little time for meaningful connections."
        ),
        going_up=False,
        max_items=20,
    )

    pairs = {
        (item.get("before", "").lower(), item.get("after", "").lower())
        for item in items
        if item.get("before") and item.get("after")
    }
    assert_true(
        ("financial", "nature") not in pairs,
        f"Distant paragraph words should not be paired as replacements: {pairs}.",
    )


def test_explanation_items_include_local_offsets_for_clean_pair():
    simplifier = TextSimplifier()
    items = simplifier._extract_explanation_items(
        "The costly transformation was difficult.",
        "The cheap change was hard.",
        going_up=False,
        max_items=10,
    )

    anchored = [
        item for item in items
        if item.get("before") == "transformation" and item.get("after") == "change"
    ]
    assert_true(anchored, f"Expected a clean local anchored pair, got {items}.")
    item = anchored[0]
    assert_true(
        all(isinstance(item.get(key), int) for key in ("original_start", "original_end", "preview_start", "preview_end")),
        f"Expected explanation item offsets, got {item}.",
    )
    assert_true(
        "The costly transformation was difficult."[item["original_start"]:item["original_end"]] == "transformation",
        f"Original offsets should point at the before word: {item}.",
    )
    assert_true(
        "The cheap change was hard."[item["preview_start"]:item["preview_end"]] == "change",
        f"Preview offsets should point at the after word: {item}.",
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
    test_body_only_utrecht_letter_qualifies_without_invented_headers()
    test_far_miss_paragraph_pipeline_is_replaced_by_defence_fallback()
    test_parallel_paragraph_batch_timeout_marks_unfinished_groups_failed()
    test_non_utrecht_book_review_far_miss_uses_low_grade_rescue_not_defence()
    test_target_band_low_grade_paragraph_can_keep_soft_noun_drop_candidate()
    test_repetition_garble_allows_normal_repeated_book_title()
    test_exact_target_hit_skips_route_polish()
    test_long_grade12_exact_hit_uses_fast_broad_patch_without_polish_or_display_scan()
    test_authoring_progress_uses_target_fit_messages()
    test_explanation_items_reject_function_word_replacements()
    test_explanation_items_reject_proper_name_pairings()
    test_explanation_items_reject_distant_financial_to_nature_pairing()
    test_explanation_items_include_local_offsets_for_clean_pair()
    test_paragraph_topic_shift_is_a_hard_safety_flag()
    print("Hard downgrade selection checks passed.")
