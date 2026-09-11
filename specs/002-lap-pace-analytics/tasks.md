---

description: "Dependency-ordered implementation tasks for Lap Data & Driver Pace"
---

# Tasks: Lap Data & Driver Pace

**Input**: Design documents from `specs/002-lap-pace-analytics/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/openapi.yaml`, `quickstart.md`, and `checklists/requirements.md`

**Tests**: Automated tests are required by the feature specification. Write each
layer's tests first, confirm they fail for the intended missing behavior, then
implement that layer. Routine tests must remain offline and must not call the
real FastF1 session source.

**Organization**: Tasks are grouped by user story after the shared source
foundation. User Story 1 contains the reusable field-analysis core because a
correct individual `delta_to_best_ms` requires evaluating the complete session
field from the same snapshot. User Stories 2 and 3 add projections over that
same analysis rather than new loads or calculations.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it affects different files and has no
  dependency on another incomplete task in the same phase.
- **[Story]**: Maps the task to a user story in `spec.md`.
- Every task names the concrete file or directory it affects.

## Phase 1: Setup (Controlled Test Inputs)

**Purpose**: Add only the shared controlled test data needed by the new layers;
the Python project, dependencies, FastAPI app, pytest marker, and network guard
already exist and must not be reinitialized.

- [x] T001 Add reusable primitive FastF1-session/DataFrame fixtures and deterministic Monza participant/lap builders while preserving the autouse live-source blocker in `backend/tests/conftest.py`

**Checkpoint**: Analytics tests can construct controlled source snapshots
without network access, production cache creation, or new dependencies.

---

## Phase 2: Foundational FastF1 and Normalized Source Boundary

**Purpose**: Create the one-load application-owned source seam and isolate all
FastF1/Pandas adaptation before implementing pace policy.

**Critical**: Complete this phase before starting any user-story work.

- [x] T002 Write and run failing tests for a reusable session loader, one `fastf1.get_session`/`Session.load` call per invocation, existing selective load flags, cache reuse/retry, narrow source-error translation, and the unchanged `load_session_summary(...)` compatibility wrapper in `backend/tests/test_f1_data.py`
- [x] T003 Extract `load_session(...)` and refactor `load_session_summary(...)` to map its returned session without changing its signature, result, cache path, selective load flags, or exception boundary in `backend/app/f1_data.py`
- [x] T004 Define the minimal immutable participant, normalized source-lap, and field-analysis input records needed at the source/analytics boundary, without FastF1, Pandas, FastAPI, network, or cache imports, in `backend/app/lap_analytics.py`
- [x] T005 Write and run failing controlled-DataFrame tests for canonical/unique result driver numbers, exact integer-nanosecond LapTime normalization (0 ns, -1 ns, 1 ns, and 499,999 ns become null; 500,000 ns and 500,001 ns remain exact usable values), usable integral LapNumber normalization, pit-marker presence, ordered unique TrackStatus codes, nullable `IsAccurate`, diagnostic `Compound`, required columns, empty/wholly unusable laps, and participant-unmatched rows in `backend/tests/test_f1_data.py`
- [x] T006 Implement participant and lap normalization from one loaded session, requiring usable LapTime of at least 500,000 ns and mapping smaller or otherwise unusable LapTime/LapNumber to the normalized invalid-timing identity without dropping source rows, preserving source order/diagnostics, and raising `DataSourceUnavailableError` for the approved dataset-integrity failures in `backend/app/f1_data.py`
- [x] T007 Run the offline foundational checkpoint for `backend/tests/test_f1_data.py`, `backend/tests/test_sessions.py`, and `backend/tests/test_health.py`, confirming existing session-summary/health behavior and the zero-live-source guard remain intact

**Checkpoint**: One application-owned FastF1 load can produce both the existing
session summary and normalized immutable analytics inputs; FastF1/Pandas details
do not cross into the analytics core.

---

## Phase 3: User Story 1 - Inspect a Driver's Representative Race Pace (Priority: P1) MVP

**Goal**: Return one known driver's complete, explainable lap classifications
and representative pace summary, including a delta to the true session best,
from one shared field analysis.

