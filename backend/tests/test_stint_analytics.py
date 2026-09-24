"""Offline construction, qualification, and observational estimator checks."""

from collections import Counter
from dataclasses import FrozenInstanceError, replace

import pytest

from app.lap_analytics import DriverIdentity, SessionFieldInput, SourceLap


def lap(number=2, **changes):
    return replace(
        SourceLap(
            1, "2", number, 90_000_000_000, compound="MEDIUM", stint=7, tyre_life=8
        ),
        **changes,
    )


def construct(rows, participants=(DriverIdentity("2"),)):
    from app.stint_analytics import construct_session_stints

    return construct_session_stints(SessionFieldInput(participants, tuple(rows)))


def assert_reconciled(driver, rows):
    assigned = tuple(e for stint in driver.stints for e in stint.laps)
    unassigned = tuple(e for e in driver.laps if e.reported_stint is None)
    # Identity accounting checks every retained source object, including copies.
    assert Counter(id(e.lap) for e in driver.laps) == Counter(map(id, rows))
    assert Counter(id(e) for e in assigned + unassigned) == Counter(
        map(id, driver.laps)
    )
    assert driver.unassigned_lap_count == len(unassigned)
    assert len(driver.laps) == sum(
        s.sample.total_lap_count for s in driver.stints
    ) + len(unassigned)
    for stint in driver.stints:
        assert stint.sample.total_lap_count == len(stint.laps)
        assert all(e.reported_stint == stint.reported_stint for e in stint.laps)


def test_reported_identity_is_not_split_merged_or_renumbered():
    rows = (
        lap(2, stint=9),
        lap(3, stint=9, pit_in=True),
        lap(4, stint=9, pit_out=True),
        lap(5, stint=3),
    )
    (driver,) = construct(rows[::-1]).drivers
    assert [s.reported_stint for s in driver.stints] == [9, 3]
    assert [s.sample.total_lap_count for s in driver.stints] == [3, 1]
    assert all(s.metadata_reason is None for s in driver.stints)
    assert_reconciled(driver, rows)


def test_missing_or_normalized_unusable_stint_is_only_unassigned():
    # Malformed raw identifiers already normalize to None at the source boundary.
    rows = (
        lap(2, stint=None, pit_in=True),
        lap(3, stint=None, pit_out=True, compound="HARD"),
    )
    (driver,) = construct(rows).drivers
    assert driver.stints == ()
    assert driver.unassigned_lap_count == 2
    assert all(e.unassigned_reason == "missing_stint_metadata" for e in driver.laps)
    assert_reconciled(driver, rows)


def test_authoritative_roster_and_zero_row_participants():
    participants = (
        DriverIdentity("10", "TEN", "Driver Ten", "Team"),
        DriverIdentity("2", "TWO"),
        DriverIdentity("99"),
    )
    rows = (lap(), lap(driver_number="10", stint=None))
    result = construct(rows, participants)
    assert [d.driver.driver_number for d in result.drivers] == ["2", "10", "99"]
    assert result.drivers[1].driver is participants[0]
    assert result.drivers[2].stints == result.drivers[2].laps == ()
    assert result.drivers[2].unassigned_lap_count == 0
    for driver in result.drivers:
        assert_reconciled(
            driver, [r for r in rows if r.driver_number == driver.driver.driver_number]
        )


@pytest.mark.parametrize(
    "ids,inconsistent",
    [
        ((7, 7, 7), set()),
        ((7, 3, 7), {7}),
        ((7, None, 7), {7}),
        ((9, 3, 1), set()),
        ((7, 3, 7, 3), {7, 3}),
    ],
)
def test_continuity_uses_valid_lap_chronology(ids, inconsistent):
    rows = tuple(lap(i + 2, stint=stint) for i, stint in enumerate(ids))
    (driver,) = construct(rows[::-1]).drivers
    assert {s.reported_stint for s in driver.stints} == set(ids) - {None}
    assert {
        s.reported_stint for s in driver.stints if s.metadata_reason
    } == inconsistent
    assert all(
        s.metadata_reason == "inconsistent_stint_metadata"
        for s in driver.stints
        if s.reported_stint in inconsistent
    )
    assert_reconciled(driver, rows)


def test_null_lap_numbers_are_assigned_but_do_not_define_continuity():
    rows = (
        lap(2),
        lap(None, stint=3),
        lap(4),
        lap(None, stint=None),
        lap(None, stint=1),
    )
    (driver,) = construct(rows).drivers
    assert [s.reported_stint for s in driver.stints] == [7, 1, 3]
    assert all(s.metadata_reason is None for s in driver.stints)
    assert all(
        e.structural_reason == "invalid_timing"
        for e in driver.laps
        if e.lap.lap_number is None
    )
    assert_reconciled(driver, rows)


@pytest.mark.parametrize(
    "compounds,inconsistent",
    [
        (("medium", "MEDIUM", "Medium"), False),
        ((" MEDIUM ", "medium"), False),
        (("MEDIUM", None), False),
        ((None, None), False),
        (("WET", "wet"), False),
        (("UNKNOWN", "unknown"), False),
        (("MEDIUM", "HARD"), True),
        (("UNKNOWN", "OTHER"), True),
    ],
)
def test_compound_continuity_preserves_evidence_without_reconstruction(
    compounds, inconsistent
):
    rows = tuple(lap(i + 2, compound=c, pit_in=True) for i, c in enumerate(compounds))
    (driver,) = construct(rows[::-1]).drivers
    (stint,) = driver.stints
    assert stint.reported_stint == 7
    assert (stint.metadata_reason is not None) == inconsistent
    assert [e.lap.compound for e in driver.laps] == list(compounds)
    assert stint.reported_compound == compounds[0]
    assert_reconciled(driver, rows)


def test_ranges_retain_reported_age_and_invalid_timing_evidence():
    rows = (
        lap(6, tyre_life=12),
        lap(2, tyre_life=8),
        lap(None, tyre_life=20, compound="medium"),
        lap(4, tyre_life=None),
    )
    (driver,) = construct(rows).drivers
    (stint,) = driver.stints
    assert (stint.lap_range.minimum, stint.lap_range.maximum) == (2, 6)
    assert (
        stint.reported_tire_age_range.minimum,
        stint.reported_tire_age_range.maximum,
    ) == (8, 20)
    assert stint.reported_compound == "MEDIUM"
    assert stint.metadata_reason is None
    assert_reconciled(driver, rows)


def test_construction_reuses_shared_classifier(monkeypatch):
    from unittest.mock import Mock

    from app import stint_analytics

    shared = Mock(wraps=stint_analytics.classify_structural_status_laps)
    monkeypatch.setattr(stint_analytics, "classify_structural_status_laps", shared)
    rows = (
        lap(2, pit_in=True, track_status_codes=("7", "2")),
        lap(3, is_accurate=False, provider_generated=True, tyre_life=None),
    )
    (driver,) = construct(rows).drivers
    shared.assert_called_once()
    assert driver.laps[0].structural_reason == "pit_in"
    assert driver.laps[0].disruptive_statuses == ("yellow", "virtual_safety_car_ending")
    assert driver.laps[1].structural_reason is None
    assert driver.laps[1].lap is rows[1]


