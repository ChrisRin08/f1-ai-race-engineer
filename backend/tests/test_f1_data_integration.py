import json
import os

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("F1_RUN_INTEGRATION") != "1",
    reason="Set F1_RUN_INTEGRATION=1 to run the real FastF1 integration test.",
)
def test_real_monza_race_pace_through_application_service() -> None:
    from app.pace_service import (
        load_driver_pace,
        load_pace_comparison,
        load_session_pace,
    )

    source = (2025, "Italian Grand Prix", "Race")
    field = load_session_pace(*source)
    assert field.context.year == 2025
    assert field.context.event.name == "Italian Grand Prix"
    assert field.context.event.location == field.context.circuit.name == "Monza"
    assert field.context.session.name == "Race"
    assert field.source.provider == "FastF1"
    assert field.policy.policy_id == "representative-race-pace-v1"
    assert field.policy.track_conditions_adjusted is False
    assert field.drivers
    numbers = [driver.driver.driver_number for driver in field.drivers]
    assert len(numbers) == len(set(numbers))
    available = [driver for driver in field.drivers if driver.status == "available"]
    assert len(available) >= 2
    medians = [driver.metrics.median_lap_time_ms for driver in available]
    assert medians == sorted(medians)
    assert numbers == [
        driver.driver.driver_number
        for driver in sorted(
            field.drivers,
            key=lambda driver: (
                driver.metrics is None,
                driver.metrics.median_lap_time_ms if driver.metrics else 0,
                int(driver.driver.driver_number),
            ),
        )
    ]
    for driver in field.drivers:
        sample = driver.sample
        assert (
            sample.source_lap_count
            == sample.representative_lap_count + sample.excluded_lap_count
        )
        assert sum(sample.exclusions.model_dump().values()) == sample.excluded_lap_count
        assert driver.source.provider == "FastF1"
        if driver.metrics is not None:
            assert sample.representative_lap_count >= 5
            assert all(
                type(value) is int for value in driver.metrics.model_dump().values()
            )
            median = driver.metrics.median_lap_time_ms
            assert driver.delta_to_best_ms == median - medians[0]
            assert driver.rank == medians.index(median) + 1
            assert driver.tied == (medians.count(median) > 1)
        else:
            assert sample.representative_lap_count < 5
            assert driver.rank is driver.tied is driver.delta_to_best_ms is None
    a, b = (driver.driver.driver_number for driver in available[:2])
    detail = load_driver_pace(*source, a)
    assert detail.driver == available[0]
    assert len(detail.laps) == detail.driver.sample.source_lap_count
    comparison = load_pace_comparison(*source, a, b)
    assert comparison.driver_a == available[0]
    assert comparison.driver_b == available[1]
    assert comparison.comparison.delta_ms == medians[0] - medians[1]
    assert load_session_pace(*source) == field
    for response in (field, detail, comparison):
        json.dumps(response.model_dump(mode="json"), allow_nan=False)


@pytest.mark.skipif(
    os.getenv("F1_RUN_INTEGRATION") != "1",
    reason="Set F1_RUN_INTEGRATION=1 to run the real FastF1 integration test.",
)
def test_real_monza_race_session_maps_to_control_summary() -> None:
    from app.f1_data import load_session_summary

    summary = load_session_summary(2025, "Italian Grand Prix", "Race")

    assert summary.year == 2025
    assert summary.event.name == "Italian Grand Prix"
    assert summary.event.location == "Monza"
    assert summary.session.name == "Race"
    assert summary.session.type == "race"
    assert summary.circuit.name == "Monza"
    assert summary.participants
    assert summary.data_availability.results == "available"
    assert summary.data_availability.laps == "available"
    assert summary.source.provider == "FastF1"
