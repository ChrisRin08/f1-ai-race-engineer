from typing import Annotated

from fastapi import FastAPI, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.data.f1_data import DataSourceUnavailableError, load_session_summary
from app.models.pace_models import (
    DRIVER_NUMBER_PATTERN,
    DriverPaceAnalysisResponse,
    DriverPaceComparisonResponse,
    SessionPaceAnalysisResponse,
)
from app.models.race_context_models import (
    DriverRaceContextResponse,
    SessionRaceContextResponse,
)
from app.models.session_models import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    SessionSummary,
)
from app.models.stint_models import (
    DriverTireStintAnalysisResponse,
    SessionTireStintAnalysisResponse,
)
from app.services.pace_service import (
    DriverNotFoundError,
    load_driver_pace,
    load_pace_comparison,
    load_session_pace,
)
from app.services.race_context_service import (
    SessionNotSupportedError,
    load_driver_race_context,
    load_session_race_context,
)
from app.services.session_support import resolve_supported_session
from app.services.stint_service import load_driver_tire_stints, load_session_tire_stints

app = FastAPI(title="F1 AI Race Engineer Backend", version="0.1.0")

_SESSION_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


@app.get("/health", response_model=HealthResponse, operation_id="getHealth")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get(
    "/api/v1/seasons/{year}/events/{event}/sessions/{session}",
    response_model=SessionSummary,
    operation_id="getSessionSummary",
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_session_summary(
    year: Annotated[int, Path(ge=1950)],
    event: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    session: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
) -> SessionSummary | JSONResponse:
    source_identifiers = resolve_supported_session(year, event, session)
    if source_identifiers is None:
        return _error_response(
            status_code=404,
            code="session_not_supported",
            message="The requested session is not supported.",
        )

    try:
        return load_session_summary(*source_identifiers)
    except DataSourceUnavailableError:
        return _error_response(
            status_code=503,
            code="data_source_unavailable",
            message="Formula 1 session data is currently unavailable.",
        )


@app.get(
    "/api/v1/seasons/{year}/events/{event}/sessions/{session}/pace/drivers/{driver_number}",
    response_model=DriverPaceAnalysisResponse,
    operation_id="getDriverPaceAnalysis",
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_driver_pace(
    year: Annotated[int, Path(ge=1950)],
    event: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    session: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    driver_number: Annotated[str, Path(pattern=DRIVER_NUMBER_PATTERN)],
) -> DriverPaceAnalysisResponse | JSONResponse:
    source_identifiers = resolve_supported_session(year, event, session)
    if source_identifiers is None:
        return _error_response(
            status_code=404,
            code="session_not_supported",
            message="The requested session is not supported.",
        )
    try:
        return load_driver_pace(*source_identifiers, driver_number)
    except DriverNotFoundError:
        return _error_response(
            status_code=404,
            code="driver_not_found",
            message="The requested driver is not in the session results.",
        )
    except DataSourceUnavailableError:
        return _error_response(
            status_code=503,
            code="data_source_unavailable",
            message="Formula 1 session data is currently unavailable.",
        )


@app.get(
    "/api/v1/seasons/{year}/events/{event}/sessions/{session}"
    "/pace/drivers/{driver_a}/comparisons/{driver_b}",
    response_model=DriverPaceComparisonResponse,
    operation_id="compareDriverPace",
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def compare_driver_pace(
    year: Annotated[int, Path(ge=1950)],
    event: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    session: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    driver_a: Annotated[str, Path(pattern=DRIVER_NUMBER_PATTERN)],
    driver_b: Annotated[str, Path(pattern=DRIVER_NUMBER_PATTERN)],
) -> DriverPaceComparisonResponse | JSONResponse:
    source_identifiers = resolve_supported_session(year, event, session)
    if source_identifiers is None:
        return _error_response(
            status_code=404,
            code="session_not_supported",
            message="The requested session is not supported.",
        )
    try:
        return load_pace_comparison(*source_identifiers, driver_a, driver_b)
    except DriverNotFoundError:
        return _error_response(
            status_code=404,
            code="driver_not_found",
            message="The requested driver is not in the session results.",
        )
    except DataSourceUnavailableError:
        return _error_response(
            status_code=503,
            code="data_source_unavailable",
            message="Formula 1 session data is currently unavailable.",
        )


@app.get(
    "/api/v1/seasons/{year}/events/{event}/sessions/{session}/pace",
    response_model=SessionPaceAnalysisResponse,
    operation_id="getSessionPaceAnalysis",
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_session_pace(
    year: Annotated[int, Path(ge=1950)],
    event: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    session: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
) -> SessionPaceAnalysisResponse | JSONResponse:
    source_identifiers = resolve_supported_session(year, event, session)
    if source_identifiers is None:
        return _error_response(
            status_code=404,
            code="session_not_supported",
            message="The requested session is not supported.",
        )
    try:
        return load_session_pace(*source_identifiers)
    except DataSourceUnavailableError:
        return _error_response(
            status_code=503,
            code="data_source_unavailable",
            message="Formula 1 session data is currently unavailable.",
        )


@app.get(
    "/api/v1/seasons/{year}/events/{event}/sessions/{session}"
    "/tire-stints/drivers/{driver_number}",
    response_model=DriverTireStintAnalysisResponse,
    operation_id="getDriverTireStintAnalysis",
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_driver_tire_stints(
    year: Annotated[int, Path(ge=1950)],
    event: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    session: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    driver_number: Annotated[str, Path(pattern=DRIVER_NUMBER_PATTERN)],
) -> DriverTireStintAnalysisResponse | JSONResponse:
    source_identifiers = resolve_supported_session(year, event, session)
    if source_identifiers is None:
        return _error_response(
            status_code=404,
            code="session_not_supported",
            message="The requested session is not supported.",
        )
    try:
        return load_driver_tire_stints(*source_identifiers, driver_number)
    except DriverNotFoundError:
        return _error_response(
            status_code=404,
            code="driver_not_found",
            message="The requested driver is not in the session results.",
        )
    except DataSourceUnavailableError:
        return _error_response(
            status_code=503,
            code="data_source_unavailable",
            message="Formula 1 session data is currently unavailable.",
        )


@app.get(
    "/api/v1/seasons/{year}/events/{event}/sessions/{session}/tire-stints",
    response_model=SessionTireStintAnalysisResponse,
    operation_id="getSessionTireStintAnalysis",
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
def get_session_tire_stints(
    year: Annotated[int, Path(ge=1950)],
    event: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    session: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
) -> SessionTireStintAnalysisResponse | JSONResponse:
    source_identifiers = resolve_supported_session(year, event, session)
    if source_identifiers is None:
        return _error_response(
            status_code=404,
            code="session_not_supported",
            message="The requested session is not supported.",
        )
    try:
        return load_session_tire_stints(*source_identifiers)
    except DataSourceUnavailableError:
        return _error_response(
            status_code=503,
            code="data_source_unavailable",
            message="Formula 1 session data is currently unavailable.",
        )


@app.get(
    "/api/v1/seasons/{year}/events/{event}/sessions/{session}/race-context",
    response_model=SessionRaceContextResponse,
    operation_id="getSessionRaceContext",
    summary="Get compact pit-lane and lap-boundary context for the session field",
    description=(
        "Projects exactly one compact entry per authoritative participant from "
        "one central race-context analysis. Complete lap-context and pit-evidence "
        "collections are intentionally omitted."
    ),
    responses={
        200: {
            "description": (
                "Canonically ordered compact participant context from one loaded "
                "and normalized session snapshot."
            )
        },
        404: {
            "model": ErrorResponse,
            "description": "The well-formed session tuple is not supported.",
        },
        422: {
            "description": "One or more path parameters are malformed.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
                }
            },
        },
        503: {
            "model": ErrorResponse,
            "description": "The supported session cannot be served from FastF1.",
        },
    },
)
def get_session_race_context(
    year: Annotated[int, Path(ge=1950)],
    event: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    session: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
) -> SessionRaceContextResponse | JSONResponse:
    try:
        return SessionRaceContextResponse.model_validate(
            _race_context_response_input(
                load_session_race_context(year, event, session)
            )
        )
    except SessionNotSupportedError:
        return _error_response(
            status_code=404,
            code="session_not_supported",
            message="The requested session is not supported.",
        )
    except DataSourceUnavailableError:
        return _error_response(
            status_code=503,
            code="data_source_unavailable",
            message="Formula 1 session data is currently unavailable.",
        )


@app.get(
    "/api/v1/seasons/{year}/events/{event}/sessions/{session}"
    "/race-context/drivers/{driver_number}",
    response_model=DriverRaceContextResponse,
    operation_id="getDriverRaceContext",
    summary="Get one driver's auditable pit-lane and lap-boundary context",
    description=(
        "Projects the participant summary, complete compact normalized lap "
        "series, and all pit evidence from the same central analysis used by the "
        "session resource. This is not a live-gap or telemetry resource."
    ),
    responses={
        200: {
            "description": (
                "One authoritative participant's complete auditable race-context "
                "projection from one loaded and normalized session snapshot."
            )
        },
        404: {
            "model": ErrorResponse,
            "description": (
                "The session is unsupported or the driver is not in its results."
            ),
        },
        422: {
            "description": "One or more path parameters are malformed.",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
                }
            },
        },
        503: {
            "model": ErrorResponse,
            "description": "The supported session cannot be served from FastF1.",
        },
    },
)
def get_driver_race_context(
    year: Annotated[int, Path(ge=1950)],
    event: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    session: Annotated[str, Path(pattern=_SESSION_SLUG_PATTERN)],
    driver_number: Annotated[str, Path(pattern=DRIVER_NUMBER_PATTERN)],
) -> DriverRaceContextResponse | JSONResponse:
    try:
        return DriverRaceContextResponse.model_validate(
            _race_context_response_input(
                load_driver_race_context(year, event, session, driver_number)
            )
        )
    except SessionNotSupportedError:
        return _error_response(
            status_code=404,
            code="session_not_supported",
            message="The requested session is not supported.",
        )
    except DriverNotFoundError:
        return _error_response(
            status_code=404,
            code="driver_not_found",
            message="The requested driver is not in the session results.",
        )
    except DataSourceUnavailableError:
        return _error_response(
            status_code=503,
            code="data_source_unavailable",
            message="Formula 1 session data is currently unavailable.",
        )


def _race_context_response_input(value: object) -> object:
    # Preserve even undeclared model_copy updates so fresh validation rejects them.
    # model_dump can silently omit such fields from nested model instances.
    if isinstance(value, BaseModel):
        return _race_context_response_input(vars(value) | (value.model_extra or {}))
    if isinstance(value, dict):
        return {key: _race_context_response_input(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_race_context_response_input(item) for item in value)
    if isinstance(value, list):
        return [_race_context_response_input(item) for item in value]
    return value


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    error = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=error.model_dump())
