---

description: "Dependency-ordered implementation tasks for Backend Foundation & F1 Data Access"
---

# Tasks: Backend Foundation & F1 Data Access

**Input**: Design documents from `specs/001-backend-f1-data-access/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/openapi.yaml`, and `quickstart.md`

**Tests**: Automated tests are required by the feature specification. Write
story tests first, verify that they fail for the expected missing behavior, and
then implement the story. Routine tests must not contact FastF1 services.

**Organization**: Tasks are grouped by user story so each story has a clear,
independently verifiable outcome.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it affects different files and has no
  dependency on another incomplete task in the same phase.
- **[Story]**: Maps the task to a user story in `spec.md`.
- Every task names the file or directory it affects.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the independently managed Python backend environment.

- [x] T001 Create the Python 3.12 version declaration in `backend/.python-version`
- [x] T002 [P] Configure the non-publishable uv application, FastAPI/Uvicorn/FastF1 runtime dependencies, pytest/HTTPX/Ruff development dependencies, and Ruff Python 3.12 settings in `backend/pyproject.toml`
- [x] T003 Generate the reproducible dependency lock and synchronize the local environment from `backend/pyproject.toml` into `backend/uv.lock`

**Checkpoint**: `backend/` is a reproducible uv project and no application
behavior has been implemented.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create only the package and shared test boundaries required by all
stories.

**Critical**: Complete this phase before starting user-story work.

- [x] T004 Create the backend application package marker in `backend/app/__init__.py`
- [x] T005 Create reusable TestClient and deterministic session-summary fixtures without live FastF1 access in `backend/tests/conftest.py`

**Checkpoint**: Imports and controlled test fixtures are ready; no endpoint or
FastF1 behavior exists yet.

---

## Phase 3: User Story 1 - Confirm Backend Availability (Priority: P1)

**Goal**: Start the backend and expose a deterministic health response that is
independent of Formula 1 data availability.

**Independent Test**: Start the service or use TestClient, request
`GET /health` repeatedly, and receive HTTP `200` with exactly
`{"status": "ok"}` every time without invoking FastF1.

### Tests for User Story 1

- [x] T006 [US1] Write failing tests for the exact, repeatable, FastF1-independent health response in `backend/tests/test_health.py`

### Implementation for User Story 1

- [x] T007 [US1] Add the typed health response model in `backend/app/models.py`
- [x] T008 [US1] Create the FastAPI application and synchronous `GET /health` endpoint in `backend/app/main.py`
- [x] T009 [US1] Run and satisfy the User Story 1 tests in `backend/tests/test_health.py`, including a local application startup smoke check for `backend/app/main.py` that verifies `GET /health` returns HTTP `200` with `{"status": "ok"}` within 5 seconds, without introducing a performance-testing framework

**Checkpoint**: User Story 1 is independently functional and provides the
smallest backend MVP.

---

## Phase 4: User Story 2 - Retrieve Control Session Information (Priority: P1)

**Goal**: Return deterministic FastF1-backed information for the 2025 Italian
Grand Prix Race control session, including identity, circuit/timing,
participants, availability, and provenance.

**Independent Test**: Request the canonical control path through a controlled
test double and receive the contracted HTTP `200` response twice with identical
values; separately, run the marked integration test to prove the real FastF1
path when network access is available.

### Tests for User Story 2

- [x] T010 [P] [US2] Write failing deterministic mapping tests for source timestamps, participant ordering, null preservation, circuit fallback, required-data failures, and availability statuses in `backend/tests/test_f1_data.py`
- [x] T011 [P] [US2] Write failing API tests for `/api/v1/seasons/2025/events/italian-grand-prix/sessions/race`, exact response shape, repeated-response equality, and `503 data_source_unavailable` behavior using controlled doubles in `backend/tests/test_sessions.py`
- [x] T012 [P] [US2] Write the separately marked real-data control-session validation without running it during routine tests in `backend/tests/test_f1_data_integration.py`

### Implementation for User Story 2

