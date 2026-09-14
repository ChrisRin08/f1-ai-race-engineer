# Feature Specification: Tire Stints & Observed Degradation Analytics

**Feature Branch**: `003-tire-stint-analytics`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Feature 003 — Tire Stints & Observed Degradation Analytics"

## Clarifications

### Session 2026-09-11

- Q: Should Feature 003 require Theil-Sen as the analytical method for its robust straight-line trend, while leaving the implementation/library choice to planning? → A: Require Theil-Sen as the Feature 003 analytical method; defer library and implementation selection to planning.
- Q: To what precision should Feature 003 publish both `observed_pace_trend_seconds_per_lap` and the median absolute residual, after calculating them from unrounded source values? → A: Publish both metrics in seconds rounded to three decimal places; retain source precision throughout calculation before publication rounding.
- Q: After inherited and Feature 003 non-age lap exclusions are applied, how should missing, repeated, or decreasing reported tire ages affect the stint trend? → A: Exclude individual missing or unusable tire-age observations; allow a trend when at least six other eligible observations remain; invalidate the entire stint trend for repeated or decreasing valid reported ages; allow gaps; never reconstruct or infer tire age.
- Q: Should a missing compound and a present but unknown or unsupported compound produce distinct primary unavailability outcomes? → A: Treat missing compound metadata and a present unknown or unsupported compound as separate semantic outcomes at the same precedence level; defer exact serialized enum names to planning.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect One Driver's Stints (Priority: P1)

As a race analyst, I want to retrieve one driver's observed tire stints so that
I can understand how that driver's lap pace changed as reported tire age
increased and audit every lap used or excluded from each result.

**Why this priority**: Driver detail delivers the core analytical value and the
lap-level evidence needed to trust the result.

**Independent Test**: Use controlled race-session data for one known driver with
multiple reported stints, including one analytically available slick stint and
one unavailable stint. Verify the stint identities, metadata, trend result,
sample counts, primary availability reasons, limitations, and complete lap
evidence without relying on session-wide output.

**Acceptance Scenarios**:

1. **Given** a known driver with a valid slick-tire stint containing at least six
   eligible laps with valid increasing reported tire ages, **When** the user
   retrieves that driver's stint analytics, **Then** the result includes the
   observed pace trend in seconds per lap of reported tire age, a robust residual
   measure in seconds, complete sample counts, and the metric limitations.
2. **Given** a known driver with laps excluded by inherited lap-quality rules or
   Feature 003 quality rules, **When** the user retrieves driver detail, **Then**
   every source lap is accounted for once and shows whether it contributed to a
   trend and, when it did not, a deterministic primary reason.
3. **Given** a known driver whose reported stint cannot support a responsible
   trend, **When** the user retrieves driver detail, **Then** the stint remains
   visible with its available source metadata, no invented trend value, and one
   machine-readable primary unavailability reason.
4. **Given** a well-formed driver identifier that is absent from the supported
   session, **When** driver stint analytics are requested, **Then** the operation
   reports that the driver is unknown without fabricating an empty driver.
5. **Given** a lap whose accuracy or provider-generation metadata is unavailable
   but which otherwise satisfies every applicable eligibility rule, **When** the
   driver's stint is analyzed, **Then** the missing quality assertion alone does
   not exclude the lap and the unavailable source value remains auditable.

---

### User Story 2 - Review the Session Stint Field (Priority: P2)

As a race analyst, I want a summarized view of the observed tire stints for all
drivers in a supported race so that I can identify which stints have usable
trend estimates and choose where deeper driver-level inspection is worthwhile.

**Why this priority**: The session view makes the analytics discoverable across
the race while keeping detailed evidence in the driver resource.

**Independent Test**: Use a controlled supported session containing drivers
with available, wet-weather, missing-compound, present-unsupported-compound,
invalid-metadata, and insufficient-sample stints. Verify that every results
participant is represented, every identified stint has a summarized status, and
lap-level evidence is not duplicated into the session response.

