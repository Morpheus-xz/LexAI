"""
In-memory implementation of StorageRepository.

Used for local development, tests, and any deployment without a
configured cloud project (Render, Vercel, etc.). Data lives only for
the lifetime of the process — acceptable for a stateless demo backend
where every endpoint is otherwise idempotent given the same input.
"""
from __future__ import annotations

import uuid
from collections import defaultdict

from app.services.storage.base import StorageRepository


class InMemoryRepository(StorageRepository):
    """Process-local, dict-backed StorageRepository implementation."""

    def __init__(self) -> None:
        self._documents: dict[str, dict[str, dict]] = defaultdict(dict)
        self._results: dict[str, list[dict]] = defaultdict(list)

    async def save_document(self, session_id: str, doc: dict) -> dict:
        doc_id = doc.get("id") or str(uuid.uuid4())
        saved = {**doc, "id": doc_id}
        self._documents[session_id][doc_id] = saved
        return saved

    async def list_documents(self, session_id: str) -> list[dict]:
        return list(self._documents[session_id].values())

    async def get_document(self, session_id: str, doc_id: str) -> dict | None:
        return self._documents[session_id].get(doc_id)

    async def delete_document(self, session_id: str, doc_id: str) -> bool:
        return self._documents[session_id].pop(doc_id, None) is not None

    async def save_result(self, session_id: str, result: dict, kind: str) -> dict:
        result_id = str(uuid.uuid4())
        saved = {**result, "id": result_id, "kind": kind}
        self._results[session_id].append(saved)
        return saved