**Independent Test**: Using a controlled supported-session snapshot, request a
known driver and verify every source lap is classified exactly once, counts
reconcile, eligible metrics/delta are correct, insufficient data is explicit,
and repeated results are identical after exactly one source load and one field
analysis.

### Pure Policy and Classification Tests

- [x] T008 [US1] Write and run failing table-driven tests for the exact first-match precedence `invalid_timing`, `lap_one_start`, `pit_in`, `pit_out`, `disrupted_status`, `anomalous_pace`; unusable LapTime or LapNumber as `invalid_timing`, explicitly covering source durations 0 ns, -1 ns, 1 ns, and 499,999 ns through normalized null timing; 500,000 ns and 500,001 ns pass timing validity and publish as 1 ms when other rules allow; Lap 1; both pit markers; disruptive TrackStatus codes `2`, `4`, `5`, `6`, `7` alone and in multi-code values; missing/unknown status diagnostics; and overlapping exclusions in `backend/tests/test_lap_analytics.py`
- [x] T009 [US1] Implement the immutable v1 policy/result records, `representative-race-pace-v1` metadata, six exclusion reasons, five verified disruptive-status mappings, and deterministic diagnostic ordering in `backend/app/lap_analytics.py`
- [x] T010 [US1] Implement first-match structural/status classification and the exact driver-relative anomaly pass (`lap_time_ns * 5 > fastest_ns * 6`), keeping equality at 120%, `IsAccurate` diagnostic-only, Compound non-excluding, and the mixed-condition limitation unchanged in `backend/app/lap_analytics.py`
- [x] T011 [US1] Run and satisfy the classification subset in `backend/tests/test_lap_analytics.py`, including one primary reason per excluded lap, source-count reconciliation, stable lap ordering, and repeated deterministic output

### Metrics and Shared Field Analysis Tests

- [x] T012 [US1] Write and run failing tests for exactly-five versus fewer-than-five eligibility, median/mean/fastest/population-standard-deviation calculations from unrounded nanoseconds, local high-precision decimal arithmetic, half-up integer-millisecond publication including five 500,000 ns laps yielding median/mean/fastest of 1 ms and population standard deviation of 0 ms; prove median/mean/fastest remain positive for representative inputs at or above 500,000 ns, and rejection of NaN/infinity/fabricated unavailable values in `backend/tests/test_lap_analytics.py`
- [x] T013 [US1] Implement full-precision metric aggregation, population standard deviation, explicit local decimal context, and deterministic `ROUND_HALF_UP` millisecond publication helpers without clamping (representative durations are at least 500,000 ns; median/mean/fastest publish at least 1 ms, while population standard deviation and deltas may be zero) in `backend/app/lap_analytics.py`
- [x] T014 [US1] Write and run failing shared-field tests covering every results participant, participants with zero rows, all-excluded drivers, stable numeric driver ordering, published-median ties, competition ranks (`1, 1, 3`), non-negative delta-to-best, best delta zero, different controlled input ordering, and complete count invariants in `backend/tests/test_lap_analytics.py`
- [x] T015 [US1] Implement `analyze_session_field(...)` to classify all participant laps once, publish eligible/insufficient summaries, order eligible then insufficient drivers deterministically, assign published-median competition ranks/ties, and calculate delta-to-best from published medians in `backend/app/lap_analytics.py`
- [x] T016 [US1] Run and satisfy all pure deterministic analytics tests in `backend/tests/test_lap_analytics.py`, confirming the module imports no FastAPI, FastF1, Pandas, network, or cache APIs

### Application Service and Strict Contracts

- [x] T017 [P] [US1] Write and run failing service tests proving an individual-driver operation performs exactly one loader call, one summary/source normalization, and one shared field analysis before selecting the known driver; distinguish unknown drivers from known insufficient drivers and preserve unexpected exceptions in `backend/tests/test_pace_service.py`
- [x] T018 [P] [US1] Write and run failing contract tests for strict extra-field rejection, canonical driver-number identity, policy literals, lap inclusion/exclusion state, sample reconciliation, and available-versus-insufficient nullable-field invariants in `backend/tests/test_pace_api.py`
- [x] T019 [US1] Implement the shared strict analytics contract vocabulary and validators—context, policy, driver identity, lap classification, exclusion/sample counts, pace metrics, driver summary, and individual-driver response—while reusing existing session/source components in `backend/app/pace_models.py`
- [x] T020 [US1] Implement the one-load/one-analysis application operation and individual-driver response projection, including `driver_not_found` distinction without reloading or recomputing the field, in `backend/app/pace_service.py`