def test_construction_results_are_immutable():
    (driver,) = construct((lap(),)).drivers
    for obj, name, value in (
        (driver, "stints", ()),
        (driver.stints[0], "reported_stint", 99),
        (driver.laps[0], "lap", lap(9)),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, name, value)


def test_unrostered_rows_fail_instead_of_creating_a_driver():
    with pytest.raises(ValueError, match="participant"):
        construct((lap(driver_number="99"),))


@pytest.mark.parametrize(
    "ids", [(7, 7), (7, 3), (7, None), (None, None), (7, 3, None, 7)]
)
def test_duplicate_identity_retains_every_assignment_and_blocks_each_stint(ids):
    rows = tuple(lap(4, stint=stint, tyre_life=i + 8) for i, stint in enumerate(ids))
    (driver,) = construct(rows).drivers
    assert {s.reported_stint for s in driver.stints} == set(ids) - {None}
    for stint in driver.stints:
        assert stint.metadata_reason == "inconsistent_stint_metadata"
        assert stint.metadata_valid_laps == ()
        assert stint.sample.total_lap_count == ids.count(stint.reported_stint)
    assert driver.unassigned_lap_count == ids.count(None)
    assert_reconciled(driver, rows)


def test_identical_duplicate_multiplicity_and_whole_stint_block():
    duplicate = lap(4)
    rows = (lap(2), duplicate, duplicate, replace(duplicate, source_order=99), lap(5))
    (driver,) = construct(rows).drivers
    (stint,) = driver.stints
    assert stint.metadata_reason == "inconsistent_stint_metadata"
    assert stint.metadata_valid_laps == ()
    assert stint.sample.total_lap_count == 5
    assert driver.laps[1] == driver.laps[2] == driver.laps[3]
    assert_reconciled(driver, rows)


@pytest.mark.parametrize("identical", [False, True])
def test_duplicate_permutations_and_source_positions_have_identical_content(identical):
    from itertools import permutations

    rows = (
        lap(4, stint=7),
        lap(4, stint=7 if identical else 3),
        lap(4, stint=7 if identical else None),
        lap(5, stint=9),
    )
    expected = construct(rows)
    assert expected == construct(rows) == construct(rows)
    for permutation in permutations(rows):
        repositioned = tuple(
            replace(row, source_order=100 - i) for i, row in enumerate(permutation)
        )
        actual = construct(repositioned)
        assert actual == expected
        assert_reconciled(actual.drivers[0], repositioned)
    assert all(
        s.metadata_valid_laps == ()
        for s in expected.drivers[0].stints
        if s.reported_stint != 9
    )
    assert expected.drivers[0].stints[-1].metadata_reason is None


def test_duplicate_identity_is_driver_scoped_and_requires_valid_lap_number():
    rows = (lap(4), lap(4, driver_number="10"), lap(None), lap(None))
    result = construct(rows, (DriverIdentity("10"), DriverIdentity("2")))
    assert all(s.metadata_reason is None for d in result.drivers for s in d.stints)
    for driver in result.drivers:
        assert_reconciled(
            driver, [r for r in rows if r.driver_number == driver.driver.driver_number]
        )


@pytest.mark.parametrize(
    "field,values",
    [
        ("driver_number", ("2", "10")),
        ("lap_number", (2, 3, None)),
        ("stint", (3, 7, None)),
        ("tyre_life", (8, 9, None)),
        ("lap_time_ns", (90_000_000_001, 90_000_000_002, None)),
        ("compound", ("HARD", "MEDIUM", "medium", None)),
        ("pit_in", (False, True)),
        ("pit_out", (False, True)),
        ("track_status_codes", (("1",), ("2",), ("2", "4"), None)),
        ("is_accurate", (False, True, None)),
        ("provider_generated", (False, True, None)),
    ],
)
def test_canonical_key_ranks_each_fact_explicitly(field, values):
    from app.stint_analytics import canonical_lap_key

    rows = tuple(lap(**{field: value}) for value in values)
    assert tuple(sorted(rows[::-1], key=canonical_lap_key)) == rows
    assert len({canonical_lap_key(row) for row in rows}) == len(values)
    assert canonical_lap_key(rows[0]) == canonical_lap_key(
        replace(rows[0], source_order=-999)
    )


def test_canonical_key_prioritizes_facts_in_approved_sequence():
    from app.stint_analytics import canonical_lap_key

    # Each earlier field must dominate even when every later field sorts later.
    early = dict(
        driver_number="2",
        lap_number=2,
        stint=3,
        tyre_life=8,
        lap_time_ns=90_000_000_001,
        compound="HARD",
        pit_in=False,
        pit_out=False,
        track_status_codes=("1",),
        is_accurate=False,
        provider_generated=False,
    )
    late = dict(
        driver_number="10",
        lap_number=None,
        stint=None,
        tyre_life=None,
        lap_time_ns=None,
        compound=None,
        pit_in=True,
        pit_out=True,
        track_status_codes=None,
        is_accurate=None,
        provider_generated=None,
    )
    names = tuple(early)
    for i, name in enumerate(names):
        left = dict(early)
        right = dict(early)
        left.update({n: late[n] for n in names[i + 1 :]})
        right[name] = late[name]
        assert canonical_lap_key(lap(**left)) < canonical_lap_key(lap(**right))


def test_summary_compound_selection_is_lap_then_token_not_age():
    rows = (
        lap(4, compound="medium", tyre_life=1),
        lap(4, compound="MEDIUM", tyre_life=20),
        lap(None, compound="HARD"),
    )
    (stint,) = construct(rows).drivers[0].stints
    assert stint.reported_compound == "MEDIUM"
    assert stint.compound_keys == ("HARD", "MEDIUM")


def test_pure_module_has_only_approved_analytics_imports():
    import ast
    import inspect

    import app.stint_analytics as analytics

    tree = ast.parse(inspect.getsource(analytics))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)
        if isinstance(node, ast.Attribute):
            assert node.attr != "source_order"
    assert set(imports) <= {
        "dataclasses",
        "enum",
        "collections",
        "decimal",
        "math",
        "statistics",
        "scipy.stats",
        "app.lap_analytics",
    }