**Acceptance Scenarios**:

1. **Given** a supported race with multiple participants and reported stints,
   **When** the user retrieves session-wide stint analytics, **Then** every
   authoritative results participant appears with summarized stint metadata,
   sample counts, availability, and trend values only where responsible.
2. **Given** a participant with no assignable stint laps, **When** the session
   view is retrieved, **Then** the participant remains visible with zero stints
   and an explicit summary of unassigned source evidence when such evidence
   exists.
3. **Given** repeated analysis of the same normalized session data, **When** the
   session view is retrieved more than once, **Then** its values and ordering are
   identical.

---

### User Story 3 - Understand Unavailable Trends (Priority: P3)

As a user or downstream explanation consumer, I want unavailable trends to state
why they were withheld so that I do not mistake missing, contradictory, wet, or
unsupported data for a zero-degradation result.

**Why this priority**: Explicit failure semantics prevent misleading conclusions
and make incomplete provider data safe to consume.

**Independent Test**: Present each defined stint-level source-data, compound,
tire-age, and sample failure independently and in controlled combinations.
Verify that no trend or residual is published and that the same fixed primary
reason is selected every time. Separately verify explicit inaccurate and
provider-generated lap exclusions and the neutral treatment of unavailable
quality assertions.

**Acceptance Scenarios**:

1. **Given** an intermediate or wet stint, **When** it is analyzed, **Then** the
   stint remains visible but has no trend or residual and is identified as a
   wet-weather compound outcome.
2. **Given** missing compound metadata, **When** the stint is analyzed, **Then**
   the missing source value remains explicit, no trend or residual is
   calculated, and the primary outcome distinguishes missing compound metadata.
3. **Given** a present unknown or unsupported compound, **When** the stint is
   analyzed, **Then** the source compound value is preserved, no trend or
   residual is calculated, and the primary outcome distinguishes a present
   unsupported value.
4. **Given** missing tire-age observations leave at least six other eligible
   observations with valid increasing reported ages, **When** the affected stint
   is analyzed, **Then** only the missing-age observations are excluded and the
   remaining observations may produce a trend without reconstruction.
5. **Given** fewer than six eligible observations after exclusions unrelated to
   missing tire age and no higher-precedence blocker, **When** an otherwise valid
   slick stint is analyzed, **Then** no trend or residual is published and the
   insufficient-sample outcome includes the observed count and required minimum.
6. **Given** repeated or decreasing valid reported tire ages in chronological
   lap order, **When** the affected stint is analyzed, **Then** the complete
   stint trend is unavailable because its tire-age history is inconsistent and
   no observation is silently repaired or discarded to restore monotonicity.

### Edge Cases

- A reported stint begins with tire age greater than one because the tire was
  previously used; the reported age is retained rather than restarted at one.
- One reported stint identifier occurs in separated lap ranges or is interrupted
  by another reported stint identifier.
- A reported stint contains multiple non-missing compound values, missing
  compound metadata, or a present compound value the policy does not recognize;
  conflicting values make stint metadata inconsistent, while the latter two
  cases produce distinct compound outcomes at the same precedence level.
- After non-age exclusions, a candidate lap has a missing, non-finite,
  non-positive, or non-integral reported tire age; only that observation is
  excluded, and the stint may remain analytically available if the minimum valid
  sample remains.
- After non-age exclusions, valid reported tire ages repeat or decrease in
  chronological lap-number order; the entire stint trend is unavailable rather
  than selectively dropping observations to repair the sequence.
- Structurally excluded laps create gaps in the eligible tire-age sequence; their
  ages are not reconstructed and valid later observations retain their reported
  values.
- A lap satisfies multiple exclusion conditions; exactly one primary lap reason
  is selected using the fixed policy order while other source diagnostics remain
  available.