### Individual Driver API

- [x] T021 [P] [US1] Write and run failing TestClient cases for the driver resource success shape, every classified lap, known `insufficient_data` HTTP 200, malformed driver `422` before loading, unsupported session `404` before loading, unknown driver `404` after one analysis, expected source `503`, uncaught internal `500`, and repeated equality in `backend/tests/test_pace_api.py`
- [x] T022 [P] [US1] Add failing semantic OpenAPI tests for the nested driver path, `getDriverPaceAnalysis`, canonical driver-number pattern, response/error references, strict analytics schemas, nullability, units, and policy constants without snapshotting generated prose/order in `backend/tests/test_openapi.py`
- [x] T023 [US1] Add the synchronous thin individual-driver route with existing session resolution, canonical driver path validation, stable `404`/`503` error responses, and operation ID `getDriverPaceAnalysis` in `backend/app/main.py`
- [x] T024 [US1] Run the complete offline User Story 1 checkpoint across `backend/tests/test_lap_analytics.py`, `backend/tests/test_f1_data.py`, `backend/tests/test_pace_service.py`, `backend/tests/test_pace_api.py`, `backend/tests/test_openapi.py`, `backend/tests/test_health.py`, and `backend/tests/test_sessions.py`

**Checkpoint**: User Story 1 is independently usable: one driver receives
complete evidence and a correct field-relative delta from one shared snapshot,
while unknown and insufficient drivers remain distinct.

---

## Phase 4: User Story 2 - Compare Two Drivers on the Same Pace Basis (Priority: P2)

**Goal**: Compare ordered Driver A and Driver B summaries from the same shared
field analysis using the published-median A-minus-B convention.

**Independent Test**: Compare two controlled eligible drivers, reverse the
operand order, compare a driver with itself, and include an insufficient driver;
verify signs, magnitude, outcome, winner availability, summaries, and exactly
one source load/field analysis per request.

### Tests for User Story 2

- [x] T025 [US2] Write and run failing service tests for available, reversed, tied, same-driver, insufficient, and unknown-driver comparisons, asserting `delta_ms = A published median - B published median` and one shared load/analysis in `backend/tests/test_pace_service.py`

### Implementation for User Story 2

- [x] T026 [US2] Add strict comparison result/response contracts and implement comparison projection from the existing field analysis, including null result fields for insufficiency and no extra loading or pace recomputation, in `backend/app/pace_models.py` and `backend/app/pace_service.py`
- [x] T027 [P] [US2] Write and run failing TestClient cases for directional success, reversed sign, tie/same-driver behavior, insufficient HTTP 200, malformed `422`, unsupported/unknown `404`, expected `503`, and uncaught `500` behavior in `backend/tests/test_pace_api.py`
- [x] T028 [P] [US2] Add failing semantic OpenAPI tests for the ordered comparison path, `compareDriverPace`, both canonical driver selectors, strict response schema, signed delta, nullable insufficiency fields, and error references in `backend/tests/test_openapi.py`
- [x] T029 [US2] Add the synchronous thin comparison route that calls one service operation and preserves operand order/error semantics with operation ID `compareDriverPace` in `backend/app/main.py`
- [x] T030 [US2] Run the offline User Story 2 checkpoint in `backend/tests/test_pace_service.py`, `backend/tests/test_pace_api.py`, and `backend/tests/test_openapi.py`, plus the User Story 1 regression set in `backend/tests/test_lap_analytics.py`

**Checkpoint**: User Stories 1 and 2 work from the same policy and field-analysis
primitive; reversing operands changes only the signed comparison conclusion,
not either driver's facts.

---

## Phase 5: User Story 3 - Identify the Strongest Overall Representative Pace (Priority: P3)

**Goal**: Expose the compact full-field ordering that identifies the strongest
eligible representative pace and retains insufficient participants without
invented metrics.

