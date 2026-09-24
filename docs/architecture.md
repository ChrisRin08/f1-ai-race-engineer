# Architecture

## System Responsibilities

F1 AI Race Engineer is a monorepo with separate frontend, backend, and documentation areas:

- `frontend/` will contain the Next.js web application.
- `backend/` contains Python services, deterministic analytics, and the FastAPI application.
- `docs/` contains product and architecture documentation.

The product analyzes real Formula 1 data, computes trusted race analytics in Python, and presents the results in a dashboard. Later AI features will explain and orchestrate those trusted calculations instead of replacing them.

## Frontend and Backend Boundary

The frontend is responsible for presentation and user interaction. It should request structured results from the backend and render them clearly for the user.

The frontend must not be the authoritative source for race analytics, observed tire-stint pace trends, strategy calculations, or predictive results. It may format, filter, and visualize backend responses, but authoritative calculations belong in the backend.

The backend is responsible for data loading, validation, deterministic analytics, future predictive ML workflows, and API responses. It exposes those results through FastAPI.

## Next.js App Router Boundary

The frontend should use the Next.js App Router without making the entire dashboard a Client Component by default. Non-interactive layout, navigation, shell, and static framing should remain server-rendered where practical.

Interactive charts, selectors, hover states, and future simulation controls will require Client Components. Those client boundaries should be introduced at the smallest practical component level so presentation interactivity does not blur the backend's authority over race calculations.

## Deterministic Analytics Principle

The core principle is:

```text
Real F1 data -> deterministic Python analytics -> predictive ML when justified -> FastAPI -> Next.js dashboard
```

The system should calculate first and explain second. Numerical race outputs must come from deterministic analytics or validated predictive models, not from an LLM.

When an AI Race Engineer is introduced later, it should receive structured tool outputs and explain them in natural language. It should not invent lap times, observed tire-stint pace-trend values, pit windows, gaps, or strategy recommendations.

## Backend Data Flow

For Demo v0.1, the intended flow is:

1. Backend loads the controlled Formula 1 session dataset: 2025 Italian Grand Prix at Monza, Race session.
2. Backend runs deterministic Python analytics for the requested season, event, session, and driver scope.
3. Backend returns structured JSON through FastAPI.
4. Frontend fetches API results.
5. Frontend renders dashboard views for session analysis.

The architecture should support generic season/event/session queries, but Demo v0.1 will validate against one known race/session first to keep the vertical slice controlled. The Monza race is a control dataset for validation, not a hard-coded product limitation.

## API Direction

Feature `001-backend-f1-data-access` defines the first session-summary route around this Formula 1 resource hierarchy:

```text
year -> event -> session
```

The initial contract uses `GET /api/v1/seasons/{year}/events/{event}/sessions/{session}` and guarantees only the Monza control session. Broader route coverage and dynamic selection remain future work; the control dataset does not replace the generic resource model.

## Initial Analytics Slice

Feature `002-lap-pace-analytics` implements overall representative race pace through three nested resources: session `/pace`, driver `/pace/drivers/{driver_number}`, and ordered comparison `/pace/drivers/{driver_a}/comparisons/{driver_b}`.

Each operation follows one shared data flow:

```text
FastAPI -> pace_service.py -> f1_data.load_session (once)
  -> f1_data normalization -> lap_analytics.analyze_session_field (once)
  -> service projection -> pace_models strict response -> JSON
```

`f1_data.py` owns FastF1/Pandas adaptation, disk caching, and expected source errors. `lap_analytics.py` consumes immutable application-owned inputs using only deterministic standard-library Python. `pace_service.py` reuses the complete field result for all projections, including each driver's delta-to-best. `pace_models.py` owns response validation; routes do not calculate pace. No cross-request cache is added.

Policy `representative-race-pace-v1` uses median representative lap time, at least five laps, half-up millisecond publication, and published-median competition ranking. IsAccurate and Compound do not directly exclude laps. Its driver-relative 120% anomaly rule is intentionally condition-unaware and can exclude legitimate slower-condition laps; condition/stint-aware policies are deferred. See the [policy and contracts](../specs/002-lap-pace-analytics/data-model.md) for exclusion precedence and explicit insufficient-data semantics.

## Tire-Stint Analytics Slice

Feature `003-tire-stint-analytics` adds a compact session resource and an
auditable driver resource. Each operation uses one provider snapshot:

