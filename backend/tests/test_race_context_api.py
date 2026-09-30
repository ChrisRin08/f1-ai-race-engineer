"""Direct construction of Feature 004 public models; no HTTP orchestration."""

from copy import deepcopy
from importlib import import_module, util

import pytest
from pydantic import ValidationError


def models():
    name = "app.models.race_context_models"
    assert util.find_spec(name) is not None, "Feature 004 public models are missing"
    return import_module(name)


def identity(number="2"):
    return dict(driver_number=number, abbreviation=None, full_name=None, team_name=None)


def classification():
    return dict(
        evidence_status="unavailable",
        source_evidence_count=1,
        finish_position=None,
        classified_position=None,
        status=None,
        completed_laps=None,
    )


def track():
    return dict(availability="available", track_statuses=["green"], is_disrupted=False)


def lap(number=1, driver="2"):
    return dict(
        driver_number=driver,
        lap_number=number,
        evidence_status="available",
        source_evidence_count=1,
        lap_completion_session_time_ms=1000,
        lap_completion_position=2,
        track_status=track(),
        provider_generated=False,
        reported_compound="HARD",
        reported_stint=1,
        leader_reference=dict(
            driver_number="1", lap_number=number, lap_completion_session_time_ms=900
        ),
        laps_behind_status="available",
        laps_behind=0,
        equal_distance_time_deficit_status="available",
        equal_distance_time_deficit_ms=100,
    )


def unavailable_lap():
    return dict(
        lap(),
        lap_completion_session_time_ms=None,
        leader_reference=None,
        laps_behind_status="unavailable",
        laps_behind=None,
        equal_distance_time_deficit_status="unavailable",
        equal_distance_time_deficit_ms=None,
        reported_compound=None,
        reported_stint=None,
        lap_completion_position=None,
        provider_generated=None,
    )


def test_d1_shared_contract_exists_and_preserves_classification():
    m = models()
    assert m.RaceContextParticipantIdentity(**identity("A")).driver_number == "A"
    payload = dict(
        classification(),
        evidence_status="conflicting",
        status="Not started",
        completed_laps=0,
    )
    assert m.RaceClassificationContext(**payload).model_dump(mode="json") == payload
    assert m.LapContextReference(driver_number="A", lap_number=1).lap_number == 1
    assert m.LeaderReference(**lap()["leader_reference"]).lap_number == 1


def test_d1_lap_available_and_unavailable_contracts():
    m = models()
    for payload in (lap(), unavailable_lap()):
        assert m.LapCompletionContext(**payload).model_dump(mode="json") == payload


def test_d1_track_order_is_not_enum_order():
    m = models()
    for statuses in (["yellow", "green"], ["green", "yellow"]):
        payload = dict(track(), track_statuses=statuses, is_disrupted=True)
        before = deepcopy(payload)
        assert m.TrackStatusContext(**payload).model_dump(mode="json") == before
        assert payload == before


@pytest.mark.parametrize(
    "statuses,availability,disrupted",
    [
        (["green"], "available", False),
        (["unknown"], "available", None),
        (["green", "unknown"], "available", None),
        (["yellow", "unknown"], "available", True),
        (["safety_car"], "available", True),
        (["virtual_safety_car"], "available", True),
        (["virtual_safety_car_ending"], "available", True),
        (["red_flag"], "available", True),
        ([], "unavailable", None),
        (["yellow"], "available", True),
    ],
)
def test_d1_track_truth_table_accepts(statuses, availability, disrupted):
    models().TrackStatusContext(
        availability=availability, track_statuses=statuses, is_disrupted=disrupted
    )


@pytest.mark.parametrize(
    "statuses,availability,disrupted",
    [
        (["green", "green"], "available", False),
        (["unknown"], "available", False),
        (["yellow"], "available", False),
        (["yellow"], "available", None),
        (["green"], "available", None),
        ([], "available", False),
        (["green"], "unavailable", False),
        (["yellow"], "unavailable", True),
        (["green"], "unavailable", None),
        ([], "unavailable", True),
        (["GREEN"], "available", False),
    ],
)
def test_d1_track_contradictions_reject_without_mutation(
    statuses, availability, disrupted
):
    payload = dict(
        availability=availability, track_statuses=statuses, is_disrupted=disrupted
    )
    before = deepcopy(payload)
    with pytest.raises(ValidationError):
        models().TrackStatusContext(**payload)
    assert payload == before


@pytest.mark.parametrize(
    "statuses",
    [
        ["green"],
        ["yellow"],
        ["safety_car"],
        ["virtual_safety_car"],
        ["virtual_safety_car_ending"],
        ["red_flag"],
        ["unknown"],
        ["yellow", "unknown"],
        ["unknown", "yellow"],
    ],
)
@pytest.mark.parametrize("disrupted", [None, False, True])
def test_d1_unavailable_track_status_rejects_all_nonempty_evidence(statuses, disrupted):
    payload = dict(
        availability="unavailable", track_statuses=statuses, is_disrupted=disrupted
    )
    before = deepcopy(payload)
    with pytest.raises(ValidationError):
        models().TrackStatusContext(**payload)
    assert payload == before


