import os

import pytest

if os.getenv("F1_RUN_INTEGRATION") != "1":
    pytest.skip(
        "Set F1_RUN_INTEGRATION=1 to run the real FastF1 integration test.",
        allow_module_level=True,
    )

pytestmark = pytest.mark.integration


def test_real_monza_race_session_maps_to_control_summary() -> None:
    import fastf1

    from app.f1_data import map_session_summary

    session = fastf1.get_session(2025, "Italian Grand Prix", "Race")
    session.load(laps=True, telemetry=False, weather=False, messages=False)

    summary = map_session_summary(session)

    assert summary.year == 2025
    assert summary.event.name == "Italian Grand Prix"
    assert summary.session.name == "Race"
    assert summary.participants
    assert summary.timing.scheduled_start_utc is not None
    assert summary.source.provider == "FastF1"
