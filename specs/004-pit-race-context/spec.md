# Feature Specification: Pit-Lane Visits & Lap-Boundary Race Context

**Feature Branch**: `004-pit-race-context`

**Created**: 2026-09-24

**Status**: Draft

**Input**: User description: "Feature 004 — Pit-Lane Visits & Lap-Boundary Race Context. Establish a trusted deterministic race-context layer that represents complete and incomplete pit-lane evidence and semantically correct lap-completion race context before later strategy simulation."

## Clarifications

### Session 2026-09-24

- Q: Which driver's observation must serve as the reference for an equal-distance lap-boundary separation? → A: The lap leader at that completed-lap boundary.
- Q: At which observed boundary should `laps_behind` be evaluated relative to the lap leader? → A: At each selected-driver lap completion, using the leader's latest completed lap at the same session timestamp.

### Session 2026-09-25

- Q: Which public numeric contract should represent session-relative timestamps, pit-lane elapsed time, equal-distance time deficit, and lapped-driver availability? → A: Publish integer milliseconds with half-up rounding; use `_session_time_ms`, `entry_to_exit_elapsed_ms`, and `equal_distance_time_deficit_ms`; keep `laps_behind` separate; and use `available`, `not_applicable`, or `unavailable` time-deficit status.
- Q: Which combined public evidence policy should Feature 004 use for pit states, before/after context, and disrupted track status? → A: Use pit evidence states `complete`, `unpaired_entry`, `unpaired_exit`, `conflicting`, and `unavailable`; take before/after context from the entry/in-lap and exit/out-lap completion rows without fallback; and expose ordered, de-duplicated normalized `track_statuses` with explicit availability and nullable `is_disrupted`. `is_disrupted` is true when any known disrupted status is present, false only when trustworthy status evidence supports no disrupted status, and null when the evidence is unavailable or cannot support a trustworthy boolean; `unknown` is never treated as green.
- Q: Which combined public projection contract should Feature 004 use for resource composition, audit granularity, ordering, and direct-construction invariants? → A: Provide a compact session-level participant view and auditable driver detail, with all pit evidence in driver detail and no separate pit-only resource in v1. Driver detail exposes the complete compact normalized lap-context series rather than raw provider rows. Apply canonical participant, lap, and pit-evidence ordering; represent duplicate source evidence through explicit conflict or multiplicity semantics; and reject ordering contradictions provable from exposed public fields, duplicate public identities, and state/field contradictions during direct construction. Both resources are projections of one centrally derived race-context analysis, not independently calculated views.

### Session 2026-09-29

- Q: How can public models validate order after millisecond publication loses exact chronology and TrackStatus lacks independent source-order provenance? → A: Keep exact domain canonical ordering, integer nanoseconds, ROUND_HALF_UP millisecond publication, and the current public schema. Services and projections preserve central-analysis order exactly. Direct public construction rejects only ordering contradictions provable from exposed fields; equal published milliseconds do not prove equal exact timestamps, and validators cannot independently reconstruct original TrackStatus observation order. Public ambiguity never authorizes sorting, inference, or repair.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect a Driver's Pit-Lane Visits (Priority: P1)

As a race analyst, I want to inspect a driver's source-backed pit-lane visits
and their surrounding race context so that I can understand when the driver
entered and exited the pit lane without mistaking lane transit for stationary
service time.

**Why this priority**: Pit-lane visit evidence is the smallest independently
useful addition and directly fills the product's current inability to explain
what happened around a driver's pit-lane passage.

**Independent Test**: Use controlled race-session facts for one known driver
with a normal completed visit and verify that the entry boundary, exit boundary,
entry-to-exit elapsed value, reported before/after tire and stint facts, and
available lap-completion context are all traceable to the same normalized
session snapshot.

**Acceptance Scenarios**:

1. **Given** one unambiguous pit entry followed by its corresponding pit exit,
   **When** the analyst retrieves the driver's pit evidence, **Then** one
   pit-lane visit with state `complete` identifies both boundary laps, both
   session timestamps, and the derived entry-to-exit elapsed value.
2. **Given** a complete pit-lane visit, **When** its elapsed value is presented,
   **Then** the result describes it only as entry-to-exit pit-lane elapsed time
   and does not label it stationary stop, service, mechanic, or tire-change
   duration.
3. **Given** source-backed compound and stint values exist around a complete
   visit, **When** the visit is inspected, **Then** the result preserves the
   entry/in-lap values as before context and the exit/out-lap values as after
   context, and whether each reported value changed, without claiming that a
   physical tire change was confirmed.
4. **Given** a driver has multiple unambiguous visits, **When** the driver's pit
   evidence is retrieved, **Then** every visit is represented once in a stable
   race chronology rather than only the first or last visit.
