# Tasks: Pit-Lane Visits & Lap-Boundary Race Context

**Input**: Design documents from specs/004-pit-race-context/
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml, quickstart.md

**Tests**: Tests are required by the approved specification and plan. Each behavioral group begins with controlled failing tests, followed by the smallest implementation needed to satisfy them.

**Organization**: The responsibility-package migration is a bounded preliminary group. Gate A is a hard blocker: no Feature 004 normalization, analytics, model, service, route, or test work may start until every Gate A check passes and a fresh independent reviewer approves the migration.

## Phase 1: Group A — Responsibility-Package Migration

**Purpose**: Move existing Feature 001–003 modules into responsibility-based packages without changing behavior, policies, public contracts, algorithms, loader flags, or dependencies.

- [ ] T001 Capture the pre-migration generated OpenAPI document and route/operation/schema inventory from backend/app/main.py as an exact comparison baseline at /tmp/feature-004-pre-migration-openapi.json before moving any module
- [ ] T002 Create declaration-only backend/app/analytics/__init__.py and move backend/app/lap_analytics.py to backend/app/analytics/lap_analytics.py and backend/app/stint_analytics.py to backend/app/analytics/stint_analytics.py, changing only import paths required by the moves
- [ ] T003 Create declaration-only backend/app/models/__init__.py and move backend/app/models.py to backend/app/models/session_models.py, backend/app/pace_models.py to backend/app/models/pace_models.py, and backend/app/stint_models.py to backend/app/models/stint_models.py, changing only import paths required by the moves
- [ ] T004 Create declaration-only backend/app/data/__init__.py and move backend/app/f1_data.py to backend/app/data/f1_data.py, changing only required imports and the relative path-depth expression needed to keep FASTF1_CACHE_DIR resolving to backend/cache/fastf1
- [ ] T005 Create declaration-only backend/app/services/__init__.py and move backend/app/pace_service.py to backend/app/services/pace_service.py and backend/app/stint_service.py to backend/app/services/stint_service.py, changing only import paths required by the moves
- [ ] T006 Update backend/app/main.py to import the moved data, model, and service modules while preserving app.main:app, every existing route, operation ID, response schema, error mapping, supported-session selector, and loader behavior
- [ ] T007 [P] Update only migration-required imports, module-string assertions, and patch targets in backend/tests/test_f1_data.py, backend/tests/test_health.py, backend/tests/test_sessions.py, and backend/tests/test_openapi.py without changing test meaning or expected behavior
- [ ] T008 [P] Update only migration-required imports and patch targets in backend/tests/test_pace_api.py and backend/tests/test_pace_service.py without changing Feature 002 expectations
- [ ] T009 [P] Update only migration-required imports and patch targets in backend/tests/test_stint_analytics.py, backend/tests/test_stint_api.py, and backend/tests/test_stint_service.py without changing Feature 003 expectations
- [ ] T010 [P] Update only migration-required imports and patch targets in backend/tests/test_lap_analytics.py and backend/tests/test_f1_data_integration.py without changing controlled fixture or integration expectations

## Phase 2: Gate A — Migration Verification and Independent Approval

**Hard gate**: T011–T017 must all pass. T017 must record fresh independent approval. T018 and every later task are blocked until then.

- [ ] T011 Run an import smoke test for app.main and every moved module under backend/app/data/, backend/app/analytics/, backend/app/models/, and backend/app/services/, confirming no compatibility wrapper or package re-export is required
- [ ] T012 Run the complete existing Feature 001–003 offline regression suite in backend/tests/ and confirm unchanged routes, schemas, policies, supported-session behavior, and 404/422/503/500 error semantics
- [ ] T013 Run Ruff format checking and Ruff lint over backend/app/ and backend/tests/ without applying unrelated formatting or cleanup
- [ ] T014 Generate OpenAPI from backend/app/main.py after the migration and require exact equality with /tmp/feature-004-pre-migration-openapi.json, including paths, operation IDs, and schemas
- [ ] T015 Verify backend/app/data/f1_data.py still resolves FASTF1_CACHE_DIR to backend/cache/fastf1 and verify backend/pyproject.toml and backend/uv.lock have no diff
- [ ] T016 Audit the migration diff for only file moves, declaration-only package markers, required import/module-path changes, and cache-path preservation, then run git diff --check from the repository root
- [ ] T017 Obtain fresh independent Codex review approval of the bounded migration diff in backend/app/ and backend/tests/, explicitly confirming Feature 001–003 behavior preservation and recording approval before T018 begins

