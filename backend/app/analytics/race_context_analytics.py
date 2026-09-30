"""Application-owned inputs and pure deterministic race-context analytics."""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TypeVar


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


class RaceContextAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class EqualDistanceTimeDeficitStatus(StrEnum):
    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


class PitBoundaryKind(StrEnum):
    ENTRY = "entry"
    EXIT = "exit"


class PitEvidenceState(StrEnum):
    COMPLETE = "complete"
    UNPAIRED_ENTRY = "unpaired_entry"
    UNPAIRED_EXIT = "unpaired_exit"
    CONFLICTING = "conflicting"
    UNAVAILABLE = "unavailable"


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


@dataclass(frozen=True)
class LeaderReference:
    driver_number: str
    lap_number: int
    completion_time_ns: int
    completion_time_ms: int

    def __post_init__(self) -> None:
        if type(self.driver_number) is not str or not self.driver_number:
            raise ValueError("Leader reference requires a driver identity.")
        if type(self.lap_number) is not int or self.lap_number <= 0:
            raise ValueError("Leader reference requires a positive lap number.")
        for value in (self.completion_time_ns, self.completion_time_ms):
            if type(value) is not int or value < 0:
                raise ValueError("Leader reference timing must be non-negative.")


@dataclass(frozen=True)
class LapContextReference:
    driver_number: str
    lap_number: int

    def __post_init__(self) -> None:
        if type(self.driver_number) is not str or not self.driver_number:
            raise ValueError("Lap-context reference requires a driver identity.")
        if type(self.lap_number) is not int or self.lap_number <= 0:
            raise ValueError("Lap-context reference requires a positive lap number.")


@dataclass(frozen=True)
class PitBoundary:
    kind: PitBoundaryKind
    evidence_status: EvidenceStatus
    source_evidence_count: int
    lap_number: int | None
    session_time_ns: int | None
    session_time_ms: int | None
    lap_context_reference: LapContextReference | None

    def __post_init__(self) -> None:
        if (
            type(self.source_evidence_count) is not int
            or self.source_evidence_count <= 0
        ):
            raise ValueError("Pit boundary requires source evidence.")
        if self.lap_number is not None and (
            type(self.lap_number) is not int or self.lap_number <= 0
        ):
            raise ValueError("Pit boundary lap number must be positive or None.")
        if (self.session_time_ns is None) != (self.session_time_ms is None):
            raise ValueError("Exact and published pit-boundary timing must be paired.")
        for value in (self.session_time_ns, self.session_time_ms):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Pit-boundary timing must be non-negative.")
        if self.evidence_status is EvidenceStatus.AVAILABLE and (
            self.lap_number is None or self.session_time_ns is None
        ):
            raise ValueError("Available pit boundary requires lap and timing evidence.")
        if (
            self.lap_context_reference is not None
            and self.lap_context_reference.lap_number != self.lap_number
        ):
            raise ValueError("Pit boundary must reference its own lap context.")


@dataclass(frozen=True)
class PitTransitionContext:
    availability: EvidenceStatus
    lap_context_reference: LapContextReference | None
    reported_compound: str | None
    reported_stint: int | None

    def __post_init__(self) -> None:
        if self.reported_compound is not None and (
            type(self.reported_compound) is not str or not self.reported_compound
        ):
            raise ValueError("Reported transition compound must be normalized or None.")
        if self.reported_stint is not None and (
            type(self.reported_stint) is not int or self.reported_stint <= 0
        ):
            raise ValueError("Reported transition stint must be positive or None.")