**Independent Test**: Request a controlled session field and verify every
results participant appears once, available drivers are ordered/ranked by
published median, ties and deltas are correct, insufficient drivers follow in
numeric order, and the request performs one load and one analysis.

### Tests for User Story 3

- [x] T031 [US3] Write and run failing service tests for the complete session projection, every-participant inclusion, available/insufficient ordering, published-median ties and competition ranks, best-driver zero delta, provenance/context preservation, repeated equality, and one loader/analyzer invocation in `backend/tests/test_pace_service.py`

### Implementation for User Story 3

- [x] T032 [US3] Implement the strict session pace response and compact full-field projection directly from the existing shared analysis without per-driver reloads or recomputation in `backend/app/pace_models.py` and `backend/app/pace_service.py`
- [x] T033 [P] [US3] Write and run failing TestClient cases for the field resource success/order/determinism, unsupported and malformed requests before source access, expected source `503`, and uncaught internal `500` behavior in `backend/tests/test_pace_api.py`
- [x] T034 [P] [US3] Add failing semantic OpenAPI tests for the session pace path, `getSessionPaceAnalysis`, strict field-response schema, policy metadata, ordering-relevant fields, and stable `404`/`422`/`503` references in `backend/tests/test_openapi.py`
- [x] T035 [US3] Add the synchronous thin session pace route with operation ID `getSessionPaceAnalysis`, reusing the existing support map and common error response boundary in `backend/app/main.py`
- [x] T036 [US3] Run the offline User Story 3 checkpoint in `backend/tests/test_pace_service.py`, `backend/tests/test_pace_api.py`, and `backend/tests/test_openapi.py`, then rerun all User Story 1 and 2 analytics regressions under `backend/tests/`

**Checkpoint**: All three analytics resources project one deterministic field
analysis and answer the individual, comparison, and strongest-field questions
without changing the source or policy boundary.

---

## Phase 6: Documentation and Complete Verification

**Purpose**: Reconcile documentation/contracts, preserve existing behavior,
prove routine isolation, and perform the separately authorized real Monza check.

- [x] T037 [P] Extend the marked opt-in Monza validation through the application-owned pace service, checking 2025 Italian Grand Prix Race/Monza identity, FastF1 provenance, participants, usable eligible metrics, finite integer publications, count reconciliation, rankings, and deltas in `backend/tests/test_f1_data_integration.py`
- [x] T038 [P] Document the implemented lap/pace purpose, three analytics resources, policy/sample semantics, condition-unaware 120% limitation, one-load shared analysis, routine offline tests, and opt-in real validation without overclaiming deferred work in `README.md`
- [x] T039 [P] Update the deterministic analytics/source/service/API data flow and current demo capability while preserving repository-local ignored cache guidance and deferred condition/stint/AI scope in `docs/architecture.md` and `docs/demo-v0.1.md`
- [x] T040 [P] Review the implemented behavior against every command and expected result in `specs/002-lap-pace-analytics/quickstart.md`, correcting only materially stale instructions and preserving explicit real-source opt-in
- [x] T041 Run the frozen offline routine gates from `backend/`: collect tests, run the complete pytest suite with `F1_RUN_INTEGRATION` unset, prove integration tests are deselected by default, and explicitly select `-m integration` without opt-in to prove safe skips under `backend/tests/` and `backend/pyproject.toml`
- [x] T042 Run `uv run --offline --frozen --no-sync ruff format --check .` and `uv run --offline --frozen --no-sync ruff check --no-cache .` from `backend/`, fixing only feature-related findings in `backend/app/` and `backend/tests/`
- [x] T043 Compare generated FastAPI OpenAPI semantics with `specs/002-lap-pace-analytics/contracts/openapi.yaml`, run the health/session-summary/OpenAPI regression tests, and reconcile only meaningful implementation mismatches in `backend/app/main.py`, `backend/app/models.py`, `backend/app/pace_models.py`, and `backend/tests/test_openapi.py`
- [x] T044 Run exactly `F1_RUN_INTEGRATION=1 uv run --frozen --no-sync pytest -m integration` from `backend/`; if it fails, classify the application, test, provider/network, environment/dependency, or stale-source assumption before changing `backend/app/` or `backend/tests/`
- [x] T045 Execute the complete acceptance flow in `specs/002-lap-pace-analytics/quickstart.md`; verify real control-resource determinism, error boundaries, health/session-summary compatibility, `git diff --check`, Git status, ignored/untracked `backend/cache/fastf1/`, absent `backend/data/`, unchanged `backend/pyproject.toml` and `backend/uv.lock`, unchanged feature-001 contract, no deferred-scope work, and final compliance with `.specify/memory/constitution.md`