**Checkpoint**: Responsibility packages exist, the migration is independently verified, and no Feature 004 behavior has been introduced.

## Phase 3: Group B — Feature 004 Provider Normalization

**Purpose**: Define application-owned immutable Feature 004 input facts and map one already-loaded public FastF1 Session snapshot into them. Provider-specific FastF1, Pandas, NumPy, missing-value, scalar, and duplicate-label behavior ends at this boundary.

- [ ] T018 Extend controlled provider fixtures in backend/tests/conftest.py with authoritative results, participant classification, lap completion, Position, PitInTime, PitOutTime, TrackStatus, FastF1Generated, Compound, Stint, duplicate-result, and duplicate-lap evidence needed by Feature 004 tests
- [ ] T019 Add failing provider-normalization tests in backend/tests/test_f1_data.py covering the authoritative results roster, participants with no laps, lap rows that cannot invent participants, Python built-in scalar conversion, exact integer-nanosecond preservation, NaT/NaN/infinity/malformed values, optional missing fields, duplicate consumed labels, duplicate rows/results, Position, FastF1Generated including absent assertions, Compound, Stint, and raw FastF1 TrackStatus normalization into row-level green/yellow/safety_car/virtual_safety_car/virtual_safety_car_ending/red_flag/unknown evidence that preserves first-observed code order while de-duplicating within one source row, including unknown-code retention, missing/malformed availability, no raw-code leakage, and the approved is_disrupted truth table: known disruption true, trustworthy fully understood non-disrupted evidence false, and missing/malformed/unknown-only/indeterminate evidence null with unknown never treated as green
- [ ] T020 Define the minimal immutable normalized Feature 004 input enums and value objects in backend/app/analytics/race_context_analytics.py, separating participant/result facts, source lap-row occurrences, evidence quality, and exact nanosecond timing without importing FastF1, Pandas, FastAPI, or Pydantic
- [ ] T021 Extend backend/app/data/f1_data.py with Feature 004 participant/result normalization and provider-scalar conversion that distinguishes missing from invalid evidence and preserves authoritative participant identity and classification context
- [ ] T022 Complete the one-snapshot Feature 004 mapper in backend/app/data/f1_data.py for every source lap-row occurrence, exact lap-completion/PitInTime/PitOutTime nanoseconds, provider Position, FastF1Generated, Compound, Stint, multiplicity, and source occurrence identity; at this provider boundary parse raw FastF1 TrackStatus codes, distinguish missing/malformed evidence, map supported codes to normalized green/yellow/safety_car/virtual_safety_car/virtual_safety_car_ending/red_flag/unknown statuses, retain unknown codes as unknown, preserve first-observed code order while de-duplicating within each row, establish row-level availability and approved nullable is_disrupted semantics, and prevent raw provider codes or objects from entering analytics
- [ ] T023 Run backend/tests/test_f1_data.py and an import/type audit proving the Feature 004 mapper consumes one already-loaded session snapshot and emits only Python/application-owned immutable facts into backend/app/analytics/race_context_analytics.py
- [ ] T024 Obtain fresh independent review of the provider-boundary changes in backend/app/data/f1_data.py, backend/app/analytics/race_context_analytics.py, backend/tests/conftest.py, and backend/tests/test_f1_data.py before central analytics work proceeds

**Checkpoint**: Feature 004 has a reviewed, provider-isolated, immutable normalized input from one session snapshot.

## Phase 4: Group C1 — User Story 2: Trusted Lap-Boundary Race Context (Priority: P1)

**Goal**: Derive trustworthy lap-completion context, lap leaders, laps behind, and equal-distance time deficits without live-gap, telemetry, interpolation, or prediction semantics.

**Independent Test**: Pure analytics tests can supply normalized facts directly and verify same-lap leader/reference behavior, lapped-driver semantics, status context, exact-nanosecond subtraction, and deterministic results without FastF1 or the API.