def decisions(rows):
    from app.stint_analytics import classify_stint_laps

    return classify_stint_laps(construct(rows).drivers[0].laps)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"lap_time_ns": None, "lap_number": 1, "pit_in": True}, "invalid_timing"),
        ({"lap_number": None}, "invalid_timing"),
        ({"lap_number": 1, "pit_in": True}, "lap_one_start"),
        ({"pit_in": True, "pit_out": True}, "pit_in"),
        ({"pit_out": True}, "pit_out"),
        ({"track_status_codes": ("7", "2")}, "disrupted_status"),
        ({"track_status_codes": ("1",)}, "explicitly_inaccurate"),
        ({"track_status_codes": ("1",), "is_accurate": True}, "provider_generated"),
        (
            {
                "track_status_codes": ("1",),
                "is_accurate": True,
                "provider_generated": False,
            },
            "unusable_tire_age",
        ),
    ],
)
def test_stint_first_match_exclusions(changes, reason):
    row = replace(
        lap(
            is_accurate=False,
            provider_generated=True,
            tyre_life=None,
            track_status_codes=("2",),
        ),
        **changes,
    )
    (decision,) = decisions((row,))
    assert decision.primary_exclusion_reason == reason
    assert decision.disposition == "excluded"
    assert decision.unassigned_reason is None
    assert decision.lap is row


@pytest.mark.parametrize("accurate", [True, False, None])
@pytest.mark.parametrize("generated", [True, False, None])
def test_stint_quality_tri_states(accurate, generated):
    (decision,) = decisions((lap(is_accurate=accurate, provider_generated=generated),))
    expected = (
        "explicitly_inaccurate"
        if accurate is False
        else ("provider_generated" if generated is True else None)
    )
    assert decision.primary_exclusion_reason == expected
    assert decision.disposition == ("excluded" if expected else "eligible")


def test_unassigned_remains_separate_from_every_exclusion():
    (decision,) = decisions(
        (
            lap(
                stint=None,
                lap_time_ns=None,
                is_accurate=False,
                provider_generated=True,
                tyre_life=None,
                track_status_codes=("2",),
            ),
        )
    )
    assert decision.disposition == "unassigned"
    assert decision.primary_exclusion_reason is None
    assert decision.unassigned_reason == "missing_stint_metadata"
    assert decision.structural_reason == "invalid_timing"
    assert decision.disruptive_statuses == ("yellow",)


def test_feature_two_anomaly_is_not_a_stint_exclusion():
    from app.lap_analytics import classify_driver_laps

    rows = (lap(2), lap(3, lap_time_ns=180_000_000_000, tyre_life=9))
    assert classify_driver_laps(rows)[1].primary_exclusion_reason == "anomalous_pace"
    assert all(d.disposition == "eligible" for d in decisions(rows))


@pytest.mark.parametrize(
    "ages,consistent,minimum",
    [
        ((8, 9, 10, 11, 12, 13), True, True),
        ((8, 10, 13, 15, 19, 22), True, True),
        ((8, 9, 10, 11, 12), True, False),
        ((8, 9, 10, 10, 11, 12), False, False),
        ((8, 9, 10, 11, 12, 8), False, False),
        ((8, 9, 10, 11, 13, 12), False, True),
        ((8, None, 9, 10, 11, 12, 13), True, True),
        ((), True, False),
    ],
)
def test_eligible_age_sample_uses_reported_chronology(ages, consistent, minimum):
    from app.stint_analytics import assess_tire_age_sample

    rows = tuple(
        lap(i + 2, tyre_life=age, source_order=100 - i) for i, age in enumerate(ages)
    )
    classified = decisions(rows[::-1])
    eligible = tuple(d for d in classified if d.disposition == "eligible")
    assessment = assess_tire_age_sample(eligible)
    assert assessment.is_consistent is consistent
    assert assessment.has_minimum_sample is minimum
    assert tuple(d.lap.tyre_life for d in eligible) == tuple(
        a for a in ages if a is not None
    )
    assert sum(
        d.primary_exclusion_reason == "unusable_tire_age" for d in classified
    ) == ages.count(None)


def test_excluded_ages_do_not_corrupt_candidate_history():
    from app.stint_analytics import assess_tire_age_sample

    rows = (
        lap(2, tyre_life=8),
        lap(3, tyre_life=1, is_accurate=False),
        lap(4, tyre_life=2, pit_in=True),
        lap(5, tyre_life=10),
    )
    eligible = tuple(d for d in decisions(rows) if d.disposition == "eligible")
    assert assess_tire_age_sample(eligible).is_consistent
    assert [d.lap.tyre_life for d in eligible] == [8, 10]


def test_stint_exclusion_policy_is_exact_and_does_not_extend_feature_two():
    from app.lap_analytics import EXCLUSION_PRECEDENCE
    from app.stint_analytics import STINT_ANALYSIS_POLICY, StintLapExclusionReason

    expected = (
        "invalid_timing",
        "lap_one_start",
        "pit_in",
        "pit_out",
        "disrupted_status",
        "explicitly_inaccurate",
        "provider_generated",
        "unusable_tire_age",
    )
    assert tuple(StintLapExclusionReason) == expected
    assert STINT_ANALYSIS_POLICY.lap_exclusion_precedence == expected
    assert EXCLUSION_PRECEDENCE[-1] == "anomalous_pace"


def analyze(rows, participants=(DriverIdentity("2"),)):
    from app.stint_analytics import analyze_session_stints

    return analyze_session_stints(SessionFieldInput(participants, tuple(rows)))


def stint_rows(count=6, **changes):
    return tuple(lap(i + 2, tyre_life=i + 8, **changes) for i in range(count))


@pytest.mark.parametrize(
    "compound,reason,normalized",
    [
        ("SOFT", None, "SOFT"),
        ("MEDIUM", None, "MEDIUM"),
        ("HARD", None, "HARD"),
        (" medium ", None, "MEDIUM"),
        ("INTERMEDIATE", "wet_weather_compound", "INTERMEDIATE"),
        ("wet", "wet_weather_compound", "WET"),
        (None, "missing_compound", None),
        ("UNKNOWN", "unsupported_compound", None),
    ],
)
def test_stint_compound_availability(compound, reason, normalized):
    rows = stint_rows(compound=compound)
    (driver,) = analyze(rows).drivers
    (stint,) = driver.stints
    assert stint.reported_compound == compound
    assert stint.normalized_compound == normalized
    assert stint.unavailability_reason == reason
    assert stint.status == ("unavailable" if reason else "available")
    assert len(stint.available_sample) == (0 if reason else 6)
    if reason:
        assert getattr(stint, "observed_pace_trend_seconds_per_lap", None) is None
        assert getattr(stint, "median_absolute_residual_seconds", None) is None
    assert_reconciled(driver, rows)


def test_conflicting_recognized_compounds_do_not_publish_trusted_compound():
    rows = stint_rows(compound="medium") + (lap(9, compound="HARD"),)
    (stint,) = analyze(rows[::-1]).drivers[0].stints
    assert stint.reported_compound == "medium"
    assert stint.normalized_compound is None
    assert stint.status == "unavailable"
    assert stint.unavailability_reason == "inconsistent_stint_metadata"
    assert stint.available_sample == ()


