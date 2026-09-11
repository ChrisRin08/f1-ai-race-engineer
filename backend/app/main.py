from typing import Annotated

from fastapi import FastAPI, Path
from fastapi.responses import JSONResponse

from app.f1_data import DataSourceUnavailableError, load_session_summary
from app.models import ErrorDetail, ErrorResponse, HealthResponse, SessionSummary
from app.pace_models import (
    DRIVER_NUMBER_PATTERN,
    DriverPaceAnalysisResponse,
    DriverPaceComparisonResponse,
    SessionPaceAnalysisResponse,
)
from app.pace_service import (
    DriverNotFoundError,
    load_driver_pace,
    load_pace_comparison,
    load_session_pace,
)

app = FastAPI(title="F1 AI Race Engineer Backend", version="0.1.0")

_SESSION_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_SUPPORTED_SESSIONS = {
    (2025, "italian-grand-prix", "race"): (2025, "Italian Grand Prix", "Race")
}


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
    source_identifiers = _SUPPORTED_SESSIONS.get((year, event, session))
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
    source_identifiers = _SUPPORTED_SESSIONS.get((year, event, session))
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
    source_identifiers = _SUPPORTED_SESSIONS.get((year, event, session))
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
    source_identifiers = _SUPPORTED_SESSIONS.get((year, event, session))
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


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    error = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=error.model_dump())
