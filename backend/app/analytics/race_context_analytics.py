"""Application-owned inputs and pure deterministic race-context analytics."""

import re
from collections import defaultdict
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
class _LeaderLapEvidence:
    reference: LeaderReference | None
    progression_times_ns: tuple[int, ...]


@dataclass(frozen=True)
class _PitBoundaryCandidate:
    boundary: PitBoundary
    transition_context: PitTransitionContext


_ConsensusValue = TypeVar("_ConsensusValue")


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
    participant_numbers = {
        participant.identity.driver_number for participant in race_context.participants
    }
    if driver_number not in participant_numbers:
        return ()

    contexts_by_identity = {
        (context.driver_number, context.lap_number): context for context in lap_contexts
    }
    candidates: list[_PitBoundaryCandidate] = []
    for row in race_context.lap_rows:
        if (
            row.driver_number != driver_number
            or row.provider_generated is not False
            or row.lap_number.state is not NormalizedValueState.AVAILABLE
        ):
            continue

        lap_number = row.lap_number.value
        lap_context = contexts_by_identity[(driver_number, lap_number)]
        lap_reference = LapContextReference(driver_number, lap_number)
        transition_context = PitTransitionContext(
            availability=lap_context.evidence_status,
            lap_context_reference=lap_reference,
            reported_compound=lap_context.reported_compound,
            reported_stint=lap_context.reported_stint,
        )
        for kind, timestamp in (
            (PitBoundaryKind.ENTRY, row.pit_entry_time_ns),
            (PitBoundaryKind.EXIT, row.pit_exit_time_ns),
        ):
            if timestamp.state is not NormalizedValueState.AVAILABLE:
                continue
            candidates.append(
                _PitBoundaryCandidate(
                    boundary=PitBoundary(
                        kind=kind,
                        evidence_status=EvidenceStatus.AVAILABLE,
                        source_evidence_count=1,
                        lap_number=lap_number,
                        session_time_ns=timestamp.value,
                        session_time_ms=_publish_milliseconds(timestamp.value),
                        lap_context_reference=lap_reference,
                    ),
                    transition_context=transition_context,
                )
            )

    candidates_by_time: dict[int, list[_PitBoundaryCandidate]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_time[candidate.boundary.session_time_ns].append(candidate)

    visits: list[PitLaneEvidence] = []
    open_entry: _PitBoundaryCandidate | None = None
    for session_time_ns in sorted(candidates_by_time):
        same_time_candidates = candidates_by_time[session_time_ns]
        if len(same_time_candidates) != 1:
            open_entry = None
            continue

        candidate = same_time_candidates[0]
        if candidate.boundary.kind is PitBoundaryKind.ENTRY:
            if open_entry is None:
                open_entry = candidate
            else:
                open_entry = None
            continue
        if open_entry is None:
            continue
        if candidate.boundary.lap_number < open_entry.boundary.lap_number:
            open_entry = None
            continue
        visits.append(_build_complete_pit_visit(open_entry, candidate))
        open_entry = None

    return tuple(visits)


def _build_complete_pit_visit(
    entry: _PitBoundaryCandidate,
    exit_: _PitBoundaryCandidate,
) -> PitLaneEvidence:
    entry_time_ns = entry.boundary.session_time_ns
    exit_time_ns = exit_.boundary.session_time_ns
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
        boundaries=(entry.boundary, exit_.boundary),
        source_boundary_count=(
            entry.boundary.source_evidence_count + exit_.boundary.source_evidence_count
        ),
        entry_lap_number=entry.boundary.lap_number,
        exit_lap_number=exit_.boundary.lap_number,
        entry_session_time_ns=entry_time_ns,
        entry_session_time_ms=entry.boundary.session_time_ms,
        exit_session_time_ns=exit_time_ns,
        exit_session_time_ms=exit_.boundary.session_time_ms,
        entry_to_exit_elapsed_ns=elapsed_ns,
        entry_to_exit_elapsed_ms=_publish_milliseconds(elapsed_ns),
        entry_context=entry_context,
        exit_context=exit_context,
        reported_compound_changed=compound_changed,
        reported_stint_changed=stint_changed,
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
