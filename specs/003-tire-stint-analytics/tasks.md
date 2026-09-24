---

description: "Implementation tasks for Feature 003 tire-stint analytics"
---

# Tasks: Tire Stints & Observed Degradation Analytics

**Input**: Approved design documents from `specs/003-tire-stint-analytics/`

**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/openapi.yaml`, `quickstart.md`, and `checklists/requirements.md`

**Tests**: Tests are required and are paired with the implementation group that introduces each behavior. Routine verification remains offline; real FastF1 acceptance remains gated by `F1_RUN_INTEGRATION=1`.

**Organization**: Shared provider normalization, classification, and pure analytics are foundational because all three user stories depend on them. User-story phases then add the driver resource, session resource, and exhaustive unavailability explanations.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Safe to execute in parallel after the stated prerequisites because the tasks touch different files and have no incomplete behavioral dependency
- **[Story]**: Maps the task to User Story 1, 2, or 3 from `spec.md`
- Every task names the concrete repository file or files it changes or verifies

## Phase 1: Shared Test Setup

**Purpose**: Extend controlled test data for Feature 003 while preserving the existing Feature 001/002 defaults and offline source guard.

- [X] T001 Extend the controlled session factory with optional `Stint`, `TyreLife`, and `FastF1Generated` columns while preserving existing defaults and the autouse network guard in `backend/tests/conftest.py`

**Checkpoint**: Controlled provider-shaped data can express Feature 003 cases without changing existing tests or accessing FastF1.

---

## Phase 2: Foundational Source and Pure Analytics

**Purpose**: Build the normalized input, shared five-rule classifier, deterministic stint construction, eligibility, availability, and estimator boundaries required by every user story.

**Critical order**: Complete source normalization, then classifier extraction, then construction/eligibility, then availability, then the estimator. This phase blocks all user-story API work.

### Source normalization extensions

- [X] T002 Add failing normalization tests for finite positive integral `Stint`/`TyreLife`, boolean rejection, optional/malformed-to-`None` behavior, tri-state `FastF1Generated`, preserved compound/accuracy/timing/pit/status fields, duplicate consumed labels, absent optional columns, and unchanged Feature 001/002 behavior in `backend/tests/test_f1_data.py`
- [X] T003 Append defaulted `stint: int | None`, `tyre_life: int | None`, and `provider_generated: bool | None` fields with normalized-value invariants to `SourceLap` without changing existing positional construction in `backend/app/lap_analytics.py`
- [X] T004 Extend the single `map_lap_inputs()` path to normalize the three approved fields, reject ambiguous consumed labels, keep missing quality assertions neutral, and preserve `messages=False` with no `FreshTyre` or `Deleted` behavior in `backend/app/f1_data.py`
- [X] T005 Run the focused normalization and existing session tests in `backend/tests/test_f1_data.py` and `backend/tests/test_sessions.py` and confirm Feature 001/002 results remain unchanged

### Shared structural/status classifier

- [X] T006 Add failing regression tests for the reusable five-rule order and for unchanged Feature 002 six-rule output, strict 120% comparison, ordering, diagnostics, counts, and policy metadata in `backend/tests/test_lap_analytics.py`
- [X] T007 Extract `classify_structural_status_laps()` and a five-value precedence tuple, then make `classify_driver_laps()` apply the unchanged anomaly pass afterward without adding Feature 003 values to `LapExclusionReason` in `backend/app/lap_analytics.py`
- [X] T008 Run classifier, pace service, pace API, and OpenAPI regression tests in `backend/tests/test_lap_analytics.py`, `backend/tests/test_pace_service.py`, `backend/tests/test_pace_api.py`, and `backend/tests/test_openapi.py`

### Pure stint construction and canonical evidence

- [X] T009 Add failing tests for reported-stint identity, missing/unusable IDs as unassigned evidence, zero-row participants, `A -> B -> A`, `A -> unassigned -> A`, compound continuity, no reconstruction/splitting/merging/renumbering, and exact assigned/unassigned reconciliation in `backend/tests/test_stint_analytics.py`
- [X] T010 Create immutable Feature 003 policy, reason, decision, sample, stint, driver, and session analysis types plus normalized-fact canonical key helpers in `backend/app/stint_analytics.py`
- [X] T011 Implement authoritative-roster grouping, reported-stint construction, continuity and compound validation, zero-row participant retention, and disjoint assigned/unassigned evidence in `backend/app/stint_analytics.py`
- [X] T012 Add failing duplicate-policy tests for one-stint, cross-stint, identified-plus-unassigned, unassigned-only, and fully identical duplicate groups with full row multiplicity in `backend/tests/test_stint_analytics.py`
- [X] T013 Implement duplicate driver/valid-lap detection that marks every represented identified stint inconsistent, admits no affected row to age validation or estimation, retains all evidence/counts, and canonically orders by driver, null-last lap/stint/age/duration/compound, pit flags, statuses, and explicitly ranked nullable booleans without `source_order` in `backend/app/stint_analytics.py`

### Feature 003 lap eligibility and tire-age validation

- [X] T014 Add failing tests for all five inherited exclusions followed by `explicitly_inaccurate`, `provider_generated`, `unusable_tire_age`, and eligible; include true/false/missing quality assertions, proof the 120% anomaly is ignored, repeated/decreasing ages, gaps, starting age above one, six distinct ages, and five-age failure in `backend/tests/test_stint_analytics.py`
- [X] T015 Implement exact first-match Feature 003 lap decisions through the shared five-rule classifier, keep unassignment/exclusion/stint unavailability separate, and validate strictly increasing eligible reported ages without repair in `backend/app/stint_analytics.py`

### Availability and reconciled samples

- [X] T016 Add failing single-blocker and sample tests for slick, wet/intermediate, missing, unsupported, and conflicting compounds; all seven unavailable reasons; exact counts; metric suppression; and sample-decisive absent or malformed/unusable tire age in `backend/tests/test_stint_analytics.py`
- [X] T017 Implement available/unavailable states, the six-tier decision order, same-tier compound metadata handling, count reconciliation, and `missing_tire_age` only when `eligible_count < 6`, `unusable_tire_age_count > 0`, and their sum reaches six in `backend/app/stint_analytics.py`

### Direct dependency and Theil-Sen trend analytics

- [X] T018 Add direct `scipy>=1.11,<2` application dependency in `backend/pyproject.toml`, regenerate `backend/uv.lock`, and audit the lockfile diff so no unrelated resolver drift is accepted
- [X] T019 Add failing estimator tests for positive, zero, and negative slopes; an extreme eligible outlier; explicit joint intercept; median absolute residual; full-source-precision calculation; half-up 0.001 publication; negative-zero normalization; finite guards; six observations and six distinct ages; and absence of confidence-interval output in `backend/tests/test_stint_analytics.py`
- [X] T020 Implement `scipy.stats.theilslopes(y, x, method="joint")`, joint-line predictions, median absolute residual, finite invariants, and isolated `Decimal`/`ROUND_HALF_UP` publication in `backend/app/stint_analytics.py`
- [X] T021 Run the complete foundational suites in `backend/tests/test_f1_data.py`, `backend/tests/test_lap_analytics.py`, and `backend/tests/test_stint_analytics.py`; require at least three identical repeated executions, equal canonical public/analysis content when distinguishable normalized rows or fully identical duplicate rows are permuted, preserved duplicate multiplicity, and proof that changing `source_order` never changes any Feature 003 result

**Checkpoint**: Pure analysis deterministically accounts for every normalized row and produces complete internal driver/session results without FastAPI, Pydantic, Pandas, FastF1, cache, or network imports in `backend/app/stint_analytics.py`.

---

## Phase 3: User Story 1 - Inspect One Driver's Stints (Priority: P1) MVP

**Goal**: Return one known driver's ordered stint summaries, trend availability, limitations, and one auditable evidence record for every normalized source row.

**Independent Test**: Using controlled data for a known driver with one available slick stint and one unavailable stint, verify identities, metadata, metrics, counts, reasons, limitations, complete evidence, unknown-driver behavior, and a known zero-row driver without using the session endpoint.

### Tests for User Story 1

- [X] T022 [P] [US1] Add failing strict-contract tests for required nullable fields, forbidden extras, signed finite trend, non-negative residual, status/reason/metric invariants, exact sample/evidence reconciliation, canonical duplicate multiplicity, policy metadata, and observational limitations in `backend/tests/test_stint_api.py`
- [X] T023 [P] [US1] Add failing driver-service tests for one load, one map, one summary projection, one complete analysis, known/unknown/zero-row drivers, canonical evidence order, deterministic repeats, and expected/unexpected failure propagation in `backend/tests/test_stint_service.py`

### Implementation for User Story 1

- [X] T024 [US1] Implement the shared strict frozen Feature 003 policy, limitation, range, sample, stint-summary, and evidence models plus the driver-detail public response model(s) required by User Story 1, reusing existing shared context/identity/provenance types and the exact approved schemas in `specs/003-tire-stint-analytics/contracts/openapi.yaml`, in `backend/app/stint_models.py`
- [X] T025 [US1] Implement one-snapshot driver orchestration, shared summary/evidence projection, policy and limitation projection, canonical driver lookup, and `DriverNotFoundError` behavior in `backend/app/stint_service.py`
- [X] T026 [US1] Add failing driver-route tests for success, malformed selectors before loading, unsupported session, unknown driver after one analysis, sanitized 503, unexpected 500, finite JSON, and complete evidence in `backend/tests/test_stint_api.py`
- [X] T027 [P] [US1] Add semantic OpenAPI assertions for the driver tire-stint path, operation ID, parameters, responses, strict schemas, required-nullable fields, numeric metric bounds, and unchanged inherited components in `backend/tests/test_openapi.py`
- [X] T028 [US1] Add only `GET /api/v1/seasons/{year}/events/{event}/sessions/{session}/tire-stints/drivers/{driver_number}` with operation ID `getDriverTireStintAnalysis` and existing selector/error semantics in `backend/app/main.py`
- [X] T029 [US1] Run the independent driver-detail tests in `backend/tests/test_stint_analytics.py`, `backend/tests/test_stint_service.py`, `backend/tests/test_stint_api.py`, and `backend/tests/test_openapi.py`

**Checkpoint**: User Story 1 is independently usable and auditable without the session-wide tire-stint endpoint.

---

## Phase 4: User Story 2 - Review the Session Stint Field (Priority: P2)

**Goal**: Return compact ordered stint summaries for every authoritative results participant without duplicating lap evidence.

**Independent Test**: Using a controlled supported session containing available and unavailable stints plus a zero-row participant, verify every participant, compact summaries, unassigned counts, deterministic order, one-snapshot orchestration, and absence of lap evidence.

### Tests for User Story 2

- [X] T030 [US2] Add failing session-service tests for every authoritative participant, numeric driver order, chronological stint order, zero-row participants, compact projection, unassigned counts, one load/map/summary/analysis call, and deterministic repeats in `backend/tests/test_stint_service.py`
- [X] T031 [US2] Add failing session-route tests for compact success payloads, absence of lap evidence, malformed/unsupported selectors, sanitized 503, unexpected 500, and repeated deterministic JSON in `backend/tests/test_stint_api.py`
- [X] T032 [P] [US2] Add semantic OpenAPI assertions for the session tire-stint path, `getSessionTireStintAnalysis`, shared parameters/responses, compact response schema, and unchanged Feature 001/002 paths and operation IDs in `backend/tests/test_openapi.py`

### Implementation for User Story 2

- [X] T033 [US2] Implement the session-specific public response model(s), including the approved `SessionTireStintAnalysisResponse` shape and any session-only wrapper required by `specs/003-tire-stint-analytics/contracts/openapi.yaml`, in `backend/app/stint_models.py`, then add the compact session projection without reloading, remapping, or reanalyzing in `backend/app/stint_service.py`
- [X] T034 [US2] Add only `GET /api/v1/seasons/{year}/events/{event}/sessions/{session}/tire-stints` with operation ID `getSessionTireStintAnalysis` and existing supported-session/error semantics in `backend/app/main.py`
- [X] T035 [US2] Run the independent session-summary tests in `backend/tests/test_stint_service.py`, `backend/tests/test_stint_api.py`, and `backend/tests/test_openapi.py`

**Checkpoint**: User Story 2 provides a compact discovery view while User Story 1 remains the sole complete lap-evidence resource.

---

## Phase 5: User Story 3 - Understand Unavailable Trends (Priority: P3)

**Goal**: Prove every unavailable result selects one deterministic primary reason, suppresses both metrics, and communicates the observational limits of available results.

**Independent Test**: Exercise every blocker independently and in approved combinations, then verify the exact six-tier policy, same-tier compound outcomes, sample-decisive missing-age rule, metric suppression, and machine/human limitation disclosure.

### Exhaustive verification for User Story 3

- [X] T036 [P] [US3] Add multi-blocker precedence, same-tier compound tie handling, sample-decisive unusable-age, other-exclusion shortfall, and duplicate-metadata precedence cases to `backend/tests/test_stint_analytics.py`
- [X] T037 [P] [US3] Add public validation and endpoint cases for every unavailability enum, unavailable metric suppression, zero as an available result, all six limitation identifiers, and the fixed non-causal description in `backend/tests/test_stint_api.py`
- [X] T038 [P] [US3] Assert the exact eight-value lap exclusion sequence, exact six availability tiers, unordered two-member compound tier, all reason enums, estimator disclosure, and limitation schema in `backend/tests/test_openapi.py`

**Checkpoint**: All User Story 3 outcomes are verified through pure analytics, strict public models, both endpoints, and generated OpenAPI without adding a separate explanation subsystem.

---

## Phase 6: Integration, Documentation, and Final Verification

**Purpose**: Validate the real provider boundary, preserve existing features, document the shipped behavior, and complete the repository quality gates.

- [X] T039 Extend gated Monza acceptance to validate tire metadata compatibility, provenance, participant/stint/lap reconciliation, deterministic ordering, finite/null invariants, and limitation disclosure without asserting an external degradation value in `backend/tests/test_f1_data_integration.py`
- [X] T040 [P] Document the two tire-stint resources, observed metric meaning, audit evidence, and non-causal limits in `README.md`
- [X] T041 [P] Document the one-snapshot source-to-normalization-to-pure-analysis-to-service architecture and shared five-rule classifier boundary in `docs/architecture.md`
- [X] T042 [P] Add a Feature 003 demonstration flow with available/unavailable examples and interpretation guardrails in `docs/demo-v0.1.md`
- [X] T043 Review implementation discoveries against `specs/003-tire-stint-analytics/quickstart.md` and update only factual commands or acceptance expectations that require synchronization
- [X] T044 Run the complete Feature 001/002 regression set in `backend/tests/test_health.py`, `backend/tests/test_sessions.py`, `backend/tests/test_f1_data.py`, `backend/tests/test_lap_analytics.py`, `backend/tests/test_pace_service.py`, `backend/tests/test_pace_api.py`, and `backend/tests/test_openapi.py`
- [X] T045 Run offline collection, the complete offline pytest suite, Ruff format check, and Ruff lint with the commands in `specs/003-tire-stint-analytics/quickstart.md`, confirming the autouse source guard and integration deselection
- [X] T046 Run the explicitly opted-in `F1_RUN_INTEGRATION=1` acceptance in `backend/tests/test_f1_data_integration.py` when live FastF1 access is authorized, preserving its integration marker and network gate
- [X] T047 Audit `backend/pyproject.toml`, `backend/uv.lock`, `backend/cache/fastf1/`, `specs/003-tire-stint-analytics/contracts/openapi.yaml`, and the final Git diff for dependency drift, cache artifacts, contract preservation, scope exclusions, whitespace errors, and unintended files

**Checkpoint**: All approved offline checks pass, real-source acceptance is explicitly gated, documentation matches behavior, and the final diff contains only Feature 003 scope.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1** has no dependency and prepares reusable controlled source data.
- **Phase 2** depends on T001 and is intentionally sequential by subgroup: T002–T005 normalization, T006–T008 shared classification, T009–T013 construction/duplicates, T014–T015 eligibility/age, T016–T017 availability, and T018–T021 estimator/dependency verification.
- **User Story 1 (Phase 3)** depends on all foundational tasks through T021. T022 and T023 can start together; T024 precedes T025; T026 and T027 define route/contract expectations before T028; T029 closes the story.
- **User Story 2 (Phase 4)** depends on the shared models/service from User Story 1. T030–T032 define the compact projection contract before T033–T034; T035 closes the story.
- **User Story 3 (Phase 5)** depends on the complete analytical and public boundaries from Phases 2–4. T036–T038 are independent exhaustive verification tasks.
- **Phase 6** depends on all selected user stories. T039 precedes the live run in T046; documentation tasks T040–T042 can run together; T043 follows implementation discoveries; T044–T047 form the final quality gate.

### User story dependency graph

```text
Phase 1 shared test setup
  -> Phase 2 source/classifier/pure analytics foundation
       -> US1 driver detail (MVP)
            -> US2 compact session field
                 -> US3 exhaustive unavailability explanations
                      -> integration, documentation, and final verification
