import os

import pytest

pytestmark = pytest.mark.integration


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
