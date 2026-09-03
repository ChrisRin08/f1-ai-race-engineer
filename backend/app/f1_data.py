import sqlite3
from collections.abc import Mapping
from datetime import datetime, timezone
from functools import cache
from pathlib import Path

import fastf1
import pandas as pd
from fastf1.core import Session
from fastf1.exceptions import DataNotLoadedError, RateLimitExceededError

from app.models import (
    AvailabilityStatus,
    CircuitSummary,
    DataAvailability,
    EventSummary,
    Participant,
    SessionIdentity,
    SessionSummary,
    SessionTiming,
    SourceProvenance,
)

FASTF1_CACHE_DIR = Path(__file__).resolve().parents[1] / "cache" / "fastf1"


class DataSourceUnavailableError(RuntimeError):
    """Raised when the required FastF1 source data cannot be provided."""


@cache
def _configure_fastf1_cache() -> None:
    FASTF1_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(FASTF1_CACHE_DIR))


def load_session_summary(
    year: int,
    event_name: str,
    session_name: str,
) -> SessionSummary:
    try:
        _configure_fastf1_cache()
    except (OSError, sqlite3.Error) as exc:
        raise DataSourceUnavailableError(
            "Formula 1 data cache is unavailable."
        ) from exc

    try:
        session = fastf1.get_session(year, event_name, session_name)
    except SystemExit as exc:
        raise DataSourceUnavailableError(
            "Formula 1 session data is unavailable."
        ) from exc
    except (ValueError, RateLimitExceededError) as exc:
        raise DataSourceUnavailableError(
            "Formula 1 session data is unavailable."
        ) from exc

    try:
        session.load(
            laps=True,
            telemetry=False,
            weather=False,
            messages=False,
        )
    except SystemExit as exc:
        raise DataSourceUnavailableError(
            "Formula 1 session data is unavailable."
        ) from exc
    except (DataNotLoadedError, RateLimitExceededError) as exc:
        raise DataSourceUnavailableError(
            "Formula 1 session data is unavailable."
        ) from exc

    return map_session_summary(session)


def map_session_summary(session: Session) -> SessionSummary:
    event = session.event
    session_info = _optional_loaded_value(session, "session_info")
    results = _required_results(session)
    laps = _optional_loaded_value(session, "laps")

    event_name = _required_text(event.get("EventName"), "event name")
    event_location = _optional_text(event.get("Location"))
    circuit_name = _circuit_name(session_info) or event_location
    if circuit_name is None:
        raise DataSourceUnavailableError("Required circuit data is unavailable.")

    year = _normalize_missing(getattr(event, "year", None))
    if year is None:
        raise DataSourceUnavailableError("Required event year is unavailable.")

    session_name = _required_text(session.name, "session name")
    participants = _map_participants(results)

    return SessionSummary(
        year=year,
        event=EventSummary(
            name=event_name,
            round_number=_normalize_missing(event.get("RoundNumber")),
            country=_optional_text(event.get("Country")),
            location=event_location,
        ),
        session=SessionIdentity(name=session_name, type="race"),
        circuit=CircuitSummary(name=circuit_name),
        timing=SessionTiming(
            scheduled_start_utc=_normalize_utc_timestamp(session.date),
            total_laps=_map_total_laps(session),
        ),
        participants=participants,
        data_availability=DataAvailability(
            session_info=_availability_for_mapping(session_info),
            results=AvailabilityStatus.AVAILABLE,
            laps=_availability_for_table(laps),
            telemetry=AvailabilityStatus.NOT_REQUESTED,
            weather=AvailabilityStatus.NOT_REQUESTED,
            race_control_messages=AvailabilityStatus.NOT_REQUESTED,
        ),
        source=SourceProvenance(provider="FastF1"),
    )


def _normalize_missing(value: object) -> object | None:
    if value is None:
        return None

    missing = pd.isna(value)
    try:
        if bool(missing):
            return None
    except ValueError:
        pass

    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return value


def _optional_text(value: object) -> str | None:
    value = _normalize_missing(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise DataSourceUnavailableError(f"Required {field_name} is unavailable.")
    return text


def _normalize_utc_timestamp(value: object) -> datetime:
    value = _normalize_missing(value)
    if value is None:
        raise DataSourceUnavailableError("Required session date is unavailable.")

    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    else:
        timestamp = timestamp.tz_convert(timezone.utc)
    return timestamp.to_pydatetime()


def _optional_loaded_value(session: Session, attribute: str) -> object | None:
    try:
        return getattr(session, attribute)
    except DataNotLoadedError:
        return None


def _map_total_laps(session: Session) -> object | None:
    total_laps = _normalize_missing(_optional_loaded_value(session, "total_laps"))
    if total_laps is not None and total_laps <= 0:
        raise DataSourceUnavailableError("Source total lap count is invalid.")
    return total_laps


def _required_results(session: Session) -> pd.DataFrame:
    try:
        results = session.results
    except DataNotLoadedError as exc:
        raise DataSourceUnavailableError(
            "Required session results are unavailable."
        ) from exc

    if results is None or results.empty:
        raise DataSourceUnavailableError("Required session results are unavailable.")
    return results


def _circuit_name(session_info: object | None) -> str | None:
    if not isinstance(session_info, Mapping):
        return None
    meeting = session_info.get("Meeting")
    if not isinstance(meeting, Mapping):
        return None
    circuit = meeting.get("Circuit")
    if not isinstance(circuit, Mapping):
        return None
    return _optional_text(circuit.get("ShortName"))


def _map_participants(results: pd.DataFrame) -> list[Participant]:
    ordered_participants: list[tuple[tuple[bool, float, int], Participant]] = []

    for source_order, (_, row) in enumerate(results.iterrows()):
        position = _normalize_missing(row.get("Position"))
        participant = Participant(
            position=position,
            driver_number=_required_text(row.get("DriverNumber"), "driver number"),
            abbreviation=_optional_text(row.get("Abbreviation")),
            full_name=_optional_text(row.get("FullName")),
            team_name=_optional_text(row.get("TeamName")),
        )
        sort_position = float(position) if position is not None else 0.0
        sort_key = (position is None, sort_position, source_order)
        ordered_participants.append((sort_key, participant))

    ordered_participants.sort(key=lambda item: item[0])
    return [participant for _, participant in ordered_participants]


def _availability_for_mapping(value: object | None) -> AvailabilityStatus:
    if isinstance(value, Mapping) and value:
        return AvailabilityStatus.AVAILABLE
    return AvailabilityStatus.UNAVAILABLE


def _availability_for_table(value: object | None) -> AvailabilityStatus:
    if isinstance(value, pd.DataFrame) and not value.empty:
        return AvailabilityStatus.AVAILABLE
    return AvailabilityStatus.UNAVAILABLE
