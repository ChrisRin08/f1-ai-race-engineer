import ast
import inspect
from dataclasses import FrozenInstanceError, fields, replace
from itertools import permutations

import pytest

import app.analytics.race_context_analytics as race_analytics
from app.analytics.race_context_analytics import (
    EqualDistanceTimeDeficitStatus,
    EvidenceStatus,
    NormalizedTrackStatus,
    NormalizedTrackStatusEvidence,
    NormalizedValue,
    NormalizedValueState,
    PitBoundaryKind,
    PitEvidenceState,
    RaceContextAvailability,
    RaceContextInput,
    RaceContextLapRowInput,
    RaceContextParticipantIdentity,
    RaceContextParticipantInput,
    TrackStatusAvailability,
    analyze_complete_pit_visits,
    analyze_lap_contexts,
    analyze_pit_evidence,
)


def _value(value: int | None) -> NormalizedValue:
    if value is None:
        return NormalizedValue(NormalizedValueState.ABSENT)
    return NormalizedValue(NormalizedValueState.AVAILABLE, value)


def _track_status(
    *statuses: NormalizedTrackStatus,
    availability: TrackStatusAvailability = TrackStatusAvailability.AVAILABLE,
    is_disrupted: bool | None = False,
) -> NormalizedTrackStatusEvidence:
    return NormalizedTrackStatusEvidence(availability, statuses, is_disrupted)


GREEN = _track_status(NormalizedTrackStatus.GREEN)
UNAVAILABLE_TRACK_STATUS = _track_status(
    availability=TrackStatusAvailability.UNAVAILABLE,
    is_disrupted=None,
)


def _participant(driver_number: str) -> RaceContextParticipantInput:
    return RaceContextParticipantInput(
        identity=RaceContextParticipantIdentity(driver_number),
        result_evidence_count=1,
        result_evidence_status=EvidenceStatus.AVAILABLE,
        finish_position=None,
        classified_position=None,
        classification_status=None,
        completed_laps=None,
    )


def _row(
    driver_number: str | None,
    lap_number: int | None,
    *,
    source_occurrence: int = 1,
    completion_time_ns: int | None = 10_000_000,
    completion_position: int | None = 2,
    track_status: NormalizedTrackStatusEvidence = GREEN,
    provider_generated: bool | None = False,
    reported_compound: str | None = "MEDIUM",
    reported_stint: int | None = 1,
    pit_entry_time_ns: int | None = None,
    pit_exit_time_ns: int | None = None,
) -> RaceContextLapRowInput:
    return RaceContextLapRowInput(
        source_occurrence=source_occurrence,
        driver_number=driver_number,
        lap_number=_value(lap_number),
        lap_completion_time_ns=_value(completion_time_ns),
        lap_completion_position=_value(completion_position),
        pit_entry_time_ns=_value(pit_entry_time_ns),
        pit_exit_time_ns=_value(pit_exit_time_ns),
        track_status=track_status,
        provider_generated=provider_generated,
        reported_compound=reported_compound,
        reported_stint=reported_stint,
    )


def _input(
    rows: tuple[RaceContextLapRowInput, ...],
    *,
    drivers: tuple[str, ...] = ("1", "4"),
    unassociated_row_count: int = 0,
) -> RaceContextInput:
    return RaceContextInput(
        participants=tuple(_participant(driver) for driver in drivers),
        lap_rows=rows,
        unassociated_row_count=unassociated_row_count,
    )


def _contexts_by_identity(analysis):
    return {
        (context.driver_number, context.lap_number): context
        for context in analysis.lap_contexts
    }


def _complete_pit_visits(race_context: RaceContextInput, driver_number: str = "4"):
    lap_analysis = analyze_lap_contexts(race_context)
    return analyze_complete_pit_visits(
        race_context,
        lap_analysis.lap_contexts,
        driver_number,
    )


def _pit_evidence(race_context: RaceContextInput, driver_number: str = "4"):
    lap_analysis = analyze_lap_contexts(race_context)
    return analyze_pit_evidence(
        race_context,
        lap_analysis.lap_contexts,
        driver_number,
    )


def _assert_no_pit_elapsed(evidence):
    assert evidence.entry_to_exit_elapsed_ns is None
    assert evidence.entry_to_exit_elapsed_ms is None


def _assert_derived_context_unavailable(context):
    assert context.leader_reference is None
    assert context.laps_behind_status is RaceContextAvailability.UNAVAILABLE
    assert context.laps_behind is None
    assert (
        context.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.UNAVAILABLE
    )
    assert context.equal_distance_time_deficit_ns is None
    assert context.equal_distance_time_deficit_ms is None


def test_consolidation_uses_only_authoritative_driver_and_valid_lap_identity():
    analysis = analyze_lap_contexts(
        _input(
            (
                _row("4", 2),
                _row("99", 2, source_occurrence=2),
                _row("4", None, source_occurrence=3),
            ),
            unassociated_row_count=1,
        )
    )

    assert [(lap.driver_number, lap.lap_number) for lap in analysis.lap_contexts] == [
        ("4", 2)
    ]
    assert analysis.lap_contexts[0].source_evidence_count == 1


def test_roster_orphans_and_participant_invalid_laps_remain_separate():
    analysis = analyze_lap_contexts(
        _input(
            (
                _row("1", 2),
                _row("4", None, source_occurrence=2),
                _row("99", 2, source_occurrence=3),
            ),
            unassociated_row_count=1,
        )
    )

    assert analysis.roster_orphan_row_count == 1
    assert [
        (count.driver_number, count.invalid_lap_identity_count)
        for count in analysis.invalid_lap_identity_counts
    ] == [("1", 0), ("4", 1)]


def test_invalid_lap_counts_are_per_driver_canonical_and_order_independent():
    rows = (
        _row("10", None, source_occurrence=1),
        _row("2", None, source_occurrence=2),
        _row("10", None, source_occurrence=3),
        _row("2", 1, source_occurrence=4),
        _row("99", None, source_occurrence=5),
    )

    analyses = tuple(
        analyze_lap_contexts(
            _input(
                ordered_rows,
                drivers=("10", "2"),
                unassociated_row_count=1,
            )
        )
        for ordered_rows in (rows, tuple(reversed(rows)))
    )

    assert analyses[0] == analyses[1]
    assert analyses[0].roster_orphan_row_count == 1
    assert [
        (count.driver_number, count.invalid_lap_identity_count)
        for count in analyses[0].invalid_lap_identity_counts
    ] == [("2", 1), ("10", 2)]
    assert [
        (lap.driver_number, lap.lap_number) for lap in analyses[0].lap_contexts
    ] == [("2", 1)]


def test_exact_duplicates_keep_multiplicity_without_using_source_occurrence():
    first = _row("4", 2, source_occurrence=9)
    duplicate = _row("4", 2, source_occurrence=9)

    context = analyze_lap_contexts(_input((first, duplicate))).lap_contexts[0]

    assert context.source_evidence_count == 2
    assert context.evidence_status is EvidenceStatus.AVAILABLE
    assert context.completion_time_ns == 10_000_000
    assert context.reported_compound == "MEDIUM"


@pytest.mark.parametrize(
    "changed_row,affected_field,expected",
    [
        (_row("4", 2, completion_time_ns=11_000_000), "completion_time_ns", None),
        (_row("4", 2, completion_time_ns=None), "completion_time_ns", None),
        (_row("4", 2, completion_position=3), "completion_position", None),
        (_row("4", 2, provider_generated=True), "provider_generated", None),
        (_row("4", 2, reported_compound="HARD"), "reported_compound", None),
        (_row("4", 2, reported_stint=2), "reported_stint", None),
        (
            _row(
                "4",
                2,
                track_status=_track_status(
                    NormalizedTrackStatus.YELLOW, is_disrupted=True
                ),
            ),
            "track_status",
            UNAVAILABLE_TRACK_STATUS,
        ),
    ],
)
def test_contradictory_duplicates_suppress_only_the_affected_fact(
    changed_row, affected_field, expected
):
    context = analyze_lap_contexts(_input((_row("4", 2), changed_row))).lap_contexts[0]

    assert context.evidence_status is EvidenceStatus.CONFLICTING
    assert getattr(context, affected_field) == expected
    if affected_field != "completion_time_ns":
        assert context.completion_time_ns == 10_000_000
        assert context.completion_time_ms == 10


@pytest.mark.parametrize(
    "track_status",
    [
        _track_status(NormalizedTrackStatus.GREEN),
        _track_status(NormalizedTrackStatus.YELLOW, is_disrupted=True),
        _track_status(NormalizedTrackStatus.SAFETY_CAR, is_disrupted=True),
        _track_status(NormalizedTrackStatus.VIRTUAL_SAFETY_CAR, is_disrupted=True),
        _track_status(
            NormalizedTrackStatus.VIRTUAL_SAFETY_CAR_ENDING,
            is_disrupted=True,
        ),
        _track_status(NormalizedTrackStatus.RED_FLAG, is_disrupted=True),
        _track_status(
            NormalizedTrackStatus.GREEN,
            NormalizedTrackStatus.YELLOW,
            NormalizedTrackStatus.UNKNOWN,
            is_disrupted=True,
        ),
        _track_status(NormalizedTrackStatus.UNKNOWN, is_disrupted=None),
        UNAVAILABLE_TRACK_STATUS,
    ],
)
def test_consolidation_preserves_already_normalized_track_status(track_status):
    context = analyze_lap_contexts(
        _input(
            (
                _row("4", 2, track_status=track_status),
                _row("4", 2, source_occurrence=2, track_status=track_status),
            )
        )
    ).lap_contexts[0]

    assert context.track_status == track_status
    assert context.source_evidence_count == 2