- Explicitly inaccurate and explicitly provider-generated laps are excluded even
  when their timing and tire metadata otherwise appear usable.
- Accuracy or provider-generation metadata is unavailable for a lap; the missing
  assertion remains visible but does not exclude the lap by itself.
- Every stint is wet or unsupported, every lap is excluded, a participant has no
  lap rows, or the entire session has no analytically available trend.
- Two or more eligible laps have equal lap times, or the fitted trend is exactly
  zero or negative; these are valid numerical outcomes and are not relabeled.
- A supported session contains a driver who retired, was lapped, started from the
  pit lane, or completed fewer than six eligible observations.
- Source rows arrive in a different table order while retaining the same driver,
  lap, stint, and tire-age facts; the published result remains deterministic.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide summarized stint analytics for every
  authoritative results participant in a supported race session.
- **FR-002**: The system MUST provide detailed stint analytics for one known
  driver in a supported race session.
- **FR-003**: The feature MUST retain the existing supported-session boundary and
  MUST NOT add session coverage solely for stint analytics.
- **FR-004**: Existing Feature 001 and Feature 002 observable behavior, response
  meanings, and public contracts MUST remain unchanged.
- **FR-005**: Each analytics operation MUST use one loaded normalized race-session
  snapshot from the existing source boundary and MUST NOT create an independent
  source-loading path or perform duplicate source acquisition for separate
  projections within that operation.
- **FR-006**: Source-specific concerns, normalized race-lap facts, deterministic
  analytics, public result validation, and presentation concerns MUST remain
  separated according to the existing system boundaries.
- **FR-007**: Reported stint metadata MUST be the primary identity for an
  observed stint, scoped to one driver.
- **FR-008**: A usable reported stint identifier MUST be a finite, positive,
  integral source value. A missing or unusable identifier MUST NOT be replaced
  with an inferred identifier.
- **FR-009**: Laps sharing one driver and reported stint identifier MUST form one
  chronologically continuous observed run. Reappearance after another reported
  stint identifier or an unassigned interruption MUST make the reported stint
  inconsistent rather than silently joining or repairing it.
- **FR-010**: A valid stint MUST have one consistent non-missing compound value
  across its assigned source laps. Conflicting compound values MUST make the
  stint inconsistent.
- **FR-011**: A lap with a missing or unusable reported stint identifier MUST
  appear only as unassigned evidence. A usable reported stint identifier whose
  assigned laps contain contradictory stint metadata MUST produce one unavailable
  stint result for that reported identifier. Neither case may be repaired or
  replaced with inferred history.
- **FR-012**: Each identified stint summary MUST include the driver identity,
  reported stint identifier, preserved compound, observed lap-number range,
  observed reported tire-age range, total assigned lap count, eligible
  observation count, excluded observation count, analytical status, and primary
  unavailability reason when unavailable.
- **FR-013**: Driver detail MUST account for every normalized source lap for the
  selected driver exactly once, either within an identified reported stint or as
  unassigned source evidence.
- **FR-014**: Session-wide results MUST summarize stints and MUST NOT duplicate
  the complete lap-level evidence supplied by driver detail.
- **FR-015**: Feature 003 MUST reuse the existing structural/status lap-quality
  behavior for invalid timing, Lap 1, pit-in, pit-out, and disruptive track
  status from one shared policy implementation.
- **FR-016**: Feature 003 MUST preserve the existing first-match order among the
  inherited structural/status exclusions.
- **FR-017**: Feature 003 MUST NOT require a lap to pass Feature 002's driver-wide
  120% representative-pace anomaly rule before it may contribute to a stint
  trend.
- **FR-018**: After inherited exclusions, `IsAccurate == False` MUST exclude a lap
  from the trend sample, while `IsAccurate == True` MUST pass this quality check.
- **FR-019**: After inherited exclusions, a provider-generated value of `True`
  MUST exclude a lap from the trend sample, while a value of `False` MUST pass
  this quality check.