@pytest.mark.parametrize(
    "compounds,ages,reason",
    [
        (("WET", "HARD"), (8, 8), "inconsistent_stint_metadata"),
        (("MEDIUM", "HARD", None), (8, 8, 8), "inconsistent_stint_metadata"),
        (("WET", "WET"), (8, 8), "wet_weather_compound"),
        (("WET", None), (8, None), "wet_weather_compound"),
        (("MEDIUM", None), (8, 8), "missing_compound"),
        (("UNKNOWN", "UNKNOWN"), (8, 8), "unsupported_compound"),
        (("UNKNOWN", None), (8, 8), "missing_compound"),
        (("MEDIUM", "MEDIUM", "MEDIUM"), (8, 8, None), "inconsistent_tire_age"),
    ],
)
def test_availability_precedence_and_approved_compound_tie(compounds, ages, reason):
    rows = tuple(
        lap(i + 2, compound=c, tyre_life=a)
        for i, (c, a) in enumerate(zip(compounds, ages, strict=True))
    )
    (stint,) = analyze(rows).drivers[0].stints
    assert stint.unavailability_reason == reason
    assert stint.available_sample == ()


@pytest.mark.parametrize(
    "valid,extra_count,extra,reason",
    [
        (5, 1, {"tyre_life": None}, "missing_tire_age"),
        (4, 2, {"tyre_life": None}, "missing_tire_age"),
        (3, 3, {"tyre_life": None}, "missing_tire_age"),
        (0, 6, {"tyre_life": None}, "missing_tire_age"),
        (2, 8, {"tyre_life": None}, "missing_tire_age"),
        (2, 2, {"tyre_life": None}, "insufficient_eligible_sample"),
        (4, 1, {"tyre_life": None}, "insufficient_eligible_sample"),
        (5, 1, {"is_accurate": False}, "insufficient_eligible_sample"),
        (5, 1, {"provider_generated": True}, "insufficient_eligible_sample"),
        (5, 1, {"pit_in": True, "tyre_life": None}, "insufficient_eligible_sample"),
        (
            5,
            1,
            {"is_accurate": False, "tyre_life": None},
            "insufficient_eligible_sample",
        ),
        (6, 1, {"tyre_life": None}, None),
    ],
)
def test_sample_decisive_unusable_age(valid, extra_count, extra, reason):
    rows = stint_rows(valid) + tuple(
        replace(lap(valid + 2 + i, tyre_life=30 + i), **extra)
        for i in range(extra_count)
    )
    (driver,) = analyze(rows).drivers
    (stint,) = driver.stints
    assert stint.unavailability_reason == reason
    assert stint.sample.eligible_observation_count == valid
    assert stint.sample.excluded_observation_count == extra_count
    if extra == {"tyre_life": None}:
        assert dict(stint.sample.exclusions)["unusable_tire_age"] == extra_count
    assert_reconciled(driver, rows)


@pytest.mark.parametrize(
    "ages,unusable", [((8, 9, 10, 10, 11), 1), ((8, 9, 11, 10), 2)]
)
def test_inconsistent_tire_age_outranks_sample_decisive_missing_age(ages, unusable):
    rows = tuple(lap(i + 2, tyre_life=age) for i, age in enumerate(ages)) + tuple(
        lap(len(ages) + 2 + i, tyre_life=None) for i in range(unusable)
    )
    (driver,) = analyze(rows).drivers
    (stint,) = driver.stints
    sample = stint.sample
    # Every missing_tire_age precondition holds, so only tier order can decide.
    assert sample.eligible_observation_count == len(ages)
    assert sample.eligible_observation_count < 6
    assert dict(sample.exclusions)["unusable_tire_age"] == unusable
    assert sample.eligible_observation_count + unusable >= 6
    assert stint.unavailability_reason == "inconsistent_tire_age"
    assert stint.available_sample == ()
    assert stint.observed_pace_trend_seconds_per_lap is None
    assert stint.median_absolute_residual_seconds is None
    assert_reconciled(driver, rows)


def sample_counts(**changes):
    from app.stint_analytics import STINT_LAP_EXCLUSION_PRECEDENCE, StintSample

    values = dict(
        total_lap_count=0,
        eligible_observation_count=0,
        excluded_observation_count=0,
        distinct_eligible_tire_age_count=0,
        exclusions=tuple((reason, 0) for reason in STINT_LAP_EXCLUSION_PRECEDENCE),
    )
    values.update(changes)
    return StintSample(**values)


@pytest.mark.parametrize(
    "field",
    [
        "total_lap_count",
        "eligible_observation_count",
        "excluded_observation_count",
        "distinct_eligible_tire_age_count",
    ],
)
@pytest.mark.parametrize("value", [-1, True, 0.5])
def test_sample_rejects_invalid_count_domain(field, value):
    with pytest.raises(ValueError, match="non-negative integers"):
        sample_counts(**{field: value})


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"total_lap_count": 1}, "total"),
        ({"total_lap_count": 1, "excluded_observation_count": 1}, "exclusion"),
        ({"distinct_eligible_tire_age_count": 1}, "distinct"),
    ],
)
def test_sample_rejects_unreconciled_counts(changes, message):
    with pytest.raises(ValueError, match=message):
        sample_counts(**changes)


@pytest.mark.parametrize("value", [-1, True, 0.5])
def test_sample_rejects_invalid_detailed_count(value):
    exclusions = sample_counts().exclusions
    with pytest.raises(ValueError, match="non-negative integers"):
        sample_counts(exclusions=((exclusions[0][0], value),) + exclusions[1:])


@pytest.mark.parametrize("case", ["missing", "duplicate", "unknown"])
def test_sample_requires_one_count_per_documented_reason(case):
    exclusions = sample_counts().exclusions
    malformed = {
        "missing": exclusions[:-1],
        "duplicate": exclusions[:-1] + (exclusions[0],),
        "unknown": exclusions[:-1] + (("anomalous_pace", 0),),
    }[case]
    with pytest.raises(ValueError, match="one count per exclusion reason"):
        sample_counts(exclusions=malformed)


def test_sample_accepts_empty_and_reconciled_counts_and_remains_frozen():
    empty = sample_counts()
    assert empty.total_lap_count == 0
    sample = sample_counts(
        total_lap_count=3,
        eligible_observation_count=2,
        excluded_observation_count=1,
        distinct_eligible_tire_age_count=1,
        exclusions=((empty.exclusions[0][0], 1),) + empty.exclusions[1:],
    )
    with pytest.raises(FrozenInstanceError):
        sample.total_lap_count = 4


@pytest.mark.parametrize("compound", ["UNKNOWN", "medium", " MEDIUM ", "", 1])
def test_analysis_rejects_out_of_domain_normalized_compound(compound):
    (stint,) = analyze(stint_rows()).drivers[0].stints
    with pytest.raises(ValueError, match="normalized_compound"):
        replace(stint, normalized_compound=compound)


