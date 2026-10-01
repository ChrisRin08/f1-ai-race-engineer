# Implementation Plan: Pit-Lane Visits & Lap-Boundary Race Context

**Branch**: 004-pit-race-context | **Date**: 2026-09-25 | **Spec**:
[spec.md](spec.md)

**Input**: Feature specification from
specs/004-pit-race-context/spec.md at checkpoint
8122cd22b8f9674a280ad2c436cf3d14e1945fdb.

## Summary

Extend the existing Python 3.12 FastAPI modular monolith with one deterministic,
auditable race-context analysis derived from supported public FastF1 session
data. A new provider mapper converts one loaded Session snapshot into immutable
Feature 004 participant and lap-row facts while preserving missing, invalid,
duplicate, generated, and contradictory evidence. Pure analytics consolidates
lap observations, identifies the same-lap provider-position leader, derives
lap-deficit and equal-distance time semantics, associates pit boundaries
conservatively, and produces one reusable central result. Two additive public
projections expose a compact complete-field session view and an auditable
driver detail without independently recalculating shared facts.

Before Feature 004 behavior begins, the existing application modules move in
one bounded, behavior-preserving group into shallow data, analytics, models, and
services packages. main.py remains the transport entry point. The complete
Feature 001–003 regression suite and a fresh independent review gate the
migration before Feature 004 adds one focused module to each analytical,
public-model, and service package. There is no dependency addition, telemetry,
private-provider API, persistence, strategy simulation, frontend, or
Feature 001–003 behavior change.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Existing FastAPI 0.141.x, FastF1 3.8.3, Pandas 2.3.x,
NumPy 2.5.x, and Pydantic 2.13.x; Python standard-library dataclasses, enum,
collections, and exact integer arithmetic

**Storage**: No application persistence; existing ignored FastF1 disk cache at
backend/cache/fastf1/

**Testing**: pytest 8.x, FastAPI TestClient, controlled Pandas/NumPy provider
fixtures, pure immutable analytics fixtures, Ruff, and separately opted-in
FastF1 integration

**Target Platform**: Local macOS/Linux development and the existing portable
synchronous ASGI service

**Project Type**: Backend web service within the existing monorepo modular
monolith

**Performance Goals**: Exactly one supported FastF1 session acquisition, one
Feature 004 normalization, and one central race-context analysis per operation;
both public projections reuse central results; deterministic processing for one
race field and race distance; no unsupported latency SLA

**Constraints**: Preserve FR-001 through FR-065 and SC-001 through SC-013;
preserve every Feature 001–003 public contract and policy; use public
Session.laps and Session.results only; telemetry remains disabled; strict finite
JSON; no private timing API, live-gap claim, stationary-service claim, physical
tire-change confirmation, strategy, AI/ML, frontend, database, deployment, or
Monza-specific rule; package migration must be isolated, behavior-preserving,
fully regressed, and independently approved before Feature 004 behavior begins

**Scale/Scope**: One supported race session per request, approximately one
Formula 1 field and race distance; two additive race-context GET resources;
future Feature 005 reuse of the central domain result

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Gate | Result |
|---|---|---|
| Deterministic Analytics Before AI | Pure analytics owns consolidation, leader selection, deficits, pit association, state selection, canonical ordering, and publication rounding | Pass |
| Real Data and Provenance | Supported public FastF1 session data is the sole source; generated, missing, duplicate, and conflicting evidence stays explicit | Pass |
| Testable, Verifiable Engineering | Offline normalization, analytics, model, service, API, OpenAPI, regression, and opted-in real-source checks are designed | Pass |
| Incremental Complexity | One bounded shallow responsibility-package migration precedes three focused Feature 004 modules; no feature-number packages, second loader, repository, factory, interface, or new infrastructure | Pass |
| Explainability and Learning | Public states, source multiplicity, leader references, lap references, and provenance explain values and unavailability | Pass |
| Security and Configuration Hygiene | No secrets, new network path, deployment, or configuration; existing ignored cache boundary remains | Pass |
| Quality Over Token/Speed Optimization | Conservative ambiguity handling, strict construction, exact arithmetic, and regression protection take priority | Pass |
| Spec-Driven Feature Development | The approved specification and five owner decisions govern all design choices | Pass |

