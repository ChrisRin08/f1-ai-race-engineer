# Implementation Plan: Tire Stints & Observed Degradation Analytics

**Branch**: `003-tire-stint-analytics` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-tire-stint-analytics/spec.md`

## Summary

Extend the existing Python 3.12 FastAPI modular monolith with deterministic,
auditable tire-stint analysis. The existing FastF1 session loader remains the
only provider path and each request maps one loaded snapshot to the existing
provider-neutral `SessionFieldInput`. Three nullable tire fields extend
`SourceLap`; a small extraction exposes Feature 002's five structural/status
rules without moving or changing its 120% anomaly behavior. A new pure
`stint_analytics.py` boundary constructs reported stints, classifies every lap,
selects one explicit availability outcome, and uses SciPy Theil-Sen with a joint
intercept for eligible slick stints. New strict response models and two additive
GET resources expose a compact session view and complete driver evidence.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI 0.141.x, FastF1 3.8.3, Pandas 2.3.x, NumPy
2.5.x, Pydantic 2.13.x, SciPy 1.18.x via a new direct `scipy>=1.11,<2`
declaration; Python standard-library `dataclasses`, `decimal`, `enum`, and
`statistics`

**Storage**: No application persistence; existing ignored FastF1 disk cache at
`backend/cache/fastf1/`

**Testing**: pytest 8.x, FastAPI `TestClient`, controlled Pandas fixtures, pure
immutable analytics fixtures, Ruff, and separately marked opt-in FastF1
integration

**Target Platform**: Local macOS/Linux development and the existing portable
synchronous ASGI service

**Project Type**: Backend web service within the existing monorepo modular
monolith

**Performance Goals**: Exactly one FastF1 session load, one normalization, and
one complete stint-field analysis per Feature 003 request; deterministic
processing for one race field and race distance; no unsupported latency SLA

**Constraints**: Preserve every Feature 001/002 route, operation ID, response,
policy, exclusion order, and error boundary; strict finite JSON; routine tests
make zero live requests; no race-control-message load, Deleted filtering,
telemetry, weather, frontend, database, AI/ML, strategy, or causal tire-wear
claim

**Scale/Scope**: The existing guaranteed 2025 Italian Grand Prix Race session,
approximately 20 participants and one race distance per operation; two additive
tire-stint GET resources

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Gate | Result |
|---|---|---|
| Deterministic Analytics Before AI | Pure analytics owns construction, eligibility, Theil-Sen, rounding, and outcome precedence | Pass |
| Real Data and Provenance | FastF1 is the only fact source; no stint or tire age is inferred or repaired | Pass |
| Testable, Verifiable Engineering | Offline unit, normalization, service, API, OpenAPI, regression, and gated real-source checks are designed | Pass |
| Incremental Complexity | Three focused Feature 003 modules extend the modular monolith; no parallel loader or infrastructure | Pass |
| Explainability and Learning | Versioned policy, one primary reason, count reconciliation, and complete driver lap evidence are public | Pass |
| Security and Configuration Hygiene | No secrets or new configuration; existing ignored cache boundary remains | Pass |
| Quality Over Token/Speed Optimization | Explicit source validation, finite-number guards, strict models, and regression checks take priority | Pass |
| Spec-Driven Feature Development | The clarified specification and repository reconnaissance govern the design | Pass |

Post-design re-check: the data model, additive OpenAPI contract, and validation
guide preserve every gate. SciPy is justified as the specified estimator's
maintained implementation and is declared directly rather than used
transitively. No exception or complexity waiver is required.

## Project Structure

### Documentation (this feature)

```text
specs/003-tire-stint-analytics/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
├── contracts/
│   └── openapi.yaml
└── checklists/
    └── requirements.md
