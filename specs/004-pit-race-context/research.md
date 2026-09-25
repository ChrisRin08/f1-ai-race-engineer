# Research: Pit-Lane Visits & Lap-Boundary Race Context

## Scope and source basis

This research resolves implementation-level questions for Feature 004 without
changing its approved product policy. Provider observations below were verified
against FastF1 3.8.3's supported public Session, Session.laps, and
Session.results behavior in the
[official FastF1 3.8.3 source](https://github.com/theOehrly/Fast-F1/blob/v3.8.3/fastf1/core.py)
and [public core API documentation](https://docs.fastf1.dev/en/stable/core.html).
Feature 004 does not use fastf1._api, timing-stream internals, telemetry, or
cache internals.

## Decision 1: Migrate to responsibility-based application packages first

**Decision**: Before any Feature 004 behavior is implemented, move the existing
backend/app modules into four shallow responsibility packages: data, analytics,
models, and services. Keep main.py as the root transport/composition entry
point. Add Feature 004 modules directly to the matching packages. Do not create
feature-number directories, compatibility wrappers, generic repositories,
factories, interfaces, or deeper nesting.

**Why grouping is now justified**: The current application has eight
substantive root modules across four responsibilities. Feature 004 adds one
analytics module, one public-model module, and one service module, bringing the
root toward eleven substantive modules; Feature 005 is explicitly expected to
reuse the central analytics result. The existing models.py name also blocks a
clean models package. At this trajectory, responsibility grouping improves
discoverability and makes dependency direction visible before another domain is
added. The owner has approved the bounded migration cost.

### Exact existing-module moves

| Current path | Planned path | Responsibility |
|---|---|---|
| backend/app/f1_data.py | backend/app/data/f1_data.py | FastF1/Pandas acquisition and normalization |
| backend/app/lap_analytics.py | backend/app/analytics/lap_analytics.py | Pure Feature 002/shared lap analytics |
| backend/app/stint_analytics.py | backend/app/analytics/stint_analytics.py | Pure Feature 003 analytics |
| backend/app/models.py | backend/app/models/session_models.py | Shared/Feature 001 public session contracts |
| backend/app/pace_models.py | backend/app/models/pace_models.py | Feature 002 public contracts |
| backend/app/stint_models.py | backend/app/models/stint_models.py | Feature 003 public contracts |
| backend/app/pace_service.py | backend/app/services/pace_service.py | Feature 002 orchestration/projection |
| backend/app/stint_service.py | backend/app/services/stint_service.py | Feature 003 orchestration/projection |

Add empty or declaration-only __init__.py files under data, analytics, models,
and services. Leave backend/app/__init__.py and backend/app/main.py in place.
Do not re-export moved symbols through package __init__.py files: explicit
module imports keep ownership and dependency direction visible and avoid import
side effects.

### Feature 004 destinations

- backend/app/analytics/race_context_analytics.py
- backend/app/models/race_context_models.py
- backend/app/services/race_context_service.py

Feature 004 provider normalization extends backend/app/data/f1_data.py; it does
not add a second provider module.

### Import and path effects

Application imports change mechanically:

- app.f1_data becomes app.data.f1_data;
- app.lap_analytics and app.stint_analytics become app.analytics equivalents;
- app.models becomes app.models.session_models;
- app.pace_models and app.stint_models become app.models equivalents; and
- app.pace_service and app.stint_service become app.services equivalents.

main.py imports the new data, model, and service paths but remains the Uvicorn
entry point app.main:app. Tests remain in the existing flat backend/tests
directory; only imports, module-string assertions, and monkeypatch targets that
name moved modules change.

Moving f1_data.py one directory deeper changes the meaning of
Path(__file__).resolve().parents[1]. The migration must adjust only that
path-relative constant so FASTF1_CACHE_DIR continues to resolve to
backend/cache/fastf1, then verify it explicitly. That is required preservation,
not a cache-policy change.

### Dependency direction and circular-import control

The observed dependency graph becomes:

    analytics.lap_analytics
      <- analytics.stint_analytics
      <- models.stint_models

    models.session_models
      <- data.f1_data
      <- services
      <- main

    analytics modules + models.session_models
      <- models.pace_models / models.stint_models
      <- services
      <- main

data.f1_data continues to import immutable input types from
analytics.lap_analytics and session response models from
models.session_models, preserving existing behavior. Analytics never imports
data, services, transport, or Pydantic models. Models never import data or
services. Services may import data, analytics, and models. main.py imports data,
models, and services. Package __init__.py files stay empty, so importing a
package cannot recursively import a service or transport module.

The existing stint service reuses DriverNotFoundError from the pace service;
after the move it imports app.services.pace_service explicitly. Extracting that
error into a speculative shared module is outside this migration because the
current dependency is acyclic and behaviorally established.

### Why this is behavior-preserving and preliminary

The migration changes module locations, import paths, four package markers, and
the path-depth expression needed to keep the existing cache location. It does
not alter algorithms, constants, public models, field names, route paths,
operation IDs, response schemas, policies, exception semantics, loader flags,
or dependency versions. No unrelated cleanup is combined with it.

It runs before Feature 004 so a pure structural change can be reviewed and
verified independently. Mixing moves with new provider facts, analytics, and
routes would make regressions harder to attribute and would weaken review.

Independent migration acceptance requires:

1. an import smoke test for app.main plus every moved module;
2. the entire Feature 001–003 test suite passing offline with only required
   import/module-path edits and unchanged behavioral assertions;
3. Ruff format and lint passing;
4. generated OpenAPI equality before and after the migration;
5. route/operation-ID and response-schema equality;
6. explicit confirmation that FASTF1_CACHE_DIR remains backend/cache/fastf1;
7. no dependency or lockfile diff;
8. a diff audit proving changes are moves, import rewrites, package markers, and
   the required cache-path depth adjustment only; and
9. a fresh independent review approval before Feature 004 behavior begins.

**Alternatives considered**:

- Retain the flat layout: superseded by the owner-approved decision because the
  fourth analytical domain and Feature 005 reuse now justify visible
  responsibility boundaries.
- Create feature-number packages: rejected because permanent ownership is by
  responsibility, not delivery order.
- Add a shared domain, repository, interface, or factory layer: rejected because
  current imports remain acyclic without speculative abstraction.
- Move tests into mirrored subpackages: rejected because import-only changes are
  sufficient and moving tests would add unrelated review noise.

## Decision 2: Introduce a Feature 004 normalized input

**Decision**: Add an immutable RaceContextInput-like domain input rather than
extending the pace-oriented SourceLap. data/f1_data.py maps one already loaded
session into authoritative participants and normalized lap-row evidence.

**Rationale**: SourceLap intentionally contains lap duration and pit booleans.
Feature 004 needs exact completion and pit-boundary timestamps, lap-completion
position, value-quality states, track-status semantics, source multiplicity,
generated state, compound, stint, and results/classification context. Extending
SourceLap would expose unrelated semantics to Features 002 and 003 and would
still lose absent-versus-invalid pit evidence.

The mapper preserves every source row and source occurrence for evidence
accounting. Source order may be retained for diagnostics but never selects a
winner, establishes chronology, or resolves a tie. Pandas, NumPy, NaT, NaN,
infinity, duplicate-column behavior, and provider scalar conversion remain
inside data/f1_data.py.

## Decision 3: Treat public FastF1 laps as processed provider facts

**Provider behavior**:

- LapNumber identifies the driver's completed-lap count represented by a row.
- Time is a session-relative timestamp at lap completion. It is not rebased to
  the race start by this feature.
- Position is generated by FastF1 for race-like sessions by ordering completion
  Time within the same LapNumber. It is provider-exposed lap-completion race
  position, not official final classification, live timing, GPS, physical
  coordinates, or pit-boundary position.
- PitInTime and PitOutTime identify pit-lane entry on the in-lap row and
  pit-lane exit on the out-lap row.
- FastF1Generated marks provider-created lap evidence. FastF1 can append a
  retirement row with an assumed timestamp.
- Session.results contains the authoritative participant roster, including a
  participant who has no lap rows, and separate final classification facts.

**Project policy**:

- Normalize LapNumber and Position only from finite positive integral,
  non-boolean values.
- Normalize timestamp-like values to exact non-negative integer nanoseconds in
  the provider session-time coordinate. Retain explicit absent or invalid state
  where that distinction affects evidence.
- Accept Position == 1 as leader evidence only when the consolidated lap item
  is uniquely trustworthy. Do not recreate a missing leader by selecting the
  minimum Time.
- Retain generated rows in audit evidence but do not use generated completion
  timestamps to establish a trusted lap completion, leader, time deficit,
  laps-behind state, or pit visit.
- IsAccurate is not an exclusion rule for Feature 004. FastF1 can mark required
  pit, neutralized, red-flag, and generated evidence inaccurate; using it as a
  blanket filter would erase evidence the specification requires.

## Decision 4: Normalize track status at the provider boundary

**Provider behavior**: FastF1 TrackStatus is an ordered concatenation of unique
single-digit status codes whose intervals overlap the lap. It is lap context,
not necessarily the single status at the instant of completion. Supported
public codes used here are 1 clear, 2 yellow, 4 Safety Car, 5 Red Flag, 6
Virtual Safety Car, and 7 VSC ending.

**Decision**: data/f1_data.py converts provider codes to the ordered,
de-duplicated domain values green, yellow, safety_car, red_flag,
virtual_safety_car,
virtual_safety_car_ending, and unknown. Unknown codes remain unknown. Empty,
missing, or malformed status evidence is unavailable.

is_disrupted follows the approved truth table:

- true if any known disrupted value is present, even if unknown also appears;
- false only if trustworthy status evidence contains no disrupted or unknown
  value;
- null if status evidence is missing, malformed, or contains unknown without a
  known disrupted value.

No downstream layer parses provider status codes, and unknown never means green.

## Decision 5: Consolidate duplicate lap evidence without losing multiplicity

**Decision**: Pure analytics consolidates rows by authoritative driver and valid
LapNumber into exactly one compact logical lap item. Exact normalized repeats
produce one item with source_evidence_count greater than one. Incompatible
values or competing present-versus-absent claims produce explicit conflict on
the affected fact and make dependent derivations unavailable.

Rows that cannot be associated with a valid driver/lap identity remain
participant-level unavailable evidence accounting; they do not create a second
public driver/lap identity. Duplicate result rows consolidate by driver number
with multiplicity/conflict rather than producing duplicate participants. An
unusable participant identity is a provider-unavailable operation because it
cannot be attached to the authoritative roster.

**Alternatives considered**:

- Dictionary overwrite or first/last row wins: rejected because it silently
  discards source evidence and depends on incidental row order.
- Publishing duplicate driver/lap items: rejected by the public identity
  invariant.
- Inventing a synthetic row identity: rejected because the provider supplies no
  such domain identity.

## Decision 6: Identify the lap leader from unique provider position evidence

**Decision**: For completed lap n, the reference observation is the unique
trustworthy consolidated observation with provider-exposed Position == 1 at
LapNumber n. Missing or multiple/contradictory leader evidence makes dependent
equal-distance results unavailable.

For a trustworthy driver completion at lap n:

- find the unique leader observation for the same n;
- calculate exact driver completion nanoseconds minus leader completion
  nanoseconds;
- publish zero or a positive result;
- treat a negative result as unavailable.

This is equal-distance lap-boundary separation. It is never described as live,
current, instantaneous, physical, telemetry, or GPS separation.

## Decision 7: Evaluate laps behind at the selected completion timestamp

**Decision**: At a trustworthy selected-driver completion time t for lap n,
select the greatest completed lap L among trustworthy leader observations whose
completion Time is less than or equal to t. laps_behind is L - n.

- L == n permits an available same-lap time deficit when its evidence is also
  trustworthy.
- L > n requires equal_distance_time_deficit_status = not_applicable and a null
  time value.
- Missing, ambiguous, negative, or otherwise contradictory evidence yields
  unavailable, never a clamped or predicted value.

No interpolation predicts when a lapped driver would complete the leader's
current lap. An exact equal timestamp is included by the less-than-or-equal
boundary.

## Decision 8: Pair pit boundaries with a conservative chronological state machine

**Decision**: Create logical boundary candidates from normalized PitInTime and
PitOutTime facts, then process each participant independently:

1. Coalesce exact duplicate candidate evidence while retaining occurrence
   count. Differing claims for the same logical boundary are conflicting.
2. Order usable candidates by session timestamp and then lap identity. Equal
   timestamps or timestamp/lap contradictions are ambiguous and are not
   tie-broken by source row order.
3. An exit with no open entry becomes unpaired_exit.
4. One entry followed by the next single trustworthy exit becomes complete only
   when exit time is strictly later, lap identity is nondecreasing when both
   sides exist, and no competing boundary intervenes.
5. An open entry at the end becomes unpaired_entry.
6. Entry-before-entry, competing candidates, equal or reversed times, or any
   otherwise non-unique association becomes one conflicting group that accounts
   for each involved occurrence exactly once.
7. An asserted but unusable boundary becomes unavailable and is never paired.

Do not require the exit lap to equal entry lap plus one; the public provider can
associate pit-out evidence with the current or next logical lap. Temporal
ordering and unambiguous alternation are the defensible invariants. Do not pair
rows merely because they are adjacent and never manufacture a boundary.

The entry context is exactly the consolidated row carrying PitInTime. The exit
context is exactly the consolidated row carrying PitOutTime. Missing or
conflicting context stays unavailable; there is no nearby-racing-lap fallback.

## Decision 9: Keep generated evidence auditable but analytically untrusted

**Decision**: A provider-generated row is retained with its flag, multiplicity,
track status, reported compound/stint, and any normalized source facts. Its
completion and boundary timestamps do not establish a trusted completion,
leader, lap deficit, or pit association.

**Rationale**: FastF1 may synthesize a final retirement row and, when telemetry
is disabled, may use an assumed time. Publishing that timestamp as observed race
separation would overstate source evidence. The row remains visible so its
effect and unavailability are auditable.

## Decision 10: Calculate exactly, then publish half-up milliseconds once

**Decision**: Preserve exact integer nanoseconds through normalization and all
subtraction. Publish session timestamps, entry-to-exit elapsed, and
equal-distance time deficit as integer milliseconds using deterministic half-up
rounding after calculation.

For the non-negative quantities in Feature 004:

    published_ms = (exact_ns + 500_000) // 1_000_000

Never subtract independently rounded endpoints; doing so can change a result by
one millisecond. The existing pure publication helper has the same semantics
and may be reused without changing Feature 002 or 003 policy.

## Decision 11: Derive one central analysis and project it twice

**Decision**: analytics/race_context_analytics.py owns one immutable central
analysis per normalized session. It contains each participant's compact lap
series, all pit evidence, latest trusted/available summary context, pit-state
counts, conflict accounting, and final-classification context. The session and
driver resources are projections of this result.

The service may select a participant and map domain values to public models. It
does not identify leaders, calculate deficits, pair visits, count evidence,
select latest context, round time, or re-normalize provider data. Future Feature
005 consumes the central domain result, not Pydantic response models.

## Decision 12: Use two additive resources and no pit-only resource

**Decision**:

- GET /api/v1/seasons/{year}/events/{event}/sessions/{session}/race-context
  with operationId getSessionRaceContext.
- GET
  /api/v1/seasons/{year}/events/{event}/sessions/{session}/race-context/drivers/{driver_number}
  with operationId getDriverRaceContext.

The session resource contains exactly one compact entry per authoritative
participant in numeric driver-number order and does not duplicate full lap or
pit collections. Driver detail contains the same compact participant summary,
the complete compact normalized lap-context series, all pit evidence, and
unassociated/unavailable evidence accounting. There is no separate pit-only
resource in v1.

Existing selector validation and error semantics remain: malformed selectors
422, unsupported session 404 before provider loading, unknown canonical driver
404 after one analysis, expected provider/schema failure 503, and unexpected
defect 500.

## Decision 13: Enforce strict construction without performing analytics

**Decision**: Public models reject noncanonical participant, lap, status, pit,
and boundary ordering; duplicate public identities; invalid enum/value
combinations; count mismatches; and contradictory state/field combinations.
They do not sort, deduplicate, pair, calculate, infer, or repair.

Representative invariants:

- available equal-distance status requires laps_behind == 0 and a non-negative
  integer value;
- not_applicable requires laps_behind > 0 and a null value;
- unavailable requires a null value;
- complete pit evidence requires exactly one entry and one later exit plus a
  non-negative elapsed value;
- unpaired states contain exactly the named boundary and no elapsed value;
- conflicting and unavailable items expose their evidence/multiplicity and no
  falsely trusted elapsed result.

## Dependency decision

No new direct dependency is required. Python dataclasses, enums, tuples,
collections, and integer arithmetic cover normalization and pure analytics.
FastAPI, Pydantic, FastF1, Pandas, NumPy, pytest, and Ruff already exist for
their current responsibilities. A graph, interval, dataframe, or validation
package would add maintenance cost without solving a missing capability.

## Controlled-source observation and test implications

The cached 2025 Italian Grand Prix Race snapshot contains 20 results
participants and 974 lap rows. One authoritative participant has no lap row.
Observed pit evidence includes ordinary completed visits, initial unpaired
exits, and a final unpaired entry. TrackStatus includes mixed ordered codes such
as 12 and 21. No duplicate driver/lap evidence was observed, so duplicate,
conflicting, malformed, neutralized, and ambiguous cases require controlled
fixtures.

These observations guide acceptance coverage; none becomes a general business
rule or a fixed expected race result.

## Risks retained for implementation verification

- FastF1 laps are processed provider output and may change on provider upgrade;
  pinning plus adapter and opt-in integration tests protect the boundary.
- Position is provider-derived, so a missing or conflicting value cannot be
  replaced with a second project-owned timing-order algorithm.
- Session Time is not race-elapsed zero; field names and documentation must
  preserve session-time meaning.
- Generated timestamps may be assumed; generated evidence must not leak into
  trusted derivatives.
- Duplicate and invalid provider values need targeted fixtures because Monza
  does not exhibit every required state.

No approved product-policy question remains open.