Post-design re-check: research, the layered data model, additive contract, and
quickstart preserve every gate. No constitution exception or complexity waiver
is required.

## Project Structure

### Documentation for this feature

    specs/004-pit-race-context/
    ├── plan.md
    ├── research.md
    ├── data-model.md
    ├── quickstart.md
    ├── contracts/
    │   └── openapi.yaml
    └── checklists/
        └── requirements.md

tasks.md is intentionally absent. It belongs to the later task-generation stage.

### Final source layout after the bounded migration and Feature 004

    backend/
    ├── app/
    │   ├── __init__.py
    │   ├── main.py
    │   ├── data/
    │   │   ├── __init__.py
    │   │   └── f1_data.py
    │   ├── analytics/
    │   │   ├── __init__.py
    │   │   ├── lap_analytics.py
    │   │   ├── stint_analytics.py
    │   │   └── race_context_analytics.py
    │   ├── models/
    │   │   ├── __init__.py
    │   │   ├── session_models.py
    │   │   ├── pace_models.py
    │   │   ├── stint_models.py
    │   │   └── race_context_models.py
    │   └── services/
    │       ├── __init__.py
    │       ├── pace_service.py
    │       ├── stint_service.py
    │       └── race_context_service.py
    └── tests/
        ├── conftest.py                    # Later add Feature 004 provider fixture
        ├── test_f1_data.py                # Migration import + new normalization
        ├── test_f1_data_integration.py    # Migration import + Monza acceptance
        ├── test_health.py                 # Migration imports only
        ├── test_lap_analytics.py          # Migration imports only
        ├── test_openapi.py                # Migration import + additive contract
        ├── test_pace_api.py               # Migration imports only
        ├── test_pace_service.py           # Migration imports only
        ├── test_sessions.py               # Migration imports only
        ├── test_stint_analytics.py        # Migration imports/module string only
        ├── test_stint_api.py              # Migration imports only
        ├── test_stint_service.py          # Migration imports only
        ├── test_race_context_analytics.py # New pure analysis tests
        ├── test_race_context_api.py       # New model/route tests
        └── test_race_context_service.py   # New orchestration/projection tests

Implementation documentation is expected to update README.md,
docs/architecture.md, and docs/demo-v0.1.md narrowly. backend/pyproject.toml,
backend/uv.lock, prior feature specification artifacts, and test locations do
not change.

**Structure Decision**: Use four shallow responsibility packages. The current
eight root modules already span provider, analytics, public-model, and service
roles; Feature 004 adds another module in three of those roles and Feature 005
will reuse its analytical domain result. The migration resolves the models.py
file/package collision by renaming that file to models/session_models.py.
Package __init__.py files stay empty or declaration-only; explicit module paths
avoid hidden imports. main.py remains at app/main.py because it is the single
transport/composition entry point and no route split is justified.

### Exact existing file moves

| From | To |
|---|---|
| backend/app/f1_data.py | backend/app/data/f1_data.py |
| backend/app/lap_analytics.py | backend/app/analytics/lap_analytics.py |
| backend/app/stint_analytics.py | backend/app/analytics/stint_analytics.py |
| backend/app/models.py | backend/app/models/session_models.py |
| backend/app/pace_models.py | backend/app/models/pace_models.py |
| backend/app/stint_models.py | backend/app/models/stint_models.py |
| backend/app/pace_service.py | backend/app/services/pace_service.py |
| backend/app/stint_service.py | backend/app/services/stint_service.py |

The migration also adds data/__init__.py, analytics/__init__.py,
models/__init__.py, and services/__init__.py. It updates imports in the moved
modules, main.py, and the eleven listed existing test modules. It makes the
single required path-depth adjustment in moved data/f1_data.py so the existing
FASTF1_CACHE_DIR remains backend/cache/fastf1. No algorithm, model, route,
policy, exception, loader flag, dependency, or test assertion changes.

## Preliminary Implementation Sequence

The implementation order is a hard gate:

    responsibility-package migration
      -> complete unchanged Feature 001–003 offline regression
      -> Ruff format/lint, import smoke, OpenAPI equality, and cache-path check
      -> fresh independent review and explicit approval
      -> Feature 004 provider normalization
      -> Feature 004 pure race-context analytics
      -> Feature 004 public models, service projections, and API routes
      -> complete Feature 001–004 validation and opted-in acceptance

