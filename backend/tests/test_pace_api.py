import json
from dataclasses import asdict
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.lap_analytics import RACE_PACE_POLICY

BASE = "/api/v1/seasons/2025/events/italian-grand-prix/sessions/race"


@pytest.mark.parametrize(
    "a,b,delta,outcome",
    [
        ("1", "4", -1000, "driver_a_faster"),
        ("4", "1", 1000, "driver_b_faster"),
        ("1", "1", 0, "tied"),
        ("1", "27", None, None),
    ],
)
def test_comparison_endpoint(
    client, controlled_source, monkeypatch, a, b, delta, outcome
):
    from app import lap_analytics
    from app.pace_models import DriverPaceComparisonResponse

    analyzer = Mock(wraps=lap_analytics.analyze_session_field)
    monkeypatch.setattr(lap_analytics, "analyze_session_field", analyzer)
    path = BASE + f"/pace/drivers/{a}/comparisons/{b}"
    response = client.get(path)
    assert response.status_code == 200
    result = DriverPaceComparisonResponse.model_validate(response.json())
    assert result.driver_a.driver.driver_number == a
    assert result.driver_b.driver.driver_number == b
    assert result.comparison.delta_ms == delta
    assert result.comparison.outcome == outcome
    controlled_source.assert_called_once()
    analyzer.assert_called_once()
    assert client.get(path).json() == response.json()
    assert controlled_source.call_count == analyzer.call_count == 2
    json.dumps(response.json(), allow_nan=False)


@pytest.mark.parametrize("a,b", [("01", "4"), ("1", "VER"), ("0", "4"), ("1", "-1")])
def test_comparison_malformed_selector_before_load(client, controlled_source, a, b):
    assert client.get(BASE + f"/pace/drivers/{a}/comparisons/{b}").status_code == 422
    controlled_source.assert_not_called()


