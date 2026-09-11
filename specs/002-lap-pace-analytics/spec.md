# Feature Specification: Lap Data & Driver Pace

**Feature Branch**: `002-lap-pace-analytics`

**Created**: 2026-09-07

**Status**: Draft

**Input**: User description: "Build Phase 2 — Race Analytics Engine, Part 1:
Lap Data & Driver Pace. Extend the existing Formula 1 data foundation with
deterministic, explainable driver lap filtering, overall race-pace summaries,
session pace ranking, and driver-to-driver comparison."

## Clarifications

### Session 2026-09-07

- Q: Should wet and intermediate laps remain eligible for the initial overall race-pace metric? → A: Keep dry, intermediate, and wet laps eligible when they pass all other rules, and disclose that the metric is not adjusted for track conditions.
- Q: How many representative laps must a driver have before the system publishes race-pace metrics? → A: At least five representative laps.
- Q: Which source-backed identifier should clients use to select a driver in analytics requests? → A: Use driver_number as the canonical request identifier; return abbreviation and name only as descriptive identity fields.
- Q: When one driver's summary is requested, must the system analyze every session participant with lap data to determine that driver's delta to the true session-best pace? → A: Yes. Load the FastF1 session/lap dataset once per analysis operation, derive the complete session-field analysis from that shared snapshot, and reuse it for individual summaries and comparisons.
- Q: Which numeric publication policy should define consistency, rounding, ranking, and ties? → A: Use population standard deviation; calculate from unrounded source durations; publish durations as integer milliseconds using half-up rounding; derive deltas, ranks, and ties from published median values; order tied drivers by ascending numeric driver_number.
- Q: How should positive durations that round to 0 ms be treated? → A: A usable lap duration must be at least 500,000 ns. Smaller durations are `invalid_timing`; exactly 500,000 ns is valid timing and publishes as 1 ms. Never clamp a rounded zero or weaken the positive-millisecond contract.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Inspect a Driver's Representative Race Pace (Priority: P1)

As a race analyst, I want to inspect a driver's source laps, understand which
laps represent normal racing pace, and see a repeatable overall pace summary so
that I can assess the driver's race performance without relying on a single
fastest lap.

**Why this priority**: A trustworthy per-driver pace summary is the foundation
for every comparison and is the smallest independently useful analytics result.

**Independent Test**: Select a driver from the supported control race and
verify that the result identifies the driver, accounts for every source lap,
explains each included or excluded lap, and calculates all required metrics
from only the representative laps.

**Acceptance Scenarios**:

1. **Given** a supported driver with usable race laps, **When** the analyst
   requests that driver's lap and pace information, **Then** the result includes
   driver identity, source-lap count, representative-lap count, median, mean,
   fastest lap, consistency, delta to the best driver, filtering policy, and
   exclusion information.
2. **Given** source laps containing Lap 1, missing or invalid lap times, pit-in
   laps, pit-out laps, and other laps excluded by the documented policy,
   **When** the pace summary is calculated, **Then** those laps do not affect
   the pace metrics and their exclusions are visible and explainable.
3. **Given** the same source snapshot and filtering policy, **When** the same
   driver analysis is requested repeatedly, **Then** all returned lap
   classifications and pace values are identical.
4. **Given** a driver's accuracy indicator is unavailable or false only because
   the source could not perform its accuracy check, **When** representative
   laps are selected, **Then** otherwise usable laps are not discarded solely
   for that reason.
5. **Given** a supported driver has too few representative laps for a valid
   pace result, **When** the analysis is requested, **Then** the system reports
   the insufficiency and the exclusion evidence without inventing metrics.

---

### User Story 2 - Compare Two Drivers on the Same Pace Basis (Priority: P2)

As a race analyst, I want to compare two drivers using the same representative
lap policy and primary pace metric so that I can tell which driver had stronger
overall race pace and by how much.

**Why this priority**: Direct comparison answers a central race-engineering
question while depending on the trusted per-driver analysis established in the
first story.

**Independent Test**: Select two supported drivers from the control race and
verify that both summaries use the same source snapshot and policy, and that
the comparison delta agrees exactly with their primary pace values.

**Acceptance Scenarios**:

1. **Given** two supported drivers with sufficient representative laps,
   **When** Driver A is compared with Driver B, **Then** both driver summaries
   are returned with an explicit result identifying the faster representative
   pace and the signed difference between them.
