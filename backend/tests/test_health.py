from unittest.mock import Mock

import app.main as main_module
from app.f1_data import DataSourceUnavailableError


def test_health_returns_ok(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_is_deterministic_and_fastf1_independent(client) -> None:
    responses = [client.get("/health") for _ in range(3)]

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert [response.json() for response in responses] == [
        {"status": "ok"},
        {"status": "ok"},
        {"status": "ok"},
    ]


def test_health_remains_available_when_session_loader_fails(
    client, monkeypatch
) -> None:
    loader = Mock(side_effect=DataSourceUnavailableError("controlled source failure"))
    monkeypatch.setattr(main_module, "load_session_summary", loader, raising=True)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    loader.assert_not_called()