- [ ] T025 [US2] Add failing pure tests in backend/tests/test_race_context_analytics.py for participant/lap evidence consolidation using already-normalized row-level TrackStatus statuses, availability, and is_disrupted values; cover identical and contradictory duplicate lap rows, canonical normalized status ordering, reconciliation of multiple source rows for one driver/lap, and explicit conflict/unavailability when no single trustworthy consolidated interpretation exists, without supplying or interpreting raw FastF1 status codes
- [ ] T026 [US2] Add failing pure tests in backend/tests/test_race_context_analytics.py for unique trusted Position 1 leader selection, equal timestamps, positive equal-distance deficit, contradictory negative deficit, missing/duplicate/conflicting leader evidence, laps_behind at the selected driver completion timestamp, and no interpolation or prediction
- [ ] T027 [US2] Add failing tests in backend/tests/test_race_context_analytics.py for generated-row audit preservation without trusted timing use, half-up millisecond publication of session timestamps and derived deficits, proof that exact nanosecond endpoints are subtracted before rounding, source-row permutation determinism, three identical executions, and an architecture check that analytics imports no FastF1, Pandas, FastAPI, or Pydantic
- [ ] T028 [US2] Implement deterministic lap-evidence consolidation in backend/app/analytics/race_context_analytics.py by consuming only already-normalized row-level TrackStatus statuses, availability, and is_disrupted evidence from the provider boundary; preserve canonical normalized status ordering and multiplicity/conflict/provenance, reconcile multiple source rows for one driver/lap, and expose conflict or unavailability when no single trustworthy consolidated interpretation exists without parsing raw codes, repeating the provider truth table, or treating unknown as green
- [ ] T029 [US2] Implement trusted lap qualification, unique Position 1 lap-leader identification, laps_behind evaluation, lap-completion session-time publication, and equal_distance_time_deficit derivation in backend/app/analytics/race_context_analytics.py using exact integer nanoseconds and final ROUND_HALF_UP integer-millisecond publication only
- [ ] T030 [US2] Implement canonical lap-context ordering, explicit available/not_applicable/unavailable deficit states, leader/lap reference consistency, generated-evidence audit retention, and invalid/contradictory evidence handling in backend/app/analytics/race_context_analytics.py
- [ ] T031 [US2] Run the User Story 2 slice in backend/tests/test_race_context_analytics.py and confirm it is deterministic, provider-independent, and free of live-gap or telemetry claims

**Checkpoint**: User Story 2 is independently verifiable at the pure domain layer.

## Phase 5: Group C2 — User Story 1: Complete Pit-Lane Visits (Priority: P1)

**Goal**: Associate trustworthy entry and exit evidence into complete visits and attach only the specified in-lap/out-lap completion context.

**Independent Test**: Pure analytics tests can supply normal, multiple, and absent pit-boundary observations and verify complete visit association, elapsed time, transition context, and source-backed compound/stint changes.

- [ ] T032 [US1] Add failing pure tests in backend/tests/test_race_context_analytics.py for a normal complete visit, multiple visits, no visit, exact entry-to-exit elapsed time, entry/in-lap and exit/out-lap context with no fallback, same and changed reported compound/stint values, unavailable transition values, and canonical pit-evidence ordering
- [ ] T033 [US1] Implement source-backed pit-boundary candidates and the conservative chronological complete-visit association path in backend/app/analytics/race_context_analytics.py without adjacency-only pairing, fabricated boundaries, or Monza-specific assumptions
- [ ] T034 [US1] Implement exact-nanosecond pit-boundary session-time and entry-to-exit elapsed derivation with final ROUND_HALF_UP integer-millisecond publication, in-lap/out-lap context attachment, reported compound/stint before/after values and change flags, boundary occurrence accounting, and canonical complete-visit ordering in backend/app/analytics/race_context_analytics.py
- [ ] T035 [US1] Run the User Story 1 slice in backend/tests/test_race_context_analytics.py and confirm no stationary-service-time or confirmed-tire-change claim is introduced

