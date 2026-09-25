import os

os.environ["ENV"] = "test"
os.environ.setdefault("GEMINI_API_KEY", "test-key")

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def mock_gemini():
    with patch("app.main.generate_json", new_callable=AsyncMock) as m:
        yield m
