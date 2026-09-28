"""Application-owned immutable inputs for deterministic race-context analysis."""

from dataclasses import dataclass
from enum import StrEnum


class NormalizedValueState(StrEnum):
    AVAILABLE = "available"
    ABSENT = "absent"
    INVALID = "invalid"


class EvidenceStatus(StrEnum):
    AVAILABLE = "available"
    CONFLICTING = "conflicting"
    UNAVAILABLE = "unavailable"


class TrackStatusAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class NormalizedTrackStatus(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    SAFETY_CAR = "safety_car"
    VIRTUAL_SAFETY_CAR = "virtual_safety_car"
    VIRTUAL_SAFETY_CAR_ENDING = "virtual_safety_car_ending"
    RED_FLAG = "red_flag"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NormalizedValue:
    state: NormalizedValueState
    value: int | None = None

    def __post_init__(self) -> None:
        if self.state is NormalizedValueState.AVAILABLE and type(self.value) is not int:
            raise ValueError("Available normalized evidence requires a Python integer.")
        if self.state is not NormalizedValueState.AVAILABLE and self.value is not None:
            raise ValueError("Unavailable normalized evidence cannot carry a value.")


@dataclass(frozen=True)
class RaceContextParticipantIdentity:
    driver_number: str
    abbreviation: str | None = None
    full_name: str | None = None
    team_name: str | None = None

    def __post_init__(self) -> None:
        if type(self.driver_number) is not str or not self.driver_number:
            raise ValueError("Participant identity requires a driver number.")
        for value in (self.abbreviation, self.full_name, self.team_name):
            if value is not None and (type(value) is not str or not value):
                raise ValueError("Participant identity text must be normalized.")


@dataclass(frozen=True)
class RaceContextParticipantInput:
    identity: RaceContextParticipantIdentity
    result_evidence_count: int
    result_evidence_status: EvidenceStatus
    finish_position: int | None
    classified_position: str | None
    classification_status: str | None
    completed_laps: int | None

    def __post_init__(self) -> None:
        if (
            type(self.result_evidence_count) is not int
            or self.result_evidence_count <= 0
        ):
            raise ValueError("Result evidence count must be a positive integer.")
        if self.finish_position is not None and (
            type(self.finish_position) is not int or self.finish_position <= 0
        ):
            raise ValueError("Finish position must be normalized or None.")
        if self.completed_laps is not None and (
            type(self.completed_laps) is not int or self.completed_laps < 0
        ):
            raise ValueError("Completed laps must be normalized or None.")
        for value in (self.classified_position, self.classification_status):
            if value is not None and (type(value) is not str or not value):
                raise ValueError("Classification text must be normalized.")


@dataclass(frozen=True)
class NormalizedTrackStatusEvidence:
    availability: TrackStatusAvailability
    statuses: tuple[NormalizedTrackStatus, ...]
    is_disrupted: bool | None

    def __post_init__(self) -> None:
        if len(set(self.statuses)) != len(self.statuses):
            raise ValueError("Normalized track statuses must be unique.")
        if self.availability is TrackStatusAvailability.UNAVAILABLE and (
            self.statuses or self.is_disrupted is not None
        ):
            raise ValueError("Unavailable track status cannot carry evidence.")
        if self.availability is TrackStatusAvailability.AVAILABLE and not self.statuses:
            raise ValueError("Available track status requires normalized evidence.")
        if self.is_disrupted is not None and type(self.is_disrupted) is not bool:
            raise ValueError("Track disruption state must be a boolean or None.")


@dataclass(frozen=True)
class RaceContextLapRowInput:
    source_occurrence: int
    driver_number: str | None
    lap_number: NormalizedValue
    lap_completion_time_ns: NormalizedValue
    lap_completion_position: NormalizedValue
    pit_entry_time_ns: NormalizedValue
    pit_exit_time_ns: NormalizedValue
    track_status: NormalizedTrackStatusEvidence
    provider_generated: bool | None
    reported_compound: str | None
    reported_stint: int | None

    def __post_init__(self) -> None:
        if type(self.source_occurrence) is not int or self.source_occurrence <= 0:
            raise ValueError("Source occurrence must be a positive integer.")
        if self.driver_number is not None and (
            type(self.driver_number) is not str or not self.driver_number
        ):
            raise ValueError("Lap-row driver number must be normalized or None.")
        for field_name, evidence, minimum in (
            ("Lap number", self.lap_number, 1),
            ("Lap completion time", self.lap_completion_time_ns, 0),
            ("Lap completion position", self.lap_completion_position, 1),
            ("Pit entry time", self.pit_entry_time_ns, 0),
            ("Pit exit time", self.pit_exit_time_ns, 0),
        ):
            if (
                evidence.state is NormalizedValueState.AVAILABLE
                and evidence.value is not None
                and evidence.value < minimum
            ):
                raise ValueError(f"{field_name} must be at least {minimum}.")
        if self.provider_generated is not None and (
            type(self.provider_generated) is not bool
        ):
            raise ValueError("Generated state must be a boolean or None.")
        if self.reported_compound is not None and (
            type(self.reported_compound) is not str or not self.reported_compound
        ):
            raise ValueError("Reported compound must be normalized or None.")
        if self.reported_stint is not None and (
            type(self.reported_stint) is not int or self.reported_stint <= 0
        ):
            raise ValueError("Reported stint must be normalized or None.")


@dataclass(frozen=True)
class RaceContextInput:
    participants: tuple[RaceContextParticipantInput, ...]
    lap_rows: tuple[RaceContextLapRowInput, ...]
    unassociated_row_count: int

    def __post_init__(self) -> None:
        if (
            type(self.unassociated_row_count) is not int
            or self.unassociated_row_count < 0
        ):
            raise ValueError("Unassociated row count must be non-negative.")
