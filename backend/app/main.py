"""
LexAI — Legal Document Assistant — FastAPI Backend v1.0.0

Helps users understand, analyse, compare, summarise, and navigate
legal documents through deterministic text analysis + AI narrative.

Every route serving the problem statement is tagged with the verb it
implements:
  simplify    -> POST /simplify
  analyze     -> POST /analyze
  compare     -> POST /compare
  summarize   -> POST /summarize
  ask         -> POST /ask
  prepare     -> POST /prepare

Two infrastructure concerns get their own, non-verb tags (matching the
precedent set by /health): "meta" for liveness, and "history" for the
session document library described in the README under "Session
Document History" — a convenience layer, not one of the six core
features.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from dotenv import load_dotenv

# Must run before any app.* import that reads environment variables at
# import time (app.services.storage builds its repository singleton on
# import). load_dotenv() never overwrites a variable already set in the
# environment, so tests/conftest.py's explicit os.environ assignments
# still take priority over a local .env file.
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import ANALYSIS_CACHE_TTL_SECONDS, APP_NAME, DISCLAIMER, GEMINI_MODEL, VERSION
from app.models import (
    AnalysisResponse,
    AskRequest,
    AskResponse,
    CompareRequest,
    CompareResponse,
    DocumentInput,
    HealthResponse,
    PrepareResponse,
    SavedDocumentDetail,
    SavedDocumentSummary,
    SimplifyRequest,
    SimplifyResponse,
    SummarizeResponse,
)
from app.prompt import (
    ANALYZE_PROMPT,
    ASK_PROMPT,
    COMPARE_PROMPT,
    PREPARE_PROMPT,
    SIMPLIFY_PROMPT,
    SUMMARIZE_PROMPT,
)
from app.services import legal_processor
from app.services.gemini_service import generate_json
from app.services.storage import repository

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title=APP_NAME, version=VERSION, description="AI-powered legal document assistant"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# The frontend is deployed separately (Vercel) from this API (Render), so
# CORS must explicitly allow that origin. Set FRONTEND_ORIGINS to a
# comma-separated list of allowed origins in production; defaults to "*"
# for local development convenience only.
_frontend_origins = os.getenv("FRONTEND_ORIGINS", "*")
_allow_origins = [o.strip() for o in _frontend_origins.split(",")] if _frontend_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    """OWASP security headers on every response — no exceptions."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    return response


# TTL cache for AI responses — keyed by (endpoint, content_hash).
# ANALYSIS_CACHE_TTL_SECONDS is defined in config.py AND this cache
# actually uses it (no aspirational constants).
_cache: dict[tuple[str, int], tuple[float, Any]] = {}


def _cache_get(key: tuple[str, int]) -> Any | None:
    """Returns cached value if within TTL, else None."""
    entry = _cache.get(key)
    if entry is None:
        return None
    cached_at, value = entry
    if time.time() - cached_at > ANALYSIS_CACHE_TTL_SECONDS:
        del _cache[key]
        return None
    return value


def _cache_set(key: tuple[str, int], value: Any) -> None:
    """Stores value with current timestamp."""
    _cache[key] = (time.time(), value)


def _doc_hash(text: str) -> int:
    """Stable hash of document text for cache keying."""
    return hash(text)