**Checkpoint**: Complete pit visits are independently verifiable from normalized facts and reuse the lap context derived under one policy.

## Phase 6: Group C3 — User Story 3: Incomplete, Conflicting, and Unavailable Evidence (Priority: P2)

**Goal**: Preserve every source occurrence and expose unpaired, conflicting, generated, missing, and unusable evidence explicitly.

**Independent Test**: Pure analytics tests can inject pit-lane starts, terminal retirements, competing boundaries, generated rows, malformed identities, and missing evidence and verify that nothing is fabricated or silently discarded.

- [ ] T036 [US3] Add failing tests in backend/tests/test_race_context_analytics.py for initial unpaired exits, terminal unpaired entries, duplicate boundaries, competing boundaries, equal/reversed timestamps, unusable boundary timestamps, contradictory evidence, unavailable evidence, unassociated evidence, and exact source-occurrence accounting
- [ ] T037 [US3] Add failing tests in backend/tests/test_race_context_analytics.py for non-starters, retirement after valid earlier context, generated rows, invalid participant/lap identities, missing timing/position/status/compound/stint/classification context, unavailable interpretation when required classification is missing, identical versus contradictory lap duplicates, and canonical participant accounting from results only
- [ ] T038 [US3] Extend the conservative chronological pit state machine in backend/app/analytics/race_context_analytics.py to emit unpaired_entry, unpaired_exit, conflicting, and unavailable evidence while consolidating trustworthy duplicate boundaries and accounting for every source occurrence exactly once
- [ ] T039 [US3] Implement non-starter, retirement, invalid-identity, generated, missing, duplicate, and contradictory lap-evidence handling in backend/app/analytics/race_context_analytics.py without allowing generated rows to establish trusted completion, leader, deficit, laps behind, or pit association
- [ ] T040 [US3] Add cross-case source-row permutation and three-run repeatability assertions to backend/tests/test_race_context_analytics.py for incomplete/conflicting pit and lap evidence, ensuring stable identities, multiplicity, ordering, counts, and availability states
- [ ] T041 [US3] Run the User Story 3 slice in backend/tests/test_race_context_analytics.py and reconcile every trustworthy, unusable, duplicate, and conflicting occurrence with exactly one auditable outcome

**Checkpoint**: Missing and contradictory evidence remain explicit and auditable; no source fact is repaired or invented.

## Phase 7: Group C4 — User Story 4: One Reusable Session-Wide Analysis (Priority: P2)

**Goal**: Assemble one immutable central result that owns shared race-context policy and supports both v1 projections plus future Feature 005 reuse.

**Independent Test**: One analysis invocation over normalized input yields authoritative participant summaries, complete driver detail facts, canonical ordering, and reusable central results without view-specific recalculation.

- [ ] T042 [US4] Add failing tests in backend/tests/test_race_context_analytics.py for one central session-wide result, exactly one authoritative participant summary per results participant, zero-evidence participants, state counts, latest trustworthy context, canonical participant/lap/pit ordering, and projection-ready facts without raw provider rows
- [ ] T043 [US4] Implement the central race-context analysis coordinator and participant-summary derivation in backend/app/analytics/race_context_analytics.py by composing the reviewed lap and pit transformations once, without a giant function, view-specific analytics, or speculative interfaces
- [ ] T044 [US4] Run all of backend/tests/test_race_context_analytics.py and confirm central result reuse, deterministic ordering, exact evidence accounting, repeatability, and Feature 005-ready domain ownership
- [ ] T045 [US4] Obtain fresh independent Codex review of backend/app/analytics/race_context_analytics.py and backend/tests/test_race_context_analytics.py, focusing on duplicate policy, pit association, leader/lapped semantics, exact timing, generated evidence, determinism, and absence of duplicated or misplaced analytics

**Checkpoint**: Central analytics are independently approved before public models, orchestration, or transport are added.

## Phase 8: Group D — Strict Public Models

**Purpose**: Define strict projection/validation models only. Validators reject invalid structures but never normalize provider data, calculate race facts, round, sort, deduplicate, pair, or repair.