@dataclass(frozen=True)
class PitLaneEvidence:
    state: PitEvidenceState
    boundaries: tuple[PitBoundary, ...]
    source_boundary_count: int
    entry_lap_number: int | None
    exit_lap_number: int | None
    entry_session_time_ns: int | None
    entry_session_time_ms: int | None
    exit_session_time_ns: int | None
    exit_session_time_ms: int | None
    entry_to_exit_elapsed_ns: int | None
    entry_to_exit_elapsed_ms: int | None
    entry_context: PitTransitionContext | None
    exit_context: PitTransitionContext | None
    reported_compound_changed: bool | None
    reported_stint_changed: bool | None

    def __post_init__(self) -> None:
        if (
            type(self.source_boundary_count) is not int
            or self.source_boundary_count <= 0
        ):
            raise ValueError("Pit-lane evidence requires source boundaries.")
        if self.source_boundary_count != sum(
            boundary.source_evidence_count for boundary in self.boundaries
        ):
            raise ValueError("Pit-lane boundary multiplicity must reconcile.")
        for exact, published in (
            (self.entry_session_time_ns, self.entry_session_time_ms),
            (self.exit_session_time_ns, self.exit_session_time_ms),
            (self.entry_to_exit_elapsed_ns, self.entry_to_exit_elapsed_ms),
        ):
            if (exact is None) != (published is None):
                raise ValueError("Exact and published pit timing must be paired.")
            if exact is not None and (
                type(exact) is not int
                or exact < 0
                or type(published) is not int
                or published < 0
            ):
                raise ValueError("Pit-lane timing must be non-negative.")
        for changed in (
            self.reported_compound_changed,
            self.reported_stint_changed,
        ):
            if changed is not None and type(changed) is not bool:
                raise ValueError("Reported transition changes must be boolean or None.")
        if self.state is PitEvidenceState.COMPLETE:
            if len(self.boundaries) != 2 or tuple(
                boundary.kind for boundary in self.boundaries
            ) != (PitBoundaryKind.ENTRY, PitBoundaryKind.EXIT):
                raise ValueError("Complete pit evidence requires entry then exit.")
            if any(
                value is None
                for value in (
                    self.entry_lap_number,
                    self.exit_lap_number,
                    self.entry_session_time_ns,
                    self.exit_session_time_ns,
                    self.entry_to_exit_elapsed_ns,
                    self.entry_context,
                    self.exit_context,
                )
            ):
                raise ValueError("Complete pit evidence requires both boundaries.")
            if self.exit_session_time_ns <= self.entry_session_time_ns:
                raise ValueError("Complete pit evidence requires a later exit.")
            if self.exit_lap_number < self.entry_lap_number:
                raise ValueError("Complete pit evidence cannot reverse lap identity.")
            if (
                self.entry_to_exit_elapsed_ns
                != self.exit_session_time_ns - self.entry_session_time_ns
            ):
                raise ValueError("Pit-lane elapsed timing must use exact boundaries.")
            if any(
                boundary.evidence_status is not EvidenceStatus.AVAILABLE
                for boundary in self.boundaries
            ):
                raise ValueError("Complete pit evidence requires trusted boundaries.")
            return

        if self.entry_to_exit_elapsed_ns is not None or any(
            changed is not None
            for changed in (
                self.reported_compound_changed,
                self.reported_stint_changed,
            )
        ):
            raise ValueError("Incomplete pit evidence cannot carry derived values.")
        if self.state is PitEvidenceState.UNPAIRED_ENTRY:
            self._validate_unpaired(PitBoundaryKind.ENTRY)
        elif self.state is PitEvidenceState.UNPAIRED_EXIT:
            self._validate_unpaired(PitBoundaryKind.EXIT)
        elif self.state is PitEvidenceState.CONFLICTING:
            if any(
                boundary.evidence_status is not EvidenceStatus.CONFLICTING
                for boundary in self.boundaries
            ):
                raise ValueError(
                    "Conflicting pit evidence requires conflicting boundaries."
                )
            self._validate_no_trusted_boundary_fields()
        elif self.state is PitEvidenceState.UNAVAILABLE:
            if any(
                boundary.evidence_status is not EvidenceStatus.UNAVAILABLE
                for boundary in self.boundaries
            ):
                raise ValueError(
                    "Unavailable pit evidence requires unavailable boundaries."
                )
            self._validate_no_trusted_boundary_fields()

    def _validate_unpaired(self, kind: PitBoundaryKind) -> None:
        if len(self.boundaries) != 1 or self.boundaries[0].kind is not kind:
            raise ValueError("Unpaired pit evidence requires its named boundary.")
        boundary = self.boundaries[0]
        if boundary.evidence_status is not EvidenceStatus.AVAILABLE:
            raise ValueError("Unpaired pit evidence requires a trusted boundary.")
        if kind is PitBoundaryKind.ENTRY:
            valid = (
                self.entry_lap_number == boundary.lap_number
                and self.entry_session_time_ns == boundary.session_time_ns
                and self.entry_session_time_ms == boundary.session_time_ms
                and self.entry_context is not None
                and self.exit_lap_number is None
                and self.exit_session_time_ns is None
                and self.exit_context is None
            )
        else:
            valid = (
                self.exit_lap_number == boundary.lap_number
                and self.exit_session_time_ns == boundary.session_time_ns
                and self.exit_session_time_ms == boundary.session_time_ms
                and self.exit_context is not None
                and self.entry_lap_number is None
                and self.entry_session_time_ns is None
                and self.entry_context is None
            )
        if not valid:
            raise ValueError("Unpaired pit evidence fields must match its boundary.")

    def _validate_no_trusted_boundary_fields(self) -> None:
        if any(
            value is not None
            for value in (
                self.entry_lap_number,
                self.exit_lap_number,
                self.entry_session_time_ns,
                self.exit_session_time_ns,
            )
        ):
            raise ValueError("Untrusted pit evidence cannot carry trusted boundaries.")


@dataclass(frozen=True)
class ConsolidatedLapContext:
    driver_number: str
    lap_number: int
    evidence_status: EvidenceStatus
    source_evidence_count: int
    completion_time_ns: int | None
    completion_time_ms: int | None
    completion_position: int | None
    track_status: NormalizedTrackStatusEvidence
    provider_generated: bool | None
    reported_compound: str | None
    reported_stint: int | None
    leader_reference: LeaderReference | None
    laps_behind_status: RaceContextAvailability
    laps_behind: int | None
    equal_distance_time_deficit_status: EqualDistanceTimeDeficitStatus
    equal_distance_time_deficit_ns: int | None
    equal_distance_time_deficit_ms: int | None

    def __post_init__(self) -> None:
        if type(self.driver_number) is not str or not self.driver_number:
            raise ValueError("Lap context requires a driver identity.")
        if type(self.lap_number) is not int or self.lap_number <= 0:
            raise ValueError("Lap context requires a positive lap number.")
        if (
            type(self.source_evidence_count) is not int
            or self.source_evidence_count <= 0
        ):
            raise ValueError("Lap context requires source evidence.")
        for exact, published in (
            (self.completion_time_ns, self.completion_time_ms),
            (
                self.equal_distance_time_deficit_ns,
                self.equal_distance_time_deficit_ms,
            ),
        ):
            if (exact is None) != (published is None):
                raise ValueError("Exact and published timing must be paired.")
            if exact is not None and (
                type(exact) is not int
                or exact < 0
                or type(published) is not int
                or published < 0
            ):
                raise ValueError("Lap-context timing must be non-negative.")
        if self.completion_position is not None and (
            type(self.completion_position) is not int or self.completion_position <= 0
        ):
            raise ValueError("Completion position must be positive or None.")
        if self.laps_behind_status is RaceContextAvailability.AVAILABLE:
            if type(self.laps_behind) is not int or self.laps_behind < 0:
                raise ValueError("Available lap deficit must be non-negative.")
            if self.leader_reference is None:
                raise ValueError("Available lap deficit requires its leader reference.")
        elif self.laps_behind is not None or self.leader_reference is not None:
            raise ValueError("Unavailable lap deficit cannot carry derived values.")
        if (
            self.equal_distance_time_deficit_status
            is EqualDistanceTimeDeficitStatus.AVAILABLE
        ):
            if self.laps_behind != 0 or self.equal_distance_time_deficit_ns is None:
                raise ValueError(
                    "Available equal-distance timing requires zero laps behind."
                )
        elif (
            self.equal_distance_time_deficit_status
            is EqualDistanceTimeDeficitStatus.NOT_APPLICABLE
        ):
            if not self.laps_behind or self.equal_distance_time_deficit_ns is not None:
                raise ValueError("Unequal distance requires a positive lap deficit.")
        elif self.equal_distance_time_deficit_ns is not None:
            raise ValueError("Unavailable equal-distance timing cannot carry a value.")
        if self.provider_generated is not False and (
            self.leader_reference is not None or self.laps_behind is not None
        ):
            raise ValueError("Untrusted generated state cannot carry derived context.")


