# Data Model: Tire Stints & Observed Degradation Analytics

## Internal Normalized Input

### SourceLap extension

The existing frozen `lap_analytics.SourceLap` remains the single normalized lap
record. Feature 003 appends these defaulted fields:

| Field | Type | Source | Rule |
|---|---|---|---|
| `stint` | `int | None` | FastF1 `Stint` | Positive integral value or null; null is unassigned and never inferred |
| `tyre_life` | `int | None` | FastF1 `TyreLife` | Positive integral reported age or null; null is unusable for a trend |
| `provider_generated` | `bool | None` | FastF1 `FastF1Generated` | Explicit true excludes; false passes; null is neutral |

Existing fields used by Feature 003 are `source_order`, `driver_number`,
`lap_number`, `lap_time_ns`, `pit_in`, `pit_out`, `track_status_codes`,
`is_accurate`, and `compound`. `source_order` remains available for Feature 002
compatibility and provider diagnostics. Feature 003 does not publish it or use
it for chronology, grouping, canonical selection, or output ordering.

## Pure Analytical Entities

### StintAnalysisPolicy

A frozen policy value with:

- `policy_id = observed-tire-stint-pace-trend-v1`
- `metric = observed_pace_trend_seconds_per_lap`
- `estimator = theil_sen`
- `intercept_method = joint`
- `minimum_eligible_observations = 6`
- `minimum_distinct_tire_ages = 6`
- `tire_age_axis = reported_tire_age_laps`
- `publication_unit = seconds_per_lap`
- `publication_decimal_places = 3`
- `rounding = half_up`
- eligible compounds `SOFT`, `MEDIUM`, `HARD`
- wet-weather compounds `INTERMEDIATE`, `WET`
- ordered lap-exclusion and stint-availability policies

### StintLapExclusionReason

Exact values, in first-match order:

1. `invalid_timing`
2. `lap_one_start`
3. `pit_in`
4. `pit_out`
5. `disrupted_status`
6. `explicitly_inaccurate`
7. `provider_generated`
8. `unusable_tire_age`

This is a Feature 003 enum. Feature 002's `LapExclusionReason` remains unchanged
and retains `anomalous_pace` only in its own six-rule policy.

### StintAnalysisStatus

- `available`
- `unavailable`

### StintUnavailabilityReason

Exact serialized values:

- `inconsistent_stint_metadata`
- `wet_weather_compound`
- `missing_compound`
- `unsupported_compound`
- `inconsistent_tire_age`
- `missing_tire_age`
- `insufficient_eligible_sample`

`missing_tire_age` is the public label for unavailable/unusable normalized
reported tire age. It covers both an absent source value and a malformed source
value normalized to `None`; it remains aligned with the lap-level
`unusable_tire_age` reason and does not imply that the provider cell was
literally empty.

### UnassignedLapReason

- `missing_stint_metadata`

This covers absent or unusable reported stint identifiers without inventing a
new distinction unsupported by the normalized contract.

### StintLapDecision

| Field | Type | Rule |
|---|---|---|
| `lap` | `SourceLap` | Original immutable normalized row |
| `disposition` | `eligible | excluded | unassigned` | Exactly one state |
| `reported_stint` | `int | None` | Non-null for assigned states; null for unassigned |
| `primary_exclusion_reason` | `StintLapExclusionReason | None` | Required only for excluded |
| `unassigned_reason` | `UnassignedLapReason | None` | Required only for unassigned |
| `disruptive_statuses` | tuple | Shared normalized diagnostics |

State invariants:

- eligible: reported stint present, both reasons null;
- excluded: reported stint present, exclusion reason present, unassigned reason
  null;
- unassigned: reported stint null, exclusion reason null, unassigned reason
  present.

### StintSample

| Field | Type | Validation |
|---|---|---|
| `total_lap_count` | non-negative integer | All rows assigned to this stint |
| `eligible_observation_count` | non-negative integer | Assigned rows that passed all lap-level rules; an inconsistent stint is still blocked before any such row reaches the estimator |
| `excluded_observation_count` | non-negative integer | Has one lap exclusion reason |
| `exclusions` | fixed reason-count object | One non-negative count per reason |
| `distinct_eligible_tire_age_count` | non-negative integer | Distinct x values after lap exclusions |

