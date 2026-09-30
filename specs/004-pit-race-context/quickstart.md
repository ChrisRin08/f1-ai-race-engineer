# Quickstart: Pit-Lane Visits & Lap-Boundary Race Context

This is the planned validation guide for Feature 004. The authoritative
semantics are in [spec.md](spec.md), implementation decisions are in
[research.md](research.md), layered types are in
[data-model.md](data-model.md), and the additive API contract is in
[contracts/openapi.yaml](contracts/openapi.yaml).

## Prerequisites

- uv and Python 3.12 are available;
- the existing reviewed lockfile is synchronized;
- routine tests have no live network access;
- real FastF1 validation is run only with explicit opt-in.

No dependency change is planned for Feature 004.

## Run routine offline validation

From the repository root:

    cd backend
    env -u F1_RUN_INTEGRATION PYTHONDONTWRITEBYTECODE=1 \
      uv run --offline --frozen --no-sync pytest -p no:cacheprovider --collect-only
    env -u F1_RUN_INTEGRATION PYTHONDONTWRITEBYTECODE=1 \
      uv run --offline --frozen --no-sync pytest -p no:cacheprovider -q
    env -u F1_RUN_INTEGRATION PYTHONDONTWRITEBYTECODE=1 \
      uv run --offline --frozen --no-sync ruff format --check .
    env -u F1_RUN_INTEGRATION PYTHONDONTWRITEBYTECODE=1 \
      uv run --offline --frozen --no-sync ruff check --no-cache .

Expected:

- all Feature 001–003 behaviors and assertions pass after any required
  package-import updates;
- Feature 004 normalization, pure analytics, public model, service, API, and
  OpenAPI tests pass;
- integration remains deselected by default;
- the network guard rejects accidental FastF1 acquisition;
- no routine test writes provider cache data;
- no JSON response contains NaN or infinity.

An integration selection without opt-in must skip safely:

    cd backend
    env -u F1_RUN_INTEGRATION PYTHONDONTWRITEBYTECODE=1 \
      uv run --offline --frozen --no-sync pytest -p no:cacheprovider -m integration

## Validate the preliminary package migration

Complete and approve this structural checkpoint before adding any Feature 004
provider field, analytics rule, public model, service, or route.

Expected application layout:

    backend/app/
    ├── __init__.py
    ├── main.py
    ├── data/
    │   ├── __init__.py
    │   └── f1_data.py
    ├── analytics/
    │   ├── __init__.py
    │   ├── lap_analytics.py
    │   └── stint_analytics.py
    ├── models/
    │   ├── __init__.py
    │   ├── session_models.py
    │   ├── pace_models.py
    │   └── stint_models.py
    └── services/
        ├── __init__.py
        ├── pace_service.py
        └── stint_service.py

Run an import smoke check after the moves:

    cd backend
    env -u F1_RUN_INTEGRATION PYTHONDONTWRITEBYTECODE=1 \
      uv run --offline --frozen --no-sync python -c \
      "import app.main; import app.data.f1_data; import app.analytics.lap_analytics; import app.analytics.stint_analytics; import app.models.session_models; import app.models.pace_models; import app.models.stint_models; import app.services.pace_service; import app.services.stint_service"

Then run the entire existing Feature 001–003 suite and Ruff commands from the
routine validation section. Before moving files, capture the generated
app.openapi() document in canonical JSON; after the migration, regenerate it
and require exact equality. Also verify:

- all existing route paths, operation IDs, response schemas, policies, errors,
  and test assertions are unchanged;
- FASTF1_CACHE_DIR still resolves to backend/cache/fastf1 even though
  f1_data.py moved one directory deeper;
- backend/pyproject.toml and backend/uv.lock have no diff;
- the diff contains only the eight file moves, four package markers, explicit
  import/module-path rewrites, and the cache-path depth preservation;
- no compatibility wrapper, re-export, algorithm edit, cleanup, or Feature 004
  behavior appears; and
- a fresh independent reviewer approves this checkpoint.

Do not begin Feature 004 normalization until all migration checks pass and the
independent review is complete.

## Validate provider isolation

Controlled provider-shaped fixtures must prove:

- Session.results is the authoritative roster and preserves a participant with
  no lap rows;
- lap rows cannot create a participant;
- LapNumber, Position, Stint, timestamps, booleans, compound, and classification
  facts normalize to builtin immutable values;