@pytest.mark.parametrize(
    "changes",
    [
        dict(laps_behind=1),
        dict(laps_behind=None),
        dict(laps_behind_status="unavailable"),
        dict(equal_distance_time_deficit_ms=None),
        dict(equal_distance_time_deficit_status="not_applicable"),
        dict(equal_distance_time_deficit_status="unavailable"),
        dict(provider_generated=True),
        dict(provider_generated=None),
        dict(lap_completion_session_time_ms=None),
        dict(leader_reference=None),
        dict(
            leader_reference=dict(
                driver_number="1", lap_number=2, lap_completion_session_time_ms=900
            )
        ),
        dict(
            leader_reference=dict(
                driver_number="1", lap_number=1, lap_completion_session_time_ms=1001
            )
        ),
    ],
)
def test_d1_lap_state_contradictions_reject(changes):
    with pytest.raises(ValidationError):
        models().LapCompletionContext(**dict(lap(), **changes))


def test_d1_lapped_zero_and_partial_conflict_are_representable():
    m = models()
    payload = dict(
        lap(),
        laps_behind=1,
        equal_distance_time_deficit_status="not_applicable",
        equal_distance_time_deficit_ms=None,
    )
    payload["leader_reference"]["lap_number"] = 2
    m.LapCompletionContext(**payload)
    m.LapCompletionContext(**dict(lap(), equal_distance_time_deficit_ms=0))
    m.LapCompletionContext(
        **dict(lap(), evidence_status="conflicting", reported_stint=None)
    )
    m.LapCompletionContext(
        **dict(
            lap(),
            equal_distance_time_deficit_status="unavailable",
            equal_distance_time_deficit_ms=None,
        )
    )


@pytest.mark.parametrize("generated", [True, None])
def test_d1_generated_keeps_audit_timing_without_trusted_derivatives(generated):
    payload = dict(
        unavailable_lap(),
        provider_generated=generated,
        lap_completion_session_time_ms=1000,
    )
    assert (
        models().LapCompletionContext(**payload).lap_completion_session_time_ms == 1000
    )


D1_VALUES = [
    ("RaceContextParticipantIdentity", identity()),
    ("RaceClassificationContext", classification()),
    ("TrackStatusContext", track()),
    ("LapContextReference", dict(driver_number="2", lap_number=1)),
    ("LeaderReference", lap()["leader_reference"]),
    ("LapCompletionContext", unavailable_lap()),
]


@pytest.mark.parametrize("name,payload", D1_VALUES)
def test_d1_required_fields_and_extra_rejection(name, payload):
    model = getattr(models(), name)
    model(**payload)
    for key in payload:
        omitted = dict(payload)
        del omitted[key]
        with pytest.raises(ValidationError):
            model(**omitted)
    with pytest.raises(ValidationError):
        model(**dict(payload, unexpected=True))


BAD_INTS = [True, False, "1", "1000", 1.0, float("nan"), float("inf"), -float("inf")]
D1_INTS = (
    [
        ("RaceClassificationContext", classification(), key)
        for key in ("source_evidence_count", "finish_position", "completed_laps")
    ]
    + [
        ("LapContextReference", dict(driver_number="2", lap_number=1), "lap_number"),
        ("LeaderReference", lap()["leader_reference"], "lap_number"),
        (
            "LeaderReference",
            lap()["leader_reference"],
            "lap_completion_session_time_ms",
        ),
    ]
    + [
        ("LapCompletionContext", lap(), key)
        for key in (
            "lap_number",
            "source_evidence_count",
            "lap_completion_session_time_ms",
            "lap_completion_position",
            "reported_stint",
            "laps_behind",
            "equal_distance_time_deficit_ms",
        )
    ]
)


@pytest.mark.parametrize("name,payload,key", D1_INTS)
@pytest.mark.parametrize("bad", BAD_INTS)
def test_d1_every_integer_is_strict(name, payload, key, bad):
    with pytest.raises(ValidationError):
        getattr(models(), name)(**dict(payload, **{key: bad}))


@pytest.mark.parametrize("bad", [1, True, b"2", ""])
def test_d1_identity_no_coercion_or_empty_identity(bad):
    with pytest.raises(ValidationError):
        models().RaceContextParticipantIdentity(**identity(bad))


def test_d1_identity_is_not_trimmed():
    assert (
        models().RaceContextParticipantIdentity(**identity(" A ")).driver_number
        == " A "
    )