def test_unique_position_one_establishes_same_lap_leader_and_positive_deficit():
    analysis = analyze_lap_contexts(
        _input(
            (
                _row("1", 3, completion_time_ns=100_000_000, completion_position=1),
                _row("4", 3, completion_time_ns=102_500_000, completion_position=2),
            )
        )
    )
    selected = _contexts_by_identity(analysis)[("4", 3)]

    assert selected.leader_reference.driver_number == "1"
    assert selected.leader_reference.lap_number == 3
    assert selected.laps_behind_status is RaceContextAvailability.AVAILABLE
    assert selected.laps_behind == 0
    assert (
        selected.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.AVAILABLE
    )
    assert selected.equal_distance_time_deficit_ns == 2_500_000
    assert selected.equal_distance_time_deficit_ms == 3


def test_equal_completion_timestamps_produce_zero_deficit():
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 3, completion_time_ns=100, completion_position=1),
                    _row("4", 3, completion_time_ns=100, completion_position=2),
                )
            )
        )
    )[("4", 3)]

    assert selected.laps_behind == 0
    assert selected.equal_distance_time_deficit_ns == 0
    assert selected.equal_distance_time_deficit_ms == 0


def test_negative_driver_minus_leader_time_is_unavailable_not_clamped():
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 3, completion_time_ns=200, completion_position=1),
                    _row("4", 3, completion_time_ns=100, completion_position=2),
                )
            )
        )
    )[("4", 3)]

    assert selected.leader_reference is None
    assert selected.laps_behind_status is RaceContextAvailability.UNAVAILABLE
    assert selected.laps_behind is None
    assert (
        selected.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.UNAVAILABLE
    )
    assert selected.equal_distance_time_deficit_ns is None
    assert selected.equal_distance_time_deficit_ms is None


@pytest.mark.parametrize(
    "leader_rows",
    [
        (_row("1", 3, completion_position=2),),
        (
            _row("1", 3, completion_position=1),
            _row("7", 3, source_occurrence=2, completion_position=1),
        ),
        (
            _row("1", 3, completion_position=1),
            _row("1", 3, source_occurrence=2, completion_position=2),
        ),
        (_row("1", 3, completion_time_ns=None, completion_position=1),),
        (_row("1", 3, completion_position=1, provider_generated=True),),
        (_row("1", 3, completion_position=1, provider_generated=None),),
    ],
)
def test_missing_duplicate_conflicting_or_unusable_leader_is_not_inferred(
    leader_rows,
):
    drivers = ("1", "4", "7")
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                leader_rows
                + (
                    _row(
                        "4",
                        3,
                        source_occurrence=10,
                        completion_time_ns=20_000_000,
                        completion_position=2,
                    ),
                ),
                drivers=drivers,
            )
        )
    )[("4", 3)]

    assert selected.leader_reference is None
    assert selected.laps_behind_status is RaceContextAvailability.UNAVAILABLE
    assert selected.laps_behind is None
    assert (
        selected.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.UNAVAILABLE
    )
    assert selected.equal_distance_time_deficit_ms is None


def test_one_trusted_leader_is_not_displaced_by_generated_position_one_evidence():
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 3, completion_time_ns=100, completion_position=1),
                    _row(
                        "7",
                        3,
                        source_occurrence=2,
                        completion_time_ns=110,
                        completion_position=1,
                        provider_generated=True,
                    ),
                    _row(
                        "4",
                        3,
                        source_occurrence=3,
                        completion_time_ns=200,
                        completion_position=2,
                    ),
                ),
                drivers=("1", "4", "7"),
            )
        )
    )[("4", 3)]

    assert selected.leader_reference.driver_number == "1"
    assert selected.laps_behind == 0
    assert selected.equal_distance_time_deficit_ns == 100


def test_unrelated_source_conflict_does_not_erase_trusted_timing_derivatives():
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 3, completion_time_ns=100, completion_position=1),
                    _row(
                        "4",
                        3,
                        source_occurrence=2,
                        completion_time_ns=200,
                        completion_position=2,
                        reported_compound="MEDIUM",
                    ),
                    _row(
                        "4",
                        3,
                        source_occurrence=3,
                        completion_time_ns=200,
                        completion_position=2,
                        reported_compound="HARD",
                    ),
                )
            )
        )
    )[("4", 3)]

    assert selected.evidence_status is EvidenceStatus.CONFLICTING
    assert selected.reported_compound is None
    assert selected.completion_time_ns == 200
    assert selected.laps_behind == 0
    assert selected.equal_distance_time_deficit_ns == 100


def test_disrupted_status_does_not_suppress_trustworthy_completion():
    yellow = _track_status(NormalizedTrackStatus.YELLOW, is_disrupted=True)
    analysis = analyze_lap_contexts(
        _input(
            (
                _row(
                    "1",
                    3,
                    completion_time_ns=100,
                    completion_position=1,
                    track_status=yellow,
                ),
                _row(
                    "4",
                    3,
                    source_occurrence=2,
                    completion_time_ns=200,
                    completion_position=2,
                    track_status=yellow,
                ),
            )
        )
    )
    selected = _contexts_by_identity(analysis)[("4", 3)]

    assert selected.track_status == yellow
    assert selected.leader_reference.driver_number == "1"
    assert selected.leader_reference.lap_number == 3
    assert selected.laps_behind == 0
    assert (
        selected.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.AVAILABLE
    )
    assert selected.equal_distance_time_deficit_ns == 100


def test_invalid_completion_evidence_remains_unavailable():
    invalid = replace(
        _row("4", 2),
        lap_completion_time_ns=NormalizedValue(NormalizedValueState.INVALID),
    )

    context = analyze_lap_contexts(_input((invalid,))).lap_contexts[0]

    assert context.evidence_status is EvidenceStatus.UNAVAILABLE
    assert context.completion_time_ns is None
    assert context.completion_time_ms is None
    assert context.laps_behind_status is RaceContextAvailability.UNAVAILABLE
    assert (
        context.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.UNAVAILABLE
    )
    assert context.equal_distance_time_deficit_ms is None


def test_unusable_selected_completion_withholds_all_derived_context():
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 3, completion_time_ns=100, completion_position=1),
                    _row("4", 3, completion_time_ns=None, completion_position=2),
                )
            )
        )
    )[("4", 3)]

    assert selected.completion_time_ns is None
    assert selected.leader_reference is None
    assert selected.laps_behind_status is RaceContextAvailability.UNAVAILABLE
    assert selected.laps_behind is None
    assert (
        selected.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.UNAVAILABLE
    )


def test_ambiguous_latest_leader_lap_blocks_earlier_trusted_reference():
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 4, completion_time_ns=300, completion_position=1),
                    _row("1", 5, completion_time_ns=400, completion_position=1),
                    _row(
                        "7",
                        5,
                        source_occurrence=2,
                        completion_time_ns=410,
                        completion_position=1,
                    ),
                    _row(
                        "4",
                        3,
                        source_occurrence=3,
                        completion_time_ns=500,
                        completion_position=2,
                    ),
                ),
                drivers=("1", "4", "7"),
            )
        )
    )[("4", 3)]

    assert selected.leader_reference is None
    assert selected.laps_behind_status is RaceContextAvailability.UNAVAILABLE
    assert selected.laps_behind is None


def test_later_lap_without_unique_leader_blocks_older_leader_fallback():
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 4, completion_time_ns=300, completion_position=1),
                    _row(
                        "7",
                        5,
                        source_occurrence=2,
                        completion_time_ns=400,
                        completion_position=2,
                    ),
                    _row(
                        "4",
                        3,
                        source_occurrence=3,
                        completion_time_ns=500,
                        completion_position=2,
                    ),
                ),
                drivers=("1", "4", "7"),
            )
        )
    )[("4", 3)]

    assert selected.leader_reference is None
    assert selected.laps_behind_status is RaceContextAvailability.UNAVAILABLE
    assert selected.laps_behind is None
    assert (
        selected.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.UNAVAILABLE
    )
    assert selected.equal_distance_time_deficit_ns is None
    assert selected.equal_distance_time_deficit_ms is None


@pytest.mark.parametrize(
    "later_rows",
    [
        (
            _row(
                "7",
                5,
                source_occurrence=2,
                completion_time_ns=400,
                completion_position=1,
            ),
            _row(
                "7",
                5,
                source_occurrence=3,
                completion_time_ns=400,
                completion_position=2,
            ),
        ),
        (
            _row(
                "7",
                5,
                source_occurrence=2,
                completion_time_ns=400,
                completion_position=1,
            ),
            _row(
                "7",
                5,
                source_occurrence=3,
                completion_time_ns=450,
                completion_position=1,
            ),
        ),
        (
            _row(
                "7",
                5,
                source_occurrence=2,
                completion_time_ns=400,
                completion_position=1,
                provider_generated=False,
            ),
            _row(
                "7",
                5,
                source_occurrence=3,
                completion_time_ns=400,
                completion_position=1,
                provider_generated=True,
            ),
        ),
    ],
    ids=("position-conflict", "completion-time-conflict", "generated-conflict"),
)
def test_later_relevant_leader_conflict_blocks_older_leader_fallback(later_rows):
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 4, completion_time_ns=300, completion_position=1),
                    *later_rows,
                    _row(
                        "4",
                        3,
                        source_occurrence=4,
                        completion_time_ns=500,
                        completion_position=2,
                    ),
                ),
                drivers=("1", "4", "7"),
            )
        )
    )[("4", 3)]

    _assert_derived_context_unavailable(selected)