def test_three_distinct_stints_on_one_lap_preserve_every_row_under_permutations():
    from itertools import permutations

    rows = tuple(lap(4, stint=stint) for stint in (7, 3, 1))
    expected = analyze(rows)
    for permutation in permutations(rows):
        actual = analyze(permutation)
        assert actual == expected
        (driver,) = actual.drivers
        assert len(driver.laps) == 3
        assert [s.reported_stint for s in driver.stints] == [1, 3, 7]
        assert_reconciled(driver, rows)
        for stint in driver.stints:
            assert stint.unavailability_reason == "inconsistent_stint_metadata"
            assert stint.available_sample == ()
            assert stint.sample.total_lap_count == 1
            assert stint.laps[0].lap is next(
                row for row in rows if row.stint == stint.reported_stint
            )


@pytest.mark.parametrize(
    "ages,reason",
    [
        ((8, 9, 10, 11, 12), "insufficient_eligible_sample"),
        ((8, 10, 13, 15, 19, 22), None),
        ((8, 9, 10, 10, 11, 12), "inconsistent_tire_age"),
        ((8, 9, 10, 11, 13, 12), "inconsistent_tire_age"),
    ],
)
def test_age_failure_blocks_whole_stint_without_rewriting_lap_decisions(ages, reason):
    rows = tuple(lap(i + 2, tyre_life=age) for i, age in enumerate(ages))
    (driver,) = analyze(rows[::-1]).drivers
    (stint,) = driver.stints
    assert stint.unavailability_reason == reason
    assert all(d.disposition == "eligible" for d in driver.laps)
    assert stint.sample.eligible_observation_count == len(ages)
    assert len(stint.available_sample) == (0 if reason else len(ages))
    assert stint.eligible_tire_age_range.minimum == min(ages)
    assert stint.eligible_tire_age_range.maximum == max(ages)


@pytest.mark.parametrize("raw_age", [None, "bad", True, -1, 1.5, float("inf")])
@pytest.mark.parametrize("valid", [5, 6])
def test_absent_and_malformed_source_age_share_sample_decisive_meaning(
    pace_session_factory, raw_age, valid
):
    from app.f1_data import map_lap_inputs
    from app.stint_analytics import analyze_session_stints

    session = pace_session_factory()
    session.laps = session.laps.iloc[:6].copy()
    if valid == 6:
        session.laps.loc[6] = session.laps.iloc[0]
    session.laps["LapNumber"] = list(range(2, valid + 3))
    session.laps["Stint"] = 7
    session.laps["TyreLife"] = list(range(8, 8 + valid)) + [raw_age]
    source = map_lap_inputs(session)
    assert source.laps[-1].tyre_life is None
    (stint,) = analyze_session_stints(source).drivers[0].stints
    assert stint.unavailability_reason == ("missing_tire_age" if valid == 5 else None)
    assert dict(stint.sample.exclusions)["unusable_tire_age"] == 1


def test_all_exclusion_counts_reconcile_and_unassigned_is_separate():
    excluded = (
        lap(20, lap_time_ns=None),
        lap(1),
        lap(21, pit_in=True),
        lap(22, pit_out=True),
        lap(23, track_status_codes=("2",)),
        lap(24, is_accurate=False),
        lap(25, provider_generated=True),
        lap(26, tyre_life=None),
    )
    rows = stint_rows() + excluded + (lap(27, stint=None),)
    (driver,) = analyze(rows).drivers
    (stint,) = driver.stints
    assert stint.status == "available"
    assert stint.sample.total_lap_count == 14
    assert stint.sample.eligible_observation_count == 6
    assert stint.sample.excluded_observation_count == 8
    assert stint.sample.distinct_eligible_tire_age_count == 6
    assert all(count == 1 for _, count in stint.sample.exclusions)
    assert sum(count for _, count in stint.sample.exclusions) == 8
    assert_reconciled(driver, rows)


@pytest.mark.parametrize(
    "blocker", ["duplicate", "continuity", "compound", "wet", "missing", "unsupported"]
)
def test_higher_metadata_tiers_skip_age_validation_but_keep_counts(
    monkeypatch, blocker
):
    from unittest.mock import Mock

    from app import stint_analytics

    rows = stint_rows()
    reason = "inconsistent_stint_metadata"
    if blocker == "duplicate":
        rows += (rows[0], replace(rows[0], stint=None))
    elif blocker == "continuity":
        rows = rows[:2] + (replace(rows[2], stint=None),) + rows[3:]
    elif blocker == "compound":
        rows += (lap(9, compound="WET", is_accurate=False),)
    else:
        compound = {"wet": "WET", "missing": None, "unsupported": "UNKNOWN"}[blocker]
        rows = tuple(replace(row, compound=compound) for row in rows)
        reason = {
            "wet": "wet_weather_compound",
            "missing": "missing_compound",
            "unsupported": "unsupported_compound",
        }[blocker]
    validator = Mock(side_effect=AssertionError("Blocked stint reached age validation"))
    monkeypatch.setattr(stint_analytics, "assess_tire_age_sample", validator)
    (driver,) = analyze(rows).drivers
    (stint,) = driver.stints
    validator.assert_not_called()
    assert stint.unavailability_reason == reason
    assert stint.available_sample == ()
    assert (
        stint.sample.total_lap_count
        == stint.sample.eligible_observation_count
        + stint.sample.excluded_observation_count
    )
    assert (
        sum(count for _, count in stint.sample.exclusions)
        == stint.sample.excluded_observation_count
    )
    assert_reconciled(driver, rows)


def test_availability_policy_has_six_tiers_and_seven_reasons():
    from app.stint_analytics import STINT_ANALYSIS_POLICY, StintUnavailabilityReason

    tiers = (
        frozenset(("inconsistent_stint_metadata",)),
        frozenset(("wet_weather_compound",)),
        frozenset(("missing_compound", "unsupported_compound")),
        frozenset(("inconsistent_tire_age",)),
        frozenset(("missing_tire_age",)),
        frozenset(("insufficient_eligible_sample",)),
    )
    assert STINT_ANALYSIS_POLICY.availability_precedence == tiers
    assert set(StintUnavailabilityReason) == set().union(*tiers)


def test_analysis_preserves_roster_and_is_permutation_deterministic():
    participants = (DriverIdentity("10"), DriverIdentity("2"), DriverIdentity("99"))
    rows = stint_rows() + (
        lap(4, driver_number="10"),
        lap(4, driver_number="10"),
        lap(5, driver_number="10", stint=None),
    )
    expected = analyze(rows, participants)
    assert expected == analyze(rows, participants) == analyze(rows, participants)
    permuted = tuple(
        replace(row, source_order=100 - i) for i, row in enumerate(rows[::-1])
    )
    assert analyze(permuted, participants[::-1]) == expected
    assert [d.driver.driver_number for d in expected.drivers] == ["2", "10", "99"]
    assert expected.drivers[-1].laps == expected.drivers[-1].stints == ()