```text
FastAPI route
  -> stint_service
  -> f1_data.load_session (once)
  -> f1_data.map_lap_inputs (once) -> SourceLap values
  -> f1_data.map_session_summary from the same snapshot
  -> stint_analytics.analyze_session_stints (once)
     -> shared five-rule structural/status classifier
     -> deterministic stint construction and qualification
     -> validated estimator sample
     -> SciPy Theil-Sen with joint intercept
  -> compact session or detailed driver projection
  -> stint_models strict response
  -> JSON
```

`f1_data.py` owns FastF1/Pandas types and missing-value adaptation. The shared
classifier in `lap_analytics.py` owns only invalid timing, Lap 1, pit-in,
pit-out, and disruptive-status decisions. Feature 002 adds its existing 120%
anomaly pass after that boundary. Feature 003 instead adds explicit inaccurate,
provider-generated, and unusable-tire-age decisions; it never applies the 120%
rule.

`stint_analytics.py` owns grouping, qualification, availability, estimation,
and publication. Services and routes project its completed result and do not
recalculate analytics. The source-reported stint and tire age are never
inferred. `reported_compound` is audit/display evidence;
`normalized_compound` is trusted for policy only when one unambiguous recognized
compound key exists.

Feature 003 drivers are unique and already ordered by numeric driver number.
Its stints are ordered by earliest valid lap, followed by stints with no valid
earliest lap, then reported stint ID as the deterministic tie-break. Evidence
ordering is derived from normalized facts, retains duplicate multiplicity, and
does not use `source_order`. The session response contains compact summaries;
driver detail adds every normalized lap as eligible, excluded, or unassigned
evidence.

Feature 003's session response rejects direct construction with duplicate or
noncanonical driver ordering instead of silently sorting it. Feature 002's
older session response protects uniqueness but does not add this direct-model
ordering invariant; that difference is intentional and does not change Feature
002 ranking behavior. Shared `AnalyticsSessionContext.year` and
`EventSummary.round_number` retain their existing integer schemas while strict
runtime validation rejects boolean or string coercion.

The handwritten Feature 003 OpenAPI contract and generated Pydantic/OpenAPI
must agree on paths, operation IDs, fields, required and nullable structure,
enum domains, constraints, ordered versus unordered semantics, and strict
objects. The handwritten contract may include explanatory prose that generated
schemas do not reproduce word for word, such as joint-intercept or precedence
descriptions. Such prose-only differences are acceptable when those semantics
remain equivalent and verified.

The broader Demo v0.1 analytics direction includes the following. Tire compounds
and observed stint trends are implemented; pit-stop timing remains future work:

- Lap times
- Fastest lap
- Representative or average race pace
- Tire compounds
- Stint lengths and observed within-stint pace trends
- Pit-stop timing
- Basic driver pace comparison where supported by the available data

## Current Technologies

Chosen technologies for the initial architecture:

- Repository: monorepo
- Frontend: Next.js, React, TypeScript, App Router, npm
- Backend: Python 3.12, FastAPI, uv, pytest, Ruff
- Analytics/data: FastF1, Pandas, NumPy, SciPy

FastF1 uses the ignored repo-local `backend/cache/fastf1/` cache. The backend resolves this path from its project location, creates it on first data access, and enables FastF1's disk cache there. Application import and health checks do not create the cache or load race data.

Cache growth is a known future concern. Do not implement cache eviction, Docker volumes, or production cache infrastructure during Day 1. Revisit cache strategy before containerized or production deployment.

## Monorepo Validation

Frontend and backend validation should eventually be scoped independently. Frontend-only changes should not unnecessarily trigger every backend check, and backend-only changes should not unnecessarily trigger every frontend check.

No CI/CD workflows are created during Day 1. When CI/CD is introduced, it should reflect the monorepo boundary between `frontend/`, `backend/`, and documentation-only changes.

## Deferred Technologies

The following are intentionally deferred:

- PostgreSQL, Supabase, and database persistence
- pgvector and retrieval-augmented generation
- Amazon Bedrock implementation
- Gemini Live or real-time voice interaction
- Authentication
- Docker
- scikit-learn predictive ML models
- Pit strategy simulation

These technologies should be added only when the product requirements justify them.

## AI Role

The AI layer is planned as an explanation and orchestration layer. Its job is to help users understand trusted tool results, compare scenarios, and ask better questions of the analytics system.

The AI layer must not generate authoritative calculations. Any future LLM response that contains numerical race analysis should be grounded in backend analytics or model outputs.
