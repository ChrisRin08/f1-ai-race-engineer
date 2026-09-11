from unittest.mock import Mock

import pytest

from app import f1_data, lap_analytics

SOURCE = (2025, "Italian Grand Prix", "Race")


@pytest.mark.parametrize("no_eligible", [False, True])
def test_session_projection_retains_complete_ordered_field(
    monkeypatch, pace_session_factory, no_eligible
):
    import pandas as pd

    from app.pace_service import load_session_pace

    session = pace_session_factory()
    session.laps.loc[session.laps.DriverNumber == "1", "DriverNumber"] = "10"
    session.laps.loc[session.laps.DriverNumber == "10", "LapTime"] = pd.Timedelta(
        90_000_499_999, unit="ns"
    )
    for _, row in session.laps[session.laps.DriverNumber == "4"].copy().iterrows():
        row["DriverNumber"] = "1"
        row["LapTime"] = pd.Timedelta(90, unit="s")
        session.laps.loc[len(session.laps)] = row
    session.results = pd.DataFrame({"DriverNumber": ["27", "10", "4", "1", "2"]})
    if no_eligible:
        session.laps["TrackStatus"] = "2"
    loader = Mock(return_value=session)
    analyzer = Mock(wraps=lap_analytics.analyze_session_field)
    normalizer = Mock(wraps=f1_data.map_lap_inputs)
    mapper = Mock(wraps=f1_data.map_session_summary)
    monkeypatch.setattr(f1_data, "load_session", loader)
    monkeypatch.setattr(f1_data, "map_lap_inputs", normalizer)
    monkeypatch.setattr(f1_data, "map_session_summary", mapper)
    monkeypatch.setattr(lap_analytics, "analyze_session_field", analyzer)
    first = load_session_pace(*SOURCE)
    assert [d.driver.driver_number for d in first.drivers] == (
        ["1", "2", "4", "10", "27"] if no_eligible else ["1", "10", "4", "2", "27"]
    )
    assert [d.rank for d in first.drivers] == (
        [None] * 5 if no_eligible else [1, 1, 3, None, None]
    )
    assert [d.delta_to_best_ms for d in first.drivers] == (
        [None] * 5 if no_eligible else [0, 0, 1000, None, None]
    )
    assert [d.tied for d in first.drivers] == (
        [None] * 5 if no_eligible else [True, True, False, None, None]
    )
    for driver in first.drivers:
        assert driver.source == first.source
        assert driver.sample.source_lap_count == (
            driver.sample.representative_lap_count + driver.sample.excluded_lap_count
        )
        if driver.status == "insufficient_data":
            assert driver.metrics is driver.rank is driver.delta_to_best_ms is None
    assert first.context.year == 2025
    assert first.context.event.name == "Italian Grand Prix"
    assert first.context.circuit.name == "Monza"
    assert first.source.provider == "FastF1"
    loader.assert_called_once_with(*SOURCE)
    analyzer.assert_called_once()
    normalizer.assert_called_once_with(session)
    mapper.assert_called_once_with(session)
    assert load_session_pace(*SOURCE) == first
    assert loader.call_count == analyzer.call_count == 2


@pytest.mark.parametrize(
    "a,b,delta,outcome,winner",
    [
        ("1", "4", -1000, "driver_a_faster", "1"),
        ("4", "1", 1000, "driver_b_faster", "1"),
        ("1", "1", 0, "tied", None),
        ("1", "27", None, None, None),
        ("27", "1", None, None, None),
        ("27", "27", None, None, None),
        ("999", "1", None, None, None),
        ("1", "999", None, None, None),
    ],
)
def test_comparison_projects_one_shared_analysis(
    monkeypatch, pace_session_factory, a, b, delta, outcome, winner
):
    from app import pace_service

    session = pace_session_factory()
    loader = Mock(return_value=session)
    mapper = Mock(wraps=f1_data.map_session_summary)
    normalizer = Mock(wraps=f1_data.map_lap_inputs)
    analyzer = Mock(wraps=lap_analytics.analyze_session_field)
    monkeypatch.setattr(f1_data, "load_session", loader)
    monkeypatch.setattr(f1_data, "map_session_summary", mapper)
    monkeypatch.setattr(f1_data, "map_lap_inputs", normalizer)
    monkeypatch.setattr(lap_analytics, "analyze_session_field", analyzer)
    if "999" in (a, b):
        with pytest.raises(pace_service.DriverNotFoundError):
            pace_service.load_pace_comparison(*SOURCE, a, b)
    else:
        result = pace_service.load_pace_comparison(*SOURCE, a, b)
        assert result.driver_a.driver.driver_number == a
        assert result.driver_b.driver.driver_number == b
        assert result.comparison.delta_ms == delta
        assert result.comparison.outcome == outcome
        assert result.comparison.faster_driver_number == winner
        assert result.comparison.status == (
            "available" if delta is not None else "insufficient_data"
        )
        if delta is not None:
            assert delta == (
                result.driver_a.metrics.median_lap_time_ms
                - result.driver_b.metrics.median_lap_time_ms
            )
        assert result.source.provider == "FastF1"
    loader.assert_called_once_with(*SOURCE)
    mapper.assert_called_once_with(session)
    normalizer.assert_called_once_with(session)
    analyzer.assert_called_once()