5. **Given** reported compound is the same before and after a visit, **When**
   the visit is inspected, **Then** the unchanged reported values remain visible
   and no tire-change event is inferred.
6. **Given** a known participant has no pit entry or pit exit evidence, **When**
   the participant's result is retrieved, **Then** it explicitly represents no
   observed pit-lane visit rather than fabricating one or treating the driver as
   unknown.

---

### User Story 2 - Understand Race Context at Completed-Lap Boundaries (Priority: P1)

As a race analyst, I want trusted race context at completed-lap boundaries so
that I can understand a driver's race position and equal-distance time deficit
without interpreting the result as a live or physical on-track gap.

**Why this priority**: A pit event is not meaningful without race context, and
lap completion is the strongest supported common-distance boundary available
without introducing telemetry or private timing streams.

**Independent Test**: Use controlled lap-completion facts for a driver and the
lap leader and verify that their comparison uses the same completed lap number,
identifies the leader observation, and equals the driver's normalized completion
timestamp minus the leader's normalized completion timestamp.

**Acceptance Scenarios**:

1. **Given** a driver and the lap leader both completed lap `n` with trustworthy
   session timestamps, **When** their equal-distance time deficit is requested,
   **Then** the derived time value equals the driver's lap-`n` completion time
   minus the lap leader's lap-`n` completion time.
2. **Given** an equal-distance time deficit is available, **When** it is
   presented, **Then** its meaning is explicitly "elapsed-time deficit after
   both observations completed the same race distance" and not live gap,
   current gap, instantaneous gap, physical separation, or telemetry distance.
3. **Given** trustworthy lap-completion position is available, **When** race
   context is presented, **Then** it is identified as lap-completion race
   position and not GPS position, physical coordinates, instantaneous position
   at pit entry, or live timing position.
4. **Given** the lap leader has completed more laps when a selected driver
   completes a lap, **When** race context is presented, **Then** the result
   preserves the difference between the leader's latest completed-lap count at
   that timestamp and the driver's newly completed-lap count, and does not
   invent a seconds value or predict a future completion.
5. **Given** a lap-completion observation overlaps Yellow, Safety Car, Virtual
   Safety Car, VSC ending, or Red Flag status, **When** race context is
   presented, **Then** the underlying timing observation remains available when
   otherwise trustworthy, every observed normalized status remains explicit,
   and `is_disrupted` is true.
6. **Given** trustworthy status evidence contains only understood,
   non-disrupted status, **When** race context is presented, **Then**
   `is_disrupted` is false; **And given** status evidence is unavailable or
   cannot support a trustworthy boolean, **Then** `is_disrupted` is null and an
   `unknown` status is not treated as green.

---

### User Story 3 - Preserve Incomplete and Uncertain Evidence (Priority: P2)

As a race analyst or downstream explanation consumer, I want incomplete,
missing, generated, or contradictory evidence to remain explicit so that I can
distinguish a trustworthy absence or unavailable result from a complete event.

**Why this priority**: Real race data includes pit-lane starts, retirements,
missing values, and source-generated rows. Silently dropping or repairing these
cases would make later strategy reasoning untrustworthy.

**Independent Test**: Use controlled participants containing an unpaired
initial exit, an unpaired final entry, a non-starter, a retirement, generated
lap evidence, and contradictory boundary facts. Verify that every source fact
is accounted for without a fabricated pair or metric.

**Acceptance Scenarios**:

1. **Given** a pit-lane starter has an initial pit exit with no earlier race pit
   entry, **When** pit evidence is derived, **Then** the unpaired exit remains
   visible with state `unpaired_exit` and is not discarded or paired with a
   fabricated entry.
2. **Given** a retiring driver has a final pit entry with no later exit,
   **When** pit evidence is derived, **Then** the unpaired entry remains visible
   with state `unpaired_entry` and has no entry-to-exit elapsed value.
3. **Given** an authoritative participant never starts and has no usable lap
   evidence, **When** session race context is produced, **Then** the participant
   remains identifiable with explicit absence or unavailability and no invented
   lap, position, gap, or pit visit.
4. **Given** a driver retires after producing some trustworthy race evidence,
   **When** the driver's result is produced, **Then** the earlier evidence is
   retained and later missing completion or exit facts are not synthesized.
5. **Given** a relevant provider value is missing, malformed, non-finite, or
   otherwise unusable, **When** normalization and analysis occur, **Then** the
   affected fact or derived value is explicitly unavailable while unrelated
   trustworthy evidence remains representable.
6. **Given** a lap observation is marked as provider-generated, **When** it is
   exposed or contributes to race context, **Then** that state remains explicit
   and the observation is not silently presented as ordinary measured evidence.
