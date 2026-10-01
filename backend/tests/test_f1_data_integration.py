import json
import os
import re
from collections import Counter
from dataclasses import asdict
from enum import Enum
from math import isfinite
from unittest.mock import Mock

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("F1_RUN_INTEGRATION") != "1",
    reason="Set F1_RUN_INTEGRATION=1 to run the real FastF1 integration test.",
)
def test_real_monza_race_context_from_one_snapshot(monkeypatch) -> None:
    from app.analytics import race_context_analytics as analytics
    from app.data import f1_data
    from app.services import race_context_service as service

    loader = Mock(wraps=f1_data.load_session)
    monkeypatch.setattr(f1_data, "load_session", loader)
    snapshot = f1_data.load_session(2025, "Italian Grand Prix", "Race")
    inputs = f1_data.map_race_context_inputs(snapshot)
    summary = f1_data.map_session_summary(snapshot)
    analysis = analytics.analyze_race_context(inputs)
    loader.assert_called_once_with(2025, "Italian Grand Prix", "Race")
    assert inputs.participants and inputs.lap_rows
    assert len(inputs.lap_rows) == len(snapshot.laps)
    assert sum(p.result_evidence_count for p in inputs.participants) == len(
        snapshot.results
    )
    numbers = [p.identity.driver_number for p in analysis.participants]
    assert set(numbers) == {p.identity.driver_number for p in inputs.participants}
    assert len(numbers) == len(set(numbers))
    assert numbers == sorted(
        numbers,
        key=lambda n: (0, int(n), "") if re.fullmatch(r"[1-9][0-9]*", n) else (1, 0, n),
    )

    pending = [asdict(inputs)]
    while pending:
        value = pending.pop()
        if type(value) is dict:
            pending.extend(value.values())
        elif type(value) is tuple:
            pending.extend(value)
        elif isinstance(value, Enum):
            assert type(value).__module__ == analytics.__name__
        else:
            assert type(value) in {str, int, bool, type(None)}

    for participant in analysis.participants:
        rows = [
            row
            for row in inputs.lap_rows
            if row.driver_number == participant.identity.driver_number
        ]
        keyed = [
            row
            for row in rows
            if row.lap_number.state == analytics.NormalizedValueState.AVAILABLE
        ]
        assert sum(
            lap.source_evidence_count for lap in participant.lap_contexts
        ) == len(keyed)
        assert participant.unassociated_evidence_count == len(rows) - len(keyed)
        expected_boundaries = Counter(
            (kind, row.lap_number.value)
            for row in keyed
            for kind, timestamp in (
                (analytics.PitBoundaryKind.ENTRY, row.pit_entry_time_ns),
                (analytics.PitBoundaryKind.EXIT, row.pit_exit_time_ns),
            )
            if timestamp.state != analytics.NormalizedValueState.ABSENT
        )
        represented = Counter()
        for item in participant.pit_evidence:
            assert item.source_boundary_count == sum(
                boundary.source_evidence_count for boundary in item.boundaries
            )
            for boundary in item.boundaries:
                represented[(boundary.kind, boundary.lap_number)] += (
                    boundary.source_evidence_count
                )
        assert represented == expected_boundaries
        states = Counter(item.state.value for item in participant.pit_evidence)
        counts = asdict(participant.pit_evidence_counts)
        assert counts.pop("total") == len(participant.pit_evidence)
        assert counts == {
            state.value: states[state.value] for state in analytics.PitEvidenceState
        }

    assert inputs.unassociated_row_count == sum(
        row.driver_number not in set(numbers) for row in inputs.lap_rows
    )
    assert all(analytics.analyze_race_context(inputs) == analysis for _ in range(3))

    # Exercise both real projections of this retained result, not another acquisition.
    shared = Mock(return_value=(summary, analysis))
    monkeypatch.setattr(service, "_load_analysis", shared)
    no_reload = Mock(side_effect=AssertionError("Acceptance must reuse its snapshot"))
    for name in ("load_session", "map_race_context_inputs", "map_session_summary"):
        monkeypatch.setattr(f1_data, name, no_reload)
    selectors = (2025, "italian-grand-prix", "race")
    field = service.load_session_race_context(*selectors)
    selected = next(
        p
        for p in field.participants
        if re.fullmatch(r"[1-9][0-9]*", p.driver.driver_number)
    )
    detail = service.load_driver_race_context(*selectors, selected.driver.driver_number)
    assert detail.participant == selected
    assert detail.context == field.context
    assert field.source.provider == detail.source.provider == "FastF1"
    assert [p.driver.driver_number for p in field.participants] == numbers
    internal = next(
        p
        for p in analysis.participants
        if p.identity.driver_number == selected.driver.driver_number
    )
    assert len(detail.lap_contexts) == len(internal.lap_contexts)
    assert len(detail.pit_evidence) == len(internal.pit_evidence)
    assert service.load_session_race_context(*selectors) == field
    assert (
        service.load_driver_race_context(*selectors, selected.driver.driver_number)
        == detail
    )
    no_reload.assert_not_called()
    loader.assert_called_once()
    assert shared.call_count == 4
    for response in (field, detail):
        json.dumps(response.model_dump(mode="json"), allow_nan=False)