2. **Given** Driver A's median representative lap is slower than Driver B's,
   **When** the comparison is calculated, **Then** the comparison delta is
   positive because it is defined as Driver A's median minus Driver B's median.
3. **Given** the comparison order is reversed, **When** Driver B is compared
   with Driver A from the same snapshot, **Then** the signed comparison delta
   has the same magnitude and the opposite sign.
4. **Given** either driver lacks sufficient representative laps, **When** a
   comparison is requested, **Then** no winner or fabricated pace difference
   is returned and the unavailable comparison is explained.

---

### User Story 3 - Identify the Strongest Overall Representative Pace (Priority: P3)

As a race analyst, I want to review comparable pace summaries across eligible
drivers in a session so that I can identify who had the strongest
representative overall race pace.

**Why this priority**: A session-wide view answers the headline analytics
question and supplies the best-pace reference used by individual driver
summaries.

**Independent Test**: Analyze the supported control race and verify that every
eligible driver is ranked by the same primary metric, the best driver has a
zero delta, and every other delta is measured from that best value.

**Acceptance Scenarios**:

1. **Given** a supported race with multiple eligible drivers, **When** the
   analyst requests the session pace view, **Then** drivers with valid summaries
   are ordered from lowest to highest median representative lap time.
2. **Given** the ordered session result, **When** pace deltas are inspected,
   **Then** the best representative driver has a zero delta and each other
   driver's delta equals that driver's median minus the best median.
3. **Given** two drivers have the same primary pace at the published precision,
   **When** the result is ordered, **Then** they are reported as tied and a
   documented stable secondary ordering is used.
4. **Given** participants without enough representative data, **When** the
   session result is produced, **Then** they remain visible as unavailable but
   do not receive a fabricated rank or pace delta.

### Edge Cases

- A driver appears in the session results but has no matching lap rows.
- A driver has source laps but every lap is excluded.
- A driver has fewer than five representative laps.
- Lap time or lap number is missing, malformed, non-positive, infinite, or not
  representable safely in the response.
- Durations of 0 ns, negative values, 1 ns, and 499,999 ns are `invalid_timing`;
  500,000 ns and 500,001 ns pass timing validity and both publish as 1 ms,
  while remaining subject to every other representative-lap rule.
- One lap satisfies multiple exclusion conditions.
- Pit timing indicators are partially missing or inconsistent.
- Track-status information contains multiple status values within one lap.
- The source cannot determine lap accuracy for some or all laps.
- An anomalously slow lap is valid source data but does not represent normal
  racing pace.
- A race includes safety-car, virtual-safety-car, red-flag, wet-weather, or
  otherwise disrupted periods without the additional data categories deferred
  from this feature.
- A driver retires, is lapped, starts from the pit lane, or completes very few
  racing laps.
- Two drivers have equal median pace at the published precision.
- A requested driver number is malformed or is well-formed but absent from the
  supported session.
- The supported session is available but its lap data is missing or incomplete.
- The external source or repository-local cache is unavailable.
- Repeated requests observe the same source snapshot but arrive in a different
  input order.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST calculate lap and pace results from authoritative
  FastF1 source data and MUST NOT use a language model, predictive model,
  inference, or fabrication to produce race facts.
- **FR-002**: The system MUST preserve the 2025 Italian Grand Prix Race at
  Monza as the guaranteed control dataset while retaining season, event, and
  session concepts for later expansion.
- **FR-003**: An analyst MUST be able to retrieve lap-level classification and
  overall representative pace information for a driver participating in the
  supported session.
- **FR-004**: Analytics requests MUST select drivers by their source-backed
  `driver_number`. Driver identity in results MUST use `driver_number` as its
  canonical identifier and MAY include abbreviation and name only as
  descriptive fields.
- **FR-005**: The source-lap count MUST include every loaded lap row associated
  with the selected driver before representative-lap filtering.
- **FR-006**: Every source lap considered MUST be classified exactly once as
  representative or excluded, and every excluded lap MUST have one documented
  primary exclusion reason so the source-lap count equals representative laps
  plus excluded laps.
- **FR-007**: The representative-lap policy MUST exclude Lap 1, laps without a
  usable lap time, non-positive or non-finite lap times, pit-in laps, and
  pit-out laps. A usable normalized lap duration MUST be at least 500,000 ns;
  any smaller duration, including a positive one, MUST be `invalid_timing`.
  Exactly 500,000 ns passes timing validity and publishes as 1 ms.