**Final Checkpoint**: Routine tests are offline, the explicit Monza integration
has passed, generated and handwritten contracts are semantically reconciled,
existing endpoints remain compatible, cache/data/dependency hygiene is clean,
and the implementation matches the approved feature artifacts.

---

## Dependencies and Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately and adds no runtime behavior.
- **Foundation (Phase 2)**: Depends on T001 and blocks all user stories. Execute
  T002-T007 in order so loader compatibility is proven before source
  normalization and analytics policy.
- **User Story 1 (Phase 3)**: Depends on T007. Its internal order is
  classification -> metrics -> shared field analysis -> service/contracts ->
  driver API.
- **User Story 2 (Phase 4)**: Depends on T024 because comparison projects the
  complete field analysis and shared summary contract delivered by US1.
- **User Story 3 (Phase 5)**: Depends on T024. It may be developed alongside
  US2 only with coordination because both stories edit `pace_service.py`,
  `pace_models.py`, `main.py`, and shared test files; the numeric task order is
  the safe single-developer sequence.
- **Documentation and Complete Verification (Phase 6)**: Depends on T030 and
  T036. T041-T045 are sequential gates; T044 is the only task authorized to
  contact real FastF1.

### User Story Dependency Graph

```text
Setup -> FastF1/normalized foundation -> US1 (P1 MVP)
                                         |-> US2 (P2 comparison)
                                         `-> US3 (P3 field resource)
US2 + US3 -> documentation/routine gates -> opt-in integration -> final acceptance
```

### Within Each User Story

- Write and run the named tests first; confirm failure is caused by missing
  intended behavior rather than test setup or accidental source access.
- Keep FastF1/Pandas adaptation in `f1_data.py` and pure calculations in
  `lap_analytics.py`.
- Complete classification before metric aggregation and metric aggregation
  before field ranking/deltas.
- Complete the shared field analysis before any service projection.
- Define strict contracts before routes return them; services before thin API
  handlers.
- Stop at each checkpoint and localize failures before starting the next layer.

## Parallel Opportunities

- **US1**: T017 and T018 can run in parallel after T016; T021 and T022 can run
  in parallel after T019-T020.
- **US2**: T027 and T028 can run in parallel after T026.
- **US3**: T033 and T034 can run in parallel after T032.
- **Final phase**: T037-T040 can run in parallel after all three stories because
  they affect separate test/documentation files. T041-T045 remain ordered
  verification gates.
- US2 and US3 are conceptually independent projections after US1, but parallel
  implementation requires explicit ownership coordination for their shared
  production and test files; otherwise follow task-number order.

## Parallel Examples by User Story

### User Story 1

```text
Parallel test batch after the pure core passes:
- T017: backend/tests/test_pace_service.py
- T018: backend/tests/test_pace_api.py

