# Research: Tire Stints & Observed Degradation Analytics

## Decision 1: Extend the existing normalized session input

**Decision**: Append nullable `stint`, `tyre_life`, and `provider_generated`
fields to the existing `lap_analytics.SourceLap`. Keep `map_lap_inputs()` as the
only lap normalization path and keep every Feature 003 operation on one loaded
session snapshot.

**Rationale**: `SourceLap` already owns driver identity, exact lap duration, lap
number, pit flags, track status, accuracy, and compound. Appending defaulted
fields preserves existing constructors and prevents a second provider model.
FastF1 3.8.3 declares the corresponding lap columns as `Stint` float64,
`TyreLife` float64, and `FastF1Generated` bool. Live acceptance observed NumPy
boolean scalars for `FastF1Generated` and `IsAccurate`; normalization converts
them to Python `bool`. It also observed `RoundNumber` as `numpy.int64`, which is
normalized to Python `int` before strict public validation.

**Alternatives considered**:

- A second tire-lap mapper/model: rejected because it would duplicate source
  loading and normalization rules.
- Moving `SourceLap` into a new shared module: rejected as a broad Feature 002
  refactor with no user-visible benefit.
- Adding `FreshTyre`: rejected because no approved rule consumes it and reported
  tire age already preserves used-tire context.
- Loading race-control messages for `Deleted`: rejected because Feature 003 does
  not require Deleted filtering and the current loader intentionally uses
  `messages=False`.

## Decision 2: Normalize optional tire metadata conservatively

**Decision**: Normalize Stint and TyreLife only when finite, positive, integral,
and non-boolean. Normalize provider-generated and accuracy assertions only from
actual booleans. Preserve a trimmed, case-sensitive compound string. Missing or
malformed optional scalars become `None`; duplicated consumed DataFrame labels
are a source-schema failure.

**Rationale**: This matches existing LapNumber/boolean normalization patterns,
keeps missing quality assertions neutral, and never selects an arbitrary Pandas
column or invents an identifier/age.

**Alternatives considered**:

- Coercing numeric strings or rounding floats: rejected as source repair.
- Making new columns session-required: rejected because missing metadata belongs
  in explicit lap/stint outcomes and would change Feature 002 availability.
- Silently selecting one duplicate column: rejected as nondeterministic source
  interpretation.

## Decision 3: Extract the structural/status classifier only

**Decision**: Extract `classify_structural_status_laps()` from the first pass of
Feature 002's existing classifier. Keep the five current reasons and order in
the existing enum; make `classify_driver_laps()` apply the unchanged 120%
anomaly pass afterward.

**Rationale**: Both features need the same timing/Lap 1/pit/status rules, while
only Feature 002 owns representative-pace anomaly behavior. Reusing the exact
function prevents policy drift without adding Feature 003 enum members to a
published Feature 002 schema.

**Alternatives considered**:

- Copying five rules into `stint_analytics.py`: rejected as forbidden duplication.
- General rule-engine abstraction: rejected as unnecessary complexity.
- Moving or extending `LapExclusionReason`: rejected because it can change
  Feature 002 OpenAPI and interview explainability.

## Decision 4: Construct stints from reported identity and chronology

**Decision**: Group by driver and positive integral reported stint ID, but
validate each ID as one continuous occurrence in lap-number chronology. Missing
or unusable IDs become unassigned evidence. Reappearance after another ID or a
chronologically placed unassigned row makes the reappearing stint inconsistent.
Every normalized row in a duplicate driver/valid-lap-number group is retained.
Each identified stint represented by such a group is contradictory, including
when different rows report different stint IDs or when identified and
unassigned rows coexist. A duplicate group containing only unassigned rows
remains entirely unassigned. Assigned rows still receive their ordinary
lap-level decisions and reconcile in their reported stint counts, but the
metadata blocker prevents every row in an affected stint from reaching tire-age
validation or estimation. Thus duplicates never become multiple valid trend
observations and are never silently deduplicated.

**Rationale**: This uses provider metadata as authoritative while refusing to
split, merge, renumber, or infer uncertain history. It remains independent of
incidental DataFrame row order. Feature 003 orders evidence using a total key of
authoritative driver identity and normalized facts only. `source_order` is not
an ordering input. Rows identical under every normalized fact serialize as
identical evidence objects, so retaining their multiplicity makes their relative
order unobservable.

