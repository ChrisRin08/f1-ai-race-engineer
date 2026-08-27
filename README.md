# F1 AI Race Engineer

An AI-powered Formula 1 race analysis and strategy platform built using real race data.

## Goal

Build a production-style application that analyzes Formula 1 race data, runs deterministic strategy calculations and simulations, and uses generative AI to explain the results like a race engineer.

## Core Principle

The AI does not invent race calculations.

Deterministic Python analytics and simulation tools calculate the results first. The AI receives those results and explains them in natural language.

## MVP Features

- Load real Formula 1 race/session data
- Analyze lap times
- Analyze tire compounds and stints
- Display pit stops and race gaps
- Compare two drivers
- Estimate tire degradation
- Identify possible pit windows
- Run basic what-if strategy simulations
- Generate AI race-engineer explanations

## Planned Stack

### Frontend
- Next.js
- React
- TypeScript

### Backend
- Python
- FastAPI

### Data / Analytics
- FastF1
- Pandas
- NumPy
- scikit-learn

### Database
- PostgreSQL
- Supabase

### AI / AWS
- Amazon Bedrock
- AWS services introduced as the project grows

## Status

Phase 1 — Foundation and AI/ML fundamentals