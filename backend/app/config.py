"""
Central configuration — single source of truth for LexAI.

Every keyword list, size limit, model name, and tunable setting lives
here. No other module hardcodes these values — they import from this
file, making the app auditable and trivially retuneable.
"""

APP_NAME: str = "LexAI — Legal Document Assistant"
VERSION: str = "1.0.0"
GEMINI_MODEL: str = "gemini-2.5-flash"
MAX_RETRIES: int = 3
MAX_DOCUMENT_CHARS: int = 50_000  # ~12,500 words — generous but bounded
ANALYSIS_CACHE_TTL_SECONDS: int = 1800  # 30 minutes — used by app.main _cache

# Risk-indicator keywords → category mapping.
# Keys must be lowercase (flag_risks() compares against text.lower()).
RISK_KEYWORDS: dict[str, str] = {
    "indemnif": "Indemnification",
    "liability": "Liability",
    "limitation of liability": "Liability Cap",
    "liquidated damages": "Financial Penalty",
    "penalty": "Financial Penalty",
    "termination for convenience": "Termination Risk",
    "terminate": "Termination",
    "non-compete": "Restrictive Covenant",
    "non-solicitation": "Restrictive Covenant",
    "arbitration": "Dispute Resolution",
    "governing law": "Jurisdiction",
    "force majeure": "Force Majeure",
    "waiver": "Rights Waiver",
    "disclaimer": "Disclaimer",
    "as is": "No Warranty",
    "intellectual property": "IP Rights",
    "confidential": "Confidentiality",
    "perpetual": "Perpetual Obligation",
    "irrevocable": "Irrevocable Commitment",
    "auto-renew": "Auto-Renewal",
}

OBLIGATION_KEYWORDS: list[str] = [
    "shall",
    "must",
    "agrees to",
    "is required to",
    "will",
    "undertakes to",
    "is obligated to",
]

RIGHT_KEYWORDS: list[str] = [
    "may",
    "is entitled to",
    "reserves the right",
    "has the right",
    "at its sole discretion",
    "may elect",
]

# Regex patterns for detecting common legal clause headers.
CLAUSE_HEADERS: list[str] = [
    r"^\d+\.\s+[A-Z][A-Z\s]{2,}",  # "1. DEFINITIONS"
    r"^[A-Z][A-Z\s]{4,}(?:\s*:)",  # "LIMITATION OF LIABILITY:"
    r"^Article\s+\d+",  # "Article 1"
    r"^Section\s+\d+",  # "Section 1"
    r"^SCHEDULE\s+\d+",  # "SCHEDULE 1"
]

DISCLAIMER: str = (
    "LexAI provides legal information and education only — not legal "
    "advice. Always consult a qualified solicitor or attorney for advice "
    "specific to your situation."
)