def test_generated_only_later_evidence_does_not_displace_older_leader():
    analysis = analyze_lap_contexts(
        _input(
            (
                _row("1", 4, completion_time_ns=300, completion_position=1),
                _row(
                    "7",
                    5,
                    source_occurrence=2,
                    completion_time_ns=400,
                    completion_position=1,
                    provider_generated=True,
                ),
                _row(
                    "4",
                    3,
                    source_occurrence=3,
                    completion_time_ns=500,
                    completion_position=2,
                ),
            ),
            drivers=("1", "4", "7"),
        )
    )
    selected = _contexts_by_identity(analysis)[("4", 3)]
    generated = _contexts_by_identity(analysis)[("7", 5)]

    assert generated.provider_generated is True
    assert generated.completion_time_ns == 400
    assert selected.leader_reference.driver_number == "1"
    assert selected.leader_reference.lap_number == 4
    assert selected.laps_behind == 1
    assert (
        selected.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.NOT_APPLICABLE
    )


@pytest.mark.parametrize(
    "generated_states,expected_state,expected_evidence_status,trusts_completion",
    [
        ((False, False), False, EvidenceStatus.AVAILABLE, True),
        ((True, True), True, EvidenceStatus.AVAILABLE, False),
        ((None, None), None, EvidenceStatus.AVAILABLE, False),
        ((False, True), None, EvidenceStatus.CONFLICTING, False),
        ((False, None), None, EvidenceStatus.CONFLICTING, False),
        ((True, None), None, EvidenceStatus.CONFLICTING, False),
    ],
)
def test_duplicate_generated_state_matrix_is_order_independent(
    generated_states,
    expected_state,
    expected_evidence_status,
    trusts_completion,
):
    duplicate_rows = tuple(
        _row(
            "4",
            3,
            source_occurrence=occurrence,
            completion_time_ns=200,
            completion_position=2,
            provider_generated=generated_state,
        )
        for occurrence, generated_state in zip((2, 99), generated_states, strict=True)
    )
    analyses = tuple(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 3, completion_time_ns=100, completion_position=1),
                    *ordered_duplicates,
                )
            )
        )
        for ordered_duplicates in (duplicate_rows, tuple(reversed(duplicate_rows)))
    )
    selected = _contexts_by_identity(analyses[0])[("4", 3)]

    assert analyses[0] == analyses[1]
    assert selected.source_evidence_count == 2
    assert selected.provider_generated is expected_state
    assert selected.evidence_status is expected_evidence_status
    if trusts_completion:
        assert selected.laps_behind == 0
        assert selected.equal_distance_time_deficit_ns == 100
    else:
        _assert_derived_context_unavailable(selected)


@pytest.mark.parametrize(
    "latest_leader_lap,expected_laps_behind",
    [(3, 0), (4, 1), (5, 2)],
)
def test_laps_behind_uses_greatest_leader_lap_completed_at_selected_time(
    latest_leader_lap, expected_laps_behind
):
    leader_rows = tuple(
        _row(
            "1",
            lap,
            source_occurrence=lap,
            completion_time_ns=lap * 100,
            completion_position=1,
        )
        for lap in range(3, latest_leader_lap + 1)
    )
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                leader_rows
                + (
                    _row(
                        "4",
                        3,
                        source_occurrence=20,
                        completion_time_ns=latest_leader_lap * 100,
                        completion_position=2,
                    ),
                )
            )
        )
    )[("4", 3)]

    assert selected.laps_behind_status is RaceContextAvailability.AVAILABLE
    assert selected.laps_behind == expected_laps_behind
    assert selected.leader_reference.lap_number == latest_leader_lap
    if expected_laps_behind:
        assert (
            selected.equal_distance_time_deficit_status
            is EqualDistanceTimeDeficitStatus.NOT_APPLICABLE
        )
        assert selected.equal_distance_time_deficit_ns is None


def test_future_leader_completion_is_not_interpolated_or_predicted():
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 4, completion_time_ns=300, completion_position=1),
                    _row(
                        "1",
                        5,
                        source_occurrence=2,
                        completion_time_ns=500,
                        completion_position=1,
                    ),
                    _row(
                        "4",
                        3,
                        source_occurrence=3,
                        completion_time_ns=400,
                        completion_position=2,
                    ),
                )
            )
        )
    )[("4", 3)]

    assert selected.leader_reference.lap_number == 4
    assert selected.laps_behind == 1
    assert (
        selected.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.NOT_APPLICABLE
    )


def test_negative_leader_lap_difference_is_unavailable_not_clamped():
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 4, completion_time_ns=400, completion_position=1),
                    _row("4", 5, completion_time_ns=500, completion_position=2),
                )
            )
        )
    )[("4", 5)]

    assert selected.leader_reference is None
    assert selected.laps_behind_status is RaceContextAvailability.UNAVAILABLE
    assert selected.laps_behind is None
    assert (
        selected.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.UNAVAILABLE
    )


@pytest.mark.parametrize("provider_generated", [True, None])
def test_generated_or_unasserted_generation_state_never_establishes_completion(
    provider_generated,
):
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 3, completion_time_ns=100, completion_position=1),
                    _row(
                        "4",
                        3,
                        completion_time_ns=200,
                        completion_position=2,
                        provider_generated=provider_generated,
                        track_status=_track_status(
                            NormalizedTrackStatus.YELLOW, is_disrupted=True
                        ),
                        reported_compound="SOFT",
                        reported_stint=3,
                    ),
                )
            )
        )
    )[("4", 3)]

    assert selected.completion_time_ns == 200
    assert selected.completion_time_ms == 0
    assert selected.completion_position == 2
    assert selected.source_evidence_count == 1
    assert selected.track_status.statuses == (NormalizedTrackStatus.YELLOW,)
    assert selected.reported_compound == "SOFT"
    assert selected.reported_stint == 3
    assert selected.provider_generated is provider_generated
    assert selected.leader_reference is None
    assert selected.laps_behind_status is RaceContextAvailability.UNAVAILABLE
    assert (
        selected.equal_distance_time_deficit_status
        is EqualDistanceTimeDeficitStatus.UNAVAILABLE
    )


@pytest.mark.parametrize(
    "exact_ns,expected_ms",
    [
        (499_999, 0),
        (500_000, 1),
        (500_001, 1),
        (1_499_999, 1),
        (1_500_000, 2),
    ],
)
def test_session_time_publication_uses_integer_half_up(exact_ns, expected_ms):
    context = analyze_lap_contexts(
        _input((_row("4", 1, completion_time_ns=exact_ns),))
    ).lap_contexts[0]

    assert context.completion_time_ns == exact_ns
    assert context.completion_time_ms == expected_ms


@pytest.mark.parametrize(
    "deficit_ns,expected_ms",
    [(499_999, 0), (500_000, 1), (500_001, 1)],
)
def test_deficit_publication_uses_integer_half_up(deficit_ns, expected_ms):
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row("1", 1, completion_time_ns=1_000_000, completion_position=1),
                    _row(
                        "4",
                        1,
                        completion_time_ns=1_000_000 + deficit_ns,
                        completion_position=2,
                    ),
                )
            )
        )
    )[("4", 1)]

    assert selected.equal_distance_time_deficit_ns == deficit_ns
    assert selected.equal_distance_time_deficit_ms == expected_ms


def test_exact_endpoints_are_subtracted_before_publication():
    selected = _contexts_by_identity(
        analyze_lap_contexts(
            _input(
                (
                    _row(
                        "1",
                        1,
                        completion_time_ns=1_499_999,
                        completion_position=1,
                    ),
                    _row(
                        "4",
                        1,
                        completion_time_ns=1_500_000,
                        completion_position=2,
                    ),
                )
            )
        )
    )[("4", 1)]

    assert selected.leader_reference.completion_time_ms == 1
    assert selected.completion_time_ms == 2
    assert selected.equal_distance_time_deficit_ns == 1
    assert selected.equal_distance_time_deficit_ms == 0


def test_source_row_permutations_and_occurrence_values_do_not_change_analysis():
    facts = (
        _row(
            "1", 1, source_occurrence=99, completion_time_ns=100, completion_position=1
        ),
        _row(
            "4", 1, source_occurrence=1, completion_time_ns=201, completion_position=2
        ),
        _row(
            "4", 1, source_occurrence=1, completion_time_ns=200, completion_position=2
        ),
        _row(
            "4", 2, source_occurrence=2, completion_time_ns=300, completion_position=2
        ),
    )

    analyses = [analyze_lap_contexts(_input(rows)) for rows in permutations(facts)]

    assert all(analysis == analyses[0] for analysis in analyses[1:])