@pytest.mark.parametrize(
    "name,payload,key,bad",
    [
        ("TrackStatusContext", track(), "availability", b"available"),
        ("TrackStatusContext", track(), "availability", "AVAILABLE"),
        ("TrackStatusContext", track(), "is_disrupted", 0),
        ("LapCompletionContext", lap(), "provider_generated", 0),
        ("LapCompletionContext", lap(), "reported_compound", 1),
        ("RaceClassificationContext", classification(), "status", 1),
    ],
)
def test_d1_other_scalars_are_strict(name, payload, key, bad):
    with pytest.raises(ValidationError):
        getattr(models(), name)(**dict(payload, **{key: bad}))


def reference(number=1, driver="2"):
    return dict(driver_number=driver, lap_number=number)


def boundary(kind="entry", number=1, time=10, status="available", count=1):
    return dict(
        kind=kind,
        evidence_status=status,
        source_evidence_count=count,
        lap_number=number,
        entry_session_time_ms=time if kind == "entry" else None,
        exit_session_time_ms=time if kind == "exit" else None,
        lap_context_reference=reference(number) if number is not None else None,
    )


def transition(number=1, compound="HARD", stint=1, availability="available"):
    return dict(
        availability=availability,
        lap_context_reference=reference(number),
        reported_compound=compound,
        reported_stint=stint,
    )


def pit(state="complete"):
    payload = dict(
        state=state,
        boundaries=[],
        source_boundary_count=1,
        entry_lap_number=None,
        exit_lap_number=None,
        entry_session_time_ms=None,
        exit_session_time_ms=None,
        entry_to_exit_elapsed_ms=None,
        entry_context=None,
        exit_context=None,
        reported_compound_changed=None,
        reported_stint_changed=None,
    )
    if state == "complete":
        payload.update(
            boundaries=[boundary(), boundary("exit", 2, 20)],
            source_boundary_count=2,
            entry_lap_number=1,
            exit_lap_number=2,
            entry_session_time_ms=10,
            exit_session_time_ms=20,
            entry_to_exit_elapsed_ms=10,
            entry_context=transition(),
            exit_context=transition(2, "SOFT", 2),
            reported_compound_changed=True,
            reported_stint_changed=True,
        )
    elif state in ("unpaired_entry", "unpaired_exit"):
        kind = state.removeprefix("unpaired_")
        payload["boundaries"] = [boundary(kind)]
        payload.update(
            {
                kind + "_lap_number": 1,
                kind + "_session_time_ms": 10,
                kind + "_context": transition(),
            }
        )
    else:
        payload["boundaries"] = [boundary(status=state, time=None, count=3)]
        payload["source_boundary_count"] = 3
    return payload


def counts(**states):
    result = {
        state: states.get(state, 0)
        for state in (
            "complete",
            "unpaired_entry",
            "unpaired_exit",
            "conflicting",
            "unavailable",
        )
    }
    return dict(total=sum(result.values()), **result)


@pytest.mark.parametrize(
    "name",
    [
        "PitBoundaryEvidence",
        "PitTransitionContext",
        "PitLaneEvidence",
        "PitEvidenceCounts",
    ],
)
def test_d2_public_pit_models_exist(name):
    assert hasattr(models(), name), f"Missing public pit model: {name}"


@pytest.mark.parametrize(
    "state",
    ["complete", "unpaired_entry", "unpaired_exit", "conflicting", "unavailable"],
)
def test_d2_all_pit_states_are_preserved(state):
    payload = pit(state)
    before = deepcopy(payload)
    result = models().PitLaneEvidence(**payload)
    assert result.model_dump(mode="json") == before
    assert payload == before


@pytest.mark.parametrize(
    "changes",
    [
        dict(exit_session_time_ms=11),
        dict(entry_session_time_ms=None),
        dict(lap_number=None),
        dict(source_evidence_count=0),
        dict(lap_context_reference=reference(2)),
        dict(kind="ENTRY"),
    ],
)
def test_d2_entry_boundary_contradictions_reject(changes):
    with pytest.raises(ValidationError):
        models().PitBoundaryEvidence(**dict(boundary(), **changes))


def test_d2_exit_rejects_wrong_timestamp_and_unavailable_keeps_audit_time():
    with pytest.raises(ValidationError):
        models().PitBoundaryEvidence(**dict(boundary("exit"), entry_session_time_ms=10))
    payload = boundary(status="unavailable", time=10)
    assert models().PitBoundaryEvidence(**payload).entry_session_time_ms == 10


