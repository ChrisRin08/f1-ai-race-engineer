from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session_summary_fixture() -> dict[str, object]:
    return {
        "year": 2025,
        "event": {"name": "Italian Grand Prix"},
        "session": {"name": "Race", "type": "race"},
        "source": {"provider": "FastF1"},
    }