@pytest.mark.parametrize(
    "duplicate_rows",
    [
        (
            _row("4", 2, source_occurrence=1, track_status=GREEN),
            _row(
                "4",
                2,
                source_occurrence=2,
                track_status=_track_status(
                    NormalizedTrackStatus.YELLOW,
                    is_disrupted=True,
                ),
            ),
        ),
        (
            _row("4", 2, source_occurrence=1, completion_position=1),
            _row("4", 2, source_occurrence=2, completion_position=2),
        ),
        (
            _row("4", 2, source_occurrence=1, provider_generated=False),
            _row("4", 2, source_occurrence=2, provider_generated=True),
        ),
        (
            _row("4", 2, source_occurrence=1),
            _row("4", 2, source_occurrence=99),
        ),
    ],
    ids=(
        "track-status-conflict",
        "position-conflict",
        "generated-conflict",
        "exact-duplicate-different-occurrences",
    ),
)
def test_duplicate_fact_permutations_produce_identical_context(duplicate_rows):
    analyses = tuple(
        analyze_lap_contexts(_input(ordered_rows))
        for ordered_rows in permutations(duplicate_rows)
    )

    assert all(analysis == analyses[0] for analysis in analyses[1:])


def test_lap_contexts_follow_canonical_driver_then_lap_order():
    analysis = analyze_lap_contexts(
        _input(
            (
                _row("RESERVE", 2),
                _row("10", 2),
                _row("2", 3),
                _row("2", 1),
            ),
            drivers=("RESERVE", "10", "2"),
        )
    )

    assert [
        (context.driver_number, context.lap_number) for context in analysis.lap_contexts
    ] == [("2", 1), ("2", 3), ("10", 2), ("RESERVE", 2)]


def test_three_identical_executions_are_structurally_equal():
    normalized_input = _input(
        (
            _row("1", 1, completion_time_ns=100, completion_position=1),
            _row("4", 1, completion_time_ns=200, completion_position=2),
        )
    )

    analyses = tuple(analyze_lap_contexts(normalized_input) for _ in range(3))

    assert analyses[0] == analyses[1] == analyses[2]


def test_complete_pit_visit_uses_exact_boundaries_and_same_row_context():
    visits = _complete_pit_visits(
        _input(
            (
                _row(
                    "4",
                    8,
                    source_occurrence=20,
                    completion_time_ns=80_000_000,
                    reported_compound="MEDIUM",
                    reported_stint=1,
                    pit_entry_time_ns=1_499_999,
                ),
                _row(
                    "4",
                    10,
                    source_occurrence=3,
                    completion_time_ns=100_000_000,
                    reported_compound="HARD",
                    reported_stint=2,
                    pit_exit_time_ns=1_500_000,
                ),
            )
        )
    )

    assert len(visits) == 1
    visit = visits[0]
    assert visit.state is PitEvidenceState.COMPLETE
    assert tuple(boundary.kind for boundary in visit.boundaries) == (
        PitBoundaryKind.ENTRY,
        PitBoundaryKind.EXIT,
    )
    assert tuple(boundary.source_evidence_count for boundary in visit.boundaries) == (
        1,
        1,
    )
    assert visit.source_boundary_count == 2
    assert visit.entry_lap_number == 8
    assert visit.exit_lap_number == 10
    assert visit.entry_session_time_ns == 1_499_999
    assert visit.entry_session_time_ms == 1
    assert visit.exit_session_time_ns == 1_500_000
    assert visit.exit_session_time_ms == 2
    assert visit.entry_to_exit_elapsed_ns == 1
    assert visit.entry_to_exit_elapsed_ms == 0
    assert visit.entry_context.lap_context_reference.driver_number == "4"
    assert visit.entry_context.lap_context_reference.lap_number == 8
    assert visit.boundaries[0].lap_context_reference.lap_number == 8
    assert visit.entry_context.reported_compound == "MEDIUM"
    assert visit.entry_context.reported_stint == 1
    assert visit.exit_context.lap_context_reference.driver_number == "4"
    assert visit.exit_context.lap_context_reference.lap_number == 10
    assert visit.boundaries[1].lap_context_reference.lap_number == 10
    assert visit.exit_context.reported_compound == "HARD"
    assert visit.exit_context.reported_stint == 2
    assert visit.reported_compound_changed is True
    assert visit.reported_stint_changed is True


def test_complete_visits_are_canonical_without_row_or_lap_adjacency():
    rows = (
        _row(
            "4",
            2,
            source_occurrence=50,
            completion_time_ns=20_000_000,
            pit_entry_time_ns=100_000_000,
        ),
        _row("4", 3, source_occurrence=1, completion_time_ns=30_000_000),
        _row(
            "4",
            4,
            source_occurrence=40,
            completion_time_ns=40_000_000,
            pit_exit_time_ns=200_000_000,
        ),
        _row(
            "4",
            8,
            source_occurrence=30,
            completion_time_ns=80_000_000,
            pit_entry_time_ns=500_000_000,
        ),
        _row(
            "4",
            9,
            source_occurrence=2,
            completion_time_ns=90_000_000,
            pit_exit_time_ns=700_000_000,
        ),
    )
    ordered_inputs = (
        rows,
        tuple(reversed(rows)),
        (rows[3], rows[1], rows[4], rows[0], rows[2]),
    )

    analyses = tuple(
        _complete_pit_visits(_input(ordered_rows)) for ordered_rows in ordered_inputs
    )

    assert analyses[0] == analyses[1] == analyses[2]
    assert [visit.entry_session_time_ns for visit in analyses[0]] == [
        100_000_000,
        500_000_000,
    ]
    assert [visit.exit_session_time_ns for visit in analyses[0]] == [
        200_000_000,
        700_000_000,
    ]
    assert [
        (visit.entry_lap_number, visit.exit_lap_number) for visit in analyses[0]
    ] == [(2, 4), (8, 9)]
    assert [visit.source_boundary_count for visit in analyses[0]] == [2, 2]


def test_participant_without_pit_boundaries_has_no_complete_visit():
    race_context = _input((_row("4", 2),))

    lap_analysis = analyze_lap_contexts(race_context)
    visits = analyze_complete_pit_visits(
        race_context,
        lap_analysis.lap_contexts,
        "4",
    )

    assert ("4", 2) in _contexts_by_identity(lap_analysis)
    assert visits == ()


def test_equal_reported_transition_values_are_preserved_as_unchanged():
    visits = _complete_pit_visits(
        _input(
            (
                _row(
                    "4",
                    12,
                    reported_compound="HARD",
                    reported_stint=3,
                    pit_entry_time_ns=1_000_000,
                ),
                _row(
                    "4",
                    13,
                    source_occurrence=2,
                    reported_compound="HARD",
                    reported_stint=3,
                    pit_exit_time_ns=2_000_000,
                ),
            )
        )
    )

    visit = visits[0]
    assert visit.entry_context.reported_compound == "HARD"
    assert visit.exit_context.reported_compound == "HARD"
    assert visit.entry_context.reported_stint == 3
    assert visit.exit_context.reported_stint == 3
    assert visit.reported_compound_changed is False
    assert visit.reported_stint_changed is False


def test_unavailable_transition_values_do_not_use_nearby_lap_context():
    visits = _complete_pit_visits(
        _input(
            (
                _row(
                    "4",
                    4,
                    reported_compound="SOFT",
                    reported_stint=9,
                ),
                _row(
                    "4",
                    5,
                    source_occurrence=2,
                    completion_time_ns=None,
                    reported_compound=None,
                    reported_stint=1,
                    pit_entry_time_ns=1_000_000,
                ),
                _row(
                    "4",
                    8,
                    source_occurrence=3,
                    reported_compound="HARD",
                    reported_stint=None,
                    pit_exit_time_ns=3_000_000,
                ),
                _row(
                    "4",
                    9,
                    source_occurrence=4,
                    reported_compound="WET",
                    reported_stint=4,
                ),
            )
        )
    )

    visit = visits[0]
    assert visit.state is PitEvidenceState.COMPLETE
    assert visit.entry_context.availability is EvidenceStatus.UNAVAILABLE
    assert visit.entry_context.lap_context_reference.lap_number == 5
    assert visit.entry_context.reported_compound is None
    assert visit.entry_context.reported_stint == 1
    assert visit.exit_context.availability is EvidenceStatus.AVAILABLE
    assert visit.exit_context.lap_context_reference.lap_number == 8
    assert visit.exit_context.reported_compound == "HARD"
    assert visit.exit_context.reported_stint is None
    assert visit.reported_compound_changed is None
    assert visit.reported_stint_changed is None


def test_transition_values_reuse_same_lap_consolidated_conflict():
    rows = (
        _row(
            "4",
            4,
            reported_compound="WET",
            reported_stint=9,
        ),
        _row(
            "4",
            5,
            source_occurrence=2,
            reported_compound="SOFT",
            reported_stint=1,
            pit_entry_time_ns=1_000_000,
        ),
        _row(
            "4",
            5,
            source_occurrence=3,
            reported_compound="HARD",
            reported_stint=2,
        ),
        _row(
            "4",
            7,
            source_occurrence=4,
            reported_compound="MEDIUM",
            reported_stint=3,
            pit_exit_time_ns=3_000_000,
        ),
    )
    analyses = []
    visits_by_order = []
    for ordered_rows in (rows, tuple(reversed(rows))):
        race_context = _input(ordered_rows)
        lap_analysis = analyze_lap_contexts(race_context)
        analyses.append(lap_analysis)
        visits_by_order.append(
            analyze_complete_pit_visits(
                race_context,
                lap_analysis.lap_contexts,
                "4",
            )
        )

    entry_lap = _contexts_by_identity(analyses[0])[("4", 5)]
    assert entry_lap.evidence_status is EvidenceStatus.CONFLICTING
    assert entry_lap.reported_compound is None
    assert entry_lap.reported_stint is None
    assert visits_by_order[0] == visits_by_order[1]
    assert len(visits_by_order[0]) == 1
    visit = visits_by_order[0][0]
    assert visit.state is PitEvidenceState.COMPLETE
    assert visit.entry_context.availability is EvidenceStatus.CONFLICTING
    assert visit.entry_context.lap_context_reference.driver_number == "4"
    assert visit.entry_context.lap_context_reference.lap_number == 5
    assert visit.entry_context.reported_compound is None
    assert visit.entry_context.reported_stint is None
    assert visit.reported_compound_changed is None
    assert visit.reported_stint_changed is None