@pytest.mark.parametrize(
    "changes",
    [
        dict(boundaries=[]),
        dict(boundaries=[boundary()]),
        dict(boundaries=[boundary("exit", 2, 20), boundary()]),
        dict(source_boundary_count=3),
        dict(entry_lap_number=2),
        dict(exit_lap_number=1),
        dict(entry_session_time_ms=11),
        dict(exit_session_time_ms=19),
        dict(entry_to_exit_elapsed_ms=None),
        dict(entry_context=None),
        dict(exit_context=None),
        dict(entry_context=transition(2)),
        dict(exit_context=transition(1)),
        dict(reported_compound_changed=False),
        dict(reported_stint_changed=False),
    ],
)
def test_d2_complete_shape_contradictions_reject_without_repair(changes):
    payload = dict(pit(), **changes)
    before = deepcopy(payload)
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**payload)
    assert payload == before


def test_d2_complete_requires_trusted_boundaries_and_rejects_public_time_reversal():
    payload = pit()
    payload["boundaries"][0]["evidence_status"] = "conflicting"
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**payload)
    payload = pit()
    payload["exit_session_time_ms"] = 9
    payload["boundaries"][1]["exit_session_time_ms"] = 9
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**payload)


@pytest.mark.parametrize(
    "entry_ms,exit_ms,elapsed_ms", [(0, 1, 0), (1, 1, 0), (1, 2, 2)]
)
def test_d2_elapsed_is_not_recalculated_from_rounded_endpoints(
    entry_ms, exit_ms, elapsed_ms
):
    # Exact examples: 0.4->0.6, 1.1->1.2, and 0.51->2.49 milliseconds.
    payload = pit()
    payload.update(
        entry_session_time_ms=entry_ms,
        exit_session_time_ms=exit_ms,
        entry_to_exit_elapsed_ms=elapsed_ms,
    )
    payload["boundaries"][0]["entry_session_time_ms"] = entry_ms
    payload["boundaries"][1]["exit_session_time_ms"] = exit_ms
    assert models().PitLaneEvidence(**payload).entry_to_exit_elapsed_ms == elapsed_ms


@pytest.mark.parametrize(
    "state", ["unpaired_entry", "unpaired_exit", "conflicting", "unavailable"]
)
@pytest.mark.parametrize(
    "field,value",
    [
        ("entry_to_exit_elapsed_ms", 0),
        ("reported_compound_changed", False),
        ("reported_stint_changed", True),
    ],
)
def test_d2_noncomplete_never_claims_derived_values(state, field, value):
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**dict(pit(state), **{field: value}))


@pytest.mark.parametrize("state", ["unpaired_entry", "unpaired_exit"])
def test_d2_unpaired_rejects_fabricated_other_side_or_implicit_pairing(state):
    payload = pit(state)
    other = "exit" if state == "unpaired_entry" else "entry"
    payload[other + "_session_time_ms"] = 20
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**payload)
    payload = pit(state)
    payload["boundaries"].append(boundary(other, 2, 20))
    payload["source_boundary_count"] = 2
    before = deepcopy(payload)
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**payload)
    assert payload == before


@pytest.mark.parametrize("state", ["conflicting", "unavailable"])
def test_d2_uncertain_items_reject_trusted_fields_or_wrong_boundary_status(state):
    payload = pit(state)
    payload["entry_lap_number"] = 1
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**payload)
    payload = pit(state)
    payload["boundaries"][0]["evidence_status"] = "available"
    payload["boundaries"][0]["entry_session_time_ms"] = 1
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**payload)


@pytest.mark.parametrize("field", ["reported_compound", "reported_stint"])
def test_d2_change_flags_require_two_usable_values_but_do_not_fill_missing_flags(field):
    payload = pit()
    payload["entry_context"][field] = None
    flag = field + "_changed"
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**payload)
    payload[flag] = None
    assert getattr(models().PitLaneEvidence(**payload), flag) is None


def test_d2_partial_context_conflict_keeps_usable_reported_values():
    payload = pit()
    payload["entry_context"]["availability"] = "conflicting"
    models().PitLaneEvidence(**payload)
    payload["exit_context"].update(reported_compound="HARD", reported_stint=1)
    payload.update(reported_compound_changed=False, reported_stint_changed=False)
    models().PitLaneEvidence(**payload)


def test_d2_transition_reference_and_driver_consistency():
    with pytest.raises(ValidationError):
        models().PitTransitionContext(**dict(transition(), lap_context_reference=None))
    models().PitTransitionContext(
        availability="unavailable",
        lap_context_reference=None,
        reported_compound=None,
        reported_stint=None,
    )
    payload = pit()
    payload["exit_context"]["lap_context_reference"]["driver_number"] = "9"
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**payload)


@pytest.mark.parametrize("times", [(10, 5), (None, 5)])
def test_d2_observable_boundary_order_reversal_rejects(times):
    payload = pit("conflicting")
    payload["boundaries"] = [boundary(time=t, status="conflicting") for t in times]
    payload["source_boundary_count"] = 2
    before = deepcopy(payload)
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**payload)
    assert payload == before