- **FR-020**: Unavailable accuracy metadata or unavailable provider-generation
  metadata MUST remain explicit but MUST NOT exclude a lap solely because the
  corresponding assertion is absent. Only an explicit inaccurate value or an
  explicit provider-generated value triggers its respective quality exclusion.
- **FR-021**: Every excluded lap in driver detail MUST have exactly one primary
  reason, selected in this order: inherited structural/status reason,
  explicitly inaccurate, explicitly provider-generated, and unusable tire-age
  observation. Available source diagnostics MAY preserve additional facts
  without changing the primary reason.
- **FR-022**: The supported slick compounds for this feature MUST be `SOFT`,
  `MEDIUM`, and `HARD`. Compound matching MUST be insensitive to surrounding
  whitespace and letter case while preserving the source value for audit.
- **FR-023**: `INTERMEDIATE` and `WET` stints MUST remain visible and MUST NOT
  receive a trend or residual value.
- **FR-024**: Missing compound metadata and a present unknown or unsupported
  compound value MUST remain explicit and MUST NOT receive a trend or residual
  value. They MUST produce distinct semantic unavailability outcomes, while the
  present source value MUST be preserved for audit.
- **FR-025**: A tire-age observation used in a trend MUST be finite, positive,
  integral, and reported by the source. A missing, non-finite, non-positive, or
  non-integral tire age MUST exclude only the affected observation and MUST NOT
  be reconstructed from lap number, stint length, or neighboring observations.
- **FR-026**: After inherited and Feature 003 non-age exclusions, candidate laps
  MUST be evaluated in chronological lap-number order independent of incidental
  source-table order. Valid reported tire ages MUST increase strictly in that
  order; any repeated or decreasing valid age MUST make the entire stint's
  tire-age history inconsistent and prevent a trend, rather than being dropped
  to repair the sequence.
- **FR-027**: Gaps between otherwise valid reported tire ages MAY remain when
  intervening laps are excluded; the remaining reported values MUST NOT be
  renumbered or compressed.
- **FR-028**: A reported tire age greater than one on the first observed lap of a
  stint MUST be retained so that previously used tires do not appear new.
- **FR-029**: A trend MUST require at least six eligible observations with six
  distinct, strictly increasing reported tire ages. Missing or otherwise
  unusable tire-age observations MUST NOT prevent a trend when at least six
  other eligible observations satisfy this requirement.
- **FR-030**: The primary result MUST be named
  `observed_pace_trend_seconds_per_lap` and MUST express the observed change in
  lap time, in seconds, for each additional lap of reported tire age.
- **FR-031**: A positive trend MUST mean observed laps became slower as reported
  tire age increased, a negative trend MUST mean they became faster, and zero
  MUST remain a valid neutral numerical result.
- **FR-032**: Available trends MUST use the deterministic Theil-Sen
  straight-line estimator so that an isolated extreme eligible lap time does
  not control the published slope. The implementation or library used to
  calculate Theil-Sen MUST be selected during planning without changing this
  analytical policy. The result MUST disclose the Theil-Sen method and the
  required publication precision.
- **FR-033**: Each available trend MUST include a robust residual measure equal
  to the median absolute difference, in seconds, between eligible observed lap
  times and the trend line's predicted lap times.
- **FR-034**: Trend and residual calculations MUST use the complete eligible
  sample at source precision. At publication, both
  `observed_pace_trend_seconds_per_lap` and the median absolute residual in
  seconds MUST be rounded deterministically to three decimal places.
- **FR-035**: For every stint, `total assigned laps` MUST equal `eligible
  observations + excluded observations`, and detailed exclusion counts MUST sum
  to the excluded count.
- **FR-036**: An available stint MUST publish both its trend and residual. An
  unavailable stint MUST publish neither value.
