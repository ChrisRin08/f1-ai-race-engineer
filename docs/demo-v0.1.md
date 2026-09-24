# Demo v0.1

## Goal

Demo v0.1 targets a working vertical slice:

```text
real F1 data -> deterministic Python analytics -> FastAPI -> frontend dashboard
```

The goal is to prove that the product can load real Formula 1 session data, calculate useful analytics in Python, expose those results through an API, and display them in a focused dashboard.

## Vertical Slice

The first demo should validate one known race/session before expanding to broader season/event/session coverage.

The internal architecture should still be shaped around generic season, event, session, and driver inputs so the demo does not become a one-off implementation.

The initial validation dataset is the 2025 Italian Grand Prix at Monza, Race session. This is a control dataset for validating the vertical slice, not a permanent hard-coded product limitation. The backend should later support dynamic year, event, and session selection.

## Included Scope

Current backend capability: health, session summary, deterministic representative lap evidence, overall pace ranking, directional driver comparison, and observed tire-stint analytics for the Monza control race. Feature 002 uses median pace, a five-lap minimum, published-millisecond ties/ranks/deltas, and explicit exclusion counts. Its condition-unaware 120% anomaly heuristic is separate from Feature 003, which uses reported stint and tire-age facts, requires six eligible distinct ages, and publishes an observational Theil-Sen trend where available. The frontend and the remaining broader analytics below remain demo targets, not delivered functionality.

Demo v0.1 targets:

- A Next.js frontend dashboard.
- A FastAPI backend.
- Deterministic Python analytics.
- Real Formula 1 data loaded through the backend.
- Structured API responses consumed by the frontend.
- A controlled validation session for initial demo confidence.

The intended first analytics slice includes:

- Lap times
- Fastest lap
- Representative or average race pace
- Tire compounds
- Stint lengths
- Pit-stop timing
- Basic driver pace comparison where supported by the available data

## Deferred Scope

The following are explicitly out of scope for Demo v0.1 unless the plan changes:

- Database persistence
- Supabase or PostgreSQL
- pgvector or RAG
- Amazon Bedrock implementation
- Gemini Live voice interaction
- Authentication
- Docker
- scikit-learn model training
- Pit strategy simulation
- LLM-generated strategy calculations
- Cache eviction, Docker volumes, or production cache infrastructure
- CI/CD workflow creation
- Dynamic session coverage and analytics beyond the approved session, pace, and tire-stint resources

## Feature 003 Demonstration Flow

Start the API from the repository root:

```bash
cd backend
uv run --frozen --no-sync uvicorn app.main:app --reload
```

Request the compact session view:

```bash
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/tire-stints
```

The response keeps every authoritative participant in numeric driver-number
order and shows each reported stint's compound, ranges, reconciled sample,
status, and optional metrics. It does not duplicate lap evidence. If the loaded
provider snapshot contains an `available` stint, inspect its
`observed_pace_trend_seconds_per_lap` and
`median_absolute_residual_seconds`. If it contains an `unavailable` stint,
inspect its `unavailability_reason` and confirm both metrics are null. The demo
does not depend on a particular driver or outcome because FastF1 can correct
historical data.

Choose a canonical `driver_number` returned by the session response, export it
as `DRIVER_NUMBER`, and request the audit resource:

```bash
curl --fail --silent \
  "http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/tire-stints/drivers/${DRIVER_NUMBER}"
```

Driver detail repeats the same stint summaries and adds one evidence record for
every normalized source lap. Use `disposition`, `primary_exclusion_reason`, and
`unassigned_reason` to explain why each row did or did not enter an estimator
sample. The sample totals, detailed exclusion counts, and unassigned count must
reconcile with that evidence.

Interpret the trend as observed direction within one stint:

- positive: lap times tended to increase as reported tire age increased;
- negative: lap times tended to decrease as reported tire age increased;
- zero: no directional change remains after publication rounding.

None of these values alone proves physical tire degradation. The response
explicitly identifies an `observational_association`, sets
`isolated_physical_tire_wear` to false, and lists fuel load or burn, traffic,
track evolution, driver tire management, changing environmental conditions,
and other unmodeled race effects as unadjusted factors.

## Acceptance Criteria

Demo v0.1 is acceptable when:

- The backend can load one known Formula 1 session through a controlled path.
- The controlled path validates the 2025 Italian Grand Prix at Monza, Race session.
- The backend computes deterministic analytics without relying on an LLM.
- FastAPI exposes the analytics as structured JSON.
- The frontend fetches backend data instead of hard-coding authoritative race results.
- The dashboard presents the selected session clearly enough to explain the race analysis workflow.
- Generated caches, local data, credentials, and build artifacts are not committed.
