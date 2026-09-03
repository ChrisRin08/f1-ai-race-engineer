import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, call

import fastf1
import numpy as np
import pandas as pd
import pytest
from fastf1.exceptions import DataNotLoadedError, RateLimitExceededError
from pydantic import ValidationError

from app.models import SessionTiming

CONTROL_SOURCE_IDENTIFIERS = (2025, "Italian Grand Prix", "Race")


def test_routine_tests_block_uncontrolled_fastf1_session_access() -> None:
    with pytest.raises(
        AssertionError,
        match="Routine tests must not access the real FastF1 session source",
    ):
        fastf1.get_session(*CONTROL_SOURCE_IDENTIFIERS)


def load_mapping_boundary():
    from app.f1_data import DataSourceUnavailableError, map_session_summary

    return DataSourceUnavailableError, map_session_summary


def make_session(
    *,
    event_name: object = "Italian Grand Prix",
    event_year: object = 2025,
    round_number: object = 16,
    country: object = "Italy",
    location: object = "Monza",
    session_date: object = pd.Timestamp("2025-09-07 13:00:00"),
    circuit_short_name: object = "Monza",
    results: pd.DataFrame | None = None,
    laps: pd.DataFrame | None = None,
    total_laps: object = 53,
) -> SimpleNamespace:
    if results is None:
        results = pd.DataFrame(
            [
                {
                    "Position": 1.0,
                    "DriverNumber": "1",
                    "Abbreviation": "VER",
                    "FullName": "Max Verstappen",
                    "TeamName": "Red Bull Racing",
                },
                {
                    "Position": 2.0,
                    "DriverNumber": "4",
                    "Abbreviation": "NOR",
                    "FullName": "Lando Norris",
                    "TeamName": "McLaren",
                },
            ]
        )
    if laps is None:
        laps = pd.DataFrame([{"LapNumber": 1.0}])

    circuit = {}
    if circuit_short_name is not None:
        circuit["ShortName"] = circuit_short_name

    event = pd.Series(
        {
            "EventName": event_name,
            "RoundNumber": round_number,
            "Country": country,
            "Location": location,
        }
    )
    event.year = event_year

    return SimpleNamespace(
        event=event,
        name="Race",
        date=session_date,
        session_info={"Meeting": {"Circuit": circuit}},
        results=results,
        laps=laps,
        total_laps=total_laps,
    )


def test_session_timing_accepts_utc_datetime() -> None:
    scheduled_start = datetime(2025, 9, 7, 13, 0, tzinfo=timezone.utc)

    timing = SessionTiming(scheduled_start_utc=scheduled_start, total_laps=53)

    assert timing.scheduled_start_utc == scheduled_start


def test_session_timing_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        SessionTiming(scheduled_start_utc=datetime(2025, 9, 7, 13, 0), total_laps=53)


def test_session_timing_rejects_non_utc_offset() -> None:
    non_utc_timezone = timezone(timedelta(hours=2))

    with pytest.raises(ValidationError):
        SessionTiming(
            scheduled_start_utc=datetime(2025, 9, 7, 15, 0, tzinfo=non_utc_timezone),
            total_laps=53,
        )


def test_session_timing_serializes_utc_datetime() -> None:
    timing = SessionTiming(
        scheduled_start_utc=datetime(2025, 9, 7, 13, 0, tzinfo=timezone.utc),
        total_laps=53,
    )

    assert timing.model_dump_json() == (
        '{"scheduled_start_utc":"2025-09-07T13:00:00Z","total_laps":53}'
    )


def test_map_session_summary_normalizes_source_timestamp_to_utc() -> None:
    _, map_session_summary = load_mapping_boundary()

    summary = map_session_summary(make_session())

    assert summary.timing.scheduled_start_utc == datetime(
        2025, 9, 7, 13, 0, tzinfo=timezone.utc
    )
    assert '"scheduled_start_utc":"2025-09-07T13:00:00Z"' in summary.model_dump_json()


def test_map_session_summary_converts_aware_source_timestamp_to_utc() -> None:
    _, map_session_summary = load_mapping_boundary()
    source_timezone = timezone(timedelta(hours=2))

    summary = map_session_summary(
        make_session(session_date=datetime(2025, 9, 7, 15, 0, tzinfo=source_timezone))
    )

    assert summary.timing.scheduled_start_utc == datetime(
        2025, 9, 7, 13, 0, tzinfo=timezone.utc
    )


