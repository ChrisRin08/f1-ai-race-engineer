# Data Model: Pit-Lane Visits & Lap-Boundary Race Context

## Layer boundaries

Feature 004 deliberately uses three different model layers:

1. normalized provider/application inputs preserve supported source facts and
   quality without FastF1, Pandas, or NumPy types;
2. central analytical/domain results consolidate evidence and derive race
   context exactly once;
3. strict public projection models expose compact session and auditable driver
   views without provider objects or view-specific recalculation.

The layers are not aliases of each other. Provider inputs are not public
models, and Pydantic response models are not the reusable analytical domain.

## 1. Normalized provider/application input facts

All inputs are immutable dataclass-like values produced by
data/f1_data.py from one loaded public FastF1 Session snapshot.

### Normalized value state

For facts where absence differs from malformed evidence:

| State | Meaning |
|---|---|
| available | A supported provider value normalized to the required builtin type |
| absent | The provider did not assert this optional fact |
| invalid | A present value was malformed, non-finite, out of domain, or ambiguous |

The value is populated only for available. This state is required for pit
timestamps, completion timestamps, lap number, and position where silent
conversion to null would erase evidence meaning. It is a small Feature 004
value object, not a generic repository or public transport abstraction.

### RaceContextParticipantInput

One consolidated authoritative results participant:

| Field | Type | Meaning |
|---|---|---|
| identity | immutable participant identity | Driver number plus optional abbreviation, full name, and team |
| result_evidence_count | positive integer | Number of provider result rows consolidated |
| result_evidence_status | available, conflicting, unavailable | Quality of the authoritative result identity/classification |
| finish_position | positive integer or null | Final results position when usable |
| classified_position | string or null | Provider classification value/code when usable |
| classification_status | string or null | Provider result status when usable |
| completed_laps | non-negative integer or null | Provider results completed-lap count when usable |

The results roster is authoritative. A lap row never creates a participant.
Duplicate results rows retain multiplicity and conflict meaning. A participant
without lap rows remains in the input.

### NormalizedTrackStatusEvidence

| Field | Type | Meaning |
|---|---|---|
| availability | available or unavailable | Whether the provider status string could be interpreted |
| statuses | ordered unique tuple | green, yellow, safety_car, virtual_safety_car, virtual_safety_car_ending, red_flag, or unknown |
| is_disrupted | boolean or null | Approved three-state disruption interpretation |

The provider adapter preserves first-observed code order while de-duplicating
within one row. Unknown is retained. Analytics never receives raw provider
codes.

### RaceContextLapRowInput

One preserved provider lap-row occurrence:

| Field | Type | Meaning |
|---|---|---|
| source_occurrence | positive integer | Diagnostic occurrence identity; never a semantic tie-break |
| driver_number | string or null | Normalized row association key |
| lap_number | normalized value state plus positive integer/null | Completed-lap identity |
| lap_completion_time_ns | normalized value state plus non-negative integer/null | Exact provider session Time |
| lap_completion_position | normalized value state plus positive integer/null | Provider-exposed lap-completion position |
| pit_entry_time_ns | normalized value state plus non-negative integer/null | Exact PitInTime evidence |
| pit_exit_time_ns | normalized value state plus non-negative integer/null | Exact PitOutTime evidence |
| track_status | NormalizedTrackStatusEvidence | Normalized lap-overlap statuses |
| provider_generated | boolean or null | Provider assertion, preserved without defaulting |
| reported_compound | non-empty trimmed string or null | Provider-reported compound |
| reported_stint | positive integer or null | Provider-reported stint |

Exact integer nanoseconds are the calculation coordinate. Missing and invalid
values are never NaN, infinity, magic numbers, or empty strings.

### RaceContextInput

| Field | Type | Meaning |
|---|---|---|
| participants | ordered tuple of RaceContextParticipantInput | Authoritative complete roster |
| lap_rows | tuple of RaceContextLapRowInput | Every normalized provider row occurrence |
| unassociated_row_count | non-negative integer | Rows that cannot attach to an authoritative participant |

Input order does not control analytical results. The authoritative identity and
normalized facts establish grouping and canonical order.

## 2. Central analytical/domain results

analytics/race_context_analytics.py derives these immutable values with no
FastF1, Pandas, FastAPI, Pydantic, cache, or network dependency.

### EvidenceStatus

| Value | Meaning |
|---|---|
| available | One source-backed interpretation is justified |
| conflicting | Competing normalized claims prevent one interpretation |
| unavailable | Required usable source evidence is absent or invalid |