- [x] T013 [P] [US2] Implement the session, event, circuit, timing, participant, availability, provenance, and error response models from `contracts/openapi.yaml` in `backend/app/models.py`
- [x] T014 [P] [US2] After `backend/uv.lock` pins FastF1, inspect that locked version's actual source and data-loading exception behavior, then implement repo-relative `backend/cache/fastf1/` creation, FastF1 cache activation, control-session loading with laps enabled and telemetry/weather/messages disabled, and narrow source-related exception translation in `backend/app/f1_data.py`; map only justified source failures to `data_source_unavailable` / HTTP `503`, never use broad `except Exception` mapping, and do not guess exception classes before the dependency is locked
- [x] T015 [US2] Implement deterministic FastF1-to-SessionSummary mapping, UTC serialization, stable participant ordering, source-null handling, and required-field checks in `backend/app/f1_data.py`
- [x] T016 [US2] Add the synchronous control-session route and map expected source failures to the contracted HTTP `503` response in `backend/app/main.py`
- [x] T017 [US2] Run and satisfy the routine User Story 2 tests without network access in `backend/tests/test_f1_data.py` and `backend/tests/test_sessions.py`

**Checkpoint**: The control-session API works deterministically with controlled
data and the real-data test exists but remains outside routine execution.

---

## Phase 5: User Story 3 - Preserve Generic Session Direction (Priority: P2)

**Goal**: Accept year, event, and session resource identifiers while limiting
guaranteed support to the documented control tuple.

**Independent Test**: Confirm that the generic route returns the represented
year/event/session for the control request, HTTP `404` for a well-formed tuple
outside current support, and HTTP `422` for malformed path input.

### Tests for User Story 3

- [x] T018 [US3] Write failing tests for generic path parameters, control-tuple identity, malformed `422` responses, unsupported `404 session_not_supported` responses, and no source call for unsupported requests in `backend/tests/test_sessions.py`

### Implementation for User Story 3

- [x] T019 [US3] Add year and slug path validation plus the explicit control-tuple support check to `backend/app/main.py`
- [x] T020 [US3] Add canonical public API-to-FastF1/source identifier resolution in `backend/app/main.py` and parameterize `load_session_summary(...)` in `backend/app/f1_data.py` to accept already-resolved source identifiers without permanently hardcoding the control tuple
- [x] T021 [US3] Run and satisfy the complete generic-resource and error-boundary test set in `backend/tests/test_sessions.py`

**Checkpoint**: The public contract has a generic resource shape without
claiming unsupported dynamic coverage.

---

## Phase 6: User Story 4 - Validate Backend Behavior Automatically (Priority: P2)

**Goal**: Make health and session behavior reproducibly verifiable without
requiring live external data during routine development.

**Independent Test**: Run `uv run pytest` from `backend/`; health, session
mapping, request validation, and source-failure tests pass while the marked
real-data integration test is excluded.

### Tests and Test Configuration for User Story 4

- [x] T022 [P] [US4] Add the regression case proving `GET /health` remains successful when the FastF1 loader fails in `backend/tests/test_health.py`
- [ ] T023 [P] [US4] Register the `integration` marker and exclude it from default pytest execution in `backend/pyproject.toml`
- [ ] T024 [US4] Consolidate controlled fixtures and verify that routine tests cannot accidentally invoke the real FastF1 loader in `backend/tests/conftest.py`, `backend/tests/test_f1_data.py`, and `backend/tests/test_sessions.py`
- [ ] T025 [US4] Run and satisfy the complete network-independent test suite from `backend/`, confirming `backend/tests/test_f1_data_integration.py` is deselected by default

**Checkpoint**: Routine backend behavior is fully automated, deterministic,
and independent of external service availability.

---

## Phase 7: Polish and Cross-Cutting Verification

**Purpose**: Reconcile documentation and contracts, run all quality gates, and
perform the explicit real-data acceptance check.

