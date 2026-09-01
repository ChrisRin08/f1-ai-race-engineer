# Architecture

## System Responsibilities

F1 AI Race Engineer is a monorepo with separate frontend, backend, and documentation areas:

- `frontend/` will contain the Next.js web application.
- `backend/` will contain Python services, deterministic analytics, and the FastAPI application.
- `docs/` contains product and architecture documentation.

The product analyzes real Formula 1 data, computes trusted race analytics in Python, and presents the results in a dashboard. Later AI features will explain and orchestrate those trusted calculations instead of replacing them.

## Frontend and Backend Boundary

The frontend is responsible for presentation and user interaction. It should request structured results from the backend and render them clearly for the user.

The frontend must not be the authoritative source for race analytics, tire degradation estimates, strategy calculations, or predictive results. It may format, filter, and visualize backend responses, but authoritative calculations belong in the backend.

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

When an AI Race Engineer is introduced later, it should receive structured tool outputs and explain them in natural language. It should not invent lap times, tire degradation values, pit windows, gaps, or strategy recommendations.

## Planned Data Flow

For Demo v0.1, the intended flow is:

1. Backend loads the controlled Formula 1 session dataset: 2025 Italian Grand Prix at Monza, Race session.
2. Backend runs deterministic Python analytics for the requested season, event, session, and driver scope.
3. Backend returns structured JSON through FastAPI.
4. Frontend fetches API results.
5. Frontend renders dashboard views for session analysis.

The architecture should support generic season/event/session queries, but Demo v0.1 will validate against one known race/session first to keep the vertical slice controlled. The Monza race is a control dataset for validation, not a hard-coded product limitation.

## API Direction

Concrete FastAPI routes are not finalized yet. Conceptually, the future API should be shaped around Formula 1 resources in this hierarchy:

```text
year -> event -> session
```

The first implementation may validate one known session before exposing broader selection. It should still preserve the generic direction so later dynamic year, event, session, and driver queries can be added without replacing the core model.

## Initial Analytics Slice

The intended first analytics slice for Demo v0.1 includes:

- Lap times
- Fastest lap
- Representative or average race pace
- Tire compounds
- Stint lengths
- Pit-stop timing
- Basic driver pace comparison where supported by the available data

## Current Technologies

Chosen technologies for the initial architecture:

- Repository: monorepo
- Frontend: Next.js, React, TypeScript, App Router, npm
- Backend: Python 3.12, FastAPI, uv, pytest, Ruff
- Analytics/data: FastF1, Pandas, NumPy

FastF1 will use a repo-local ignored cache location, currently planned as `backend/cache/`, when it is introduced. Race data should not be downloaded during Day 1 setup.

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