@dataclass(frozen=True)
class DriverInvalidLapIdentityCount:
    driver_number: str
    invalid_lap_identity_count: int

    def __post_init__(self) -> None:
        if type(self.driver_number) is not str or not self.driver_number:
            raise ValueError("Invalid-lap accounting requires a driver identity.")
        if (
            type(self.invalid_lap_identity_count) is not int
            or self.invalid_lap_identity_count < 0
        ):
            raise ValueError("Invalid-lap identity count must be non-negative.")


@dataclass(frozen=True)
class LapContextAnalysis:
    lap_contexts: tuple[ConsolidatedLapContext, ...]
    roster_orphan_row_count: int
    invalid_lap_identity_counts: tuple[DriverInvalidLapIdentityCount, ...]

    def __post_init__(self) -> None:
        if (
            type(self.roster_orphan_row_count) is not int
            or self.roster_orphan_row_count < 0
        ):
            raise ValueError("Roster-orphan row count must be non-negative.")


@dataclass(frozen=True)
class RaceClassificationContext:
    evidence_status: EvidenceStatus
    source_evidence_count: int
    finish_position: int | None
    classified_position: str | None
    status: str | None
    completed_laps: int | None


@dataclass(frozen=True)
class PitEvidenceCounts:
    complete: int
    unpaired_entry: int
    unpaired_exit: int
    conflicting: int
    unavailable: int
    total: int

    def __post_init__(self) -> None:
        counts = (
            self.complete,
            self.unpaired_entry,
            self.unpaired_exit,
            self.conflicting,
            self.unavailable,
        )
        if any(type(count) is not int or count < 0 for count in (*counts, self.total)):
            raise ValueError("Pit evidence counts must be non-negative integers.")
        if sum(counts) != self.total:
            raise ValueError("Pit evidence state counts must sum to total.")


@dataclass(frozen=True)
class ParticipantRaceContextAnalysis:
    identity: RaceContextParticipantIdentity
    classification: RaceClassificationContext
    latest_lap_context: ConsolidatedLapContext | None
    pit_evidence_counts: PitEvidenceCounts
    lap_contexts: tuple[ConsolidatedLapContext, ...]
    pit_evidence: tuple[PitLaneEvidence, ...]
    unassociated_evidence_count: int

    def __post_init__(self) -> None:
        driver_number = self.identity.driver_number
        if any(context.driver_number != driver_number for context in self.lap_contexts):
            raise ValueError("Participant lap contexts must belong to that driver.")
        if self.latest_lap_context != _select_latest_trusted_lap_context(
            self.lap_contexts
        ):
            raise ValueError(
                "Latest context must match the latest trusted participant lap."
            )
        for evidence in self.pit_evidence:
            references = (
                *(boundary.lap_context_reference for boundary in evidence.boundaries),
                *(
                    context.lap_context_reference
                    for context in (evidence.entry_context, evidence.exit_context)
                    if context is not None
                ),
            )
            if any(
                reference is not None and reference.driver_number != driver_number
                for reference in references
            ):
                raise ValueError("Participant pit evidence must belong to that driver.")
        if self.pit_evidence_counts != _count_pit_evidence(self.pit_evidence):
            raise ValueError(
                "Pit evidence state counts must match the participant collection."
            )
        if (
            type(self.unassociated_evidence_count) is not int
            or self.unassociated_evidence_count < 0
        ):
            raise ValueError("Unassociated evidence count must be non-negative.")


@dataclass(frozen=True)
class SessionRaceContextAnalysis:
    participants: tuple[ParticipantRaceContextAnalysis, ...]

    def __post_init__(self) -> None:
        driver_numbers = tuple(
            item.identity.driver_number for item in self.participants
        )
        if len(set(driver_numbers)) != len(driver_numbers):
            raise ValueError("Session participant identities must be unique.")


@dataclass(frozen=True)
class _LeaderLapEvidence:
    reference: LeaderReference | None
    progression_times_ns: tuple[int, ...]


