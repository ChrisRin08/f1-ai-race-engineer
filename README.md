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
- `backend/` contains the FastAPI application, FastF1 loading/mapping, and deterministic lap/pace analytics.
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

The Python 3.12 backend exposes health, session summaries, individual lap/pace evidence, session pace ranking, and directional driver comparison with strict Pydantic contracts. The currently supported control session is the **2025 Italian Grand Prix / Monza / Race**.

The session-summary foundation and lap/pace analytics have passed controlled offline coverage and separately opted-in Monza real-data acceptance. The Next.js dashboard, dynamic session coverage, AI/ML, persistence, authentication, deployment, and live telemetry remain deferred.

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

Under that session path:

- `GET .../pace` returns every participant's pace summary in ranked order.
- `GET .../pace/drivers/{driver_number}` returns one summary and all its classified lap evidence.
- `GET .../pace/drivers/{driver_a}/comparisons/{driver_b}` compares two drivers from the same field analysis. Canonical driver numbers (for example `1`, not `01` or `VER`) are the public selectors.

Malformed path inputs return `422`; well-formed unsupported tuples return `404 session_not_supported`; expected source failures return `503 data_source_unavailable`.

Unknown drivers return `404 driver_not_found` after source-backed analysis. Known drivers with insufficient samples return `200` with explicit null metrics/rank/delta; unexpected internal failures remain `500`.

## Representative Race Pace

Policy `representative-race-pace-v1` classifies each source lap once, using this primary exclusion order: invalid timing identity, Lap 1, pit-in, pit-out, disruptive track status, then anomalous pace. Usable timing requires an integral positive lap number and a duration of at least 500,000 ns. Yellow, Safety Car, red flag, VSC, and VSC-ending code presence excludes a lap, including multi-code TrackStatus values.

After structural/status exclusions, laps strictly above 120% of that driver's fastest remaining lap are anomalous. This is a conservative v1 heuristic, not a universal racing standard. IsAccurate and Compound are diagnostic-only. The heuristic is not condition-aware: a legitimate wet/intermediate lap can still exceed it. Responses disclose `track_conditions_adjusted: false`.

At least five representative laps are needed. Median is the primary overall metric; mean, fastest representative lap, and population standard deviation describe the sample. Calculations retain nanosecond precision, then publish half-up integer milliseconds without clamping. Published medians determine competition ranks (`1, 1, 3`), ties, and delta-to-best. Numeric driver number orders tied rows without breaking the analytical tie. Insufficient participants remain visible without invented metrics.

Comparison is **A's published median minus B's**: positive means A slower, negative means A faster, zero means tied. Same-driver comparison is valid; insufficient data produces no winner or delta.

Every analytics operation loads one source snapshot and performs one shared field analysis. Pure analytics are separate from provider adaptation, service projection, and HTTP handling. No cross-request cache or condition/stint/fuel/traffic correction is implemented.

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

This invokes application-owned session and pace services and may download FastF1 data into the ignored cache. It is separate from routine testing.

See the [lap/pace quickstart](specs/002-lap-pace-analytics/quickstart.md), [session-summary quickstart](specs/001-backend-f1-data-access/quickstart.md), [architecture](docs/architecture.md), and [demo scope](docs/demo-v0.1.md) for details.