Feature 004 code must not begin before the migration regression and independent
review pass. The preliminary group contains moves, explicit import rewrites,
four package markers, and the cache-path depth preservation only. Unrelated
cleanup is excluded.

## Architecture and Data Flow

    FastF1 Session.laps / Session.results
                  |
                  v
    data.f1_data.map_race_context_inputs
      - provider schemas and scalar conversion
      - missing/invalid/value-quality states
      - status-code normalization
      - every source occurrence preserved
                  |
                  v
    immutable application-owned RaceContextInput
                  |
                  v
    analytics.race_context_analytics.analyze_race_context exactly once
      - consolidate lap evidence
      - establish lap leaders
      - derive laps behind and equal-distance deficit
      - associate pit boundaries
      - assemble summaries and canonical central result
                /   \
               v     v
    compact session  auditable driver detail
       projection      projection
                \     /
                 v   v
        strict public result models
                  |
                  v
           thin FastAPI routes

Future Feature 005 consumes the central analytical result. It does not import
Pydantic response models and does not reimplement leader identification,
lap-deficit calculation, or pit association.

### Package dependency rules

- analytics/lap_analytics.py imports no application data, model, service, or
  transport module;
- analytics/stint_analytics.py imports analytics/lap_analytics.py only within
  the application;
- data/f1_data.py imports immutable analytical input types and
  models/session_models.py, preserving the existing one-way dependencies;
- public model modules may import analytical enums/types and lower-level model
  modules, but never data, services, or main;
- service modules import data, analytics, and public models;
- services/stint_service.py may continue to import DriverNotFoundError from
  services/pace_service.py; the reverse dependency does not exist;
- main.py imports data, models, and services; no application module imports
  main.py; and
- package __init__.py files do not re-export modules or trigger eager imports.

This explicit direction keeps the observed graph acyclic without adding a
shared-interface or error-abstraction module.

## Provider Normalization Design

data/f1_data.py remains the only module that imports or interprets FastF1/Pandas
objects. After its independent move, a new map_race_context_inputs(session)
operation consumes the already loaded snapshot and returns:

- one authoritative normalized participant for every Session.results entry,
  including non-starters and participants without lap rows;
- every Session.laps row occurrence with driver, lap number, exact session Time,
  provider-exposed lap Position, exact PitInTime and PitOutTime, TrackStatus,
  FastF1Generated, Compound, and Stint evidence;
- explicit available, absent, or invalid state where null alone would erase
  evidence meaning; and
- participant-level counts for rows that cannot be associated safely.

Provider conversion rules:

- finite positive integral LapNumber, Position, and Stint become Python int;
- provider duration/timestamp scalars become exact non-negative integer
  nanoseconds;
- Pandas/NumPy missing and non-finite values never cross the boundary;
- actual provider booleans become Python bool and missing assertions remain
  null;
- compound is trimmed and case-preserved; no tire-change inference occurs;
- TrackStatus codes map in observation order to green, yellow, safety_car,
  red_flag, virtual_safety_car, virtual_safety_car_ending, or unknown;
- missing or malformed status is unavailable, and unknown never means green;
- duplicate consumed column labels are a sanitized provider/schema failure;
- duplicate rows and result entries remain represented with multiplicity; and
- source ordinal is diagnostic only and never resolves domain ambiguity.

The existing load_session configuration remains telemetry=False,
weather=False, and messages=False. Feature 004 does not change
map_lap_inputs(), SourceLap, or earlier-feature policies.

## Pure Analytical Design

analytics/race_context_analytics.py contains the new immutable normalized input
types, domain result types, and one public coordinator. A small number of
cohesive private transformations avoid both a giant function and one-use
abstraction layers.

### Consolidate lap evidence

Group by authoritative driver and valid positive lap number. Produce exactly
one compact item per driver/lap. Identical normalized repeats retain
source_evidence_count; incompatible values retain conflict state and suppress
only derivatives without a single source-backed interpretation. Unkeyable rows
remain participant-level unavailable accounting.

Provider-generated rows remain auditable but their potentially assumed
timestamps do not establish trusted completion, leader, deficit, or pit facts.

### Establish leaders and lap-boundary context

For lap n, accept the unique trustworthy compact observation with
provider-exposed completion Position 1 as the lap leader. Do not infer a leader
from minimum Time.

