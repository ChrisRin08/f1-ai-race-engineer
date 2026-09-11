# Quickstart: Lap Data & Driver Pace

This guide defines the validation path for the feature. Real-data downloads
remain intentional, separately opted-in validation, not routine testing.
The detailed policy and shapes live in [data-model.md](data-model.md) and
[contracts/openapi.yaml](contracts/openapi.yaml).

## Prerequisites

- uv installed
- Python 3.12 available to uv
- the environment synchronized from the committed lockfile
- network access only for intentional real FastF1 validation

All commands start from the repository root unless stated otherwise.

## Install the Locked Backend Environment

```bash
cd backend
uv sync --locked
```

No new dependency is required by this feature. Implementation must not change
`backend/pyproject.toml` or `backend/uv.lock` unless a separately approved plan
revision justifies it.

## Run Routine Offline Validation

Keep `F1_RUN_INTEGRATION` unset:

```bash
cd backend
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync pytest --collect-only
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync pytest
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync ruff format --check .
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync ruff check --no-cache .
```

Expected results:

- all routine unit, source-adapter, service, API, and OpenAPI tests pass;
- integration tests are deselected by the default pytest configuration;
- the autouse test guard fails any accidental `fastf1.get_session` call;
- formatting and lint checks pass;
- application import, health tests, and routine analytics tests do not create
  `backend/cache/fastf1/` or `backend/data/`.

Explicit integration selection without opt-in must skip safely and remain
offline:

```bash
cd backend
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync pytest -m integration
```

## Validate the Pure Pace Policy

The routine suite must use controlled lap inputs to prove:

- first-match precedence is `invalid_timing`, `lap_one_start`, `pit_in`,
  `pit_out`, `disrupted_status`, then `anomalous_pace`;
- a lap record with an unusable `LapTime` or unusable `LapNumber` is
  `invalid_timing` because it lacks the minimum timing identity needed to
  calculate pace, identify Lap 1, and order evidence;
- usable durations are at least 500,000 ns; smaller values normalize to null
  and receive `invalid_timing`, with the source row still counted;
- Lap 1 and pit-in/pit-out laps are excluded;
- any of FastF1 status codes `2`, `4`, `5`, `6`, or `7` excludes a lap even
  when multiple codes are present;
- missing and unknown per-row status values remain explicit diagnostics without
  fabricated status meaning;
- false or unavailable `IsAccurate` never excludes an otherwise eligible lap;
- compound alone never excludes dry, intermediate, or wet laps;
- a lap exactly at 120% of the driver's structural/status-filtered fastest lap
  remains eligible, while a greater value is anomalous;
- because the v1 anomaly rule is not condition-aware, a legitimate lap in
  substantially slower conditions can still exceed 120% and be classified as
  `anomalous_pace`;
- exactly five representative laps publishes metrics and fewer than five
  produces `insufficient_data`;
- source and exclusion counts reconcile exactly;
- median, mean, fastest, and population standard deviation use unrounded source
  durations and publish half-up integer milliseconds;
- median, mean, and fastest cannot publish as 0 ms because every representative
  duration is at least 500,000 ns; five equal minimum-duration laps publish
  those three metrics as 1 ms and population standard deviation as 0 ms;
- ranks, ties, delta-to-best, and signed A-minus-B comparison agree with
  published medians;
- reversing A and B reverses the sign without changing magnitude;
- repeated analysis of the same inputs is identical;
- duplicate/noncanonical result driver numbers and unattributable lap rows are
  rejected as source-data failures rather than silently dropped.

Use these controlled timing boundaries in source-adapter and pure-policy tests:

| Source duration | Expected timing decision | Published lap duration |
|---|---|---|
| 0 ns | `invalid_timing` | null |
| Negative duration (for example -1 ns) | `invalid_timing` | null |
| 1 ns | `invalid_timing` | null |
| 499,999 ns | `invalid_timing` | null |
| 500,000 ns | Valid timing input | 1 ms |
| 500,001 ns | Valid timing input | 1 ms |

Valid timing still has to pass all remaining representative-lap rules. Do not
clamp rounded zero values to 1 ms or weaken the public minimum. Standard
deviation and deltas retain their existing valid zero cases.

## Start the API

```bash
cd backend
uv run --frozen --no-sync uvicorn app.main:app --reload
```

The service listens at `http://127.0.0.1:8000`.

## Confirm Existing Behavior

```bash
curl --fail --silent http://127.0.0.1:8000/health
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race
```

Expected results:

- health remains exactly `{"status":"ok"}` and does not access FastF1;
- the existing session-summary shape and operation ID remain unchanged.

## Validate Analytics Resources

These calls may contact FastF1 on first use and therefore belong to intentional
real-data validation, not routine test execution.

Session field analysis:

```bash
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/pace
```

Expected result: a strict `SessionPaceAnalysisResponse` containing every
results participant, one policy object, available drivers ordered by published
median, insufficient drivers afterward, competition ranks, delta-to-best, and
FastF1 provenance. The policy reports `track_conditions_adjusted: false` and
does not imply that every legitimate wet or intermediate lap survives the
condition-unaware anomaly rule.

Individual driver analysis:

```bash
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/pace/drivers/1
```

Expected result: driver `1` plus every associated source lap classified once.
The lap count equals the summary source count, excluded laps have one primary
reason, and the two reconciliation equations in the data model hold.

Directional comparison:

```bash
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/pace/drivers/1/comparisons/4
```

Expected result: Driver A is `1`, Driver B is `4`, and `delta_ms` equals A's
published median minus B's. Its sign and outcome agree. Reversing the path
operands reverses the sign for an available comparison.

Repeat any unchanged control request and compare parsed JSON. The complete
response must be identical; no request timestamp or cache-hit metadata is part
of the contract.

## Validate Error Boundaries

Unsupported session, before source loading:

```bash
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:8000/api/v1/seasons/2024/events/italian-grand-prix/sessions/race/pace
```

Expected: `404 session_not_supported` and no FastF1 call.

Malformed driver number, before source loading:

```bash
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/pace/drivers/01
```

Expected: FastAPI `422` and no FastF1 call.

Well-formed unknown driver, after one shared analysis:

```bash
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/pace/drivers/999
```

Expected: `404 driver_not_found`. Controlled tests, rather than live calls,
must prove known-participant `insufficient_data`, expected `503`, unexpected
`500`, and exact source-load counts.

## Run Explicit Real FastF1 Validation

Run only when network/source access is intentional:

```bash
cd backend
F1_RUN_INTEGRATION=1 uv run --frozen --no-sync pytest -m integration
```

Expected result: marked integration tests load the 2025 Italian Grand Prix
Race through application-owned boundaries and validate Monza identity,
FastF1 provenance, participants, usable field analytics, finite published
metrics, count reconciliation, ranks, and deltas. Provider or network failure
is reported honestly rather than replaced with fixture data.

## Final Repository Checks

```bash
git diff --check
git status --short
git check-ignore -v backend/cache/fastf1/
git ls-files backend/cache backend/data
```

Expected results:

- no whitespace errors;
- generated FastF1 cache content remains ignored and untracked;
- `backend/data/` remains absent;
- dependencies and lockfile are unchanged;
- no frontend, database, AI, ML, telemetry, weather, race-control-message,
  strategy, deployment, or unrelated feature work appears in the feature diff.