- [ ] T026 [P] Update backend setup, run, test, and current-status instructions after implementation in `README.md`
- [ ] T027 Compare FastAPI's generated OpenAPI document with `specs/001-backend-f1-data-access/contracts/openapi.yaml` and reconcile route or schema mismatches in `backend/app/main.py` and `backend/app/models.py`
- [ ] T028 Run `uv run ruff format --check .`, `uv run ruff check .`, and the routine `uv run pytest` quality gates from `backend/`, fixing only feature-related findings in `backend/app/` and `backend/tests/`
- [ ] T029 Run the explicit `uv run pytest -m integration` control-session check with network access, verify generated data stays under ignored `backend/cache/fastf1/`, and confirm the cache ignore rule in `.gitignore`
- [ ] T030 Execute every validation scenario in `specs/001-backend-f1-data-access/quickstart.md`, update stale instructions there, and review the final implementation against `specs/001-backend-f1-data-access/spec.md`, `specs/001-backend-f1-data-access/plan.md`, and `.specify/memory/constitution.md`

---

## Dependencies and Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately. T003 depends on T002.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational and establishes the app.
- **User Story 2 (Phase 4)**: Depends on User Story 1 because it extends the
  existing FastAPI application.
- **User Story 3 (Phase 5)**: Depends on User Story 2 because it validates and
  constrains the session endpoint introduced there.
- **User Story 4 (Phase 6)**: Depends on User Stories 1-3 so it can verify the
  complete routine behavior.
- **Polish (Phase 7)**: Depends on all selected user stories.

### User Story Dependency Graph

```text
Setup -> Foundational -> US1 (P1 MVP) -> US2 (P1) -> US3 (P2) -> US4 (P2)
                                                               -> Polish
```

### Within Each User Story

- Write and run story tests first; confirm failure is caused by missing story
  behavior rather than broken test setup.
- Define response models before code that returns them.
- Implement FastF1 loading before deterministic source mapping.
- Implement mapping before the session endpoint consumes it.
- Keep routine verification separate from the marked real-data check.

### Parallel Opportunities

- T010, T011, and T012 can be written in parallel in separate test files.
- T013 and T014 can run in parallel after the User Story 2 tests are in place.
- T022 and T023 can run in parallel in separate files.
- T026 can run in parallel with code-focused contract review after all stories
  are complete.

---

## Parallel Examples by User Story

### User Story 1

No safe within-story parallelism is planned: the health test, response model,
and endpoint form a short tests-first sequence in shared files.

### User Story 2

```text
Parallel test batch:
- T010: backend/tests/test_f1_data.py
- T011: backend/tests/test_sessions.py
- T012: backend/tests/test_f1_data_integration.py

Parallel implementation batch after tests:
- T013: backend/app/models.py
- T014: backend/app/f1_data.py
```

### User Story 3

No safe within-story parallelism is planned because validation, scope handling,
and identifier mapping extend the same endpoint behavior sequentially.

### User Story 4

```text
Parallel verification setup:
- T022: backend/tests/test_health.py
- T023: backend/pyproject.toml
```

---

## Implementation Strategy

### MVP First: User Story 1

1. Complete Setup and Foundational phases.
2. Complete User Story 1 tests and implementation.
3. Stop and verify `GET /health` independently.
4. Continue only after the backend foundation is stable.

### Incremental Delivery

1. **US1**: Running FastAPI service and deterministic health endpoint.
2. **US2**: FastF1-backed control-session response with isolated routine tests.
3. **US3**: Generic resource identifiers with explicit current support limits.
4. **US4**: Complete network-independent regression suite.
5. **Polish**: Contract reconciliation, quality gates, real-data validation,
   cache hygiene, and documentation review.

### Single-Developer Sequence

Execute tasks in numeric order. Do not run T029 as part of routine testing; it
is the explicit external-data acceptance check and may download FastF1 data.

## Notes

- Keep the backend authoritative for all Formula 1 facts.
- Do not add AI, ML, database, frontend, Docker, authentication, deployment, or
  live telemetry work to these tasks.
- Do not fabricate fallback data when FastF1 data is unavailable.
- Do not commit `backend/cache/`, `backend/.venv/`, secrets, or generated test
  artifacts.
- Stop at any checkpoint to validate that story independently.
