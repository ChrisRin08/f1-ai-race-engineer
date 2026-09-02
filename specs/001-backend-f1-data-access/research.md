# Phase 0 Research: Backend Foundation & F1 Data Access

## Python Project and Dependency Management

**Decision**: Make `backend/` an independent uv-managed Python 3.12 application
with `pyproject.toml`, `.python-version`, and a committed `uv.lock`. Keep runtime
dependencies separate from a development dependency group containing pytest,
HTTPX, and Ruff.

**Rationale**: The repository already chose uv and independently scoped
frontend/backend tooling. uv treats `pyproject.toml` as the project definition,
uses a local `.venv`, and documents `uv.lock` as a cross-platform lockfile that
should be committed for reproducible environments.

**Alternatives considered**: A root Python project would blur the monorepo
boundary. `requirements.txt` would duplicate dependency metadata and give up
uv's project/lock workflow. A publishable package/build backend is unnecessary
for this local web application.

Sources: [uv projects](https://docs.astral.sh/uv/guides/projects/),
[uv dependencies](https://docs.astral.sh/uv/concepts/projects/dependencies/)

## Minimal Application Structure

**Decision**: Use one `app` package with `main.py`, `models.py`, and
`f1_data.py`.

**Rationale**: The API already has two distinct responsibilities: HTTP behavior
and external F1 data access. One module boundary makes source behavior easy to
replace in tests while remaining small enough to explain directly.

**Alternatives considered**: Putting all logic in `main.py` would couple API
tests to FastF1. Router/service/repository/domain layers would add structure
without current behavior to justify it.

Source: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)

## API Resource Shape

**Decision**: Model session retrieval as
`/api/v1/seasons/{year}/events/{event}/sessions/{session}`. The first canonical
values are `2025`, `italian-grand-prix`, and `race`.

**Rationale**: This makes the documented `year -> event -> session` direction
explicit while allowing the implementation to enforce one control tuple. URL
slugs avoid spaces and keep identifiers independent from FastF1's accepted
aliases.

**Alternatives considered**: Query parameters are simpler syntactically but do
not express the resource hierarchy as clearly. A one-off `/monza` endpoint
would turn the control dataset into an API limitation.

## FastF1 Loading Profile

**Decision**: Enable the repo-local FastF1 cache, obtain the session with
`fastf1.get_session`, and load laps while disabling telemetry, weather, and
race-control messages. Map session/event metadata, results, and lap
availability into the response.

**Rationale**: FastF1 exposes most session properties after `Session.load` and
supports selective loading. Results provide participating drivers and teams;
lap loading proves timing-data access and supports a truthful availability
summary without downloading telemetry that this feature does not return.

**Alternatives considered**: Loading every data category would increase network
and cache cost with no accepted use case. Loading metadata only would not prove
the first meaningful timing-data path needed by the demo.

Sources: [FastF1 Session source](https://github.com/theOehrly/Fast-F1/blob/v3.8.3/fastf1/core.py),
[FastF1 releases](https://github.com/theOehrly/Fast-F1/releases)

## Cache Policy

**Decision**: Use `backend/cache/fastf1/`, resolved from the backend project
path and created on first data access. Rely on the existing `backend/cache/`
Git ignore rule. Do not add eviction or deployment-specific storage.

**Rationale**: FastF1 recommends caching because session retrieval is expensive.
The path is repository-relative, portable, and consistent with project
documentation. Cache growth is already recorded as a concern to revisit before
containerized or production deployment.

**Alternatives considered**: A user-home cache is machine-specific. A tracked
cache would commit generated data. Configurable volumes and eviction policies
belong to later deployment work.

Source: [FastF1 package documentation](https://pypi.org/project/fastf1/)

## Blocking I/O Boundary

**Decision**: Implement the session path operation as a synchronous function.

**Rationale**: FastF1 performs blocking work. FastAPI runs synchronous path
operations in a worker thread, keeping that work off the event loop without
introducing a task queue or custom concurrency layer.

**Alternatives considered**: Declaring the route `async` while directly calling
FastF1 would block the event loop. Background jobs would change the API into an
asynchronous workflow that the feature does not require.

Source: [FastAPI async guidance](https://fastapi.tiangolo.com/async/)

## Response Modeling and Determinism

**Decision**: Use explicit Pydantic response models, normalize timestamps to
UTC ISO 8601 JSON values, preserve source nulls, and use a stable participant
ordering based on source classification. Include `source.provider = "FastF1"`
but no request-time timestamp or cache-hit flag.

**Rationale**: FastAPI response models validate, document, serialize, and
filter output. Excluding volatile request metadata ensures repeated responses
for the same FastF1 snapshot remain equal.

**Alternatives considered**: Returning Pandas/FastF1 objects directly would
leak unstable, non-JSON-native structures. Adding `retrieved_at` would make an
otherwise unchanged response non-deterministic.

Source: [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/)

## Error Semantics

**Decision**: Use `422` for malformed path input, `404` with
`session_not_supported` for a well-formed tuple outside the current supported
scope, and `503` with `data_source_unavailable` for a supported request that
cannot be loaded. Do not convert unexpected programming errors into source
errors.

**Rationale**: This separates client input/scope problems from temporary
dependency failures as required by the clarified spec. Narrow exception
translation avoids hiding defects.

**Alternatives considered**: Returning `404` for every failure would hide
outages. Catching every exception and returning `503` would misclassify coding
errors and make diagnosis harder.

Source: [FastAPI error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)

## Test Boundary

**Decision**: Use FastAPI `TestClient` for HTTP behavior, controlled objects or
fixtures for FastF1 mapping, and a pytest `integration` marker excluded from
the default run. The explicit integration run loads the Monza control session.

**Rationale**: Routine tests remain fast and deterministic while the separate
check still verifies the real source path. HTTPX is an explicit development
dependency because FastAPI's TestClient requires it.

**Alternatives considered**: Requiring live FastF1 access in every test run
would make tests slow and flaky. Omitting real-data validation would leave the
core external integration unproven.

Source: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)

## Lint and Format Configuration

**Decision**: Configure Ruff in `backend/pyproject.toml` for Python 3.12 and use
it for both linting and formatting.

**Rationale**: One local configuration keeps backend checks discoverable and
matches the selected toolchain without adding another formatter.

**Alternatives considered**: Separate configuration files are unnecessary for
this small backend. Adding mypy now would expand the approved toolchain and
quality surface before it is required.

Source: [Ruff configuration](https://docs.astral.sh/ruff/configuration/)
