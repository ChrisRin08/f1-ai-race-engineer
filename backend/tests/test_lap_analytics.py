from dataclasses import replace

import pytest

from app.lap_analytics import SourceLap


def lap(order=1, **changes):
    return replace(SourceLap(order, "1", order + 1, 90_000_000_000), **changes)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"lap_time_ns": None, "lap_number": 1, "pit_in": True}, "invalid_timing"),
        ({"lap_number": None, "pit_out": True}, "invalid_timing"),
        ({"lap_number": 1, "pit_in": True}, "lap_one_start"),
        ({"pit_in": True, "pit_out": True, "track_status_codes": ("2",)}, "pit_in"),
        ({"pit_out": True, "track_status_codes": ("2",)}, "pit_out"),
        *[
            ({"track_status_codes": tuple(code)}, "disrupted_status")
            for code in ("2", "4", "5", "6", "7", "12", "26", "724257")
        ],
        ({"track_status_codes": ("3", "9")}, None),
        ({"track_status_codes": None}, None),
        ({"is_accurate": False}, None),
        ({"is_accurate": None}, None),
        *[
            ({"compound": compound}, None)
            for compound in ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET", None)
        ],
    ],
)
def test_classification_precedence(changes, reason):
    from app.lap_analytics import classify_driver_laps

    decision = classify_driver_laps((lap(**changes),))[0]
    assert decision.primary_exclusion_reason == reason


def test_anomaly_reference_excludes_structural_and_status_laps():
    from app.lap_analytics import classify_driver_laps

    inputs = (
        lap(1, lap_time_ns=10_000_000_000, pit_in=True),
        lap(2, lap_time_ns=20_000_000_000, track_status_codes=("2",)),
        lap(3),
        lap(4, lap_time_ns=108_000_000_000),
        lap(5, lap_time_ns=108_000_000_001, compound="WET"),
    )
    decisions = classify_driver_laps(inputs)
    assert [d.primary_exclusion_reason for d in decisions] == [
        "pit_in",
        "disrupted_status",
        None,
        None,
        "anomalous_pace",
    ]


def test_classification_order_and_diagnostics_are_deterministic():
    from app.lap_analytics import classify_driver_laps

    inputs = (
        lap(3, lap_number=None),
        lap(2, lap_number=2),
        lap(1, lap_number=2, track_status_codes=("7", "2", "4")),
    )
    expected = classify_driver_laps(inputs)
    assert [d.lap.source_order for d in expected] == [1, 2, 3]
    assert expected[0].disruptive_statuses == (
        "yellow",
        "safety_car",
        "virtual_safety_car_ending",
    )
    assert expected[0].lap.track_status_codes == ("7", "2", "4")
    assert classify_driver_laps(tuple(reversed(inputs))) == expected


@pytest.mark.parametrize("ns", [0, -1, 1, 499_999, 500_000, 500_001])
def test_timing_boundary_through_normalized_inputs(ns):
    from app.lap_analytics import classify_driver_laps

    normalized = ns if ns >= 500_000 else None
    decision = classify_driver_laps((lap(lap_time_ns=normalized),))[0]
    assert decision.primary_exclusion_reason == (
        "invalid_timing" if normalized is None else None
    )


@pytest.mark.parametrize(
    "ns,expected",
    [(500_000, 1), (500_001, 1), (90_000_499_999, 90_000), (90_000_500_000, 90_001)],
)
def test_half_up_publication(ns, expected):
    from app.lap_analytics import publish_milliseconds

    assert publish_milliseconds(ns) == expected


def test_metrics_use_unrounded_values_and_population_deviation():
    from app.lap_analytics import calculate_metrics

    # A population standard deviation of sqrt(2) seconds, not sample sqrt(2.5).
    metrics = calculate_metrics(tuple(x * 1_000_000_000 for x in (90, 91, 92, 93, 94)))
    assert (
        metrics.median_lap_time_ms,
        metrics.mean_lap_time_ms,
        metrics.fastest_lap_time_ms,
        metrics.population_standard_deviation_ms,
    ) == (92_000, 92_000, 90_000, 1414)
    # Pre-rounding these six values changes the rounded median from 1 to 2.
    precise = calculate_metrics((1_499_999,) * 3 + (1_500_000,) * 3)
    assert precise.median_lap_time_ms == precise.mean_lap_time_ms == 1


