"""Driver and session projections, using controlled source snapshots."""

from dataclasses import replace
from unittest.mock import Mock

import pandas as pd
import pytest

from app import f1_data, stint_analytics

SOURCE = (2025, "Italian Grand Prix", "Race")


@pytest.fixture(name="stint_session")
def make_stint_session(pace_session_factory):
    rows = []
    for number in range(1, 10):
        rows.append(
            dict(
                DriverNumber="1",
                LapNumber=number,
                LapTime=pd.Timedelta(90_000_500_000 + number * 123_000_000, unit="ns"),
                PitInTime=pd.NaT,
                PitOutTime=pd.NaT,
                TrackStatus="1",
                IsAccurate=None,
                Compound="medium" if number < 8 else "WET",
                Stint=9 if number < 8 else 3,
                TyreLife=number + 5,
                FastF1Generated=None,
            )
        )
    rows.append(dict(rows[-1], LapNumber=10, Stint=None, TyreLife=None))
    rows.append(dict(rows[-1]))  # Identical unassigned rows must both survive.
    rows.append(dict(rows[0], DriverNumber="4", LapNumber=2, Stint=1))
    laps = pd.DataFrame(rows)
    for column in ("PitInTime", "PitOutTime"):
        laps[column] = pd.Series(pd.NaT, index=laps.index, dtype="timedelta64[ns]")
    return pace_session_factory(laps=laps)


@pytest.mark.parametrize("number", ["1", "4", "27", "999"])
def test_driver_uses_one_complete_snapshot(monkeypatch, stint_session, number):
    from app import stint_service
    from app.pace_service import DriverNotFoundError

    loaded = Mock(return_value=stint_session)
    mapped = Mock(wraps=f1_data.map_lap_inputs)
    summary = Mock(wraps=f1_data.map_session_summary)
    analyzed = Mock(wraps=stint_analytics.analyze_session_stints)
    monkeypatch.setattr(f1_data, "load_session", loaded)
    monkeypatch.setattr(f1_data, "map_lap_inputs", mapped)
    monkeypatch.setattr(f1_data, "map_session_summary", summary)
    monkeypatch.setattr(stint_analytics, "analyze_session_stints", analyzed)
    if number == "999":
        with pytest.raises(DriverNotFoundError):
            stint_service.load_driver_tire_stints(*SOURCE, number)
    else:
        response = stint_service.load_driver_tire_stints(*SOURCE, number)
        assert response.driver.driver.driver_number == number
        assert response.context.year == 2025
        assert response.context.event.name == "Italian Grand Prix"
        assert response.source.provider == "FastF1"
        if number == "27":
            assert not response.driver.stints and not response.laps
            assert response.driver.unassigned_lap_count == 0
        elif number == "1":
            assert [s.reported_stint for s in response.driver.stints] == [9, 3]
            assert [s.status for s in response.driver.stints] == [
                "available",
                "unavailable",
            ]
            assert (
                response.driver.stints[0].observed_pace_trend_seconds_per_lap == 0.123
            )
            assert response.driver.stints[0].median_absolute_residual_seconds == 0.0
            assert (
                response.driver.stints[1].unavailability_reason
                == "wet_weather_compound"
            )
            assert len(response.laps) == 11
            assert response.laps[-1] == response.laps[-2]
            assert response.driver.unassigned_lap_count == 2
    loaded.assert_called_once_with(*SOURCE)
    mapped.assert_called_once_with(stint_session)
    summary.assert_called_once_with(stint_session)
    analyzed.assert_called_once()
    assert {d.driver_number for d in analyzed.call_args.args[0].participants} == {
        "1",
        "4",
        "27",
    }


def test_projection_preserves_analytics_without_recalculation(
    monkeypatch, stint_session
):
    from app import stint_service

    inputs = f1_data.map_lap_inputs(stint_session)
    field = stint_analytics.analyze_session_stints(inputs)
    driver = field.drivers[0]
    # Deliberately different valid published metrics prove projection, not fitting.
    changed = replace(
        driver.stints[0],
        observed_pace_trend_seconds_per_lap=-0.789,
        median_absolute_residual_seconds=1.234,
    )
    field = replace(
        field,
        drivers=(
            replace(driver, stints=(changed, *driver.stints[1:])),
            *field.drivers[1:],
        ),
    )
    monkeypatch.setattr(f1_data, "load_session", Mock(return_value=stint_session))
    analyzer = Mock(return_value=field)
    monkeypatch.setattr(stint_analytics, "analyze_session_stints", analyzer)
    result = stint_service.load_driver_tire_stints(*SOURCE, "1")
    assert result.driver.stints[0].observed_pace_trend_seconds_per_lap == -0.789
    assert result.driver.stints[0].median_absolute_residual_seconds == 1.234
    for actual, expected in zip(result.driver.stints, driver.stints, strict=True):
        assert actual.reported_compound == expected.reported_compound
        assert actual.normalized_compound == expected.normalized_compound
        assert actual.sample.total_lap_count == expected.sample.total_lap_count
        assert actual.sample.exclusions.model_dump() == dict(expected.sample.exclusions)
    for actual, expected in zip(result.laps, driver.laps, strict=True):
        assert actual.reported_tire_age == expected.lap.tyre_life
        assert actual.reported_compound == expected.lap.compound
        assert actual.disposition == expected.disposition
        assert actual.primary_exclusion_reason == expected.primary_exclusion_reason
        assert actual.disruptive_statuses == expected.disruptive_statuses
    analyzer.assert_called_once_with(inputs)


