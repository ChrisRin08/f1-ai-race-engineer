# Quickstart: Backend Foundation & F1 Data Access

This guide defines the validation path for the completed feature. It does not
authorize implementation or data download during planning.

## Prerequisites

- uv installed
- Python 3.12 available to uv
- Network access only for the explicit real-data validation

All commands below start from the repository root.

## Install the Backend Environment

```bash
cd backend
uv sync
```

Expected result: uv creates or updates `backend/.venv/` from the committed
`backend/uv.lock`. No credentials are required.

## Run Routine Quality Checks

```bash
cd backend
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Expected result: formatting, linting, and routine tests pass without contacting
FastF1. The default test selection excludes the `integration` marker.

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

The first successful load creates generated cache content under
`backend/cache/fastf1/`. That directory must remain ignored by Git.

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
uv run pytest -m integration
```

Expected result: the control session loads through FastF1 and satisfies the
minimum identity, participant, timing, and provenance assertions. A network or
upstream outage is reported as an integration failure, not replaced with fake
data.

## Final Repository Check

```bash
git status --short
git check-ignore -v backend/cache/fastf1/
```

Expected result: no cache contents, virtual environment files, credentials, or
other generated data appear as tracked changes.