7. **Given** duplicate or contradictory source rows make a pit boundary or
   lap-completion fact ambiguous, **When** analysis occurs, **Then** the conflict
   is preserved with state `conflicting` where it affects pit evidence, or the
   affected derivation is withheld, rather than silently deduplicated, sorted
   into a preferred answer, repaired, or estimated.

---

### User Story 4 - Reuse One Auditable Race-Context Result (Priority: P2)

As a future product consumer, I want pit and lap-boundary facts derived once
from a consistent race snapshot so that compact session, auditable driver, and
later strategy views cannot disagree because they independently reinterpreted
the same source evidence.

**Why this priority**: Feature 004 is the trusted context foundation for later
strategy work, so its domain results must be reusable without speculative
architecture or duplicated calculations.

**Independent Test**: Analyze one controlled session snapshot, project the
compact session-level participant view and auditable driver detail from the same
central result, and verify identical shared facts, complete participant and pit
evidence accounting, canonical ordering, direct-construction rejection of
invalid structures, and no additional source acquisition within that operation.

**Acceptance Scenarios**:

1. **Given** one Feature 004 operation needs the session-level or driver-detail
   projection, **When** the operation completes, **Then** both projections use
   one source snapshot and one centrally derived race-context result rather
   than independently calculating shared facts.
2. **Given** identical normalized source facts, **When** analysis is repeated
   or projected differently, **Then** shared event identities, availability
   states, timing values, lap deficits, and ordering are identical.
3. **Given** a later strategy feature consumes Feature 004 results, **When** it
   needs pit or lap-boundary context, **Then** it can reuse the trusted result
   without reimplementing provider normalization, boundary pairing, or
   equal-distance time-deficit logic.
4. **Given** the session-level resource is requested, **When** it is projected,
   **Then** it contains one compact entry for every authoritative participant
   without duplicating the complete lap-context series or pit evidence.
5. **Given** a driver's detail is requested, **When** it is projected, **Then**
   it contains that driver's complete compact normalized lap-context series and
   all pit evidence, rather than raw provider rows or a separately calculated
   pit-only view.
6. **Given** a public result is directly constructed with an ordering violation
   provable from exposed public fields, duplicate public identities, or a
   state/field contradiction, **When** it is validated, **Then** it is rejected
   rather than silently sorted, deduplicated, or repaired. Valid canonical
   central projections remain accepted when millisecond collisions or missing
   independent source-order provenance prevent an ordering violation from
   being proved.

### Edge Cases

- A driver starts from the pit lane and the first pit evidence is an exit with
  no preceding race entry.
- A retiring driver records a final pit entry without a subsequent exit.
- A driver never starts, has no lap rows, or has no completed lap.
- A driver completes part of the race, retires, and has trustworthy earlier
  context but no later context.
- A driver makes multiple pit-lane visits, including consecutive or closely
  spaced boundary evidence.
- A driver has no pit-lane visit.
- Reported compound changes across a visit, remains the same, is missing on one
  side, or conflicts across candidate context observations.
- Reported stint changes across a visit, remains the same, is missing on one
  side, or is unusable.
- A complete boundary pair has usable timestamps but unavailable boundary-row
  tire, stint, position, or time-deficit context.
- An entry timestamp is not earlier than a candidate exit timestamp, or the
  source provides more than one plausible boundary for a pairing.
- A lap number, lap-completion timestamp, position, track status, participant
  identity, or classification fact is missing, malformed, non-finite,
  non-integral where integral identity is required, or contradictory.
- Duplicate rows represent identical evidence, conflicting evidence for the
  same driver/lap, or competing pit boundaries.
- A provider-generated lap carries otherwise usable timing or position facts.
- A lap contains more than one track-status state, including a disrupted state
  alongside another state.
- Track-status evidence is missing, unusable, or normalizes to `unknown`, with
  no known disrupted status that would make `is_disrupted` true.
- A pit boundary or lap completion occurs during Yellow, Safety Car, Virtual
  Safety Car, VSC ending, or Red Flag conditions.
- Two drivers have completion timestamps for the same lap number; equal times
  and positive deficits remain representable, while a contradictory negative
  driver-minus-leader result is unavailable.
- A driver is one or more completed laps behind the race reference; a seconds
  deficit for unequal race distance is not fabricated.
- The lap leader's observation for a completed lap is missing or unusable even
  though the selected driver's observation exists.
- Source rows arrive in a different incidental table order while retaining the
  same normalized facts.
- The controlled 2025 Monza snapshot does not contain every edge case; controlled
  source data covers cases that cannot be relied on in the live dataset.

