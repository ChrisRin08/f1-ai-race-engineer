# Phase 0 Research: Lap Data & Driver Pace

This research resolves the remaining planning decisions against the clarified
feature specification, the current backend, and the installed FastF1 3.8.3
source. It does not claim that the selected v1 pace policy is a universal
motorsport standard.

## Existing Loader Extension

**Decision**: Extract a reusable `load_session(...)` function inside
`f1_data.py`. Keep the existing `load_session_summary(...)` signature and
behavior as a wrapper that calls the loader once and maps the returned session.
Analytics operations call the same loader once, then map summary context and
normalized lap inputs from that shared object.

**Rationale**: The current function already centralizes repository-local cache
configuration, `fastf1.get_session`, selective loading, and narrow expected
error translation. Extraction creates the needed reuse without duplicating
source orchestration or changing the existing endpoint contract.

**Alternatives considered**: Loading independently for summary and analytics
would violate the shared-snapshot requirement. Returning only
`SessionSummary` discards laps. A repository/service framework would add
indirection without persistence or multiple providers to justify it.

## Normalized Source Boundary

**Decision**: Map FastF1/Pandas rows in `f1_data.py` to immutable,
application-owned lap inputs containing source order, driver number, normalized
lap number, lap duration in integer nanoseconds, pit-presence flags,
TrackStatus codes, and nullable `IsAccurate`. The pure analytics module does
not import FastF1 or Pandas. Reject noncanonical or duplicate result driver
numbers and any lap row that cannot map to the authoritative result roster.

**Rationale**: FastF1 3.8.3 declares `LapTime`, `PitInTime`, and `PitOutTime` as
timedelta-like columns, `LapNumber` as floating point, `DriverNumber` and
`TrackStatus` as strings, and `IsAccurate` as boolean. Normalizing once isolates
provider missing-value behavior and gives tests a small deterministic input.

**Alternatives considered**: Passing a FastF1 `Laps` frame into analytics
would scatter provider column assumptions. Converting directly into API models
would couple calculation state to serialization. Silently dropping an
unattributable lap row would make field accounting incomplete.

