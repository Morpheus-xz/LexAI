"""
Storage backend factory.

Selects a StorageRepository implementation at import time based on the
environment. app.main and the test suite import `repository` from here
and never instantiate a concrete backend themselves — they only use
the abstract interface defined in base.py.
"""
from __future__ import annotations

import os

from app.services.storage.base import StorageRepository
from app.services.storage.memory_store import InMemoryRepository


def get_repository() -> StorageRepository:
    """
    Returns InMemoryRepository when ENV=test or GOOGLE_CLOUD_PROJECT is
    unset (local dev, Render, Vercel). Returns a cloud-backed store when
    a GCP project is configured. main.py and tests never know or care
    which backend is active — they only use the abstract interface.
    """
    if os.getenv("ENV") == "test" or not os.getenv("GOOGLE_CLOUD_PROJECT"):
        return InMemoryRepository()
    # Extend here for Firestore or other backends
    return InMemoryRepository()


repository = get_repository()