## Requirements *(mandatory)*

### Functional Requirements

#### Product Boundary and Compatibility

- **FR-001**: The system MUST provide deterministic pit-lane visit evidence and
  lap-boundary race context for authoritative participants in a supported race
  session.
- **FR-002**: Feature 004 MUST retain the existing supported-session boundary;
  the 2025 Italian Grand Prix Race at Monza is the controlled acceptance dataset
  and MUST NOT become a permanent race-specific business rule.
- **FR-003**: Existing Feature 001 session-summary behavior, response schema,
  operation identifiers, and error semantics MUST remain unchanged.
- **FR-004**: Existing Feature 002 `representative-race-pace-v1` behavior,
  including its 120% anomaly rule, ranking, tie, comparison, response, and error
  semantics, MUST remain unchanged.
- **FR-005**: Existing Feature 003 `observed-tire-stint-pace-trend-v1` behavior,
  including structural exclusion precedence, availability precedence, compound
  rules, tire-age rules, estimator, response, and error semantics, MUST remain
  unchanged.
- **FR-006**: Feature 004 MUST use supported public FastF1 session data,
  including justified facts from public `Session.laps` and `Session.results`, as
  its foundational provider evidence.
- **FR-007**: Feature 004 MUST NOT depend on `fastf1._api`, private timing-stream
  parsing, private `GapToLeader` or `IntervalToPositionAhead` fields, unstable
  cache internals, telemetry loading, `DistanceToDriverAhead`, GPS coordinates,
  distance integration, or speed-derived separation.
- **FR-008**: Authoritative participant identity MUST continue to come from the
  session's trusted participant or classification source; lap rows MUST NOT
  silently create participants.

#### Pit-Lane Visit Evidence

- **FR-009**: The system MUST retain each trustworthy pit entry boundary with
  its driver, source lap identity, and normalized session timestamp when
  available; the public timestamp MUST be named `entry_session_time_ms`.
- **FR-010**: The system MUST retain each trustworthy pit exit boundary with its
  driver, source lap identity, and normalized session timestamp when available;
  the public timestamp MUST be named `exit_session_time_ms`.
- **FR-011**: The system MUST represent a complete `pit_lane_visit` only when an
  entry and exit can be associated unambiguously from source-backed evidence.
- **FR-012**: A complete pit-lane visit MUST expose its entry lap, exit lap,
  `entry_session_time_ms`, `exit_session_time_ms`, and
  `entry_to_exit_elapsed_ms` when the required timestamps are usable.
- **FR-013**: `entry_to_exit_elapsed_ms` MUST equal the normalized exit session
  timestamp minus the normalized entry session timestamp, calculated at source
  precision and published only afterward as integer milliseconds using half-up
  rounding. It MUST be withheld when either boundary timestamp is unavailable,
  invalid, contradictory, or not unambiguously paired.
- **FR-014**: The system MUST describe `entry_to_exit_elapsed_ms` as pit-lane
  entry-to-exit elapsed time and MUST NOT describe it as stationary pit-stop
  time, service time, mechanic time, tire-change duration, or any narrower event
  the source does not prove.
- **FR-015**: Unpaired entry evidence and unpaired exit evidence MUST remain
  representable and MUST NOT silently disappear, become a complete visit, or
  receive a fabricated missing boundary.
- **FR-016**: Each pit evidence result MUST use exactly one explicit state from
  `complete`, `unpaired_entry`, `unpaired_exit`, `conflicting`, or `unavailable`
  rather than requiring consumers to infer its meaning from omitted fields.
- **FR-017**: Every trustworthy pit boundary for a participant MUST be accounted
  for exactly once within evidence whose state is `complete`, `unpaired_entry`,
  `unpaired_exit`, `conflicting`, or `unavailable`, as justified by the source.
- **FR-018**: All pit evidence for one driver, including multiple pit-lane
  visits, MUST be retained and ordered by earliest usable boundary session
  timestamp, then earliest usable boundary lap, then the fixed state order
  `complete`, `unpaired_entry`, `unpaired_exit`, `conflicting`, and
  `unavailable`, independent of incidental provider table order. Evidence
  without a usable chronology MUST appear after chronologically orderable
  evidence.
- **FR-019**: Pit transition context MUST use the pit-entry/in-lap completion
  row for reported before values and the pit-exit/out-lap completion row for
  reported after values. It MUST expose reported compound and reported stint
  from those rows when usable, preserve unavailable values explicitly, and MUST
  NOT substitute a last pre-entry or first post-exit racing row.
- **FR-020**: The system MAY state whether reported compound or reported stint
  values differ across the selected before/after context, but MUST NOT call the
  result a `confirmed_tire_change` or claim a physical tire change occurred.