@dataclass(frozen=True)
class _PitBoundaryCandidate:
    kind: PitBoundaryKind
    lap_number: int
    evidence_status: EvidenceStatus
    boundary: PitBoundary
    transition_context: PitTransitionContext


_ConsensusValue = TypeVar("_ConsensusValue")


def analyze_race_context(race_context: RaceContextInput) -> SessionRaceContextAnalysis:
    """Compose one reusable session result from one normalized snapshot."""
    participants = tuple(
        sorted(
            race_context.participants,
            key=lambda participant: _driver_number_order(
                participant.identity.driver_number
            ),
        )
    )
    driver_numbers = tuple(p.identity.driver_number for p in participants)
    if len(set(driver_numbers)) != len(driver_numbers):
        raise ValueError("Normalized authoritative participants must be unique.")

    lap_analysis = analyze_lap_contexts(race_context)
    contexts_by_identity = {
        (context.driver_number, context.lap_number): context
        for context in lap_analysis.lap_contexts
    }
    laps_by_driver: dict[str, list[ConsolidatedLapContext]] = defaultdict(list)
    rows_by_driver: dict[str, list[RaceContextLapRowInput]] = defaultdict(list)
    for context in lap_analysis.lap_contexts:
        laps_by_driver[context.driver_number].append(context)
    for row in race_context.lap_rows:
        if row.driver_number in driver_numbers:
            rows_by_driver[row.driver_number].append(row)
    invalid_counts = {
        count.driver_number: count.invalid_lap_identity_count
        for count in lap_analysis.invalid_lap_identity_counts
    }
    analyses = []
    for participant in participants:
        driver_number = participant.identity.driver_number
        lap_contexts = tuple(laps_by_driver[driver_number])
        pit_evidence = _derive_pit_evidence(
            rows_by_driver[driver_number],
            contexts_by_identity,
            driver_number,
        )
        analyses.append(
            ParticipantRaceContextAnalysis(
                identity=participant.identity,
                classification=RaceClassificationContext(
                    participant.result_evidence_status,
                    participant.result_evidence_count,
                    participant.finish_position,
                    participant.classified_position,
                    participant.classification_status,
                    participant.completed_laps,
                ),
                latest_lap_context=_select_latest_trusted_lap_context(lap_contexts),
                pit_evidence_counts=_count_pit_evidence(pit_evidence),
                lap_contexts=lap_contexts,
                pit_evidence=pit_evidence,
                unassociated_evidence_count=invalid_counts[driver_number],
            )
        )
    return SessionRaceContextAnalysis(tuple(analyses))


def _select_latest_trusted_lap_context(
    lap_contexts: tuple[ConsolidatedLapContext, ...],
) -> ConsolidatedLapContext | None:
    return next(
        (
            context
            for context in reversed(lap_contexts)
            if _has_trusted_completion(context)
        ),
        None,
    )


def _count_pit_evidence(evidence: tuple[PitLaneEvidence, ...]) -> PitEvidenceCounts:
    counts = Counter(item.state for item in evidence)
    return PitEvidenceCounts(
        complete=counts[PitEvidenceState.COMPLETE],
        unpaired_entry=counts[PitEvidenceState.UNPAIRED_ENTRY],
        unpaired_exit=counts[PitEvidenceState.UNPAIRED_EXIT],
        conflicting=counts[PitEvidenceState.CONFLICTING],
        unavailable=counts[PitEvidenceState.UNAVAILABLE],
        total=len(evidence),
    )


def analyze_lap_contexts(race_context: RaceContextInput) -> LapContextAnalysis:
    """Derive canonical lap-boundary context without provider-specific behavior."""
    consolidated, invalid_lap_identity_counts = _consolidate_lap_evidence(race_context)
    leader_laps = _establish_lap_leaders(consolidated, race_context.lap_rows)
    contexts = tuple(
        _derive_lap_boundary_context(context, leader_laps) for context in consolidated
    )
    return LapContextAnalysis(
        contexts,
        race_context.unassociated_row_count,
        invalid_lap_identity_counts,
    )


def analyze_complete_pit_visits(
    race_context: RaceContextInput,
    lap_contexts: tuple[ConsolidatedLapContext, ...],
    driver_number: str,
) -> tuple[PitLaneEvidence, ...]:
    """Derive unambiguous complete visits for one authoritative participant."""
    return tuple(
        evidence
        for evidence in analyze_pit_evidence(
            race_context,
            lap_contexts,
            driver_number,
        )
        if evidence.state is PitEvidenceState.COMPLETE
    )


def analyze_pit_evidence(
    race_context: RaceContextInput,
    lap_contexts: tuple[ConsolidatedLapContext, ...],
    driver_number: str,
) -> tuple[PitLaneEvidence, ...]:
    """Derive canonical auditable pit evidence for one authoritative participant."""
    participant_numbers = {
        participant.identity.driver_number for participant in race_context.participants
    }
    if driver_number not in participant_numbers:
        return ()

    contexts_by_identity = {
        (context.driver_number, context.lap_number): context for context in lap_contexts
    }
    return _derive_pit_evidence(
        race_context.lap_rows,
        contexts_by_identity,
        driver_number,
    )


