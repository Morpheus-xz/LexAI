"""
Abstract persistence interface for LexAI.

app.main and the test suite depend only on this interface — never on
a concrete backend. This is what makes swapping InMemoryRepository for
a cloud-backed store (Firestore, etc.) a zero-blast-radius change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class StorageRepository(ABC):
    """Abstract persistence interface for documents and analysis results."""

    @abstractmethod
    async def save_document(self, session_id: str, doc: dict) -> dict:
        """Persists a document under a session, returning it with an id."""

    @abstractmethod
    async def list_documents(self, session_id: str) -> list[dict]:
        """Returns all documents saved under a session."""

    @abstractmethod
    async def get_document(self, session_id: str, doc_id: str) -> dict | None:
        """Returns a single document by id, or None if not found."""

    @abstractmethod
    async def delete_document(self, session_id: str, doc_id: str) -> bool:
        """Deletes a document by id. Returns True if it existed."""

    @abstractmethod
    async def save_result(self, session_id: str, result: dict, kind: str) -> dict:
        """Persists an analysis result (e.g. 'analyze', 'compare') for a session."""