- **FR-021**: Relevant available lap-completion race context from the selected
  entry/in-lap and exit/out-lap completion rows MUST remain associated with the
  event without being mislabeled as instantaneous context at the entry or exit
  timestamp; a missing boundary row MUST remain unavailable without fallback.
- **FR-022**: A participant with no pit boundary evidence MUST remain visible as
  having no observed pit-lane visit in the compact session-level participant
  view and corresponding driver detail rather than receiving an invented event.

#### Lap-Boundary Race Context

- **FR-023**: The system MUST represent trusted race context at completed-lap
  boundaries using the source-reported lap number and a normalized
  lap-completion session timestamp when each is usable; the public timestamp
  MUST be named `lap_completion_session_time_ms`.
- **FR-024**: Lap-boundary context MUST preserve the provider-exposed
  lap-completion race position when usable and MUST identify it narrowly as a
  lap-completion position.
- **FR-025**: Lap-completion position MUST NOT be described as GPS position,
  physical track coordinates, instantaneous position at pit entry, or live
  timing position.
- **FR-026**: Lap-boundary context MUST expose an ordered, de-duplicated
  `track_statuses` collection of observed normalized labels drawn from `green`,
  `yellow`, `safety_car`, `virtual_safety_car`,
  `virtual_safety_car_ending`, `red_flag`, and `unknown`, together with explicit
  `available` or `unavailable` track-status availability and whether the source
  marks the lap as provider-generated. Mixed observed statuses MUST remain
  visible in deterministic source-backed observation order.
- **FR-027**: `is_disrupted` MUST be true when any known `yellow`, `safety_car`,
  `virtual_safety_car`, `virtual_safety_car_ending`, or `red_flag` status is
  present. It MUST be false only when trustworthy status evidence exists, every
  observed status is understood, and no disrupted status is present. It MUST be
  null when status evidence is unavailable or cannot support a trustworthy
  boolean; `unknown` MUST NOT be silently treated as `green`, although a known
  disrupted status alongside `unknown` is sufficient for true.
- **FR-028**: A trustworthy underlying lap-completion timing observation MUST
  NOT be removed solely because it occurred during a disrupted or neutralized
  status; sufficient status context MUST accompany it for downstream
  interpretation.
- **FR-029**: When both a driver and the lap leader have trustworthy completion
  timestamps for the same completed lap number `n`, the system MUST be able to
  derive `equal_distance_time_deficit_ms` as
  `driver_completion_time(n) - lap_leader_completion_time(n)`. The lap leader
  for this metric is the participant with provider-exposed lap-completion race
  position `1` at boundary `n`. The difference MUST be calculated at source
  precision and published only afterward as a non-negative integer number of
  milliseconds using half-up rounding; a contradictory negative result MUST be
  unavailable rather than published.
- **FR-030**: Every equal-distance time deficit MUST identify or make
  unambiguous the driver observation, lap-leader observation, shared completed
  lap number, and driver-minus-leader direction of the value.
- **FR-031**: An equal-distance time deficit MUST be described as elapsed-time
  deficit after both observations completed the same race distance and MUST
  NOT be described as live gap, current gap, instantaneous gap, physical car
  separation, or telemetry separation.
- **FR-032**: The system MUST NOT derive an equal-distance time deficit
  from observations with different completed-lap counts.
- **FR-033**: At each trustworthy selected-driver lap-completion timestamp, the
  system MUST evaluate `laps_behind` as the lap leader's latest trustworthy
  completed-lap count at or before that timestamp minus the selected driver's
  newly completed-lap count. When this value is one or greater, the result MUST
  preserve that explicit lap-deficit meaning, set
  `equal_distance_time_deficit_ms` to null, and set its status to
  `not_applicable`. When `laps_behind` is zero and both same-lap timestamps are
  trustworthy, the status MUST be `available` and the time deficit MUST be
  present. When required evidence is missing, invalid, or conflicting, the time
  deficit MUST be null and its status MUST be `unavailable`.
- **FR-034**: The system MUST NOT predict when a lapped participant would
  complete the lap leader's current lap or translate that prediction into a
  fabricated seconds gap.
- **FR-035**: Required race or classification context used to interpret a lap
  deficit or lap-completion observation MUST remain source-backed and explicit;
  missing classification facts MUST yield an unavailable interpretation rather
  than an inferred race state.

#### Integrity, Public Semantics, and Auditability

- **FR-036**: Missing, invalid, non-finite, ambiguous, duplicate, or
  contradictory provider facts MUST NOT be silently sorted, repaired,
  deduplicated, estimated, or fabricated to simplify a result.