# T019–T021: estimation starts only after complete qualification.
def qualified(rows):
    from app.stint_analytics import _qualify_stint, classify_stint_laps

    (stint,) = construct(rows).drivers[0].stints
    return _qualify_stint(stint, classify_stint_laps(stint.laps))


def estimator_sample(rows):
    from app.stint_analytics import _build_validated_estimator_sample

    return _build_validated_estimator_sample(qualified(rows))


def timed_rows(ages, nanoseconds):
    return tuple(
        lap(i + 2, tyre_life=age, lap_time_ns=ns)
        for i, (age, ns) in enumerate(zip(ages, nanoseconds, strict=True))
    )


@pytest.mark.parametrize("step", [250_000_000, 0, -250_000_000])
def test_estimator_signed_slopes(step):
    rows = timed_rows(range(8, 14), [90_000_000_000 + i * step for i in range(6)])
    (stint,) = analyze(rows).drivers[0].stints
    assert stint.observed_pace_trend_seconds_per_lap == step / 1_000_000_000
    assert stint.median_absolute_residual_seconds == 0.0
    assert stint.status == "available"


def test_estimator_keeps_extreme_eligible_outlier(monkeypatch):
    from unittest.mock import Mock

    from app import stint_analytics as analytics

    rows = timed_rows(
        range(8, 15), [90_000_000_000 + i * 250_000_000 for i in range(7)]
    )
    rows = rows[:-1] + (replace(rows[-1], lap_time_ns=300_000_000_000),)
    spy = Mock(wraps=analytics.theilslopes)
    monkeypatch.setattr(analytics, "theilslopes", spy)
    (stint,) = analyze(rows).drivers[0].stints
    assert stint.sample.eligible_observation_count == 7
    assert stint.observed_pace_trend_seconds_per_lap == 0.25
    assert stint.median_absolute_residual_seconds == 0.0
    assert spy.call_count == 1
    assert spy.call_args.args[0][-1] == 300.0


def test_estimator_joint_line_and_median_residual(monkeypatch):
    from dataclasses import asdict
    from unittest.mock import Mock

    from app import stint_analytics as analytics

    # Pairwise median slope is 1.5; joint intercept is 88.25, separate 88.75.
    # Absolute joint residuals: .25, .25, 1.25, .25, 1.75, 2.75 => median .75.
    rows = timed_rows(
        range(1, 7), [n * 1_000_000_000 for n in (90, 91, 94, 94, 94, 100)]
    )
    spy = Mock(wraps=analytics.theilslopes)
    monkeypatch.setattr(analytics, "theilslopes", spy)
    result = analytics._estimate_stint_trend(estimator_sample(rows))
    assert asdict(result) == {
        "observed_pace_trend_seconds_per_lap": 1.5,
        "median_absolute_residual_seconds": 0.75,
    }
    spy.assert_called_once_with(
        (90.0, 91.0, 94.0, 94.0, 94.0, 100.0), (1, 2, 3, 4, 5, 6), method="joint"
    )


def test_estimator_uses_reported_ages_and_unrounded_nanoseconds(monkeypatch):
    from unittest.mock import Mock

    from app import stint_analytics as analytics

    ages = (8, 10, 13, 17, 22, 28)
    durations = tuple(90_000_000_001 + age * 500_100 for age in ages)
    rows = timed_rows(ages, durations)
    spy = Mock(wraps=analytics.theilslopes)
    monkeypatch.setattr(analytics, "theilslopes", spy)
    result = analytics._estimate_stint_trend(estimator_sample(rows))
    spy.assert_called_once_with(
        tuple(ns / 1_000_000_000 for ns in durations), ages, method="joint"
    )
    assert result.observed_pace_trend_seconds_per_lap == 0.001
    assert result.median_absolute_residual_seconds == 0.0


@pytest.mark.parametrize(
    "value,expected",
    [(0.0005, 0.001), (-0.0005, -0.001), (1.2345, 1.235), (-0.0004, 0.0), (-0.0, 0.0)],
)
def test_estimator_publication_half_up_isolated_context(value, expected):
    from decimal import ROUND_DOWN, Inexact, localcontext
    from math import copysign

    from app.stint_analytics import _publish_metric

    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        assert _publish_metric(value) == expected
        assert context.prec == 2 and context.rounding == ROUND_DOWN
    if expected == 0:
        assert copysign(1, _publish_metric(value)) == 1


def test_estimator_residual_uses_unrounded_line(monkeypatch):
    from types import SimpleNamespace

    from app import stint_analytics as analytics

    # Rounding this slope before prediction gives a large, false residual.
    rows = timed_rows(
        range(100, 106), [90_000_000_000 + x * 400_000 for x in range(100, 106)]
    )
    monkeypatch.setattr(
        analytics,
        "theilslopes",
        lambda *a, **k: SimpleNamespace(slope=0.0004, intercept=90.0),
    )
    result = analytics._estimate_stint_trend(estimator_sample(rows))
    assert result.observed_pace_trend_seconds_per_lap == 0.0
    assert result.median_absolute_residual_seconds == 0.0