@pytest.mark.parametrize("provider_generated", [True, None])
def test_generated_or_unasserted_boundaries_do_not_establish_complete_visit(
    provider_generated,
):
    visits = _complete_pit_visits(
        _input(
            (
                _row(
                    "4",
                    5,
                    provider_generated=provider_generated,
                    pit_entry_time_ns=1_000_000,
                ),
                _row(
                    "4",
                    6,
                    source_occurrence=2,
                    pit_exit_time_ns=2_000_000,
                ),
            )
        )
    )

    assert visits == ()


@pytest.mark.parametrize(
    "boundary_kwargs,expected_state,expected_kind",
    [
        (
            {"pit_exit_time_ns": 1_000_000},
            PitEvidenceState.UNPAIRED_EXIT,
            PitBoundaryKind.EXIT,
        ),
        (
            {"pit_entry_time_ns": 1_000_000},
            PitEvidenceState.UNPAIRED_ENTRY,
            PitBoundaryKind.ENTRY,
        ),
    ],
)
def test_trustworthy_single_boundary_remains_unpaired(
    boundary_kwargs,
    expected_state,
    expected_kind,
):
    evidence = _pit_evidence(_input((_row("4", 5, **boundary_kwargs),)))

    assert len(evidence) == 1
    item = evidence[0]
    assert item.state is expected_state
    assert len(item.boundaries) == 1
    assert item.boundaries[0].kind is expected_kind
    assert item.boundaries[0].evidence_status is EvidenceStatus.AVAILABLE
    assert item.source_boundary_count == 1
    _assert_no_pit_elapsed(item)
    if expected_kind is PitBoundaryKind.ENTRY:
        assert item.entry_lap_number == 5
        assert item.exit_lap_number is None
    else:
        assert item.entry_lap_number is None
        assert item.exit_lap_number == 5


def test_equal_lap_leading_exit_does_not_block_later_complete_visit():
    rows = (
        _row("4", 5, pit_exit_time_ns=100),
        _row("4", 5, source_occurrence=2, pit_entry_time_ns=200),
        _row("4", 6, source_occurrence=3, pit_exit_time_ns=300),
    )

    analyses = tuple(
        _pit_evidence(_input(ordered_rows))
        for ordered_rows in (rows, tuple(reversed(rows)))
    )
    evidence = analyses[0]

    assert analyses[0] == analyses[1]
    assert [item.state for item in evidence] == [
        PitEvidenceState.UNPAIRED_EXIT,
        PitEvidenceState.COMPLETE,
    ]
    assert evidence[0].exit_lap_number == 5
    assert evidence[1].entry_lap_number == 5
    assert evidence[1].exit_lap_number == 6
    assert evidence[1].entry_to_exit_elapsed_ns == 100


def test_each_leading_exit_is_independently_unpaired():
    rows = (
        _row("4", 1, pit_exit_time_ns=100),
        _row("4", 2, source_occurrence=2, pit_exit_time_ns=200),
    )

    analyses = tuple(
        _pit_evidence(_input(ordered_rows))
        for ordered_rows in (rows, tuple(reversed(rows)))
    )
    evidence = analyses[0]

    assert analyses[0] == analyses[1]
    assert [item.state for item in evidence] == [
        PitEvidenceState.UNPAIRED_EXIT,
        PitEvidenceState.UNPAIRED_EXIT,
    ]
    assert [item.exit_lap_number for item in evidence] == [1, 2]
    assert sum(item.source_boundary_count for item in evidence) == 2


def test_leading_exits_do_not_consume_a_later_complete_visit():
    rows = (
        _row("4", 1, pit_exit_time_ns=100),
        _row("4", 2, source_occurrence=2, pit_exit_time_ns=200),
        _row("4", 30, source_occurrence=3, pit_entry_time_ns=300),
        _row("4", 31, source_occurrence=4, pit_exit_time_ns=400),
    )

    analyses = tuple(
        _pit_evidence(_input(ordered_rows))
        for ordered_rows in (rows, tuple(reversed(rows)))
    )
    evidence = analyses[0]

    assert analyses[0] == analyses[1]
    assert [item.state for item in evidence] == [
        PitEvidenceState.UNPAIRED_EXIT,
        PitEvidenceState.UNPAIRED_EXIT,
        PitEvidenceState.COMPLETE,
    ]
    assert [item.exit_lap_number for item in evidence[:2]] == [1, 2]
    assert evidence[2].entry_lap_number == 30
    assert evidence[2].exit_lap_number == 31
    assert sum(item.source_boundary_count for item in evidence) == 4


@pytest.mark.parametrize(
    "provider_generated,kind",
    [
        (True, PitBoundaryKind.ENTRY),
        (True, PitBoundaryKind.EXIT),
        (None, PitBoundaryKind.ENTRY),
        (None, PitBoundaryKind.EXIT),
    ],
    ids=(
        "generated-entry",
        "generated-exit",
        "unasserted-entry",
        "unasserted-exit",
    ),
)
def test_timestamped_untrusted_boundary_does_not_split_trusted_visit(
    provider_generated,
    kind,
):
    boundary_field = (
        "pit_entry_time_ns" if kind is PitBoundaryKind.ENTRY else "pit_exit_time_ns"
    )
    intervening = _row(
        "4",
        3,
        source_occurrence=2,
        provider_generated=provider_generated,
        **{boundary_field: 150},
    )
    rows = (
        _row("4", 2, pit_entry_time_ns=100),
        intervening,
        _row("4", 4, source_occurrence=3, pit_exit_time_ns=200),
    )
    analyses = tuple(
        _pit_evidence(_input(ordered_rows))
        for ordered_rows in (rows, tuple(reversed(rows)))
    )

    assert analyses[0] == analyses[1]
    assert [item.state for item in analyses[0]] == [
        PitEvidenceState.COMPLETE,
        PitEvidenceState.UNAVAILABLE,
    ]
    complete, unavailable = analyses[0]
    assert complete.entry_lap_number == 2
    assert complete.exit_lap_number == 4
    assert complete.entry_to_exit_elapsed_ns == 100
    assert unavailable.boundaries[0].kind is kind
    assert unavailable.boundaries[0].lap_number == 3
    assert sum(item.source_boundary_count for item in analyses[0]) == 3


def test_timestamped_conflict_does_not_split_trusted_visit():
    rows = (
        _row("4", 2, pit_entry_time_ns=100),
        _row(
            "4",
            3,
            source_occurrence=2,
            provider_generated=False,
            pit_entry_time_ns=150,
        ),
        _row(
            "4",
            3,
            source_occurrence=3,
            provider_generated=True,
            pit_entry_time_ns=150,
        ),
        _row("4", 4, source_occurrence=4, pit_exit_time_ns=200),
    )
    analyses = tuple(
        _pit_evidence(_input(ordered_rows))
        for ordered_rows in (rows, tuple(reversed(rows)))
    )

    assert analyses[0] == analyses[1]
    assert [item.state for item in analyses[0]] == [
        PitEvidenceState.COMPLETE,
        PitEvidenceState.CONFLICTING,
    ]
    assert analyses[0][0].entry_to_exit_elapsed_ns == 100
    assert analyses[0][1].boundaries[0].session_time_ns == 150
    assert analyses[0][1].source_boundary_count == 2
    assert sum(item.source_boundary_count for item in analyses[0]) == 4


def test_timestampless_untrusted_boundary_does_not_split_trusted_visit():
    invalid_entry = replace(
        _row("4", 3, source_occurrence=2),
        pit_entry_time_ns=NormalizedValue(NormalizedValueState.INVALID),
    )
    rows = (
        _row("4", 2, pit_entry_time_ns=100),
        invalid_entry,
        _row("4", 4, source_occurrence=3, pit_exit_time_ns=200),
    )
    analyses = tuple(
        _pit_evidence(_input(ordered_rows))
        for ordered_rows in (rows, tuple(reversed(rows)))
    )

    assert analyses[0] == analyses[1]
    assert [item.state for item in analyses[0]] == [
        PitEvidenceState.COMPLETE,
        PitEvidenceState.UNAVAILABLE,
    ]
    assert analyses[0][0].entry_to_exit_elapsed_ns == 100
    assert analyses[0][1].boundaries[0].session_time_ns is None
    assert sum(item.source_boundary_count for item in analyses[0]) == 3