def test_comparison_uses_published_medians_and_repeats(
    monkeypatch, pace_session_factory
):
    import pandas as pd

    from app.pace_service import load_pace_comparison

    session = pace_session_factory()
    # These differ internally but tie publicly; subtracting before publication
    # would incorrectly round their difference to a nonzero millisecond.
    for number, ns in (("1", 90_000_500_001), ("4", 90_001_499_999)):
        session.laps.loc[session.laps.DriverNumber == number, "LapTime"] = pd.Timedelta(
            ns, unit="ns"
        )
    loader = Mock(return_value=session)
    monkeypatch.setattr(f1_data, "load_session", loader)
    first = load_pace_comparison(*SOURCE, "1", "4")
    second = load_pace_comparison(*SOURCE, "1", "4")
    assert first == second
    assert first.driver_a.metrics.median_lap_time_ms == 90_001
    assert first.driver_b.metrics.median_lap_time_ms == 90_001
    assert first.comparison.delta_ms == 0
    assert first.comparison.outcome == "tied"
    assert first.comparison.faster_driver_number is None
    assert loader.call_count == 2


@pytest.mark.parametrize("number", ["1", "4", "27", "999"])
def test_driver_operation_uses_one_snapshot_and_field_analysis(
    monkeypatch, pace_session_factory, number
):
    from app import pace_service

    session = pace_session_factory()
    loader = Mock(return_value=session)
    mapper = Mock(wraps=f1_data.map_session_summary)
    normalizer = Mock(wraps=f1_data.map_lap_inputs)
    analyzer = Mock(wraps=lap_analytics.analyze_session_field)
    monkeypatch.setattr(f1_data, "load_session", loader)
    monkeypatch.setattr(f1_data, "map_session_summary", mapper)
    monkeypatch.setattr(f1_data, "map_lap_inputs", normalizer)
    monkeypatch.setattr(lap_analytics, "analyze_session_field", analyzer)

    if number == "999":
        with pytest.raises(pace_service.DriverNotFoundError):
            pace_service.load_driver_pace(*SOURCE, number)
    else:
        response = pace_service.load_driver_pace(*SOURCE, number)
        assert response.driver.driver.driver_number == number
        assert response.source.provider == "FastF1"
        assert response.context.event.name == "Italian Grand Prix"
        assert response.context.circuit.name == "Monza"
        assert response.context.year == 2025
        assert len(response.laps) == response.driver.sample.source_lap_count
        if number == "27":
            assert response.driver.status == "insufficient_data"
            assert response.driver.metrics is None
            assert response.driver.rank is None
            assert response.driver.delta_to_best_ms is None
        elif number == "4":
            assert response.driver.metrics.median_lap_time_ms == 91_000
            assert response.driver.delta_to_best_ms == 1000
            assert response.driver.rank == 2

    loader.assert_called_once_with(*SOURCE)
    mapper.assert_called_once_with(session)
    normalizer.assert_called_once_with(session)
    analyzer.assert_called_once()
    assert {d.driver_number for d in analyzer.call_args.args[0].participants} == {
        "1",
        "4",
        "27",
    }


def test_driver_operations_do_not_cache_across_requests(
    monkeypatch, pace_session_factory
):
    from app.pace_service import load_driver_pace

    loader = Mock(return_value=pace_session_factory())
    monkeypatch.setattr(f1_data, "load_session", loader)
    first = load_driver_pace(*SOURCE, "4").model_dump(mode="json")
    second = load_driver_pace(*SOURCE, "4").model_dump(mode="json")
    assert first == second
    assert loader.call_count == 2


@pytest.mark.parametrize(
    "failure", [f1_data.DataSourceUnavailableError("source"), RuntimeError("bug")]
)
def test_service_preserves_expected_and_unexpected_failures(monkeypatch, failure):
    from app.pace_service import load_driver_pace

    monkeypatch.setattr(f1_data, "load_session", Mock(side_effect=failure))
    with pytest.raises(type(failure), match=str(failure)):
        load_driver_pace(*SOURCE, "1")