@pytest.mark.parametrize("reverse", [False, True])
def test_d2_boundary_millisecond_collision_never_uses_lower_keys(reverse):
    # Exact 1,100,000 ns lap 2 exit precedes 1,200,000 ns lap 1 entry.
    boundaries = [
        boundary("exit", 2, 1, "conflicting"),
        boundary("entry", 1, 1, "conflicting"),
    ]
    if reverse:
        boundaries.reverse()
    payload = dict(pit("conflicting"), boundaries=boundaries, source_boundary_count=2)
    before = deepcopy(payload)
    assert models().PitLaneEvidence(**payload).model_dump(mode="json") == before
    assert payload == before


def test_d2_absent_chronology_allows_observable_lap_kind_order_checks():
    for boundaries in (
        [
            boundary(number=2, time=None, status="unavailable"),
            boundary(number=1, time=None, status="unavailable"),
        ],
        [
            boundary("exit", time=None, status="unavailable"),
            boundary("entry", time=None, status="unavailable"),
        ],
    ):
        payload = dict(
            pit("unavailable"), boundaries=boundaries, source_boundary_count=2
        )
        with pytest.raises(ValidationError):
            models().PitLaneEvidence(**payload)


def test_d2_multiplicity_reconciles_without_becoming_multiple_events():
    payload = pit("conflicting")
    result = models().PitLaneEvidence(**payload)
    assert len(result.boundaries) == 1
    assert result.source_boundary_count == 3
    models().PitEvidenceCounts(**counts(conflicting=1))
    with pytest.raises(ValidationError):
        models().PitLaneEvidence(**dict(payload, source_boundary_count=1))
    with pytest.raises(ValidationError):
        models().PitEvidenceCounts(**dict(counts(conflicting=1), total=3))


D2_VALUES = [
    ("PitBoundaryEvidence", boundary()),
    ("PitTransitionContext", transition()),
    ("PitLaneEvidence", pit("unavailable")),
    ("PitEvidenceCounts", counts()),
]


@pytest.mark.parametrize("name,payload", D2_VALUES)
def test_d2_required_fields_and_extras(name, payload):
    model = getattr(models(), name)
    model(**payload)
    for key in payload:
        omitted = dict(payload)
        del omitted[key]
        with pytest.raises(ValidationError):
            model(**omitted)
    with pytest.raises(ValidationError):
        model(**dict(payload, unexpected=True))


D2_INTS = (
    [
        ("PitBoundaryEvidence", boundary(), key)
        for key in (
            "source_evidence_count",
            "lap_number",
            "entry_session_time_ms",
            "exit_session_time_ms",
        )
    ]
    + [("PitTransitionContext", transition(), "reported_stint")]
    + [
        ("PitLaneEvidence", pit(), key)
        for key in (
            "source_boundary_count",
            "entry_lap_number",
            "exit_lap_number",
            "entry_session_time_ms",
            "exit_session_time_ms",
            "entry_to_exit_elapsed_ms",
        )
    ]
    + [("PitEvidenceCounts", counts(), key) for key in counts()]
)


@pytest.mark.parametrize("name,payload,key", D2_INTS)
@pytest.mark.parametrize("bad", BAD_INTS)
def test_d2_every_integer_is_strict(name, payload, key, bad):
    with pytest.raises(ValidationError):
        getattr(models(), name)(**dict(payload, **{key: bad}))


def context():
    return dict(
        year=2025,
        event=dict(
            name="Italian Grand Prix",
            round_number=16,
            country="Italy",
            location="Monza",
        ),
        session=dict(name="Race", type="Race"),
        circuit=dict(name="Monza"),
    )


def participant(number="2"):
    return dict(
        driver=identity(number),
        classification=classification(),
        latest_lap_context=None,
        pit_evidence_counts=counts(),
        unassociated_evidence_count=0,
    )


def session():
    return dict(
        context=context(),
        participants=[participant(n) for n in ("1", "2", "10", "A", "B")],
        source=dict(provider="FastF1"),
    )


def detail():
    return dict(
        context=context(),
        participant=participant(),
        lap_contexts=[],
        pit_evidence=[],
        source=dict(provider="FastF1"),
    )


def populated_detail():
    payload = detail()
    payload["lap_contexts"] = [
        lap(),
        dict(lap(2), reported_compound="SOFT", reported_stint=2),
    ]
    payload["participant"]["latest_lap_context"] = deepcopy(payload["lap_contexts"][1])
    payload["pit_evidence"] = [
        pit(state)
        for state in (
            "complete",
            "unpaired_entry",
            "unpaired_exit",
            "conflicting",
            "unavailable",
        )
    ]
    payload["participant"]["pit_evidence_counts"] = counts(
        complete=1, unpaired_entry=1, unpaired_exit=1, conflicting=1, unavailable=1
    )
    return payload