For each trustworthy selected-driver completion at n and t:

- select the greatest trusted leader lap L completed at or before t;
- publish laps_behind = L - n only when non-negative and unambiguous;
- if L is greater than n, set equal-distance status to not_applicable and its
  value to null;
- if L equals n and both same-lap times are trusted, calculate selected driver
  Time(n) minus leader Time(n);
- withhold a contradictory negative difference as unavailable;
- never interpolate or predict a lapped driver's future completion.

The domain retains the leader reference, exact nanoseconds, published
milliseconds, status, track context, generated state, position, and
multiplicity needed for audit and future reuse.

### Normalize disrupted context

Status values remain ordered and de-duplicated. is_disrupted is:

- true when any known yellow, Safety Car, VSC, VSC ending, or Red Flag value is
  present;
- false only when status evidence is trustworthy, completely understood, and
  has no known disrupted value;
- null when evidence is unavailable or unknown prevents a trustworthy false.

Disrupted observations remain in the lap series.

### Associate pit evidence

Build logical entry/exit candidates from the boundary timestamps carried by
their own rows. Coalesce exact repeats with multiplicity, mark incompatible
claims conflicting, and order usable candidates by timestamp then lap without
using row adjacency.

A per-driver state machine:

- retains an exit without an open entry as unpaired_exit;
- holds one trusted entry open;
- forms complete only with the next unique trusted, strictly later exit whose
  lap identity is nondecreasing and has no competing boundary;
- retains an open terminal entry as unpaired_entry;
- groups entry-before-entry, competing, equal-time, reversed-time, or otherwise
  non-unique evidence as conflicting; and
- retains asserted unusable boundary evidence as unavailable.

Each source occurrence is accounted for exactly once through a compact boundary
and multiplicity. Entry context is the PitInTime row and exit context is the
PitOutTime row. There is no neighboring-racing-lap fallback and no requirement
that exit lap equal entry lap plus one.

entry_to_exit_elapsed is exact exit minus entry and is published only after
subtraction. Reported compound/stint changes are differences in reported
values, never confirmation of a physical tire change.

### Publish timing

All subtraction uses exact integer nanoseconds. Non-negative session
timestamps, elapsed values, and deficits are published once with half-up
millisecond rounding. Endpoints are never independently rounded before
subtraction. The existing semantically identical pure publication helper may be
reused without changing earlier policies.

## Central Result and Projection Ownership

SessionRaceContextAnalysis-like domain output contains canonical participant
analyses, each with:

- normalized identity and final classification context;
- complete compact lap-context series;
- every pit evidence item;
- latest lap context selected centrally;
- counts for each pit state and total;
- source multiplicity/conflict information; and
- unassociated/unavailable evidence accounting.

services/race_context_service.py owns one private load-and-analyze operation:

1. validate the existing supported-session boundary before provider access;
2. call load_session once;
3. call map_race_context_inputs once and map_session_summary from the same
   snapshot;
4. call analyze_race_context once;
5. project either the full compact participant list or one driver detail; and
6. construct strict public models.

Projection preserves central-analysis collection order exactly and maps
existing domain values only. It does not count, choose latest
context, normalize, sort, pair, calculate, or round. The driver operation
returns driver_not_found only after the one complete analysis, preserving
authoritative field semantics.

## Public Model Design

models/race_context_models.py reuses existing AnalyticsSessionContext and
SourceProvenance where semantics match. It defines Feature 004 participant,
classification, lap context, track status, leader reference, pit boundary,
transition context, evidence-count, and response types.

Explicit state/value combinations include:

| laps_behind | Equal-distance status | Value |
|---:|---|---:|
| 0 | available | non-negative integer ms |
| greater than 0 | not_applicable | null |
| null/untrusted | unavailable | null |

Pit states are complete, unpaired_entry, unpaired_exit, conflicting, and
unavailable. complete requires one trusted entry, one later trusted exit, and a
non-negative elapsed result. Incomplete/conflicting/unavailable states publish
no elapsed result. Public descriptions use pit-lane entry-to-exit elapsed,
reported compound/stint, provider-exposed lap-completion position, and
equal-distance time deficit. They do not claim stationary service, confirmed
tire change, live gap, physical separation, or instantaneous pit position.