- [ ] T046 [US2] Add failing direct-construction tests in backend/tests/test_race_context_api.py for participant/classification, lap context, leader reference, TrackStatus enum validity/uniqueness/availability/disruption truth-table consistency and preservation of supplied source order without enum-order invention or reconstruction of original observation provenance, laps_behind and available/not_applicable/unavailable equal-distance state/value combinations, strict integer milliseconds, bool-as-int rejection, numeric-string rejection, and NaN/infinity rejection
- [ ] T047 [US1] Add failing direct-construction tests in backend/tests/test_race_context_api.py for complete pit visits, boundary/context provenance, exact evidence counts, reported compound/stint changes, entry_to_exit_elapsed_ms, rejection of boundary/evidence ordering violations provable from public fields, acceptance of valid exact-domain order across millisecond collisions without false lap/kind/state tie-breaks, and rejection of contradictory complete-visit field combinations
- [ ] T048 [US3] Add failing direct-construction tests in backend/tests/test_race_context_api.py for unpaired_entry, unpaired_exit, conflicting, and unavailable pit states; multiplicity/conflict representation; count reconciliation; full participant/lap-order validation, duplicate statuses and publicly provable boundary/pit-order violations; rounding-collision acceptance and no reconstruction of lost TrackStatus source order; duplicate identities; mismatched references; and proof of no silent sorting, deduplication, or repair
- [ ] T049 [US4] Add failing direct-construction tests in backend/tests/test_race_context_api.py for exactly one compact participant per authoritative identity, canonical participant order, a compact session response without full lap/pit collections, and driver detail with the matching summary plus complete canonical lap context and all pit evidence
- [ ] T050 [US2] Implement strict shared enums, identity/classification, track-status, leader-reference, and lap-context projection models in backend/app/models/race_context_models.py matching specs/004-pit-race-context/contracts/openapi.yaml without analytics in validators
- [ ] T051 [US1] Implement strict pit-boundary, transition-context, evidence-status, count, and complete/incomplete pit projection models in backend/app/models/race_context_models.py using source-backed terminology and explicit millisecond fields
- [ ] T052 [US3] Implement direct-construction invariants in backend/app/models/race_context_models.py that reject ordering contradictions provable from exposed fields, duplicate public identities/statuses, invalid state/value combinations, bad evidence counts, mismatched references, coercible non-strict scalars, and non-finite values without mutation or repair; preserve full participant/lap-order validation and never reconstruct lost exact chronology or TrackStatus observation order, descend into lower keys on rounded timestamp collisions, or resolve ambiguous public ties
- [ ] T053 [US4] Implement compact session and auditable driver-detail response models in backend/app/models/race_context_models.py, enforcing projection composition and prohibiting complete lap-context or pit-evidence duplication in the compact session view
- [ ] T054 [US4] Run the public-model slice in backend/tests/test_race_context_api.py and verify exact alignment with specs/004-pit-race-context/contracts/openapi.yaml, FR-062 through FR-065, and SC-013; prove detectable invalid public order is rejected, valid exact-domain order survives millisecond collisions, ambiguous public ties are not resolved by validators, and TrackStatus sequences are retained without enum-order invention

**Checkpoint**: Invalid public structures fail direct construction; valid structures retain explicit status and provenance semantics.

## Phase 9: Group E — Service Projections

**Purpose**: Orchestrate one supported-session operation from one session load, one normalization, one central analysis, and two projections of the same result.

- [ ] T055 [US4] Add failing service tests in backend/tests/test_race_context_service.py for supported-session validation before provider access, one load_session call, one Feature 004 mapper call, one map_session_summary call on the same snapshot, one central analysis call, session and driver projections from that result, known participants with unavailable evidence, authoritative unknown-driver handling, and provider/normalization/unexpected failure propagation
- [ ] T056 [US4] Implement backend/app/services/race_context_service.py to enforce the established supported-session boundary before provider access, load once, normalize once, map the session summary from the same snapshot, analyze once, project either compact session output or one driver detail, and construct strict public models without normalization, analytics, rounding, sorting, pit pairing, or latest-context selection
- [ ] T057 [US4] Run backend/tests/test_race_context_service.py and verify both projections share the same central result and no view-specific analytics or repeated provider acquisition occurs

