# Quickstart: Tire Stints & Observed Degradation Analytics

This is the validation guide for Feature 003. It describes checks to run after
implementation; planning does not execute them. Detailed rules are in
[data-model.md](data-model.md), and the additive API contract is in
[contracts/openapi.yaml](contracts/openapi.yaml).

## Prerequisites

- uv installed
- Python 3.12 available to uv
- the environment synchronized from the reviewed lockfile
- network access only for explicitly authorized real FastF1 validation

All commands begin at the repository root unless stated otherwise.

## Synchronize the Reviewed Environment

Feature 003 plans a direct SciPy dependency because application code imports
`scipy.stats.theilslopes`:

```bash
cd backend
uv sync --locked
```

Before accepting the implementation diff, confirm that `pyproject.toml`
declares `scipy>=1.11,<2` and that lock regeneration did not introduce unrelated
package changes.

## Run Routine Offline Validation

Keep live integration disabled:

```bash
cd backend
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync pytest --collect-only
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync pytest
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync ruff format --check .
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync ruff check --no-cache .
```

Expected results:

- all source-normalization, shared-classifier, pure analytics, service, API,
  OpenAPI, and Feature 001/002 regression tests pass;
- integration tests remain deselected by default;
- the autouse guard fails any accidental `fastf1.get_session` access;
- no routine test creates or modifies provider cache data;
- JSON tests reject NaN and infinity.

An explicit integration selection without opt-in must skip safely:

```bash
cd backend
env -u F1_RUN_INTEGRATION uv run --offline --frozen --no-sync pytest -m integration
```

## Validate Normalization

Controlled Pandas tests must prove:

- Stint and TyreLife accept only finite positive integral non-boolean values;
- missing/malformed values become null without inference;
- FastF1Generated and IsAccurate retain true/false/null semantics;
- missing quality assertions remain neutral;
- source compound text is trimmed and case-preserved;
- new optional columns may be absent without making Feature 002 unavailable;
- duplicate consumed labels are rejected as ambiguous source schema;
- race-control messages remain unrequested and Deleted is not used.

## Validate Shared Classification

Feature 002 regression tests must prove that extraction preserves:

1. invalid timing;
2. Lap 1;
3. pit-in;
4. pit-out;
5. disruptive TrackStatus;
6. Feature 002's existing strict 120% anomaly pass.

Feature 003 tests must call the shared first five rules and then its own quality
and tire-age rules. A lap above Feature 002's 120% threshold remains eligible for
Feature 003 when it passes every Feature 003 rule.

## Validate Pure Stint Analytics

Controlled immutable inputs must cover:

- known positive, zero, and negative Theil-Sen slopes;
- a single extreme eligible time that does not control the slope;
- joint-intercept prediction and median absolute residual;
- half-up three-decimal publication from unrounded calculations;
- exactly six eligible observations and exactly five;
- absent and malformed/unusable TyreLife with six valid observations remaining;
- absent and malformed/unusable TyreLife that is sample-decisive and produces
  the public `missing_tire_age` reason;
- repeated and decreasing age, valid gaps, and starting age above one;
- explicit true, false, and missing IsAccurate and provider-generated assertions;
- every inherited exclusion and fixed first-match precedence;
- each supported slick, wet-weather, missing, unsupported, and conflicting
  compound case;
- missing stint ID and interrupted/reappearing ID;
- duplicate driver/lap identities within one stint, across different identified
  stints, mixed with unassigned rows, and containing only unassigned rows;
- duplicate rows retained with full multiplicity, affected identified stints
  returning `inconsistent_stint_metadata`, and no duplicate group reaching the
  estimator;
- canonical response equality when source rows, including distinguishable and
  fully identical duplicates, are supplied in different orders;
- every row reconciled once across assigned/unassigned and eligible/excluded
  counts, and every unavailable result suppressing both metrics;
- at least three identical repeated executions.

## Start the API

```bash
cd backend
uv run --frozen --no-sync uvicorn app.main:app --reload
```

The service listens at `http://127.0.0.1:8000`.

## Confirm Existing Contracts

```bash
curl --fail --silent http://127.0.0.1:8000/health
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/pace
```

Expected: Feature 001/002 response shapes, operation IDs, policies, error codes,
and values remain unchanged.

## Validate Feature 003 Resources

Session summary:

```bash
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/tire-stints
```

Expected: every authoritative participant appears in numeric driver order with
compact ordered stint summaries and an unassigned count. No lap evidence array
is duplicated into this response.

Driver detail:

```bash
curl --fail --silent \
  http://127.0.0.1:8000/api/v1/seasons/2025/events/italian-grand-prix/sessions/race/tire-stints/drivers/1
```

Expected: the same driver/stint summaries plus one evidence record for every
normalized driver source lap. Assigned and unassigned counts reconcile exactly.
Available slick stints contain both finite metrics; unavailable stints contain
one reason and neither metric. Policy and limitation metadata identify the joint
Theil-Sen method, 0.001-second publication, the exact exclusion sequence, the
six availability tiers, and observational interpretation. A
`missing_tire_age` result means unavailable/unusable normalized TyreLife was
sample-decisive; it is not limited to a literally absent provider value.

Repeat either request against unchanged normalized data and against permutations
of the same normalized rows. Parsed JSON must be identical. Exact duplicate rows
remain as the same number of adjacent identical evidence objects; they are not
silently deduplicated.

## Validate Error Boundaries

- malformed driver `01`: 422 before source loading;
- unsupported session tuple: 404 `session_not_supported` before source loading;
- canonical absent driver `999`: 404 `driver_not_found` after one analysis;
- expected provider/schema failure: sanitized 503 `data_source_unavailable`;
- unexpected defect: framework 500 without private detail disclosure.

## Run Explicit Real FastF1 Acceptance

Run this only when live source access is separately authorized:

```bash
cd backend
F1_RUN_INTEGRATION=1 uv run --frozen --no-sync pytest -m integration
```

The acceptance test validates real Monza provider columns, provenance,
participant and lap reconciliation, deterministic ordering, finite available
outputs, null unavailable outputs, and limitation disclosure. It does not assert
an external analyst's degradation number.

## Final Repository Audit

```bash
git diff --check
git status --short
git diff -- backend/pyproject.toml backend/uv.lock
git check-ignore -v backend/cache/fastf1/
git ls-files backend/cache backend/data
```

Expected: no unrelated dependency drift, generated cache remains ignored,
Feature 001/002 contracts remain unchanged, and no frontend, AI/ML, telemetry,
race-control, database, strategy, or deployment work appears.