Direct construction rejects:

- noncanonical participant and lap ordering, and boundary/pit-evidence ordering
  contradictions provable from exposed public fields;
- duplicate TrackStatus values and availability/disruption contradictions;
- duplicate public participant and driver/lap identities;
- state/value contradictions;
- identity/reference mismatches;
- multiplicity/count reconciliation failures; and
- non-finite or coercible-but-wrong scalar types.

Validators do not sort, deduplicate, repair, derive, pair, or perform analytics.

Canonical domain order remains owned by central analytics using exact
nanoseconds and supported source-observation order. Public validation does not
reconstruct information lost during projection. Distinct published
milliseconds permit chronological checks; equal published milliseconds do not
imply equal exact timestamps and cannot justify descending into lap, kind, or
state tie-breaks. Usable chronology precedes absent chronology; when chronology
is genuinely absent, lower exposed keys may be checked only where the domain
policy makes the relation provable. Structural state rules remain enforceable.

TrackStatus validation checks enum validity, uniqueness, availability, and the
approved disruption truth table. It preserves the supplied sequence without
inventing enum order or claiming to verify original provider observation order
from an independent provenance sequence that the schema does not expose.
Public ambiguity cannot authorize reordering or rejection of an otherwise
valid canonical central projection. The current public schema is unchanged.

## API and Contract Design

Two additive GET resources are specified in contracts/openapi.yaml:

| Resource | Operation ID | Purpose |
|---|---|---|
| /api/v1/seasons/{year}/events/{event}/sessions/{session}/race-context | getSessionRaceContext | Exactly one compact entry per authoritative participant |
| /api/v1/seasons/{year}/events/{event}/sessions/{session}/race-context/drivers/{driver_number} | getDriverRaceContext | Complete compact lap series and all pit evidence for one participant |

The compact entry contains identity, classification context, latest lap
context, pit-state counts, and unavailable/unassociated accounting. It does not
embed complete lap or pit collections. Driver detail reuses the identical
compact entry and adds all lap and pit evidence. There is no pit-only v1
resource.

Existing path selector, 404 session_not_supported, 404 driver_not_found, 422
validation, sanitized 503 data_source_unavailable, and unexpected 500 behavior
remains. Existing routes and operation IDs are unchanged.

The responsibility-package migration is entirely internal and does not change
contracts/openapi.yaml. Exact pre/post generated OpenAPI equality is a migration
acceptance gate.

## Layered Test Strategy

### Provider normalization

Controlled FastF1/Pandas-shaped tests cover:

- all consumed public columns and authoritative results identities;
- NumPy scalar conversion and Python builtin output;
- NaT, NaN, infinity, malformed values, absent optional columns, and duplicate
  consumed labels;
- exact integer timestamp conversion without early rounding;
- position, generated, compound, and stint handling;
- TrackStatus single, mixed, repeated, unknown, missing, and malformed values;
- duplicate rows/results retained rather than overwritten; and
- no FastF1/Pandas/NumPy objects reaching immutable inputs.

### Pure analytics

Controlled immutable inputs cover:

- normal complete visit, multiple visits, no visit, pit-lane-start initial
  unpaired exit, retirement final unpaired entry;
- competing entries/exits, equal/reversed timestamps, duplicate boundaries,
  contradictory boundaries, unavailable timestamps, and exact evidence
  accounting;
- same compound/stint, changed reported values, and unavailable transition
  values;
- unique leader, equal timestamp, positive deficit, contradictory negative
  deficit, missing/duplicate leader, lapped driver, non-starter, and retirement
  after valid earlier context;
- generated rows retained but excluded from trusted derivatives;
- green, yellow, Safety Car, VSC, VSC ending, Red Flag, mixed, unknown, and
  missing status evidence;
- duplicate identical lap rows, contradictory lap rows, invalid identities,
  and unassociated evidence;
- half-up boundaries and proof differences use unrounded endpoints;
- incidental source-row permutations and at least three identical repetitions;
  and
- architecture checks forbidding provider/framework imports.

### Public models

Direct construction covers accepted canonical examples and rejects:

- noncanonical participant/lap order and publicly provable boundary/pit order
  violations;