- Time, PitInTime, and PitOutTime retain exact integer nanoseconds until
  analytical publication;
- NumPy scalars, Pandas NaT/NaN, infinity, malformed values, missing optional
  fields, and duplicate consumed labels do not leak;
- duplicate source rows remain represented rather than overwritten;
- TrackStatus is mapped to ordered de-duplicated normalized labels, including
  mixed and unknown codes;
- unknown status cannot produce is_disrupted false;
- FastF1Generated remains nullable and explicit;
- data/f1_data.py is the only FastF1/Pandas-aware Feature 004 layer; and
- telemetry, weather, messages, private timing APIs, and cache internals remain
  unused.

## Validate pure race-context analytics

Pure immutable-input tests must prove:

### Lap-boundary context

- one compact item per authoritative driver/lap identity;
- exact duplicate evidence retains multiplicity;
- contradictory duplicates retain conflict and suppress affected derivatives;
- a unique trusted Position 1 observation establishes the lap leader;
- missing or conflicting leader evidence is not reconstructed from minimum
  completion Time;
- a leader and driver completing together can produce zero milliseconds;
- a later same-lap completion produces a positive equal-distance deficit;
- a contradictory negative driver-minus-leader result is unavailable;
- laps_behind uses the leader's latest trusted completion at or before the
  selected driver's completion timestamp;
- a positive lap deficit makes equal-distance time not_applicable and null;
- no interpolation predicts a lapped driver's future completion;
- generated rows remain auditable but cannot establish trusted leader,
  completion, deficit, or pit facts;
- non-starters and retirees retain authoritative participant entries; and
- source-row permutations produce identical central results.

### Track context

- green supports false only with trustworthy fully understood evidence;
- yellow, Safety Car, VSC, VSC ending, and Red Flag each support true;
- mixed statuses stay ordered and de-duplicated;
- known disruption plus unknown remains true;
- unknown without a known disruption produces null;
- missing or malformed status produces unavailable and null; and
- disrupted observations remain in the lap series.

### Pit evidence

- one normal complete visit;
- multiple complete visits;
- no visit;
- initial unpaired exit for a pit-lane start;
- terminal unpaired entry for a retirement;
- entry-before-entry, exit-before-exit, equal timestamps, reversed timestamps,
  and other ambiguous associations;
- exact duplicate boundary multiplicity and contradictory boundary conflicts;
- asserted but unusable boundary evidence;
- missing completion context without nearby-lap fallback;
- same and changed reported compound/stint values;
- unavailable compound/stint context;
- entry-to-exit elapsed derived from exact timestamps before rounding; and
- every source boundary occurrence reconciled exactly once.

### Determinism and precision

- half-up values immediately below, at, and above a half-millisecond boundary;
- endpoint rounding is never performed before subtraction;
- canonical participant, lap, status, boundary, and pit order;
- at least three identical executions produce equal results; and
- no pure analytics module imports FastF1, Pandas, FastAPI, or Pydantic.

## Validate strict public construction

Direct model tests must accept canonical valid structures and reject:

- noncanonical participant/lap order and boundary/pit-evidence order violations
  provable from exposed public fields;
- duplicate statuses and invalid enum/availability/disruption combinations;
- duplicate participant or driver/lap public identities;
- available equal-distance state without laps_behind zero and a value;
- not_applicable without positive laps_behind or with a time value;
- unavailable state with a time value;
- a complete visit without one trusted entry and one later trusted exit;
- elapsed values on unpaired, conflicting, or unavailable evidence;
- change flags without two usable reported values;
- mismatched driver/lap references or pit-state counts;
- booleans accepted as integers, coercible numeric strings, NaN, or infinity;
  and
- any attempted silent sorting, deduplication, pairing, or repair.

Ordering acceptance checks under FR-062–FR-065 and SC-013 must include:

1. Two distinct exact timestamps, such as 1,100,000 ns and 1,200,000 ns,
   collapse to the same published millisecond under ROUND_HALF_UP.
2. A canonical central projection with the earlier boundary on lap 2 and the
   later boundary on lap 1 remains accepted when both public timestamps are
   1 ms. Cover boundaries within conflicting evidence and chronology-bearing
   pit evidence items.
