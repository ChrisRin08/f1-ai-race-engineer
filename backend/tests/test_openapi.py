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


STINT_PATH = (
    "/api/v1/seasons/{year}/events/{event}/sessions/{session}"
    "/tire-stints/drivers/{driver_number}"
)


def test_driver_stint_operation_contract():
    operation = app.openapi()["paths"][STINT_PATH]["get"]
    assert operation["operationId"] == "getDriverTireStintAnalysis"
    assert set(operation["responses"]) == {"200", "404", "422", "503"}
    parameters = {p["name"]: p for p in operation["parameters"]}
    assert set(parameters) == {"year", "event", "session", "driver_number"}
    assert all(p["required"] and p["in"] == "path" for p in parameters.values())
    assert parameters["year"]["schema"]["minimum"] == 1950
    for name in ("event", "session"):
        assert parameters[name]["schema"]["pattern"] == r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    assert parameters["driver_number"]["schema"]["pattern"] == r"^[1-9][0-9]*$"
    for code, name in [
        ("200", "DriverTireStintAnalysisResponse"),
        ("404", "ErrorResponse"),
        ("422", "HTTPValidationError"),
        ("503", "ErrorResponse"),
    ]:
        assert (
            operation["responses"][code]["content"]["application/json"]["schema"][
                "$ref"
            ]
            == "#/components/schemas/" + name
        )


@pytest.mark.parametrize(
    "name",
    [
        "ObservedTireStintPolicy",
        "ObservationalLimitations",
        "PositiveIntegerRange",
        "StintExclusionCounts",
        "StintSample",
        "ObservedStintSummary",
        "DriverTireStintSummary",
        "TireStintLapEvidence",
        "DriverTireStintAnalysisResponse",
    ],
)
def test_driver_stint_schemas_strict_required(name):
    schema = app.openapi()["components"]["schemas"][name]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


def test_driver_stint_required_nullable_and_metric_bounds():
    schemas = app.openapi()["components"]["schemas"]
    for name, fields in {
        "ObservedStintSummary": (
            "reported_compound",
            "normalized_compound",
            "lap_range",
            "reported_tire_age_range",
            "eligible_tire_age_range",
            "unavailability_reason",
            "observed_pace_trend_seconds_per_lap",
            "median_absolute_residual_seconds",
        ),
        "TireStintLapEvidence": (
            "lap_number",
            "lap_time_ms",
            "reported_stint",
            "reported_compound",
            "reported_tire_age",
            "track_status_codes",
            "is_accurate",
            "provider_generated",
            "primary_exclusion_reason",
            "unassigned_reason",
        ),
    }.items():
        for field in fields:
            assert field in schemas[name]["required"]
            assert {"type": "null"} in schemas[name]["properties"][field]["anyOf"]
    fields = schemas["ObservedStintSummary"]["properties"]
    for metric in (
        "observed_pace_trend_seconds_per_lap",
        "median_absolute_residual_seconds",
    ):
        number = next(
            item for item in fields[metric]["anyOf"] if item.get("type") == "number"
        )
        assert number["multipleOf"] == 0.001
        if metric == "median_absolute_residual_seconds":
            assert number["minimum"] == 0
        else:
            assert (
                not {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}
                & number.keys()
            )
    assert "source_order" not in schemas["TireStintLapEvidence"]["properties"]
    assert "trusted" in fields["normalized_compound"]["description"].lower()
    assert "audit" in fields["reported_compound"]["description"].lower()


def test_stint_policy_openapi_discloses_estimator_and_exclusion_sequence():
    policy = app.openapi()["components"]["schemas"]["ObservedTireStintPolicy"]
    fields = policy["properties"]
    for name, const in {
        "policy_id": "observed-tire-stint-pace-trend-v1",
        "metric": "observed_pace_trend_seconds_per_lap",
        "estimator": "theil_sen",
        "intercept_method": "joint",
        "tire_age_axis": "reported_tire_age_laps",
        "trend_unit": "seconds_per_lap_of_reported_tire_age",
        "residual_unit": "seconds",
        "minimum_eligible_observations": 6,
        "minimum_distinct_tire_ages": 6,
        "publication_decimal_places": 3,
        "rounding": "half_up",
    }.items():
        assert fields[name]["const"] == const
    exclusions = fields["lap_exclusion_precedence"]
    assert exclusions["minItems"] == exclusions["maxItems"] == 8
    assert [item["const"] for item in exclusions["prefixItems"]] == [
        "invalid_timing",
        "lap_one_start",
        "pit_in",
        "pit_out",
        "disrupted_status",
        "explicitly_inaccurate",
        "provider_generated",
        "unusable_tire_age",
    ]