Parallel API-boundary test batch after contracts/service exist:
- T021: backend/tests/test_pace_api.py
- T022: backend/tests/test_openapi.py
```

### User Story 2

```text
Parallel boundary tests after comparison projection:
- T027: backend/tests/test_pace_api.py
- T028: backend/tests/test_openapi.py
```

### User Story 3

```text
Parallel boundary tests after session projection:
- T033: backend/tests/test_pace_api.py
- T034: backend/tests/test_openapi.py
```

## Verification Gates

1. **T007 - Source foundation**: loader compatibility, normalized source
   integrity, and existing health/session regressions pass offline.
2. **T011/T016 - Pure analytics**: classifications, metrics, reconciliation,
   ranks, ties, deltas, and determinism pass without framework/provider imports.
3. **T024 - Driver MVP**: one-load individual response and all error/contract
   semantics pass offline.
4. **T030 - Comparison**: signed/reversed/tied/insufficient comparison behavior
   passes offline.
5. **T036 - Session field**: complete ordered field response and all analytics
   regressions pass offline.
6. **T041-T043 - Routine acceptance**: zero live source access, safe integration
   deselection/skip, Ruff, existing endpoint compatibility, and OpenAPI semantic
   reconciliation pass.
7. **T044 - Real-source acceptance**: explicitly opted-in Monza validation is
   run only after all offline gates pass.
8. **T045 - Repository acceptance**: quickstart, determinism, Git/cache/data/
   dependency hygiene, scope, and constitution checks pass.

## Requirement and Success-Criterion Coverage

| Requirement or criterion | Task coverage |
|---|---|
| FR-001-FR-002 | T003-T007, T037, T044-T045 |
| FR-003-FR-010 | T008-T011, T018-T024 |
| FR-011-FR-015 | T012-T016, T018-T020 |
| FR-016-FR-020 | T014-T016, T020, T025-T036 |
| FR-021-FR-027 | T008-T024, T031-T036, T043 |
| FR-028-FR-031 | T001-T007, T021-T024, T027-T030, T033-T045 |
| SC-001 | T014-T016, T031-T037, T044-T045 |
| SC-002 | T025-T030, T037, T044-T045 |
| SC-003 | T008-T016, T021, T037 |
| SC-004 | T012-T024, T031-T037 |
| SC-005 | T005-T011, T024 |
| SC-006 | T011, T014-T016, T021, T031-T037 |
| SC-007 | T005-T016, T018-T021, T037 |
| SC-008 | T008-T016, T018-T024, T037 |
| SC-009 | T001-T007, T037, T041, T044-T045 |
| SC-010 | T003, T007, T024, T030, T036, T043-T045 |

All functional requirements and success criteria have at least one controlled
test or verification task and one implementation/source task where applicable.

## Implementation Strategy

### MVP First: User Story 1

1. Complete T001-T007 to establish the compatible source boundary.
2. Complete T008-T016 to build and verify the pure shared field-analysis core.
3. Complete T017-T024 to expose the independently useful driver resource.
4. Stop and review the MVP before adding the comparison and field projections.

### Incremental Delivery

1. **Foundation**: one FastF1 load plus normalized immutable inputs.
2. **US1**: complete lap evidence and individual pace with true field delta.
3. **US2**: directional comparison as a projection of the same analysis.
4. **US3**: compact strongest-pace field ordering from the same analysis.
5. **Acceptance**: documentation, offline gates, opt-in Monza validation, and
   repository hygiene review.

### Single-Developer Sequence

Execute tasks in numeric order. Do not run T044 before all offline gates pass.
If the real integration fails, stop at its classification gate rather than
editing code immediately.

## Expected Implementation Files

Production code:

- `backend/app/f1_data.py`
- `backend/app/lap_analytics.py`
- `backend/app/pace_models.py`
- `backend/app/pace_service.py`
- `backend/app/main.py`

Tests:

- `backend/tests/conftest.py`
- `backend/tests/test_f1_data.py`
- `backend/tests/test_lap_analytics.py`
- `backend/tests/test_pace_service.py`
- `backend/tests/test_pace_api.py`
- `backend/tests/test_openapi.py`
- `backend/tests/test_f1_data_integration.py`

Documentation:

- `README.md`
- `docs/architecture.md`
- `docs/demo-v0.1.md`
- `specs/002-lap-pace-analytics/quickstart.md` only if implementation validation
  proves an instruction materially stale

`backend/app/models.py` is a compatibility dependency and should change only if
T043 proves a meaningful approved contract mismatch. `backend/pyproject.toml`,
`backend/uv.lock`, and `specs/001-backend-f1-data-access/contracts/openapi.yaml`
are expected to remain unchanged.

## Notes

- Do not add dependencies or run live FastF1 in any routine task.
- Do not duplicate source loading, field analysis, or driver calculations among
  resources.
- Do not use FastF1 convenience filtering as the representative-lap policy.
- Do not add frontend, database, authentication, deployment, AI, ML, strategy,
  telemetry, weather, race-control messages, or other deferred work.
- Do not commit generated FastF1 cache, local data, secrets, or tooling output.
- No unresolved task-level decision remains; implementation names below the
  approved module/function boundaries may follow existing code style without
  changing the specified behavior or contracts.