```

US2 reuses US1's shared stint summaries and service projections. US3 verifies behavior introduced by the foundation and public resources rather than creating a parallel analytics or explanation path.

### Parallel opportunities

- After T021, T022 (`backend/tests/test_stint_api.py`) and T023 (`backend/tests/test_stint_service.py`) can be authored in parallel.
- After T025, T026 (`backend/tests/test_stint_api.py`) and T027 (`backend/tests/test_openapi.py`) can be authored in parallel.
- In User Story 2, T032 can be authored alongside T030–T031 because it touches `backend/tests/test_openapi.py` rather than the service/API test files.
- In User Story 3, T036–T038 can run in parallel because they extend three separate test modules against already implemented shared behavior.
- After application behavior stabilizes, T040–T042 can run in parallel across `README.md`, `docs/architecture.md`, and `docs/demo-v0.1.md`.

## Parallel Execution Examples

### User Story 1

```text
Task T022: Define strict public contract expectations in backend/tests/test_stint_api.py
Task T023: Define one-snapshot driver orchestration expectations in backend/tests/test_stint_service.py
```

### User Story 2

```text
Task T030: Define compact session service behavior in backend/tests/test_stint_service.py
Task T032: Define session OpenAPI behavior in backend/tests/test_openapi.py
```

### User Story 3

```text
Task T036: Verify pure precedence combinations in backend/tests/test_stint_analytics.py
Task T037: Verify public unavailable states in backend/tests/test_stint_api.py
Task T038: Verify serialized policy structure in backend/tests/test_openapi.py
```

## Implementation Strategy

### MVP first

1. Complete Phase 1 and all foundational work in Phase 2.
2. Complete User Story 1 through T029.
3. Stop and validate the driver-detail resource independently before adding the compact session projection.

### Incremental delivery

1. Normalize source facts and preserve Feature 001/002 behavior.
2. Extract and regress the shared five-rule classifier.
3. Complete pure construction, duplicate handling, eligibility, availability, and Theil-Sen publication.
4. Deliver the independently testable driver detail resource.
5. Reuse the same analysis and summaries for the compact session resource.
6. Complete exhaustive unavailability and disclosure verification.
7. Run integration, documentation, regression, and repository audits.

## Requirement Coverage

- **Source boundary and compatibility**: FR-003, FR-004, FR-005, FR-006, FR-008, FR-020, FR-044, FR-045 are covered by T001–T008, T023–T028, T030–T035, and T044–T047.
- **Stint identity, construction, evidence, and summaries**: FR-001, FR-002, FR-007, FR-009, FR-010, FR-011, FR-012, FR-013, FR-014, FR-035, FR-039, FR-042, FR-043 are covered by T009–T017 and T022–T035.
- **Lap eligibility and compounds**: FR-015, FR-016, FR-017, FR-018, FR-019, FR-021, FR-022, FR-023, FR-024 are covered by T006–T008, T014–T017, and T036–T038.
- **Tire age and sample policy**: FR-025, FR-026, FR-027, FR-028, FR-029, FR-037, FR-038 are covered by T014–T017, T019–T021, and T036–T038.
- **Trend, residual, availability, and interpretation**: FR-030, FR-031, FR-032, FR-033, FR-034, FR-036, FR-040, FR-041 are covered by T016–T020, T022–T029, T036–T043, and T047.
- **Acceptance and scope**: FR-046 and FR-047 are covered by T039–T047.
- **Session participation and row accounting outcomes**: SC-001, SC-002 are covered by T009–T017 and T022–T035.
- **Analytical and unavailable outcomes**: SC-003, SC-004, SC-005 are covered by T014–T020 and T036–T038.
- **Determinism and compatibility**: SC-006, SC-007 are covered by T005–T008, T012–T021, T023–T035, and T044–T047.
- **Disclosure and source-quality outcomes**: SC-008, SC-009, SC-010 are covered by T014–T017, T022–T029, T036–T043, and T047.

Every FR-001 through FR-047 and SC-001 through SC-010 appears in the coverage map above and has at least one implementation or verification task.

## Notes

- Do not use `source_order` anywhere in Feature 003 chronology, grouping, canonical selection, or serialized ordering; its continued use is limited to unchanged Feature 002 behavior.
- Keep fully indistinguishable duplicate evidence objects repeated with their original multiplicity.
- Do not add frontend, AI/LLM, ML, strategy, telemetry, persistence, deployment, race-control-message, `FreshTyre`, or `Deleted` work.
- Preserve Feature 001/002 public schemas and meanings. The approved shared
  `year` and `round_number` runtime validation hardening rejects coercion without
  redesigning those contracts; regression tasks protect all other behavior.
