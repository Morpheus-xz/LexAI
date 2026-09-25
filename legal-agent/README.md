# LexAI — AI Legal Document Assistant

> Makes legal information accessible by helping users understand, compare,
> simplify, and navigate legal documents — without replacing a qualified
> legal professional.
>
> **Deployment target:** Render (Docker web service). This repository has
> not yet been deployed to a public URL; see [Deployment](#deployment) for
> the exact steps to stand it up on Render using the included `Dockerfile`.

## How this solves the problem statement

The problem statement identifies six concrete ways to help users with legal
documents. Every feature in LexAI maps to exactly one of them — this mapping
is explicit in the FastAPI route tags (`tags=[...]` in `app/main.py`), in
the UI button labels (`static/index.html`), and in this table:

| User Need | Feature | Endpoint | UI Section |
|-----------|---------|----------|------------|
| Simplify complex documents | Plain-English rewriter | `POST /simplify` | "📝 Simplify" button |
| Highlight clauses, risks, obligations | Deterministic risk/obligation/clause extractor + AI narrative | `POST /analyze` | "🔍 Analyze" button |
| Compare contracts or policies | Two-document structural diff + AI comparison | `POST /compare` | "⚖️ Compare" button |
| Generate summaries, checklists, actionable outputs | Executive summary + key points + action items | `POST /summarize` | "📋 Summarize" button |
| Answer questions based on a document | Document-grounded Q&A | `POST /ask` | "❓ Ask a Question" button |
| Prepare information/questions for a legal professional | Question + checklist + red-flag generator | `POST /prepare` | "👨‍⚖️ Prepare for Lawyer" button |

Two additional routes exist purely as infrastructure and are tagged outside
the six-verb mapping above: `GET /health` (tag `meta`, liveness probe) and
`GET/DELETE /documents...` (tag `history`, a session-scoped convenience
layer described in [Session Document History](#session-document-history)).

## Architecture decision: deterministic analysis, AI for reasoning

The single most important design decision in LexAI is the separation
between **fact** and **narrative**:

- **`app/services/legal_processor.py`** is a pure, side-effect-free,
  fully unit-tested module. Every structural claim about a document —
  which clauses it contains, which risk keywords appear, which sentences
  are obligations vs. rights, which dates are mentioned, how long it is —
  is computed here with plain regex and string logic. Given the same
  input, it always returns the same output, and every function is
  independently tested in `tests/test_legal_processor.py`.
- **`app/services/gemini_service.py`** and **`app/prompt.py`** are used
  ONLY to explain, compare, and advise on top of the structured data the
  processor already extracted. Every Gemini prompt is grounded with the
  processor's output and explicitly instructed not to invent facts.

This means every factual claim LexAI makes about a document is auditable
and reproducible without calling an LLM, while AI is used for exactly what
it is good at: turning structured facts into plain-English guidance. This
also keeps the app cheap and fast to test — the pure core has trivial
100% branch coverage with no mocking required.

## Session Document History

`GET /documents`, `GET /documents/{id}`, and `DELETE /documents/{id}`
(tag `history`) let a user revisit or delete documents they previously
submitted in the same browser session, so they don't have to re-paste
text to run a second action against it. Session scoping is by caller IP
address (`app/main.py::_session_id`) since the app has no login — this is
a reasonable convenience for an anonymous demo tool, not a security
boundary. The storage layer behind it (`app/services/storage/`) is a
`StorageRepository` abstract interface with an in-memory implementation
(`InMemoryRepository`), selected by `app/services/storage/__init__.py`'s
factory function so a future cloud-backed implementation (e.g. Firestore)
can be swapped in without touching `app/main.py` or the tests.

## Caching

`ANALYSIS_CACHE_TTL_SECONDS` (30 minutes, `app/config.py`) backs an
in-process TTL cache (`app/main.py::_cache`) keyed by `(endpoint,
hash(document text))`. `/analyze`, `/simplify`, `/compare`, `/summarize`,
and `/prepare` all check the cache before calling Gemini and populate it
after a successful call, so re-submitting the same document text within
the TTL window returns instantly with zero additional Gemini cost.
`tests/test_endpoints.py::test_analyze_cached_on_second_call` asserts the
underlying Gemini mock is called exactly once across two identical
requests. `/ask` is intentionally not cached — the same document is
expected to be asked many different questions, so caching by document
text alone would return stale answers to new questions.

## Security

- **Input validation at the edge**: every request body is a Pydantic
  model with bounded string lengths (`app/models.py`) and a shared
  `_require_non_empty_text()` validator rejecting blank/whitespace-only
  text — malformed input never reaches business logic.
- **Security headers on every response**: `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`,
  `Strict-Transport-Security`, and a restrictive `Permissions-Policy`
  are set by middleware in `app/main.py`, verified in
  `tests/test_security.py` including on 404 responses.
- **Rate limiting**: every AI-backed route is rate-limited per client IP
  via `slowapi` (e.g. `20/minute` on `/analyze`, `10/minute` on the more
  expensive `/compare`), preventing single-client abuse of the Gemini
  quota.
- **CORS**: credentials are disabled (`allow_credentials=False`); the app
  serves no cookies or session tokens, so there is nothing to leak
  cross-origin.
- **XSS prevention in the frontend**: `script.js` renders every AI
  response through a `safeHTML()` helper that HTML-encodes text via
  `textContent` before any `innerHTML` assignment — a document or AI
  response containing `<script>` or event-handler markup is rendered as
  inert text, never executed.
- **No secrets in the repo**: the Gemini API key is read only from the
  `GEMINI_API_KEY` environment variable (`app/services/gemini_service.py`);
  `.gitignore` excludes `.env` files.
- **Non-root container**: the `Dockerfile` creates and switches to an
  unprivileged `appuser` before running the app.

## Efficiency

- **Non-blocking Gemini calls**: the Gemini SDK is synchronous, so
  `gemini_service.generate()` offloads it to a thread pool via
  `asyncio.to_thread`, keeping the FastAPI event loop free to serve other
  requests concurrently.
- **Exponential backoff retries**: transient Gemini failures are retried
  up to `MAX_RETRIES` (3) times with exponential backoff (`tenacity`)
  before surfacing an error to the user.
- **Result caching** (see above) avoids redundant Gemini calls entirely
  for repeated documents within the TTL window.
- **Bounded document size**: `MAX_DOCUMENT_CHARS` (50,000 chars) caps both
  request payload size and Gemini prompt/token cost; prompts additionally
  truncate previews (e.g. first 3,000–8,000 chars) rather than sending
  the full document where a preview suffices.

## Testing

Testing concentrates effort where it has the highest signal-to-cost
ratio: the pure `legal_processor` module, which is exhaustively unit
tested with no mocking (`tests/test_legal_processor.py`), plus focused
endpoint, security, and model-validation tests using a mocked Gemini
client (`tests/conftest.py::mock_gemini`) so tests never make real API
calls or depend on model output quality.

```bash
make test
# or directly:
ENV=test GEMINI_API_KEY=test-key pytest tests/ -v
```

## Accessibility

- A skip link is the first focusable element on the page, jumping to
  `#main-content`.
- All buttons carry explicit `aria-label`s describing their action; the
  document textarea is `aria-required="true"`.
- The results panel is `role="region" aria-live="polite"`, so screen
  readers announce new AI results as they arrive.
- Risk flags never rely on color alone — each carries a `⚠️` icon and a
  text category label.
- `prefers-reduced-motion: reduce` disables the loading spinner animation
  and all transitions.
- The navy/gold/white/grey palette maintains at least 4.5:1 text contrast.

## Project structure

```
legal-agent/
├── app/
│   ├── main.py                  # FastAPI app, routes, middleware, caching
│   ├── config.py                # All constants, keyword lists, settings
│   ├── models.py                # All Pydantic models + shared validators
│   ├── prompt.py                # All Gemini prompt templates
│   └── services/
│       ├── legal_processor.py   # Pure deterministic text analysis
│       ├── gemini_service.py    # Gemini wrapper (retry, async, JSON)
│       └── storage/             # Abstract repository + in-memory impl
├── tests/
├── static/                      # Vanilla HTML/CSS/JS frontend
├── requirements.txt
├── Dockerfile
├── Makefile
└── README.md
```

## Running locally

```bash
make install
export GEMINI_API_KEY=your-real-key   # or omit to use test-key for local smoke testing
make run
# App is served at http://localhost:8080
```

## Deployment

LexAI ships with a hardened, non-root `Dockerfile` and is designed to be
deployed as a Render **Web Service**:

1. Push this repository to GitHub.
2. On Render, create a new **Web Service** from the repo, choose the
   **Docker** runtime (Render will use the included `Dockerfile`
   automatically).
3. Set the environment variable `GEMINI_API_KEY` in the Render dashboard.
4. Render sets `$PORT` automatically; the `Dockerfile` already reads
   `ENV PORT=8080` and the app binds to it via `uvicorn --port 8080` —
   if Render assigns a different port, update the `CMD` to use `$PORT`.
5. Render's health check can point at `GET /health`.

## Important disclaimer

⚠️ LexAI provides legal information and education only — not legal
advice. It does not create an attorney-client relationship, and its
output should never be treated as a substitute for consulting a
qualified solicitor or attorney about your specific situation. Every
API response includes this disclaimer in its `disclaimer` field, and it
is always visible in the page footer.
