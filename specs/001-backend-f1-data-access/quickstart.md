# Quickstart: Backend Foundation & F1 Data Access

This guide defines the validation path for the completed feature. It does not
authorize implementation or data download during planning.

## Prerequisites

- uv installed
- Python 3.12 available to uv
- Network access for initial dependency setup when needed and intentional real-data validation

All commands below start from the repository root.

## Install the Backend Environment

```bash
cd backend
uv sync --locked
```

Expected result: uv creates or updates `backend/.venv/` from the committed
`backend/uv.lock`. No credentials are required.

## Run Routine Quality Checks

```bash
cd backend
uv run --offline --frozen --no-sync ruff format --check .
uv run --offline --frozen --no-sync ruff check --no-cache .
uv run --offline --frozen --no-sync pytest
```

Expected result: formatting, linting, and routine tests pass without contacting
FastF1. Keep `F1_RUN_INTEGRATION` unset. The default test selection deselects
tests marked `integration`. Explicit selection without opt-in safely skips the
real test:

```bash
cd backend
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync pytest -m integration
```

## Start the API

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Expected result: the service listens locally on `http://127.0.0.1:8000`.

## Validate Backend Availability

```bash
curl --fail --silent http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

This endpoint must remain available without FastF1 or network access.

## Validate the Control Session Through the API

This request may download real session data on first use:

```bash
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race
```

Expected result: HTTP `200` with the shape defined in
[`contracts/openapi.yaml`](contracts/openapi.yaml), including:

- 2025 Italian Grand Prix Race identity
- circuit and scheduled session timing
- participating drivers and teams
- availability statuses for session data categories
- `source.provider` equal to `FastF1`

The loader creates and enables the repo-local `backend/cache/fastf1/` cache on
first data access, even if the subsequent source load fails. Generated cache
content stays under that path, ignored by the `backend/cache/` rule in
`.gitignore`. Application import and health checks do not create the cache.

## Validate Error Boundaries

A well-formed but unsupported request:

```bash
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:8000/api/v1/seasons/2024/events/italian-grand-prix/sessions/race
```

Expected result: HTTP `404` with error code `session_not_supported`.

A malformed request:

```bash
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:8000/api/v1/seasons/not-a-year/events/italian-grand-prix/sessions/race
```

Expected result: HTTP `422` validation response.

## Run Explicit Real-Data Validation

Stop the development server before running the command if desired. This check
is separate from routine tests and may access external services:

```bash
cd backend
F1_RUN_INTEGRATION=1 uv run --frozen --no-sync pytest -m integration
```

Expected result: the control session loads through the application's
`load_session_summary(...)` boundary and satisfies the identity, Monza
circuit/location, participant, results/laps availability, and FastF1 provenance
assertions. A network or upstream outage is reported as an integration failure,
not replaced with fake data.

## Final Repository Check

```bash
git status --short
git check-ignore -v backend/cache/fastf1/
```

Expected result: no cache contents, virtual environment files, credentials, or
other generated data appear as tracked changes.
