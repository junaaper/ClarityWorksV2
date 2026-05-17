import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / 'ml-service'
sys.path.insert(0, str(ROOT))

from models.rag_engine import RAGEngine
from utils.text_cleaner import TextCleaner


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_common_pdf_ti_glyph_repairs():
    broken = (
        "This strengthened communica�on and organiza�onal skills. "
        "It helped me work effec�vely. My ambi�on is to build on this "
        "founda�on as a prac��oner."
    )

    repaired, repaired_count = TextCleaner.repair_pdf_replacement_glyphs(broken)

    assert_true(repaired_count == 7, f"Expected 7 repairs, got {repaired_count}")
    assert_true("communication" in repaired, repaired)
    assert_true("organizational" in repaired, repaired)
    assert_true("effectively" in repaired, repaired)
    assert_true("ambition" in repaired, repaired)
    assert_true("foundation" in repaired, repaired)
    assert_true("practitioner" in repaired, repaired)
    assert_true(TextCleaner.PDF_REPLACEMENT_CHAR not in repaired, repaired)


def test_ambiguous_o_circumflex_glyph_repairs_ft_and_ti():
    broken = (
        "AÔer this iniÔal exposure, I studied SoÔware Engineering. "
        "This gave me a strong foundaÔon and helped me become a pracÔÔoner."
    )

    repaired, repaired_count = TextCleaner.repair_extracted_glyphs(broken)

    assert_true(repaired_count == 6, f"Expected 6 repairs, got {repaired_count}: {repaired}")
    assert_true("After this initial exposure" in repaired, repaired)
    assert_true("Software Engineering" in repaired, repaired)
    assert_true("foundation" in repaired, repaired)
    assert_true("practitioner" in repaired, repaired)
    assert_true("Ô" not in repaired, repaired)


def test_latin_extended_ligature_glyph_repairs():
    broken = (
        "Master's programme: ArƟficial Intelligence\n\n"
        "Leter of MoƟvaƟon\n"
        "The first Ɵme a friend menƟoned Mind Rockets, I saw impacƞul work. "
        "UnƟl then, I had only seen medicine as meaningful. Soon aŌer, I studied SoŌware."
    )

    cleaned = TextCleaner.clean_extracted_text(broken)

    assert_true("Artificial Intelligence" in cleaned, cleaned)
    assert_true("Letter of Motivation" in cleaned, cleaned)
    assert_true("The first time" in cleaned, cleaned)
    assert_true("mentioned Mind Rockets" in cleaned, cleaned)
    assert_true("impactful work" in cleaned, cleaned)
    assert_true("Until then" in cleaned, cleaned)
    assert_true("Soon after" in cleaned, cleaned)
    assert_true("Software" in cleaned, cleaned)
    for glyph in ("Ɵ", "Ō", "ƞ"):
        assert_true(glyph not in cleaned, cleaned)


def test_unicode_mojibake_ligature_repairs_before_control_stripping():
    broken_fi = "\ufb01".encode("utf-8").decode("latin-1")
    broken_fl = "\ufb02".encode("utf-8").decode("latin-1")
    broken_quote = "\u2019".encode("utf-8").decode("latin-1")
    broken = f"Arti{broken_fi}cial intelligence {broken_fl}ow isn{broken_quote}t broken."

    cleaned = TextCleaner.clean_extracted_text(broken)

    assert_true("Artificial intelligence flow isn't broken." in cleaned, cleaned)
    assert_true("ï" not in cleaned, cleaned)
    assert_true("\x81" not in cleaned, cleaned)


def test_quality_metrics_return_common_artifact_cleaned_text():
    metrics = TextCleaner.pdf_extraction_quality_metrics("Leter of MoƟvaƟon")

    assert_true(metrics["text"] == "Letter of Motivation", metrics)


def test_pdf_visual_line_wraps_reflow_into_paragraphs():
    broken = (
        "Letter of Motivation\n"
        "The first time I was introduced to the world of programming and computer science was when a\n"
        "good friend of mine mentioned how his brother had launched a company named Mind Rockets,\n"
        "that won an award for their work on a virtual website sign language interpreter for the deaf.\n"
        "Coming from a medical oriented family, this blew my mind. Until that moment, I had thought\n"
        "that the only way to do meaningful, impactful work was in the field of medicine.\n"
    )

    cleaned = TextCleaner.clean_extracted_text(broken)

    assert_true("Letter of Motivation\n\nThe first time" in cleaned, cleaned)
    assert_true("when a good friend" in cleaned, cleaned)
    assert_true("Mind Rockets, that won" in cleaned, cleaned)
    assert_true("the deaf. Coming from" in cleaned, cleaned)


def test_pdf_quality_flags_unrepaired_glyphs():
    metrics = TextCleaner.pdf_extraction_quality_metrics("Clean words with one unknown�glyph left.")
    warnings = TextCleaner.pdf_extraction_warnings(metrics)

    assert_true(metrics["replacement_char_count"] == 1, metrics)
    assert_true(metrics["quality_label"] == "degraded", metrics)
    assert_true(any("unreadable or suspicious glyph" in warning for warning in warnings), warnings)


def test_keyword_retrieval_prefers_explicit_terms():
    engine = object.__new__(RAGEngine)
    exact = "The SDLC includes requirements engineering, software development, testing, and evolution."
    broad = "Software engineering uses process models to organize development work."

    exact_score = engine._keyword_score("Teach me about Software Engineering models and the SDLC", exact)
    broad_score = engine._keyword_score("Teach me about Software Engineering models and the SDLC", broad)

    assert_true(exact_score > broad_score, f"Expected SDLC chunk to win: {exact_score} <= {broad_score}")


if __name__ == "__main__":
    test_common_pdf_ti_glyph_repairs()
    test_ambiguous_o_circumflex_glyph_repairs_ft_and_ti()
    test_latin_extended_ligature_glyph_repairs()
    test_unicode_mojibake_ligature_repairs_before_control_stripping()
    test_quality_metrics_return_common_artifact_cleaned_text()
    test_pdf_visual_line_wraps_reflow_into_paragraphs()
    test_pdf_quality_flags_unrepaired_glyphs()
    test_keyword_retrieval_prefers_explicit_terms()
    print("PDF extraction quality and RAG keyword checks passed.")