**Checkpoint**: The service owns orchestration only and enforces the one-snapshot/one-analysis architecture.

## Phase 10: Group F — API and OpenAPI Contract

**Purpose**: Add the two approved thin resources while preserving every existing endpoint and error contract.

- [ ] T058 [P] [US4] Add failing API tests in backend/tests/test_race_context_api.py for the compact session resource, complete driver detail, canonical driver lookup, known participants with unavailable evidence, unknown participant 404 driver_not_found, malformed selector 422, unsupported session 404 session_not_supported, expected provider/schema/normalization 503 data_source_unavailable, unexpected framework 500 without private detail, finite standards-safe JSON, and absence of a pit-only v1 resource
- [ ] T059 [P] [US4] Add failing contract tests in backend/tests/test_openapi.py for exactly the two additive race-context paths, operation IDs getSessionRaceContext and getDriverRaceContext, required/nullable fields, enum values, strict identity constraints, integer-millisecond semantics, narrow lap-completion-position and equal-distance descriptions, and unchanged Feature 001–003 paths, operation IDs, and schemas
- [ ] T060 [US4] Add thin routes to backend/app/main.py for GET /api/v1/seasons/{year}/events/{event}/sessions/{session}/race-context and GET /api/v1/seasons/{year}/events/{event}/sessions/{session}/race-context/drivers/{driver_number}, reusing established selector and error handling and delegating all work to backend/app/services/race_context_service.py
- [ ] T061 [US4] Compare generated OpenAPI from backend/app/main.py with specs/004-pit-race-context/contracts/openapi.yaml and resolve only model/route implementation mismatches in backend/app/models/race_context_models.py or backend/app/main.py without weakening the authoritative contract
- [ ] T062 [US4] Run backend/tests/test_race_context_api.py and backend/tests/test_openapi.py, confirming the two resources are additive, thin, standards-safe, deterministic, and preserve all prior public behavior

**Checkpoint**: Both public resources are contract-complete projections of one central analysis; no pit-only resource exists.

## Phase 11: Group G — Integration, Regression, Documentation, and Final Review

**Purpose**: Validate real-provider compatibility, full regression safety, documentation accuracy, and final task-to-requirement coverage without turning Monza observations into rules.

- [ ] T063 [P] Add an opt-in 2025 Italian Grand Prix Race provider-compatibility test in backend/tests/test_f1_data_integration.py covering one-snapshot Feature 004 normalization, both projections, provenance, deterministic invariants, and evidence accounting while leaving all missing edge cases to controlled fixtures and avoiding incidental Monza assertions as business rules
- [ ] T064 [P] Update README.md with the two Feature 004 resources, precise equal-distance and pit-lane terminology, opt-in acceptance guidance, and no live-gap, stationary-service-time, or confirmed-tire-change claims
- [ ] T065 [P] Update docs/architecture.md with the responsibility-package layout, provider-boundary ownership, immutable normalized inputs, central pure race-context analysis, shared projections, and future Feature 005 reuse boundary
- [ ] T066 [P] Update docs/demo-v0.1.md only for the approved Feature 004 demo capabilities, unavailable/conflict semantics, and controlled Monza acceptance scope without speculative strategy, frontend, or live-race behavior
- [ ] T067 Run the complete offline backend/tests/ suite with cache writing disabled and confirm all Feature 001–004 tests pass without changes to Feature 001–003 expectations
- [ ] T068 Run Ruff format checking and Ruff lint over backend/app/ and backend/tests/, applying only Feature 004-related corrections and then rerunning both checks
- [ ] T069 Run the opt-in Feature 004 Monza integration slice in backend/tests/test_f1_data_integration.py when provider access is authorized, recording provider compatibility separately from synthetic policy coverage
- [ ] T070 Audit backend/app/, backend/tests/, README.md, docs/architecture.md, docs/demo-v0.1.md, and specs/004-pit-race-context/ against FR-001–FR-065, SC-001–SC-013, the OpenAPI contract, prohibited scope, exact file layout, no dependency diffs, no private FastF1 API or telemetry, and git diff --check
- [ ] T071 Obtain fresh independent Codex review of the completed Feature 004 diff across backend/app/, backend/tests/, README.md, docs/architecture.md, and docs/demo-v0.1.md before any feature commit, with explicit attention to Gate A preservation, provider isolation, central-analysis reuse, pit pairing, lapped semantics, strict public invariants, error compatibility, test sufficiency, and architectural simplicity
- [ ] T072 After resolving only approved review findings, rerun backend/tests/, Ruff format/lint, generated OpenAPI checks, dependency-diff checks, integration checks when authorized, and git diff --check, then record final owner-review readiness without committing, pushing, or merging