@pytest.mark.parametrize(
    "name",
    [
        "SessionRaceContextParticipant",
        "SessionRaceContextResponse",
        "DriverRaceContextResponse",
    ],
)
def test_d3_response_models_exist(name):
    assert hasattr(models(), name), f"Missing public response model: {name}"


def test_d3_zero_evidence_participant_and_compact_session():
    m = models()
    payload = session()
    before = deepcopy(payload)
    result = m.SessionRaceContextResponse(**payload)
    assert result.model_dump(mode="json") == before
    assert payload == before
    assert set(result.participants[0].model_dump()) == set(participant())
    for key in ("lap_contexts", "pit_evidence"):
        with pytest.raises(ValidationError):
            m.SessionRaceContextParticipant(**dict(participant(), **{key: []}))
        with pytest.raises(ValidationError):
            m.SessionRaceContextResponse(**dict(payload, **{key: []}))


@pytest.mark.parametrize(
    "numbers",
    [
        ["1", "10", "2", "A", "B"],
        ["A", "1"],
        ["1", "B", "A"],
        ["1", "1"],
        ["A", "A"],
    ],
)
def test_d3_participant_order_and_duplicates_reject_without_repair(numbers):
    payload = dict(session(), participants=[participant(n) for n in numbers])
    before = deepcopy(payload)
    with pytest.raises(ValidationError):
        models().SessionRaceContextResponse(**payload)
    assert payload == before


def test_d3_driver_complete_collection_and_item_counts_not_source_multiplicity():
    payload = populated_detail()
    before = deepcopy(payload)
    result = models().DriverRaceContextResponse(**payload)
    assert result.model_dump(mode="json") == before
    assert result.participant.pit_evidence_counts.total == 5
    assert result.participant.pit_evidence_counts.conflicting == 1
    assert result.pit_evidence[3].source_boundary_count == 3
    assert payload == before


@pytest.mark.parametrize(
    "mutation",
    [
        "lap_order",
        "lap_duplicate",
        "lap_driver",
        "latest_driver",
        "latest_missing",
        "latest_contradiction",
        "boundary_driver",
        "boundary_missing_lap",
        "transition_fact",
        "transition_status",
        "counts_distribution",
        "counts_total",
    ],
)
def test_d3_composition_contradictions_reject_without_repair(mutation):
    payload = populated_detail()
    if mutation == "lap_order":
        payload["lap_contexts"].reverse()
    elif mutation == "lap_duplicate":
        payload["lap_contexts"].append(deepcopy(payload["lap_contexts"][1]))
    elif mutation == "lap_driver":
        payload["lap_contexts"][0]["driver_number"] = "9"
    elif mutation == "latest_driver":
        payload["participant"]["latest_lap_context"]["driver_number"] = "9"
    elif mutation == "latest_missing":
        payload["participant"]["latest_lap_context"] = lap(3)
    elif mutation == "latest_contradiction":
        payload["participant"]["latest_lap_context"]["reported_compound"] = "MEDIUM"
    elif mutation == "boundary_driver":
        payload["pit_evidence"][1]["boundaries"][0]["lap_context_reference"][
            "driver_number"
        ] = "9"
        payload["pit_evidence"][1]["entry_context"]["lap_context_reference"][
            "driver_number"
        ] = "9"
    elif mutation == "boundary_missing_lap":
        payload["lap_contexts"].pop(0)
    elif mutation == "transition_fact":
        payload["pit_evidence"][1]["entry_context"]["reported_compound"] = "MEDIUM"
    elif mutation == "transition_status":
        payload["pit_evidence"][1]["entry_context"]["availability"] = "conflicting"
    elif mutation == "counts_distribution":
        payload["participant"]["pit_evidence_counts"].update(
            complete=0, unpaired_entry=2
        )
    elif mutation == "counts_total":
        payload["participant"]["pit_evidence_counts"] = counts(
            complete=2, unpaired_entry=1, unpaired_exit=1, conflicting=1, unavailable=1
        )
    before = deepcopy(payload)
    with pytest.raises(ValidationError):
        models().DriverRaceContextResponse(**payload)
    assert payload == before


def test_d3_latest_is_checked_as_shared_fact_not_reselected():
    payload = populated_detail()
    payload["participant"]["latest_lap_context"] = deepcopy(payload["lap_contexts"][0])
    assert (
        models()
        .DriverRaceContextResponse(**payload)
        .participant.latest_lap_context.lap_number
        == 1
    )
    payload["participant"]["latest_lap_context"] = None
    assert (
        models().DriverRaceContextResponse(**payload).participant.latest_lap_context
        is None
    )


