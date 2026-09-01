# F1 AI Race Engineer

An AI-powered Formula 1 race analysis and strategy platform built using real race data.

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
- `backend/` will contain Python services, deterministic analytics, and the FastAPI application.
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

Phase 1 — Foundation and AI/ML fundamentals.

Setup and scaffolding are still in progress. Next.js, FastAPI, and project dependencies have not been initialized yet.

See [docs/architecture.md](docs/architecture.md) and [docs/demo-v0.1.md](docs/demo-v0.1.md) for the current Day 1 architecture and demo scope.