@pytest.mark.parametrize(
    "rows",
    [
        (
            _row("4", 5, pit_entry_time_ns=100),
            _row("4", 6, source_occurrence=2, pit_entry_time_ns=200),
            _row("4", 7, source_occurrence=3, pit_exit_time_ns=300),
        ),
        (
            _row("4", 5, pit_entry_time_ns=100),
            _row("4", 6, source_occurrence=2, pit_exit_time_ns=200),
            _row("4", 7, source_occurrence=3, pit_exit_time_ns=300),
        ),
        (
            _row("4", 5, pit_entry_time_ns=100),
            _row("4", 6, source_occurrence=2, pit_exit_time_ns=100),
        ),
        (
            _row("4", 6, pit_entry_time_ns=100),
            _row("4", 5, source_occurrence=2, pit_exit_time_ns=100),
        ),
        (
            _row("4", 5, pit_entry_time_ns=200),
            _row("4", 6, source_occurrence=2, pit_exit_time_ns=100),
        ),
        (
            _row("4", 6, pit_entry_time_ns=100),
            _row("4", 5, source_occurrence=2, pit_exit_time_ns=200),
        ),
    ],
    ids=(
        "entry-before-entry",
        "competing-exits",
        "equal-time",
        "equal-time-reversed-lap-order",
        "reversed-time",
        "reversed-lap",
    ),
)
def test_ambiguous_boundary_sequences_form_one_conflicting_group(rows):
    evidence = _pit_evidence(_input(rows))

    assert len(evidence) == 1
    item = evidence[0]
    assert item.state is PitEvidenceState.CONFLICTING
    assert item.source_boundary_count == len(rows)
    assert sum(boundary.source_evidence_count for boundary in item.boundaries) == len(
        rows
    )
    assert all(
        boundary.evidence_status is EvidenceStatus.CONFLICTING
        for boundary in item.boundaries
    )
    _assert_no_pit_elapsed(item)


@pytest.mark.parametrize("kind", [PitBoundaryKind.ENTRY, PitBoundaryKind.EXIT])
def test_asserted_invalid_boundary_is_unavailable(kind):
    timestamp_field = (
        "pit_entry_time_ns" if kind is PitBoundaryKind.ENTRY else "pit_exit_time_ns"
    )
    row = replace(
        _row("4", 5),
        **{timestamp_field: NormalizedValue(NormalizedValueState.INVALID)},
    )

    evidence = _pit_evidence(_input((row,)))

    assert len(evidence) == 1
    item = evidence[0]
    assert item.state is PitEvidenceState.UNAVAILABLE
    assert item.boundaries[0].kind is kind
    assert item.boundaries[0].evidence_status is EvidenceStatus.UNAVAILABLE
    assert item.boundaries[0].session_time_ns is None
    assert item.source_boundary_count == 1
    _assert_no_pit_elapsed(item)


def test_exact_duplicate_boundary_coalesces_with_multiplicity():
    rows = (
        _row("4", 5, source_occurrence=50, pit_entry_time_ns=1_000_000),
        _row("4", 5, source_occurrence=2, pit_entry_time_ns=1_000_000),
        _row("4", 7, source_occurrence=1, pit_exit_time_ns=3_000_000),
    )

    evidence = _pit_evidence(_input(rows))

    assert len(evidence) == 1
    visit = evidence[0]
    assert visit.state is PitEvidenceState.COMPLETE
    assert len(visit.boundaries) == 2
    assert visit.boundaries[0].kind is PitBoundaryKind.ENTRY
    assert visit.boundaries[0].source_evidence_count == 2
    assert visit.boundaries[1].source_evidence_count == 1
    assert visit.source_boundary_count == 3


def test_contradictory_logical_boundary_retains_all_claims_as_conflicting():
    rows = (
        _row("4", 5, source_occurrence=99, pit_entry_time_ns=1_000_000),
        _row("4", 5, source_occurrence=1, pit_entry_time_ns=1_500_000),
    )

    analyses = tuple(
        _pit_evidence(_input(ordered_rows))
        for ordered_rows in (rows, tuple(reversed(rows)))
    )

    assert analyses[0] == analyses[1]
    assert len(analyses[0]) == 1
    item = analyses[0][0]
    assert item.state is PitEvidenceState.CONFLICTING
    assert len(item.boundaries) == 1
    assert item.boundaries[0].kind is PitBoundaryKind.ENTRY
    assert item.boundaries[0].lap_number == 5
    assert item.boundaries[0].session_time_ns is None
    assert item.boundaries[0].source_evidence_count == 2
    assert item.source_boundary_count == 2
    assert all(
        boundary.evidence_status is EvidenceStatus.CONFLICTING
        for boundary in item.boundaries
    )
    _assert_no_pit_elapsed(item)


def test_canonical_boundary_order_and_unusable_chronology_last():
    invalid_entry = replace(
        _row("4", 8, source_occurrence=3),
        pit_entry_time_ns=NormalizedValue(NormalizedValueState.INVALID),
    )
    evidence = _pit_evidence(
        _input(
            (
                invalid_entry,
                _row(
                    "4",
                    5,
                    source_occurrence=2,
                    pit_entry_time_ns=100,
                    pit_exit_time_ns=100,
                ),
                _row("4", 1, source_occurrence=1, pit_exit_time_ns=50),
            )
        )
    )

    assert [item.state for item in evidence] == [
        PitEvidenceState.UNPAIRED_EXIT,
        PitEvidenceState.CONFLICTING,
        PitEvidenceState.UNAVAILABLE,
    ]
    assert [boundary.kind for boundary in evidence[1].boundaries] == [
        PitBoundaryKind.ENTRY,
        PitBoundaryKind.EXIT,
    ]
    assert evidence[-1].boundaries[0].session_time_ns is None


@pytest.mark.parametrize("provider_generated", [True, None])
def test_generated_or_unasserted_boundary_is_auditable_but_unavailable(
    provider_generated,
):
    evidence = _pit_evidence(
        _input(
            (
                _row(
                    "4",
                    5,
                    provider_generated=provider_generated,
                    pit_entry_time_ns=1_000_000,
                ),
            )
        )
    )

    assert len(evidence) == 1
    item = evidence[0]
    assert item.state is PitEvidenceState.UNAVAILABLE
    assert item.boundaries[0].kind is PitBoundaryKind.ENTRY
    assert item.boundaries[0].session_time_ns == 1_000_000
    assert item.boundaries[0].evidence_status is EvidenceStatus.UNAVAILABLE
    assert item.source_boundary_count == 1
    _assert_no_pit_elapsed(item)


def test_invalid_identity_populations_remain_separate_from_pit_evidence():
    invalid_lap = replace(
        _row("4", 5, pit_entry_time_ns=1_000_000),
        lap_number=NormalizedValue(NormalizedValueState.INVALID),
    )
    roster_orphan = _row(
        "99",
        2,
        source_occurrence=2,
        pit_exit_time_ns=2_000_000,
    )
    race_context = _input(
        (invalid_lap, roster_orphan),
        unassociated_row_count=1,
    )

    lap_analysis = analyze_lap_contexts(race_context)
    evidence = analyze_pit_evidence(
        race_context,
        lap_analysis.lap_contexts,
        "4",
    )

    assert lap_analysis.roster_orphan_row_count == 1
    assert [
        (count.driver_number, count.invalid_lap_identity_count)
        for count in lap_analysis.invalid_lap_identity_counts
    ] == [("1", 0), ("4", 1)]
    assert evidence == ()


def test_nonstarter_and_retirement_keep_authoritative_and_earlier_context():
    nonstarter = replace(
        _participant("27"),
        classified_position="DNS",
        classification_status="Did not start",
        completed_laps=0,
    )
    retiree = replace(
        _participant("4"),
        classified_position="DNF",
        classification_status="Retired",
        completed_laps=3,
    )
    race_context = RaceContextInput(
        participants=(nonstarter, retiree),
        lap_rows=(
            _row("4", 3, completion_time_ns=3_000_000),
            _row(
                "4",
                4,
                source_occurrence=2,
                completion_time_ns=4_000_000,
                provider_generated=True,
                pit_entry_time_ns=4_500_000,
            ),
        ),
        unassociated_row_count=0,
    )

    lap_analysis = analyze_lap_contexts(race_context)
    contexts = _contexts_by_identity(lap_analysis)
    retiree_pit_evidence = analyze_pit_evidence(
        race_context,
        lap_analysis.lap_contexts,
        "4",
    )

    assert not any(
        context.driver_number == "27" for context in lap_analysis.lap_contexts
    )
    assert contexts[("4", 3)].completion_time_ns == 3_000_000
    assert contexts[("4", 3)].provider_generated is False
    assert contexts[("4", 4)].provider_generated is True
    assert retiree_pit_evidence[0].state is PitEvidenceState.UNAVAILABLE


def test_missing_classification_and_lap_facts_remain_explicit():
    participant = _participant("4")
    missing_facts = _row(
        "4",
        2,
        completion_time_ns=None,
        completion_position=None,
        track_status=UNAVAILABLE_TRACK_STATUS,
        reported_compound=None,
        reported_stint=None,
    )
    race_context = RaceContextInput(
        participants=(participant,),
        lap_rows=(missing_facts,),
        unassociated_row_count=0,
    )

    context = analyze_lap_contexts(race_context).lap_contexts[0]

    assert participant.finish_position is None
    assert participant.classified_position is None
    assert participant.classification_status is None
    assert participant.completed_laps is None
    assert context.evidence_status is EvidenceStatus.UNAVAILABLE
    assert context.completion_time_ns is None
    assert context.completion_position is None
    assert context.track_status is UNAVAILABLE_TRACK_STATUS
    assert context.reported_compound is None
    assert context.reported_stint is None