- **FR-008**: Before implementation is accepted, the representative-lap policy
  MUST explicitly define and justify its treatment of anomalously slow laps,
  source accuracy indicators, track-status conditions, disrupted race periods,
  overlapping exclusion conditions, and the minimum valid sample size.
- **FR-009**: A lap MUST NOT be excluded solely because the source could not
  perform or confirm an accuracy check unless documented research demonstrates
  that the flag reliably indicates unusable timing rather than unavailable
  validation.
- **FR-010**: Representative-lap analysis MUST NOT depend on telemetry,
  weather, race-control messages, fuel correction, traffic correction, or
  predictive estimates for this feature. Dry, intermediate, and wet laps MUST
  remain eligible when they pass all other representative-lap rules, and
  results MUST disclose that pace is not adjusted for track conditions.
- **FR-011**: The same documented filter policy and metric definitions MUST be
  applied to every driver in an analysis and every driver comparison.
- **FR-012**: Each valid driver pace summary MUST report the median, arithmetic
  mean, fastest value, and population standard deviation across representative
  laps.
- **FR-013**: Median representative lap time MUST be the primary overall
  race-pace metric for ranking and comparison in this feature.
- **FR-014**: Pace calculations MUST use source-duration precision without
  pre-rounding. Published lap durations, pace metrics, consistency values, and
  deltas MUST be integer milliseconds rounded to the nearest millisecond using
  half-up rounding. Pace metrics MUST be available only when a driver has at
  least five representative laps. Published lap durations, median, mean, and
  fastest values MUST be at least 1 ms without clamping rounded values.
  Population standard deviation and pace deltas MAY legitimately be zero.
- **FR-015**: All returned numeric values MUST be finite and safe to represent;
  unavailable values MUST be expressed explicitly rather than as NaN,
  infinity, or a fabricated number.
- **FR-016**: Each valid driver summary MUST include a pace delta to the best
  valid representative driver pace in the same session snapshot, calculated as
  that driver's published median minus the lowest eligible published median.
  This delta MUST be non-negative, and the best driver's delta MUST be zero.
  Determining that reference MUST evaluate every session participant with
  loaded lap data under the same policy.
- **FR-017**: A two-driver comparison MUST calculate its signed delta as Driver
  A's median representative lap time minus Driver B's. A positive value means
  Driver A was slower, a negative value means Driver A was faster, and zero
  means their published median pace was equal. The delta MUST be derived from
  the two published median values.
- **FR-018**: Driver comparisons MUST calculate both drivers from the same
  session snapshot and MUST expose each driver's source and representative
  sample counts. Each analysis operation MUST load its FastF1 session/lap
  dataset once, derive one shared session-field analysis, and reuse that
  analysis for individual summaries and comparisons rather than independently
  reloading either driver.
- **FR-019**: The session pace result MUST order eligible drivers from fastest
  to slowest by published median representative lap time. Drivers with equal
  published medians MUST be reported as tied and ordered for display by
  ascending numeric `driver_number`.
- **FR-020**: Drivers without enough representative laps MUST remain
  distinguishable from unknown drivers and from source outages; they MUST NOT
  receive a rank, winner designation, or invented pace metric.
- **FR-021**: Results MUST identify the applied filtering policy and provide
  exclusion counts by primary reason, including a total excluded-lap count.
- **FR-022**: Lap-level results MUST be deterministically ordered and MUST
  expose each lap's inclusion decision, usable lap time when present, and
  primary exclusion reason when excluded.
- **FR-023**: All analytics results MUST identify FastF1 as their source and
  preserve the represented season, event, and session identity.
- **FR-024**: All analytics responses MUST follow explicit strict contracts
  that reject unexpected fields.
- **FR-025**: Analytics resources MUST be versioned and nested beneath the
  existing season, event, and session resource hierarchy; their exact resource
  design will be finalized during planning.
- **FR-026**: Malformed inputs, unsupported sessions, unknown drivers, expected
  source failures, and unexpected internal failures MUST remain distinguishable
  through stable error behavior consistent with the existing backend boundary.
- **FR-027**: Repeated analysis of the same source snapshot with the same inputs
  and policy MUST produce identical classifications, metrics, rankings, and
  comparisons.
- **FR-028**: Routine automated validation MUST cover filtering, metrics,
  comparison arithmetic, ordering, insufficient data, and error behavior
  without contacting the live Formula 1 source.
- **FR-029**: Real-source validation MUST remain separately identified and
  explicitly opted in.
- **FR-030**: Existing health and session-summary behavior MUST remain
  compatible and independently usable.