```

`tasks.md` records the generated implementation and verification tasks; T001
through T043 are complete at this documentation checkpoint.

### Source Code (repository root)

```text
backend/
├── app/
│   ├── f1_data.py             # Extend the existing normalized lap mapping
│   ├── lap_analytics.py       # Extract shared structural/status classification
│   ├── main.py                # Add two thin, additive routes
│   ├── models.py              # Reuse schemas; strictly validate shared round number
│   ├── pace_models.py         # Reuse types; strictly validate shared context year
│   ├── pace_service.py        # Preserve unchanged Feature 002 orchestration
│   ├── stint_analytics.py     # New pure construction, policy, and trend logic
│   ├── stint_models.py        # New strict Feature 003 public contracts
│   └── stint_service.py       # New one-snapshot orchestration/projection
└── tests/
    ├── conftest.py
    ├── test_f1_data.py
    ├── test_f1_data_integration.py
    ├── test_lap_analytics.py
    ├── test_openapi.py
    ├── test_stint_analytics.py
    ├── test_stint_api.py
    └── test_stint_service.py
```

Implementation also updates `backend/pyproject.toml`, `backend/uv.lock`,
`README.md`, `docs/architecture.md`, and `docs/demo-v0.1.md`. Existing Feature
001/002 specification and contract artifacts remain unchanged.

**Structure Decision**: Keep `SourceLap` and `SessionFieldInput` where Feature
002 currently owns them instead of moving shared types in v1. Extend those
immutable inputs with defaults, extract only the reusable five-rule classifier,
and place all new rules in Feature 003 modules. This is the smallest boundary
that prevents rule duplication without exposing Feature 003 enums through
Feature 002's OpenAPI schema.

## Architecture and Data Flow

```text
FastAPI tire-stint route
  -> validate the existing supported-session and driver selector boundary
  -> stint_service operation
     -> f1_data.load_session(...) exactly once
     -> f1_data.map_lap_inputs(...) exactly once
     -> f1_data.map_session_summary(...) from the same session
     -> stint_analytics.analyze_session_stints(...) exactly once
        -> shared structural/status classification
        -> reported-stint construction and validation
        -> Feature 003 lap eligibility
        -> availability precedence
        -> SciPy Theil-Sen for available stints only
     -> session summary or driver-detail projection
     -> strict stint_models response
     -> JSON