- **FR-037**: Duplicate or contradictory source evidence MUST retain explicit
  multiplicity or conflict meaning within the single applicable compact public
  item. It MUST NOT create duplicate public identities or be silently
  discarded, and any affected derived value MUST be unavailable when no single
  source-backed interpretation is justified.
- **FR-038**: A non-starter, retiree, lapped participant, pit-lane starter,
  participant with multiple visits, and participant with no visit MUST all be
  representable without race-specific exceptions.
- **FR-039**: Provider-generated lap evidence MUST retain an explicit generated
  state wherever it is exposed or used; absence of that source assertion MUST
  not be converted into an affirmative generated or non-generated fact.
- **FR-040**: The eventual public contract MUST distinguish source facts from
  derived metrics and distinguish complete, incomplete, unavailable, and
  conflicting states wherever those meanings differ.
- **FR-041**: Nullable or unavailable values MUST have explicit semantics and
  MUST NOT be represented as NaN, infinity, a magic number, an empty string, or
  a fabricated zero.
- **FR-042**: The public contract MUST avoid an ambiguous single-number race-gap
  representation and MUST preserve lap deficit separately from any optional
  `equal_distance_time_deficit_ms` value and its explicit status.
- **FR-043**: Results MUST be deterministic and sufficiently auditable for a
  user to determine which source boundaries and lap-completion observations
  support a value or why the value is unavailable without exposing raw provider
  rows.

#### Architecture, Reuse, and Verification Constraints

- **FR-044**: Provider-specific table types, scalar types, column conventions,
  and missing-value behavior MUST remain isolated at the provider boundary and
  MUST NOT enter pure race-context analysis.
- **FR-045**: Feature 004 analysis MUST consume reusable application-owned,
  immutable normalized facts rather than treating provider objects as the
  domain model.
- **FR-046**: Each Feature 004 operation MUST use one loaded session snapshot
  and normalize it once where practical; it MUST NOT independently reload the
  source for each driver, pit event, reference comparison, or response view.
- **FR-047**: Pit and lap-boundary race-context facts MUST be derived once into
  one central race-context analysis. The compact session-level participant view
  and auditable driver detail MUST be projections of that same result, and
  future strategy features MUST be able to reuse it rather than recalculating
  shared facts under view-specific rules.
- **FR-048**: Analytical calculations and evidence qualification MUST remain in
  pure deterministic analytics, not in transport routes, orchestration
  services, public-model validators, frontend code, or a future AI layer.
- **FR-049**: The feature MUST preserve the established flow of approved source
  data to provider normalization, application-owned immutable input, pure
  deterministic analytics, orchestration, strict public results, and transport
  exposure.
- **FR-050**: The design MUST use the simplest boundaries needed for provider
  isolation, reusable analysis, and future Feature 005 consumption; it MUST NOT
  require speculative repositories, generic factories, plugin systems, broad
  inheritance hierarchies, single-implementation interfaces, or duplicate
  wrapper layers.
- **FR-051**: Routine verification MUST use controlled source data without live
  provider or network access and MUST cover edge cases not guaranteed to occur
  in the Monza acceptance snapshot.
- **FR-052**: Separately opted-in real-source acceptance MUST validate supported
  public-provider compatibility, provenance, deterministic invariants, and
  evidence accounting without freezing incidental Monza results as universal
  business rules.
- **FR-053**: Repeating analysis of identical normalized facts MUST produce
  identical visit association, incomplete/conflicting states, lap-boundary
  context, time-deficit semantics, availability, and ordering.
- **FR-054**: The session-level resource MUST contain exactly one compact entry
  for every authoritative participant.
- **FR-055**: Session-level participant entries MUST be ordered by ascending
  numeric driver number. Participants without a usable numeric driver number
  MUST follow numbered participants in normalized authoritative-identity order.
- **FR-056**: A compact session-level participant entry MUST NOT embed or
  duplicate that participant's complete lap-context series or pit evidence.
- **FR-057**: Driver detail MUST contain the driver's complete compact
  lap-context series.
- **FR-058**: Driver detail MUST contain all pit evidence for that driver.
- **FR-059**: Driver-detail lap-context items MUST be ordered by ascending lap
  number.
- **FR-060**: Driver detail MUST expose application-owned normalized domain
  evidence rather than raw provider rows.
- **FR-061**: Feature 004 v1 MUST NOT expose a separate pit-only public
  resource.