Source: [FastF1 3.8.3 `Laps` source](https://github.com/theOehrly/Fast-F1/blob/v3.8.3/fastf1/core.py)

## TrackStatus Loading and Multi-Code Semantics

**Decision**: Use lap-level `TrackStatus` without enabling race-control
messages. Treat the value as a sequence of unique single-character codes and
exclude a lap when any verified disruptive code is present: `2` yellow, `4`
Safety Car, `5` red flag, `6` Virtual Safety Car, or `7` VSC ending. Preserve
the observed codes as diagnostics and use presence testing rather than string
equality.

**Rationale**: In FastF1 3.8.3, `Session.load(laps=True, ...)` loads session
status, total-lap count, track status, and lap timing before considering the
separate `messages` flag. FastF1 builds each lap's `TrackStatus` by appending
every unique status that overlaps its time span. Its public lap selector offers
`contains` and `any` modes specifically because values can contain multiple
codes.

**Alternatives considered**: Equality with one code misses laps such as `12`
or `26`. Race-control messages and telemetry are unnecessary for identifying
lap overlap and are explicitly out of scope. Estimating time lost within a lap
is not supported by this lap-aggregated field.

Sources: [FastF1 3.8.3 session loading and lap status mapping](https://github.com/theOehrly/Fast-F1/blob/v3.8.3/fastf1/core.py),
[FastF1 3.8.3 track-status API](https://github.com/theOehrly/Fast-F1/blob/v3.8.3/fastf1/_api.py)

## Unknown or Missing Track Status

**Decision**: Absence of the required `TrackStatus` column makes the analytics
dataset unavailable. A missing/empty value on an individual row is retained as
diagnostic absence and does not fabricate either a clear or disruptive state.
Only verified disruptive-code presence triggers `disrupted_status`. Raw codes
retain first-observed source order, while normalized disruption values use the
fixed public policy order. The undocumented code `3` and any future unknown
code remain visible diagnostics but do not receive invented semantics.

**Rationale**: FastF1 3.8.3 documents `3` as unknown and its status-loading
helpers are soft-failing. Treating unknown data as a verified flag would
fabricate a fact; excluding it under a named regulatory reason would also be
misleading. Requiring the column catches a broad source-shape failure while
allowing isolated uncertainty to remain explicit.

**Alternatives considered**: Treating missing values as all-clear hides source
uncertainty. Treating them as disrupted invents a regulatory state. Failing the
entire operation for one empty row is disproportionate when every lap still
has an explicit diagnostic value.

## `IsAccurate` Policy

**Decision**: Do not use `IsAccurate` in lap eligibility. Normalize it as
nullable source diagnostic metadata and expose it on lap classifications.

**Rationale**: FastF1's 3.8.3 check requires more than aggregate `LapTime`: no
pit markers, no generated lap, a narrow TrackStatus set, all three sector
times, sector-sum agreement, previous-lap conditions, and timeline agreement.
Failures therefore do not prove that a finite aggregate lap duration is
unusable for this v1 metric. The function is also wrapped in FastF1's soft
exception handling, and the validated Monza run showed that verification can
fail for a driver.

**Alternatives considered**: Requiring `True` would silently remove usable
samples for reasons outside the feature's aggregate timing question. Ignoring
the field entirely would lose useful provenance diagnostics.

Source: [FastF1 3.8.3 lap accuracy check](https://github.com/theOehrly/Fast-F1/blob/v3.8.3/fastf1/core.py)

## Primary Exclusion Precedence

The source normalization minimum is 500,000 ns, as resolved below. A smaller
duration is unusable timing, not an anomalous-pace decision.

**Decision**: Use first-match precedence:

1. `invalid_timing`
2. `lap_one_start`
3. `pit_in`
4. `pit_out`
5. `disrupted_status`
6. `anomalous_pace`

`invalid_timing` means that a lap record lacks the minimum valid timing
identity required for deterministic pace analysis. It includes an unusable
`LapTime` or an unusable `LapNumber`, because the system cannot calculate pace,
safely evaluate Lap 1, or publish deterministic lap evidence without those
values. Any non-null pit marker counts as present; when both are present,
`pit_in` wins. Multiple disruptive codes still produce one
`disrupted_status` primary reason.

**Rationale**: Structural validity must precede semantic filtering. Start and
pit events are direct lap facts. Regulatory disruption must be removed before
the driver's anomaly reference is calculated. One primary reason makes counts
reconcile while retained diagnostics preserve additional evidence.

**Alternatives considered**: Multiple counted reasons break reconciliation.
Running anomaly detection first lets known slow structural laps distort their
own reference. Adding more public exclusion categories is unnecessary for the
validated v1 policy.

## Driver-Relative Slow-Lap Heuristic

**Decision**: After rules 1-5, find each driver's fastest remaining lap and
exclude a lap only when it is strictly greater than 120% of that reference.
Compare integer nanoseconds exactly as `lap_ns * 5 > fastest_ns * 6`; equality
at 120% remains representative.

**Rationale**: The specified 120% threshold is deliberately conservative and
driver-relative. Exact integer comparison avoids floating-point boundary drift.
FastF1's `pick_quicklaps()` instead defaults to a selection-wide 107% threshold
and keeps values strictly below its threshold, which is a different metric and
would prune normal race variation more aggressively.

**Alternatives considered**: `pick_quicklaps()` and global-fastest thresholds
do not match the feature meaning. Distribution-based, stint-aware, compound-
aware, fuel-corrected, and traffic-aware methods belong to later analytics.

Source: [FastF1 3.8.3 `pick_quicklaps`](https://github.com/theOehrly/Fast-F1/blob/v3.8.3/fastf1/core.py)

## Mixed Conditions

**Decision**: Do not filter on `Compound`. Dry, intermediate, wet, unknown, or
missing compound values are evaluated by the same policy. Every response
exposes `track_conditions_adjusted: false`. The v1 120% anomaly rule is not
condition-aware, so a legitimate lap in substantially slower conditions can
still exceed the driver-relative threshold and receive `anomalous_pace`.

**Rationale**: The clarified feature is an overall, unadjusted race metric and
does not load weather or segment by condition. Compound never excludes a lap
by itself, but compound eligibility cannot guarantee survival of the separate
anomaly rule. This limitation must be explicit because drivers can experience
different condition mixes.

**Alternatives considered**: Dry-only output would change the agreed metric.
Condition buckets, normalization, or a condition-aware anomaly threshold would
expand Part 1 into later policy work.

## Metric Calculation and Publication

**Timing-validity resolution**: A normalized duration must be at least
500,000 ns to be usable. Values below that minimum become null at the source
boundary and receive the existing `invalid_timing` classification; their lap
rows remain counted. Exactly 500,000 ns is usable timing and publishes as 1 ms.

This is a representation boundary, not a claim about a physically plausible
Formula 1 lap time. Positive values below 500,000 ns round to 0 ms using
`ROUND_HALF_UP`, which violates the positive public lap-duration contract.
Clamping 0 ms to 1 ms would change the rounding rule; allowing public 0 ms
lap durations would weaken the approved contract. Neither is permitted.

Controlled expectations: 0 ns, any negative duration, 1 ns, and 499,999 ns
are `invalid_timing`; 500,000 ns and 500,001 ns are valid timing inputs and
both publish as 1 ms. Passing timing validity does not bypass the other rules.

**Decision**: Calculate median, arithmetic mean, fastest, and population
standard deviation from unrounded integer-nanosecond durations. Use exact
integer sums and decimal arithmetic in an explicit local context of at least
50 digits, then publish each duration as an integer millisecond using
`ROUND_HALF_UP`. Calculate published deltas from published medians.

**Rationale**: Integer source units avoid binary-float conversion before
aggregation. Population standard deviation describes the complete selected lap
sample rather than estimating a larger unseen population. Half-up rounding is
explicit and stable, and published-value deltas guarantee arithmetic visible
to clients.

For every non-empty representative sample, each duration is at least
500,000 ns. Its minimum and arithmetic mean therefore cannot be smaller;
neither can its median (including the average of two middle values). Thus all
three publish as at least 1 ms without clamping. Population standard deviation
measures spread, not lap duration: equal durations yield 0 ms, which remains
valid under its non-negative contract. Deltas likewise may be zero.

**Alternatives considered**: Binary floats can create boundary and serialization
surprises. Sample standard deviation does not match the clarified metric.
Ranking unrounded values while showing rounded values could report two visible
equals as analytically different.

Source: [Python `decimal` rounding modes](https://docs.python.org/3/library/decimal.html)

## Eligibility, Ranking, and Ties

**Decision**: Publish pace metrics only with at least five representative laps.
Rank eligible drivers by published median milliseconds with competition ranks
(`1, 1, 3`). Equal published medians are analytical ties; numeric driver number
orders tied rows only. Insufficient drivers follow eligible drivers in numeric
driver-number order without rank or delta.

**Rationale**: This implements the clarified threshold and keeps displayed
ordering deterministic without using identity to invent a performance
distinction. Competition ranking communicates skipped positions after a tie.

**Alternatives considered**: Dense ranking (`1, 1, 2`) is deterministic but
less directly communicates the tied positions. Ordinal ranking would contradict
the analytical tie.

## Driver Identity and Comparison

**Decision**: Accept canonical positive decimal driver-number paths matching
`^[1-9][0-9]*$`; do not accept leading zeros or abbreviations. Allow comparing
a driver with the same driver number, yielding a zero delta and tied result.

**Rationale**: Existing results require a non-empty source driver number, while
abbreviation is optional. Canonical decimal syntax makes numeric ordering and
identity unambiguous. Same-driver comparison follows the same arithmetic and
needs no special error.

**Alternatives considered**: Accepting number and abbreviation creates alias
resolution and ambiguity. Rejecting same-driver comparison adds a special case
without preventing an invalid fact.

## API Resources and Error Boundary

**Decision**: Add three GET resources beneath the existing session:

- `/pace` for compact field summaries;
- `/pace/drivers/{driver_number}` for one summary and lap evidence;
- `/pace/drivers/{driver_a}/comparisons/{driver_b}` for directional A-minus-B
  comparison.

Malformed paths return `422`; unsupported sessions return the existing
`404 session_not_supported` before loading; an absent source-backed driver
returns `404 driver_not_found` after one operation load; known insufficient
drivers return `200`; expected source/data failures return the existing
`503 data_source_unavailable`; unexpected defects remain `500`.

**Rationale**: The payloads have genuinely different scopes. All share one
application operation and response vocabulary, and the comparison path makes
operand order explicit. The error mapping extends the current philosophy
without changing established behavior.

**Alternatives considered**: One response containing every lap for every driver
is unnecessarily large for field ranking. Optional query parameters that
change response type weaken contract clarity. A separate top-level analytics
API would break the established resource hierarchy.

## Known Insufficiency Versus Source Failure

**Decision**: A participant present in results but with fewer than five
representative laps receives a successful `insufficient_data` summary with all
counts and classifications available to that resource. A missing/empty session
lap table, missing required lap columns, or a table with no valid
participant-linked timing anywhere is a source failure (`503`).

**Rationale**: Driver retirement or a small sample is an honest analytical
outcome. A dataset that cannot support any analysis is an upstream availability
problem, not twenty independent driver conclusions.

**Alternatives considered**: Returning `404` for insufficient data would
misstate participant identity. Returning all-insufficient for an absent lap
dataset would hide a source failure.

## Testing and Real-Source Validation

**Decision**: Put policy and arithmetic coverage in pure unit tests using
immutable controlled inputs. Test FastF1 normalization with controlled Pandas
frames, application orchestration with mocks, and HTTP semantics through
`TestClient`. Keep the existing autouse FastF1 source blocker. Extend the
integration-marked validation to the application-owned pace operation for the
2025 Italian Grand Prix Race.

**Rationale**: This isolates deterministic business rules from provider and
network variability while preserving one explicit proof of the real path.

**Alternatives considered**: Real data in routine tests is slow and flaky.
Testing only API responses would make exclusion and boundary cases difficult to
pinpoint. Testing only pure functions would leave loader and contract seams
unverified.

## Dependency and Scale Decision

**Decision**: Add no dependency and no cross-request cache. Keep synchronous
routes, FastF1's repository-local disk cache, and O(L log L) field analysis.

**Rationale**: FastF1 already brings Pandas and NumPy, while Python's standard
library is sufficient for the exact policy. A Formula 1 race contains a small,
bounded field and lap table. FastAPI already executes synchronous handlers away
from the event loop.

**Alternatives considered**: SciPy is transitively installed but unnecessary
as an application dependency. Background jobs, Redis, databases, and
microservices would solve scale and lifecycle problems this feature does not
have.

## Resolved Unknowns

All planning unknowns are resolved. The v1 limitation is explicit: lap-level
TrackStatus proves only that a state overlapped a lap; it cannot quantify time
loss, and unknown/missing status values cannot be assigned invented meanings.
The 120% rule remains a versioned baseline heuristic, not a universal Formula 1
standard. It can classify legitimate substantially slower-condition laps as
anomalous until a future condition-aware policy version is introduced.