def test_stint_policy_openapi_tiers_keep_the_compound_pair_unordered():
    tiers = app.openapi()["components"]["schemas"]["ObservedTireStintPolicy"][
        "properties"
    ]["availability_precedence"]
    assert tiers["minItems"] == tiers["maxItems"] == 6
    compound = tiers["prefixItems"][2]
    single = tiers["prefixItems"][:2] + tiers["prefixItems"][3:]
    assert [tier["prefixItems"][0]["const"] for tier in single] == [
        "inconsistent_stint_metadata",
        "wet_weather_compound",
        "inconsistent_tire_age",
        "missing_tire_age",
        "insufficient_eligible_sample",
    ]
    assert all(tier["minItems"] == tier["maxItems"] == 1 for tier in single)
    # The shared tier must stay a set: membership only, never positional consts.
    assert "prefixItems" not in compound
    assert compound["minItems"] == compound["maxItems"] == 2
    assert compound["uniqueItems"] is True
    assert set(compound["items"]["enum"]) == {
        "missing_compound",
        "unsupported_compound",
    }
    assert {rule["contains"]["const"] for rule in compound["allOf"]} == set(
        compound["items"]["enum"]
    )


@pytest.mark.parametrize(
    "name,members",
    [
        (
            "StintUnavailabilityReason",
            (
                "inconsistent_stint_metadata",
                "wet_weather_compound",
                "missing_compound",
                "unsupported_compound",
                "inconsistent_tire_age",
                "missing_tire_age",
                "insufficient_eligible_sample",
            ),
        ),
        (
            "StintLapExclusionReason",
            (
                "invalid_timing",
                "lap_one_start",
                "pit_in",
                "pit_out",
                "disrupted_status",
                "explicitly_inaccurate",
                "provider_generated",
                "unusable_tire_age",
            ),
        ),
        ("UnassignedLapReason", ("missing_stint_metadata",)),
        ("StintAnalysisStatus", ("available", "unavailable")),
        ("StintLapDisposition", ("eligible", "excluded", "unassigned")),
        ("NormalizedTireCompound", ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")),
    ],
)
def test_stint_openapi_reason_enums_are_exact(name, members):
    schema = app.openapi()["components"]["schemas"][name]
    assert schema["type"] == "string"
    assert tuple(schema["enum"]) == members


def test_stint_limitation_openapi_schema_is_fixed_and_non_causal():
    schema = app.openapi()["components"]["schemas"]["ObservationalLimitations"]
    fields = schema["properties"]
    assert schema["additionalProperties"] is False
    assert (
        set(schema["required"])
        == set(fields)
        == {
            "interpretation",
            "isolated_physical_tire_wear",
            "unadjusted_for",
            "description",
        }
    )
    assert fields["interpretation"]["const"] == "observational_association"
    assert fields["isolated_physical_tire_wear"]["const"] is False
    limitations = fields["unadjusted_for"]
    assert limitations["minItems"] == limitations["maxItems"] == 6
    assert limitations["uniqueItems"] is True
    assert limitations["items"]["enum"] == [
        "fuel_load_or_burn",
        "traffic",
        "track_evolution",
        "driver_tire_management",
        "changing_environmental_conditions",
        "other_unmodeled_race_effects",
    ]
    assert fields["description"]["const"] == (
        "This observed pace trend is an unadjusted association and is not an "
        "estimate of isolated physical tire wear."
    )


def test_driver_stints_preserve_inherited_openapi_components():
    from fastapi.openapi.utils import get_openapi

    inherited = get_openapi(
        title=app.title,
        version=app.version,
        routes=[route for route in app.routes if "tire-stints" not in route.path],
    )
    generated = app.openapi()
    for name, schema in inherited["components"]["schemas"].items():
        assert generated["components"]["schemas"][name] == schema
    for path, operations in inherited["paths"].items():
        assert generated["paths"][path] == operations


@pytest.mark.parametrize("year,valid", [(2025, True), (True, False), ("2025", False)])
def test_shared_context_year_requires_integer(session_summary_fixture, year, valid):
    from app.pace_models import AnalyticsSessionContext

    context = {
        key: session_summary_fixture[key]
        for key in ("year", "event", "session", "circuit")
    }
    context["year"] = year
    if valid:
        assert AnalyticsSessionContext.model_validate(context).year == year
    else:
        with pytest.raises(ValidationError):
            AnalyticsSessionContext.model_validate(context)


@pytest.mark.parametrize(
    "number,valid",
    [
        (16, True),
        (1, True),
        (None, True),
        (True, False),
        ("16", False),
        (0, False),
        (-1, False),
    ],
)
def test_shared_event_round_requires_positive_integer_or_null(
    session_summary_fixture, number, valid
):
    from app.models import EventSummary

    event = dict(session_summary_fixture["event"], round_number=number)
    if valid:
        assert EventSummary.model_validate(event).round_number == number
    else:
        with pytest.raises(ValidationError):
            EventSummary.model_validate(event)


def test_shared_context_integer_openapi_shapes_are_preserved():
    schemas = app.openapi()["components"]["schemas"]
    assert schemas["AnalyticsSessionContext"]["properties"]["year"] == {
        "title": "Year",
        "type": "integer",
    }
    assert schemas["EventSummary"]["properties"]["round_number"] == {
        "title": "Round Number",
        "anyOf": [{"type": "integer", "exclusiveMinimum": 0}, {"type": "null"}],
    }


SESSION_STINT_PATH = STINT_PATH.split("/drivers/")[0]


def test_session_stint_operation_contract():
    schema = app.openapi()
    operation = schema["paths"][SESSION_STINT_PATH]["get"]
    assert operation["operationId"] == "getSessionTireStintAnalysis"
    assert set(operation["responses"]) == {"200", "404", "422", "503"}
    parameters = {p["name"]: p for p in operation["parameters"]}
    assert set(parameters) == {"year", "event", "session"}
    driver_parameters = schema["paths"][STINT_PATH]["get"]["parameters"]
    assert operation["parameters"] == [
        p for p in driver_parameters if p["name"] != "driver_number"
    ]
    for code, name in [
        ("200", "SessionTireStintAnalysisResponse"),
        ("404", "ErrorResponse"),
        ("422", "HTTPValidationError"),
        ("503", "ErrorResponse"),
    ]:
        assert operation["responses"][code]["content"]["application/json"][
            "schema"
        ] == {"$ref": "#/components/schemas/" + name}


def test_session_stint_schema_is_compact_and_reuses_driver_summary():
    schemas = app.openapi()["components"]["schemas"]
    root = schemas["SessionTireStintAnalysisResponse"]
    assert root["additionalProperties"] is False
    assert (
        set(root["required"])
        == set(root["properties"])
        == {"context", "policy", "limitations", "drivers", "source"}
    )
    assert root["properties"]["drivers"]["type"] == "array"
    assert root["properties"]["drivers"]["items"] == {
        "$ref": "#/components/schemas/DriverTireStintSummary"
    }
    for key in ("context", "policy", "limitations", "source"):
        assert (
            root["properties"][key]
            == schemas["DriverTireStintAnalysisResponse"]["properties"][key]
        )
    # Walk every reachable public schema; full lap evidence is not in this graph.
    pending = ["SessionTireStintAnalysisResponse"]
    visited = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        current = schemas[name]
        if current.get("type") == "object":
            assert current["additionalProperties"] is False
            assert set(current["required"]) == set(current["properties"])
            assert not {"laps", "source_order"} & current["properties"].keys()

        def references(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    yield value["$ref"].split("/")[-1]
                for child in value.values():
                    yield from references(child)
            elif isinstance(value, list):
                for child in value:
                    yield from references(child)

        pending.extend(references(current))
    assert "TireStintLapEvidence" not in visited
    assert {
        "ObservedStintSummary",
        "StintSample",
        "StintExclusionCounts",
        "PositiveIntegerRange",
    } <= visited


def test_session_stints_preserve_all_existing_routes_and_schemas():
    from fastapi.openapi.utils import get_openapi

    prior = get_openapi(
        title=app.title,
        version=app.version,
        routes=[r for r in app.routes if r.path != SESSION_STINT_PATH],
    )
    generated = app.openapi()
    assert generated["paths"].keys() - prior["paths"].keys() == {SESSION_STINT_PATH}
    for path, operation in prior["paths"].items():
        assert generated["paths"][path] == operation
    for name, schema in prior["components"]["schemas"].items():
        assert generated["components"]["schemas"][name] == schema