- **FR-062**: Central analytics MUST own canonical order using the full
  normalized facts, including exact nanosecond chronology and supported
  TrackStatus observation order. Services and projections MUST preserve that
  order exactly without sorting or reinterpretation. Direct public construction
  MUST reject every ordering contradiction provable from exposed public fields.
  Participant and lap-context ordering under FR-055 and FR-059 remains fully
  checkable. Pit-boundary and pit-evidence ordering is checkable only where the
  public facts establish the preceding ordering dimensions: equal published
  milliseconds MUST NOT be treated as proof of equal exact timestamps or used
  to justify lap/kind/state tie-breaks. Genuinely absent chronology permits
  lower observable keys only where the domain policy justifies them.
  TrackStatus validation MUST enforce allowed values, uniqueness, availability,
  and the disruption truth table, without independently reconstructing original
  source-observation order or inventing enum order.
- **FR-063**: Direct construction MUST reject duplicate public participant or
  driver/lap identities.
- **FR-064**: Direct construction MUST reject combinations of public state and
  fields that contradict the specified state semantics.
- **FR-065**: Direct construction MUST NOT silently sort, deduplicate, or repair
  supplied collections or invalid public results under FR-062, FR-063, or
  FR-064. Validators MUST NOT derive, calculate, pair, infer, or reconstruct
  ordering distinctions lost during projection. Public ambiguity means an
  ordering violation cannot independently be proved; it MUST NOT cause a
  valid canonical central projection to be rejected or authorize a different
  canonical order.

### Approved Source and Architecture Constraints

The approved v1 foundation is supported public FastF1 `Session.laps` and
`Session.results` data. The feature does not enable telemetry loading. Private
timing APIs, private gap fields, unstable cache internals, and telemetry are not
acceptable foundational dependencies. The existing architectural flow remains
authoritative:

```text
FastF1/Pandas
  -> provider normalization
  -> application-owned immutable inputs
  -> pure deterministic race-context analytics
  -> service/orchestration
  -> strict public results
  -> API transport
```

The specification requires these boundaries and outcomes but does not select
new class names, file names, route paths, or estimation libraries. Its clarified
session-level and driver-detail composition is a product contract rather than a
class or transport design.

### Key Entities

- **Pit Boundary Evidence**: One source-backed pit entry or pit exit observation
  for an authoritative driver, including its reported lap identity, normalized
  session timestamp when usable, provenance, and evidence quality state.
- **Pit-Lane Visit**: An unambiguous association between one entry boundary and
  one exit boundary, with derived entry-to-exit elapsed time only when both
  timestamps support it.
- **Incomplete Pit Evidence**: A trustworthy unpaired entry or exit that must
  remain visible without a fabricated counterpart.
- **Pit Transition Context**: Source-backed reported compound, reported stint,
  and lap-completion race context from the entry/in-lap and exit/out-lap
  completion rows, with a missing side unavailable and no racing-lap fallback.
- **Lap-Completion Observation**: One driver's source-backed state after
  completing a reported lap number, including normalized session timestamp,
  lap-completion position when available, ordered normalized `track_statuses`,
  explicit track-status availability, nullable `is_disrupted`, and generated
  state.
- **Equal-Distance Time Deficit**: The selected driver's trustworthy
  completion timestamp minus the lap leader's trustworthy completion timestamp
  for the same completed lap number, published as
  `equal_distance_time_deficit_ms`; it is not a live or physical separation.
- **Lap-Deficit Context**: The difference between the lap leader's latest
  trustworthy completed-lap count and the selected driver's newly completed-lap
  count at the selected driver's lap-completion timestamp, kept distinct from an
  optional equal-distance time deficit.
- **Race-Context Availability**: The complete, incomplete, unavailable,
  not-applicable, or conflicting meaning that explains whether a source fact or
  derived value can be published responsibly.
- **Race-Context Analysis**: The reusable deterministic result for the complete
  authoritative participant field from one normalized session snapshot and the
  sole analytical source for both public projections and future Feature 005
  reuse.

## Out of Scope

Feature 004 does not implement or claim:

- TV-style live race gaps, current gaps, or instantaneous on-track separation;
- exact stationary pit-service, mechanic, or tire-change duration;
- confirmed physical tire-change events;
- causal pit-stop time loss, clean-air estimates, undercut conclusions, overcut
  conclusions, pit-window recommendations, what-if simulation, or predictive
  strategy;
- machine learning or AI-generated calculations or explanations;
- frontend or dashboard implementation;
- live-race behavior;
- telemetry loading or analysis, GPS coordinates, distance-to-driver-ahead, or
  speed-integration gap models;
- private provider timing-stream parsing, private gap/interval fields, or
  unstable cache internals;
- database persistence, cloud infrastructure, deployment work, authentication,
  or unrelated platform expansion;
- a complex neutralization correction model; or
- broader dynamic session coverage solely for this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In controlled complete-visit cases, 100% of unambiguous entry and
  exit pairs produce one visit containing both boundary laps and timestamps,
  and every valid `entry_to_exit_elapsed_ms` equals the source-precision exit
  time minus entry time published once with half-up millisecond rounding.