## Dependencies and Execution Order

### Hard dependency chain

Group A migration (T001–T010)
→ Gate A verification and independent approval (T011–T017)
→ Group B provider normalization (T018–T024)
→ Group C1 lap context (T025–T031)
→ Group C2 complete pit visits (T032–T035)
→ Group C3 incomplete/conflicting evidence (T036–T041)
→ Group C4 central result and independent approval (T042–T045)
→ Group D public models (T046–T054)
→ Group E service projections (T055–T057)
→ Group F API/OpenAPI (T058–T062)
→ Group G integration/regression/documentation/final review (T063–T072)

No task at or after T018 may begin until T017 records approval. The dependency graph is intentionally linear across policy-bearing groups so shared semantics are implemented once and reused downstream.

### User-story dependencies

- US2 and US1 are both P1. US2 is scheduled first because the approved pit transition context consumes trusted lap-completion context; this is a technical dependency, not a priority change.
- US3 depends on the US1 pit state machine and US2 lap evidence semantics so incomplete/conflicting behavior extends one policy rather than duplicating it.
- US4 depends on US1–US3 because it assembles their results centrally and projects them without recalculation.
- The first externally usable Feature 004 increment therefore completes Groups A–F; pure US1 and US2 behaviors remain independently testable before transport is added.

### Parallel opportunities

- T007–T010 may run in parallel only after T002–T006 because they edit disjoint test files and make migration-only import/patch-target changes.
- T058 and T059 may run in parallel after T057 because they edit separate API and OpenAPI test files against the same completed service contract.
- T063–T066 may run in parallel after T062 because they edit one integration-test file and three separate documentation files with no shared implementation ownership.
- Provider, analytics, model, service, and route implementation tasks are deliberately not marked parallel when they share a file, establish policy consumed downstream, or could create duplicate logic.

### Parallel execution examples by user story

- US1: Keep T032–T035 sequential because the test, state-machine, and elapsed/context tasks share backend/tests/test_race_context_analytics.py and backend/app/analytics/race_context_analytics.py. Parallel work would risk two pit policies.
- US2: Keep T025–T031 sequential because leader, lapped-driver, status, and rounding semantics share the same analytics and test modules. The independent test slice can run as soon as T031 is reached.
- US3: Keep T036–T041 sequential because incomplete/conflicting behavior extends the same pit and lap policies and must preserve one occurrence-accounting rule.
- US4: After T057, run T058 and T059 in parallel because API behavior tests and OpenAPI contract tests are in disjoint files; reconverge at T060–T062 before documentation or integration work.

## Implementation Strategy

### Bounded delivery

1. Complete Group A only, then stop at Gate A for the full regression, exact OpenAPI comparison, diff audit, and fresh independent approval.
2. Complete and review Group B as a provider-boundary increment before any analytical behavior is added.
3. Build the two co-P1 domain slices in dependency order: US2 lap context first, then US1 pit visits that consume that context.
4. Extend the same policies for US3 incomplete/conflicting evidence, then assemble and independently review the single US4 central result.
5. Add strict public models, orchestration, and the two transport resources only after central analytics are stable.
6. Finish with real-provider compatibility, complete regression, documentation, traceability audit, and fresh independent review.

### MVP scope

US1 and US2 are co-P1 and the approved public driver resource combines their facts. The smallest externally usable Feature 004 increment is therefore Groups A through F, including Gate A, provider normalization, both P1 analytics slices, explicit uncertainty handling required for truthful output, the one central result, strict models, service projections, and both approved routes. US3 and US4 are not optional architecture embellishments: they supply mandatory evidence integrity and the single-analysis projection contract. Group G is required before release readiness.