def test_canonical_repeats_and_duplicate_multiplicity(monkeypatch, stint_session):
    from app.stint_service import load_driver_tire_stints

    # Add two identical assigned rows: retain them and the blocked stint.
    stint_session.laps = stint_session.laps.iloc[
        [*range(len(stint_session.laps)), 2, 2]
    ].reset_index(drop=True)
    loader = Mock(return_value=stint_session)
    monkeypatch.setattr(f1_data, "load_session", loader)
    first = load_driver_tire_stints(*SOURCE, "1").model_dump(mode="json")
    for seed in range(3):
        stint_session.laps = stint_session.laps.sample(
            frac=1, random_state=seed
        ).reset_index(drop=True)
        assert load_driver_tire_stints(*SOURCE, "1").model_dump(mode="json") == first
    assert loader.call_count == 4
    assert (
        first["driver"]["stints"][0]["unavailability_reason"]
        == "inconsistent_stint_metadata"
    )
    assert len([lap for lap in first["laps"] if lap["lap_number"] == 3]) == 3
    assert "source_order" not in str(first)


@pytest.mark.parametrize(
    "stage",
    ["load_session", "map_lap_inputs", "map_session_summary", "analyze_session_stints"],
)
@pytest.mark.parametrize("error", [f1_data.DataSourceUnavailableError, RuntimeError])
def test_service_propagates_failures(monkeypatch, stint_session, stage, error):
    from app.stint_service import load_driver_tire_stints

    monkeypatch.setattr(f1_data, "load_session", Mock(return_value=stint_session))
    failure = error("private failure")
    owner = stint_analytics if stage == "analyze_session_stints" else f1_data
    monkeypatch.setattr(owner, stage, Mock(side_effect=failure))
    with pytest.raises(error) as caught:
        load_driver_tire_stints(*SOURCE, "1")
    assert caught.value is failure


@pytest.fixture(name="stint_field_session")
def make_stint_field_session(stint_session):
    # Numeric order differs from both source roster order and lexical order.
    stint_session.results = pd.DataFrame(
        [
            {"DriverNumber": number, "Position": i}
            for i, number in enumerate(("27", "10", "4", "1"), 1)
        ]
    )
    rows = stint_session.laps
    expanded = rows.iloc[[*range(len(rows)), 0, 0, -1, -1]].reset_index(drop=True)
    expanded = expanded.astype({"LapNumber": float, "Stint": float})
    expanded.loc[len(rows) :, "DriverNumber"] = ["10", "4", "4", "4"]
    expanded.loc[len(rows) :, "LapNumber"] = [2, float("nan"), float("nan"), 3]
    expanded.loc[len(rows) :, "Stint"] = [float("nan"), 3, 2, 1]
    expanded.loc[len(expanded) - 1, "Compound"] = "HARD"
    stint_session.laps = expanded
    return stint_session


def test_session_uses_one_complete_snapshot(monkeypatch, stint_field_session):
    from app import stint_service

    inputs = f1_data.map_lap_inputs(stint_field_session)
    summary = f1_data.map_session_summary(stint_field_session)
    loaded = Mock(return_value=stint_field_session)
    mapped = Mock(return_value=inputs)
    summarized = Mock(return_value=summary)
    analyzed = Mock(wraps=stint_analytics.analyze_session_stints)
    monkeypatch.setattr(f1_data, "load_session", loaded)
    monkeypatch.setattr(f1_data, "map_lap_inputs", mapped)
    monkeypatch.setattr(f1_data, "map_session_summary", summarized)
    monkeypatch.setattr(stint_analytics, "analyze_session_stints", analyzed)
    detail = Mock(side_effect=AssertionError("Session must not call driver service"))
    evidence = Mock(side_effect=AssertionError("Session must not project lap evidence"))
    monkeypatch.setattr(stint_service, "load_driver_tire_stints", detail)
    monkeypatch.setattr(stint_service, "_lap_response", evidence)

    result = stint_service.load_session_tire_stints(*SOURCE)
    loaded.assert_called_once_with(*SOURCE)
    mapped.assert_called_once_with(stint_field_session)
    summarized.assert_called_once_with(stint_field_session)
    analyzed.assert_called_once_with(inputs)
    detail.assert_not_called()
    evidence.assert_not_called()
    assert result.context.year == summary.year
    assert result.context.event == summary.event
    assert result.source == summary.source
    assert [d.driver.driver_number for d in result.drivers] == ["1", "4", "10", "27"]
    first, unavailable, unassigned, empty = result.drivers
    assert [s.reported_stint for s in first.stints] == [9, 3]
    assert [s.status for s in first.stints] == ["available", "unavailable"]
    assert first.unassigned_lap_count == 2
    assert [s.reported_stint for s in unavailable.stints] == [1, 2, 3]
    assert all(s.status == "unavailable" for s in unavailable.stints)
    assert unavailable.stints[0].reported_compound == "medium"
    assert unavailable.stints[0].normalized_compound is None
    assert unavailable.stints[0].unavailability_reason == "inconsistent_stint_metadata"
    assert unassigned.stints == () and unassigned.unassigned_lap_count == 1
    assert empty.stints == () and empty.unassigned_lap_count == 0
    assert set(result.model_dump()) == {
        "context",
        "policy",
        "limitations",
        "drivers",
        "source",
    }
    assert all(
        set(d.model_dump()) == {"driver", "stints", "unassigned_lap_count"}
        for d in result.drivers
    )