def _derive_pit_evidence(
    lap_rows: tuple[RaceContextLapRowInput, ...] | list[RaceContextLapRowInput],
    contexts_by_identity: dict[tuple[str, int], ConsolidatedLapContext],
    driver_number: str,
) -> tuple[PitLaneEvidence, ...]:
    claims: dict[
        tuple[PitBoundaryKind, int],
        list[tuple[NormalizedValue, bool | None]],
    ] = defaultdict(list)
    for row in lap_rows:
        if (
            row.driver_number != driver_number
            or row.lap_number.state is not NormalizedValueState.AVAILABLE
        ):
            continue

        lap_number = row.lap_number.value
        for kind, timestamp in (
            (PitBoundaryKind.ENTRY, row.pit_entry_time_ns),
            (PitBoundaryKind.EXIT, row.pit_exit_time_ns),
        ):
            if timestamp.state is NormalizedValueState.ABSENT:
                continue
            claims[(kind, lap_number)].append((timestamp, row.provider_generated))

    candidates = []
    for (kind, lap_number), logical_claims in claims.items():
        lap_context = contexts_by_identity[(driver_number, lap_number)]
        lap_reference = LapContextReference(driver_number, lap_number)
        transition_context = PitTransitionContext(
            availability=lap_context.evidence_status,
            lap_context_reference=lap_reference,
            reported_compound=lap_context.reported_compound,
            reported_stint=lap_context.reported_stint,
        )
        claim_counts = Counter(logical_claims)
        if len(claim_counts) == 1:
            (timestamp, provider_generated), source_count = next(
                iter(claim_counts.items())
            )
            evidence_status = (
                EvidenceStatus.AVAILABLE
                if timestamp.state is NormalizedValueState.AVAILABLE
                and provider_generated is False
                else EvidenceStatus.UNAVAILABLE
            )
            boundary = _build_pit_boundary(
                kind,
                lap_number,
                timestamp,
                evidence_status,
                source_count,
                lap_reference,
            )
        else:
            timestamps = tuple(
                timestamp for timestamp, _provider_generated in logical_claims
            )
            timestamp = (
                timestamps[0]
                if all(
                    candidate_timestamp == timestamps[0]
                    for candidate_timestamp in timestamps
                )
                else NormalizedValue(NormalizedValueState.INVALID)
            )
            boundary = _build_pit_boundary(
                kind,
                lap_number,
                timestamp,
                EvidenceStatus.CONFLICTING,
                len(logical_claims),
                lap_reference,
            )
            evidence_status = EvidenceStatus.CONFLICTING
        candidates.append(
            _PitBoundaryCandidate(
                kind=kind,
                lap_number=lap_number,
                evidence_status=evidence_status,
                boundary=boundary,
                transition_context=transition_context,
            )
        )

    ordered_candidates = tuple(sorted(candidates, key=_pit_candidate_order))
    trusted_candidates = tuple(
        candidate
        for candidate in ordered_candidates
        if candidate.evidence_status is EvidenceStatus.AVAILABLE
    )
    evidence = list(_associate_trusted_pit_candidates(trusted_candidates))
    for candidate in ordered_candidates:
        if candidate.evidence_status is EvidenceStatus.AVAILABLE:
            continue
        if candidate.evidence_status is EvidenceStatus.CONFLICTING:
            evidence.append(
                _build_noncomplete_pit_evidence(
                    PitEvidenceState.CONFLICTING,
                    (candidate,),
                )
            )
        else:
            evidence.append(
                _build_noncomplete_pit_evidence(
                    PitEvidenceState.UNAVAILABLE,
                    (candidate,),
                )
            )
    return tuple(sorted(evidence, key=_pit_evidence_order))


def _build_pit_boundary(
    kind: PitBoundaryKind,
    lap_number: int,
    timestamp: NormalizedValue,
    evidence_status: EvidenceStatus,
    source_count: int,
    lap_reference: LapContextReference,
) -> PitBoundary:
    exact_time = (
        timestamp.value if timestamp.state is NormalizedValueState.AVAILABLE else None
    )
    return PitBoundary(
        kind=kind,
        evidence_status=evidence_status,
        source_evidence_count=source_count,
        lap_number=lap_number,
        session_time_ns=exact_time,
        session_time_ms=(
            _publish_milliseconds(exact_time) if exact_time is not None else None
        ),
        lap_context_reference=lap_reference,
    )


def _associate_trusted_pit_candidates(
    candidates: tuple[_PitBoundaryCandidate, ...],
) -> tuple[PitLaneEvidence, ...]:
    evidence = []
    index = 0
    while index < len(candidates):
        candidate = candidates[index]
        if candidate.kind is PitBoundaryKind.EXIT:
            next_candidate = (
                candidates[index + 1] if index + 1 < len(candidates) else None
            )
            if (
                next_candidate is not None
                and next_candidate.kind is PitBoundaryKind.ENTRY
                and (
                    _pit_candidate_time(candidate)
                    == _pit_candidate_time(next_candidate)
                    or candidate.lap_number > next_candidate.lap_number
                )
            ):
                entry_end = index + 1
                while (
                    entry_end < len(candidates)
                    and candidates[entry_end].kind is PitBoundaryKind.ENTRY
                ):
                    entry_end += 1
                evidence.append(
                    _build_noncomplete_pit_evidence(
                        PitEvidenceState.CONFLICTING,
                        candidates[index:entry_end],
                    )
                )
                index = entry_end
                continue
            evidence.append(
                _build_noncomplete_pit_evidence(
                    PitEvidenceState.UNPAIRED_EXIT,
                    (candidate,),
                )
            )
            index += 1
            continue

        entry_end = index
        while (
            entry_end < len(candidates)
            and candidates[entry_end].kind is PitBoundaryKind.ENTRY
        ):
            entry_end += 1
        exit_end = entry_end
        while (
            exit_end < len(candidates)
            and candidates[exit_end].kind is PitBoundaryKind.EXIT
        ):
            exit_end += 1
        entry_run = candidates[index:entry_end]
        exit_run = candidates[entry_end:exit_end]
        if not exit_run:
            state = (
                PitEvidenceState.UNPAIRED_ENTRY
                if len(entry_run) == 1
                else PitEvidenceState.CONFLICTING
            )
            evidence.append(_build_noncomplete_pit_evidence(state, entry_run))
        elif len(entry_run) == 1 and len(exit_run) == 1:
            entry = entry_run[0]
            exit_ = exit_run[0]
            if (
                _pit_candidate_time(exit_) > _pit_candidate_time(entry)
                and exit_.lap_number >= entry.lap_number
            ):
                evidence.append(_build_complete_pit_visit(entry, exit_))
            else:
                evidence.append(
                    _build_noncomplete_pit_evidence(
                        PitEvidenceState.CONFLICTING,
                        entry_run + exit_run,
                    )
                )
        else:
            evidence.append(
                _build_noncomplete_pit_evidence(
                    PitEvidenceState.CONFLICTING,
                    entry_run + exit_run,
                )
            )
        index = exit_end
    return tuple(evidence)