```text
total_lap_count = eligible_observation_count + excluded_observation_count
excluded_observation_count = sum(exclusions.*)
```

### ObservedStintAnalysis

| Field | Type | Meaning |
|---|---|---|
| `driver_number` | canonical string | Authoritative results participant |
| `reported_stint` | positive integer | Source identity; never renumbered |
| `reported_compound` | string or null | Canonical case-preserved source value selected by valid lap number with null last, then lexical token order |
| `normalized_compound` | `SOFT | MEDIUM | HARD | INTERMEDIATE | WET | null` | Recognized uppercase value only |
| `lap_range` | range or null | Minimum/maximum valid assigned lap number |
| `reported_tire_age_range` | range or null | Minimum/maximum valid assigned source age |
| `eligible_tire_age_range` | range or null | Minimum/maximum eligible source age |
| `sample` | `StintSample` | Reconciled counts |
| `status` | `StintAnalysisStatus` | Available or unavailable |
| `unavailability_reason` | enum or null | Exactly one when unavailable |
| `observed_pace_trend_seconds_per_lap` | finite number or null | Signed published Theil-Sen slope |
| `median_absolute_residual_seconds` | finite non-negative number or null | Published robust residual |

Availability invariants:

- available: supported slick, consistent metadata/age, at least six eligible
  distinct ages, reason null, and both metrics present;
- unavailable: one primary reason and both metrics null;
- a numerical zero trend is available and distinct from unavailable;
- published metrics are multiples of 0.001 seconds after half-up quantization.

### DriverStintAnalysis

One authoritative `DriverIdentity`, ordered `ObservedStintAnalysis` values,
ordered `StintLapDecision` evidence, and `unassigned_lap_count`.

```text
len(lap decisions)
  = sum(stint.sample.total_lap_count) + unassigned_lap_count
```

Every source row belongs to exactly one assigned stint or the unassigned set.
For an identified stint blocked by duplicate identity, ordinary lap-level counts
remain auditable row counts; none of its otherwise eligible rows is treated as a
valid trend observation or passed to the estimator.

### SessionStintAnalysis

One ordered `DriverStintAnalysis` per authoritative results participant. Pure
analysis retains complete evidence; the service selects compact or detailed
public projection without re-analysis.

## Construction Rules

1. Group normalized rows only under authoritative results participants.
2. Canonically order evidence by authoritative driver identity, valid lap number
   with null last, reported stint with null last, reported tire age with null
   last, exact duration with null last, case-preserved compound with null last,
   pit flags, normalized track-status codes, `is_accurate`, and
   `provider_generated`. Nullable booleans and values use explicit fixed ranks.
   Never use source row position.
3. A duplicate identity is more than one normalized row for one authoritative
   driver and valid lap number. Retain every row and mark every identified stint
   represented on those rows inconsistent. This includes one-ID, cross-ID, and
   identified-plus-unassigned groups. A duplicate group containing only
   unassigned rows remains unassigned and creates no stint.
4. Assign each positive integral reported stint ID to one group. Put every null
   ID in unassigned evidence.
5. In valid-lap chronology, verify each ID occupies one continuous block. An
   intervening different or unassigned ID invalidates a later reappearance.
6. Validate present compound keys across all assigned rows. More than one key is
   inconsistent stint metadata.
7. Apply lap exclusions in the fixed order and retain each row once. Duplicate
   assigned rows contribute individually to total and ordinary eligible/excluded
   row counts; duplicate unassigned rows contribute individually to the
   unassigned count. Because affected identified stints are already inconsistent,
   none of their rows enters age validation or estimation.
8. Validate increasing ages among eligible rows only after all higher-precedence
   stint metadata checks pass.
9. Select the primary stint outcome by the fixed decision tree.
10. Fit and publish the line only for available stints.

## Availability State Flow

