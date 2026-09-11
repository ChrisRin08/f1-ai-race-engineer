import json

import pytest
from pydantic import ValidationError

from app.main import app
from app.models import HealthResponse


@pytest.mark.parametrize(
    ("path", "operation_id"),
    [
        ("/health", "getHealth"),
        (
            "/api/v1/seasons/{year}/events/{event}/sessions/{session}",
            "getSessionSummary",
        ),
    ],
)
def test_openapi_operation_ids(path: str, operation_id: str) -> None:
    schema = app.openapi()

    assert schema["paths"][path]["get"]["operationId"] == operation_id


def test_openapi_health_response_forbids_additional_properties() -> None:
    schema = app.openapi()
    health_schema = schema["components"]["schemas"]["HealthResponse"]

    assert health_schema["additionalProperties"] is False


def test_health_response_rejects_unexpected_property() -> None:
    with pytest.raises(ValidationError):
        HealthResponse.model_validate({"status": "ok", "unexpected": True})


def test_health_response_serializes_valid_payload() -> None:
    response = HealthResponse(status="ok")

    assert json.loads(response.model_dump_json()) == {"status": "ok"}


PACE_PATH = (
    "/api/v1/seasons/{year}/events/{event}/sessions/{session}"
    "/pace/drivers/{driver_number}"
)


@pytest.mark.parametrize(
    "suffix,operation_id,response_name,selectors",
    [
        (
            "/pace/drivers/{driver_a}/comparisons/{driver_b}",
            "compareDriverPace",
            "DriverPaceComparisonResponse",
            ("driver_a", "driver_b"),
        ),
        ("/pace", "getSessionPaceAnalysis", "SessionPaceAnalysisResponse", ()),
    ],
)
def test_remaining_pace_resources(suffix, operation_id, response_name, selectors):
    base = "/api/v1/seasons/{year}/events/{event}/sessions/{session}"
    operation = app.openapi()["paths"][base + suffix]["get"]
    assert operation["operationId"] == operation_id
    parameters = {p["name"]: p for p in operation["parameters"]}
    assert set(parameters) == {"year", "event", "session", *selectors}
    for name in selectors:
        assert parameters[name]["schema"]["pattern"] == r"^[1-9][0-9]*$"
        assert parameters[name]["required"] and parameters[name]["in"] == "path"
    for status, name in (
        ("200", response_name),
        ("404", "ErrorResponse"),
        ("422", "HTTPValidationError"),
        ("503", "ErrorResponse"),
    ):
        assert operation["responses"][status]["content"]["application/json"]["schema"][
            "$ref"
        ].endswith("/" + name)


def test_comparison_delta_schema_is_signed_and_nullable():
    fields = app.openapi()["components"]["schemas"]["DriverPaceComparisonResult"][
        "properties"
    ]
    for name in ("delta_ms", "outcome", "faster_driver_number"):
        schema = fields[name]
        assert "null" in schema.get("type", []) or any(
            branch.get("type") == "null" for branch in schema.get("anyOf", [])
        )
    integer = next(
        branch
        for branch in fields["delta_ms"]["anyOf"]
        if branch.get("type") == "integer"
    )
    assert (
        not {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}
        & integer.keys()
    )


def test_driver_pace_openapi_operation_and_parameters():
    operation = app.openapi()["paths"][PACE_PATH]["get"]
    assert operation["operationId"] == "getDriverPaceAnalysis"
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert set(parameters) == {"year", "event", "session", "driver_number"}
    assert all(p["required"] and p["in"] == "path" for p in parameters.values())
    assert parameters["driver_number"]["schema"]["pattern"] == r"^[1-9][0-9]*$"
    assert parameters["year"]["schema"]["minimum"] == 1950
    for status, model in (
        ("200", "DriverPaceAnalysisResponse"),
        ("404", "ErrorResponse"),
        ("422", "HTTPValidationError"),
        ("503", "ErrorResponse"),
    ):
        schema = operation["responses"][status]["content"]["application/json"]["schema"]
        assert schema["$ref"].split("/")[-1] == model


@pytest.mark.parametrize(
    "name",
    [
        "AnalyticsSessionContext",
        "AnalyticsDriverIdentity",
        "RepresentativeRacePacePolicy",
        "LapClassification",
        "ExclusionCounts",
        "LapSample",
        "PaceMetrics",
        "DriverPaceSummary",
        "DriverPaceAnalysisResponse",
        "DriverPaceComparisonResult",
        "DriverPaceComparisonResponse",
        "SessionPaceAnalysisResponse",
    ],
)
def test_analytics_openapi_objects_are_strict_and_fields_required(name):
    schema = app.openapi()["components"]["schemas"][name]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_analytics_openapi_policy_and_nullable_metrics():
    schemas = app.openapi()["components"]["schemas"]
    policy = schemas["RepresentativeRacePacePolicy"]["properties"]
    assert policy["policy_id"]["const"] == "representative-race-pace-v1"
    assert policy["timing_unit"]["const"] == "milliseconds"
    assert policy["rounding"]["const"] == "half_up"
    assert policy["minimum_representative_laps"]["const"] == 5
    assert policy["anomalous_pace_threshold_percent"]["const"] == 120
    assert policy["track_conditions_adjusted"]["const"] is False
    assert policy["is_accurate_used_for_exclusion"]["const"] is False
    assert [
        item["const"] for item in policy["exclusion_precedence"]["prefixItems"]
    ] == [
        "invalid_timing",
        "lap_one_start",
        "pit_in",
        "pit_out",
        "disrupted_status",
        "anomalous_pace",
    ]
    for field in ("metrics", "rank", "tied", "delta_to_best_ms"):
        value = schemas["DriverPaceSummary"]["properties"][field]
        types = value.get("type", [])
        assert "null" in types or any(
            branch.get("type") == "null" for branch in value.get("anyOf", [])
        )
    for name, value in schemas["PaceMetrics"]["properties"].items():
        assert value["type"] == "integer"
        assert value["minimum"] == (
            0 if name == "population_standard_deviation_ms" else 1
        )