def detail_with_pits(items):
    payload = detail()
    payload["lap_contexts"] = [lap(), lap(2)]
    payload["pit_evidence"] = items
    payload["participant"]["pit_evidence_counts"] = counts(
        **{
            state: sum(item["state"] == state for item in items)
            for state in counts()
            if state != "total"
        }
    )
    return payload


@pytest.mark.parametrize("reverse", [False, True])
def test_d3_pit_item_collision_retains_input_without_lap_or_state_tiebreak(reverse):
    a = dict(
        pit("unpaired_exit"),
        boundaries=[boundary("exit", 2, 1)],
        exit_lap_number=2,
        exit_session_time_ms=1,
        exit_context=transition(2),
    )
    b = dict(
        pit("unpaired_entry"),
        boundaries=[boundary("entry", 1, 1)],
        entry_session_time_ms=1,
    )
    payload = detail_with_pits([b, a] if reverse else [a, b])
    before = deepcopy(payload)
    assert (
        models().DriverRaceContextResponse(**payload).model_dump(mode="json") == before
    )
    assert payload == before


@pytest.mark.parametrize(
    "case", ["chronology", "usable_last", "absent_laps", "absent_states"]
)
def test_d3_provable_pit_item_order_reversal_rejects(case):
    a, b = pit("unpaired_entry"), pit("unpaired_exit")
    if case == "chronology":
        a["entry_session_time_ms"] = 20
        a["boundaries"][0]["entry_session_time_ms"] = 20
    elif case == "usable_last":
        a = pit("unavailable")
    elif case == "absent_laps":
        a, b = pit("unavailable"), pit("unavailable")
        a["boundaries"][0].update(lap_number=2, lap_context_reference=reference(2))
    else:
        a, b = pit("unavailable"), pit("conflicting")
    payload = detail_with_pits([a, b])
    before = deepcopy(payload)
    with pytest.raises(ValidationError):
        models().DriverRaceContextResponse(**payload)
    assert payload == before


D3_VALUES = [
    ("SessionRaceContextParticipant", participant()),
    ("SessionRaceContextResponse", session()),
    ("DriverRaceContextResponse", detail()),
]


@pytest.mark.parametrize("name,payload", D3_VALUES)
def test_d3_required_fields_and_extras(name, payload):
    model = getattr(models(), name)
    model(**payload)
    for key in payload:
        omitted = dict(payload)
        del omitted[key]
        with pytest.raises(ValidationError):
            model(**omitted)
    with pytest.raises(ValidationError):
        model(**dict(payload, unexpected=True))


@pytest.mark.parametrize("bad", BAD_INTS)
def test_d3_unassociated_count_is_strict(bad):
    with pytest.raises(ValidationError):
        models().SessionRaceContextParticipant(
            **dict(participant(), unassociated_evidence_count=bad)
        )


def test_d3_response_reuses_existing_shared_types():
    from app.models.pace_models import AnalyticsSessionContext
    from app.models.session_models import SourceProvenance

    m = models()
    for model in (m.SessionRaceContextResponse, m.DriverRaceContextResponse):
        assert model.model_fields["context"].annotation is AnalyticsSessionContext
        assert model.model_fields["source"].annotation is SourceProvenance


@pytest.mark.parametrize("name,payload", D1_VALUES + D2_VALUES + D3_VALUES)
def test_contract_schema_has_exact_required_fields_and_forbids_extras(name, payload):
    schema = getattr(models(), name).model_json_schema()
    assert set(schema["properties"]) == set(payload)
    assert set(schema["required"]) == set(payload)
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "name,values",
    [
        ("RaceContextEvidenceStatus", ["available", "conflicting", "unavailable"]),
        ("RaceContextAvailability", ["available", "unavailable"]),
        (
            "EqualDistanceTimeDeficitStatus",
            ["available", "not_applicable", "unavailable"],
        ),
        (
            "NormalizedTrackStatus",
            [
                "green",
                "yellow",
                "safety_car",
                "virtual_safety_car",
                "virtual_safety_car_ending",
                "red_flag",
                "unknown",
            ],
        ),
        (
            "PitEvidenceState",
            [
                "complete",
                "unpaired_entry",
                "unpaired_exit",
                "conflicting",
                "unavailable",
            ],
        ),
        ("PitBoundaryKind", ["entry", "exit"]),
    ],
)
def test_contract_enum_vocabulary_has_no_aliases(name, values):
    enum = getattr(models(), name)
    assert [member.value for member in enum] == values
    assert len(enum.__members__) == len(values)


@pytest.mark.parametrize(
    "name,payload,key",
    [
        ("TrackStatusContext", track(), "track_statuses"),
        (
            "SessionRaceContextResponse",
            dict(session(), participants=[]),
            "participants",
        ),
        ("DriverRaceContextResponse", detail(), "lap_contexts"),
        ("DriverRaceContextResponse", detail(), "pit_evidence"),
    ],
)
def test_unordered_collections_cannot_be_coerced_into_public_order(name, payload, key):
    payload = deepcopy(payload)
    payload[key] = set(payload[key])
    with pytest.raises(ValidationError):
        getattr(models(), name)(**payload)