@pytest.mark.parametrize("field", ["slope", "intercept"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_estimator_rejects_nonfinite_library_output(monkeypatch, field, value):
    from types import SimpleNamespace

    from app import stint_analytics as analytics

    values = {"slope": 0.0, "intercept": 90.0, field: value}
    monkeypatch.setattr(
        analytics, "theilslopes", lambda *a, **k: SimpleNamespace(**values)
    )
    with pytest.raises(ValueError, match="finite"):
        analytics._estimate_stint_trend(estimator_sample(stint_rows()))


def test_estimator_rejects_nonfinite_predictions(monkeypatch):
    from types import SimpleNamespace

    from app import stint_analytics as analytics

    monkeypatch.setattr(
        analytics,
        "theilslopes",
        lambda *a, **k: SimpleNamespace(slope=1e308, intercept=90.0),
    )
    with pytest.raises(ValueError, match="finite"):
        analytics._estimate_stint_trend(estimator_sample(stint_rows()))


@pytest.mark.parametrize(
    "reason,rows",
    [
        ("inconsistent_stint_metadata", stint_rows() + (lap(2),)),
        (
            "inconsistent_stint_metadata",
            stint_rows()[:2] + (lap(4, stint=None),) + stint_rows()[3:],
        ),
        ("inconsistent_stint_metadata", stint_rows() + (lap(9, compound="HARD"),)),
        ("wet_weather_compound", stint_rows(compound="WET")),
        ("missing_compound", stint_rows(compound=None)),
        ("unsupported_compound", stint_rows(compound="UNKNOWN")),
        ("inconsistent_tire_age", stint_rows()[:-1] + (lap(7, tyre_life=8),)),
        ("missing_tire_age", stint_rows()[:-1] + (lap(7, tyre_life=None),)),
        ("insufficient_eligible_sample", stint_rows(5)),
    ],
)
def test_estimator_boundary_rejects_every_unavailable_outcome(
    monkeypatch, reason, rows
):
    from unittest.mock import Mock

    from app import stint_analytics as analytics

    spy = Mock(side_effect=AssertionError("Unavailable stint reached estimator"))
    scipy_spy = Mock(side_effect=AssertionError("Unavailable stint reached SciPy"))
    monkeypatch.setattr(analytics, "_estimate_stint_trend", spy)
    monkeypatch.setattr(analytics, "theilslopes", scipy_spy)
    qualification = qualified(rows)
    assert qualification.unavailability_reason == reason
    with pytest.raises(ValueError, match="unavailable"):
        analytics._build_validated_estimator_sample(qualification)
    (stint,) = analyze(rows).drivers[0].stints
    assert stint.observed_pace_trend_seconds_per_lap is None
    assert stint.median_absolute_residual_seconds is None
    spy.assert_not_called()
    scipy_spy.assert_not_called()


def test_estimator_contract_rejects_broad_objects_and_sample_is_frozen():
    from app.stint_analytics import (
        _build_validated_estimator_sample,
        _estimate_stint_trend,
    )

    rows = stint_rows()
    qualification = qualified(rows)
    sample = _build_validated_estimator_sample(qualification)
    assert sample.tire_ages == tuple(range(8, 14))
    assert sample.lap_times_ns == (90_000_000_000,) * 6
    with pytest.raises(FrozenInstanceError):
        sample.tire_ages = ()
    for broad in (
        qualification,
        construct(rows).drivers[0].stints[0],
        analyze(rows).drivers[0].stints[0],
        rows,
        qualification.available_sample,
    ):
        with pytest.raises(TypeError, match="_ValidatedEstimatorSample"):
            _estimate_stint_trend(broad)
    with pytest.raises(TypeError):
        _build_validated_estimator_sample(rows)
    assert (
        _estimate_stint_trend(sample)
        == _estimate_stint_trend(sample)
        == _estimate_stint_trend(sample)
    )


@pytest.mark.parametrize("slope,residual", [(None, None), (None, 0.0), (0.0, None)])
def test_estimator_final_available_requires_both_metrics(slope, residual):
    (stint,) = analyze(stint_rows()).drivers[0].stints
    with pytest.raises(ValueError, match="metrics"):
        replace(
            stint,
            observed_pace_trend_seconds_per_lap=slope,
            median_absolute_residual_seconds=residual,
        )


@pytest.mark.parametrize("slope,residual", [(1.0, None), (None, 1.0), (0.0, 0.0)])
def test_estimator_final_unavailable_forbids_any_metric(slope, residual):
    (stint,) = analyze(stint_rows(5)).drivers[0].stints
    with pytest.raises(ValueError, match="metrics"):
        replace(
            stint,
            observed_pace_trend_seconds_per_lap=slope,
            median_absolute_residual_seconds=residual,
        )


@pytest.mark.parametrize(
    "field", ["observed_pace_trend_seconds_per_lap", "median_absolute_residual_seconds"]
)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True])
def test_estimator_final_metrics_are_finite_numbers(field, value):
    (stint,) = analyze(stint_rows()).drivers[0].stints
    with pytest.raises(ValueError):
        replace(stint, **{field: value})


def test_estimator_final_residual_cannot_be_negative():
    (stint,) = analyze(stint_rows()).drivers[0].stints
    with pytest.raises(ValueError):
        replace(stint, median_absolute_residual_seconds=-0.001)


@pytest.mark.parametrize("ages", [(8, 9, 10, 11, 12), (8, 9, 10, 11, 12, 12), (8,) * 6])
def test_estimator_sample_requires_six_observations_and_distinct_ages(ages):
    from app.stint_analytics import _build_validated_estimator_sample

    rows = timed_rows(ages, [90_000_000_000] * len(ages))
    with pytest.raises(ValueError):
        _build_validated_estimator_sample(qualified(rows))


@pytest.mark.parametrize(
    "case", ["age_overflow", "duration_overflow", "float_age_collision"]
)
def test_estimator_input_representation_guard_precedes_scipy(monkeypatch, case):
    from unittest.mock import Mock

    from app import stint_analytics as analytics

    if case == "age_overflow":
        rows = timed_rows([10**400 + i for i in range(6)], [90_000_000_000] * 6)
    elif case == "duration_overflow":
        rows = timed_rows(range(8, 14), [10**400] * 6)
    else:
        rows = timed_rows([2**54 + i for i in range(6)], [90_000_000_000] * 6)
    spy = Mock(side_effect=AssertionError("Invalid input reached SciPy"))
    monkeypatch.setattr(analytics, "theilslopes", spy)
    with pytest.raises(ValueError):
        analyze(rows)
    spy.assert_not_called()


def test_estimator_guards_nonfinite_residual_with_finite_prediction(monkeypatch):
    from types import SimpleNamespace

    from app import stint_analytics as analytics

    rows = timed_rows(range(8, 14), [10**317] * 6)
    monkeypatch.setattr(
        analytics,
        "theilslopes",
        lambda *a, **k: SimpleNamespace(slope=0.0, intercept=-1e308),
    )
    with pytest.raises(ValueError, match="finite"):
        analyze(rows)


def test_estimator_residual_publication_half_up_after_median(monkeypatch):
    from types import SimpleNamespace

    from app import stint_analytics as analytics

    # Exactly representable 0.0625 tests a residual publication midpoint.
    rows = timed_rows(range(8, 14), [90_062_500_000] * 6)
    monkeypatch.setattr(
        analytics,
        "theilslopes",
        lambda *a, **k: SimpleNamespace(slope=-0.0, intercept=90.0),
    )
    result = analytics._estimate_stint_trend(estimator_sample(rows))
    assert result.observed_pace_trend_seconds_per_lap == 0.0
    assert result.median_absolute_residual_seconds == 0.063


def canonical_analysis_json(result):
    """Test-only canonical analysis content; source position is diagnostic only."""
    import json
    from dataclasses import asdict

    def without_source_position(value):
        if isinstance(value, dict):
            return {
                key: without_source_position(item)
                for key, item in value.items()
                if key != "source_order"
            }
        if isinstance(value, (tuple, list)):
            return [without_source_position(item) for item in value]
        return value

    return json.dumps(
        without_source_position(asdict(result)), sort_keys=True, allow_nan=False
    )


