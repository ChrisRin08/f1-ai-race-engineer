# Demo v0.1

## Goal

Demo v0.1 targets a working vertical slice:

```text
real F1 data -> deterministic Python analytics -> FastAPI -> frontend dashboard
```

The goal is to prove that the product can load real Formula 1 session data, calculate useful analytics in Python, expose those results through an API, and display them in a focused dashboard.

## Vertical Slice

The first demo should validate one known race/session before expanding to broader season/event/session coverage.

The internal architecture should still be shaped around generic season, event, session, and driver inputs so the demo does not become a one-off implementation.

The initial validation dataset is the 2025 Italian Grand Prix at Monza, Race session. This is a control dataset for validating the vertical slice, not a permanent hard-coded product limitation. The backend should later support dynamic year, event, and session selection.

## Included Scope

Current backend capability: health, session summary, deterministic representative lap evidence, overall pace ranking, directional driver comparison, observed tire-stint analytics, and auditable pit-lane/lap-boundary race context for the Monza control race. Feature 002 uses median pace, a five-lap minimum, published-millisecond ties/ranks/deltas, and explicit exclusion counts. Its condition-unaware 120% anomaly heuristic is separate from Feature 003, which uses reported stint and tire-age facts, requires six eligible distinct ages, and publishes an observational Theil-Sen trend where available. The frontend and the remaining broader analytics below remain demo targets, not delivered functionality.

Demo v0.1 targets:

- A Next.js frontend dashboard.
- A FastAPI backend.
- Deterministic Python analytics.
- Real Formula 1 data loaded through the backend.
- Structured API responses consumed by the frontend.
- A controlled validation session for initial demo confidence.

The intended first analytics slice includes:

- Lap times
- Fastest lap
- Representative or average race pace
- Tire compounds
- Stint lengths
- Pit-lane entry/exit evidence and entry-to-exit elapsed time (not stationary service timing)
- Basic driver pace comparison where supported by the available data

## Deferred Scope

The following are explicitly out of scope for Demo v0.1 unless the plan changes:

- Database persistence
- Supabase or PostgreSQL
- pgvector or RAG
- Amazon Bedrock implementation
- Live voice interaction
- Authentication
- Docker
- scikit-learn model training
- Pit strategy simulation
- LLM-generated strategy calculations
- Cache eviction, Docker volumes, or production cache infrastructure
- CI/CD workflow creation
- Dynamic session coverage and analytics beyond the approved session, pace, tire-stint, and race-context resources

## Feature 003 Demonstration Flow

Start the API from the repository root:

```bash
cd backend
uv run --frozen --no-sync uvicorn app.main:app --reload
```

Request the compact session view:

```bash
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/tire-stints
```

The response keeps every authoritative participant in numeric driver-number
order and shows each reported stint's compound, ranges, reconciled sample,
status, and optional metrics. It does not duplicate lap evidence. If the loaded
provider snapshot contains an `available` stint, inspect its
`observed_pace_trend_seconds_per_lap` and
`median_absolute_residual_seconds`. If it contains an `unavailable` stint,
inspect its `unavailability_reason` and confirm both metrics are null. The demo
does not depend on a particular driver or outcome because FastF1 can correct
historical data.

Choose a canonical `driver_number` returned by the session response, export it
as `DRIVER_NUMBER`, and request the audit resource:

```bash
curl --fail --silent \
  "http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/tire-stints/drivers/${DRIVER_NUMBER}"
```

Driver detail repeats the same stint summaries and adds one evidence record for
every normalized source lap. Use `disposition`, `primary_exclusion_reason`, and
`unassigned_reason` to explain why each row did or did not enter an estimator
sample. The sample totals, detailed exclusion counts, and unassigned count must
reconcile with that evidence.

Interpret the trend as observed direction within one stint:

- positive: lap times tended to increase as reported tire age increased;
- negative: lap times tended to decrease as reported tire age increased;
- zero: no directional change remains after publication rounding.

None of these values alone proves physical tire degradation. The response
explicitly identifies an `observational_association`, sets
`isolated_physical_tire_wear` to false, and lists fuel load or burn, traffic,
track evolution, driver tire management, changing environmental conditions,
and other unmodeled race effects as unadjusted factors.

## Feature 004 Demonstration Flow

With the same API running, request the compact race-context view:

```bash
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/race-context
```

Inspect `source.provider` (`FastF1`), the canonical authoritative participants,
source-backed classification, `latest_lap_context`, `pit_evidence_counts`, and
`unassociated_evidence_count`. A known participant with no usable evidence is
still present; no lap or pit event is invented. The compact response does not
duplicate complete lap or pit collections.

Choose a canonical numeric `driver_number` from that response, set
`DRIVER_NUMBER`, and request its detail:

```bash
curl --fail --silent \
  "http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/race-context/drivers/${DRIVER_NUMBER}"
```

Driver detail repeats the compact participant summary and adds the complete
compact `lap_contexts` and `pit_evidence`. Separate requests load separate
snapshots; equality of their shared facts assumes the same underlying source
facts. Each operation performs one central analysis, not per-driver or per-pit
acquisition.

Use the audit fields to explain:

- `lap_completion_position`: provider-exposed race position at lap completion,
  not live position, GPS, or instantaneous pit-entry position.
- `laps_behind`: completed-lap deficit at the selected completion. Positive
  values require a null equal-distance metric with `not_applicable` status.
- `equal_distance_time_deficit_ms`: selected driver minus lap leader completion
  for the same completed lap number, when trustworthy. It is not a current,
  live, TV, or physical gap. Unusable required evidence remains `unavailable`.
- Pit states: `complete`, `unpaired_entry`, `unpaired_exit`, `conflicting`, or
  `unavailable`. Inspect whichever states occur; do not require this historical
  snapshot to demonstrate all of them.
- `entry_to_exit_elapsed_ms`: available only for a trustworthy complete pair;
  it measures elapsed time from pit-lane entry to exit, not stationary service,
  mechanic work, or tire-change duration.
- Entry/exit lap references and reported compound/stint context: from exactly
  the in-lap/out-lap completion rows, without nearby-lap fallback. Changed flags
  compare reported values; they do not confirm a physical tire change.
- Generated state, source multiplicity, and ordered track statuses: evidence
  remains explicit. Unknown status is not green; unavailable status has an
  empty list and null disruption flag.

The real-provider acceptance slice uses one retained 2025 Italian GP Race
snapshot to validate compatibility, provenance, evidence reconciliation,
determinism, and finite JSON. Run the dedicated opt-in command in the
[README](../README.md#pit-lane-and-lap-boundary-race-context) only with provider
access authorized. Controlled offline fixtures, not incidental Monza outcomes,
establish incomplete, conflicting, generated, rounding-collision, and other
edge-case policy. This feature supplies auditable context, not pit loss,
strategy recommendations, predictions, a dashboard, or live-race analysis.

## Acceptance Criteria

Demo v0.1 is acceptable when:

- The backend can load one known Formula 1 session through a controlled path.
- The controlled path validates the 2025 Italian Grand Prix at Monza, Race session.
- The backend computes deterministic analytics without relying on an LLM.
- FastAPI exposes the analytics as structured JSON.
- The frontend fetches backend data instead of hard-coding authoritative race results.
- The dashboard presents the selected session clearly enough to explain the race analysis workflow.
- Generated caches, local data, credentials, and build artifacts are not committed.