3. Validators do not treat equal published milliseconds as exact timestamp
   ties or descend into lap/kind/state keys on that basis. Distinct published
   timestamps and usable-versus-absent chronology still expose order violations;
   genuinely absent chronology permits lower keys only where domain policy
   makes their relationship provable. No ambiguous input is sorted or repaired.
4. Supported TrackStatus sequences such as green/yellow and yellow/green are
   preserved by projection and accepted when their availability and disruption
   facts are consistent. Validation checks uniqueness and the truth table,
   without reconstructing source order or sorting by enum declaration.

Central analytics remains the authoritative owner of exact canonical order.
Services and projections preserve it exactly. Public ambiguity does not
authorize another order or rejection of an otherwise valid central projection.
Extra fields, missing required nullable fields, scalar coercion, duplicate
identities, reference/count mismatches, and state/field contradictions still
fail strict construction.

## Validate one central analysis

Service tests must inject controlled functions and establish exactly:

- one load_session call;
- one map_race_context_inputs call;
- one map_session_summary call using the same loaded Session;
- one analyze_race_context call;
- no per-driver, per-lap, per-reference, or per-pit reload;
- the compact session and driver-detail mappers consume the central result;
- counts, latest context, leader references, deficits, and visits are not
  recomputed in service code;
- a known participant with unavailable evidence still returns detail; and
- an unknown canonical participant returns driver_not_found only after the one
  complete analysis.

## Start and inspect the API

Start the existing service:

    cd backend
    uv run --frozen --no-sync uvicorn app.main:app --reload

Confirm existing resources still respond:

    curl --fail --silent http://127.0.0.1:8000/health
    curl --fail --silent \
      http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race
    curl --fail --silent \
      http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/pace
    curl --fail --silent \
      http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/tire-stints

Expected: Feature 001–003 shapes, operation IDs, policy values, and error
semantics are unchanged.

Inspect the compact session projection:

    curl --fail --silent \
      http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/race-context

Expected:

- exactly one compact entry per authoritative participant;
- canonical participant order;
- final classification context and latest available lap context;
- explicit pit-state counts, including zero visits;
- no complete lap_contexts or pit_evidence arrays; and
- source provider FastF1.

Inspect one driver detail:

    curl --fail --silent \
      "http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/race-context/drivers/$DRIVER_NUMBER"

Set DRIVER_NUMBER from the compact response. Expected:

- the same compact participant summary;
- the complete canonical compact lap-context series;
- all complete, unpaired, conflicting, and unavailable pit evidence;
- explicit status/value combinations for laps_behind and
  equal_distance_time_deficit_ms;
- ordered track_statuses plus availability and nullable is_disrupted;
- provider-generated state and source multiplicity/conflict evidence;
- pit context taken from the entry/in-lap and exit/out-lap rows only; and
- no raw provider rows.

The API must describe Position as provider-exposed lap-completion race
position, equal-distance deficit as same-completed-lap elapsed separation, and
pit elapsed as entry-to-exit time. It must not claim a live gap, physical
separation, stationary service time, or confirmed physical tire change.

## Validate error boundaries

- malformed driver 01: 422 before source loading;
- unsupported session tuple: 404 session_not_supported before source loading;
- canonical absent driver 999: 404 driver_not_found after one analysis;
- expected provider/schema failure: sanitized 503 data_source_unavailable;
- unexpected defect: framework 500 without private detail disclosure.

## Run explicit real-source acceptance

Run only when provider/network access is separately authorized:

    cd backend
    F1_RUN_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
      uv run --frozen --no-sync pytest -m integration

The Monza acceptance validates public-provider schema compatibility,
authoritative roster inclusion, ordinary and incomplete pit evidence, mixed
status normalization, deterministic ordering, one-snapshot analysis,
provenance, evidence reconciliation, and finite JSON. It does not freeze
incidental driver outcomes, exact visit counts, 53 laps, every starter
finishing, or the absence of Safety Car/Red Flag as business rules.

## Final repository audit

    git diff --check
    git status --short
    git diff -- backend/pyproject.toml backend/uv.lock
    git check-ignore -v backend/cache/fastf1/
    git ls-files backend/cache backend/data

Expected:

- no dependency or lockfile change;
- no cache or generated provider data tracked;
- no Feature 001–003 contract or behavior change;
- no private provider, telemetry, frontend, strategy, AI/ML, database,
  deployment, or pit-only-resource work; and
- planning artifacts remain consistent with the implemented public OpenAPI.