def test_map_session_summary_preserves_source_event_year() -> None:
    _, map_session_summary = load_mapping_boundary()

    summary = map_session_summary(make_session(event_year=2024))

    assert summary.year == 2024


def test_map_session_summary_preserves_nullable_source_values() -> None:
    _, map_session_summary = load_mapping_boundary()

    results = pd.DataFrame(
        [
            {
                "Position": np.nan,
                "DriverNumber": "27",
                "Abbreviation": pd.NA,
                "FullName": pd.NA,
                "TeamName": pd.NA,
            }
        ]
    )

    summary = map_session_summary(
        make_session(
            round_number=np.nan,
            country=pd.NA,
            location=pd.NA,
            circuit_short_name="Monza",
            results=results,
            total_laps=np.nan,
        )
    )

    assert summary.event.round_number is None
    assert summary.event.country is None
    assert summary.event.location is None
    assert summary.timing.total_laps is None
    assert summary.participants[0].position is None
    assert summary.participants[0].abbreviation is None
    assert summary.participants[0].full_name is None
    assert summary.participants[0].team_name is None


@pytest.mark.parametrize("total_laps", [0, -1], ids=["zero", "negative"])
def test_map_session_summary_rejects_non_positive_total_laps(total_laps: int) -> None:
    DataSourceUnavailableError, map_session_summary = load_mapping_boundary()

    with pytest.raises(DataSourceUnavailableError):
        map_session_summary(make_session(total_laps=total_laps))


def test_map_session_summary_orders_classified_then_unclassified_stably() -> None:
    _, map_session_summary = load_mapping_boundary()

    results = pd.DataFrame(
        [
            {"Position": np.nan, "DriverNumber": "99"},
            {"Position": 2.0, "DriverNumber": "44"},
            {"Position": 1.0, "DriverNumber": "1"},
            {"Position": np.nan, "DriverNumber": "22"},
        ]
    )

    summary = map_session_summary(make_session(results=results))

    assert [participant.driver_number for participant in summary.participants] == [
        "1",
        "44",
        "99",
        "22",
    ]


def test_map_session_summary_prefers_circuit_short_name() -> None:
    _, map_session_summary = load_mapping_boundary()

    summary = map_session_summary(
        make_session(
            location="Monza event location", circuit_short_name="Monza circuit"
        )
    )

    assert summary.circuit.name == "Monza circuit"


def test_map_session_summary_falls_back_to_event_location() -> None:
    _, map_session_summary = load_mapping_boundary()

    summary = map_session_summary(
        make_session(location="Monza", circuit_short_name=None)
    )

    assert summary.circuit.name == "Monza"


@pytest.mark.parametrize(
    "overrides",
    [
        {"event_name": pd.NA},
        {"session_date": pd.NaT},
        {"location": pd.NA, "circuit_short_name": None},
        {"results": pd.DataFrame()},
    ],
    ids=[
        "missing-event-name",
        "missing-session-date",
        "missing-circuit",
        "missing-results",
    ],
)
def test_map_session_summary_rejects_missing_required_data(
    overrides: dict[str, object],
) -> None:
    DataSourceUnavailableError, map_session_summary = load_mapping_boundary()

    with pytest.raises(DataSourceUnavailableError):
        map_session_summary(make_session(**overrides))


def test_map_session_summary_maps_data_availability_statuses() -> None:
    _, map_session_summary = load_mapping_boundary()

    session = make_session(laps=pd.DataFrame())
    session.session_info = {}

    summary = map_session_summary(session)

    assert summary.data_availability.model_dump() == {
        "session_info": "unavailable",
        "results": "available",
        "laps": "unavailable",
        "telemetry": "not_requested",
        "weather": "not_requested",
        "race_control_messages": "not_requested",
    }


@pytest.fixture
def isolated_loader(monkeypatch, tmp_path):
    import app.f1_data as f1_data

    cache_enable = Mock()
    f1_data._configure_fastf1_cache.cache_clear()
    monkeypatch.setattr(f1_data, "FASTF1_CACHE_DIR", tmp_path / "fastf1")
    monkeypatch.setattr(f1_data.fastf1.Cache, "enable_cache", cache_enable)

    yield SimpleNamespace(module=f1_data, cache_enable=cache_enable)

    f1_data._configure_fastf1_cache.cache_clear()