- duplicate statuses and invalid status availability/disruption combinations;
- duplicate participant and driver/lap identities;
- contradictory availability/value and pit-state/field combinations;
- mismatched counts and references;
- NaN, infinity, booleans-as-integers, and coercible strings; and
- every attempted silent sort, deduplication, or repair.

Acceptance cases cover valid exact-domain order when distinct nanosecond
timestamps publish to the same millisecond, with no false lap/kind/state
tie-break, and supported TrackStatus permutations preserved without enum
sorting or reconstruction of lost source-observation provenance.

### Service and API

Mocks prove one load, one normalization, and one central analysis per operation.
Projection tests inject a known central result and prove session and driver
views reuse it without recomputation. API tests cover compact/full shapes,
known participants with unavailable evidence, unknown participant behavior,
malformed selectors, unsupported session, 503 expected failures, unexpected
500 behavior, provenance, and standards-safe JSON.

### OpenAPI, regression, and real source

OpenAPI tests verify exact additive paths, operation IDs, required/nullable
fields, enums, integer-millisecond units, constraints, and preservation of
every existing path/schema. All Feature 001–003 assertions remain unchanged
apart from the import/module paths required by the migration.

Before any Feature 004 assertions are added, the migration group separately
verifies that importing app.main and every moved module succeeds, the entire
existing suite passes with only import/module-path updates, generated OpenAPI is
identical to the pre-migration baseline, the FastF1 cache path is unchanged,
and the dependency/lock files have no diff. A fresh independent review then
approves or rejects the structural group.

Separately opted-in integration uses the 2025 Italian Grand Prix Race to verify
public-provider compatibility, one-snapshot analysis, authoritative participant
accounting, normal and incomplete pit evidence, deterministic ordering,
provenance, and finite JSON. Synthetic fixtures cover edge cases absent from
Monza. Tests do not freeze incidental driver results or visit counts as general
policy.

## Dependency Decision

No dependency is added. Existing Python and project packages are sufficient.
The design needs immutable values, grouping, sorting, state transitions, exact
integer arithmetic, strict validation, and HTTP transport; all are already
available. Adding an interval, graph, dataframe, or domain-model package would
increase maintenance and supply-chain surface without a missing capability.

## Feature 001–003 Compatibility

- Move SourceLap and SessionFieldInput with their module without modifying
  them, Feature 002 classification, the
  120% anomaly rule, rankings, or tie behavior.
- Move Feature 003 modules without modifying construction, exclusions,
  availability, compound/age policy, estimator, public models, or services.
- Do not alter existing routes, operation IDs, schemas, supported-session
  checks, or error bodies.
- Keep the existing session loader flags unchanged.
- Add a separate Feature 004 mapper and one new module in each responsibility
  package.
- Keep existing test locations and assertions; update only imports,
  module-string checks, and patch targets required by the moves.
- Require the full existing suite and an independent migration review before
  Feature 004-specific work.
- Keep all OpenAPI additions backward compatible and verify prior paths
  structurally.

## Design Risks and Controls

| Risk | Control |
|---|---|
| FastF1 public laps are processed and can change on upgrade | Pin existing version; isolate adapter; normalization and opted-in integration tests |
| Provider-generated retirement time may be assumed | Preserve generated evidence but withhold it from trusted completion/leader/pit derivation |
| Duplicate evidence could be overwritten by convenient mappings | Preserve row occurrences; consolidate with count/conflict; permutation tests |
| Position could be mistaken for live or physical position | Provider-exposed lap-completion naming and contract descriptions |
| Session Time could be mistaken for race-elapsed zero | Keep explicit session_time_ms names and never rebase |
| Separate views could drift | One central analysis with injected-result projection tests |
| Strict validators could become hidden analytics | Limit them to rejection and reconciliation; analytics tests own calculation policies |
| Package migration could hide a behavioral regression | Isolate it as the first bounded group; allow only moves/imports/package markers/cache-path preservation; require full regression, OpenAPI equality, and independent review |
| Moving f1_data.py could redirect the cache | Adjust the path-depth expression only and assert the resolved path remains backend/cache/fastf1 |
| Package __init__ re-exports could create cycles | Keep package initializers empty/declaration-only and use explicit module imports |

No unresolved implementation-level ambiguity remains. Provider changes
discovered during implementation must be recorded as research amendments rather
than answered by silent repair.

## Complexity Tracking

No constitution violations or complexity exceptions are present.
