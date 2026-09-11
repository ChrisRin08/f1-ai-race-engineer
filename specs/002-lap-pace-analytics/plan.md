# Implementation Plan: Lap Data & Driver Pace

**Branch**: `002-lap-pace-analytics` | **Date**: 2026-09-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-lap-pace-analytics/spec.md`

## Summary

Extend the existing Python 3.12 FastAPI modular monolith with deterministic,
explainable overall race-pace analytics. A small source-loading refactor keeps
FastF1 cache setup, loading, and source-error translation in `f1_data.py` while
allowing one loaded session snapshot to feed both the existing session-summary
mapper and a new normalized lap input. A pure `lap_analytics.py` boundary
classifies every driver lap, calculates field-wide pace once, and exposes
stable projections through three nested API resources. Routine tests use
controlled data and never contact FastF1; real Monza validation remains marked
and explicitly opted in.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI 0.141.x, FastF1 3.8.3, Pandas 2.3.x, NumPy
2.5.x, Pydantic 2.13.x; Python standard-library `dataclasses`, `decimal`, and
`enum`; no new dependency

**Storage**: No application persistence; existing ignored FastF1 disk cache at
`backend/cache/fastf1/`

**Testing**: pytest 8.4.x, FastAPI `TestClient`, controlled Pandas fixtures,
pure analytics fixtures, Ruff; separately marked opt-in FastF1 integration

**Target Platform**: Local macOS/Linux development and the existing portable
synchronous ASGI service

**Project Type**: Backend web service within the existing monorepo modular
monolith

**Performance Goals**: Exactly one FastF1 session load and one complete field
analysis per analytics request; deterministic O(L log L) processing for L
session laps; no new cold-source latency target

**Constraints**: Preserve `/health` and session-summary behavior and operation
IDs; strict JSON-safe contracts; no NaN or infinity; routine tests make zero
live requests; no telemetry, weather, race-control messages, database,
frontend, AI, ML, strategy, deployment, or dependency changes

**Scale/Scope**: One guaranteed 2025 Italian Grand Prix Race control session,
approximately one race field and one race distance per request, three analytics
GET resources, overall unadjusted race pace only

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Gate | Result |
|---|---|---|
| Deterministic Analytics Before AI | Pure Python policy owns every classification, metric, rank, and delta | Pass |
| Real Data and Provenance | FastF1 is the only fact source; missing data is explicit and provenance is returned | Pass |
| Testable, Verifiable Engineering | Pure controlled tests, API boundary tests, and opt-in real validation are planned | Pass |
| Incremental Complexity | Three focused modules extend the modular monolith; no repository framework or service infrastructure | Pass |
| Explainability and Learning | Named policy, ordered exclusions, per-lap evidence, and count reconciliation are public | Pass |
| Security and Configuration Hygiene | No secrets; existing ignored repository-local cache remains unchanged | Pass |
| Quality Over Token/Speed Optimization | Exact arithmetic, strict models, and skeptical contract tests take priority | Pass |
| Spec-Driven Feature Development | Clarified requirements and researched source semantics drive all design artifacts | Pass |

Post-design re-check: the data model, OpenAPI contract, and quickstart preserve
all gates. No exception or complexity waiver is required.

## Project Structure

### Documentation (this feature)

```text
specs/002-lap-pace-analytics/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
├── checklists/
│   └── requirements.md
└── tasks.md                 # Created later by $speckit-tasks; not in this plan run
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py              # Existing API boundary; add thin analytics routes
│   ├── models.py            # Existing contracts; preserve current models
│   ├── pace_models.py       # New strict analytics API contracts
│   ├── f1_data.py           # FastF1 load/cache/errors and source normalization
│   ├── lap_analytics.py     # New pure policy, classification, metrics, ranking
│   └── pace_service.py      # New load-once application orchestration/projections
└── tests/
    ├── conftest.py
    ├── test_f1_data.py
    ├── test_lap_analytics.py
    ├── test_pace_service.py
    ├── test_pace_api.py
    ├── test_openapi.py
    └── test_f1_data_integration.py