def test_load_session_summary_configures_cache_once_and_loads_requested_session(
    isolated_loader, monkeypatch
) -> None:
    f1_data = isolated_loader.module
    source_identifiers = (2024, "Monaco Grand Prix", "Qualifying")
    session = make_session()
    session.load = Mock()
    get_session = Mock(return_value=session)
    expected_summary = object()
    map_session = Mock(return_value=expected_summary)
    monkeypatch.setattr(f1_data.fastf1, "get_session", get_session)
    monkeypatch.setattr(f1_data, "map_session_summary", map_session)

    summaries = [f1_data.load_session_summary(*source_identifiers) for _ in range(2)]

    assert summaries == [expected_summary, expected_summary]
    isolated_loader.cache_enable.assert_called_once_with(str(f1_data.FASTF1_CACHE_DIR))
    assert f1_data.FASTF1_CACHE_DIR.is_dir()
    assert get_session.call_args_list == [
        call(2024, "Monaco Grand Prix", "Qualifying"),
        call(2024, "Monaco Grand Prix", "Qualifying"),
    ]
    assert session.load.call_args_list == [
        call(laps=True, telemetry=False, weather=False, messages=False),
        call(laps=True, telemetry=False, weather=False, messages=False),
    ]
    assert map_session.call_args_list == [call(session), call(session)]


@pytest.mark.parametrize(
    "cache_error",
    [
        OSError("controlled filesystem failure"),
        sqlite3.Error("controlled database failure"),
    ],
    ids=["os-error", "sqlite-error"],
)
def test_load_session_summary_retries_cache_configuration_after_failure(
    isolated_loader, monkeypatch, cache_error
) -> None:
    f1_data = isolated_loader.module
    session = make_session()
    session.load = Mock()
    enable_cache = Mock(side_effect=[cache_error, None])
    monkeypatch.setattr(f1_data.fastf1.Cache, "enable_cache", enable_cache)
    monkeypatch.setattr(f1_data.fastf1, "get_session", Mock(return_value=session))
    monkeypatch.setattr(f1_data, "map_session_summary", Mock(return_value=object()))

    with pytest.raises(f1_data.DataSourceUnavailableError):
        f1_data.load_session_summary(*CONTROL_SOURCE_IDENTIFIERS)

    f1_data.load_session_summary(*CONTROL_SOURCE_IDENTIFIERS)

    assert enable_cache.call_count == 2


@pytest.mark.parametrize(
    "source_error",
    [
        ValueError("controlled resolution failure"),
        RateLimitExceededError("controlled rate limit"),
        SystemExit(),
    ],
    ids=["value-error", "rate-limit-exceeded", "system-exit"],
)
def test_load_session_summary_translates_session_resolution_failure(
    isolated_loader, monkeypatch, source_error
) -> None:
    f1_data = isolated_loader.module
    monkeypatch.setattr(f1_data.fastf1, "get_session", Mock(side_effect=source_error))

    with pytest.raises(f1_data.DataSourceUnavailableError):
        f1_data.load_session_summary(*CONTROL_SOURCE_IDENTIFIERS)


@pytest.mark.parametrize(
    "source_error",
    [
        DataNotLoadedError("controlled missing data"),
        RateLimitExceededError("controlled rate limit"),
        SystemExit(),
    ],
    ids=["data-not-loaded", "rate-limit-exceeded", "system-exit"],
)
def test_load_session_summary_translates_session_load_failure(
    isolated_loader, monkeypatch, source_error
) -> None:
    f1_data = isolated_loader.module
    session = make_session()
    session.load = Mock(side_effect=source_error)
    monkeypatch.setattr(f1_data.fastf1, "get_session", Mock(return_value=session))
    map_session = Mock()
    monkeypatch.setattr(f1_data, "map_session_summary", map_session)

    with pytest.raises(f1_data.DataSourceUnavailableError):
        f1_data.load_session_summary(*CONTROL_SOURCE_IDENTIFIERS)

    map_session.assert_not_called()


def test_load_session_summary_does_not_translate_mapper_system_exit(
    isolated_loader, monkeypatch
) -> None:
    f1_data = isolated_loader.module
    session = make_session()
    session.load = Mock()
    monkeypatch.setattr(f1_data.fastf1, "get_session", Mock(return_value=session))
    monkeypatch.setattr(f1_data, "map_session_summary", Mock(side_effect=SystemExit()))

    with pytest.raises(SystemExit):
        f1_data.load_session_summary(*CONTROL_SOURCE_IDENTIFIERS)
