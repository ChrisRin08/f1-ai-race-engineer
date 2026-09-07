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
