"""
Legal Document Processing Engine.

Design principle: every structural insight about a legal document
(clause detection, risk flags, obligation identification, date
extraction, readability stats) is computed by pure, deterministic,
unit-tested functions below — never by an LLM.

Gemini is used elsewhere ONLY to explain, compare, and advise on
top of the structured data this engine already extracted. This keeps
every factual claim about the document auditable and reproducible,
while using AI for what it genuinely excels at: plain-English
reasoning and personalized guidance.
"""
from __future__ import annotations

import re

from app.config import CLAUSE_HEADERS, OBLIGATION_KEYWORDS, RIGHT_KEYWORDS, RISK_KEYWORDS


def preprocess(text: str) -> str:
    """
    Normalises raw document text: collapses whitespace, strips zero-width
    characters, normalises smart quotes to ASCII. Called on every document
    before any other processing — a single clean input prevents downstream
    functions from having to handle encoding edge cases individually.
    """
    text = re.sub(r"[​‌‍﻿]", "", text)
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def extract_clauses(text: str) -> list[dict]:
    """
    Detects and extracts named sections (clauses) from a legal document
    by matching known clause-header patterns from CLAUSE_HEADERS config.
    Returns a list of {title, content, char_start} dicts.
    Pure function — same input always yields same output.
    """
    clauses = []
    for pattern in CLAUSE_HEADERS:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            start = match.start()
            title = match.group(0).strip()
            # Content runs until the next clause header or end of text
            next_match = re.search(
                "|".join(CLAUSE_HEADERS),
                text[start + len(title) :],
                re.IGNORECASE | re.MULTILINE,
            )
            end = (
                start + len(title) + next_match.start()
                if next_match
                else len(text)
            )
            content = text[start + len(title) : end].strip()
            clauses.append(
                {
                    "title": title,
                    "content": content[:500],  # preview only
                    "char_start": start,
                }
            )
    return clauses


def flag_risks(text: str) -> list[dict]:
    """
    Scans text for risk-indicator keywords from RISK_KEYWORDS config.
    Returns list of {keyword, category, context} dicts — one per match.
    'Context' is the 120-char window around the keyword for display.
    Deterministic: same document, same flags every time.
    """
    flags = []
    text_lower = text.lower()
    for keyword, category in RISK_KEYWORDS.items():
        # Anchor only at the start of the keyword: several RISK_KEYWORDS
        # entries are intentional word stems (e.g. "indemnif" for
        # "indemnify"/"indemnification"/"indemnified"), which never end
        # on a \b boundary. A leading \b still prevents mid-word false
        # matches (e.g. "liability" inside "reliability").
        for match in re.finditer(r"\b" + re.escape(keyword), text_lower):
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 60)
            flags.append(
                {
                    "keyword": keyword,
                    "category": category,
                    "context": text[start:end].strip(),
                }
            )
    return flags


def extract_obligations(text: str) -> list[str]:
    """
    Extracts sentences containing obligation keywords (shall, must, agrees
    to, is required to, will). These are the actionable commitments buried
    in legal language that users most need to understand.
    """
    obligations = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        lower = sentence.lower()
        if any(kw in lower for kw in OBLIGATION_KEYWORDS):
            obligations.append(sentence.strip())
    return obligations


def extract_rights(text: str) -> list[str]:
    """
    Extracts sentences conferring rights (may, is entitled to, reserves
    the right, has the right). Counterpart to extract_obligations —
    together they give users a balanced view of the contract.
    """
    rights = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        lower = sentence.lower()
        if any(kw in lower for kw in RIGHT_KEYWORDS):
            rights.append(sentence.strip())
    return rights


def extract_dates(text: str) -> list[str]:
    """
    Finds date-like patterns (deadlines, effective dates, expiry dates).
    Covers common formats: DD/MM/YYYY, Month DD YYYY, DD Month YYYY.
    Returns raw matched strings for Gemini to contextualise.
    """
    patterns = [
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b",
    ]
    dates = []
    for pattern in patterns:
        dates.extend(re.findall(pattern, text, re.IGNORECASE))
    return list(dict.fromkeys(dates))  # deduplicate, preserve order


def document_stats(text: str) -> dict:
    """
    Computes structural statistics about the document: word count,
    estimated reading time (avg 200 wpm), sentence count, paragraph
    count. Used to give users immediate orientation before AI analysis.
    """
    words = len(text.split())
    sentences = len(re.findall(r"[.!?]+", text)) or 1
    paragraphs = len([p for p in text.split("\n\n") if p.strip()])
    return {
        "word_count": words,
        "estimated_reading_minutes": round(words / 200),
        "sentence_count": sentences,
        "paragraph_count": paragraphs,
        "character_count": len(text),
    }


def compare_texts_structurally(doc_a: str, doc_b: str) -> dict:
    """
    Pure structural diff between two documents: counts unique risks,
    obligations, rights, and clauses in each. This deterministic
    comparison gives Gemini grounded numbers to reason about —
    it never invents which document has more risks, because this
    function already counted them.
    """
    return {
        "doc_a": {
            "stats": document_stats(doc_a),
            "risk_count": len(flag_risks(doc_a)),
            "obligation_count": len(extract_obligations(doc_a)),
            "right_count": len(extract_rights(doc_a)),
            "clause_count": len(extract_clauses(doc_a)),
            "dates": extract_dates(doc_a),
        },
        "doc_b": {
            "stats": document_stats(doc_b),
            "risk_count": len(flag_risks(doc_b)),
            "obligation_count": len(extract_obligations(doc_b)),
            "right_count": len(extract_rights(doc_b)),
            "clause_count": len(extract_clauses(doc_b)),
            "dates": extract_dates(doc_b),
        },
    }