```text
identified stint
  -> contradictory continuity, duplicate chronology, or compound keys?
       inconsistent_stint_metadata
  -> sole present recognized compound is INTERMEDIATE/WET?
       wet_weather_compound
  -> assigned compound missing?
       missing_compound
  -> sole present compound not SOFT/MEDIUM/HARD?
       unsupported_compound
  -> eligible valid ages repeat or decrease?
       inconsistent_tire_age
  -> eligible count < 6 and restoring only unavailable/unusable normalized-age
     rows reaches 6?
       missing_tire_age
  -> eligible count < 6?
       insufficient_eligible_sample
  -> available -> calculate both metrics
```

If a wet value and missing compound observations coexist without conflicting
present keys, wet wins under the specified precedence. Within the compound tier,
missing wins for a mixture of missing and one unsupported present key; this is a
deterministic tie rule, not a claim that one semantic outcome is more important.
Here `missing_tire_age` covers absent or malformed/unusable source values mapped
to normalized `tyre_life = None`; no separate malformed-age reason exists.

## Public Contract Models

All models inherit `ContractModel`, forbid extra fields, and require nullable
fields to be present.

### ObservedTireStintPolicy

Public immutable form of `StintAnalysisPolicy`, including method, joint
intercept, sample minimums, eligible/wet compounds, publication precision,
ordered exclusion values, and six ordered availability tiers. The compound tier
is an unordered two-member set containing `missing_compound` and
`unsupported_compound`, so the contract does not assign precedence between
them.

### ObservationalLimitations

| Field | Value |
|---|---|
| `interpretation` | `observational_association` |
| `isolated_physical_tire_wear` | `false` |
| `unadjusted_for` | fixed ordered list of six limitation identifiers |
| `description` | fixed human-readable non-causal statement |

Limitation identifiers:

1. `fuel_load_or_burn`
2. `traffic`
3. `track_evolution`
4. `driver_tire_management`
5. `changing_environmental_conditions`
6. `other_unmodeled_race_effects`

### ObservedStintSummary

Public form of `ObservedStintAnalysis`, including ranges, sample, status/reason,
and nullable trend/residual. It carries `driver_number` even when nested so each
stint summary independently satisfies its identity contract.

### DriverTireStintSummary

| Field | Type |
|---|---|
| `driver` | existing `AnalyticsDriverIdentity` |
| `stints` | ordered `ObservedStintSummary` array |
| `unassigned_lap_count` | non-negative integer |

### TireStintLapEvidence

Public form of `StintLapDecision` plus the existing half-up `lap_time_ms`
display, reported compound/age, status, pit, accuracy, and provider-generation
diagnostics. `source_order` is omitted and never controls Feature 003 ordering.
The public list follows the normalized-fact canonical key. Records identical
under every canonical fact produce identical evidence objects; all copies remain
in the list, so permuting those indistinguishable rows cannot change serialized
content. The displayed milliseconds do not feed the estimator, which uses the
exact internal `lap_time_ns`.

### SessionTireStintAnalysisResponse

| Field | Type |
|---|---|
| `context` | existing `AnalyticsSessionContext` |
| `policy` | `ObservedTireStintPolicy` |
| `limitations` | `ObservationalLimitations` |
| `drivers` | `DriverTireStintSummary[]` |
| `source` | existing `SourceProvenance` |

No lap-evidence array appears in this response.

### DriverTireStintAnalysisResponse

| Field | Type |
|---|---|
| `context` | existing `AnalyticsSessionContext` |
| `policy` | `ObservedTireStintPolicy` |
| `limitations` | `ObservationalLimitations` |
| `driver` | `DriverTireStintSummary` |
| `laps` | `TireStintLapEvidence[]` |
| `source` | existing `SourceProvenance` |

The root validator reconciles evidence length, assignments, per-stint sample
counts, exclusion counts, and unassigned count.

## Error Contract

Reuse the existing API behavior:

| Condition | HTTP | Result |
|---|---|---|
| Malformed path selector | 422 | Existing FastAPI validation response; no source load |
| Unsupported well-formed session | 404 | `session_not_supported`; no source load |
| Well-formed driver absent from results | 404 | `driver_not_found` after one analysis |
| Known driver with no available trend | 200 | Explicit stint outcomes or empty arrays |
| Expected cache/provider/required-schema failure | 503 | Sanitized `data_source_unavailable` |
| Unexpected invariant or implementation defect | 500 | Existing framework behavior; no fabricated analytics |