- **FR-037**: An unavailable stint MUST expose exactly one primary reason from a
  fixed policy that distinguishes, at minimum: inconsistent stint metadata,
  wet-weather compound, missing compound metadata, a present unknown or
  unsupported compound, missing tire age, inconsistent tire age, and an
  insufficient eligible sample. Exact serialized enum names are planning
  decisions.
- **FR-038**: When multiple blockers prevent a trend, the primary reason MUST
  follow this precedence: inconsistent stint metadata, wet-weather compound,
  either missing compound metadata or a present unknown or unsupported compound
  at the same precedence level, inconsistent tire age, missing-age exclusions
  that prevent the minimum eligible sample, then an otherwise insufficient
  eligible sample. Missing-age exclusions MUST NOT create a stint-level blocker
  when the minimum valid sample remains. Explicitly inaccurate and explicitly
  provider-generated laps affect the eligible sample count but do not create a
  missing-quality-metadata stint blocker.
- **FR-039**: Missing reported stint identifiers MUST be represented on
  unassigned lap evidence using `missing_stint_metadata`; they MUST NOT create a
  fabricated stint result.
- **FR-040**: Every result containing the trend MUST identify it as an observed
  association rather than isolated physical tire degradation and MUST state that
  it is not corrected for fuel load or burn, traffic, track evolution, driver
  tire management, changing environmental conditions, or other unmodeled race
  effects.
- **FR-041**: The limitation and adjustment status MUST be available in
  machine-readable result metadata as well as understandable descriptive text
  so downstream consumers cannot present the value as a causal tire-wear
  measurement without contradicting the source result.
- **FR-042**: Repeated analysis of identical normalized source data MUST produce
  identical stint identities, ordering, classifications, counts, availability
  outcomes, trend values, residual values, and limitation metadata.
- **FR-043**: Drivers and stints MUST have a stable deterministic order based on
  authoritative driver identity and chronological reported stint occurrence,
  independent of incidental source-table row order.
- **FR-044**: Missing or inconsistent required session-level source data MUST
  fail explicitly without fabricated participants, stints, lap evidence, trend
  values, or fallback facts.
- **FR-045**: Routine automated verification MUST use controlled source data and
  MUST NOT require live provider or network access.
- **FR-046**: Real-source acceptance MUST validate source compatibility,
  provenance, reconciliation, deterministic invariants, finite outputs, and
  limitation disclosure without treating an external analyst's degradation
  estimate as mathematical ground truth.
- **FR-047**: The feature MUST NOT add fuel, traffic, clean-air, track-evolution,
  environmental, or driver-management correction; physical tire-wear causality;
  wet/intermediate trend modeling; race-wide compound superiority; strategy or
  pit-window recommendations; prediction; AI explanation; telemetry analysis;
  frontend behavior; persistence or cloud infrastructure; or live-race behavior.

### Key Entities

- **Stint Analysis Policy**: The versioned rules for stint identity, supported
  compounds, inherited and feature-specific exclusions, tire-age validity,
  minimum sample, trend meaning, residual meaning, rounding, ordering, outcome
  precedence, and disclosed limitations.
- **Normalized Tire Lap**: One provider-derived race-lap observation containing
  driver and timing identity, structural/status quality facts, reported stint,
  reported compound, reported tire age, and nullable source-quality assertions;
  an absent assertion is not affirmative evidence of an inaccurate or generated
  lap.
- **Observed Stint**: One driver's chronologically continuous run associated
  with one usable reported stint identifier and one consistent compound.
- **Stint Lap Evidence**: The driver-detail record that connects one normalized
  source lap to a stint or unassigned state and explains its single primary
  inclusion/exclusion decision.
- **Stint Sample**: Reconciled total, eligible, and excluded observation counts,
  including counts by primary exclusion reason.
- **Observed Pace Trend**: The robust within-stint relationship between reported
  tire age and eligible observed lap time, expressed in seconds per lap of
  reported tire age.
