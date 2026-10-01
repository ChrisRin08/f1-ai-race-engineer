"""Strict public race-context projections; validators only reject contradictions."""

import re
from collections import Counter
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BeforeValidator, ConfigDict, Field, model_validator

from app.models.pace_models import AnalyticsSessionContext
from app.models.session_models import ContractModel, SourceProvenance


class RaceContextEvidenceStatus(StrEnum):
    """Whether one source-backed interpretation is available, competing normalized
    claims conflict, or required usable evidence is unavailable."""

    AVAILABLE = "available"
    CONFLICTING = "conflicting"
    UNAVAILABLE = "unavailable"


class RaceContextAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class EqualDistanceTimeDeficitStatus(StrEnum):
    """Available only for trustworthy same-completed-lap observations; not_applicable
    when the selected participant is laps behind; unavailable when required
    evidence is missing, invalid, generated, or conflicting."""

    AVAILABLE = "available"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


class NormalizedTrackStatus(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    SAFETY_CAR = "safety_car"
    VIRTUAL_SAFETY_CAR = "virtual_safety_car"
    VIRTUAL_SAFETY_CAR_ENDING = "virtual_safety_car_ending"
    RED_FLAG = "red_flag"
    UNKNOWN = "unknown"


class PitEvidenceState(StrEnum):
    COMPLETE = "complete"
    UNPAIRED_ENTRY = "unpaired_entry"
    UNPAIRED_EXIT = "unpaired_exit"
    CONFLICTING = "conflicting"
    UNAVAILABLE = "unavailable"


class PitBoundaryKind(StrEnum):
    ENTRY = "entry"
    EXIT = "exit"


def _require_enum_token(value: object) -> str:
    # Enum strings are public input, but bytes/numeric coercion is not.
    if not isinstance(value, str):
        raise ValueError("Enum values require string tokens.")
    return value


def _require_ordered_collection(value: object) -> list | tuple:
    if not isinstance(value, (list, tuple)):
        raise ValueError("Public collections require an ordered list or tuple.")
    return value


EvidenceStatus = Annotated[
    RaceContextEvidenceStatus, Field(strict=False), BeforeValidator(_require_enum_token)
]
Availability = Annotated[
    RaceContextAvailability, Field(strict=False), BeforeValidator(_require_enum_token)
]
DeficitStatus = Annotated[
    EqualDistanceTimeDeficitStatus,
    Field(strict=False),
    BeforeValidator(_require_enum_token),
]
TrackStatus = Annotated[
    NormalizedTrackStatus, Field(strict=False), BeforeValidator(_require_enum_token)
]
EvidenceState = Annotated[
    PitEvidenceState, Field(strict=False), BeforeValidator(_require_enum_token)
]
BoundaryKind = Annotated[
    PitBoundaryKind, Field(strict=False), BeforeValidator(_require_enum_token)
]
DriverIdentity = Annotated[str, Field(min_length=1)]
PositiveInteger = Annotated[int, Field(ge=1)]
NonNegativeInteger = Annotated[int, Field(ge=0)]


class RaceContextContractModel(ContractModel):
    model_config = ConfigDict(strict=True, frozen=True, allow_inf_nan=False)


class RaceContextParticipantIdentity(RaceContextContractModel):
    driver_number: DriverIdentity = Field(
        description=(
            "Authoritative provider participant identity. Numeric identities are "
            "ordered numerically; any nonnumeric identity follows in normalized "
            "authoritative-identity order."
        )
    )
    abbreviation: str | None
    full_name: str | None
    team_name: str | None


class RaceClassificationContext(RaceContextContractModel):
    evidence_status: EvidenceStatus
    source_evidence_count: PositiveInteger
    finish_position: PositiveInteger | None
    classified_position: str | None
    status: str | None
    completed_laps: NonNegativeInteger | None


class TrackStatusContext(RaceContextContractModel):
    """Ordered, de-duplicated lap-overlap status evidence. Unknown is never treated
    as green. is_disrupted is true for any known disruption, false only for
    trustworthy fully understood non-disrupted evidence, and null when unavailable
    or indeterminate."""

    availability: Availability
    track_statuses: Annotated[
        tuple[TrackStatus, ...], BeforeValidator(_require_ordered_collection)
    ] = Field(strict=False, json_schema_extra={"uniqueItems": True})
    is_disrupted: bool | None

    @model_validator(mode="after")
    def validate_status_evidence(self) -> Self:
        if len(self.track_statuses) != len(set(self.track_statuses)):
            raise ValueError("Track statuses must be unique without deduplication.")
        if self.availability == RaceContextAvailability.UNAVAILABLE:
            if self.track_statuses or self.is_disrupted is not None:
                raise ValueError(
                    "Unavailable status requires empty statuses and null disruption."
                )
            return self
        known_disruption = any(
            status not in (NormalizedTrackStatus.GREEN, NormalizedTrackStatus.UNKNOWN)
            for status in self.track_statuses
        )
        if not self.track_statuses:
            raise ValueError("Available track status requires observed statuses.")
        if known_disruption:
            if self.is_disrupted is not True:
                raise ValueError("Known disruption requires is_disrupted true.")
        elif NormalizedTrackStatus.UNKNOWN not in self.track_statuses:
            if self.is_disrupted is not False:
                raise ValueError(
                    "Fully understood non-disrupted evidence requires false."
                )
        elif self.is_disrupted is not None:
            raise ValueError("Indeterminate track evidence requires null disruption.")
        return self


class LapContextReference(RaceContextContractModel):
    driver_number: DriverIdentity
    lap_number: PositiveInteger


class LeaderReference(RaceContextContractModel):
    """Latest trustworthy lap-leader completion known at or before the selected
    driver's completion timestamp."""

    driver_number: DriverIdentity
    lap_number: PositiveInteger
    lap_completion_session_time_ms: NonNegativeInteger


class LapCompletionContext(RaceContextContractModel):
    """One compact normalized driver/lap item. Position is provider-exposed
    lap-completion race position, not GPS, physical coordinates, instantaneous
    pit-boundary position, or live timing position. equal_distance_time_deficit_ms
    is selected-driver completion minus lap-leader completion for the same
    completed lap, never a live gap."""

    driver_number: DriverIdentity
    lap_number: PositiveInteger
    evidence_status: EvidenceStatus
    source_evidence_count: PositiveInteger
    lap_completion_session_time_ms: NonNegativeInteger | None
    lap_completion_position: PositiveInteger | None = Field(
        description=(
            "Provider-exposed lap-completion race position, not live or GPS position."
        )
    )
    track_status: TrackStatusContext
    provider_generated: bool | None
    reported_compound: str | None
    reported_stint: PositiveInteger | None
    leader_reference: LeaderReference | None
    laps_behind_status: Availability
    laps_behind: NonNegativeInteger | None
    equal_distance_time_deficit_status: DeficitStatus
    equal_distance_time_deficit_ms: NonNegativeInteger | None = Field(
        description=(
            "Selected-driver minus lap-leader completion at equal distance, "
            "never a live gap."
        )
    )

    @model_validator(mode="after")
    def validate_derived_state(self) -> Self:
        available_laps = self.laps_behind_status == RaceContextAvailability.AVAILABLE
        if available_laps != (self.laps_behind is not None):
            raise ValueError("Lap-deficit availability must match its value.")
        if not available_laps:
            if (
                self.leader_reference is not None
                or self.equal_distance_time_deficit_status
                != EqualDistanceTimeDeficitStatus.UNAVAILABLE
            ):
                raise ValueError(
                    "Unavailable lap deficit cannot claim a trusted reference "
                    "or time deficit."
                )
        else:
            if (
                self.provider_generated is not False
                or self.lap_completion_session_time_ms is None
                or self.leader_reference is None
            ):
                raise ValueError(
                    "Trusted derivatives require measured completion "
                    "and a leader reference."
                )
            if self.leader_reference.lap_number != self.lap_number + self.laps_behind:
                raise ValueError("Leader lap must agree with the supplied lap deficit.")
            if (
                self.leader_reference.lap_completion_session_time_ms
                > self.lap_completion_session_time_ms
            ):
                raise ValueError("Leader reference cannot follow selected completion.")
            if (
                self.leader_reference.driver_number == self.driver_number
                and self.leader_reference.lap_number == self.lap_number
                and self.leader_reference.lap_completion_session_time_ms
                != self.lap_completion_session_time_ms
            ):
                raise ValueError(
                    "The same driver/lap reference must agree with its completion."
                )

        status = self.equal_distance_time_deficit_status
        if status == EqualDistanceTimeDeficitStatus.AVAILABLE:
            if (
                not available_laps
                or self.laps_behind != 0
                or self.equal_distance_time_deficit_ms is None
            ):
                raise ValueError(
                    "Available equal-distance deficit requires zero laps behind "
                    "and a value."
                )
        elif self.equal_distance_time_deficit_ms is not None:
            raise ValueError("Unavailable/not-applicable deficit must be null.")
        if status == EqualDistanceTimeDeficitStatus.NOT_APPLICABLE:
            if not available_laps or self.laps_behind == 0:
                raise ValueError(
                    "Not-applicable deficit requires positive laps behind."
                )
        if (
            available_laps
            and self.laps_behind > 0
            and status != EqualDistanceTimeDeficitStatus.NOT_APPLICABLE
        ):
            raise ValueError("Lapped observations require not-applicable time deficit.")
        return self


class PitBoundaryEvidence(RaceContextContractModel):
    """One compact pit entry or exit candidate with duplicate multiplicity. Exactly
    one of entry_session_time_ms or exit_session_time_ms can be populated
    consistently with kind."""

    kind: BoundaryKind
    evidence_status: EvidenceStatus
    source_evidence_count: PositiveInteger
    lap_number: PositiveInteger | None
    entry_session_time_ms: NonNegativeInteger | None
    exit_session_time_ms: NonNegativeInteger | None
    lap_context_reference: LapContextReference | None

    @model_validator(mode="after")
    def validate_boundary_fields(self) -> Self:
        wrong_time = (
            self.exit_session_time_ms
            if self.kind == PitBoundaryKind.ENTRY
            else self.entry_session_time_ms
        )
        if wrong_time is not None:
            raise ValueError("Boundary kind cannot carry the opposite timestamp.")
        if self.evidence_status == RaceContextEvidenceStatus.AVAILABLE and (
            self.lap_number is None or _boundary_time(self) is None
        ):
            raise ValueError("Available boundary requires lap identity and timing.")
        if (
            self.lap_context_reference is not None
            and self.lap_context_reference.lap_number != self.lap_number
        ):
            raise ValueError("Boundary reference must identify its own lap.")
        return self


class PitTransitionContext(RaceContextContractModel):
    """Reported compound/stint and lap-context reference from exactly the
    entry/in-lap or exit/out-lap completion row. It is not instantaneous context
    at the pit boundary, and no nearby racing lap is substituted."""

    availability: EvidenceStatus
    lap_context_reference: LapContextReference | None
    reported_compound: str | None
    reported_stint: PositiveInteger | None

    @model_validator(mode="after")
    def validate_context_provenance(self) -> Self:
        if (
            self.availability == RaceContextEvidenceStatus.AVAILABLE
            and self.lap_context_reference is None
        ):
            raise ValueError(
                "Available transition context requires its source lap reference."
            )
        return self


def _boundary_time(boundary: PitBoundaryEvidence) -> int | None:
    return (
        boundary.entry_session_time_ms
        if boundary.kind == PitBoundaryKind.ENTRY
        else boundary.exit_session_time_ms
    )


def _validate_public_chronology(previous: int | None, current: int | None) -> bool:
    """Return whether lower keys are observable: only when both times are absent."""
    if previous is None and current is not None:
        raise ValueError("Usable chronology must precede unavailable chronology.")
    if previous is not None and current is not None and previous > current:
        raise ValueError("Published chronology must not reverse.")
    # Equal published times can hide distinct exact timestamps, not an exact tie.
    return previous is None and current is None


def _absent_time_boundary_key(boundary: PitBoundaryEvidence) -> tuple[bool, int, int]:
    return (
        boundary.lap_number is None,
        boundary.lap_number or 0,
        0 if boundary.kind == PitBoundaryKind.ENTRY else 1,
    )


def _validate_boundary_context(
    boundary: PitBoundaryEvidence, context: PitTransitionContext
) -> None:
    ref = context.lap_context_reference
    if ref is not None and (
        ref.lap_number != boundary.lap_number
        or (
            boundary.lap_context_reference is not None
            and ref != boundary.lap_context_reference
        )
    ):
        raise ValueError("Transition context must reference the boundary's own lap.")


class PitLaneEvidence(RaceContextContractModel):
    """Complete, unpaired, conflicting, or unavailable pit-lane evidence.
    entry_to_exit_elapsed_ms is pit-lane entry-to-exit elapsed time, not
    stationary service, mechanic, or tire-change duration. Changed fields compare
    reported values and do not confirm a physical tire change."""

    state: EvidenceState
    boundaries: Annotated[
        tuple[PitBoundaryEvidence, ...], BeforeValidator(_require_ordered_collection)
    ] = Field(strict=False, min_length=1)
    source_boundary_count: PositiveInteger
    entry_lap_number: PositiveInteger | None
    exit_lap_number: PositiveInteger | None
    entry_session_time_ms: NonNegativeInteger | None
    exit_session_time_ms: NonNegativeInteger | None
    entry_to_exit_elapsed_ms: NonNegativeInteger | None = Field(
        description=(
            "Pit-lane entry-to-exit elapsed, "
            "not stationary service or tire-change duration."
        )
    )
    entry_context: PitTransitionContext | None
    exit_context: PitTransitionContext | None
    reported_compound_changed: bool | None
    reported_stint_changed: bool | None

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.source_boundary_count != sum(
            b.source_evidence_count for b in self.boundaries
        ):
            raise ValueError(
                "Source boundary count must reconcile with multiplicities."
            )
        for previous, current in zip(self.boundaries, self.boundaries[1:]):
            if _validate_public_chronology(
                _boundary_time(previous), _boundary_time(current)
            ):
                if _absent_time_boundary_key(previous) > _absent_time_boundary_key(
                    current
                ):
                    raise ValueError(
                        "Chronology-less boundaries must follow lap/kind order."
                    )
        references = [b.lap_context_reference for b in self.boundaries]
        references.extend(
            c.lap_context_reference
            for c in (self.entry_context, self.exit_context)
            if c is not None
        )
        if len({r.driver_number for r in references if r is not None}) > 1:
            raise ValueError("Pit evidence references must belong to one participant.")

        if self.state == PitEvidenceState.COMPLETE:
            self._validate_complete()
        else:
            if (
                self.entry_to_exit_elapsed_ms is not None
                or self.reported_compound_changed is not None
                or self.reported_stint_changed is not None
            ):
                raise ValueError(
                    "Noncomplete evidence cannot carry derived elapsed "
                    "or changed flags."
                )
            if self.state in (
                PitEvidenceState.UNPAIRED_ENTRY,
                PitEvidenceState.UNPAIRED_EXIT,
            ):
                self._validate_unpaired()
            else:
                self._validate_uncertain()
        return self

    def _validate_side(self, boundary: PitBoundaryEvidence) -> None:
        entry = boundary.kind == PitBoundaryKind.ENTRY
        number = self.entry_lap_number if entry else self.exit_lap_number
        timestamp = self.entry_session_time_ms if entry else self.exit_session_time_ms
        context = self.entry_context if entry else self.exit_context
        if (
            number != boundary.lap_number
            or timestamp != _boundary_time(boundary)
            or context is None
        ):
            raise ValueError(
                "Trusted side fields and context must match the supplied boundary."
            )
        _validate_boundary_context(boundary, context)

    def _validate_complete(self) -> None:
        if len(self.boundaries) != 2 or tuple(b.kind for b in self.boundaries) != (
            PitBoundaryKind.ENTRY,
            PitBoundaryKind.EXIT,
        ):
            raise ValueError("Complete evidence requires exactly entry then exit.")
        if any(
            b.evidence_status != RaceContextEvidenceStatus.AVAILABLE
            for b in self.boundaries
        ):
            raise ValueError("Complete evidence requires trusted boundaries.")
        for boundary in self.boundaries:
            self._validate_side(boundary)
        if self.entry_to_exit_elapsed_ms is None:
            raise ValueError("Complete evidence requires supplied elapsed.")
        if (
            self.exit_lap_number < self.entry_lap_number
            or self.exit_session_time_ms < self.entry_session_time_ms
        ):
            raise ValueError(
                "Complete evidence cannot reverse public lap/time chronology."
            )
        # Elapsed is independently published from exact ns, not rounded endpoints.
        for field, changed in (
            ("reported_compound", self.reported_compound_changed),
            ("reported_stint", self.reported_stint_changed),
        ):
            before = getattr(self.entry_context, field)
            after = getattr(self.exit_context, field)
            if changed is not None and (
                before is None or after is None or changed != (before != after)
            ):
                raise ValueError(
                    "Changed flags must agree with two usable reported values."
                )

    def _validate_unpaired(self) -> None:
        entry = self.state == PitEvidenceState.UNPAIRED_ENTRY
        kind = PitBoundaryKind.ENTRY if entry else PitBoundaryKind.EXIT
        if (
            len(self.boundaries) != 1
            or self.boundaries[0].kind != kind
            or self.boundaries[0].evidence_status != RaceContextEvidenceStatus.AVAILABLE
        ):
            raise ValueError(
                "Unpaired evidence requires exactly its named trusted boundary."
            )
        self._validate_side(self.boundaries[0])
        opposite = (
            (self.exit_lap_number, self.exit_session_time_ms, self.exit_context)
            if entry
            else (self.entry_lap_number, self.entry_session_time_ms, self.entry_context)
        )
        if any(value is not None for value in opposite):
            raise ValueError("Unpaired evidence cannot fabricate the opposite side.")

    def _validate_uncertain(self) -> None:
        expected = RaceContextEvidenceStatus(self.state.value)
        if any(b.evidence_status != expected for b in self.boundaries):
            raise ValueError(
                "Uncertain evidence must retain boundaries with the matching state."
            )
        if any(
            value is not None
            for value in (
                self.entry_lap_number,
                self.exit_lap_number,
                self.entry_session_time_ms,
                self.exit_session_time_ms,
            )
        ):
            raise ValueError("Uncertain evidence cannot publish trusted side fields.")
        for kind, context in (
            (PitBoundaryKind.ENTRY, self.entry_context),
            (PitBoundaryKind.EXIT, self.exit_context),
        ):
            if context is not None:
                matching = [b for b in self.boundaries if b.kind == kind]
                if len(matching) != 1:
                    raise ValueError(
                        "Transition context requires one source-associated boundary."
                    )
                _validate_boundary_context(matching[0], context)


class PitEvidenceCounts(RaceContextContractModel):
    """The five state counts must sum to total."""

    total: NonNegativeInteger
    complete: NonNegativeInteger
    unpaired_entry: NonNegativeInteger
    unpaired_exit: NonNegativeInteger
    conflicting: NonNegativeInteger
    unavailable: NonNegativeInteger

    @model_validator(mode="after")
    def validate_state_total(self) -> Self:
        if (
            self.total
            != self.complete
            + self.unpaired_entry
            + self.unpaired_exit
            + self.conflicting
            + self.unavailable
        ):
            raise ValueError("Pit state counts must sum to total.")
        return self


class SessionRaceContextParticipant(RaceContextContractModel):
    """Compact participant projection. It intentionally has no complete lap-context
    or pit-evidence collection."""

    driver: RaceContextParticipantIdentity
    classification: RaceClassificationContext
    latest_lap_context: LapCompletionContext | None
    pit_evidence_counts: PitEvidenceCounts
    unassociated_evidence_count: NonNegativeInteger

    @model_validator(mode="after")
    def validate_latest_identity(self) -> Self:
        if (
            self.latest_lap_context is not None
            and self.latest_lap_context.driver_number != self.driver.driver_number
        ):
            raise ValueError("Summary lap context must belong to the participant.")
        return self


def _participant_order_key(driver_number: str) -> tuple[int, int, str]:
    if re.fullmatch(r"[1-9][0-9]*", driver_number):
        return (0, int(driver_number), "")
    return (1, 0, driver_number)


class SessionRaceContextResponse(RaceContextContractModel):
    """Exactly one compact entry per authoritative participant, already in canonical
    participant order, projected from one central analysis."""

    context: AnalyticsSessionContext
    participants: Annotated[
        tuple[SessionRaceContextParticipant, ...],
        BeforeValidator(_require_ordered_collection),
    ] = Field(strict=False)
    source: SourceProvenance

    @model_validator(mode="after")
    def validate_participant_collection(self) -> Self:
        numbers = [p.driver.driver_number for p in self.participants]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Participant identities must be unique.")
        for previous, current in zip(numbers, numbers[1:]):
            if _participant_order_key(previous) > _participant_order_key(current):
                raise ValueError(
                    "Participants must already be in canonical identity order."
                )
        return self


def _validate_pit_collection_order(items: tuple[PitLaneEvidence, ...]) -> None:
    state_order = {state: index for index, state in enumerate(PitEvidenceState)}
    for previous, current in zip(items, items[1:]):
        previous_times = [
            _boundary_time(b)
            for b in previous.boundaries
            if _boundary_time(b) is not None
        ]
        current_times = [
            _boundary_time(b)
            for b in current.boundaries
            if _boundary_time(b) is not None
        ]
        if _validate_public_chronology(
            min(previous_times) if previous_times else None,
            min(current_times) if current_times else None,
        ):
            previous_laps = [
                b.lap_number for b in previous.boundaries if b.lap_number is not None
            ]
            current_laps = [
                b.lap_number for b in current.boundaries if b.lap_number is not None
            ]
            previous_key = (
                not previous_laps,
                min(previous_laps) if previous_laps else 0,
                state_order[previous.state],
            )
            current_key = (
                not current_laps,
                min(current_laps) if current_laps else 0,
                state_order[current.state],
            )
            if previous_key > current_key:
                raise ValueError(
                    "Chronology-less pit evidence must follow exposed lap/state order."
                )


class DriverRaceContextResponse(RaceContextContractModel):
    """Auditable driver projection from the same central analysis as the session
    resource. Lap contexts and pit evidence must already be in canonical order and
    are never silently repaired."""

    context: AnalyticsSessionContext
    participant: SessionRaceContextParticipant
    lap_contexts: Annotated[
        tuple[LapCompletionContext, ...], BeforeValidator(_require_ordered_collection)
    ] = Field(strict=False)
    pit_evidence: Annotated[
        tuple[PitLaneEvidence, ...], BeforeValidator(_require_ordered_collection)
    ] = Field(strict=False)
    source: SourceProvenance

    @model_validator(mode="after")
    def validate_driver_collections(self) -> Self:
        driver = self.participant.driver.driver_number
        if any(lap.driver_number != driver for lap in self.lap_contexts):
            raise ValueError("Lap contexts must belong to the participant.")
        numbers = [lap.lap_number for lap in self.lap_contexts]
        if any(previous >= current for previous, current in zip(numbers, numbers[1:])):
            raise ValueError("Lap contexts must be unique and already ascending.")
        if (
            self.participant.latest_lap_context is not None
            and self.participant.latest_lap_context not in self.lap_contexts
        ):
            raise ValueError(
                "Supplied summary lap must agree with the exposed lap series."
            )
        contexts = {lap.lap_number: lap for lap in self.lap_contexts}
        for evidence in self.pit_evidence:
            for boundary in evidence.boundaries:
                self._validate_reference(
                    boundary.lap_context_reference, driver, contexts
                )
            for transition in (evidence.entry_context, evidence.exit_context):
                if (
                    transition is not None
                    and transition.lap_context_reference is not None
                ):
                    self._validate_reference(
                        transition.lap_context_reference, driver, contexts
                    )
                    lap = contexts[transition.lap_context_reference.lap_number]
                    if (
                        transition.availability != lap.evidence_status
                        or transition.reported_compound != lap.reported_compound
                        or transition.reported_stint != lap.reported_stint
                    ):
                        raise ValueError(
                            "Transition facts must match the referenced completion row."
                        )
        _validate_pit_collection_order(self.pit_evidence)
        item_counts = Counter(item.state for item in self.pit_evidence)
        supplied = self.participant.pit_evidence_counts
        if supplied.total != len(self.pit_evidence) or any(
            getattr(supplied, state.value) != item_counts[state]
            for state in PitEvidenceState
        ):
            raise ValueError(
                "Summary counts must match actual pit evidence items by state."
            )
        return self

    @staticmethod
    def _validate_reference(
        reference: LapContextReference | None,
        driver: str,
        contexts: dict[int, LapCompletionContext],
    ) -> None:
        if reference is not None and (
            reference.driver_number != driver or reference.lap_number not in contexts
        ):
            raise ValueError(
                "Pit references must identify an exposed lap of this participant."
            )
