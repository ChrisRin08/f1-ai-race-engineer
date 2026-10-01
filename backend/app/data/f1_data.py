import re
import sqlite3
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from functools import cache
from math import isfinite
from numbers import Real
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd
from fastf1.core import Session
from fastf1.exceptions import DataNotLoadedError, RateLimitExceededError

from app.analytics.lap_analytics import (
    MINIMUM_LAP_TIME_NS,
    DriverIdentity,
    SessionFieldInput,
    SourceLap,
)
from app.analytics.race_context_analytics import (
    EvidenceStatus,
    NormalizedTrackStatus,
    NormalizedTrackStatusEvidence,
    NormalizedValue,
    NormalizedValueState,
    RaceContextInput,
    RaceContextLapRowInput,
    RaceContextParticipantIdentity,
    RaceContextParticipantInput,
    TrackStatusAvailability,
)
from app.models.session_models import (
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

FASTF1_CACHE_DIR = Path(__file__).resolve().parents[2] / "cache" / "fastf1"

_RACE_CONTEXT_RESULT_COLUMNS = frozenset(
    {
        "DriverNumber",
        "Abbreviation",
        "FullName",
        "TeamName",
        "Position",
        "ClassifiedPosition",
        "Status",
        "Laps",
    }
)
_RACE_CONTEXT_LAP_COLUMNS = frozenset(
    {
        "DriverNumber",
        "LapNumber",
        "Time",
        "Position",
        "PitInTime",
        "PitOutTime",
        "TrackStatus",
        "FastF1Generated",
        "Compound",
        "Stint",
    }
)
_TRACK_STATUS_BY_CODE = {
    "1": NormalizedTrackStatus.GREEN,
    "2": NormalizedTrackStatus.YELLOW,
    "4": NormalizedTrackStatus.SAFETY_CAR,
    "5": NormalizedTrackStatus.RED_FLAG,
    "6": NormalizedTrackStatus.VIRTUAL_SAFETY_CAR,
    "7": NormalizedTrackStatus.VIRTUAL_SAFETY_CAR_ENDING,
}
_DISRUPTED_TRACK_STATUSES = frozenset(
    {
        NormalizedTrackStatus.YELLOW,
        NormalizedTrackStatus.SAFETY_CAR,
        NormalizedTrackStatus.RED_FLAG,
        NormalizedTrackStatus.VIRTUAL_SAFETY_CAR,
        NormalizedTrackStatus.VIRTUAL_SAFETY_CAR_ENDING,
    }
)


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
    return map_session_summary(load_session(year, event_name, session_name))


def load_session(year: int, event_name: str, session_name: str) -> Session:
    """Load one source snapshot with shared cache and expected-error handling."""
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

    return session


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


def map_lap_inputs(session: Session) -> SessionFieldInput:
    """Normalize one snapshot without dropping rows or inventing timing facts."""
    results = _required_results(session)
    participants = []
    numbers = set()
    for _, row in results.iterrows():
        number = _canonical_driver_number(row.get("DriverNumber"))
        if number in numbers:
            raise DataSourceUnavailableError("Duplicate result driver number.")
        numbers.add(number)
        participants.append(
            DriverIdentity(
                number,
                _optional_text(row.get("Abbreviation")),
                _optional_text(row.get("FullName")),
                _optional_text(row.get("TeamName")),
            )
        )

    table = _optional_loaded_value(session, "laps")
    required = {
        "DriverNumber",
        "LapNumber",
        "LapTime",
        "PitInTime",
        "PitOutTime",
        "TrackStatus",
    }
    if not isinstance(table, pd.DataFrame) or table.empty:
        raise DataSourceUnavailableError("Required session laps are unavailable.")
    if not required.issubset(table.columns):
        raise DataSourceUnavailableError("Required lap columns are unavailable.")
    consumed = required | {
        "IsAccurate",
        "Compound",
        "Stint",
        "TyreLife",
        "FastF1Generated",
    }
    duplicated_consumed = consumed.intersection(
        table.columns[table.columns.duplicated()].tolist()
    )
    if duplicated_consumed:
        raise DataSourceUnavailableError("Consumed lap columns are ambiguous.")

    laps = []
    for source_order, (_, row) in enumerate(table.iterrows(), 1):
        number = _canonical_driver_number(row["DriverNumber"])
        if number not in numbers:
            raise DataSourceUnavailableError("Lap has no matching participant.")
        accurate = _normalize_missing(row.get("IsAccurate"))
        generated = row.get("FastF1Generated")
        generated = (
            _normalize_missing(generated) if pd.api.types.is_scalar(generated) else None
        )
        laps.append(
            SourceLap(
                source_order=source_order,
                driver_number=number,
                lap_number=_lap_number(row["LapNumber"]),
                lap_time_ns=_lap_duration_ns(row["LapTime"]),
                pit_in=not bool(pd.isna(row["PitInTime"])),
                pit_out=not bool(pd.isna(row["PitOutTime"])),
                track_status_codes=_track_status_codes(row["TrackStatus"]),
                is_accurate=accurate if isinstance(accurate, bool) else None,
                compound=_optional_text(row.get("Compound")),
                stint=_positive_integer(row.get("Stint")),
                tyre_life=_positive_integer(row.get("TyreLife")),
                provider_generated=generated if isinstance(generated, bool) else None,
            )
        )
    if not any(
        lap.lap_number is not None and lap.lap_time_ns is not None for lap in laps
    ):
        raise DataSourceUnavailableError("No usable participant-linked lap timing.")
    return SessionFieldInput(tuple(participants), tuple(laps))


def map_race_context_inputs(session: Session) -> RaceContextInput:
    """Normalize one loaded public session snapshot for future pure analytics."""
    results = _required_results(session)
    if not isinstance(results, pd.DataFrame):
        raise DataSourceUnavailableError("Required session results are unavailable.")
    _reject_duplicate_consumed_columns(results, _RACE_CONTEXT_RESULT_COLUMNS)
    participants = _map_race_context_participants(results)

    laps = _optional_loaded_value(session, "laps")
    if not isinstance(laps, pd.DataFrame):
        raise DataSourceUnavailableError("Required session laps are unavailable.")
    _reject_duplicate_consumed_columns(laps, _RACE_CONTEXT_LAP_COLUMNS)
    rows, unassociated_count = _map_race_context_lap_rows(
        laps,
        frozenset(item.identity.driver_number for item in participants),
    )
    return RaceContextInput(participants, rows, unassociated_count)


def _map_race_context_participants(
    results: pd.DataFrame,
) -> tuple[RaceContextParticipantInput, ...]:
    grouped: dict[
        str,
        list[dict[str, tuple[NormalizedValueState, object | None]]],
    ] = {}
    for _, row in results.iterrows():
        driver_number = _normalized_authoritative_identity(row.get("DriverNumber"))
        if driver_number is None:
            raise DataSourceUnavailableError(
                "Invalid authoritative participant identity."
            )
        facts = {
            "abbreviation": _normalized_text_evidence(row.get("Abbreviation")),
            "full_name": _normalized_text_evidence(row.get("FullName")),
            "team_name": _normalized_text_evidence(row.get("TeamName")),
            "finish_position": _normalized_integer_fact(row.get("Position")),
            "classified_position": _normalized_text_evidence(
                row.get("ClassifiedPosition")
            ),
            "classification_status": _normalized_text_evidence(row.get("Status")),
            "completed_laps": _normalized_integer_fact(
                row.get("Laps"), allow_zero=True
            ),
        }
        grouped.setdefault(driver_number, []).append(facts)

    participants = []
    for driver_number, records in grouped.items():
        conflicts = {
            field: len({record[field] for record in records}) > 1
            for field in records[0]
        }
        has_conflict = any(conflicts.values())
        has_invalid = any(
            state is NormalizedValueState.INVALID
            for record in records
            for state, _ in record.values()
        )
        if has_conflict:
            evidence_status = EvidenceStatus.CONFLICTING
        elif has_invalid:
            evidence_status = EvidenceStatus.UNAVAILABLE
        else:
            evidence_status = EvidenceStatus.AVAILABLE

        def resolved(field: str) -> object | None:
            if conflicts[field]:
                return None
            return records[0][field][1]

        participants.append(
            RaceContextParticipantInput(
                identity=RaceContextParticipantIdentity(
                    driver_number=driver_number,
                    abbreviation=resolved("abbreviation"),
                    full_name=resolved("full_name"),
                    team_name=resolved("team_name"),
                ),
                result_evidence_count=len(records),
                result_evidence_status=evidence_status,
                finish_position=resolved("finish_position"),
                classified_position=resolved("classified_position"),
                classification_status=resolved("classification_status"),
                completed_laps=resolved("completed_laps"),
            )
        )
    return tuple(participants)


def _map_race_context_lap_rows(
    laps: pd.DataFrame,
    participant_numbers: frozenset[str],
) -> tuple[tuple[RaceContextLapRowInput, ...], int]:
    rows = []
    unassociated_count = 0
    for source_occurrence, (_, row) in enumerate(laps.iterrows(), 1):
        driver_number = _normalized_authoritative_identity(row.get("DriverNumber"))
        if driver_number not in participant_numbers:
            unassociated_count += 1
        rows.append(
            RaceContextLapRowInput(
                source_occurrence=source_occurrence,
                driver_number=driver_number,
                lap_number=_normalized_integer_evidence(row.get("LapNumber")),
                lap_completion_time_ns=_normalized_timestamp_evidence(row.get("Time")),
                lap_completion_position=_normalized_integer_evidence(
                    row.get("Position")
                ),
                pit_entry_time_ns=_normalized_timestamp_evidence(row.get("PitInTime")),
                pit_exit_time_ns=_normalized_timestamp_evidence(row.get("PitOutTime")),
                track_status=_normalized_track_status(row.get("TrackStatus")),
                provider_generated=_normalized_boolean(row.get("FastF1Generated")),
                reported_compound=_normalized_optional_text(row.get("Compound")),
                reported_stint=_normalized_optional_positive_integer(row.get("Stint")),
            )
        )
    return tuple(rows), unassociated_count


def _reject_duplicate_consumed_columns(
    table: pd.DataFrame, consumed: frozenset[str]
) -> None:
    duplicated = consumed.intersection(
        table.columns[table.columns.duplicated()].tolist()
    )
    if duplicated:
        raise DataSourceUnavailableError("Consumed provider columns are ambiguous.")


def _normalized_text_evidence(
    value: object,
) -> tuple[NormalizedValueState, str | None]:
    if _is_missing_provider_scalar(value):
        return NormalizedValueState.ABSENT, None
    normalized = _normalize_missing(value)
    if type(normalized) is not str:
        return NormalizedValueState.INVALID, None
    text = normalized.strip()
    if not text:
        return NormalizedValueState.ABSENT, None
    return NormalizedValueState.AVAILABLE, text


def _normalized_integer_fact(
    value: object, *, allow_zero: bool = False
) -> tuple[NormalizedValueState, int | None]:
    if _is_missing_provider_scalar(value):
        return NormalizedValueState.ABSENT, None
    normalized = _normalize_missing(value)
    minimum = 0 if allow_zero else 1
    if (
        isinstance(normalized, bool)
        or not isinstance(normalized, Real)
        or not isfinite(normalized)
        or normalized < minimum
        or int(normalized) != normalized
    ):
        return NormalizedValueState.INVALID, None
    return NormalizedValueState.AVAILABLE, int(normalized)


def _normalized_integer_evidence(
    value: object, *, allow_zero: bool = False
) -> NormalizedValue:
    state, normalized = _normalized_integer_fact(value, allow_zero=allow_zero)
    return NormalizedValue(state, normalized)


def _normalized_timestamp_evidence(value: object) -> NormalizedValue:
    if _is_missing_provider_scalar(value):
        return NormalizedValue(NormalizedValueState.ABSENT)
    if not isinstance(value, (pd.Timedelta, timedelta, np.timedelta64)):
        return NormalizedValue(NormalizedValueState.INVALID)
    try:
        nanoseconds = int(pd.Timedelta(value).value)
    except (TypeError, ValueError, OverflowError):
        return NormalizedValue(NormalizedValueState.INVALID)
    if nanoseconds < 0:
        return NormalizedValue(NormalizedValueState.INVALID)
    return NormalizedValue(NormalizedValueState.AVAILABLE, nanoseconds)


def _normalized_authoritative_identity(value: object) -> str | None:
    value = _normalize_missing(value)
    if type(value) is not str:
        return None
    identity = value.strip()
    return identity or None


def _normalized_boolean(value: object) -> bool | None:
    value = _normalize_missing(value)
    return value if type(value) is bool else None


def _normalized_optional_text(value: object) -> str | None:
    state, normalized = _normalized_text_evidence(value)
    if state is not NormalizedValueState.AVAILABLE:
        return None
    return normalized


def _normalized_optional_positive_integer(value: object) -> int | None:
    state, normalized = _normalized_integer_fact(value)
    if state is not NormalizedValueState.AVAILABLE:
        return None
    return normalized


def _normalized_track_status(value: object) -> NormalizedTrackStatusEvidence:
    if _is_missing_provider_scalar(value):
        return NormalizedTrackStatusEvidence(
            TrackStatusAvailability.UNAVAILABLE,
            (),
            None,
        )
    value = _normalize_missing(value)
    if type(value) is not str or re.fullmatch(r"[0-9]+", value) is None:
        return NormalizedTrackStatusEvidence(
            TrackStatusAvailability.UNAVAILABLE,
            (),
            None,
        )

    statuses = tuple(
        dict.fromkeys(
            _TRACK_STATUS_BY_CODE.get(code, NormalizedTrackStatus.UNKNOWN)
            for code in value
        )
    )
    if any(status in _DISRUPTED_TRACK_STATUSES for status in statuses):
        is_disrupted = True
    elif NormalizedTrackStatus.UNKNOWN in statuses:
        is_disrupted = None
    else:
        is_disrupted = False
    return NormalizedTrackStatusEvidence(
        TrackStatusAvailability.AVAILABLE,
        statuses,
        is_disrupted,
    )


def _is_missing_provider_scalar(value: object) -> bool:
    if value is None:
        return True
    if not pd.api.types.is_scalar(value):
        return False
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return type(missing) in {bool, np.bool_} and bool(missing)


def _canonical_driver_number(value: object) -> str:
    value = _normalize_missing(value)
    if not isinstance(value, str) or re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise DataSourceUnavailableError("Invalid source driver number.")
    return value


def _lap_duration_ns(value: object) -> int | None:
    if not isinstance(value, (pd.Timedelta, timedelta)) or pd.isna(value):
        return None
    try:
        nanoseconds = pd.Timedelta(value).value
    except (ValueError, OverflowError):
        return None
    return nanoseconds if nanoseconds >= MINIMUM_LAP_TIME_NS else None


def _positive_integer(value: object) -> int | None:
    if not pd.api.types.is_scalar(value):
        return None
    return _lap_number(value)


def _lap_number(value: object) -> int | None:
    value = _normalize_missing(value)
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    if not isfinite(value) or value <= 0 or int(value) != value:
        return None
    return int(value)


def _track_status_codes(value: object) -> tuple[str, ...] | None:
    text = _optional_text(value)
    if text is None:
        return None
    if re.fullmatch(r"[0-9]+", text) is None:
        raise DataSourceUnavailableError("Malformed source track status.")
    return tuple(dict.fromkeys(text))


def _normalize_missing(value: object) -> object | None:
    if value is None:
        return None

    missing = pd.isna(value)
    try:
        if bool(missing):
            return None
    except ValueError:
        pass

    if isinstance(value, (np.ndarray, pd.Series)) and value.size != 1:
        return value
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    return value


def _optional_text(value: object) -> str | None:
    value = _normalize_missing(value)
    if value is None:
        return None
    if isinstance(value, (np.ndarray, pd.Series)):
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