**Alternatives considered**:

- Inferring stints from pit stops or compound changes: rejected by the spec.
- Splitting a repeated ID into multiple synthetic stints: rejected as repair.
- Requiring stint numbers to increase consecutively: rejected because no
  requirement establishes that provider numbering invariant.

## Decision 5: Keep lap exclusion, unassignment, and stint availability separate

**Decision**: An assigned lap receives exactly one reason in this order:
inherited structural/status, explicitly inaccurate, provider-generated, unusable
tire age, or eligible. An unusable stint ID is unassigned instead of excluded.
Stint-level blockers do not rewrite otherwise eligible lap decisions.

**Rationale**: This makes all three state layers independently auditable and
supports exact source-row and count reconciliation. Missing quality assertions
remain neutral because only explicit false/true assertions trigger their rules.

**Alternatives considered**:

- Treating unassigned rows as excluded stint laps: rejected because no stint may
  be invented.
- Using Feature 002 classifications directly: rejected because they contain the
  prohibited 120% anomaly rule.

## Decision 6: Use reported tire age without repair

**Decision**: Evaluate eligible reported ages in chronological lap order.
Unavailable/unusable normalized age, whether absent in the provider source or
rejected as malformed during normalization, excludes only its row; gaps and
starting ages above one are valid; any repeated or decreasing valid age blocks
the entire stint trend.

**Rationale**: Absence can leave a sufficient trustworthy sample, while a
non-increasing valid sequence contradicts the tire history itself. Selective
deletion would hide the contradiction.

**Alternatives considered**:

- Renumbering ages from observed stint length: rejected as fabrication.
- Dropping repeated/decreasing points until monotonic: rejected as silent repair.
- Invalidating a stint for one missing value despite six valid points: rejected
  by clarification.

## Decision 7: Use SciPy Theil-Sen with a joint intercept

**Decision**: Call `scipy.stats.theilslopes(y, x, method="joint")`. Use reported
tire age as x and unrounded lap duration in seconds as y. The joint intercept is
`median(y - slope*x)`; predictions use `intercept + slope*x`; reliability is the
median absolute prediction residual.

**Rationale**: The specification requires Theil-Sen. SciPy documents the slope
as the median of pairwise slopes and offers two intercept definitions. The joint
definition centers residuals around the selected slope and directly supports the
required residual metric. Passing `method` explicitly avoids depending on
SciPy's current `separate` default. See the official
[SciPy `theilslopes` documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.theilslopes.html).

**Alternatives considered**:

- SciPy's `method="separate"`: rejected because it defines a different line via
  `median(y) - slope*median(x)` and does not center residuals for the fitted
  slope.
- Scikit-learn `TheilSenRegressor`: rejected because it is absent, designed for
  broader multidimensional fitting, and would add a larger dependency.
- A handwritten estimator: rejected because a maintained direct dependency is
  already resolved through FastF1 and reduces implementation risk.
- Publishing SciPy's confidence interval: rejected as outside the approved
  reliability contract.

## Decision 8: Declare SciPy directly

**Decision**: Declare `scipy>=1.11,<2` as a direct production dependency and
record it in the uv lockfile.

**Rationale**: FastF1 currently brings SciPy transitively and `uv.lock` resolves
1.18.1, but application code must declare what it imports. The range matches
FastF1 3.8.3's installed dependency constraint and avoids an accidental SciPy 2
contract change.

**Alternatives considered**:

- Relying on the transitive dependency: rejected as undeclared application use.
- Adding scikit-learn: rejected as unnecessary.
- Pinning exactly 1.18.1 in `pyproject.toml`: rejected because the lockfile owns
  exact resolution while the manifest states the supported compatible range.

## Decision 9: Publish numeric millisecond resolution deterministically

**Decision**: Calculate from unrounded values; quantize slope and residual to
`Decimal("0.001")` with `ROUND_HALF_UP`; publish finite JSON numbers and normalize
rounded negative zero to positive zero.

**Rationale**: This implements the clarification and follows Feature 002's
isolated decimal-context convention. JSON numeric equivalence does not preserve
trailing zero characters, so the contract promises 0.001-second resolution,
not fixed-width text.

**Alternatives considered**:

- Python binary `round`: rejected because tie behavior and binary conversion are
  less explicit.