```

No Feature 003 route calls `load_session_summary()` or a per-driver loader, and
no operation reloads or renormalizes the session for separate projections.

## Normalized Source Extension

Append these nullable fields with `None` defaults to the existing immutable
`SourceLap`; existing fields and positional construction stay compatible.

| Normalized field | FastF1/Pandas source | Type | Normalization and failure behavior |
|---|---|---|---|
| `stint` | `Laps["Stint"]` (`float64` in FastF1 3.8.3) | `int \| None` | Finite, positive, integral, non-boolean values become Python `int`; missing or malformed scalars become `None` and therefore unassigned evidence |
| `tyre_life` | `Laps["TyreLife"]` (`float64`) | `int \| None` | Finite, positive, integral, non-boolean values become Python `int`; missing or malformed values become `None` and receive the lap-level unusable-age reason |
| `provider_generated` | `Laps["FastF1Generated"]` (NumPy boolean in the verified FastF1 snapshot) | `bool \| None` | Provider booleans become Python `bool`; missing or malformed values become `None` and are neutral |

`is_accurate: bool | None` and `compound: str | None` already exist and remain.
The verified FastF1 snapshot likewise supplies `IsAccurate` as a NumPy boolean,
which normalization converts to Python `bool`.
Compound is trimmed and case-preserved in `f1_data.py`; policy matching happens
in pure analytics with an uppercase comparison key. The new source columns are
optional: absence does not make Feature 001/002 unavailable. Duplicate labels
among any consumed source columns are schema-ambiguous and produce the existing
sanitized `DataSourceUnavailableError` boundary rather than selecting an
arbitrary column.

`FreshTyre` is deliberately omitted. No approved eligibility, availability, or
response rule consumes it, `TyreLife > 1` already represents used-tire context,
and the specification defines no policy for conflicts between the two fields.
`Deleted` is also omitted; `messages=False` remains unchanged.

## Shared Structural/Status Classifier

Extract `classify_structural_status_laps()` in `lap_analytics.py` from the first
pass of `classify_driver_laps()`. It returns the existing `ClassifiedLap` using
only the existing first five `LapExclusionReason` values:

1. `invalid_timing`
2. `lap_one_start`
3. `pit_in`
4. `pit_out`
5. `disrupted_status`

Add a module-level five-value precedence tuple for tests without changing the
existing six-value `EXCLUSION_PRECEDENCE`. Then make `classify_driver_laps()`
call the extracted function before applying its exact strict
`lap_time_ns * 100 > fastest * 120` anomaly rule. Do not add Feature 003 members
to `LapExclusionReason`; that enum is part of Feature 002's contract. Preserve
current sorting, disruption diagnostics, minimum timing boundary, and the
unresolved all-empty `TrackStatus` behavior.

## Stint Construction and Eligibility

`stint_analytics.py` is pure: immutable application-owned inputs and outputs,
with no FastF1, Pandas, FastAPI, Pydantic, cache, or network imports.

- Start from the authoritative results roster and retain zero-row participants.
- Establish driver chronology by valid lap number, independent of Pandas row
  order. A duplicate identity means more than one normalized row for the same
  authoritative driver and valid lap number. Retain every duplicate row. Mark
  every identified stint represented in that duplicate group inconsistent, even
  when the rows report different stint IDs or some rows are unassigned. A group
  containing only unassigned rows creates no stint result. Rows without a valid
  lap number retain `invalid_timing`; a usable stint ID keeps them assigned, but
  they do not define chronological continuity.
- A positive integral reported stint ID creates at most one result. Missing or
  unusable IDs remain disjoint unassigned evidence with
  `missing_stint_metadata`; no inferred stint is created.
- In the valid-lap chronology, `A -> B -> A` and `A -> unassigned -> A` make A
  inconsistent. B may remain valid if its own occurrence is continuous. Numeric
  stint IDs need not be consecutive or increasing; the source identity is not
  repaired.
- Validate compound continuity across every assigned row, including excluded
  rows. Multiple distinct present uppercase keys make the stint inconsistent.
  Preserve each case-preserved source value in detail evidence.
- Classify each assigned lap exactly once: inherited structural/status reason,
  then `explicitly_inaccurate`, then `provider_generated`, then
  `unusable_tire_age`, otherwise `eligible`. Missing quality assertions are
  neutral. Feature 002's anomaly result is never consulted.
- Duplicate rows keep those ordinary lap-level decisions and participate in
  `total_lap_count`, eligible/excluded counts, reason counts, and detail evidence
  exactly like every other assigned row. Unassigned duplicate rows participate
  only in unassigned evidence/counts. Because duplicate identity is the
  higher-precedence stint metadata blocker, no row from an affected stint is
  admitted to tire-age validation or the estimator and duplicate rows never
  count as multiple valid trend observations. No row is deduplicated or moved
  between reported stints.
- Evaluate eligible ages in lap-number order. Gaps and a starting age above one
  are valid. Any repeated or decreasing valid age makes the entire stint's age
  history inconsistent; no eligible row is selectively removed to repair it.
- Reconcile `total_lap_count = eligible_observation_count +
  excluded_observation_count`. Assigned and unassigned evidence are disjoint,
  so every driver source row appears exactly once.

Drivers publish in numeric driver-number order. Stints publish by earliest valid
lap number, with missing earliest lap last, then reported stint ID. Lap evidence
uses a total canonical key made only from authoritative driver identity and
normalized facts: valid lap number with null last, reported stint with null
last, reported tire age with null last, exact `lap_time_ns` with null last,
case-preserved compound with null last, pit flags, normalized track-status
codes, `is_accurate`, and `provider_generated`. Boolean and nullable values use
explicit fixed ranks rather than language/runtime comparison accidents.
`source_order` may remain on `SourceLap` for Feature 002 compatibility and
diagnostics, but Feature 003 never uses it for chronology, grouping, selection,
or serialization order.

The summary `reported_compound` is selected by valid lap number with null last,
then the case-preserved compound token lexically; it never depends on which row
arrived first. If two rows remain indistinguishable after every canonical fact,
their Feature 003 evidence objects are also identical. Retaining the same
multiplicity of adjacent identical objects makes any permutation semantically
and byte-for-byte equivalent after JSON serialization. No synthetic row ID is
invented and no row is discarded. Lap evidence reuses Feature 002's existing
half-up `lap_time_ms` publication for display only; the canonical key and trend
estimation use the underlying unrounded `lap_time_ns`.

## Theil-Sen Policy

For an available stint, call `scipy.stats.theilslopes(y, x, method="joint")`
explicitly:

- `x`: validated source-reported `tyre_life` integers.
- `y`: exact normalized `lap_time_ns` converted to seconds without publication
  rounding.
- slope: the median of all pairwise slopes, interpreted directly as
  `observed_pace_trend_seconds_per_lap`.
- intercept: `median(y - slope * x)`, SciPy's joint convention.
- prediction: `intercept + slope * x` for each eligible observation.
- residual: median of `abs(y - prediction)` over exactly that sample.

Do not expose SciPy's confidence interval. Positive, zero, and negative slopes
are all valid observational outcomes. Require finite slope, intercept,
predictions, and residual. Preconditions prevent fewer than six points,
non-finite values, and duplicate/all-equal x values from reaching SciPy; a
non-finite library result is an internal invariant failure, not a fabricated
normal availability outcome.

Quantize slope and residual independently to `0.001` seconds with an isolated
`Decimal` context and `ROUND_HALF_UP`, then publish finite JSON numbers. Normalize
rounded negative zero to `0.0`. JSON need not render trailing zeroes; the
contract is numeric millisecond resolution. Calculations use the unrounded
source sample and unrounded fitted line.

Because application code directly imports SciPy, `backend/pyproject.toml`
declares `scipy>=1.11,<2` and the reviewed lockfile records it as a direct root
dependency. SciPy 1.18.1 remains the resolved package; unrelated resolver drift
is not accepted.

## Compound and Availability Policy

Canonical comparison keys are trimmed uppercase source strings. Only `SOFT`,
`MEDIUM`, and `HARD` can be available. `INTERMEDIATE` and `WET` remain visible
with `wet_weather_compound`. A missing value and one present unknown value are
distinct outcomes; the present source token remains visible.

Exact status values:

- `available`
- `unavailable`

Exact unavailable reason values:

1. `inconsistent_stint_metadata`
2. `wet_weather_compound`
3. `missing_compound`
4. `unsupported_compound`
5. `inconsistent_tire_age`
6. `missing_tire_age`
7. `insufficient_eligible_sample`

Selection follows this decision order: inconsistent stint metadata; a sole
wet-weather compound; compound tier; inconsistent eligible age history; sample
outcome. Within the compound tier, any missing assigned compound selects
`missing_compound`; otherwise one present unknown key selects
`unsupported_compound`. This deterministic tie rule does not assign a policy
priority between the two semantic outcomes.

For sample outcomes, `missing_tire_age` is the public reason for normalized
reported tire age that is unavailable or unusable, whether the provider value
was absent or normalization rejected a non-finite, non-positive, non-integral,
or boolean value. It applies exactly when `eligible_count < 6`, at least one lap
has the primary `unusable_tire_age` reason, and
`eligible_count + unusable_tire_age_count >= 6`. If restoring only those
unusable-age observations would still leave fewer than six, use
`insufficient_eligible_sample`. Explicit quality exclusions only reduce the
sample and never create their own stint blocker.

## API and Public Models

Add exactly two resources:

| Resource | Operation ID | Response |
|---|---|---|
| `GET /api/v1/seasons/{year}/events/{event}/sessions/{session}/tire-stints` | `getSessionTireStintAnalysis` | `SessionTireStintAnalysisResponse` |
| `GET /api/v1/seasons/{year}/events/{event}/sessions/{session}/tire-stints/drivers/{driver_number}` | `getDriverTireStintAnalysis` | `DriverTireStintAnalysisResponse` |

Reuse the existing supported-session lookup, selector regex, 404 codes, 422
validation, sanitized 503 mapping, and unexpected 500 behavior. A known
zero-row driver returns 200 with empty stints/evidence; an unknown canonical
driver returns `driver_not_found` after one analysis.

`stint_models.py` inherits the existing `ContractModel` and imports the existing
`AnalyticsSessionContext`, `AnalyticsDriverIdentity`, driver-number type, and
`SourceProvenance` without moving or editing their definitions. Feature 003 owns
its policy, limitation, range, sample, exclusion, stint-summary, evidence, and
root response models. Every field is required even when nullable and every model
forbids extras.

The session response contains context, policy, limitations, one driver summary
for every results participant, and provenance. Driver summaries contain compact
ordered stint summaries plus an unassigned count; no session-level lap evidence
is included. Driver detail returns the same driver summary values plus one flat,
canonically ordered evidence record for every driver source row. Evidence uses
`eligible`, `excluded`, or `unassigned` dispositions with exactly the compatible
exclusion or unassigned reason.

Each response contains immutable limitation metadata:

- `interpretation = observational_association`
- `isolated_physical_tire_wear = false`
- fixed `unadjusted_for` values for fuel load/burn, traffic, track evolution,
  driver tire management, changing environmental conditions, and other
  unmodeled race effects
- a fixed human-readable statement that the metric is not isolated physical
  tire wear

## Test Strategy

Routine tests remain offline under the existing autouse FastF1 guard.

- Extend `test_f1_data.py` for the three new normalized fields, optional-column
  absence, strict scalar normalization, raw compound preservation, missing
  quality neutrality, and duplicate consumed-column rejection.
- Extend `test_lap_analytics.py` to prove the extracted five-rule classifier and
  Feature 002's six-rule output are unchanged, including the strict 120% rule.
- Add `test_stint_analytics.py` for positive/zero/negative slopes, isolated
  extremes, half-up 0.001 publication, six/five samples, every tire-age case,
  explicit true/false/missing accuracy and provider-generation states, every
  structural exclusion, absence of the 120% rule, every compound state, stint
  conflicts, absent and malformed sample-decisive tire age, and duplicate
  identities within one stint, across different identified stints, mixed with
  unassigned rows, and containing only unassigned rows. Permutation tests assert
  identical public serialization, full row multiplicity, exact
  assigned/unassigned and eligible/excluded reconciliation, no duplicate-group
  observations reaching the estimator, unavailable metric suppression, and
  repeated execution.
- Add `test_stint_service.py` for one load/map/summary/analyze call per operation,
  compact/detail projections, all participants, unknown/zero-row drivers,
  determinism, and failure propagation.
- Add `test_stint_api.py` for success/error paths, strict nested-state validators,
  finite JSON, complete detail evidence, compact session output, and malformed
  selector behavior.
- Extend `test_openapi.py` with semantic path, operation, response-reference,
  strictness, required-nullable, enum, signed trend, non-negative residual,
  policy, and limitation checks. Do not snapshot generated schemas.
- Extend the existing gated `test_f1_data_integration.py` to validate normalized
  real FastF1 tire metadata, participant/stint reconciliation, finite available
  values, null unavailable values, limitation disclosure, and deterministic
  invariants. Do not assert an external degradation number.
- Run the complete existing Feature 001/002 suite as the regression gate.

## Implemented Sequence

1. Normalized source extensions and focused provider-adapter tests.
2. Shared structural/status classifier extraction and Feature 002 regression
   tests.
3. Pure stint construction, lap eligibility, availability selection, and unit
   tests.
4. Direct SciPy declaration, Theil-Sen joint-line calculation, publication, and
   analytical unit tests.
5. Strict public models, one-snapshot service projection, and service tests.
6. Additive routes, semantic OpenAPI contract checks, and API tests.
7. Gated FastF1 acceptance, complete offline regression verification, and
   narrow README/architecture/demo documentation updates.

These groups were expanded into `tasks.md` and implemented in that dependency
order.

## Dependency and Contract Audit

| File or boundary | Implemented change |
|---|---|
| `backend/pyproject.toml` | Declares direct `scipy>=1.11,<2` production dependency |
| `backend/uv.lock` | Records reviewed root dependency metadata with SciPy 1.18.1 retained |
| `backend/app/f1_data.py` | Maps three additional nullable fields without changing source loading flags |
| `backend/app/lap_analytics.py` | Extracts the shared five-rule function and appends defaulted source fields while preserving Feature 002 outputs |
| `backend/app/models.py` | Keeps the public schema and meaning; strictly validates `EventSummary.round_number` as a runtime integer |
| `backend/app/pace_models.py` | Reuses Feature 002 types and strictly validates `AnalyticsSessionContext.year` as a runtime integer; other Feature 002 behavior is unchanged |
| `backend/app/pace_service.py` | No change |
| `backend/app/main.py` | Adds two routes with existing error/session validation behavior |
| Feature 001/002 OpenAPI artifacts | No change |
| Feature 003 OpenAPI | Complete additive contract in `contracts/openapi.yaml` |
| Documentation | README, architecture, demo, and validation artifacts synchronized after verified behavior |

### Exact implementation file inventory

New application and test files:

- `backend/app/stint_analytics.py`
- `backend/app/stint_models.py`
- `backend/app/stint_service.py`
- `backend/tests/test_stint_analytics.py`
- `backend/tests/test_stint_api.py`
- `backend/tests/test_stint_service.py`

Existing files to modify:

- `backend/app/f1_data.py`
- `backend/app/lap_analytics.py`
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/pace_models.py`
- `backend/tests/conftest.py`
- `backend/tests/test_f1_data.py`
- `backend/tests/test_lap_analytics.py`
- `backend/tests/test_openapi.py`
- `backend/tests/test_f1_data_integration.py`
- `backend/pyproject.toml`
- `backend/uv.lock`
- `README.md`
- `docs/architecture.md`
- `docs/demo-v0.1.md`