- **FR-031**: Generated cache and local data MUST remain outside version
  control.

### Scope Boundaries

This feature includes source lap retrieval, explainable representative-lap
classification, overall driver pace summaries, session pace ordering, and
two-driver comparison.

It excludes tire-degradation modeling, stint-adjusted pace, fuel correction,
traffic correction, strategy simulation, predictive modeling, generated
explanations, frontend visualization, persistence, authentication, deployment,
containerization, and live telemetry analysis.

### Key Entities

- **Session Context**: The represented season, event, and race session plus its
  approved source provenance.
- **Driver Identity**: A participant identified canonically by the
  source-backed driver number, with optional source-backed abbreviation and
  name as descriptive fields.
- **Source Lap**: One loaded lap row associated with a driver before filtering,
  including its lap number, usable timing value when present, and policy-relevant
  source indicators.
- **Lap Classification**: The representative or excluded decision for a source
  lap, with a primary exclusion reason when excluded.
- **Filtering Policy**: The named, documented set of eligibility rules,
  precedence rules, sample threshold, units, precision, and rounding behavior
  applied uniformly to every driver.
- **Driver Pace Summary**: Driver identity, sample accounting, primary and
  supporting pace metrics, consistency, exclusions, availability state, and
  delta to the best eligible session pace.
- **Driver Pace Comparison**: Two driver summaries from the same snapshot, the
  signed median difference, and the resulting faster/slower/tied outcome when
  both summaries are valid.
- **Session Pace Result**: The stable ordering of valid driver pace summaries,
  including unavailable participants without fabricated ranks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the Monza control race, an analyst can identify the driver
  with the strongest eligible representative overall pace and inspect the
  evidence used for that result.
- **SC-002**: For any two eligible control-race drivers, an analyst can obtain a
  comparison whose signed difference exactly equals Driver A's published
  median minus Driver B's published median.
- **SC-003**: One hundred percent of source laps considered for a driver are
  accounted for as either representative or excluded, and every excluded lap
  has a primary reason.
- **SC-004**: One hundred percent of valid driver summaries include source and
  representative sample counts, median, mean, fastest lap, consistency, delta
  to best, policy identity, exclusion totals, and source provenance.
- **SC-005**: Controlled validation demonstrates that Lap 1, missing timing,
  non-finite timing, durations below 500,000 ns (including non-positive values),
  pit-in laps, and pit-out laps never affect the published representative pace
  metrics. It verifies the explicit timing boundaries in Edge Cases and that
  eligible median, mean, and fastest values cannot publish as 0 ms.
- **SC-006**: Repeated analyses of an unchanged source snapshot produce exactly
  the same lap classifications, metric values, ordering, and comparison result.
- **SC-007**: Every published numeric analytics value is finite, and every
  unavailable result is represented explicitly without a fabricated number.
- **SC-008**: A reviewer can determine from the result why each excluded lap
  was excluded and reconcile the representative and excluded counts with the
  source-lap count.
- **SC-009**: Routine automated validation completes with zero live source
  requests, while a separately opted-in validation can verify the real Monza
  control data path.
- **SC-010**: Existing backend availability and session-summary scenarios
  continue to produce their established results after this feature is added.

## Assumptions

- This part analyzes race sessions and does not define representative pace for
  qualifying, sprint qualifying, or practice sessions.
- The 2025 Italian Grand Prix Race remains the only guaranteed session; the
  resource vocabulary stays generic so support can expand later.
- A supported driver is a participant identifiable from the represented
  session's authoritative results and lap data.
- Source-lap count refers to loaded lap rows matched to that driver before any
  pace filter is applied.
- Exclusion reasons use documented precedence so each excluded lap has one
  primary reason even when multiple conditions apply; additional diagnostic
  reasons may be provided without affecting count reconciliation.
- Median representative lap time is the initial primary metric because it is
  less sensitive to extreme values than the arithmetic mean.
- Overall race pace includes otherwise eligible dry, intermediate, and wet
  laps and is explicitly unadjusted for differences in track conditions.
- The exact slow-lap threshold, track-status treatment, source-accuracy
  treatment, and overlapping-exclusion precedence are research decisions for
  planning and must be reflected in the final accepted policy and contracts.
- Existing application-owned source loading, repository-local caching, error
  distinctions, and explicit real-data opt-in remain available to this feature.
- An analysis operation uses one loaded session/lap snapshot as the common
  basis for field ranking, individual summaries, and driver comparisons.
