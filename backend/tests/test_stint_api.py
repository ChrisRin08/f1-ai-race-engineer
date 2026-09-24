"""Strict tire-stint contracts and additive HTTP resource tests."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

# Share controlled provider data without changing existing fixture defaults.
from test_stint_service import (  # noqa: F401
    SOURCE,
    make_stint_field_session,
    make_stint_session,
)

from app import f1_data
from app.stint_analytics import StintUnavailabilityReason


@pytest.fixture
def payload(monkeypatch, stint_session):
    from app.stint_service import load_driver_tire_stints

    monkeypatch.setattr(f1_data, "load_session", Mock(return_value=stint_session))
    return load_driver_tire_stints(*SOURCE, "1").model_dump(mode="json")


def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            yield from objects(child)


def test_every_public_object_forbids_extras_and_requires_nullable_fields(payload):
    from app.stint_models import DriverTireStintAnalysisResponse

    for obj in objects(payload):
        obj["unexpected"] = True
        with pytest.raises(ValidationError):
            DriverTireStintAnalysisResponse.model_validate(payload)
        del obj["unexpected"]
        for key, value in list(obj.items()):
            if value is None:
                del obj[key]
                with pytest.raises(ValidationError):
                    DriverTireStintAnalysisResponse.model_validate(payload)
                obj[key] = value
    DriverTireStintAnalysisResponse.model_validate(payload)


@pytest.mark.parametrize("trend", [-1.234, 0.0, 1.234])
def test_signed_finite_trend_and_frozen_models(payload, trend):
    from app.stint_models import DriverTireStintAnalysisResponse

    payload["driver"]["stints"][0]["observed_pace_trend_seconds_per_lap"] = trend
    result = DriverTireStintAnalysisResponse.model_validate(payload)
    assert result.driver.stints[0].observed_pace_trend_seconds_per_lap == trend
    for model, key in [
        (result, "laps"),
        (result.policy, "metric"),
        (result.limitations, "description"),
        (result.driver, "stints"),
        (result.driver.stints[0], "status"),
        (result.driver.stints[0].sample, "total_lap_count"),
        (result.laps[0], "pit_in"),
    ]:
        with pytest.raises(ValidationError):
            setattr(model, key, getattr(model, key))


@pytest.mark.parametrize(
    "key,value",
    [
        ("observed_pace_trend_seconds_per_lap", None),
        ("median_absolute_residual_seconds", None),
        ("observed_pace_trend_seconds_per_lap", float("nan")),
        ("observed_pace_trend_seconds_per_lap", float("inf")),
        ("median_absolute_residual_seconds", -float("inf")),
        ("median_absolute_residual_seconds", -0.001),
        ("observed_pace_trend_seconds_per_lap", True),
        ("observed_pace_trend_seconds_per_lap", "0.123"),
        ("observed_pace_trend_seconds_per_lap", 0.0001),
        ("status", "unavailable"),
        ("unavailability_reason", "missing_compound"),
    ],
)
def test_available_rejects_invalid_metrics_or_state(payload, key, value):
    from app.stint_models import DriverTireStintAnalysisResponse

    payload["driver"]["stints"][0][key] = value
    with pytest.raises(ValidationError):
        DriverTireStintAnalysisResponse.model_validate(payload)


@pytest.mark.parametrize(
    "key,value",
    [
        ("observed_pace_trend_seconds_per_lap", 0.0),
        ("median_absolute_residual_seconds", 0.0),
        ("unavailability_reason", None),
        ("unavailability_reason", "invented"),
        ("status", "available"),
    ],
)
def test_unavailable_requires_reason_and_null_metrics(payload, key, value):
    from app.stint_models import DriverTireStintAnalysisResponse

    payload["driver"]["stints"][1][key] = value
    with pytest.raises(ValidationError):
        DriverTireStintAnalysisResponse.model_validate(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        "drop",
        "duplicate",
        "assignment",
        "unassigned",
        "eligible",
        "exclusion",
        "distinct_age",
        "sample_total",
        "sample_excluded",
        "negative_count",
        "bool_count",
        "identity",
        "duplicate_stint",
        "disposition_reason",
        "unassigned_reason",
        "status_duplicates",
        "strict_bool",
        "range",
    ],
)
def test_public_evidence_and_sample_reconciliation(payload, mutation):
    from app.stint_models import DriverTireStintAnalysisResponse

    sample = payload["driver"]["stints"][0]["sample"]
    if mutation == "drop":
        payload["laps"].pop()
    elif mutation == "duplicate":
        payload["laps"].append(deepcopy(payload["laps"][0]))
    elif mutation == "assignment":
        payload["laps"][0]["reported_stint"] = 100
    elif mutation == "unassigned":
        payload["driver"]["unassigned_lap_count"] += 1
    elif mutation == "eligible":
        sample["eligible_observation_count"] += 1
    elif mutation == "exclusion":
        sample["exclusions"].update(lap_one_start=0, pit_in=1)
    elif mutation == "distinct_age":
        sample["distinct_eligible_tire_age_count"] -= 1
    elif mutation == "sample_total":
        sample["total_lap_count"] += 1
    elif mutation == "sample_excluded":
        sample["excluded_observation_count"] += 1
    elif mutation == "negative_count":
        sample["exclusions"]["pit_in"] = -1
    elif mutation == "bool_count":
        sample["total_lap_count"] = True
    elif mutation == "identity":
        payload["driver"]["stints"][0]["driver_number"] = "4"
    elif mutation == "duplicate_stint":
        payload["driver"]["stints"].append(deepcopy(payload["driver"]["stints"][0]))
    elif mutation == "disposition_reason":
        payload["laps"][0]["primary_exclusion_reason"] = None
    elif mutation == "unassigned_reason":
        payload["laps"][-1]["unassigned_reason"] = None
    elif mutation == "status_duplicates":
        payload["laps"][0]["track_status_codes"] = ["1", "1"]
    elif mutation == "strict_bool":
        payload["laps"][0]["pit_in"] = 0
    elif mutation == "range":
        payload["driver"]["stints"][0]["lap_range"]["minimum"] = 100
    with pytest.raises(ValidationError):
        DriverTireStintAnalysisResponse.model_validate(payload)


def test_policy_and_limitations_contract(payload):
    from app.stint_models import DriverTireStintAnalysisResponse

    policy = payload["policy"]
    assert policy["estimator"] == "theil_sen"
    assert policy["intercept_method"] == "joint"
    assert policy["publication_decimal_places"] == 3
    assert policy["availability_precedence"][2] == [
        "missing_compound",
        "unsupported_compound",
    ]
    limits = payload["limitations"]
    assert limits["interpretation"] == "observational_association"
    assert limits["isolated_physical_tire_wear"] is False
    assert limits["unadjusted_for"] == [
        "fuel_load_or_burn",
        "traffic",
        "track_evolution",
        "driver_tire_management",
        "changing_environmental_conditions",
        "other_unmodeled_race_effects",
    ]
    assert limits["description"] == (
        "This observed pace trend is an unadjusted association and is not an "
        "estimate of isolated physical tire wear."
    )
    for target, key, value in [
        (policy, "estimator", "least_squares"),
        (policy, "eligible_compounds", ["SOFT"] * 3),
        (policy, "minimum_eligible_observations", "6"),
        (limits, "isolated_physical_tire_wear", 0),
        (limits, "unadjusted_for", ["traffic"] * 6),
    ]:
        original = target[key]
        target[key] = value
        with pytest.raises(ValidationError):
            DriverTireStintAnalysisResponse.model_validate(payload)
        target[key] = original
    # Same-tier members are a set semantically; publication is canonical.
    policy["availability_precedence"][2].reverse()
    result = DriverTireStintAnalysisResponse.model_validate(payload)
    assert result.model_dump(mode="json")["policy"]["availability_precedence"][2] == [
        "missing_compound",
        "unsupported_compound",
    ]


BASE = "/api/v1/seasons/2025/events/italian-grand-prix/sessions/race"
PATH = BASE + "/tire-stints/drivers/1"


@pytest.fixture
def controlled_stint_source(monkeypatch, stint_session):
    loader = Mock(return_value=stint_session)
    monkeypatch.setattr(f1_data, "load_session", loader)
    return loader


@pytest.mark.parametrize(
    "compound,normalized,reason",
    [
        ("medium", "MEDIUM", None),
        ("INTERMEDIATE", "INTERMEDIATE", "wet_weather_compound"),
        ("WET", "WET", "wet_weather_compound"),
        (None, None, "missing_compound"),
        ("UNKNOWN", None, "unsupported_compound"),
        ("conflict", None, "inconsistent_stint_metadata"),
    ],
)
def test_driver_route_complete_finite_deterministic_response(
    client, monkeypatch, controlled_stint_source, compound, normalized, reason
):
    import json

    from app import stint_analytics
    from app.stint_models import DriverTireStintAnalysisResponse

    source = controlled_stint_source.return_value
    source.laps.loc[source.laps.Stint == 9, "Compound"] = compound
    if compound == "conflict":
        source.laps.loc[source.laps.Stint == 9, "Compound"] = "medium"
        source.laps.loc[source.laps.LapNumber == 3, "Compound"] = "HARD"
    analyzer = Mock(wraps=stint_analytics.analyze_session_stints)
    monkeypatch.setattr(stint_analytics, "analyze_session_stints", analyzer)
    response = client.get(PATH)
    assert response.status_code == 200
    result = DriverTireStintAnalysisResponse.model_validate(response.json())
    first = result.driver.stints[0]
    assert first.reported_compound == ("medium" if compound == "conflict" else compound)
    assert first.normalized_compound == normalized
    assert first.unavailability_reason == reason
    assert (first.observed_pace_trend_seconds_per_lap is not None) == (reason is None)
    assert (first.median_absolute_residual_seconds is not None) == (reason is None)
    assert len(result.laps) == 11
    assert result.laps[-1] == result.laps[-2]
    assert result.laps[-1].disposition == "unassigned"
    assert result.laps[-1].reported_tire_age is None
    assert result.laps[0].primary_exclusion_reason == "lap_one_start"
    assert all(
        lap.is_accurate is None and lap.provider_generated is None
        for lap in result.laps
    )
    assert result.laps[0].lap_time_ms == 90124  # Existing half-up display conversion.
    controlled_stint_source.assert_called_once_with(*SOURCE)
    analyzer.assert_called_once()
    for _ in range(2):
        assert client.get(PATH).content == response.content
    assert controlled_stint_source.call_count == analyzer.call_count == 3
    json.dumps(response.json(), allow_nan=False)
    assert "source_order" not in response.text


@pytest.mark.parametrize(
    "old,new,status,code",
    [
        ("2025", "bad", 422, None),
        ("2025", "1949", 422, None),
        ("italian-grand-prix", "Italian-Grand-Prix", 422, None),
        ("race", "Race", 422, None),
        ("drivers/1", "drivers/01", 422, None),
        ("drivers/1", "drivers/VER", 422, None),
        ("drivers/1", "drivers/0", 422, None),
        ("2025", "2024", 404, "session_not_supported"),
        ("italian-grand-prix", "monaco-grand-prix", 404, "session_not_supported"),
        ("race", "qualifying", 404, "session_not_supported"),
    ],
)
def test_driver_selectors_fail_before_source(
    client, controlled_stint_source, old, new, status, code
):
    response = client.get(PATH.replace(old, new))
    assert response.status_code == status
    if code:
        assert response.json()["error"]["code"] == code
    controlled_stint_source.assert_not_called()


@pytest.mark.parametrize("number,status", [("27", 200), ("4", 200), ("999", 404)])
def test_known_empty_or_unavailable_driver_is_not_missing(
    client, monkeypatch, controlled_stint_source, number, status
):
    from app import stint_analytics

    analyzer = Mock(wraps=stint_analytics.analyze_session_stints)
    monkeypatch.setattr(stint_analytics, "analyze_session_stints", analyzer)
    response = client.get(BASE + f"/tire-stints/drivers/{number}")
    assert response.status_code == status
    if status == 404:
        assert response.json() == {
            "error": {
                "code": "driver_not_found",
                "message": "The requested driver is not in the session results.",
            }
        }
    elif number == "27":
        assert response.json()["driver"]["stints"] == response.json()["laps"] == []
    else:
        assert response.json()["driver"]["stints"][0]["status"] == "unavailable"
    controlled_stint_source.assert_called_once()
    analyzer.assert_called_once()


@pytest.mark.parametrize("stage", ["source", "normalization", "analysis"])
@pytest.mark.parametrize("internal", [False, True])
def test_driver_error_boundary(monkeypatch, controlled_stint_source, stage, internal):
    from fastapi.testclient import TestClient

    from app import stint_analytics
    from app.main import app

    failure = (RuntimeError if internal else f1_data.DataSourceUnavailableError)(
        "private secret path"
    )
    if stage == "source":
        controlled_stint_source.side_effect = failure
    elif stage == "normalization":
        monkeypatch.setattr(f1_data, "map_lap_inputs", Mock(side_effect=failure))
    else:
        monkeypatch.setattr(
            stint_analytics, "analyze_session_stints", Mock(side_effect=failure)
        )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(PATH)
    assert response.status_code == (500 if internal else 503)
    assert "private secret path" not in response.text
    if not internal:
        assert response.json() == {
            "error": {
                "code": "data_source_unavailable",
                "message": "Formula 1 session data is currently unavailable.",
            }
        }


@pytest.mark.parametrize(
    "compound,eligible,distinct",
    [
        ("WET", 6, 6),
        ("INTERMEDIATE", 6, 6),
        (None, 6, 6),
        ("MEDIUM", 5, 5),
        ("MEDIUM", 6, 5),
    ],
)
def test_direct_available_summary_rejects_impossible_public_facts(
    payload, compound, eligible, distinct
):
    from app.stint_models import ObservedStintSummary, StintSample

    summary = payload["driver"]["stints"][0]
    summary["normalized_compound"] = compound
    sample = summary["sample"]
    sample.update(
        eligible_observation_count=eligible,
        distinct_eligible_tire_age_count=distinct,
        total_lap_count=eligible + sample["excluded_observation_count"],
    )
    # Keep counts valid so rejection comes from the available-state invariant,
    # not the sample model or root evidence reconciliation.
    StintSample.model_validate(sample)
    with pytest.raises(ValidationError, match="Available"):
        ObservedStintSummary.model_validate(summary)


@pytest.mark.parametrize(
    "compound,trend", [("SOFT", -0.123), ("MEDIUM", 0.0), ("HARD", 0.123)]
)
def test_direct_available_summary_preserves_slicks_and_signed_metrics(
    payload, compound, trend
):
    from app.stint_models import ObservedStintSummary

    summary = payload["driver"]["stints"][0]
    summary.update(
        reported_compound=compound,
        normalized_compound=compound,
        observed_pace_trend_seconds_per_lap=trend,
        median_absolute_residual_seconds=0.0,
    )
    result = ObservedStintSummary.model_validate(summary)
    assert result.normalized_compound == compound
    assert result.observed_pace_trend_seconds_per_lap == trend
    assert result.median_absolute_residual_seconds == 0.0


@pytest.mark.parametrize(
    "compound,reason",
    [
        ("WET", "wet_weather_compound"),
        ("INTERMEDIATE", "wet_weather_compound"),
        (None, "inconsistent_stint_metadata"),
        ("MEDIUM", "inconsistent_stint_metadata"),
        ("MEDIUM", "insufficient_eligible_sample"),
    ],
)
def test_direct_unavailable_summary_keeps_audit_states(payload, compound, reason):
    from app.stint_models import ObservedStintSummary

    summary = payload["driver"]["stints"][1]
    summary.update(
        reported_compound=compound if compound is not None else "medium",
        normalized_compound=compound,
        unavailability_reason=reason,
    )
    # Existing unavailable sample has fewer than six observations; new checks
    # must not constrain unavailable audit evidence or infer availability.
    result = ObservedStintSummary.model_validate(summary)
    assert result.status == "unavailable"
    assert result.reported_compound == summary["reported_compound"]
    assert result.normalized_compound == compound
    assert result.observed_pace_trend_seconds_per_lap is None
    assert result.median_absolute_residual_seconds is None


@pytest.mark.parametrize(
    "reason", list(StintUnavailabilityReason), ids=lambda reason: reason.value
)
def test_every_unavailability_reason_is_publicly_projectable(payload, reason):
    from app.stint_models import ObservedStintSummary

    summary = payload["driver"]["stints"][1]
    summary["unavailability_reason"] = reason.value
    result = ObservedStintSummary.model_validate(summary)
    assert result.status == "unavailable"
    assert result.unavailability_reason == reason
    assert result.observed_pace_trend_seconds_per_lap is None
    assert result.median_absolute_residual_seconds is None


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("repeated_age", "inconsistent_tire_age"),
        ("unusable_age", "missing_tire_age"),
        ("inaccurate_laps", "insufficient_eligible_sample"),
    ],
)
def test_route_projects_age_and_sample_unavailability(
    client, controlled_stint_source, mutation, reason
):
    laps = controlled_stint_source.return_value.laps
    if mutation == "repeated_age":
        laps.loc[laps.LapNumber == 7, "TyreLife"] = 11
    elif mutation == "unusable_age":
        laps.loc[laps.LapNumber == 7, "TyreLife"] = None
    else:
        laps.loc[laps.LapNumber.isin((6, 7)), "IsAccurate"] = False
    stints = client.get(PATH).json()["driver"]["stints"]
    assert [stint["reported_stint"] for stint in stints] == [9, 3]
    assert stints[0]["status"] == "unavailable"
    assert stints[0]["unavailability_reason"] == reason
    assert stints[0]["observed_pace_trend_seconds_per_lap"] is None
    assert stints[0]["median_absolute_residual_seconds"] is None


def test_route_publishes_zero_as_an_available_result(client, controlled_stint_source):
    from math import copysign

    laps = controlled_stint_source.return_value.laps
    laps["LapTime"] = laps["LapTime"].iloc[0]
    first = client.get(PATH).json()["driver"]["stints"][0]
    assert first["status"] == "available"
    assert first["unavailability_reason"] is None
    for metric in (
        "observed_pace_trend_seconds_per_lap",
        "median_absolute_residual_seconds",
    ):
        assert first[metric] == 0.0
        assert copysign(1, first[metric]) == 1


SESSION_PATH = BASE + "/tire-stints"


def test_session_route_compact_finite_deterministic_response(
    client, monkeypatch, stint_field_session
):
    import json

    from app import stint_analytics

    loader = Mock(return_value=stint_field_session)
    analyzer = Mock(wraps=stint_analytics.analyze_session_stints)
    monkeypatch.setattr(f1_data, "load_session", loader)
    monkeypatch.setattr(stint_analytics, "analyze_session_stints", analyzer)
    response = client.get(SESSION_PATH)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"context", "policy", "limitations", "drivers", "source"}
    assert [d["driver"]["driver_number"] for d in body["drivers"]] == [
        "1",
        "4",
        "10",
        "27",
    ]
    assert [s["status"] for s in body["drivers"][0]["stints"]] == [
        "available",
        "unavailable",
    ]
    assert all(s["status"] == "unavailable" for s in body["drivers"][1]["stints"])
    assert body["drivers"][2]["stints"] == body["drivers"][3]["stints"] == []
    assert [d["unassigned_lap_count"] for d in body["drivers"]] == [2, 0, 1, 0]
    assert all(
        not {"laps", "source_order", "lap_time_ms", "intercept", "predictions"}
        & obj.keys()
        for obj in objects(body)
    )
    loader.assert_called_once_with(*SOURCE)
    analyzer.assert_called_once()
    for seed in range(2):
        stint_field_session.laps = stint_field_session.laps.sample(
            frac=1, random_state=seed
        )
        assert client.get(SESSION_PATH).content == response.content
    assert loader.call_count == analyzer.call_count == 3
    json.dumps(body, allow_nan=False)


@pytest.mark.parametrize(
    "old,new,status",
    [
        ("2025", "bad", 422),
        ("2025", "1949", 422),
        ("italian-grand-prix", "Italian-Grand-Prix", 422),
        ("race", "Race", 422),
        ("2025", "2024", 404),
        ("italian-grand-prix", "monaco-grand-prix", 404),
        ("race", "qualifying", 404),
    ],
)
def test_session_selectors_fail_before_source(
    client, controlled_stint_source, old, new, status
):
    response = client.get(SESSION_PATH.replace(old, new))
    assert response.status_code == status
    if status == 404:
        assert response.json() == {
            "error": {
                "code": "session_not_supported",
                "message": "The requested session is not supported.",
            }
        }
    controlled_stint_source.assert_not_called()


@pytest.mark.parametrize(
    "stage",
    ["load_session", "map_lap_inputs", "map_session_summary", "analyze_session_stints"],
)
@pytest.mark.parametrize("internal", [False, True])
def test_session_route_error_boundary(
    monkeypatch, controlled_stint_source, stage, internal
):
    from fastapi.testclient import TestClient

    from app import stint_analytics
    from app.main import app

    failure = (RuntimeError if internal else f1_data.DataSourceUnavailableError)(
        "private secret path"
    )
    owner = stint_analytics if stage == "analyze_session_stints" else f1_data
    monkeypatch.setattr(owner, stage, Mock(side_effect=failure))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(SESSION_PATH)
    assert response.status_code == (500 if internal else 503)
    assert "private secret path" not in response.text
    if internal:
        assert response.text == "Internal Server Error"
    else:
        assert response.json() == {
            "error": {
                "code": "data_source_unavailable",
                "message": "Formula 1 session data is currently unavailable.",
            }
        }


def test_session_model_reuses_strict_compact_contract(payload):
    from app.stint_models import SessionTireStintAnalysisResponse

    body = {
        key: value for key, value in payload.items() if key not in {"driver", "laps"}
    }
    body["drivers"] = [payload["driver"]]
    result = SessionTireStintAnalysisResponse.model_validate(body)
    with pytest.raises(ValidationError):
        result.drivers = ()
    # The compact root adds no optional fields or evidence at any depth.
    for obj in objects(body):
        obj["laps"] = []
        with pytest.raises(ValidationError):
            SessionTireStintAnalysisResponse.model_validate(body)
        del obj["laps"]
        for key in list(obj):
            value = obj.pop(key)
            with pytest.raises(ValidationError):
                SessionTireStintAnalysisResponse.model_validate(body)
            obj[key] = value
    for target, key, value in [
        (body["context"], "year", True),
        (body["context"]["event"], "round_number", "16"),
        (body["drivers"][0], "unassigned_lap_count", "2"),
        (body["drivers"][0]["driver"], "driver_number", 1),
        (
            body["drivers"][0]["stints"][0],
            "observed_pace_trend_seconds_per_lap",
            float("nan"),
        ),
        (
            body["drivers"][0]["stints"][0],
            "median_absolute_residual_seconds",
            float("inf"),
        ),
        (body["drivers"][0]["stints"][0], "normalized_compound", None),
        (body["drivers"][0]["stints"][1], "observed_pace_trend_seconds_per_lap", 0.0),
    ]:
        original = target[key]
        target[key] = value
        with pytest.raises(ValidationError):
            SessionTireStintAnalysisResponse.model_validate(body)
        target[key] = original
    assert SessionTireStintAnalysisResponse.model_validate(body) == result


@pytest.mark.parametrize(
    "numbers,error",
    [
        ([], None),
        (["1"], None),
        (["1", "4", "10", "27"], None),
        (["1", "4", "10", "10", "27"], "unique"),
        (["27", "10", "4", "1"], "numeric order"),
        (["1", "10", "27", "4"], "numeric order"),
    ],
    ids=["empty", "singleton", "numeric", "duplicate", "reversed", "lexicographic"],
)
def test_session_model_driver_identities_and_order(
    monkeypatch, stint_field_session, numbers, error
):
    from app.stint_models import SessionTireStintAnalysisResponse
    from app.stint_service import load_session_tire_stints

    monkeypatch.setattr(f1_data, "load_session", Mock(return_value=stint_field_session))
    response = load_session_tire_stints(*SOURCE)
    body = response.model_dump(mode="json")
    assert SessionTireStintAnalysisResponse.model_validate(body) == response
    drivers = {driver["driver"]["driver_number"]: driver for driver in body["drivers"]}
    body["drivers"] = [deepcopy(drivers[number]) for number in numbers]
    if error == "unique":
        # Identity uniqueness must not depend on whole-object equality.
        body["drivers"][3]["driver"]["abbreviation"] = "OTHER"
    original = deepcopy(body)
    if error is not None:
        with pytest.raises(ValidationError, match=error):
            SessionTireStintAnalysisResponse.model_validate(body)
    else:
        result = SessionTireStintAnalysisResponse.model_validate(body)
        assert result.model_dump(mode="json") == body
    assert body == original