Exact duplicate observations may remain available while exposing
source_evidence_count greater than one. Contradictory duplicates are
conflicting and suppress affected derivatives.

### ConsolidatedLapContext

Exactly one logical item per authoritative driver and positive lap number:

| Field | Type | Meaning |
|---|---|---|
| driver_number | string | Public identity component |
| lap_number | positive integer | Public identity component |
| evidence_status | EvidenceStatus | Overall source-evidence quality |
| source_evidence_count | positive integer | Multiplicity represented by this item |
| completion_time_ns / completion_time_ms | integer or null | Exact and once-published lap-completion session time |
| completion_position | positive integer or null | Provider-exposed completion position |
| track_status | normalized status evidence | Ordered status context and disruption meaning |
| provider_generated | boolean or null | Preserved provider assertion |
| reported_compound | string or null | Source context; no change confirmation |
| reported_stint | positive integer or null | Source context |
| leader_reference | LeaderReference or null | Leader state used at this selected completion |
| laps_behind_status | available or unavailable | Explicit availability of lap deficit |
| laps_behind | non-negative integer or null | Leader completed laps minus selected completed laps |
| equal_distance_time_deficit_status | available, not_applicable, unavailable | Meaning of optional time metric |
| equal_distance_time_deficit_ns / ms | non-negative integer or null | Exact and once-published same-distance deficit |

Generated rows remain represented but do not provide trusted completion,
leader, lap-deficit, time-deficit, or pit facts. Conflicts may affect individual
facts without erasing other source-backed fields; evidence_status and
multiplicity explain the item.

### LeaderReference

| Field | Type | Meaning |
|---|---|---|
| driver_number | string | Participant with unique trusted completion position 1 |
| lap_number | positive integer | Latest trusted leader lap at or before the selected completion |
| completion_time_ns / completion_time_ms | non-negative integer | Reference completion session time |

When equal-distance status is available, the reference lap equals the selected
lap. When laps_behind is positive, it identifies the later leader lap used for
the lap deficit while equal-distance time is not applicable.

### PitBoundary

One compact logical boundary candidate:

| Field | Type | Meaning |
|---|---|---|
| kind | entry or exit | Boundary meaning |
| evidence_status | EvidenceStatus | Trust/conflict state |
| source_evidence_count | positive integer | Duplicate multiplicity |
| lap_number | positive integer or null | In-lap or out-lap identity |
| session_time_ns / session_time_ms | non-negative integer or null | Exact and published provider session time |
| lap_context_reference | driver/lap reference or null | Exact same-row lap context, never a nearby fallback |

### PitTransitionContext

Source-backed context from exactly the boundary row:

| Field | Type | Meaning |
|---|---|---|
| availability | available, conflicting, unavailable | Context quality |
| lap_context_reference | driver/lap reference or null | Link to the driver's compact lap series |
| reported_compound | string or null | Reported source value |
| reported_stint | positive integer or null | Reported source value |

This is lap-completion context associated with pit evidence, not instantaneous
state at the pit timestamp.

### PitLaneEvidence

One canonical evidence item:

| Field | Type | Meaning |
|---|---|---|
| state | complete, unpaired_entry, unpaired_exit, conflicting, unavailable | Explicit public meaning |
| boundaries | canonical tuple of PitBoundary | Every boundary occurrence represented once through item plus multiplicity |
| source_boundary_count | positive integer | Sum of boundary multiplicities |
| entry_lap_number / exit_lap_number | positive integer or null | Trusted boundary lap identities |
| entry_session_time_ns / ms | non-negative integer or null | Trusted entry time |
| exit_session_time_ns / ms | non-negative integer or null | Trusted exit time |
| entry_to_exit_elapsed_ns / ms | non-negative integer or null | Exit minus entry at source precision, published once |
| entry_context / exit_context | PitTransitionContext or null | Exact in-lap/out-lap source context |
| reported_compound_changed | boolean or null | Difference between two usable reported values only |
| reported_stint_changed | boolean or null | Difference between two usable reported values only |

The changed flags describe reported values only and never confirm a physical
tire change. A complete item has one trusted entry and one later trusted exit.
Unpaired states have exactly the named trusted boundary. Conflicting and
unavailable states retain candidates and multiplicity but publish no trusted
elapsed result.

### ParticipantRaceContextAnalysis