## Traceability Audit

### Functional requirements

| Requirements | Primary task coverage |
|---|---|
| FR-001 | T042–T043, T053, T056, T058–T062 |
| FR-002 | T058–T069 |
| FR-003–FR-005 | T001–T017, T059, T062, T067, T070–T072 |
| FR-006–FR-008 | T019–T024, T042–T045, T063, T070 |
| FR-009–FR-010 | T019, T022, T032–T034, T047, T051 |
| FR-011–FR-018 | T032–T041, T047–T052, T058, T063 |
| FR-019–FR-022 | T032–T041, T047–T052, T058, T063 |
| FR-023–FR-028 | T025–T031, T046, T050, T058–T061 |
| FR-029–FR-035 | T026–T031, T036–T040, T046, T050, T058–T061 |
| FR-036–FR-043 | T019–T030, T036–T041, T046–T054, T058–T063 |
| FR-044–FR-050 | T020–T024, T027–T030, T042–T045, T055–T057, T070–T072 |
| FR-051–FR-053 | T018–T019, T025–T041, T063, T067, T069–T072 |
| FR-054–FR-061 | T042–T045, T049, T053, T055–T062 |
| FR-062–FR-065 | T046–T054, T059, T061–T062 |

All identifiers FR-001 through FR-065 occur in exactly one contiguous range above; every range has implementation and/or explicit validation work.

### Success criteria

| Criterion | Primary task coverage |
|---|---|
| SC-001 | T032–T035, T047, T051, T063 |
| SC-002 | T036, T038, T041, T048, T052 |
| SC-003 | T032, T036, T038, T041, T047–T052 |
| SC-004 | T026–T031, T046, T050 |
| SC-005 | T026, T029–T031, T046, T050 |
| SC-006 | T019, T022, T025, T028–T030, T046, T050, T058 |
| SC-007 | T019, T022, T025, T027–T028, T046, T050 |
| SC-008 | T019, T025, T027, T036–T041, T048, T052 |
| SC-009 | T027, T040, T042–T044, T049, T053, T055–T057 |
| SC-010 | T023, T042–T045, T055–T057 |
| SC-011 | T001–T017, T059, T062, T067, T070–T072 |
| SC-012 | T019–T022, T025–T043, T046–T053, T058, T063 |
| SC-013 | T046–T054 |

Every identifier SC-001 through SC-013 has controlled validation coverage. SC-007 additionally uses the pre-migration OpenAPI equality gate and complete regression suite.

### Contract and data-model coverage

| Area | Task coverage |
|---|---|
| Normalized provider/application input facts | T018–T024 |
| Central analytical/domain results | T025–T045 |
| Public projection models and direct construction | T046–T054 |
| One-load/one-analysis orchestration | T055–T057 |
| Both approved paths and operation IDs | T058–T062 |
| Contract required/nullable fields, enums, strict scalars, and millisecond units | T046–T054, T059–T062 |
| Existing error behavior and Feature 001–003 contract preservation | T001, T012, T014, T055, T058–T062, T067, T070 |

## Task Quality Audit

| Check | Result |
|---|---|
| Every task uses the required checkbox, sequential ID, optional parallel marker, story label where applicable, and concrete path | PASS |
| Package migration precedes Feature 004 behavior and Gate A blocks T018+ | PASS |
| FR-001–FR-065 coverage is complete | PASS |
| SC-001–SC-013 coverage is complete | PASS |
| Both OpenAPI resources and every major schema concern are covered | PASS |
| Normalized input, central domain result, and public projection layers remain separate | PASS |
| Dependencies are acyclic | PASS |
| Tests precede implementation within behavioral groups | PASS |
| Parallel markers are limited to disjoint files after shared prerequisites | PASS |
| No new dependency task exists | PASS |
| No task introduces private FastF1 APIs, telemetry, live-gap semantics, confirmed tire-change claims, stationary service timing, persistence, frontend, AI/ML, deployment, or strategy recommendations | PASS |
| No task changes Feature 001–003 policy or uses Monza facts as general rules | PASS |
| No speculative repository, factory, plugin, interface, compatibility wrapper, or re-export task exists | PASS |