def test_session_projects_the_same_summaries_without_recalculation(
    monkeypatch, stint_field_session
):
    from app import stint_service

    field = stint_analytics.analyze_session_stints(
        f1_data.map_lap_inputs(stint_field_session)
    )
    first = field.drivers[0]
    changed = replace(
        first.stints[0],
        observed_pace_trend_seconds_per_lap=-0.789,
        median_absolute_residual_seconds=1.234,
    )
    field = replace(
        field,
        drivers=(
            replace(first, stints=(changed, *first.stints[1:])),
            *field.drivers[1:],
        ),
    )
    monkeypatch.setattr(f1_data, "load_session", Mock(return_value=stint_field_session))
    analyzer = Mock(return_value=field)
    monkeypatch.setattr(stint_analytics, "analyze_session_stints", analyzer)
    result = stint_service.load_session_tire_stints(*SOURCE)
    analyzer.assert_called_once()
    assert result.drivers[0].stints[0].observed_pace_trend_seconds_per_lap == -0.789
    assert result.drivers[0].stints[0].median_absolute_residual_seconds == 1.234
    for driver in result.drivers:
        detail = stint_service.load_driver_tire_stints(
            *SOURCE, driver.driver.driver_number
        )
        assert driver == detail.driver
        assert result.context == detail.context
        assert result.policy == detail.policy
        assert result.limitations == detail.limitations
        assert result.source == detail.source


def test_session_determinism_preserves_duplicates_and_ignores_source_order(
    monkeypatch, stint_field_session
):
    from app.stint_service import load_session_tire_stints

    source = stint_field_session
    source.laps = source.laps.iloc[[*range(len(source.laps)), 2, 2]].reset_index(
        drop=True
    )
    monkeypatch.setattr(f1_data, "load_session", Mock(return_value=source))
    first = load_session_tire_stints(*SOURCE)
    for seed in range(3):
        source.laps = source.laps.sample(frac=1, random_state=seed).reset_index(
            drop=True
        )
        source.results = source.results.sample(frac=1, random_state=seed).reset_index(
            drop=True
        )
        assert (
            load_session_tire_stints(*SOURCE).model_dump_json()
            == first.model_dump_json()
        )
    normalized = f1_data.map_lap_inputs(source)
    changed = replace(
        normalized,
        laps=tuple(
            replace(lap, source_order=1000 - i) for i, lap in enumerate(normalized.laps)
        ),
    )
    monkeypatch.setattr(f1_data, "map_lap_inputs", Mock(return_value=changed))
    assert load_session_tire_stints(*SOURCE) == first
    stint = first.drivers[0].stints[0]
    assert stint.sample.total_lap_count == 9
    assert stint.sample.eligible_observation_count == 8
    assert stint.sample.excluded_observation_count == 1
    assert stint.sample.distinct_eligible_tire_age_count == 6
    assert stint.unavailability_reason == "inconsistent_stint_metadata"
    assert first.drivers[0].unassigned_lap_count == 2
    assert "source_order" not in first.model_dump_json()


@pytest.mark.parametrize(
    "stage",
    ["load_session", "map_lap_inputs", "map_session_summary", "analyze_session_stints"],
)
@pytest.mark.parametrize("error", [f1_data.DataSourceUnavailableError, RuntimeError])
def test_session_service_propagates_failures(monkeypatch, stint_session, stage, error):
    from app.stint_service import load_session_tire_stints

    monkeypatch.setattr(f1_data, "load_session", Mock(return_value=stint_session))
    failure = error("private failure")
    owner = stint_analytics if stage == "analyze_session_stints" else f1_data
    monkeypatch.setattr(owner, stage, Mock(side_effect=failure))
    with pytest.raises(error) as caught:
        load_session_tire_stints(*SOURCE)
    assert caught.value is failure