- **Trend Reliability Evidence**: The eligible sample size, distinct tire-age
  count and range, and median absolute residual in seconds.
- **Stint Availability Outcome**: The available or unavailable state and the
  deterministic primary reason when no trend can responsibly be published.
- **Unassigned Lap Evidence**: A normalized driver lap that cannot be assigned to
  a reported stint without inventing or repairing source history.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For controlled supported-session data, users can retrieve a
  summarized stint result for 100% of authoritative results participants,
  including participants with zero identified stints.
- **SC-002**: In driver detail, 100% of the selected driver's normalized source
  laps are accounted for exactly once as included, excluded, or unassigned, and
  every count reconciliation equation holds.
- **SC-003**: For every valid slick stint with at least six eligible observations
  and valid strictly increasing reported tire ages, users receive one finite
  observed pace trend and one finite median absolute residual in seconds, each
  published to three decimal places after calculation at source precision.
- **SC-004**: For 100% of wet, intermediate, missing-compound,
  present-unsupported-compound, inconsistent stint metadata, inconsistent
  tire-age metadata, missing-age cases that prevent the minimum sample, and
  otherwise insufficient-sample control cases, no trend or residual is published
  and one deterministic machine-readable reason explains the outcome; missing
  and present unsupported compound cases produce distinct reasons.
- **SC-005**: A used tire beginning an observed stint above age one retains its
  reported starting age in 100% of controlled cases, with no reset or inferred
  reconstruction.
- **SC-006**: Repeating any analysis against identical normalized source data at
  least three times produces identical structured results each time.
- **SC-007**: Existing Feature 001 and Feature 002 acceptance cases produce the
  same observable results after Feature 003 is introduced.
- **SC-008**: Every published trend is accompanied by both machine-readable and
  human-readable interpretation metadata that identifies all six named
  unmodeled effect categories and states that the metric is observational.
- **SC-009**: In 100% of controlled cases where accuracy or provider-generation
  metadata is unavailable, the missing assertion alone does not exclude an
  otherwise eligible lap; explicit inaccurate and explicit provider-generated
  values remain excluded in 100% of their controlled cases.
- **SC-010**: A user can determine, using only one driver-detail result, the
  reported stint and tire-age context, every contributing lap, every excluded or
  unassigned lap, the primary reason for each decision, and why each stint trend
  is available or unavailable.

## Assumptions

- Feature 003 operates only on the race sessions already supported by the
  existing product boundary.
- Authoritative participant identity continues to come from existing session
  results; lap rows do not create new participants.
- Reported stint and tire-age values are source observations, not facts the
  product may infer or repair when absent or contradictory.
- `SOFT`, `MEDIUM`, and `HARD` are the only slick compound labels eligible for
  the initial trend policy. Other present values remain visible and unsupported.
- Missing compound metadata and a present unknown or unsupported compound value
  are separate semantic unavailability outcomes at the same precedence level;
  planning determines their exact serialized enum names.
- Missing accuracy or provider-generation metadata is an absence of an assertion,
  not affirmative evidence that the lap is inaccurate or provider-generated; it
  does not exclude the lap solely for that reason.
- Missing tire age excludes the affected candidate observation without
  reconstruction. If at least six other valid observations remain, missing age
  alone does not invalidate their reported chronology.
- After inherited and Feature 003 non-age exclusions, candidate observations are
  evaluated in chronological lap-number order rather than incidental source-table
  order. Repeated or decreasing valid tire age indicates an inconsistent age
  history for the entire stint and prevents a trend; gaps remain allowed.
- The detailed driver result is the audit resource; the session-wide result is a
  discovery and comparison summary.
- An unavailable trend is distinct from a numerical trend of zero.
- Exact public resource paths, schema composition, numeric schema type, and the
  implementation or library used for the required Theil-Sen estimator are
  planning decisions so long as they preserve the required three-decimal-place
  publication rule, satisfy all observable requirements above, and preserve
  existing contracts.