@pytest.mark.parametrize("a,b", [("999", "1"), ("27", "999")])
def test_comparison_unknown_driver(client, controlled_source, a, b):
    response = client.get(BASE + f"/pace/drivers/{a}/comparisons/{b}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "driver_not_found"
    controlled_source.assert_called_once()


@pytest.mark.parametrize("suffix", ["/pace/drivers/1/comparisons/4", "/pace"])
@pytest.mark.parametrize(
    "old,new,status",
    [
        ("2025", "2024", 404),
        ("2025", "bad", 422),
        ("italian-grand-prix", "monaco-grand-prix", 404),
        ("race", "Race", 422),
    ],
)
def test_new_resources_validate_session_before_load(
    client, controlled_source, suffix, old, new, status
):
    response = client.get(BASE.replace(old, new) + suffix)
    assert response.status_code == status
    controlled_source.assert_not_called()


@pytest.mark.parametrize("suffix", ["/pace/drivers/1/comparisons/4", "/pace"])
@pytest.mark.parametrize("internal", [False, True])
def test_new_resources_preserve_failure_boundary(controlled_source, suffix, internal):
    from app.f1_data import DataSourceUnavailableError
    from app.main import app

    error = RuntimeError if internal else DataSourceUnavailableError
    controlled_source.side_effect = error("private detail")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(BASE + suffix)
    assert response.status_code == (500 if internal else 503)
    assert "private detail" not in response.text
    if not internal:
        assert response.json()["error"]["code"] == "data_source_unavailable"


@pytest.mark.parametrize(
    "key,value",
    [
        ("delta_ms", None),
        ("delta_ms", float("inf")),
        ("delta_ms", float("nan")),
        ("delta_ms", True),
        ("delta_ms", 1),
        ("outcome", "tied"),
        ("faster_driver_number", None),
        ("unexpected", True),
        ("status", "insufficient_data"),
    ],
)
def test_comparison_result_contract_rejects_invalid_state(key, value):
    from app.pace_models import DriverPaceComparisonResult

    payload = dict(
        status="available",
        delta_ms=-1000,
        outcome="driver_a_faster",
        faster_driver_number="1",
    )
    payload[key] = value
    with pytest.raises(ValidationError):
        DriverPaceComparisonResult.model_validate(payload)


def test_comparison_response_rejects_extra_and_inconsistent_availability(
    controlled_source,
):
    from app.pace_models import DriverPaceComparisonResponse
    from app.pace_service import load_pace_comparison

    payload = load_pace_comparison(
        2025, "Italian Grand Prix", "Race", "1", "4"
    ).model_dump()
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        DriverPaceComparisonResponse.model_validate(payload)
    del payload["unexpected"]
    payload["comparison"] = dict(
        status="insufficient_data",
        delta_ms=None,
        outcome=None,
        faster_driver_number=None,
    )
    with pytest.raises(ValidationError):
        DriverPaceComparisonResponse.model_validate(payload)


@pytest.mark.parametrize(
    "delta,outcome,winner",
    [
        (-999, "driver_a_faster", "1"),
        (0, "tied", None),
        (1000, "driver_b_faster", "4"),
    ],
)
def test_comparison_response_requires_delta_from_published_medians(
    controlled_source, delta, outcome, winner
):
    from app.pace_models import DriverPaceComparisonResponse
    from app.pace_service import load_pace_comparison

    payload = load_pace_comparison(
        2025, "Italian Grand Prix", "Race", "1", "4"
    ).model_dump()
    payload["comparison"].update(
        delta_ms=delta,
        outcome=outcome,
        faster_driver_number=winner,
    )
    with pytest.raises(ValidationError):
        DriverPaceComparisonResponse.model_validate(payload)


def test_driver_evidence_requires_unique_but_not_consecutive_source_order(
    controlled_source,
):
    from app.pace_models import DriverPaceAnalysisResponse
    from app.pace_service import load_driver_pace

    payload = load_driver_pace(2025, "Italian Grand Prix", "Race", "1").model_dump()
    payload["laps"][1]["source_order"] = 100
    DriverPaceAnalysisResponse.model_validate(payload)
    payload["laps"][1]["source_order"] = payload["laps"][0]["source_order"]
    with pytest.raises(ValidationError):
        DriverPaceAnalysisResponse.model_validate(payload)


def test_session_response_requires_unique_driver_numbers(controlled_source):
    from app.pace_models import SessionPaceAnalysisResponse
    from app.pace_service import load_session_pace

    payload = load_session_pace(2025, "Italian Grand Prix", "Race").model_dump()
    payload["drivers"][1]["driver"]["driver_number"] = payload["drivers"][0]["driver"][
        "driver_number"
    ]
    with pytest.raises(ValidationError):
        SessionPaceAnalysisResponse.model_validate(payload)


@pytest.fixture
def controlled_source(monkeypatch, pace_session_factory):
    from app import f1_data

    loader = Mock(return_value=pace_session_factory())
    monkeypatch.setattr(f1_data, "load_session", loader)
    return loader


@pytest.mark.parametrize("no_eligible", [False, True])
def test_session_pace_endpoint(client, controlled_source, monkeypatch, no_eligible):
    from app import lap_analytics
    from app.pace_models import SessionPaceAnalysisResponse

    analyzer = Mock(wraps=lap_analytics.analyze_session_field)
    monkeypatch.setattr(lap_analytics, "analyze_session_field", analyzer)
    if no_eligible:
        controlled_source.return_value.laps["TrackStatus"] = "24"
    response = client.get(BASE + "/pace")
    assert response.status_code == 200
    result = SessionPaceAnalysisResponse.model_validate(response.json())
    assert [d.driver.driver_number for d in result.drivers] == ["1", "4", "27"]
    assert [d.rank for d in result.drivers] == (
        [None, None, None] if no_eligible else [1, 2, None]
    )
    assert result.drivers[-1].sample.source_lap_count == 0
    assert result.drivers[-1].status == "insufficient_data"
    assert result.policy.track_conditions_adjusted is False
    assert result.source.provider == "FastF1"
    controlled_source.assert_called_once()
    analyzer.assert_called_once()
    assert client.get(BASE + "/pace").json() == response.json()
    assert controlled_source.call_count == analyzer.call_count == 2
    json.dumps(response.json(), allow_nan=False)
    payload = response.json()
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        SessionPaceAnalysisResponse.model_validate(payload)


def test_driver_endpoint_returns_complete_deterministic_evidence(
    client, controlled_source
):
    from app.pace_models import DriverPaceAnalysisResponse

    first = client.get(BASE + "/pace/drivers/4")
    second = client.get(BASE + "/pace/drivers/4")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    response = DriverPaceAnalysisResponse.model_validate(first.json())
    assert response.driver.driver.driver_number == "4"
    assert response.driver.sample.source_lap_count == len(response.laps) == 6
    assert response.driver.sample.representative_lap_count == 5
    assert response.laps[0].primary_exclusion_reason == "lap_one_start"
    assert all(lap.classification == "representative" for lap in response.laps[1:])
    assert response.driver.metrics.median_lap_time_ms == 91_000
    assert response.driver.delta_to_best_ms == 1000
    assert response.driver.rank == 2
    assert response.policy.track_conditions_adjusted is False
    assert response.source.provider == response.driver.source.provider == "FastF1"
    json.dumps(first.json(), allow_nan=False)
    assert controlled_source.call_count == 2
    controlled_source.assert_called_with(2025, "Italian Grand Prix", "Race")


def test_known_zero_row_driver_is_insufficient(client, controlled_source):
    response = client.get(BASE + "/pace/drivers/27")
    assert response.status_code == 200
    result = response.json()
    assert result["driver"]["status"] == "insufficient_data"
    assert result["laps"] == []
    for name in ("metrics", "rank", "tied", "delta_to_best_ms"):
        assert result["driver"][name] is None
    controlled_source.assert_called_once()


@pytest.mark.parametrize("nanoseconds", [0, -1, 1, 499_999, 500_000, 500_001])
def test_source_timing_boundary_reaches_api_without_clamping(
    client, controlled_source, nanoseconds
):
    import pandas as pd

    session = controlled_source.return_value
    session.laps.loc[session.laps.DriverNumber == "1", "LapTime"] = pd.Timedelta(
        nanoseconds, unit="ns"
    )
    response = client.get(BASE + "/pace/drivers/1")
    assert response.status_code == 200
    body = response.json()
    sample = body["driver"]["sample"]
    assert sample["source_lap_count"] == len(body["laps"]) == 6
    if nanoseconds < 500_000:
        assert sample["exclusions"]["invalid_timing"] == 6
        assert all(lap["lap_time_ms"] is None for lap in body["laps"])
        assert body["driver"]["status"] == "insufficient_data"
        assert body["driver"]["metrics"] is None
    else:
        assert sample["representative_lap_count"] == 5
        assert all(lap["lap_time_ms"] == 1 for lap in body["laps"])
        assert body["driver"]["metrics"] == {
            "median_lap_time_ms": 1,
            "mean_lap_time_ms": 1,
            "fastest_lap_time_ms": 1,
            "population_standard_deviation_ms": 0,
        }
    json.dumps(body, allow_nan=False)
    controlled_source.assert_called_once()


@pytest.mark.parametrize("column", ["TrackStatus", "LapTime", "DriverNumber"])
def test_required_source_schema_failure_is_503(client, controlled_source, column):
    session = controlled_source.return_value
    session.laps = session.laps.drop(columns=[column])
    response = client.get(BASE + "/pace/drivers/1")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "data_source_unavailable"


@pytest.mark.parametrize("column", ["LapNumber", "TrackStatus"])
def test_duplicate_required_source_column_is_sanitized_503(
    client, controlled_source, column
):
    import pandas as pd

    session = controlled_source.return_value
    session.laps = pd.concat([session.laps, session.laps[[column]]], axis=1)
    response = client.get(BASE + "/pace")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "data_source_unavailable",
            "message": "Formula 1 session data is currently unavailable.",
        }
    }