| Field | Type | Meaning |
|---|---|---|
| identity | immutable participant identity | Authoritative participant |
| classification | normalized classification result | Source-backed final race context |
| latest_lap_context | ConsolidatedLapContext or null | Central compact selection for session projection |
| pit_evidence_counts | fixed state-count object | Counts for all five pit states and total |
| lap_contexts | canonical tuple | Complete compact normalized lap series |
| pit_evidence | canonical tuple | All evidence items |
| unassociated_evidence_count | non-negative integer | Participant rows that cannot form a public driver/lap identity |

Selection of latest_lap_context and all counts occurs in pure analytics. A
service does not calculate them.

### SessionRaceContextAnalysis

One ParticipantRaceContextAnalysis per authoritative participant, canonically
ordered. It is the sole central Feature 004 result. Both public resources and
future Feature 005 consume this result rather than rerunning leader or pit
logic.

## Central transformations

The pure analysis coordinator performs four cohesive transformations:

1. consolidate result and lap evidence, retaining multiplicity/conflicts;
2. establish trusted lap leaders and derive each lap-boundary race context;
3. build, order, and associate pit-boundary evidence;
4. assemble participant summaries and the canonical session analysis.

Private pure functions may implement those transformations. Do not create
generic factories, repositories, provider interfaces, or one-class-per-step
wrappers.

## Race-context state transitions

For each selected trustworthy completion at lap n and time t:

    leader_latest = max trusted leader lap whose completion time <= t
    laps_behind = leader_latest.lap_number - n

Then:

| Condition | laps_behind status/value | Equal-distance status/value |
|---|---|---|
| Leader/latest evidence unavailable or contradictory | unavailable/null | unavailable/null |
| Difference is negative | unavailable/null | unavailable/null |
| Difference is positive | available/positive | not_applicable/null |
| Difference is zero and unique same-lap timestamps are trusted | available/0 | available/non-negative integer ms |
| Difference is zero but same-lap time evidence is unusable | available/0 | unavailable/null |

A negative driver-minus-leader exact time is unavailable. Zero is a valid
available equal-distance result. No interpolation or prediction occurs.

## Pit association state transitions

Usable candidates are processed per driver in chronological order:

    no open entry + exit       -> unpaired_exit
    no open entry + entry      -> hold open
    open entry + unique exit   -> complete
    open entry + end of stream -> unpaired_entry
    competing/equal/reversed   -> conflicting group
    asserted unusable boundary -> unavailable

Every source occurrence contributes exactly once through a boundary
source_evidence_count. Exact duplicates consolidate; contradictory candidates
do not create multiple public identities. Pairing never uses source-row
adjacency or a manufactured boundary.

## Canonical domain ordering

- Participants: numeric driver number ascending; identities without a usable
  numeric number follow in normalized authoritative-identity order.
- Lap contexts: lap number ascending, exactly one item per driver/lap.
- Statuses: first supported provider observation order after de-duplication.
- Boundaries within evidence: usable timestamp, usable lap, then entry before
  exit; unavailable values last. Equal/contradictory evidence remains a
  conflict rather than using this order to claim causality.
- Pit evidence: earliest usable boundary time, then earliest usable boundary
  lap, then complete, unpaired_entry, unpaired_exit, conflicting, unavailable;
  items without usable chronology last.

Canonical order depends only on normalized facts, never Pandas row position.

## 3. Strict public projection models

All public models live in models/race_context_models.py, forbid extra fields,
and use strict finite builtin values. Nullable fields remain required so
omission cannot obscure unavailable state. Validators enforce shape, identity,
ordering, reconciliation, and state/field invariants only. They never perform
normalization, leader selection, deficit calculation, visit pairing, rounding,
sorting, deduplication, or repair.

### Shared public value models

#### RaceContextParticipantIdentity

driver_number is a non-empty source identity. Optional abbreviation, full name,
and team name follow existing semantics. A dedicated type is used because
FR-055 defines deterministic handling for a non-numeric authoritative identity;
the stricter Feature 002 driver-number type remains unchanged.

#### RaceClassificationContext

Contains evidence_status, source_evidence_count, finish_position,
classified_position, status, and completed_laps. Missing classification facts
remain explicit rather than inferred from lap rows.

#### TrackStatusContext

Contains availability, ordered unique track_statuses, and nullable
is_disrupted. It enforces the approved truth table without deriving it.

#### LeaderReference

Contains driver_number, lap_number, and
lap_completion_session_time_ms. Its field names make the reference boundary
auditable.

#### LapCompletionContext

Public form of ConsolidatedLapContext:

- driver_number and lap_number;
- evidence_status and source_evidence_count;
- lap_completion_session_time_ms;
- lap_completion_position;
- track_status context;
- provider_generated;
- reported_compound and reported_stint;
- leader_reference;
- laps_behind_status and laps_behind;
- equal_distance_time_deficit_status and
  equal_distance_time_deficit_ms.

The descriptions identify equal-distance direction as selected driver minus lap
leader at the same completed lap. No field uses live-gap terminology.

#### PitBoundaryEvidence

Contains kind, evidence_status, source_evidence_count, lap_number,
entry_session_time_ms or exit_session_time_ms as appropriate, and an optional
same-row lap-context reference. The wrong timestamp field for the kind is
rejected.

#### PitTransitionContext

Contains availability, lap-context reference, reported_compound, and
reported_stint. It explicitly describes in-lap/out-lap completion context, not
instantaneous pit-boundary state.

#### PitLaneEvidence

Contains state, boundaries, source_boundary_count, entry and exit lap/time
fields, entry_to_exit_elapsed_ms, entry and exit contexts, and nullable
reported-value changed flags. The model rejects state/field contradictions and
noncanonical boundary order without repairing them.

#### PitEvidenceCounts

Contains total plus one non-negative count for complete, unpaired_entry,
unpaired_exit, conflicting, and unavailable. The five state counts must sum to
total.

### SessionRaceContextParticipant

| Field | Type |
|---|---|
| driver | RaceContextParticipantIdentity |
| classification | RaceClassificationContext |
| latest_lap_context | LapCompletionContext or null |
| pit_evidence_counts | PitEvidenceCounts |
| unassociated_evidence_count | non-negative integer |

This is compact: it contains no lap_contexts or pit_evidence collection. A no-
visit participant has zero pit counts rather than an invented event.

### SessionRaceContextResponse

| Field | Type |
|---|---|
| context | existing AnalyticsSessionContext |
| participants | canonical list of SessionRaceContextParticipant |
| source | existing SourceProvenance |

It requires exactly one entry for every participant present in the supplied
central projection, rejects duplicate identities, and rejects noncanonical
participant order.

### DriverRaceContextResponse

| Field | Type |
|---|---|
| context | existing AnalyticsSessionContext |
| participant | SessionRaceContextParticipant |
| lap_contexts | complete canonical list of LapCompletionContext |
| pit_evidence | complete canonical list of PitLaneEvidence |
| source | existing SourceProvenance |

All lap items must match the participant identity, have unique driver/lap
identities, and already be ordered by ascending lap number. Pit evidence counts
must reconcile with participant summary counts. The same
SessionRaceContextParticipant value is used by both projections.

## Direct-construction invariants

The strict public boundary rejects:

- noncanonical participant, lap, status, boundary, or pit-evidence order;
- duplicate participant or driver/lap public identities;
- source_evidence_count or state-count inconsistencies;
- available values without the required evidence and null values that
  contradict available state;
- not_applicable equal-distance state unless laps_behind is positive;
- a value under unavailable or not_applicable status;
- complete visits without exactly one trusted entry and one trusted later exit;
- elapsed values on incomplete, conflicting, or unavailable evidence;
- changed flags when either reported before/after value is unavailable;
- mismatched driver/lap references;
- generated rows that claim trusted derived leader/deficit facts; and
- any silent sort, deduplication, pairing, calculation, or repair.

These are validation rules, not analytics.

## Public error boundary

Feature 004 reuses the established error model:

| Condition | Status | Code |
|---|---:|---|
| Malformed path selector | 422 | Framework validation response |
| Unsupported session tuple | 404 | session_not_supported |
| Canonical driver absent after one central analysis | 404 | driver_not_found |
| Expected provider/schema/normalization failure | 503 | data_source_unavailable |
| Unexpected defect | 500 | Framework internal error without private detail |

## Source, derived, and projection classification

| Category | Examples |
|---|---|
| Provider facts | results identity/classification, LapNumber, Time, Position, PitInTime, PitOutTime, TrackStatus, FastF1Generated, Compound, Stint |
| Normalized facts | builtin integer nanoseconds, normalized status labels, explicit value quality, immutable participants/rows |
| Derived domain facts | consolidated multiplicity/conflict, leader reference, laps behind, equal-distance deficit, pit association/state, elapsed, reported-value difference, counts, canonical order |
| Public projections | compact participant entries, driver lap series, driver pit evidence, millisecond fields, strict API responses |

No raw FastF1 or Pandas structure crosses the first boundary.