```

Implementation is also expected to update `README.md`, `docs/architecture.md`,
and `docs/demo-v0.1.md` narrowly so the validated capability and policy are not
overclaimed and the old additional-route deferral is no longer stale.
`backend/pyproject.toml`, `backend/uv.lock`, and the completed feature-001
OpenAPI contract are not expected to change.

**Structure Decision**: Keep `f1_data.py` as the only FastF1 adapter, introduce
one pure analytics module, and add one small application orchestration module.
Keep analytics response contracts in a feature-focused module that reuses the
existing strict `ContractModel` and source/session components. This separates
source, calculation, HTTP, and serialization responsibilities without adding
repositories, dependency injection frameworks, persistence, or microservices.

## Architecture and Data Flow

```text
FastAPI analytics route
  -> validate supported session and driver-number syntax
  -> pace_service application operation
     -> f1_data.load_session(...) exactly once
        -> configure existing repository-local cache
        -> FastF1 get_session + selective load
        -> translate only expected source failures
     -> f1_data maps summary context and normalized lap inputs
     -> lap_analytics.analyze_session_field(...) exactly once
     -> select session, driver, or comparison projection
     -> strict Pydantic response model
```

Each request is one analysis operation. It owns one loaded session snapshot and
one immutable field-analysis result. Individual summaries and comparisons are
projections from that result, never separate FastF1 loads or per-driver field
recomputations. Cross-request in-memory caching is deferred; FastF1's existing
disk cache remains the only cache.

## Module Responsibilities

### `f1_data.py`

- Extract the existing cache configuration, `fastf1.get_session`, selective
  `Session.load`, and narrow exception translation into `load_session(...)`.
- Preserve `load_session_summary(...)` as a compatibility wrapper around
  `load_session(...)` plus `map_session_summary(...)`.
- Normalize the loaded `Session.laps` table into application-owned immutable
  lap inputs. FastF1/Pandas column names, missing-value handling, timedeltas,
  and status codes stop at this boundary.
- Reject a missing/empty lap dataset or absent required columns as
  `DataSourceUnavailableError`; also reject duplicate/noncanonical result
  driver numbers or lap rows that cannot map to the result roster. Preserve
  unexpected programming errors.

### `lap_analytics.py`

- Define immutable internal input/result records and the versioned policy.
- Classify every source lap once using ordered first-match precedence.
- Analyze every participant from the session results, including participants
  with no lap rows.
- Calculate full-precision metrics, publish integer milliseconds, assign
  competition ranks, and calculate delta-to-best.
- Remain free of FastAPI, network, cache, FastF1 `Session`, and Pandas APIs.

### `pace_service.py`

- Own one load/map/analyze operation and response projection.
- Return a full session response, select one known driver, or compare two known
  drivers from the same field result.
- Distinguish an unknown driver from a known driver with insufficient data.
- Map only expected source failures at the API boundary; do not catch broad
  internal exceptions.

### `pace_models.py` and `main.py`

- `pace_models.py` owns strict analytics response contracts and state
  validation while reusing existing session/source models. Its analytics
  driver identity preserves source-backed descriptive fields but validates the
  canonical driver-number syntax without tightening the existing `Participant`
  contract.
- `main.py` keeps handlers synchronous and thin: path validation, supported
  tuple resolution, service call, and existing-style 404/503 responses.
- Existing routes, models, payloads, error codes, and operation IDs remain
  unchanged.

## Representative-Lap Policy

The public policy identifier is `representative-race-pace-v1`. For each result
participant, retain source row order and classify every associated row using
the first matching rule:

1. `invalid_timing`: the lap record lacks the minimum valid timing identity
   required for deterministic pace analysis. This includes a missing,
   malformed, non-finite, or below-500,000-ns lap duration (including zero,
   negative, and positive values below that minimum), or a missing,
   non-integral, non-positive, or non-finite lap number because the record
   cannot safely support Lap 1 exclusion or evidence ordering.
2. `lap_one_start`: valid lap number equals 1.
3. `pit_in`: `PitInTime` is present.
4. `pit_out`: `PitOutTime` is present.
5. `disrupted_status`: `TrackStatus` contains any verified disruptive code:
   yellow `2`, Safety Car `4`, red flag `5`, VSC `6`, or VSC ending `7`.
6. `anomalous_pace`: after rules 1-5, duration is strictly greater than 120%
   of that driver's fastest remaining lap.

The anomalous comparison uses exact integer arithmetic
`lap_time_ns * 5 > fastest_lap_ns * 6`; a lap exactly at 120% remains
representative. If both pit indicators are present, `pit_in` wins by
precedence. If multiple disruptive codes occur, the lap receives one primary
`disrupted_status` reason and retains the observed codes as diagnostics.

`IsAccurate`, compound, and wet/intermediate status do not exclude laps.
`IsAccurate` is nullable diagnostic metadata only. Missing per-row track status
does not fabricate a disruptive state; it remains explicit diagnostic absence.
The API policy states that pace is not adjusted for track conditions. The
lap-aggregated status can show that a condition overlapped a lap, but cannot
measure duration or time loss within that lap. Raw status codes retain their
first-observed source order; normalized disruptive values use the fixed public
policy order. The v1 120% heuristic is also not condition-aware: a legitimate
lap in substantially slower conditions can still exceed the driver's fastest
otherwise-eligible lap by more than 20% and be classified as
`anomalous_pace`. Compound eligibility therefore does not guarantee that every
wet or intermediate lap survives the later anomaly rule.

Counts must always satisfy:

```text
source_lap_count = representative_lap_count + excluded_lap_count
excluded_lap_count = sum(primary exclusion counts)
```

## Session-Field Analysis Algorithm

1. Build the participant field from authoritative session results, with
   canonical decimal-string driver numbers.
2. Group normalized source laps by driver number while retaining source order.
3. Apply structural/status rules 1-5 to every driver lap.
4. For each driver with at least one otherwise-eligible lap, find that driver's
   fastest duration and apply the strict 120% rule.
5. Publish per-lap classifications in lap-number order, then source order;
   invalid lap numbers follow valid lap numbers in source order.
6. Drivers with at least five representative laps receive metrics. Other known
   participants receive `insufficient_data` with counts and evidence only.
7. Sort available drivers by published median milliseconds and then numeric
   driver number. Sort insufficient drivers afterward by numeric driver number.
8. Assign competition ranks (`1, 1, 3`) for equal published medians. Numeric
   driver number affects display order only, never the analytical tie.
9. Calculate every available driver's delta from the lowest published median.

If the session lap table is missing/empty or has no valid participant-linked
timing data at all, the analytics source is unavailable rather than a field of
fabricated insufficient summaries. A known participant with zero matching rows
in an otherwise usable session remains a successful `insufficient_data`
summary.

## Metric and Publication Semantics

- Normalize usable FastF1 timedeltas to integer nanoseconds at the source
  boundary; never pre-round representative lap durations. Require at least
  500,000 ns before accepting a duration as usable; smaller values normalize
  to null and are classified as `invalid_timing`. Keep their source rows.
  Exactly 500,000 ns is valid timing and publishes as 1 ms, subject to all
  remaining classification rules.
- Calculate median, arithmetic mean, fastest, and population standard
  deviation from the full-precision nanosecond values.
- Use standard-library decimal arithmetic inside an explicit local precision
  context (at least 50 decimal digits) for deterministic aggregation and
  `ROUND_HALF_UP` publication; do not depend on process-global decimal context
  or add a numerical dependency.
- Publish every duration and delta as an integer number of milliseconds.
- Do not clamp a rounded 0 ms to 1 ms. Every representative duration is at
  least 500,000 ns, so its minimum, arithmetic mean, and median are also at
  least 500,000 ns and publish as at least 1 ms. Population standard deviation
  and deltas can legitimately be zero; their existing contracts allow it.
- Derive comparison deltas, delta-to-best, ranking, and ties from published
  median milliseconds so displayed values and conclusions cannot disagree.
- Never pass Pandas/NumPy missing scalars, NaN, infinity, or raw timedeltas into
  Pydantic responses.

## API Resource Design

All resources extend the existing session hierarchy:

| Method and path suffix | Operation ID | Purpose |
|---|---|---|
| `GET .../sessions/{session}/pace` | `getSessionPaceAnalysis` | Field summaries, ordering, ranks, and delta-to-best |
| `GET .../sessions/{session}/pace/drivers/{driver_number}` | `getDriverPaceAnalysis` | One summary plus every classified source lap |
| `GET .../sessions/{session}/pace/drivers/{driver_a}/comparisons/{driver_b}` | `compareDriverPace` | Ordered A-minus-B comparison from one field analysis |

Three resources are justified because their payloads have distinct scopes:
compact field ranking, detailed per-lap evidence, and an explicitly directional
comparison. A same-driver comparison is valid and returns zero/tied. Driver
selectors accept canonical positive decimal strings without leading zero;
abbreviation and name are descriptive only.

## Error Semantics

- `422`: malformed year/event/session or driver-number path syntax; validation
  occurs before source access.
- `404 session_not_supported`: well-formed tuple outside the existing support
  map; no source access.
- `404 driver_not_found`: well-formed canonical driver number absent from the
  loaded session results; the operation loads/analyzes once because membership
  is source-backed.
- `200 insufficient_data`: known participant with fewer than five
  representative laps; metrics, rank, delta, and comparison winner remain
  null. A comparison is unavailable when either known driver is insufficient.
- `503 data_source_unavailable`: expected FastF1/cache/load failure, missing or
  empty session laps, absent required lap columns, or a wholly unusable lap
  dataset.
- `500`: unexpected internal errors retain framework behavior and are not
  mislabeled as source outages.

## Controlled Testing Strategy

- `test_lap_analytics.py`: table-driven pure tests for every exclusion,
  overlap precedence, TrackStatus single/multiple codes, `IsAccurate` false or
  absent, wet compounds, exact 120% boundary, five-lap threshold, statistics,
  half-up rounding, reconciliation, ordering, competition ties, deltas,
  comparison reversal, and repeat determinism.
- Source-adapter and pure-policy tests must cover durations of 0 ns, a negative
  duration, 1 ns, and 499,999 ns as `invalid_timing`, and 500,000 ns and
  500,001 ns as valid timing publishing as 1 ms. Use otherwise eligible lap
  records to isolate timing validity; verify five minimum-duration laps yield
  median/mean/fastest of 1 ms and population standard deviation of 0 ms.
- `test_f1_data.py`: controlled DataFrames validate FastF1 column normalization,
  required data, null handling, status parsing, exact nanoseconds, loader split,
  cache reuse, selective load flags, and narrow exception translation.
- `test_pace_service.py`: mocks the loader and pure analyzer to prove exactly
  one load and one field analysis for each session, driver, and comparison
  operation and to distinguish unknown from insufficient drivers.
- `test_pace_api.py`: `TestClient` covers successful strict responses,
  malformed `422`, unsupported-session `404`, unknown-driver `404`, known
  insufficient `200`, source `503`, and uncaught internal `500` behavior.
- `test_openapi.py`: semantic operation-ID, strict-schema, path, unit, nullable,
  and error-response assertions without snapshotting generated OpenAPI prose or
  representation details.
- Existing routine tests remain under the autouse FastF1 network blocker. The
  integration marker stays deselected by default and skips without
  `F1_RUN_INTEGRATION=1`.
- Opted-in integration extends the application-owned pace service path for the
  2025 Italian Grand Prix Race and checks provenance, reconciliation, finite
  metrics, five-lap eligibility, stable ranking/deltas, and Monza identity.

## Scalability and Extension Boundaries

- Field analysis is immutable and reusable within an operation, allowing later
  frontend, strategy, ML, and AI-tool consumers to project trusted results
  without moving calculations into those consumers.
- Policy constants and status mapping are centralized and versioned, so later
  condition-, stint-, compound-, fuel-, or traffic-aware policies can coexist
  without changing v1 results.
- Complexity is bounded by race-lap volume and requires no parallelism,
  persistence, or distributed service. Future cross-request caching can wrap
  the application operation without changing the pure analytics contract.
- FastF1-specific schemas remain in `f1_data.py`; pure analytics consumes only
  normalized immutable values.

## Deferred Work

Frontend presentation, dynamic session support, databases, authentication,
Docker/deployment, telemetry, weather modeling, race-control messages,
condition segmentation, condition-aware anomaly detection, compound/stint
pace, degradation, fuel and traffic correction, strategy simulation,
predictive ML, and AI explanations remain outside this feature. Cache eviction
and production cache infrastructure also remain deferred.

## Phase 0 and Phase 1 Outputs

- [research.md](research.md) records resolved FastF1 and design decisions.
- [data-model.md](data-model.md) defines internal and public entities plus
  invariants.
- [contracts/openapi.yaml](contracts/openapi.yaml) defines the complete API
  contract while preserving existing routes.
- [quickstart.md](quickstart.md) defines offline and explicitly opted-in
  validation scenarios.

## Requirement Coverage

| Requirements | Planned coverage |
|---|---|
| FR-001–FR-002 | Approved FastF1 source, provenance, and Monza control tuple |
| FR-003–FR-010 | Driver/lap resources, canonical identity, complete classification, documented policy and limitations |
| FR-011–FR-019 | Uniform field analysis, metrics, publication arithmetic, ranks, ties, and deltas |
| FR-020–FR-027 | Explicit insufficiency, strict contracts, error distinctions, shared snapshot, deterministic projections |
| FR-028–FR-031 | Offline test guard, opt-in integration, existing compatibility, and ignored generated data |

## Complexity Tracking

No constitution violations require justification.