def _build_complete_pit_visit(
    entry: _PitBoundaryCandidate,
    exit_: _PitBoundaryCandidate,
) -> PitLaneEvidence:
    entry_boundary = entry.boundary
    exit_boundary = exit_.boundary
    entry_time_ns = entry_boundary.session_time_ns
    exit_time_ns = exit_boundary.session_time_ns
    elapsed_ns = exit_time_ns - entry_time_ns
    entry_context = entry.transition_context
    exit_context = exit_.transition_context
    compound_changed = (
        None
        if entry_context.reported_compound is None
        or exit_context.reported_compound is None
        else entry_context.reported_compound != exit_context.reported_compound
    )
    stint_changed = (
        None
        if entry_context.reported_stint is None or exit_context.reported_stint is None
        else entry_context.reported_stint != exit_context.reported_stint
    )
    return PitLaneEvidence(
        state=PitEvidenceState.COMPLETE,
        boundaries=(entry_boundary, exit_boundary),
        source_boundary_count=(
            entry_boundary.source_evidence_count + exit_boundary.source_evidence_count
        ),
        entry_lap_number=entry_boundary.lap_number,
        exit_lap_number=exit_boundary.lap_number,
        entry_session_time_ns=entry_time_ns,
        entry_session_time_ms=entry_boundary.session_time_ms,
        exit_session_time_ns=exit_time_ns,
        exit_session_time_ms=exit_boundary.session_time_ms,
        entry_to_exit_elapsed_ns=elapsed_ns,
        entry_to_exit_elapsed_ms=_publish_milliseconds(elapsed_ns),
        entry_context=entry_context,
        exit_context=exit_context,
        reported_compound_changed=compound_changed,
        reported_stint_changed=stint_changed,
    )


def _build_noncomplete_pit_evidence(
    state: PitEvidenceState,
    candidates: tuple[_PitBoundaryCandidate, ...],
) -> PitLaneEvidence:
    boundaries = tuple(
        sorted(
            (
                replace(
                    candidate.boundary,
                    evidence_status=(
                        EvidenceStatus.CONFLICTING
                        if state is PitEvidenceState.CONFLICTING
                        else candidate.boundary.evidence_status
                    ),
                )
                for candidate in candidates
            ),
            key=_pit_boundary_order,
        )
    )
    entry_candidates = tuple(
        candidate for candidate in candidates if candidate.kind is PitBoundaryKind.ENTRY
    )
    exit_candidates = tuple(
        candidate for candidate in candidates if candidate.kind is PitBoundaryKind.EXIT
    )
    entry_context = (
        entry_candidates[0].transition_context if len(entry_candidates) == 1 else None
    )
    exit_context = (
        exit_candidates[0].transition_context if len(exit_candidates) == 1 else None
    )
    entry_lap_number = None
    exit_lap_number = None
    entry_session_time_ns = None
    entry_session_time_ms = None
    exit_session_time_ns = None
    exit_session_time_ms = None
    if state is PitEvidenceState.UNPAIRED_ENTRY:
        boundary = boundaries[0]
        entry_lap_number = boundary.lap_number
        entry_session_time_ns = boundary.session_time_ns
        entry_session_time_ms = boundary.session_time_ms
    elif state is PitEvidenceState.UNPAIRED_EXIT:
        boundary = boundaries[0]
        exit_lap_number = boundary.lap_number
        exit_session_time_ns = boundary.session_time_ns
        exit_session_time_ms = boundary.session_time_ms
    return PitLaneEvidence(
        state=state,
        boundaries=boundaries,
        source_boundary_count=sum(
            boundary.source_evidence_count for boundary in boundaries
        ),
        entry_lap_number=entry_lap_number,
        exit_lap_number=exit_lap_number,
        entry_session_time_ns=entry_session_time_ns,
        entry_session_time_ms=entry_session_time_ms,
        exit_session_time_ns=exit_session_time_ns,
        exit_session_time_ms=exit_session_time_ms,
        entry_to_exit_elapsed_ns=None,
        entry_to_exit_elapsed_ms=None,
        entry_context=entry_context,
        exit_context=exit_context,
        reported_compound_changed=None,
        reported_stint_changed=None,
    )


def _pit_candidate_time(candidate: _PitBoundaryCandidate) -> int:
    return candidate.boundary.session_time_ns