def test_transition_context_preserves_per_fact_consensus_for_pit_evidence():
    rows = (
        _row(
            "4",
            5,
            reported_compound="SOFT",
            reported_stint=1,
            pit_entry_time_ns=1_000_000,
        ),
        _row(
            "4",
            5,
            source_occurrence=2,
            reported_compound="HARD",
            reported_stint=1,
        ),
        _row(
            "4",
            7,
            source_occurrence=3,
            reported_compound="MEDIUM",
            reported_stint=2,
            pit_exit_time_ns=3_000_000,
        ),
    )

    visit = _pit_evidence(_input(rows))[0]

    assert visit.state is PitEvidenceState.COMPLETE
    assert visit.entry_context.reported_compound is None
    assert visit.entry_context.reported_stint == 1
    assert visit.reported_compound_changed is None
    assert visit.reported_stint_changed is True


def test_incomplete_conflicting_evidence_is_deterministic_and_reconciled():
    valid_rows = (
        _row("4", 1, source_occurrence=90, pit_exit_time_ns=50),
        _row("4", 2, source_occurrence=80, pit_entry_time_ns=100),
        _row("4", 2, source_occurrence=70, pit_entry_time_ns=100),
        _row("4", 3, source_occurrence=60, pit_exit_time_ns=200),
        _row(
            "4",
            4,
            source_occurrence=50,
            provider_generated=True,
            pit_entry_time_ns=300,
        ),
        _row("4", 5, source_occurrence=40, pit_entry_time_ns=400),
    )
    invalid_lap = replace(
        _row("4", 6, source_occurrence=30, pit_entry_time_ns=500),
        lap_number=NormalizedValue(NormalizedValueState.INVALID),
    )
    roster_orphan = _row(
        "99",
        1,
        source_occurrence=20,
        pit_exit_time_ns=600,
    )
    all_rows = valid_rows + (invalid_lap, roster_orphan)
    orders = (
        all_rows,
        tuple(reversed(all_rows)),
        (
            all_rows[4],
            all_rows[1],
            all_rows[6],
            all_rows[5],
            all_rows[0],
            all_rows[7],
            all_rows[3],
            all_rows[2],
        ),
    )

    normalized_inputs = tuple(_input(rows, unassociated_row_count=1) for rows in orders)
    analyses = tuple(_pit_evidence(race_context) for race_context in normalized_inputs)
    repeated = tuple(_pit_evidence(normalized_inputs[0]) for _ in range(3))

    assert analyses[0] == analyses[1] == analyses[2]
    assert repeated[0] == repeated[1] == repeated[2]
    assert [item.state for item in analyses[0]] == [
        PitEvidenceState.UNPAIRED_EXIT,
        PitEvidenceState.COMPLETE,
        PitEvidenceState.UNAVAILABLE,
        PitEvidenceState.UNPAIRED_ENTRY,
    ]
    assert [item.source_boundary_count for item in analyses[0]] == [1, 3, 1, 1]
    lap_analysis = analyze_lap_contexts(normalized_inputs[0])
    invalid_lap_count = next(
        count.invalid_lap_identity_count
        for count in lap_analysis.invalid_lap_identity_counts
        if count.driver_number == "4"
    )
    assert sum(
        item.source_boundary_count for item in analyses[0]
    ) + invalid_lap_count + lap_analysis.roster_orphan_row_count == len(all_rows)
    assert all(
        item.entry_to_exit_elapsed_ns is None
        for item in analyses[0]
        if item.state is not PitEvidenceState.COMPLETE
    )


def test_race_context_analytics_imports_only_provider_independent_modules():
    import app.analytics.race_context_analytics as module

    imported_roots = set()
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    assert imported_roots.isdisjoint(
        {"fastf1", "pandas", "numpy", "fastapi", "pydantic", "app"}
    )


def _session_fixture():
    rows = (
        _row("4", 1, pit_exit_time_ns=1_000_000),
        _row("4", 2, pit_entry_time_ns=2_000_000),
        _row("4", 2, pit_entry_time_ns=2_000_000, source_occurrence=2),
        _row("4", 3, pit_exit_time_ns=3_000_000),
        _row("4", 4, pit_entry_time_ns=4_000_000),
        _row("4", 4, pit_entry_time_ns=5_000_000),
        _row("4", 4, pit_entry_time_ns=5_000_000, source_occurrence=3),
        _row("4", 5, pit_entry_time_ns=6_000_000, provider_generated=True),
        _row("4", 6, pit_entry_time_ns=7_000_000),
        _row("10", None, pit_entry_time_ns=8_000_000, pit_exit_time_ns=9_000_000),
        _row("10", None, pit_entry_time_ns=8_000_000, pit_exit_time_ns=9_000_000),
        _row("99", 1, pit_entry_time_ns=1_000_000),
        _row("1", 1, completion_position=1),
    )
    participants = (
        _participant("Z"),
        replace(
            _participant("2"),
            identity=RaceContextParticipantIdentity("2", "DNS", "Non Starter", "Team"),
            classified_position="N",
            classification_status="Did not start",
            completed_laps=0,
        ),
        _participant("10"),
        _participant("4"),
        _participant("A"),
        _participant("1"),
    )
    return RaceContextInput(participants, rows, unassociated_row_count=1)


def test_central_session_contains_exactly_the_authoritative_roster():
    snapshot = _session_fixture()
    result = race_analytics.analyze_race_context(snapshot)

    assert isinstance(result, race_analytics.SessionRaceContextAnalysis)
    assert [field.name for field in fields(result)] == ["participants"]
    assert tuple(item.identity.driver_number for item in result.participants) == (
        "1",
        "2",
        "4",
        "10",
        "A",
        "Z",
    )
    assert len(result.participants) == len(snapshot.participants)
    assert len({item.identity.driver_number for item in result.participants}) == 6
    assert all(
        isinstance(item, race_analytics.ParticipantRaceContextAnalysis)
        for item in result.participants
    )
    assert [field.name for field in fields(result.participants[0])] == [
        "identity",
        "classification",
        "latest_lap_context",
        "pit_evidence_counts",
        "lap_contexts",
        "pit_evidence",
        "unassociated_evidence_count",
    ]
    with pytest.raises(FrozenInstanceError):
        result.participants = ()
    with pytest.raises(FrozenInstanceError):
        result.participants[0].latest_lap_context = None


def test_central_zero_evidence_participant_preserves_identity_and_classification():
    snapshot = _session_fixture()
    item = race_analytics.analyze_race_context(snapshot).participants[1]
    source = next(p for p in snapshot.participants if p.identity.driver_number == "2")

    assert item.identity is source.identity
    assert item.classification.evidence_status is EvidenceStatus.AVAILABLE
    assert item.classification.source_evidence_count == 1
    assert item.classification.finish_position is None
    assert item.classification.classified_position == "N"
    assert item.classification.status == "Did not start"
    assert item.classification.completed_laps == 0
    assert item.latest_lap_context is None
    assert item.lap_contexts == item.pit_evidence == ()
    assert item.pit_evidence_counts == race_analytics.PitEvidenceCounts(
        0, 0, 0, 0, 0, 0
    )
    assert item.unassociated_evidence_count == 0


@pytest.mark.parametrize("status", tuple(EvidenceStatus))
def test_central_classification_is_copied_without_lap_inference(status):
    source = replace(
        _participant("4"),
        result_evidence_status=status,
        result_evidence_count=3,
        finish_position=12,
        classified_position="R",
        classification_status="Retired",
        completed_laps=None,
    )
    snapshot = RaceContextInput((source,), (_row("4", 53, completion_position=1),), 0)
    classification = (
        race_analytics.analyze_race_context(snapshot).participants[0].classification
    )

    assert classification == race_analytics.RaceClassificationContext(
        status, 3, 12, "R", "Retired", None
    )


@pytest.mark.parametrize(
    "later_rows,expected_lap",
    [
        ((_row("4", 2, completion_time_ns=20_000_000),), 2),
        ((_row("4", 2, provider_generated=True),), 1),
        ((_row("4", 2, provider_generated=None),), 1),
        ((_row("4", 2, completion_time_ns=None),), 1),
        (
            (
                replace(
                    _row("4", 2),
                    lap_completion_time_ns=NormalizedValue(
                        NormalizedValueState.INVALID
                    ),
                ),
            ),
            1,
        ),
        ((_row("4", 2), _row("4", 2, completion_time_ns=30_000_000)), 1),
        ((_row("4", 2), _row("4", 2, reported_compound="HARD")), 2),
    ],
)
def test_central_latest_uses_trusted_completion_not_highest_audit_lap(
    later_rows, expected_lap
):
    snapshot = _input((_row("4", 1), *later_rows))
    item = next(
        p
        for p in race_analytics.analyze_race_context(snapshot).participants
        if p.identity.driver_number == "4"
    )

    assert item.latest_lap_context.lap_number == expected_lap
    assert item.latest_lap_context is item.lap_contexts[expected_lap - 1]
    assert tuple(lap.lap_number for lap in item.lap_contexts) == (1, 2)


def test_central_no_trusted_completion_has_no_latest_context():
    snapshot = _input(
        (
            _row("4", 1, provider_generated=True),
            _row("4", 2, completion_time_ns=None),
        )
    )
    item = race_analytics.analyze_race_context(snapshot).participants[1]
    assert item.latest_lap_context is None
    assert len(item.lap_contexts) == 2