@pytest.mark.skipif(
    os.getenv("F1_RUN_INTEGRATION") != "1",
    reason="Set F1_RUN_INTEGRATION=1 to run the real FastF1 integration test.",
)
def test_real_monza_tire_stints_through_application_service(monkeypatch) -> None:
    from app.analytics import stint_analytics
    from app.analytics.stint_analytics import StintUnavailabilityReason
    from app.data import f1_data
    from app.services.stint_service import load_session_tire_stints

    source = (2025, "Italian Grand Prix", "Race")
    real_map = f1_data.map_lap_inputs
    real_analysis = stint_analytics.analyze_session_stints
    normalized = []

    def capture_normalization(session):
        result = real_map(session)
        normalized.append(result)
        return result

    map_spy = Mock(side_effect=capture_normalization)
    monkeypatch.setattr(f1_data, "map_lap_inputs", map_spy)

    field = load_session_tire_stints(*source)
    map_spy.assert_called_once()

    session = map_spy.call_args.args[0]
    inputs = normalized[0]
    analysis = real_analysis(inputs)
    required_columns = {
        "DriverNumber",
        "LapNumber",
        "LapTime",
        "Stint",
        "TyreLife",
        "Compound",
        "FastF1Generated",
        "IsAccurate",
        "TrackStatus",
        "PitInTime",
        "PitOutTime",
    }
    assert required_columns <= set(session.laps.columns)
    assert inputs.laps
    assert any(
        lap.stint is not None and lap.tyre_life is not None and lap.compound is not None
        for lap in inputs.laps
    )
    assert any(lap.provider_generated is not None for lap in inputs.laps)
    assert any(lap.is_accurate is not None for lap in inputs.laps)
    assert all(lap.stint is None or type(lap.stint) is int for lap in inputs.laps)
    assert all(
        lap.tyre_life is None or type(lap.tyre_life) is int for lap in inputs.laps
    )
    assert all(
        lap.provider_generated is None or type(lap.provider_generated) is bool
        for lap in inputs.laps
    )
    assert all(
        lap.is_accurate is None or type(lap.is_accurate) is bool for lap in inputs.laps
    )

    assert type(field.context.year) is int
    assert type(field.context.event.round_number) is int
    assert field.context.event.name == "Italian Grand Prix"
    assert field.context.event.location == field.context.circuit.name == "Monza"
    assert field.context.session.name == "Race"
    assert field.source.provider == "FastF1"
    assert field.drivers
    numbers = [driver.driver.driver_number for driver in field.drivers]
    participant_numbers = [driver.driver_number for driver in inputs.participants]
    assert numbers == sorted(participant_numbers, key=int)
    assert len(numbers) == len(set(numbers))
    assert numbers == [driver.driver.driver_number for driver in analysis.drivers]
    assert sum(len(driver.laps) for driver in analysis.drivers) == len(inputs.laps)
    assert any(driver.stints for driver in field.drivers)

    for public_driver, internal_driver in zip(
        field.drivers, analysis.drivers, strict=True
    ):
        assert (
            public_driver.driver.driver_number == internal_driver.driver.driver_number
        )
        assert (
            public_driver.unassigned_lap_count == internal_driver.unassigned_lap_count
        )
        assert (
            len(internal_driver.laps)
            == sum(stint.sample.total_lap_count for stint in internal_driver.stints)
            + internal_driver.unassigned_lap_count
        )
        assert sum(
            stint.sample.total_lap_count for stint in public_driver.stints
        ) + public_driver.unassigned_lap_count == len(internal_driver.laps)
        assert [stint.reported_stint for stint in public_driver.stints] == [
            stint.reported_stint for stint in internal_driver.stints
        ]
        order = [
            (
                stint.lap_range is None,
                stint.lap_range.minimum if stint.lap_range else 0,
                stint.reported_stint,
            )
            for stint in public_driver.stints
        ]
        assert order == sorted(order)
        for public_stint, internal_stint in zip(
            public_driver.stints, internal_driver.stints, strict=True
        ):
            sample = public_stint.sample
            internal_sample = internal_stint.sample
            assert sample.total_lap_count == internal_sample.total_lap_count
            assert (
                sample.eligible_observation_count
                == internal_sample.eligible_observation_count
            )
            assert (
                sample.excluded_observation_count
                == internal_sample.excluded_observation_count
            )
            assert (
                sample.distinct_eligible_tire_age_count
                == internal_sample.distinct_eligible_tire_age_count
            )
            assert sample.exclusions.model_dump() == {
                reason.value: count for reason, count in internal_sample.exclusions
            }
            if public_stint.status == "available":
                assert public_stint.normalized_compound in {"SOFT", "MEDIUM", "HARD"}
                assert sample.eligible_observation_count >= 6
                assert sample.distinct_eligible_tire_age_count >= 6
                assert public_stint.unavailability_reason is None
                assert isfinite(public_stint.observed_pace_trend_seconds_per_lap)
                assert isfinite(public_stint.median_absolute_residual_seconds)
            else:
                assert isinstance(
                    public_stint.unavailability_reason, StintUnavailabilityReason
                )
                assert public_stint.observed_pace_trend_seconds_per_lap is None
                assert public_stint.median_absolute_residual_seconds is None

    assert field.limitations.interpretation == "observational_association"
    assert field.limitations.isolated_physical_tire_wear is False
    assert field.limitations.unadjusted_for == (
        "fuel_load_or_burn",
        "traffic",
        "track_evolution",
        "driver_tire_management",
        "changing_environmental_conditions",
        "other_unmodeled_race_effects",
    )
    assert field.limitations.description == (
        "This observed pace trend is an unadjusted association and is not an "
        "estimate of isolated physical tire wear."
    )
    json.dumps(field.model_dump(mode="json"), allow_nan=False)

    monkeypatch.setattr(f1_data, "load_session", Mock(return_value=session))
    assert load_session_tire_stints(*source) == field
    assert real_analysis(inputs) == analysis


@pytest.mark.skipif(
    os.getenv("F1_RUN_INTEGRATION") != "1",
    reason="Set F1_RUN_INTEGRATION=1 to run the real FastF1 integration test.",
)
def test_real_monza_race_pace_through_application_service() -> None:
    from app.services.pace_service import (
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
    from app.data.f1_data import load_session_summary

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
