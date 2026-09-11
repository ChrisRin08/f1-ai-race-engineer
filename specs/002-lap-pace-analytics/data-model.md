# Data Model: Lap Data & Driver Pace

This feature adds no persistence. The model separates normalized internal
analytics records from strict public API contracts. All public objects reject
unexpected fields.

## Session Pace Request

Identifies one session through the existing hierarchy.

| Field | Type | Rules |
|---|---|---|
| `year` | integer | At least 1950; only 2025 is currently supported |
| `event` | string | Lowercase slug; only `italian-grand-prix` is guaranteed |
| `session` | string | Lowercase slug; only `race` is guaranteed |

A well-formed tuple outside the support map is unsupported (`404`), not
malformed. Support resolution occurs before FastF1 access.

## Driver Selector

| Field | Type | Rules |
|---|---|---|
| `driver_number` | string | Canonical positive decimal matching `^[1-9][0-9]*$`; no leading zero |

Comparison paths contain ordered selectors `driver_a` and `driver_b`. Their
order defines the sign of the comparison. A selector may equal the other
selector.

## Internal Loaded Session Snapshot

One application operation owns exactly one loaded FastF1 session object. The
snapshot provides:

- the existing mapped `SessionSummary` context;
- the authoritative participant list from results;
- one normalized source-lap sequence derived from that session's loaded laps.

It is operation-scoped and is not persisted or reused across requests.

## Internal Normalized Source Lap

Immutable input created by `f1_data.py` before deterministic analytics.

| Field | Type | Required | Rules |
|---|---|---|---|
| `source_order` | positive integer | Yes | One-based order in the loaded lap table |
| `driver_number` | string | Yes | Non-empty source value used to associate the row |
| `lap_number` | positive integer or null | Yes | Integral finite source value, otherwise null |
| `lap_time_ns` | integer at least 500,000 or null | Yes | Exact source-duration nanoseconds; missing, malformed, non-finite, or smaller durations become null |
| `pit_in` | boolean | Yes | True when `PitInTime` is non-null |
| `pit_out` | boolean | Yes | True when `PitOutTime` is non-null |
| `track_status_codes` | ordered string array or null | Yes | Unique observed FastF1 single-character codes; null when unavailable |
| `is_accurate` | boolean or null | Yes | Diagnostic only; never an eligibility input |
| `compound` | string or null | Yes | Diagnostic source value; never an eligibility input in v1 |

Required source columns are `DriverNumber`, `LapNumber`, `LapTime`,
`PitInTime`, `PitOutTime`, and `TrackStatus`. A missing required column makes
the session analytics source unavailable. `IsAccurate` and `Compound` remain
optional diagnostics. Result driver numbers must be canonical and unique; each
lap row must map to exactly one result participant or the analytics dataset is
unavailable.

## Representative Race-Pace Policy

Public, versioned policy metadata returned with every analytics response.

| Field | Type | Value |
|---|---|---|
| `policy_id` | string literal | `representative-race-pace-v1` |
| `primary_metric` | string literal | `median` |
| `consistency_metric` | string literal | `population_standard_deviation` |
| `minimum_representative_laps` | integer | `5` |
| `anomalous_pace_threshold_percent` | integer | `120` |
| `anomalous_pace_comparison` | string literal | `strictly_greater_than` |
| `anomalous_pace_reference` | string literal | `driver_fastest_after_structural_status_exclusions` |
| `timing_unit` | string literal | `milliseconds` |
| `rounding` | string literal | `half_up` |
| `ranking_method` | string literal | `competition` |
| `tie_basis` | string literal | `published_median_milliseconds` |
| `tie_display_order` | string literal | `driver_number_ascending_numeric` |
| `is_accurate_used_for_exclusion` | boolean literal | `false` |
| `track_conditions_adjusted` | boolean literal | `false` |
| `exclusion_precedence` | exclusion-reason array | Exact ordered six-value policy |
| `disruptive_track_statuses` | disruption-status array | Exact normalized five-value policy |

The policy object is immutable for v1. A future policy change that alters
classifications or metrics requires a new policy identifier.

`track_conditions_adjusted: false` also means the 120% anomaly rule has no
condition adjustment. Compound never excludes a lap by itself, but a legitimate
lap in substantially slower conditions can still exceed the threshold and be
classified as `anomalous_pace`. Condition-aware anomaly detection requires a
future policy version.

## Exclusion Reason

Serialized lower-snake-case values in precedence order:

1. `invalid_timing`
2. `lap_one_start`
3. `pit_in`
4. `pit_out`
5. `disrupted_status`
6. `anomalous_pace`

`invalid_timing` means the lap record lacks the minimum valid timing identity
required for deterministic pace analysis. It covers an unusable `LapTime` or
an unusable `LapNumber`; both are required to calculate pace, identify Lap 1,
and order lap evidence deterministically. A duration below 500,000 ns is
unusable, even if positive, because it cannot publish as a positive integer
millisecond under half-up rounding. Exactly 500,000 ns passes timing validity.
A lap has at most one primary exclusion reason; unusable durations become null
without dropping the row or changing source counts.

## Disruptive Track Status

Normalized public values and their FastF1 3.8.3 codes:

| Value | Source code |
|---|---|
| `yellow` | `2` |
| `safety_car` | `4` |
| `red_flag` | `5` |
| `virtual_safety_car` | `6` |
| `virtual_safety_car_ending` | `7` |

A lap can contain multiple values. Source code `1` means track clear. Source
code `3` has no verified semantics and is not mapped to a disruption value.
Raw codes retain first-observed source order. Normalized disruption values are
always emitted in the fixed table order above.

## Lap Classification

Public evidence for one source lap in an individual-driver response.

| Field | Type | Required | Validation |
|---|---|---|---|
| `source_order` | positive integer | Yes | Stable tie-break independent of Pandas index |
| `lap_number` | positive integer or null | Yes | Null only for an invalid timing record |
| `lap_time_ms` | positive integer or null | Yes | Half-up published usable duration (at least 500,000 ns); null when unusable; never clamped |
| `classification` | enum | Yes | `representative` or `excluded` |
| `primary_exclusion_reason` | exclusion reason or null | Yes | Null exactly when representative |
| `track_status_codes` | string array or null | Yes | Source diagnostics without invented meaning |
| `disruptive_statuses` | disruption-status array | Yes | Normalized verified statuses, possibly empty |
| `is_accurate` | boolean or null | Yes | Diagnostic only |
| `compound` | string or null | Yes | Diagnostic only; never a direct exclusion criterion |

Lap rows are ordered by valid lap number ascending, then source order. Rows
with invalid lap number follow valid rows in source order.

## Exclusion Counts

Fixed strict object with non-negative integer fields:

- `invalid_timing`
- `lap_one_start`
- `pit_in`
- `pit_out`
- `disrupted_status`
- `anomalous_pace`

All fields are present, including zero values.

## Lap Sample

| Field | Type | Required | Validation |
|---|---|---|---|
| `source_lap_count` | non-negative integer | Yes | Every participant-associated source row before filtering |
| `representative_lap_count` | non-negative integer | Yes | Rows with representative classification |
| `excluded_lap_count` | non-negative integer | Yes | Rows with an exclusion reason |
| `exclusions` | Exclusion Counts | Yes | Counts by primary reason |

Invariants:

```text
source_lap_count = representative_lap_count + excluded_lap_count
excluded_lap_count = sum(exclusions.*)
```

## Pace Metrics

Present only for an available driver.

| Field | Type | Validation |
|---|---|---|
| `median_lap_time_ms` | positive integer | Primary metric, half-up |
| `mean_lap_time_ms` | positive integer | Arithmetic mean, half-up |
| `fastest_lap_time_ms` | positive integer | Minimum representative duration |
| `population_standard_deviation_ms` | non-negative integer | Population standard deviation, half-up |

Calculations use unrounded integer nanoseconds. Publication rounding happens
only after each aggregate is calculated, within an explicit local decimal
context of at least 50 digits.

Every representative duration is at least 500,000 ns. The minimum, median,
and arithmetic mean are therefore each at least 500,000 ns and cannot publish
as 0 ms. Do not clamp publication values. Population standard deviation may
be 0 ms, including for five equal 500,000 ns laps whose other metrics are
all 1 ms. Deltas may also be zero.

Timing-boundary examples (other classification rules still apply):

| Source duration | Timing validity | Published lap duration |
|---|---|---|
| 0 ns | `invalid_timing` | null |
| Negative duration | `invalid_timing` | null |
| 1 ns | `invalid_timing` | null |
| 499,999 ns | `invalid_timing` | null |
| 500,000 ns | Valid timing input | 1 ms |
| 500,001 ns | Valid timing input | 1 ms |

## Analytics Driver Identity

This feature does not tighten or replace the existing session-summary
`Participant` contract.

