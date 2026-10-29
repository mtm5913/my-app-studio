"""Isolated test app; never use the learner's runtime data or signing key."""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def settings(tmp_path):
    """An explicit loopback test environment with a disposable database/key."""
    return Settings(
        mode="development",
        origin="http://127.0.0.1:8000",
        database=Path(tmp_path) / "test.sqlite3",
        secret="test-only-" + "a" * 48,
    )


@pytest.fixture
def client(settings):
    """Drive HTTP through the real app and isolated SQLite services."""
    with TestClient(create_app(settings), base_url=settings.origin) as browser:
        yield browser