@pytest.mark.parametrize("number", ["0", "01", "-1", "1.0", "VER", "1%20"])
def test_malformed_driver_is_422_without_source(client, controlled_source, number):
    assert client.get(BASE + "/pace/drivers/" + number).status_code == 422
    controlled_source.assert_not_called()


@pytest.mark.parametrize(
    "old,new,expected",
    [
        ("2025", "not-a-year", 422),
        ("2025", "1949", 422),
        ("italian-grand-prix", "Italian-Grand-Prix", 422),
        ("race", "Race", 422),
        ("2025", "2024", 404),
        ("italian-grand-prix", "monaco-grand-prix", 404),
        ("race", "qualifying", 404),
    ],
)
def test_session_validation_precedes_source(
    client, controlled_source, old, new, expected
):
    response = client.get(BASE.replace(old, new) + "/pace/drivers/1")
    assert response.status_code == expected
    if expected == 404:
        assert response.json()["error"]["code"] == "session_not_supported"
    controlled_source.assert_not_called()


def test_unknown_driver_is_404_after_one_analysis(
    client, controlled_source, monkeypatch
):
    from app import lap_analytics

    analyzer = Mock(wraps=lap_analytics.analyze_session_field)
    monkeypatch.setattr(lap_analytics, "analyze_session_field", analyzer)
    response = client.get(BASE + "/pace/drivers/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "driver_not_found"
    controlled_source.assert_called_once()
    analyzer.assert_called_once()


def test_source_failure_is_controlled_503(client, controlled_source):
    from app.f1_data import DataSourceUnavailableError

    controlled_source.side_effect = DataSourceUnavailableError("private source detail")
    response = client.get(BASE + "/pace/drivers/1")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "data_source_unavailable"
    assert "private" not in response.text


def test_internal_failure_remains_500(controlled_source):
    from app.main import app

    controlled_source.side_effect = RuntimeError("internal implementation defect")
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(BASE + "/pace/drivers/1")
    assert response.status_code == 500
    assert "internal implementation defect" not in response.text


def test_health_is_independent_of_pace_loading(client, controlled_source):
    controlled_source.side_effect = RuntimeError("source should not be called")
    response = client.get("/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    controlled_source.assert_not_called()


def summary_payload():
    return {
        "driver": {
            "driver_number": "1",
            "abbreviation": None,
            "full_name": None,
            "team_name": None,
        },
        "status": "available",
        "policy_id": "representative-race-pace-v1",
        "sample": {
            "source_lap_count": 5,
            "representative_lap_count": 5,
            "excluded_lap_count": 0,
            "exclusions": {
                reason: 0
                for reason in (
                    "invalid_timing",
                    "lap_one_start",
                    "pit_in",
                    "pit_out",
                    "disrupted_status",
                    "anomalous_pace",
                )
            },
        },
        "metrics": {
            "median_lap_time_ms": 1,
            "mean_lap_time_ms": 1,
            "fastest_lap_time_ms": 1,
            "population_standard_deviation_ms": 0,
        },
        "rank": 1,
        "tied": False,
        "delta_to_best_ms": 0,
        "source": {"provider": "FastF1"},
    }


def test_summary_contract_accepts_minimum_timing_and_zero_spread():
    from app.pace_models import DriverPaceSummary

    payload = summary_payload()
    assert DriverPaceSummary.model_validate(payload).model_dump(mode="json") == payload


@pytest.mark.parametrize(
    "path",
    [(), ("driver",), ("sample",), ("sample", "exclusions"), ("metrics",), ("source",)],
)
def test_contract_rejects_extra_fields_at_each_level(path):
    from app.pace_models import DriverPaceSummary

    payload = summary_payload()
    target = payload
    for key in path:
        target = target[key]
    target["unexpected"] = True
    with pytest.raises(ValidationError):
        DriverPaceSummary.model_validate(payload)


@pytest.mark.parametrize("number", ["01", "0", "-1", "VER", "1.0", " 1", 1])
def test_contract_requires_canonical_driver_number(number):
    from app.pace_models import DriverPaceSummary

    payload = summary_payload()
    payload["driver"]["driver_number"] = number
    with pytest.raises(ValidationError):
        DriverPaceSummary.model_validate(payload)


@pytest.mark.parametrize(
    "key,value",
    [
        ("metrics", None),
        ("rank", None),
        ("tied", None),
        ("delta_to_best_ms", None),
        ("status", "insufficient_data"),
    ],
)
def test_available_contract_rejects_inconsistent_state(key, value):
    from app.pace_models import DriverPaceSummary

    payload = summary_payload()
    payload[key] = value
    with pytest.raises(ValidationError):
        DriverPaceSummary.model_validate(payload)


def test_insufficient_contract_requires_null_metrics_and_small_sample():
    from app.pace_models import DriverPaceSummary

    payload = summary_payload()
    payload.update(
        status="insufficient_data",
        metrics=None,
        rank=None,
        tied=None,
        delta_to_best_ms=None,
    )
    with pytest.raises(ValidationError):
        DriverPaceSummary.model_validate(payload)
    payload["sample"].update(source_lap_count=4, representative_lap_count=4)
    assert DriverPaceSummary.model_validate(payload).metrics is None
    payload["rank"] = 1
    with pytest.raises(ValidationError):
        DriverPaceSummary.model_validate(payload)


@pytest.mark.parametrize(
    "key", ["source_lap_count", "representative_lap_count", "excluded_lap_count"]
)
def test_sample_counts_must_reconcile(key):
    from app.pace_models import DriverPaceSummary

    payload = summary_payload()
    payload["sample"][key] += 1
    with pytest.raises(ValidationError):
        DriverPaceSummary.model_validate(payload)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -1, True, "1"])