def test_minimum_duration_metrics_and_local_decimal_context():
    from decimal import ROUND_DOWN, Inexact, getcontext, localcontext

    from app.lap_analytics import calculate_metrics

    with localcontext() as context:
        context.prec = 3
        context.rounding = ROUND_DOWN
        context.traps[Inexact] = True
        expected = calculate_metrics((500_000,) * 5)
        assert expected.median_lap_time_ms == expected.mean_lap_time_ms == 1
        assert expected.fastest_lap_time_ms == 1
        assert expected.population_standard_deviation_ms == 0
        assert getcontext().prec == 3
        metrics = calculate_metrics(
            (
                90_000_000_001,
                90_000_000_003,
                90_001_000_001,
                90_001_000_003,
                90_002_000_001,
            )
        )
    assert (
        calculate_metrics(
            (
                90_000_000_001,
                90_000_000_003,
                90_001_000_001,
                90_001_000_003,
                90_002_000_001,
            )
        )
        == metrics
    )


def test_population_standard_deviation_half_up_boundary():
    from app.lap_analytics import calculate_metrics

    metrics = calculate_metrics((90_000_000_000,) * 3 + (90_001_000_000,) * 3)
    assert metrics.population_standard_deviation_ms == 1
    assert metrics.mean_lap_time_ms == metrics.median_lap_time_ms == 90_001


@pytest.mark.parametrize("bad", [0, -1, 499_999, float("nan"), float("inf"), True])
def test_normalized_input_rejects_non_normalized_duration(bad):
    with pytest.raises(ValueError):
        lap(lap_time_ns=bad)


def field_input():
    from app.lap_analytics import DriverIdentity, SessionFieldInput

    drivers = tuple(DriverIdentity(number) for number in ("27", "10", "4", "2", "99"))
    laps = tuple(
        lap(i, driver_number=number, lap_time_ns=ns)
        for number, ns in (
            ("10", 90_000_000_001),
            ("2", 90_000_499_999),
            ("4", 91_000_000_000),
        )
        for i in range(1, 6)
    )
    return SessionFieldInput(drivers, laps + (lap(6, driver_number="99", pit_in=True),))


def test_field_ranking_published_ties_and_insufficiency():
    from app.lap_analytics import analyze_session_field

    field = analyze_session_field(field_input())
    assert [d.driver.driver_number for d in field.drivers] == [
        "2",
        "10",
        "4",
        "27",
        "99",
    ]
    assert [d.rank for d in field.drivers] == [1, 1, 3, None, None]
    assert [d.tied for d in field.drivers] == [True, True, False, None, None]
    assert [d.delta_to_best_ms for d in field.drivers] == [0, 0, 1000, None, None]
    assert field.drivers[-2].sample.source_lap_count == 0
    assert field.drivers[-1].metrics is None
    assert field.drivers[-1].sample.excluded_lap_count == 1
    for driver in field.drivers:
        sample = driver.sample
        assert (
            sample.source_lap_count
            == sample.representative_lap_count + sample.excluded_lap_count
        )
        assert sum(count for _, count in sample.exclusions) == sample.excluded_lap_count
        assert len(driver.laps) == sample.source_lap_count


def test_field_repeat_and_permuted_input_order():
    from app.lap_analytics import analyze_session_field

    original = field_input()
    expected = analyze_session_field(original)
    assert analyze_session_field(original) == expected
    assert (
        analyze_session_field(
            replace(
                original,
                participants=original.participants[::-1],
                laps=original.laps[::-1],
            )
        )
        == expected
    )


@pytest.mark.parametrize("count", [0, 1, 4, 5, 6])
def test_field_minimum_sample(count):
    from app.lap_analytics import (
        DriverIdentity,
        SessionFieldInput,
        analyze_session_field,
    )

    result = analyze_session_field(
        SessionFieldInput(
            (DriverIdentity("1"),),
            tuple(lap(i, lap_time_ns=500_000) for i in range(1, count + 1)),
        )
    ).drivers[0]
    assert (result.metrics is not None) == (count >= 5)
    assert result.sample.representative_lap_count == count
    assert result.rank == (1 if count >= 5 else None)
    assert result.delta_to_best_ms == (0 if count >= 5 else None)


def test_pure_module_has_no_provider_or_framework_imports():
    import ast
    import inspect

    import app.lap_analytics as analytics

    tree = ast.parse(inspect.getsource(analytics))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module.split(".")[0])
    assert not set(imports) & {
        "fastapi",
        "fastf1",
        "pandas",
        "numpy",
        "app",
        "requests",
        "httpx",
        "socket",
        "urllib",
    }
