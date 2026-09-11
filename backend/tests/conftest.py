from collections.abc import Generator
from types import SimpleNamespace

import fastf1
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def pace_session_factory():
    """Build provider-shaped data without loading FastF1 or touching its cache."""

    def make_session(*, laps=None, results=None):
        if results is None:
            results = pd.DataFrame(
                [
                    {"DriverNumber": number, "Position": position}
                    for position, number in enumerate(("1", "4", "27"), 1)
                ]
            )
        if laps is None:
            laps = pd.DataFrame(
                [
                    {
                        "DriverNumber": number,
                        "LapNumber": float(lap),
                        "LapTime": pd.Timedelta(seconds * 1_000_000_000, unit="ns"),
                        "PitInTime": pd.NaT,
                        "PitOutTime": pd.NaT,
                        "TrackStatus": "1",
                        "IsAccurate": True,
                        "Compound": "MEDIUM",
                    }
                    for number, seconds in (("1", 90), ("4", 91))
                    for lap in range(1, 7)
                ]
            )
            for column in ("PitInTime", "PitOutTime"):
                laps[column] = pd.Series(
                    pd.NaT, index=laps.index, dtype="timedelta64[ns]"
                )
        event = pd.Series(
            {
                "EventName": "Italian Grand Prix",
                "Location": "Monza",
                "Country": "Italy",
                "RoundNumber": 16,
            }
        )
        event.year = 2025
        return SimpleNamespace(
            event=event,
            name="Race",
            results=results,
            laps=laps,
            date=pd.Timestamp("2025-09-07 13:00:00"),
            session_info={},
            total_laps=53,
        )

    return make_session


@pytest.fixture(autouse=True)
def block_external_fastf1_session_source(request, monkeypatch) -> None:
    if request.node.get_closest_marker("integration") is not None:
        return

    def fail_on_external_session_access(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(
            "Routine tests must not access the real FastF1 session source."
        )

    monkeypatch.setattr(fastf1, "get_session", fail_on_external_session_access)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session_summary_fixture() -> dict[str, object]:
    return {
        "year": 2025,
        "event": {
            "name": "Italian Grand Prix",
            "round_number": 16,
            "country": "Italy",
            "location": "Monza",
        },
        "session": {"name": "Race", "type": "race"},
        "circuit": {"name": "Monza"},
        "timing": {
            "scheduled_start_utc": "2025-09-07T13:00:00Z",
            "total_laps": 53,
        },
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