def test_duration_contract_rejects_invalid_numbers(value):
    from app.pace_models import DriverPaceSummary

    payload = summary_payload()
    payload["metrics"]["median_lap_time_ms"] = value
    with pytest.raises(ValidationError):
        DriverPaceSummary.model_validate(payload)


def test_policy_contract_is_exact_and_immutable():
    from app.pace_models import RepresentativeRacePacePolicy

    policy = RepresentativeRacePacePolicy.model_validate(asdict(RACE_PACE_POLICY))
    assert policy.track_conditions_adjusted is False
    with pytest.raises(ValidationError):
        policy.anomalous_pace_threshold_percent = 107
    for key, value in (
        ("track_conditions_adjusted", True),
        ("minimum_representative_laps", 4),
        ("exclusion_precedence", tuple(reversed(policy.exclusion_precedence))),
    ):
        payload = asdict(RACE_PACE_POLICY)
        payload[key] = value
        with pytest.raises(ValidationError):
            RepresentativeRacePacePolicy.model_validate(payload)


@pytest.mark.parametrize(
    "classification,reason,lap_number,time,valid",
    [
        ("representative", None, 2, 1, True),
        ("representative", "pit_in", 2, 1, False),
        ("excluded", None, 2, 1, False),
        ("excluded", "invalid_timing", None, 1, True),
        ("excluded", "invalid_timing", 2, None, True),
        ("excluded", "pit_in", None, 1, False),
        ("representative", None, 2, None, False),
    ],
)
def test_lap_classification_contract(classification, reason, lap_number, time, valid):
    from app.pace_models import LapClassification

    payload = dict(
        source_order=1,
        lap_number=lap_number,
        lap_time_ms=time,
        classification=classification,
        primary_exclusion_reason=reason,
        track_status_codes=None,
        disruptive_statuses=[],
        is_accurate=None,
        compound=None,
    )
    if valid:
        assert (
            LapClassification.model_validate(payload).classification == classification
        )
    else:
        with pytest.raises(ValidationError):
            LapClassification.model_validate(payload)