Explicitly unchanged files and artifacts:

- `backend/app/pace_service.py`
- `backend/tests/test_health.py`
- `backend/tests/test_sessions.py`
- `backend/tests/test_pace_api.py`
- `backend/tests/test_pace_service.py`
- all files under `specs/001-backend-f1-data-access/`
- all files under `specs/002-lap-pace-analytics/`

## Risks and Backward Compatibility

- The classifier extraction is the highest Feature 002 regression risk. Tests
  must compare its exact classifications, anomaly reference sample, ordering,
  diagnostics, counts, metrics, and OpenAPI enums before and after extraction.
- `SourceLap` is shared but housed in `lap_analytics.py`. Appending nullable
  defaults is lower risk than moving it; a shared-domain-module migration is out
  of scope.
- Duplicate optional source labels become an explicit 503 instead of ambiguous
  Pandas coercion. This is a deliberate defensive source-boundary behavior and
  must not tighten ordinary missing optional metadata into a session failure.
- Missing and malformed scalar stint/tire-age values both normalize to `None`.
  This satisfies the approved unusable-data policy but does not preserve an
  arbitrary malformed raw scalar; the public contract does not require that
  distinction.
- SciPy float outputs require explicit finite checks and decimal publication.
  NaN, infinity, negative zero, and confidence-interval fields must never leak.
- A response must not call the metric simply `degradation`, imply causality, or
  omit its limitations. Existing Feature 002 pace remains condition-unaware and
  unchanged.
- No unresolved product or architecture decision remained when tasks were
  generated. Final repository review still rejects unexpected lockfile resolver
  drift.

## Complexity Tracking

No constitution violation or exception requires tracking.