- **SC-002**: In controlled incomplete cases, 100% of unpaired initial exits and
  final entries remain visible as `unpaired_exit` and `unpaired_entry`,
  respectively, without a fabricated counterpart or elapsed value.
- **SC-003**: Across controlled participants with zero, one, and multiple pit
  visits, 100% of trustworthy pit boundaries are accounted for exactly once as
  `complete`, `unpaired_entry`, `unpaired_exit`, `conflicting`, or `unavailable`
  evidence.
- **SC-004**: In 100% of published same-distance comparison cases, both
  observations share the same completed lap number and the time value
  `equal_distance_time_deficit_ms` equals driver completion time minus
  lap-leader completion time after one half-up millisecond publication step.
- **SC-005**: In 100% of controlled unequal-distance cases, the result preserves
  the completed-lap deficit evaluated at the selected driver's lap-completion
  timestamp, reports `not_applicable` with no equal-distance time-deficit value,
  and publishes no predicted future completion.
- **SC-006**: Every published position value is identifiable from the result as
  lap-completion race position, and no result labels it as GPS, instantaneous,
  or live position.
- **SC-007**: Every controlled status case exposes its ordered normalized
  `track_statuses` and availability; `is_disrupted` is true for any known
  disrupted status, false only for trustworthy fully understood evidence with
  none present, and null for unavailable or otherwise indeterminate evidence,
  while otherwise trustworthy timing is never removed solely for status.
- **SC-008**: Controlled non-starter, retirement, missing-data,
  provider-generated, duplicate, and contradictory cases yield explicit and
  deterministic evidence or unavailability states with no fabricated race fact.
- **SC-009**: Repeating the same analysis at least three times and projecting it
  into the session-level and driver-detail resources produces identical shared
  facts, derived values, states, and canonical ordering.
- **SC-010**: Each Feature 004 operation can produce all requested projections
  from one source snapshot and one centrally derived reusable race-context
  analysis, without source acquisition or independent calculation per driver,
  boundary, comparison, or view.
- **SC-011**: Existing Feature 001, Feature 002, and Feature 003 acceptance
  scenarios produce the same observable results after Feature 004 is introduced.
- **SC-012**: Using only the resulting audit semantics, a reviewer can determine
  for every published pit elapsed value, position, lap deficit, and
  equal-distance time deficit which source observations support it or why it is
  unavailable.
- **SC-013**: Controlled direct-construction cases reject 100% of ordering
  violations provable from exposed public fields, duplicate public participant
  or driver/lap identities, and state/field contradictions without silently
  sorting, deduplicating, calculating, or repairing them. They accept 100% of
  otherwise valid canonical central projections in controlled
  millisecond-collision and TrackStatus source-order cases. Full participant
  and lap-order validation, strict scalar validation, and all other structural
  invariants remain required.

## Assumptions

- Feature 004 applies to race sessions already supported by the product; it does
  not define equivalent semantics for practice, qualifying, or sprint
  qualifying.
- Public session lap and results facts from the approved provider are sufficient
  to establish the v1 pit-boundary and lap-completion foundation, subject to
  explicit missing and inconsistent states.
- Pit entry and exit timestamps represent session-time boundaries at pit-lane
  passage; their difference represents lane entry-to-exit elapsed time only.
  Public session-relative timestamps and derived time values use integer
  milliseconds with half-up rounding after source-precision calculation.
- Lap-completion timestamps compare equal completed race distance only when lap
  numbers match and both the selected driver and lap leader observations are
  trustworthy.
- Lap deficit is evaluated when the selected driver completes a lap, using the
  lap leader's latest trustworthy completed lap at or before that same session
  timestamp.
- Lap-completion position is a discrete race-context observation at a completed
  lap boundary, not continuous vehicle location.
- Pit before/after context comes only from the entry/in-lap and exit/out-lap
  completion rows; missing boundary context is not replaced by a nearby racing
  lap.
- Neutralized or disrupted context is disclosed rather than corrected away in
  v1. Unknown status is not treated as green, and `is_disrupted` remains null
  when the evidence cannot support a trustworthy boolean.
- Reported compound and stint values are source evidence. A change in reported
  values does not by itself prove a physical tire-change event.
- Missing or contradictory evidence is a valid domain outcome and is not a
  reason to invent, interpolate, or repair race facts.
- Session-level and driver-detail resources are projections of the same central
  analysis. Driver detail publishes compact normalized audit evidence rather
  than raw provider rows, and Feature 004 v1 has no separate pit-only resource.
