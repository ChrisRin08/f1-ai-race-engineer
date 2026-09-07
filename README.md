# F1 AI Race Engineer

A Formula 1 race analysis and strategy platform in development, grounded in real race data, with AI explanations planned for later.

## Goal

Build a production-style portfolio application that analyzes Formula 1 race data, runs deterministic analytics in Python, and presents the results through a FastAPI backend and Next.js dashboard.

## Core Principle

The AI does not invent race calculations.

Deterministic Python analytics and future validated predictive tools calculate the results first. A later AI Race Engineer layer may receive those structured results and explain them in natural language.

```text
Real F1 data -> deterministic Python analytics -> predictive ML when justified -> FastAPI -> Next.js dashboard
```

## Demo v0.1 Target

This week's target is Demo v0.1:

```text
real F1 data -> deterministic Python analytics -> FastAPI -> frontend dashboard
```

The first demo will validate against the 2025 Italian Grand Prix at Monza, Race session. This is a control dataset for proving the vertical slice, not a permanent product limitation. The backend should later support dynamic year, event, and session selection.

## Planned Product Features

Some features below are post-v0.1 and remain deferred until the architecture justifies them.

- Load real Formula 1 race/session data
- Analyze lap times
- Identify fastest laps
- Summarize representative race pace
- Analyze tire compounds and stints
- Display pit stops and race gaps
- Compare two drivers
- Estimate tire degradation
- Identify possible pit windows
- Run basic what-if strategy simulations
- Generate AI race-engineer explanations

## Architecture

This repository is a monorepo:

- `frontend/` will contain the Next.js dashboard.
- `backend/` contains the FastAPI application and deterministic FastF1 loading and mapping; further analytics are planned.
- `docs/` contains product and architecture documentation.

The frontend is responsible for presentation and user interaction. It must not perform authoritative race analytics or strategy calculations.

The backend is the authoritative source for data loading, validation, deterministic analytics, future predictive ML workflows, and API responses.

## Chosen Tooling

### Frontend
- Next.js
- React
- TypeScript
- App Router
- npm

### Backend
- Python 3.12
- FastAPI
- uv
- pytest
- Ruff

### Data / Analytics
- FastF1
- Pandas
- NumPy
- scikit-learn later, when predictive ML work is justified

### Deferred
- PostgreSQL, Supabase, and pgvector
- Amazon Bedrock implementation
- Gemini Live voice interaction
- Authentication
- Docker
- Pit strategy simulation

## Status

Day 2 backend: a Python 3.12 FastAPI service exposes health and session-summary endpoints with Pydantic contracts and deterministic tests. The currently supported control session is the **2025 Italian Grand Prix / Monza / Race**. The summary includes identity, circuit, timing, participants, data availability, and FastF1 provenance.

Real-data integration and live backend API acceptance have passed for this control session. The Next.js dashboard, analytics beyond session summaries, dynamic session coverage, AI/ML, persistence, authentication, deployment, and live telemetry remain deferred.

## Run the Backend

With uv installed and Python 3.12 available, run from the repository root:

```bash
cd backend
uv sync --locked
uv run --frozen --no-sync uvicorn app.main:app --reload
```

Dependency setup may require network access. The API listens at `http://127.0.0.1:8000`:

- `GET /health` returns exactly `{"status":"ok"}` without loading FastF1 data.
- `GET /api/v1/seasons/{year}/events/{event}/sessions/{session}` returns a session summary. The supported path is `/api/v1/seasons/2025/events/italian-grand-prix/sessions/race`.

Malformed path inputs return `422`; well-formed unsupported tuples return `404 session_not_supported`; expected source failures return `503 data_source_unavailable`.

Session requests may contact FastF1 services. The loader creates and enables the ignored repo-local `backend/cache/fastf1/` cache on first data access. Importing the app or checking health does not create it. Summaries identify `source.provider` as `FastF1`; missing data is handled explicitly, without fabricated race facts. Laps are requested; telemetry, weather, and race-control messages are not requested.

## Test the Backend

From `backend/`, after setup, with `F1_RUN_INTEGRATION` unset:

```bash
uv run --offline --frozen --no-sync pytest
uv run --offline --frozen --no-sync ruff format --check .
uv run --offline --frozen --no-sync ruff check --no-cache .
```

Routine tests use controlled data and deselect integration tests. Explicit selection without opt-in safely skips the real test:

```bash
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync pytest -m integration
```

Only when intentionally validating real data with network access, opt in explicitly:

```bash
F1_RUN_INTEGRATION=1 uv run --frozen --no-sync pytest -m integration
```

This invokes the application loader and may download FastF1 data into the ignored cache. It is separate from routine testing.

See the [feature quickstart](specs/001-backend-f1-data-access/quickstart.md), [architecture](docs/architecture.md), and [demo scope](docs/demo-v0.1.md) for details.