def test_central_reuses_complete_lap_and_pit_series_and_counts_items():
    snapshot = _session_fixture()
    result = race_analytics.analyze_race_context(snapshot)
    laps = analyze_lap_contexts(snapshot)
    for item in result.participants:
        number = item.identity.driver_number
        assert item.lap_contexts == tuple(
            lap for lap in laps.lap_contexts if lap.driver_number == number
        )
        assert item.pit_evidence == analyze_pit_evidence(
            snapshot, laps.lap_contexts, number
        )
    item = result.participants[2]
    assert item.pit_evidence_counts == race_analytics.PitEvidenceCounts(
        1, 1, 1, 1, 1, 5
    )
    conflict = next(
        e for e in item.pit_evidence if e.state is PitEvidenceState.CONFLICTING
    )
    assert conflict.source_boundary_count == 3
    assert item.pit_evidence_counts.conflicting == 1
    complete = next(
        e for e in item.pit_evidence if e.state is PitEvidenceState.COMPLETE
    )
    assert complete.source_boundary_count == 3
    assert item.pit_evidence_counts.complete == 1
    assert item.pit_evidence_counts.total == len(item.pit_evidence)
    assert sum(e.source_boundary_count for e in item.pit_evidence) == 9


def test_central_invalid_identity_counts_rows_once_and_excludes_roster_orphans():
    result = race_analytics.analyze_race_context(_session_fixture())
    assert [p.unassociated_evidence_count for p in result.participants] == [
        0,
        0,
        0,
        2,
        0,
        0,
    ]
    invalid_only = result.participants[3]
    assert invalid_only.latest_lap_context is None
    assert invalid_only.lap_contexts == invalid_only.pit_evidence == ()
    assert invalid_only.pit_evidence_counts.total == 0
    assert all(p.identity.driver_number != "99" for p in result.participants)


@pytest.mark.parametrize(
    "counts",
    [
        (-1, 0, 0, 0, 0, -1),
        (0, -1, 0, 0, 0, 0),
        (0, 0, -1, 0, 0, 0),
        (0, 0, 0, -1, 0, 0),
        (0, 0, 0, 0, -1, 0),
        (0, 0, 0, 0, 0, -1),
        (1, 0, 0, 0, 0, 0),
    ],
)
def test_central_pit_count_invariants(counts):
    with pytest.raises(ValueError):
        race_analytics.PitEvidenceCounts(*counts)


def test_central_participant_ownership_and_latest_membership_invariants():
    result = race_analytics.analyze_race_context(_session_fixture())
    owner, other = result.participants[2], result.participants[0]
    for changes in (
        {"lap_contexts": other.lap_contexts},
        {"latest_lap_context": other.latest_lap_context},
        {"lap_contexts": ()},
        {"identity": other.identity},
        {"unassociated_evidence_count": -1},
    ):
        with pytest.raises(ValueError):
            replace(owner, **changes)
    with pytest.raises(ValueError):
        replace(
            other,
            pit_evidence=owner.pit_evidence,
            pit_evidence_counts=owner.pit_evidence_counts,
        )
    with pytest.raises(ValueError):
        replace(result, participants=(owner, owner))


def test_central_source_permutations_and_three_identical_runs_are_equal():
    snapshot = _session_fixture()
    expected = race_analytics.analyze_race_context(snapshot)
    for participants in (snapshot.participants, tuple(reversed(snapshot.participants))):
        for rows in (
            snapshot.lap_rows,
            tuple(reversed(snapshot.lap_rows)),
            snapshot.lap_rows[5:] + snapshot.lap_rows[:5],
        ):
            # Diagnostic ordinals also change with source order.
            reordered = replace(
                snapshot,
                participants=participants,
                lap_rows=tuple(
                    replace(row, source_occurrence=i) for i, row in enumerate(rows, 1)
                ),
            )
            assert race_analytics.analyze_race_context(reordered) == expected
    assert [race_analytics.analyze_race_context(snapshot) for _ in range(3)] == [
        expected,
        expected,
        expected,
    ]


def test_central_rejects_duplicate_authoritative_identity():
    participant = _participant("4")
    with pytest.raises(ValueError):
        race_analytics.analyze_race_context(
            RaceContextInput((participant, participant), (), 0)
        )


def test_central_derives_laps_once_from_the_supplied_snapshot(monkeypatch):
    snapshot = _session_fixture()
    calls = []
    derived = []

    def record_lap_analysis(supplied):
        calls.append(supplied)
        analysis = analyze_lap_contexts(supplied)
        derived.extend(analysis.lap_contexts)
        return analysis

    monkeypatch.setattr(race_analytics, "analyze_lap_contexts", record_lap_analysis)
    result = race_analytics.analyze_race_context(snapshot)

    assert len(calls) == 1
    assert calls[0] is snapshot
    assert len(derived) == sum(len(p.lap_contexts) for p in result.participants)
    assert all(
        any(context is original for original in derived)
        for participant in result.participants
        for context in participant.lap_contexts
    )


def test_central_numeric_order_precedes_normalized_nonnumeric_identity_order():
    snapshot = _input((), drivers=("Z", "10", "2", "01", "A", "1"))
    expected = ("1", "2", "10", "01", "A", "Z")
    for participants in permutations(snapshot.participants):
        result = race_analytics.analyze_race_context(
            replace(snapshot, participants=participants)
        )
        assert tuple(p.identity.driver_number for p in result.participants) == expected


def test_central_disrupted_trusted_context_remains_latest():
    snapshot = _input(
        (
            _row("4", 1),
            _row(
                "4",
                2,
                track_status=_track_status(
                    NormalizedTrackStatus.YELLOW, is_disrupted=True
                ),
            ),
        )
    )
    participant = race_analytics.analyze_race_context(snapshot).participants[1]
    assert participant.latest_lap_context is participant.lap_contexts[1]
    assert participant.latest_lap_context.track_status.is_disrupted is True


def test_central_empty_roster_returns_empty_session():
    result = race_analytics.analyze_race_context(
        RaceContextInput((), (_row("99", 1),), 1)
    )
    assert result == race_analytics.SessionRaceContextAnalysis(())


def test_central_direct_construction_rejects_missing_latest_with_trusted_laps():
    participant = race_analytics.analyze_race_context(
        _input((_row("4", 1), _row("4", 6)))
    ).participants[1]
    with pytest.raises(ValueError):
        replace(participant, latest_lap_context=None)


def test_central_direct_construction_rejects_stale_latest():
    participant = race_analytics.analyze_race_context(
        _input((_row("4", 1), _row("4", 6)))
    ).participants[1]
    with pytest.raises(ValueError):
        replace(participant, latest_lap_context=participant.lap_contexts[0])


def test_central_direct_construction_accepts_correct_latest():
    participant = race_analytics.analyze_race_context(
        _input((_row("4", 1), _row("4", 6)))
    ).participants[1]
    assert (
        replace(participant, latest_lap_context=participant.lap_contexts[-1])
        == participant
    )
    assert participant.latest_lap_context.lap_number == 6


def test_central_direct_construction_accepts_none_without_trusted_laps():
    participant = race_analytics.analyze_race_context(
        _input(
            (
                _row("4", 1, provider_generated=True),
                _row("4", 6, completion_time_ns=None),
            )
        )
    ).participants[1]
    assert replace(participant, latest_lap_context=None) == participant


@pytest.mark.parametrize(
    "later_rows,expected_lap",
    [
        ((_row("4", 6, provider_generated=True),), 5),
        ((_row("4", 6, provider_generated=None),), 5),
        (
            (
                replace(
                    _row("4", 6),
                    lap_completion_time_ns=NormalizedValue(
                        NormalizedValueState.INVALID
                    ),
                ),
            ),
            5,
        ),
        ((_row("4", 6), _row("4", 6, completion_time_ns=30_000_000)), 5),
        ((_row("4", 6), _row("4", 6, reported_compound="HARD")), 6),
    ],
)
def test_central_direct_construction_latest_preserves_c1_trust(
    later_rows, expected_lap
):
    participant = race_analytics.analyze_race_context(
        _input((_row("4", 5), *later_rows))
    ).participants[1]
    correct = next(
        lap for lap in participant.lap_contexts if lap.lap_number == expected_lap
    )
    assert replace(participant, latest_lap_context=correct) == participant


def test_central_direct_construction_rejects_wrong_pit_state_distribution():
    participant = race_analytics.analyze_race_context(_session_fixture()).participants[
        2
    ]
    assert {item.state for item in participant.pit_evidence} == set(PitEvidenceState)
    wrong_counts = race_analytics.PitEvidenceCounts(0, 2, 1, 1, 1, 5)
    assert wrong_counts.total == len(participant.pit_evidence)
    with pytest.raises(ValueError):
        replace(participant, pit_evidence_counts=wrong_counts)


def test_central_direct_construction_accepts_correct_pit_state_distribution():
    participant = race_analytics.analyze_race_context(_session_fixture()).participants[
        2
    ]
    correct_counts = race_analytics.PitEvidenceCounts(1, 1, 1, 1, 1, 5)
    assert replace(participant, pit_evidence_counts=correct_counts) == participant
    conflict = next(
        item
        for item in participant.pit_evidence
        if item.state is PitEvidenceState.CONFLICTING
    )
    assert conflict.source_boundary_count == 3
    assert correct_counts.conflicting == 1


def test_central_direct_construction_rejects_wrong_pit_total():
    participant = race_analytics.analyze_race_context(_session_fixture()).participants[
        2
    ]
    with pytest.raises(ValueError):
        replace(
            participant,
            pit_evidence_counts=race_analytics.PitEvidenceCounts(2, 1, 1, 1, 1, 6),
        )
