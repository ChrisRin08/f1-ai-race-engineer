import ast
import inspect
from dataclasses import replace
from itertools import permutations

import pytest

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