- String-valued decimals: rejected because the metric is numeric analytical data.
- Integer milliseconds: rejected because the public metric is specified in
  seconds per lap.

## Decision 10: Use explicit status and reason enums

**Decision**: Use status values `available` and `unavailable`. Use exact reason
values `inconsistent_stint_metadata`, `wet_weather_compound`,
`missing_compound`, `unsupported_compound`, `inconsistent_tire_age`,
`missing_tire_age`, and `insufficient_eligible_sample`. The public policy exposes
six ordered tiers, with `missing_compound` and `unsupported_compound` together
in the third tier rather than ordered against each other.

**Rationale**: These values map one-to-one to the clarified semantic outcomes.
Available stints require both metrics and no reason; unavailable stints require
one reason and neither metric.

**Alternatives considered**:

- One status enum containing every reason: rejected because availability and
  cause are separate states.
- Confidence labels: rejected by the specification.
- A quality-metadata-unavailable reason: rejected because missing assertions are
  neutral.

## Decision 11: Distinguish missing-age from general sample failure

**Decision**: `missing_tire_age` covers any normalized reported tire age that is
unavailable or unusable, including an absent provider value and a value mapped
to `None` because it is non-finite, non-positive, non-integral, or boolean. When
eligible count is below six, select this reason only if there is at least one
lap-level `unusable_tire_age` exclusion and adding only those observations would
reach six. Otherwise select `insufficient_eligible_sample`.

**Rationale**: This deterministic counterfactual implements “missing tire age
when it prevents sufficient sample.” It prevents inaccurate/generated or
structural exclusions from being mislabeled as a tire-age blocker.

**Alternatives considered**:

- Any missing age always wins: rejected because it may not be sample-decisive.
- Any shortfall is insufficient sample: rejected because it hides the specified
  missing-age outcome.

## Decision 12: Add isolated tire-stint resources and contracts

**Decision**: Add `/tire-stints` and `/tire-stints/drivers/{driver_number}` with
operation IDs `getSessionTireStintAnalysis` and
`getDriverTireStintAnalysis`. Put Feature 003 Pydantic contracts in
`stint_models.py` and orchestration in `stint_service.py`.

**Rationale**: Explicit resource naming keeps the API additive and avoids
confusing these analytics with future non-tire stint concepts. Separate models
prevent Feature 003 enums and validators from changing Feature 002's public
contract while safely reusing existing context and identity models.

**Alternatives considered**:

- Extending `/pace` responses: rejected as a Feature 002 breaking change.
- Bare `/stints`: rejected as less explicit.
- A comparison endpoint: rejected as out of scope.

## Decision 13: Keep session output compact and driver output auditable

**Decision**: Session output contains driver and stint summaries plus unassigned
counts. Driver detail reuses the same summary and adds one canonical evidence
record for every source lap, including every duplicate and unassigned row. The
canonical order uses normalized facts and authoritative identity only.

**Rationale**: Shared summaries prevent projection drift; a flat evidence list
proves exact row accounting without duplicating evidence inside nested stints.

**Alternatives considered**:

- Full lap evidence in the session response: rejected by FR-014.
- Separate duplicated summary shapes for session and detail: rejected because
  validators could diverge.

## Decision 14: Preserve observational interpretation in the contract

**Decision**: Return one strict limitations object in both response roots with
an observational interpretation, `isolated_physical_tire_wear: false`, six fixed
unadjusted-effect identifiers, and fixed human-readable text.

**Rationale**: Machine and human consumers receive the same limits without
duplicating text on every stint. The result cannot truthfully be presented as
fuel-, traffic-, track-, management-, or environment-adjusted.

**Alternatives considered**:

- Documentation-only caveat: rejected because downstream consumers need
  machine-readable safeguards.
- Naming the metric “degradation”: rejected because it overstates causality.

## Decision 15: Preserve offline-first verification

**Decision**: Add pure, normalization, service, API, and semantic OpenAPI tests
to the routine suite; extend the existing `F1_RUN_INTEGRATION=1` test module for
provider compatibility and invariants only.

**Rationale**: The repository already blocks uncontrolled FastF1 access in
routine tests and treats live source behavior as an explicit acceptance layer.

**Alternatives considered**:

- Live source data as unit fixtures: rejected as slow and nondeterministic.
- External analyst trend values as expected answers: rejected because provider
  compatibility does not establish identical analytical policy.