def _pit_candidate_order(
    candidate: _PitBoundaryCandidate,
) -> tuple[bool, int, int, int, tuple[bool, int, bool, int, int]]:
    session_time_ns = candidate.boundary.session_time_ns
    return (
        session_time_ns is None,
        session_time_ns if session_time_ns is not None else 0,
        candidate.lap_number,
        0 if candidate.kind is PitBoundaryKind.ENTRY else 1,
        _pit_boundary_order(candidate.boundary),
    )


def _pit_boundary_order(boundary: PitBoundary) -> tuple[bool, int, bool, int, int]:
    return (
        boundary.session_time_ns is None,
        boundary.session_time_ns if boundary.session_time_ns is not None else 0,
        boundary.lap_number is None,
        boundary.lap_number if boundary.lap_number is not None else 0,
        0 if boundary.kind is PitBoundaryKind.ENTRY else 1,
    )


def _pit_evidence_order(evidence: PitLaneEvidence) -> tuple:
    available_times = tuple(
        boundary.session_time_ns
        for boundary in evidence.boundaries
        if boundary.session_time_ns is not None
    )
    available_laps = tuple(
        boundary.lap_number
        for boundary in evidence.boundaries
        if boundary.lap_number is not None
    )
    state_order = {
        PitEvidenceState.COMPLETE: 0,
        PitEvidenceState.UNPAIRED_ENTRY: 1,
        PitEvidenceState.UNPAIRED_EXIT: 2,
        PitEvidenceState.CONFLICTING: 3,
        PitEvidenceState.UNAVAILABLE: 4,
    }
    return (
        not available_times,
        min(available_times) if available_times else 0,
        not available_laps,
        min(available_laps) if available_laps else 0,
        state_order[evidence.state],
        tuple(_pit_boundary_order(boundary) for boundary in evidence.boundaries),
    )


def _consolidate_lap_evidence(
    race_context: RaceContextInput,
) -> tuple[
    tuple[ConsolidatedLapContext, ...],
    tuple[DriverInvalidLapIdentityCount, ...],
]:
    participant_numbers = {
        participant.identity.driver_number for participant in race_context.participants
    }
    canonical_driver_numbers = sorted(participant_numbers, key=_driver_number_order)
    grouped: dict[tuple[str, int], list[RaceContextLapRowInput]] = defaultdict(list)
    invalid_lap_identity_counts = dict.fromkeys(canonical_driver_numbers, 0)
    for row in race_context.lap_rows:
        if row.driver_number not in participant_numbers:
            continue
        if row.lap_number.state is not NormalizedValueState.AVAILABLE:
            invalid_lap_identity_counts[row.driver_number] += 1
            continue
        grouped[(row.driver_number, row.lap_number.value)].append(row)

    participant_order = {
        driver_number: position
        for position, driver_number in enumerate(canonical_driver_numbers)
    }
    consolidated = tuple(
        _consolidate_driver_lap(driver_number, lap_number, rows)
        for (driver_number, lap_number), rows in sorted(
            grouped.items(),
            key=lambda grouped_rows: (
                participant_order[grouped_rows[0][0]],
                grouped_rows[0][1],
            ),
        )
    )
    return consolidated, tuple(
        DriverInvalidLapIdentityCount(
            driver_number, invalid_lap_identity_counts[driver_number]
        )
        for driver_number in canonical_driver_numbers
    )


def _consolidate_driver_lap(
    driver_number: str,
    lap_number: int,
    rows: list[RaceContextLapRowInput],
) -> ConsolidatedLapContext:
    completion_time, completion_time_conflict = _normalized_value_consensus(
        tuple(row.lap_completion_time_ns for row in rows)
    )
    completion_position, completion_position_conflict = _normalized_value_consensus(
        tuple(row.lap_completion_position for row in rows)
    )
    track_status, track_status_conflict = _consensus(
        tuple(row.track_status for row in rows)
    )
    provider_generated, provider_generated_conflict = _consensus(
        tuple(row.provider_generated for row in rows)
    )
    reported_compound, reported_compound_conflict = _consensus(
        tuple(row.reported_compound for row in rows)
    )
    reported_stint, reported_stint_conflict = _consensus(
        tuple(row.reported_stint for row in rows)
    )
    has_conflict = any(
        (
            completion_time_conflict,
            completion_position_conflict,
            track_status_conflict,
            provider_generated_conflict,
            reported_compound_conflict,
            reported_stint_conflict,
        )
    )
    if has_conflict:
        evidence_status = EvidenceStatus.CONFLICTING
    elif completion_time is None:
        evidence_status = EvidenceStatus.UNAVAILABLE
    else:
        evidence_status = EvidenceStatus.AVAILABLE

    if track_status is None:
        track_status = NormalizedTrackStatusEvidence(
            TrackStatusAvailability.UNAVAILABLE,
            (),
            None,
        )
    return ConsolidatedLapContext(
        driver_number=driver_number,
        lap_number=lap_number,
        evidence_status=evidence_status,
        source_evidence_count=len(rows),
        completion_time_ns=completion_time,
        completion_time_ms=(
            _publish_milliseconds(completion_time)
            if completion_time is not None
            else None
        ),
        completion_position=completion_position,
        track_status=track_status,
        provider_generated=provider_generated,
        reported_compound=reported_compound,
        reported_stint=reported_stint,
        leader_reference=None,
        laps_behind_status=RaceContextAvailability.UNAVAILABLE,
        laps_behind=None,
        equal_distance_time_deficit_status=(EqualDistanceTimeDeficitStatus.UNAVAILABLE),
        equal_distance_time_deficit_ns=None,
        equal_distance_time_deficit_ms=None,
    )


