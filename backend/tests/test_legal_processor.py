"""
Exhaustive tests for the pure, deterministic legal_processor module.
No mocks needed — every function here is a pure function of its input.
"""
from app.services import legal_processor as lp


# ---- preprocess ----------------------------------------------------------

def test_preprocess_normalises_smart_quotes():
    text = "‘Hello’ and “World”"
    assert lp.preprocess(text) == "'Hello' and \"World\""


def test_preprocess_strips_zero_width_chars():
    text = "Hello​‌‍﻿World"
    assert lp.preprocess(text) == "HelloWorld"


def test_preprocess_collapses_whitespace():
    text = "Hello    World   Foo"
    assert lp.preprocess(text) == "Hello World Foo"


# ---- extract_clauses ------------------------------------------------------

def test_extract_clauses_finds_numbered_sections():
    text = "1. DEFINITIONS\nSome content here.\n2. OBLIGATIONS\nMore content."
    clauses = lp.extract_clauses(text)
    titles = [c["title"] for c in clauses]
    assert any("DEFINITIONS" in t for t in titles)
    assert any("OBLIGATIONS" in t for t in titles)


def test_extract_clauses_empty_document_returns_empty():
    assert lp.extract_clauses("") == []


# ---- flag_risks ------------------------------------------------------------

def test_flag_risks_finds_indemnification_keyword():
    text = "The vendor shall indemnify the client against all claims."
    flags = lp.flag_risks(text)
    categories = [f["category"] for f in flags]
    assert "Indemnification" in categories


def test_flag_risks_finds_termination_keyword():
    text = "Either party may terminate this agreement with 30 days notice."
    flags = lp.flag_risks(text)
    categories = [f["category"] for f in flags]
    assert "Termination" in categories


def test_flag_risks_unknown_text_returns_empty():
    text = "The cat sat on the mat and looked at the stars."
    assert lp.flag_risks(text) == []


def test_flag_risks_context_window_correct_length():
    keyword = "penalty"
    text = "x" * 100 + f" {keyword} " + "y" * 100
    flags = lp.flag_risks(text)
    assert len(flags) == 1
    # 60 chars before + keyword (with surrounding spaces) + 60 chars after
    assert len(flags[0]["context"]) <= 60 + len(keyword) + 2 + 60


# ---- extract_obligations ----------------------------------------------------

def test_extract_obligations_finds_shall():
    text = "The tenant shall pay rent on the first of each month. The sky is blue."
    obligations = lp.extract_obligations(text)
    assert any("shall pay rent" in o for o in obligations)


def test_extract_obligations_finds_must():
    text = "The employee must complete training within 30 days. Nothing else matters."
    obligations = lp.extract_obligations(text)
    assert any("must complete training" in o for o in obligations)


def test_extract_obligations_empty_returns_empty():
    text = "The weather today is sunny and pleasant."
    assert lp.extract_obligations(text) == []


# ---- extract_rights ----------------------------------------------------------

def test_extract_rights_finds_may():
    text = "The licensee may terminate this license at any time. Unrelated fact."
    rights = lp.extract_rights(text)
    assert any("may terminate" in r for r in rights)


def test_extract_rights_finds_entitled_to():
    text = "The employee is entitled to 20 days of paid leave. Nothing else here."
    rights = lp.extract_rights(text)
    assert any("is entitled to" in r for r in rights)


# ---- extract_dates ----------------------------------------------------------

def test_extract_dates_finds_numeric_dates():
    text = "This agreement is effective as of 01/15/2026 and expires 12-31-2027."
    dates = lp.extract_dates(text)
    assert "01/15/2026" in dates
    assert "12-31-2027" in dates


def test_extract_dates_finds_month_name_dates():
    text = "The effective date is January 15, 2026."
    dates = lp.extract_dates(text)
    assert any("January 15, 2026" in d for d in dates)


def test_extract_dates_deduplicates():
    text = "Effective 01/01/2026. Also effective 01/01/2026 again."
    dates = lp.extract_dates(text)
    assert dates.count("01/01/2026") == 1


# ---- document_stats ----------------------------------------------------------

def test_document_stats_word_count_correct():
    text = "one two three four five"
    stats = lp.document_stats(text)
    assert stats["word_count"] == 5


def test_document_stats_empty_document():
    stats = lp.document_stats("")
    assert stats["word_count"] == 0
    assert stats["sentence_count"] == 1  # `or 1` fallback
    assert stats["character_count"] == 0


def test_document_stats_reading_time_scales_with_length():
    short_stats = lp.document_stats(" ".join(["word"] * 100))
    long_stats = lp.document_stats(" ".join(["word"] * 1000))
    assert long_stats["estimated_reading_minutes"] > short_stats["estimated_reading_minutes"]


# ---- compare_texts_structurally ----------------------------------------------

def test_compare_texts_structurally_returns_both_keys():
    result = lp.compare_texts_structurally("Document A text.", "Document B text.")
    assert "doc_a" in result
    assert "doc_b" in result


def test_compare_texts_structurally_higher_risk_detected():
    low_risk = "This is a simple agreement about widgets."
    high_risk = (
        "The parties agree to indemnify each other. Liability is capped. "
        "This agreement includes a penalty clause and an arbitration clause."
    )
    result = lp.compare_texts_structurally(low_risk, high_risk)
    assert result["doc_b"]["risk_count"] > result["doc_a"]["risk_count"]