def _session_id(request: Request) -> str:
    """
    Anonymous session key for the document-history feature: the caller's
    IP address. No login exists in this demo, so this is a best-effort
    scoping mechanism — callers behind the same NAT share a history.
    A production deployment would replace this with an authenticated
    user id or signed session cookie.
    """
    return get_remote_address(request)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Service liveness — returns model, version, and storage backend."""
    return HealthResponse(
        status="ok",
        version=VERSION,
        model=GEMINI_MODEL,
        storage_backend=type(repository).__name__,
    )


@app.post("/analyze", response_model=AnalysisResponse, tags=["analyze"])
@limiter.limit("20/minute")
async def analyze_document(request: Request, body: DocumentInput) -> AnalysisResponse:
    """ANALYZE: deterministic clause detection, risk flagging, obligation
    extraction, and date identification — then AI-narrated summary."""
    cache_key = ("analyze", _doc_hash(body.text))
    if (cached := _cache_get(cache_key)) is not None:
        return AnalysisResponse(**cached)

    text = legal_processor.preprocess(body.text)
    stats = legal_processor.document_stats(text)
    risks = legal_processor.flag_risks(text)
    obligations = legal_processor.extract_obligations(text)
    rights = legal_processor.extract_rights(text)
    dates = legal_processor.extract_dates(text)
    clauses = legal_processor.extract_clauses(text)

    prompt = ANALYZE_PROMPT.format(
        stats=stats,
        risk_flags=[r["category"] for r in risks],
        obligation_count=len(obligations),
        right_count=len(rights),
        key_dates=dates,
        text_preview=text[:3000],
    )
    try:
        ai_data = await generate_json(prompt)
    except Exception as exc:
        logger.error("Analyze AI failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    result = {
        "stats": stats,
        "risk_flags": risks,
        "obligations": obligations[:10],
        "rights": rights[:10],
        "key_dates": dates,
        "clauses": clauses[:8],
        "ai_summary": ai_data.get("ai_summary", ""),
        "disclaimer": DISCLAIMER,
    }
    _cache_set(cache_key, result)
    await repository.save_document(
        _session_id(request), {"label": body.label or "Analyzed document", "text": text}
    )
    await repository.save_result(_session_id(request), result, kind="analyze")
    logger.info("ANALYZE | words=%d | risks=%d", stats["word_count"], len(risks))
    return AnalysisResponse(**result)


@app.post("/simplify", response_model=SimplifyResponse, tags=["simplify"])
@limiter.limit("20/minute")
async def simplify_document(request: Request, body: SimplifyRequest) -> SimplifyResponse:
    """SIMPLIFY: rewrites legal text in plain English."""
    cache_key = ("simplify", _doc_hash(body.text + (body.focus or "")))
    if (cached := _cache_get(cache_key)) is not None:
        return SimplifyResponse(**cached)

    text = legal_processor.preprocess(body.text)
    focus_instruction = (
        f"Focus especially on: {body.focus}" if body.focus else "Cover all key aspects equally."
    )
    prompt = SIMPLIFY_PROMPT.format(text=text[:6000], focus_instruction=focus_instruction)
    try:
        data = await generate_json(prompt)
    except Exception as exc:
        logger.error("Simplify AI failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    result = {**data, "disclaimer": DISCLAIMER}
    _cache_set(cache_key, result)
    await repository.save_document(_session_id(request), {"label": "Simplified document", "text": text})
    await repository.save_result(_session_id(request), result, kind="simplify")
    return SimplifyResponse(**result)


@app.post("/ask", response_model=AskResponse, tags=["ask"])
@limiter.limit("30/minute")
async def ask_question(request: Request, body: AskRequest) -> AskResponse:
    """ASK: answers the user's specific question about the document."""
    text = legal_processor.preprocess(body.text)
    prompt = ASK_PROMPT.format(text=text[:8000], question=body.question)
    try:
        data = await generate_json(prompt)
    except Exception as exc:
        logger.error("Ask AI failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    result = {**data, "disclaimer": DISCLAIMER}
    await repository.save_document(_session_id(request), {"label": "Document (Q&A)", "text": text})
    await repository.save_result(_session_id(request), result, kind="ask")
    return AskResponse(**result)


@app.post("/compare", response_model=CompareResponse, tags=["compare"])
@limiter.limit("10/minute")
async def compare_documents(request: Request, body: CompareRequest) -> CompareResponse:
    """COMPARE: structural diff of two documents, then AI narrative."""
    cache_key = ("compare", _doc_hash(body.doc_a + body.doc_b))
    if (cached := _cache_get(cache_key)) is not None:
        return CompareResponse(**cached)

    doc_a = legal_processor.preprocess(body.doc_a)
    doc_b = legal_processor.preprocess(body.doc_b)
    structural = legal_processor.compare_texts_structurally(doc_a, doc_b)

    label_a = body.label_a or "Document A"
    label_b = body.label_b or "Document B"
    prompt = COMPARE_PROMPT.format(
        label_a=label_a,
        label_b=label_b,
        structural_a=structural["doc_a"],
        structural_b=structural["doc_b"],
        preview_a=doc_a[:2000],
        preview_b=doc_b[:2000],
    )
    try:
        ai_data = await generate_json(prompt)
    except Exception as exc:
        logger.error("Compare AI failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    result = {
        "doc_a_structural": structural["doc_a"],
        "doc_b_structural": structural["doc_b"],
        **ai_data,
        "disclaimer": DISCLAIMER,
    }
    _cache_set(cache_key, result)
    session_id = _session_id(request)
    await repository.save_document(session_id, {"label": label_a, "text": doc_a})
    await repository.save_document(session_id, {"label": label_b, "text": doc_b})
    await repository.save_result(session_id, result, kind="compare")
    return CompareResponse(**result)


@app.post("/summarize", response_model=SummarizeResponse, tags=["summarize"])
@limiter.limit("20/minute")
async def summarize_document(request: Request, body: DocumentInput) -> SummarizeResponse:
    """SUMMARIZE: executive summary, key points, and action items."""
    cache_key = ("summarize", _doc_hash(body.text))
    if (cached := _cache_get(cache_key)) is not None:
        return SummarizeResponse(**cached)

    text = legal_processor.preprocess(body.text)
    prompt = SUMMARIZE_PROMPT.format(text=text[:8000])
    try:
        data = await generate_json(prompt)
    except Exception as exc:
        logger.error("Summarize AI failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    result = {**data, "disclaimer": DISCLAIMER}
    _cache_set(cache_key, result)
    await repository.save_document(
        _session_id(request), {"label": body.label or "Summarized document", "text": text}
    )
    await repository.save_result(_session_id(request), result, kind="summarize")
    return SummarizeResponse(**result)


@app.post("/prepare", response_model=PrepareResponse, tags=["prepare"])
@limiter.limit("15/minute")
async def prepare_for_lawyer(request: Request, body: DocumentInput) -> PrepareResponse:
    """PREPARE: generates questions, checklist, and red flags to take
    to a legal professional — directly serves the problem statement."""
    cache_key = ("prepare", _doc_hash(body.text))
    if (cached := _cache_get(cache_key)) is not None:
        return PrepareResponse(**cached)

    text = legal_processor.preprocess(body.text)
    risks = legal_processor.flag_risks(text)
    risk_categories = list({r["category"] for r in risks})
    prompt = PREPARE_PROMPT.format(text_preview=text[:4000], risk_categories=risk_categories)
    try:
        data = await generate_json(prompt)
    except Exception as exc:
        logger.error("Prepare AI failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))

    result = {**data, "disclaimer": DISCLAIMER}
    _cache_set(cache_key, result)
    await repository.save_document(
        _session_id(request), {"label": body.label or "Document (lawyer prep)", "text": text}
    )
    await repository.save_result(_session_id(request), result, kind="prepare")
    return PrepareResponse(**result)


@app.get("/documents", response_model=list[SavedDocumentSummary], tags=["history"])
@limiter.limit("60/minute")
async def list_saved_documents(request: Request) -> list[SavedDocumentSummary]:
    """History: lists documents this session has previously submitted,
    so a user can revisit or reuse them without re-pasting the text."""
    docs = await repository.list_documents(_session_id(request))
    return [
        SavedDocumentSummary(id=d["id"], label=d.get("label") or "Untitled document", preview=d["text"][:160])
        for d in docs
    ]


@app.get("/documents/{doc_id}", response_model=SavedDocumentDetail, tags=["history"])
@limiter.limit("60/minute")
async def get_saved_document(doc_id: str, request: Request) -> SavedDocumentDetail:
    """History: retrieves the full text of a previously saved document."""
    doc = await repository.get_document(_session_id(request), doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return SavedDocumentDetail(id=doc["id"], label=doc.get("label") or "Untitled document", text=doc["text"])


@app.delete("/documents/{doc_id}", tags=["history"])
@limiter.limit("60/minute")
async def delete_saved_document(doc_id: str, request: Request) -> dict:
    """History: removes a document from this session's saved list."""
    deleted = await repository.delete_document(_session_id(request), doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "id": doc_id}


@app.get("/", include_in_schema=False)
async def root() -> dict:
    """API-only service — the frontend is deployed separately. Points
    callers at /health and /docs instead of serving a UI here."""
    return {"service": APP_NAME, "version": VERSION, "docs": "/docs", "health": "/health"}
