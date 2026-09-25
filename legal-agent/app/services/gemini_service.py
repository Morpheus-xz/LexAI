"""
Gemini API wrapper.

- Singleton client (one per process, not per request).
- Synchronous SDK call offloaded to thread pool (asyncio.to_thread)
  so the event loop never blocks under concurrency.
- Exponential-backoff retry on the sync call layer.
- generate_json() strips markdown fences defensively.
- This module produces ONLY natural-language narrative and structured
  JSON reasoning. It NEVER computes structural facts about a document —
  those come from legal_processor.py.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import GEMINI_MODEL, MAX_RETRIES

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Add it as an environment variable."
            )
        _client = genai.Client(api_key=key)
    return _client


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
def _generate_sync(prompt: str) -> str:
    """Synchronous Gemini call with exponential-backoff retry."""
    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    return _get_client().models.generate_content(
        model=GEMINI_MODEL, contents=contents
    ).text


async def generate(prompt: str) -> str:
    """Async wrapper — never blocks the event loop."""
    return await asyncio.to_thread(_generate_sync, prompt)


async def generate_json(prompt: str) -> Any:
    """Calls Gemini expecting JSON; strips markdown fences defensively."""
    raw = await generate(prompt)
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    return json.loads(raw.strip())
