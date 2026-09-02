<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- Template principle 1 -> I. Deterministic Analytics Before AI
- Template principle 2 -> II. Real Data and Provenance
- Template principle 3 -> III. Testable, Verifiable Engineering
- Template principle 4 -> IV. Incremental Complexity
- Template principle 5 -> V. Explainability and Learning
Added principles:
- VI. Security and Configuration Hygiene
- VII. Quality Over Token/Speed Optimization
- VIII. Spec-Driven Feature Development
Added sections:
- Development Constraints
- Quality Gates
Removed sections:
- Placeholder section names and example comments
Follow-up TODOs: None
-->
# F1 AI Race Engineer Constitution

## Core Principles

### I. Deterministic Analytics Before AI

Race calculations, telemetry analysis, strategy calculations, and ML outputs MUST
come from deterministic and testable tools. LLMs MAY explain, summarize, or
orchestrate trusted tools, but MUST NOT invent numerical race facts.

Rationale: Formula 1 analysis depends on numerical trust. Explanations can be
natural-language, but calculations must remain auditable.

### II. Real Data and Provenance

Formula 1 facts MUST originate from approved sources such as FastF1. Missing,
unavailable, incomplete, or inconsistent data MUST be handled explicitly and
MUST NOT be replaced with fabricated fallback facts.

Rationale: The product's credibility depends on traceable data and honest
failure modes.

### III. Testable, Verifiable Engineering

Important business logic and API behavior MUST have automated tests where
reasonable. Appropriate test, lint, and build checks MUST pass before a feature
is considered complete.

Rationale: This is a production-style portfolio project, and claims about
behavior must be verifiable.

### IV. Incremental Complexity

The project MUST use the simplest architecture that satisfies current
requirements. New abstractions, infrastructure, databases, cloud services, ML
models, or agents MUST NOT be introduced before requirements justify them.

Rationale: Unjustified complexity makes the system harder to explain, test, and
finish.

### V. Explainability and Learning

Major code, architecture, data flows, decisions, and tradeoffs MUST remain
understandable and explainable by the developer in an interview.

Rationale: The project must demonstrate engineering judgment, not only working
outputs.

### VI. Security and Configuration Hygiene

Secrets MUST NOT be committed. Environment-specific configuration MUST remain
separate from source code, with safe examples documented when configuration is
introduced.

Rationale: Secure defaults protect the repository and make local setup
repeatable.

### VII. Quality Over Token/Speed Optimization

Correctness, maintainability, readability, and appropriate testing MUST take
priority over minimizing AI-agent token usage or implementation time.

Rationale: Fast output is not useful if it creates fragile or unclear software.

### VIII. Spec-Driven Feature Development

Meaningful features MUST follow specification, clarification when needed, plan,
checklist/tasks/analyze as appropriate, implementation, independent review,
approved fixes, verification, and commit/merge.

Rationale: Durable artifacts reduce ambiguity and keep implementation aligned
with the project goal.

## Development Constraints

The repository MUST preserve the documented monorepo boundaries:

- `frontend/` contains the web application.
- `backend/` contains Python services, deterministic analytics, and API
  behavior.
- `docs/` contains architecture and product documentation.
- `specs/` contains Spec Kit feature artifacts.

The frontend MUST NOT perform authoritative race analytics or strategy
calculations. The backend MUST remain the authoritative source for data loading,
validation, deterministic analytics, future predictive ML workflows, and API
responses.

Deferred systems, including database persistence, AI integrations, ML models,
deployment infrastructure, authentication, and live voice features, require an
approved specification before implementation.

## Quality Gates

Each feature MUST be checked against its specification and this constitution
before implementation is considered complete. Tests, linting, build checks, and
documentation updates MUST be proportional to the feature's risk and scope.

Reviews MUST prioritize correctness, deterministic data behavior, security,
maintainability, and explainability. Generated caches, local data, credentials,
and build artifacts MUST NOT be committed.

## Governance

This constitution supersedes informal project preferences for feature planning
and implementation. Amendments require a documented reason, impact summary, and
semantic version change.

Version changes follow this policy:

- MAJOR: Backward-incompatible governance or principle changes.
- MINOR: New principles or materially expanded governance.
- PATCH: Clarifications, wording improvements, or non-semantic corrections.

Feature specifications, implementation plans, tasks, code reviews, and final
verification MUST check compliance with this constitution. Any approved
exception MUST be documented in the relevant feature artifact.

**Version**: 1.0.0 | **Ratified**: 2026-09-01 | **Last Amended**: 2026-09-01