@pytest.mark.parametrize("identical", [False, True])
def test_estimator_canonical_content_repeats_permutations_and_multiplicity(
    monkeypatch, identical
):
    from random import Random
    from unittest.mock import Mock

    from app import stint_analytics as analytics

    valid = timed_rows(
        (8, 10, 13, 17, 22, 28),
        [90_000_000_001 + age * 123_456_789 for age in (8, 10, 13, 17, 22, 28)],
    )
    duplicate = lap(30, stint=9, tyre_life=30)
    copies = (
        (duplicate, duplicate, replace(duplicate, source_order=99))
        if identical
        else (duplicate, replace(duplicate, stint=10), replace(duplicate, stint=None))
    )
    rows = valid + copies + (lap(31, stint=None),)
    spy = Mock(wraps=analytics._estimate_stint_trend)
    monkeypatch.setattr(analytics, "_estimate_stint_trend", spy)
    expected = analyze(rows)
    expected_json = canonical_analysis_json(expected)
    for _ in range(3):
        assert canonical_analysis_json(analyze(rows)) == expected_json
    rng = Random(3)
    for _ in range(20):
        shuffled = list(rows)
        rng.shuffle(shuffled)
        permuted = tuple(
            replace(row, source_order=rng.randrange(-1000, 1000)) for row in shuffled
        )
        actual = analyze(permuted)
        assert actual == expected
        assert canonical_analysis_json(actual) == expected_json
        assert_reconciled(actual.drivers[0], permuted)
        repeated = [d for d in actual.drivers[0].laps if d.lap.lap_number == 30]
        assert len(repeated) == 3
        if identical:
            assert repeated[0] == repeated[1] == repeated[2]
    assert spy.call_count == 24  # one qualified stint per complete analysis
    assert all(
        type(call.args[0]) is analytics._ValidatedEstimatorSample
        for call in spy.call_args_list
    )


def qualification_facts(qualification):
    from dataclasses import fields

    return {f.name: getattr(qualification, f.name) for f in fields(qualification)}


@pytest.mark.parametrize(
    "case",
    [
        "total",
        "eligible",
        "exclusion_reasons",
        "distinct_ages",
        "conflicting_compound",
        "duplicate_lap",
        "wrong_driver",
        "unknown_reason",
    ],
)
def test_fabricated_qualification_rejected_before_estimator_input(monkeypatch, case):
    from unittest.mock import Mock

    from app import stint_analytics as analytics

    original = qualified(stint_rows() + (lap(20, pit_in=True),))
    facts = qualification_facts(original)
    if case == "total":
        facts["sample"] = replace(
            original.sample, total_lap_count=8, eligible_observation_count=7
        )
    elif case == "eligible":
        # Still internally reconciled StintSample, but not these evidence rows.
        facts["sample"] = sample_counts(
            total_lap_count=7,
            eligible_observation_count=7,
            distinct_eligible_tire_age_count=6,
        )
    elif case == "exclusion_reasons":
        facts["sample"] = replace(
            original.sample,
            exclusions=tuple(
                (reason, int(reason == "pit_out"))
                for reason, _ in original.sample.exclusions
            ),
        )
    elif case == "distinct_ages":
        facts["sample"] = replace(original.sample, distinct_eligible_tire_age_count=5)
    elif case == "unknown_reason":
        facts["unavailability_reason"] = "made_up"
    else:
        first = original.laps[0]
        change = {
            "conflicting_compound": {"compound": "HARD"},
            "duplicate_lap": {"lap_number": 3},
            "wrong_driver": {"driver_number": "99"},
        }[case]
        facts["laps"] = (
            replace(first, lap=replace(first.lap, **change)),
        ) + original.laps[1:]
    scipy_spy = Mock(side_effect=AssertionError("Fabricated state reached SciPy"))
    monkeypatch.setattr(analytics, "theilslopes", scipy_spy)
    with pytest.raises(ValueError):
        fabricated = analytics.StintQualification(**facts)
        analytics._estimate_stint_trend(
            analytics._build_validated_estimator_sample(fabricated)
        )
    scipy_spy.assert_not_called()


def test_fabricated_available_sample_cannot_substitute_audit_rows(monkeypatch):
    from unittest.mock import Mock

    from app import stint_analytics as analytics

    class WrongSample(analytics.StintQualification):
        @property
        def available_sample(self):
            return self.laps  # Includes the excluded pit-in row.

    original = qualified(stint_rows() + (lap(20, pit_in=True),))
    spy = Mock(side_effect=AssertionError("Fabricated sample reached SciPy"))
    monkeypatch.setattr(analytics, "theilslopes", spy)
    with pytest.raises(ValueError, match="available_sample"):
        fabricated = WrongSample(**qualification_facts(original))
        analytics._build_validated_estimator_sample(fabricated)
    spy.assert_not_called()


@pytest.mark.parametrize("continuity_hidden", [False, True])
def test_locally_valid_direct_qualification_has_no_canonical_provenance(
    monkeypatch, continuity_hidden
):
    from unittest.mock import Mock

    from app import stint_analytics as analytics

    rows = stint_rows(7)
    if continuity_hidden:
        rows = rows[:3] + (replace(rows[3], stint=None),) + rows[4:]
    original = qualified(rows)
    facts = qualification_facts(original)
    facts["unavailability_reason"] = None
    # With the interrupting row absent, the stint's own evidence looks valid.
    fabricated = analytics.StintQualification(**facts)
    assert len(fabricated.available_sample) >= 6
    spy = Mock(side_effect=AssertionError("Unissued qualification reached SciPy"))
    monkeypatch.setattr(analytics, "theilslopes", spy)
    with pytest.raises(TypeError, match="canonical qualification provenance"):
        analytics._estimate_stint_trend(
            analytics._build_validated_estimator_sample(fabricated)
        )
    spy.assert_not_called()


def test_estimator_issuance_cannot_be_bypassed_by_ordinary_constructors(monkeypatch):
    from unittest.mock import Mock

    from app import stint_analytics as analytics

    canonical = qualified(stint_rows())
    spy = Mock(side_effect=AssertionError("Unissued sample reached SciPy"))
    monkeypatch.setattr(analytics, "theilslopes", spy)
    with pytest.raises(TypeError, match="pipeline"):
        analytics._CanonicalStintQualification(**qualification_facts(canonical))
    with pytest.raises(TypeError, match="canonical analysis"):
        analytics._ValidatedEstimatorSample(canonical)
    # dataclasses.replace must not copy issuance authority into edited facts.
    with pytest.raises(TypeError, match="pipeline"):
        replace(canonical, reported_stint=99)
    assert not hasattr(analytics, "ValidatedEstimatorSample")
    assert not hasattr(analytics, "estimate_stint_trend")
    spy.assert_not_called()


@pytest.mark.parametrize("compound", ["INTERMEDIATE", "WET"])
def test_wet_qualification_retains_trusted_compound_and_audit_only(compound):
    from app import stint_analytics as analytics

    canonical = qualified(stint_rows(compound=compound))
    audit = analytics.StintQualification(**qualification_facts(canonical))
    assert audit.normalized_compound == compound
    assert audit.available_sample == ()
    assert len(audit.laps) == 6
    with pytest.raises(ValueError, match="unavailable"):
        analytics._build_validated_estimator_sample(canonical)