| Field | Type | Required | Validation |
|---|---|---|---|
| `driver_number` | string | Yes | Canonical positive decimal matching `^[1-9][0-9]*$` |
| `abbreviation` | string or null | Yes | Descriptive source value only |
| `full_name` | string or null | Yes | Descriptive source value only |
| `team_name` | string or null | Yes | Descriptive source value only |

## Driver Pace Summary

Compact summary used in all three analytics responses.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `driver` | Analytics Driver Identity | Yes | Canonical number plus source-backed descriptive identity |
| `status` | enum | Yes | `available` or `insufficient_data` |
| `policy_id` | string | Yes | Policy used for this summary |
| `sample` | Lap Sample | Yes | Reconciled source and exclusion evidence |
| `metrics` | Pace Metrics or null | Yes | Null when insufficient |
| `rank` | positive integer or null | Yes | Competition rank when available |
| `tied` | boolean or null | Yes | Whether another available driver has equal published median |
| `delta_to_best_ms` | non-negative integer or null | Yes | Published median minus best published median |
| `source` | existing Source Provenance | Yes | `FastF1` |

State invariants:

- `available`: representative count is at least five; metrics, rank, tied, and
  delta are non-null.
- `insufficient_data`: representative count is below five; metrics, rank,
  tied, and delta are null.
- All available summaries sharing a published median share one competition
  rank. Driver number changes display order only.

## Analytics Session Context

| Field | Type | Required |
|---|---|---|
| `year` | integer | Yes |
| `event` | existing EventSummary | Yes |
| `session` | existing SessionIdentity | Yes |
| `circuit` | existing CircuitSummary | Yes |

No retrieval timestamp, cache-hit flag, or request identifier is added.

## Session Pace Analysis Response

| Field | Type | Required |
|---|---|---|
| `context` | Analytics Session Context | Yes |
| `policy` | Representative Race-Pace Policy | Yes |
| `drivers` | Driver Pace Summary array | Yes |
| `source` | Source Provenance | Yes |

Available summaries come first in pace order; insufficient summaries follow in
numeric driver-number order. Every results participant appears exactly once.

## Driver Pace Analysis Response

| Field | Type | Required |
|---|---|---|
| `context` | Analytics Session Context | Yes |
| `policy` | Representative Race-Pace Policy | Yes |
| `driver` | Driver Pace Summary | Yes |
| `laps` | Lap Classification array | Yes |
| `source` | Source Provenance | Yes |

The `laps` count equals `driver.sample.source_lap_count`.

## Driver Pace Comparison Result

| Field | Type | Required | Meaning |
|---|---|---|---|
| `status` | enum | Yes | `available` or `insufficient_data` |
| `delta_ms` | integer or null | Yes | Driver A published median minus Driver B |
| `outcome` | enum or null | Yes | `driver_a_faster`, `driver_b_faster`, or `tied` |
| `faster_driver_number` | string or null | Yes | Null for tied or insufficient results |

State invariants:

- `available`: both drivers are available; delta and outcome are non-null.
  Positive means A slower, negative means A faster, zero means tied.
- `insufficient_data`: at least one known driver is insufficient; delta,
  outcome, and faster-driver number are null.
- A tied available result has null `faster_driver_number`.

## Driver Pace Comparison Response

| Field | Type | Required |
|---|---|---|
| `context` | Analytics Session Context | Yes |
| `policy` | Representative Race-Pace Policy | Yes |
| `driver_a` | Driver Pace Summary | Yes |
| `driver_b` | Driver Pace Summary | Yes |
| `comparison` | Driver Pace Comparison Result | Yes |
| `source` | Source Provenance | Yes |

Both summaries and the comparison derive from the same field analysis.

## Error Response and State Flow

Existing `ErrorResponse` remains the custom error shape.

| Condition | HTTP | Code/shape |
|---|---|---|
| Malformed path | 422 | Existing FastAPI validation response |
| Unsupported well-formed session | 404 | `session_not_supported` |
| Well-formed driver absent from results | 404 | `driver_not_found` |
| Known driver below sample minimum | 200 | `insufficient_data` summary |
| Expected FastF1/cache/required-data failure | 503 | `data_source_unavailable` |
| Unexpected internal defect | 500 | Existing framework behavior |

```text
request
  -> malformed path (422, no load)
  -> unsupported session (404, no load)
  -> expected source failure (503)
  -> one shared field analysis
     -> unknown selected driver (404)
     -> known insufficient driver (200, explicit state)
     -> available analytics (200)
```
