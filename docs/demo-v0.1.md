# Demo v0.1

## Goal

Demo v0.1 targets a working vertical slice by September 6:

```text
real F1 data -> deterministic Python analytics -> FastAPI -> frontend dashboard
```

The goal is to prove that the product can load real Formula 1 session data, calculate useful analytics in Python, expose those results through an API, and display them in a focused dashboard.

## Vertical Slice

The first demo should validate one known race/session before expanding to broader season/event/session coverage.

The internal architecture should still be shaped around generic season, event, session, and driver inputs so the demo does not become a one-off implementation.

The initial validation dataset is the 2025 Italian Grand Prix at Monza, Race session. This is a control dataset for validating the vertical slice, not a permanent hard-coded product limitation. The backend should later support dynamic year, event, and session selection.

## Included Scope

Demo v0.1 includes:

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
- Concrete API route finalization

## Acceptance Criteria

Demo v0.1 is acceptable when:

- The backend can load one known Formula 1 session through a controlled path.
- The controlled path validates the 2025 Italian Grand Prix at Monza, Race session.
- The backend computes deterministic analytics without relying on an LLM.
- FastAPI exposes the analytics as structured JSON.
- The frontend fetches backend data instead of hard-coding authoritative race results.
- The dashboard presents the selected session clearly enough to explain the race analysis workflow.
- Generated caches, local data, credentials, and build artifacts are not committed.