def test_unordered_boundaries_cannot_be_coerced_into_public_order():
    m = models()
    payload = pit("unpaired_entry")
    payload["boundaries"] = {m.PitBoundaryEvidence(**boundary())}
    with pytest.raises(ValidationError):
        m.PitLaneEvidence(**payload)


def test_same_driver_lap_reference_cannot_contradict_its_exposed_completion():
    payload = lap()
    payload["leader_reference"]["driver_number"] = payload["driver_number"]
    with pytest.raises(ValidationError):
        models().LapCompletionContext(**payload)


@pytest.mark.parametrize("name,payload,key", D1_INTS + D2_INTS)
def test_integer_minima_reject_negative_values(name, payload, key):
    with pytest.raises(ValidationError):
        getattr(models(), name)(**dict(payload, **{key: -1}))


@pytest.mark.parametrize(
    "name,payload,key",
    [
        ("RaceClassificationContext", classification(), "source_evidence_count"),
        ("RaceClassificationContext", classification(), "finish_position"),
        ("LapContextReference", reference(), "lap_number"),
        ("LeaderReference", lap()["leader_reference"], "lap_number"),
        ("LapCompletionContext", lap(), "lap_number"),
        ("LapCompletionContext", lap(), "source_evidence_count"),
        ("LapCompletionContext", lap(), "lap_completion_position"),
        ("LapCompletionContext", lap(), "reported_stint"),
        ("PitBoundaryEvidence", boundary(), "source_evidence_count"),
        ("PitBoundaryEvidence", boundary(), "lap_number"),
        ("PitTransitionContext", transition(), "reported_stint"),
        ("PitLaneEvidence", pit(), "source_boundary_count"),
        ("PitLaneEvidence", pit(), "entry_lap_number"),
        ("PitLaneEvidence", pit(), "exit_lap_number"),
    ],
)
def test_positive_integer_fields_reject_zero(name, payload, key):
    with pytest.raises(ValidationError):
        getattr(models(), name)(**dict(payload, **{key: 0}))


@pytest.mark.parametrize("bad", [0, 1, "true", "false", b"true"])
@pytest.mark.parametrize(
    "name,payload,key",
    [
        ("TrackStatusContext", track(), "is_disrupted"),
        ("LapCompletionContext", lap(), "provider_generated"),
        ("PitLaneEvidence", pit(), "reported_compound_changed"),
        ("PitLaneEvidence", pit(), "reported_stint_changed"),
    ],
)
def test_every_boolean_field_is_strict(name, payload, key, bad):
    with pytest.raises(ValidationError):
        getattr(models(), name)(**dict(payload, **{key: bad}))


def test_explicit_null_boundary_and_context_facts_remain_representable():
    m = models()
    payload = boundary(status="unavailable", time=None, number=None)
    assert m.PitBoundaryEvidence(**payload).model_dump(mode="json") == payload
    payload = dict(
        transition(),
        availability="conflicting",
        reported_compound=None,
        reported_stint=None,
        lap_context_reference=None,
    )
    assert m.PitTransitionContext(**payload).model_dump(mode="json") == payload


@pytest.mark.parametrize("name,payload", D1_VALUES + D2_VALUES + D3_VALUES)
def test_new_public_models_follow_frozen_strict_contract_conventions(name, payload):
    model = getattr(models(), name)
    assert model.model_config["strict"] is True
    assert model.model_config["extra"] == "forbid"
    value = model(**payload)
    field = next(iter(payload))
    with pytest.raises(ValidationError):
        setattr(value, field, getattr(value, field))
    assert model.model_validate_json(value.model_dump_json()) == value


def test_source_boundary_order_uses_public_chronology_not_source_lap():
    payload = dict(
        pit("conflicting"),
        source_boundary_count=2,
        boundaries=[
            boundary("exit", 2, 1, "conflicting"),
            boundary("entry", 1, 2, "conflicting"),
        ],
    )
    before = deepcopy(payload)
    assert models().PitLaneEvidence(**payload).model_dump(mode="json") == before
    assert payload == before


def test_architecture_has_no_provider_analytics_service_or_transport_imports():
    import ast
    from pathlib import Path

    module = models()
    tree = ast.parse(Path(module.__file__).read_text())
    imported = [
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    imported.extend(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    forbidden = (
        "app.analytics",
        "app.data",
        "app.services",
        "app.main",
        "fastf1",
        "pandas",
        "numpy",
        "fastapi",
    )
    assert not any(name.startswith(forbidden) for name in imported)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not calls & {"sorted", "round"}
