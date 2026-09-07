# Implementation Plan: Backend Foundation & F1 Data Access

**Branch**: `001-backend-f1-data-access` | **Date**: 2026-09-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-backend-f1-data-access/spec.md`

## Summary

Create the smallest testable Python 3.12 FastAPI service that exposes a
deterministic health response and a session-summary resource backed by FastF1.
The first supported request is the 2025 Italian Grand Prix Race control
session. API tests use controlled doubles, while a separately invoked
integration check proves the real FastF1 path without making routine tests
network-dependent.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, Uvicorn, FastF1; Pydantic through FastAPI

**Storage**: No application persistence; ignored FastF1 disk cache at
`backend/cache/fastf1/`

**Testing**: pytest and FastAPI `TestClient`/HTTPX; a separately selected
FastF1 integration test for the control session

**Target Platform**: Local macOS/Linux development, with a portable ASGI
service suitable for later Linux deployment

**Project Type**: Backend web service within the existing monorepo

**Performance Goals**: Health response available within 5 seconds after service
startup; no latency target for a cold external session load in this feature

**Constraints**: Deterministic source-backed values; no LLM, database,
frontend, ML, strategy simulation, Docker, cloud deployment, or live telemetry;
routine tests must not require network access

**Scale/Scope**: Two GET endpoints, one guaranteed control session, session
identity/timing/circuit/participants/data-availability metadata only

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Gate | Result |
|---|---|---|
| Deterministic Analytics Before AI | All returned F1 facts map from FastF1; no generated numerical facts | Pass |
| Real Data and Provenance | Responses identify FastF1 and expose source failures explicitly | Pass |
| Testable, Verifiable Engineering | Health, request validation, mapping, and error behavior have planned automated coverage | Pass |
| Incremental Complexity | One application package and one data-access boundary; no deferred infrastructure | Pass |
| Explainability and Learning | Direct request-to-adapter-to-response flow with documented contracts | Pass |
| Security and Configuration Hygiene | No secrets or service credentials; generated cache remains ignored | Pass |
| Quality Over Token/Speed Optimization | Locked dependencies plus lint, format, and test gates are planned | Pass |
| Spec-Driven Feature Development | Clarified spec drives this plan and its Phase 0/1 artifacts | Pass |

Post-design re-check: the data model, OpenAPI contract, and quickstart preserve
all gates. No exception or complexity waiver is required.

## Project Structure

### Documentation (this feature)

```text
specs/001-backend-f1-data-access/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
└── tasks.md                 # Created later by $speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── .python-version
├── pyproject.toml
├── uv.lock
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, routes, and HTTP error mapping
│   ├── models.py            # API response models
│   └── f1_data.py           # FastF1 loading and deterministic mapping
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_sessions.py
    ├── test_f1_data.py
    └── test_f1_data_integration.py

backend/cache/fastf1/        # Created at runtime and ignored by Git
```

**Structure Decision**: Keep the backend as one small application package.
`main.py` owns HTTP concerns, `models.py` owns the public response shape, and
`f1_data.py` isolates FastF1 calls and source-to-domain mapping. This is enough
separation for deterministic tests without introducing repositories, layered
service classes, or configuration frameworks before they are needed.

## Design Decisions

- Expose `GET /health` and
  `GET /api/v1/seasons/{year}/events/{event}/sessions/{session}`.
- Use the canonical control path
  `/api/v1/seasons/2025/events/italian-grand-prix/sessions/race` while mapping
  it internally to FastF1's event and session identifiers.
- Reject malformed path values through FastAPI validation, return `404` for a
  well-formed request outside the supported control scope, and return `503`
  for a supported request that cannot be served because FastF1 is unavailable
  or lacks required data.
- Load session information, results, and laps for the summary; do not request
  telemetry, weather, or race-control messages in this feature.
- Return only JSON-native, explicitly modeled values. Preserve null for an
  optional source field that is absent; never infer or fabricate it.
- Keep the session route synchronous so FastAPI executes blocking FastF1 work
  outside the event loop. Do not add background jobs or an in-memory cache.
- Derive `backend/cache/fastf1/` from the backend project location, create it
  when data access is first used, and enable FastF1's disk cache there.

## Verification Strategy

Routine verification:

```text
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

The default pytest selection excludes tests marked `integration`. Unit/API
tests cover the exact health payload, control request success through a test
double, deterministic field mapping, malformed and unsupported inputs, and
source-unavailable error mapping.

Real-data verification is explicit because it may download data and depends on
external services:

```text
F1_RUN_INTEGRATION=1 uv run --frozen --no-sync pytest -m integration
```

## Complexity Tracking

No constitution violations require justification.