def _establish_lap_leaders(
    consolidated: tuple[ConsolidatedLapContext, ...],
    lap_rows: tuple[RaceContextLapRowInput, ...],
) -> dict[int, _LeaderLapEvidence]:
    by_lap: dict[int, list[ConsolidatedLapContext]] = defaultdict(list)
    for context in consolidated:
        by_lap[context.lap_number].append(context)

    contexts_by_identity = {
        (context.driver_number, context.lap_number): context for context in consolidated
    }
    progression_times_by_lap: dict[int, set[int]] = defaultdict(set)
    unresolved_position_one_times_by_lap: dict[int, set[int]] = defaultdict(set)
    for row in lap_rows:
        if (
            row.driver_number is None
            or row.lap_number.state is not NormalizedValueState.AVAILABLE
            or row.lap_completion_time_ns.state is not NormalizedValueState.AVAILABLE
        ):
            continue
        lap_number = row.lap_number.value
        completion_time_ns = row.lap_completion_time_ns.value
        context = contexts_by_identity.get((row.driver_number, lap_number))
        if context is None:
            continue
        if row.provider_generated is not False:
            continue
        context_is_trusted_leader = (
            context.completion_position == 1 and _has_trusted_completion(context)
        )
        if not context_is_trusted_leader:
            progression_times_by_lap[lap_number].add(completion_time_ns)
        if (
            row.lap_completion_position.state is NormalizedValueState.AVAILABLE
            and row.lap_completion_position.value == 1
            and not context_is_trusted_leader
        ):
            unresolved_position_one_times_by_lap[lap_number].add(completion_time_ns)

    leader_laps = {}
    for lap_number, lap_evidence in by_lap.items():
        trusted = [
            context
            for context in lap_evidence
            if context.completion_position == 1 and _has_trusted_completion(context)
        ]
        progression_times = tuple(
            sorted(
                progression_times_by_lap[lap_number]
                | {context.completion_time_ns for context in trusted}
            )
        )
        if len(trusted) == 1 and not unresolved_position_one_times_by_lap[lap_number]:
            leader = trusted[0]
            leader_laps[lap_number] = _LeaderLapEvidence(
                LeaderReference(
                    leader.driver_number,
                    leader.lap_number,
                    leader.completion_time_ns,
                    leader.completion_time_ms,
                ),
                (),
            )
            continue
        leader_laps[lap_number] = _LeaderLapEvidence(None, progression_times)
    return leader_laps


def _derive_lap_boundary_context(
    selected: ConsolidatedLapContext,
    leader_laps: dict[int, _LeaderLapEvidence],
) -> ConsolidatedLapContext:
    if not _has_trusted_completion(selected):
        return selected

    same_lap_leader = leader_laps.get(selected.lap_number)
    same_lap_deficit_ns = None
    if same_lap_leader is not None and same_lap_leader.reference is not None:
        same_lap_deficit_ns = (
            selected.completion_time_ns - same_lap_leader.reference.completion_time_ns
        )
        if same_lap_deficit_ns < 0:
            return selected

    eligible_references = tuple(
        leader.reference
        for leader in leader_laps.values()
        if leader.reference is not None
        and leader.reference.completion_time_ns <= selected.completion_time_ns
    )
    if not eligible_references:
        return selected
    leader_reference = max(
        eligible_references, key=lambda reference: reference.lap_number
    )
    if any(
        evidence.reference is None
        and lap_number >= leader_reference.lap_number
        and any(
            progression_time <= selected.completion_time_ns
            for progression_time in evidence.progression_times_ns
        )
        for lap_number, evidence in leader_laps.items()
    ):
        return selected

    laps_behind = leader_reference.lap_number - selected.lap_number
    if laps_behind < 0:
        return selected
    if laps_behind > 0:
        return replace(
            selected,
            leader_reference=leader_reference,
            laps_behind_status=RaceContextAvailability.AVAILABLE,
            laps_behind=laps_behind,
            equal_distance_time_deficit_status=(
                EqualDistanceTimeDeficitStatus.NOT_APPLICABLE
            ),
        )

    exact_deficit = same_lap_deficit_ns
    if exact_deficit is None:
        return selected
    return replace(
        selected,
        leader_reference=leader_reference,
        laps_behind_status=RaceContextAvailability.AVAILABLE,
        laps_behind=0,
        equal_distance_time_deficit_status=EqualDistanceTimeDeficitStatus.AVAILABLE,
        equal_distance_time_deficit_ns=exact_deficit,
        equal_distance_time_deficit_ms=_publish_milliseconds(exact_deficit),
    )


def _has_trusted_completion(context: ConsolidatedLapContext) -> bool:
    return (
        context.completion_time_ns is not None and context.provider_generated is False
    )


def _normalized_value_consensus(
    evidence: tuple[NormalizedValue, ...],
) -> tuple[int | None, bool]:
    consensus, conflicting = _consensus(evidence)
    if conflicting or consensus.state is not NormalizedValueState.AVAILABLE:
        return None, conflicting
    return consensus.value, False


def _consensus(
    values: tuple[_ConsensusValue, ...],
) -> tuple[_ConsensusValue | None, bool]:
    distinct_values = set(values)
    if len(distinct_values) != 1:
        return None, True
    return next(iter(distinct_values)), False


def _publish_milliseconds(exact_nanoseconds: int) -> int:
    return (exact_nanoseconds + 500_000) // 1_000_000


def _driver_number_order(driver_number: str) -> tuple[int, int, str]:
    if re.fullmatch(r"[1-9][0-9]*", driver_number):
        return (0, int(driver_number), "")
    return (1, 0, driver_number)
