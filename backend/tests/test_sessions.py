from collections.abc import Callable
from unittest.mock import Mock, call

import pytest

import app.main as main_module
from app.f1_data import DataSourceUnavailableError
from app.models import ErrorResponse

CONTROL_SESSION_URL = "/api/v1/seasons/2025/events/italian-grand-prix/sessions/race"

CONTROL_SESSION_RESPONSE = {
    "year": 2025,
    "event": {
        "name": "Italian Grand Prix",
        "round_number": 16,
        "country": "Italy",
        "location": "Monza",
    },
    "session": {"name": "Race", "type": "race"},
    "circuit": {"name": "Monza"},
    "timing": {"scheduled_start_utc": "2025-09-07T13:00:00Z", "total_laps": 53},
    "participants": [
        {
            "position": 1,
            "driver_number": "1",
            "abbreviation": "VER",
            "full_name": "Max Verstappen",
            "team_name": "Red Bull Racing",
        }
    ],
    "data_availability": {
        "session_info": "available",
        "results": "available",
        "laps": "available",
        "telemetry": "not_requested",
        "weather": "not_requested",
        "race_control_messages": "not_requested",
    },
    "source": {"provider": "FastF1"},
}


def install_loader(
    monkeypatch,
    loader: Callable[[int, str, str], dict[str, object]],
) -> None:
    monkeypatch.setattr(main_module, "load_session_summary", loader, raising=True)


def test_control_session_returns_contract_response(client, monkeypatch) -> None:
    loader = Mock(return_value=CONTROL_SESSION_RESPONSE)
    install_loader(monkeypatch, loader)

    response = client.get(CONTROL_SESSION_URL)

    assert response.status_code == 200
    assert response.json() == CONTROL_SESSION_RESPONSE
    loader.assert_called_once_with(2025, "Italian Grand Prix", "Race")


def test_control_session_response_is_deterministic(client, monkeypatch) -> None:
    loader = Mock(return_value=CONTROL_SESSION_RESPONSE)
    install_loader(monkeypatch, loader)

    responses = [client.get(CONTROL_SESSION_URL) for _ in range(2)]

    assert [response.status_code for response in responses] == [200, 200]
    assert responses[0].json() == responses[1].json() == CONTROL_SESSION_RESPONSE
    assert loader.call_args_list == [
        call(2025, "Italian Grand Prix", "Race"),
        call(2025, "Italian Grand Prix", "Race"),
    ]


def test_control_session_maps_source_failure_to_503(client, monkeypatch) -> None:
    private_message = "controlled source failure"
    loader = Mock(side_effect=DataSourceUnavailableError(private_message))
    install_loader(monkeypatch, loader)

    response = client.get(CONTROL_SESSION_URL)

    assert response.status_code == 503
    error_response = ErrorResponse.model_validate(response.json())
    assert error_response.error.code == "data_source_unavailable"
    assert error_response.error.message
    assert private_message not in error_response.error.message
    loader.assert_called_once_with(2025, "Italian Grand Prix", "Race")


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/seasons/2024/events/italian-grand-prix/sessions/race",
        "/api/v1/seasons/2025/events/monaco-grand-prix/sessions/race",
        "/api/v1/seasons/2025/events/italian-grand-prix/sessions/qualifying",
    ],
    ids=["unsupported-year", "unsupported-event", "unsupported-session"],
)
def test_unsupported_session_returns_404_without_loading_source(
    client, monkeypatch, url: str
) -> None:
    loader = Mock(return_value=CONTROL_SESSION_RESPONSE)
    install_loader(monkeypatch, loader)

    response = client.get(url)

    assert response.status_code == 404
    error_response = ErrorResponse.model_validate(response.json())
    assert error_response.error.code == "session_not_supported"
    assert error_response.error.message == "The requested session is not supported."
    loader.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/seasons/not-a-year/events/italian-grand-prix/sessions/race",
        "/api/v1/seasons/1949/events/italian-grand-prix/sessions/race",
        "/api/v1/seasons/2025/events/Italian-Grand-Prix/sessions/race",
        "/api/v1/seasons/2025/events/italian-grand-prix/sessions/Race",
    ],
    ids=[
        "non-integer-year",
        "year-before-minimum",
        "malformed-event-slug",
        "malformed-session-slug",
    ],
)
def test_malformed_session_path_returns_422_without_loading_source(
    client, monkeypatch, url: str
) -> None:
    loader = Mock(return_value=CONTROL_SESSION_RESPONSE)
    install_loader(monkeypatch, loader)

    response = client.get(url)

    assert response.status_code == 422
    assert isinstance(response.json().get("detail"), list)
    loader.assert_not_called()
