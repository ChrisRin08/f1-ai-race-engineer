"""Pure reported-stint qualification and observational Theil-Sen analytics."""

from collections import Counter
from dataclasses import dataclass, field, fields
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from enum import StrEnum
from math import isfinite
from statistics import median

from scipy.stats import theilslopes

from app.lap_analytics import (
    STRUCTURAL_STATUS_EXCLUSION_PRECEDENCE,
    DisruptiveTrackStatus,
    DriverIdentity,
    LapExclusionReason,
    SessionFieldInput,
    SourceLap,
    classify_structural_status_laps,
)


class StintLapExclusionReason(StrEnum):
    INVALID_TIMING = LapExclusionReason.INVALID_TIMING.value
    LAP_ONE_START = LapExclusionReason.LAP_ONE_START.value
    PIT_IN = LapExclusionReason.PIT_IN.value
    PIT_OUT = LapExclusionReason.PIT_OUT.value
    DISRUPTED_STATUS = LapExclusionReason.DISRUPTED_STATUS.value
    EXPLICITLY_INACCURATE = "explicitly_inaccurate"
    PROVIDER_GENERATED = "provider_generated"
    UNUSABLE_TIRE_AGE = "unusable_tire_age"


STINT_LAP_EXCLUSION_PRECEDENCE = tuple(
    StintLapExclusionReason(reason) for reason in STRUCTURAL_STATUS_EXCLUSION_PRECEDENCE
) + (
    StintLapExclusionReason.EXPLICITLY_INACCURATE,
    StintLapExclusionReason.PROVIDER_GENERATED,
    StintLapExclusionReason.UNUSABLE_TIRE_AGE,
)


class StintLapDisposition(StrEnum):
    ELIGIBLE = "eligible"
    EXCLUDED = "excluded"
    UNASSIGNED = "unassigned"


class StintAnalysisStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class StintUnavailabilityReason(StrEnum):
    INCONSISTENT_STINT_METADATA = "inconsistent_stint_metadata"
    WET_WEATHER_COMPOUND = "wet_weather_compound"
    MISSING_COMPOUND = "missing_compound"
    UNSUPPORTED_COMPOUND = "unsupported_compound"
    INCONSISTENT_TIRE_AGE = "inconsistent_tire_age"
    MISSING_TIRE_AGE = "missing_tire_age"
    INSUFFICIENT_ELIGIBLE_SAMPLE = "insufficient_eligible_sample"


STINT_AVAILABILITY_PRECEDENCE = (
    frozenset((StintUnavailabilityReason.INCONSISTENT_STINT_METADATA,)),
    frozenset((StintUnavailabilityReason.WET_WEATHER_COMPOUND,)),
    frozenset(
        (
            StintUnavailabilityReason.MISSING_COMPOUND,
            StintUnavailabilityReason.UNSUPPORTED_COMPOUND,
        )
    ),
    frozenset((StintUnavailabilityReason.INCONSISTENT_TIRE_AGE,)),
    frozenset((StintUnavailabilityReason.MISSING_TIRE_AGE,)),
    frozenset((StintUnavailabilityReason.INSUFFICIENT_ELIGIBLE_SAMPLE,)),
)


@dataclass(frozen=True)
class StintAnalysisPolicy:
    """Declared analytical method; construction does not evaluate a trend."""

    policy_id: str = "observed-tire-stint-pace-trend-v1"
    metric: str = "observed_pace_trend_seconds_per_lap"
    estimator: str = "theil_sen"
    intercept_method: str = "joint"
    minimum_eligible_observations: int = 6
    minimum_distinct_tire_ages: int = 6
    tire_age_axis: str = "reported_tire_age_laps"
    publication_unit: str = "seconds_per_lap"
    publication_decimal_places: int = 3
    rounding: str = "half_up"
    eligible_compounds: tuple[str, ...] = ("SOFT", "MEDIUM", "HARD")
    wet_weather_compounds: tuple[str, ...] = ("INTERMEDIATE", "WET")
    lap_exclusion_precedence: tuple[StintLapExclusionReason, ...] = (
        STINT_LAP_EXCLUSION_PRECEDENCE
    )
    availability_precedence: tuple[frozenset[StintUnavailabilityReason], ...] = (
        STINT_AVAILABILITY_PRECEDENCE
    )


STINT_ANALYSIS_POLICY = StintAnalysisPolicy()


class StintMetadataReason(StrEnum):
    INCONSISTENT_STINT_METADATA = "inconsistent_stint_metadata"


class UnassignedLapReason(StrEnum):
    MISSING_STINT_METADATA = "missing_stint_metadata"


def _null_last(value: int | str | tuple[str, ...] | None) -> tuple:
    return (1,) if value is None else (0, value)


def _boolean_rank(value: bool | None) -> int:
    """Fixed order: false, true, unavailable."""
    if value is None:
        return 2
    return 1 if value else 0


def canonical_lap_key(lap: SourceLap) -> tuple:
    """Total ordering of authoritative identity and normalized analytical facts."""
    return (
        int(lap.driver_number),
        _null_last(lap.lap_number),
        _null_last(lap.stint),
        _null_last(lap.tyre_life),
        _null_last(lap.lap_time_ns),
        _null_last(lap.compound),
        _boolean_rank(lap.pit_in),
        _boolean_rank(lap.pit_out),
        _null_last(lap.track_status_codes),
        _boolean_rank(lap.is_accurate),
        _boolean_rank(lap.provider_generated),
    )


@dataclass(frozen=True)
class StintConstructionLap:
    """Retain the original row; equality uses only canonical analytical facts.

    Structural diagnostics are not final Feature 003 eligibility decisions.
    Unassignment remains independent of those diagnostics.

    Content-equal evidence/decisions may represent physically distinct source rows.
    Never deduplicate these objects with sets or dict keys when row multiplicity
    matters; retain every occurrence in tuples/lists.
    """

    lap: SourceLap = field(compare=False)
    structural_reason: LapExclusionReason | None
    disruptive_statuses: tuple[DisruptiveTrackStatus, ...]
    canonical_key: tuple = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "canonical_key", canonical_lap_key(self.lap))

    @property
    def reported_stint(self) -> int | None:
        return self.lap.stint

    @property
    def unassigned_reason(self) -> UnassignedLapReason | None:
        if self.reported_stint is None:
            return UnassignedLapReason.MISSING_STINT_METADATA
        return None


@dataclass(frozen=True)
class PositiveIntegerRange:
    minimum: int
    maximum: int


@dataclass(frozen=True)
class StintConstructionSample:
    """Assigned row count; eligible/excluded counts require the later rules."""

    total_lap_count: int


@dataclass(frozen=True)
class ConstructedStint:
    driver_number: str
    reported_stint: int
    laps: tuple[StintConstructionLap, ...]
    reported_compound: str | None
    compound_keys: tuple[str, ...]
    lap_range: PositiveIntegerRange | None
    reported_tire_age_range: PositiveIntegerRange | None
    sample: StintConstructionSample
    metadata_reason: StintMetadataReason | None

    @property
    def metadata_valid_laps(self) -> tuple[StintConstructionLap, ...]:
        """Metadata gate for subsequent age/estimator work, not an eligible sample."""
        return self.laps if self.metadata_reason is None else ()


@dataclass(frozen=True)
class DriverStintConstruction:
    driver: DriverIdentity
    stints: tuple[ConstructedStint, ...]
    laps: tuple[StintConstructionLap, ...]
    unassigned_lap_count: int


@dataclass(frozen=True)
class SessionStintConstruction:
    drivers: tuple[DriverStintConstruction, ...]


def _range(values: tuple[int | None, ...]) -> PositiveIntegerRange | None:
    present = tuple(value for value in values if value is not None)
    return PositiveIntegerRange(min(present), max(present)) if present else None


def _interrupted_stints(laps: tuple[StintConstructionLap, ...]) -> set[int]:
    seen: set[int] = set()
    inconsistent: set[int] = set()
    previous = None
    for evidence in laps:
        if evidence.lap.lap_number is None:
            continue
        stint = evidence.reported_stint
        if stint is not None:
            if stint != previous and stint in seen:
                inconsistent.add(stint)
            seen.add(stint)
        previous = stint
    return inconsistent


def _duplicate_stints(laps: tuple[StintConstructionLap, ...]) -> set[int]:
    """Within one driver, block every ID on a repeated valid lap; retain all rows."""
    counts = Counter(e.lap.lap_number for e in laps if e.lap.lap_number is not None)
    return {
        e.reported_stint
        for e in laps
        if e.reported_stint is not None
        and e.lap.lap_number is not None
        and counts[e.lap.lap_number] > 1
    }


def _construct_stint(
    driver_number: str,
    stint: int,
    laps: tuple[StintConstructionLap, ...],
    inconsistent: bool,
) -> ConstructedStint:
    keys = tuple(
        sorted(
            {e.lap.compound.strip().upper() for e in laps if e.lap.compound is not None}
        )
    )
    compound_row = min(
        laps, key=lambda e: (_null_last(e.lap.lap_number), _null_last(e.lap.compound))
    )
    return ConstructedStint(
        driver_number=driver_number,
        reported_stint=stint,
        laps=laps,
        reported_compound=compound_row.lap.compound,
        compound_keys=keys,
        lap_range=_range(tuple(e.lap.lap_number for e in laps)),
        reported_tire_age_range=_range(tuple(e.lap.tyre_life for e in laps)),
        sample=StintConstructionSample(len(laps)),
        metadata_reason=(
            StintMetadataReason.INCONSISTENT_STINT_METADATA
            if inconsistent or len(keys) > 1
            else None
        ),
    )


def _construct_driver(
    driver: DriverIdentity, rows: tuple[SourceLap, ...]
) -> DriverStintConstruction:
    ordered = tuple(sorted(rows, key=canonical_lap_key))
    laps = tuple(
        StintConstructionLap(d.lap, d.primary_exclusion_reason, d.disruptive_statuses)
        for d in classify_structural_status_laps(ordered)
    )
    grouped: dict[int, list[StintConstructionLap]] = {}
    for evidence in laps:
        if evidence.reported_stint is not None:
            grouped.setdefault(evidence.reported_stint, []).append(evidence)
    inconsistent = _interrupted_stints(laps) | _duplicate_stints(laps)
    stints = tuple(
        _construct_stint(
            driver.driver_number, stint, tuple(evidence), stint in inconsistent
        )
        for stint, evidence in grouped.items()
    )
    ordered_stints = tuple(
        sorted(
            stints,
            key=lambda s: (
                _null_last(s.lap_range.minimum if s.lap_range else None),
                s.reported_stint,
            ),
        )
    )
    return DriverStintConstruction(
        driver,
        ordered_stints,
        laps,
        sum(e.reported_stint is None for e in laps),
    )


def construct_session_stints(source: SessionFieldInput) -> SessionStintConstruction:
    """Construct reported identities for the authoritative roster without repair."""
    grouped: dict[str, list[SourceLap]] = {
        d.driver_number: [] for d in source.participants
    }
    if len(grouped) != len(source.participants):
        raise ValueError("Duplicate authoritative participant identity.")
    for lap in source.laps:
        if lap.driver_number not in grouped:
            raise ValueError("Lap has no authoritative participant.")
        grouped[lap.driver_number].append(lap)
    return SessionStintConstruction(
        tuple(
            _construct_driver(driver, tuple(grouped[driver.driver_number]))
            for driver in sorted(
                source.participants, key=lambda d: int(d.driver_number)
            )
        )
    )


@dataclass(frozen=True)
class StintLapDecision(StintConstructionLap):
    primary_exclusion_reason: StintLapExclusionReason | None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.reported_stint is None and self.primary_exclusion_reason is not None:
            raise ValueError("Unassigned evidence cannot have a lap exclusion.")

    @property
    def disposition(self) -> StintLapDisposition:
        if self.reported_stint is None:
            return StintLapDisposition.UNASSIGNED
        if self.primary_exclusion_reason is not None:
            return StintLapDisposition.EXCLUDED
        return StintLapDisposition.ELIGIBLE


def classify_stint_laps(
    evidence: tuple[StintConstructionLap, ...],
) -> tuple[StintLapDecision, ...]:
    """Complete the shared structural decisions already produced by construction."""
    decisions = []
    for item in evidence:
        lap = item.lap
        reason = None
        if item.reported_stint is not None:
            if item.structural_reason is not None:
                reason = StintLapExclusionReason(item.structural_reason)
            elif lap.is_accurate is False:
                reason = StintLapExclusionReason.EXPLICITLY_INACCURATE
            elif lap.provider_generated is True:
                reason = StintLapExclusionReason.PROVIDER_GENERATED
            elif lap.tyre_life is None:
                reason = StintLapExclusionReason.UNUSABLE_TIRE_AGE
        decisions.append(
            StintLapDecision(
                lap, item.structural_reason, item.disruptive_statuses, reason
            )
        )
    return tuple(decisions)


@dataclass(frozen=True)
class TireAgeAssessment:
    is_consistent: bool
    has_minimum_sample: bool


def assess_tire_age_sample(
    eligible: tuple[StintLapDecision, ...],
) -> TireAgeAssessment:
    """Check reported eligible ages without dropping, repairing, or renumbering."""
    if any(d.disposition != StintLapDisposition.ELIGIBLE for d in eligible):
        raise ValueError("Tire-age validation requires eligible observations.")
    ordered = sorted(eligible, key=lambda d: d.canonical_key)
    ages = tuple(d.lap.tyre_life for d in ordered)
    return TireAgeAssessment(
        is_consistent=all(
            previous < current for previous, current in zip(ages, ages[1:])
        ),
        has_minimum_sample=(
            len(ages) >= STINT_ANALYSIS_POLICY.minimum_eligible_observations
            and len(set(ages)) >= STINT_ANALYSIS_POLICY.minimum_distinct_tire_ages
        ),
    )


@dataclass(frozen=True)
class StintSample:
    total_lap_count: int
    eligible_observation_count: int
    excluded_observation_count: int
    exclusions: tuple[tuple[StintLapExclusionReason, int], ...]
    distinct_eligible_tire_age_count: int

    def __post_init__(self) -> None:
        counts = (
            self.total_lap_count,
            self.eligible_observation_count,
            self.excluded_observation_count,
            self.distinct_eligible_tire_age_count,
            *(count for _, count in self.exclusions),
        )
        if any(type(count) is not int or count < 0 for count in counts):
            raise ValueError("StintSample counts must be non-negative integers.")
        reasons = tuple(reason for reason, _ in self.exclusions)
        if len(reasons) != len(STINT_LAP_EXCLUSION_PRECEDENCE) or set(reasons) != set(
            STINT_LAP_EXCLUSION_PRECEDENCE
        ):
            raise ValueError("StintSample requires one count per exclusion reason.")
        if self.total_lap_count != (
            self.eligible_observation_count + self.excluded_observation_count
        ):
            raise ValueError("StintSample total must equal eligible plus excluded.")
        if (
            sum(count for _, count in self.exclusions)
            != self.excluded_observation_count
        ):
            raise ValueError("StintSample exclusion counts must equal excluded count.")
        if self.distinct_eligible_tire_age_count > self.eligible_observation_count:
            raise ValueError("StintSample distinct ages cannot exceed eligible count.")


@dataclass(frozen=True)
class StintQualification:
    """Audit facts and qualification outcome, before estimation; no final status."""

    driver_number: str
    reported_stint: int
    reported_compound: str | None
    normalized_compound: str | None
    lap_range: PositiveIntegerRange | None
    reported_tire_age_range: PositiveIntegerRange | None
    eligible_tire_age_range: PositiveIntegerRange | None
    laps: tuple[StintLapDecision, ...]
    sample: StintSample
    unavailability_reason: StintUnavailabilityReason | None

    def __post_init__(self) -> None:
        recognized = (
            STINT_ANALYSIS_POLICY.eligible_compounds
            + STINT_ANALYSIS_POLICY.wet_weather_compounds
        )
        if (
            self.normalized_compound is not None
            and self.normalized_compound not in recognized
        ):
            raise ValueError(
                "normalized_compound must be a recognized compound or None."
            )
        if type(self.laps) is not tuple or any(
            d.lap.driver_number != self.driver_number
            or d.reported_stint != self.reported_stint
            or d.disposition == StintLapDisposition.UNASSIGNED
            for d in self.laps
        ):
            raise ValueError("Qualification requires immutable evidence for one stint.")
        if (
            self.unavailability_reason is not None
            and self.unavailability_reason not in tuple(StintUnavailabilityReason)
        ):
            raise ValueError("Qualification requires a documented unavailable reason.")
        eligible = tuple(
            d for d in self.laps if d.disposition == StintLapDisposition.ELIGIBLE
        )
        excluded = tuple(
            d for d in self.laps if d.disposition == StintLapDisposition.EXCLUDED
        )
        counts = Counter(d.primary_exclusion_reason for d in excluded)
        if (
            len(self.laps) != self.sample.total_lap_count
            or len(eligible) != self.sample.eligible_observation_count
            or len(excluded) != self.sample.excluded_observation_count
            or len({d.lap.tyre_life for d in eligible})
            != self.sample.distinct_eligible_tire_age_count
            or dict(self.sample.exclusions)
            != {reason: counts[reason] for reason in STINT_LAP_EXCLUSION_PRECEDENCE}
            or any(reason not in STINT_LAP_EXCLUSION_PRECEDENCE for reason in counts)
        ):
            raise ValueError(
                "Qualification sample counts must reconcile with evidence."
            )
        keys = {
            d.lap.compound.strip().upper()
            for d in self.laps
            if d.lap.compound is not None
        }
        trusted = next(iter(keys)) if len(keys) == 1 else None
        expected_compound = trusted if trusted in recognized else None
        if self.normalized_compound != expected_compound:
            raise ValueError(
                "normalized_compound must agree with raw compound evidence."
            )
        if (
            (len(keys) > 1 or _duplicate_stints(self.laps))
            and self.unavailability_reason
            != StintUnavailabilityReason.INCONSISTENT_STINT_METADATA
        ):
            raise ValueError(
                "Conflicting or duplicate evidence requires inconsistent metadata."
            )
        expected_sample = eligible if self.unavailability_reason is None else ()
        if tuple(map(id, self.available_sample)) != tuple(map(id, expected_sample)):
            raise ValueError(
                "available_sample must exactly match qualified eligible decisions."
            )
        if self.unavailability_reason is None:
            if trusted not in STINT_ANALYSIS_POLICY.eligible_compounds or any(
                d.lap.compound is None for d in self.laps
            ):
                raise ValueError(
                    "Estimation-ready qualification requires complete slick metadata."
                )
            if any(
                d.lap.tyre_life is None or d.lap.lap_time_ns is None for d in eligible
            ):
                raise ValueError("Eligible decisions require usable age and timing.")
            age = assess_tire_age_sample(eligible)
            if not age.is_consistent or not age.has_minimum_sample:
                raise ValueError(
                    "Estimation-ready qualification requires a valid age sample."
                )

    @property
    def available_sample(self) -> tuple[StintLapDecision, ...]:
        """Audit view of eligible decisions, never an estimator input."""
        if self.unavailability_reason is not None:
            return ()
        return tuple(
            d for d in self.laps if d.disposition == StintLapDisposition.ELIGIBLE
        )


# These private issuance conventions prevent accidental application-level use.
# They are not a security boundary against deliberate Python runtime tampering.
_ESTIMATOR_ISSUER = object()


@dataclass(frozen=True, init=False)
class _CanonicalStintQualification(StintQualification):
    """Issued by _qualify_stint after canonical context-dependent construction."""

    def __init__(self, *, _issuer: object = None, **facts) -> None:
        if _issuer is not _ESTIMATOR_ISSUER:
            raise TypeError(
                "Canonical qualification must be issued by the analysis pipeline."
            )
        super().__init__(**facts)


def _build_validated_estimator_sample(
    qualification: _CanonicalStintQualification,
) -> "_ValidatedEstimatorSample":
    """Only canonical qualification can authorize private estimator input."""
    if type(qualification) is not _CanonicalStintQualification:
        raise TypeError("Estimator input requires canonical qualification provenance.")
    return _ValidatedEstimatorSample(qualification, _issuer=_ESTIMATOR_ISSUER)


@dataclass(frozen=True, init=False)
class _ValidatedEstimatorSample:
    """Immutable numerical inputs from successful stint qualification only.

    Issued only through the private factory from canonical qualification.
    Keep full nanoseconds until the estimator converts to floating-point seconds.
    """

    tire_ages: tuple[int, ...]
    lap_times_ns: tuple[int, ...]

    def __init__(
        self, qualification: _CanonicalStintQualification, *, _issuer: object = None
    ) -> None:
        if (
            _issuer is not _ESTIMATOR_ISSUER
            or type(qualification) is not _CanonicalStintQualification
        ):
            raise TypeError(
                "Use canonical analysis to issue a validated estimator sample."
            )
        if qualification.unavailability_reason is not None:
            raise ValueError("Cannot estimate an unavailable stint.")
        eligible = qualification.available_sample
        age = assess_tire_age_sample(eligible)
        if (
            qualification.normalized_compound
            not in STINT_ANALYSIS_POLICY.eligible_compounds
            or not age.is_consistent
            or not age.has_minimum_sample
            or len(eligible) != qualification.sample.eligible_observation_count
        ):
            raise ValueError("Estimator sample requires complete valid qualification.")
        ordered = tuple(sorted(eligible, key=lambda d: d.canonical_key))
        ages = tuple(d.lap.tyre_life for d in ordered)
        durations = tuple(d.lap.lap_time_ns for d in ordered)
        # Check the actual numerical representation before passing it to SciPy.
        try:
            x = tuple(float(value) for value in ages)
            y = tuple(value / 1_000_000_000 for value in durations)
        except (OverflowError, TypeError) as exc:
            raise ValueError(
                "Estimator inputs must have finite representations."
            ) from exc
        if not all(isfinite(value) for value in x + y):
            raise ValueError("Estimator inputs must be finite.")
        if any(a >= b for a, b in zip(x, x[1:])):
            raise ValueError(
                "Estimator ages must remain distinct in float representation."
            )
        object.__setattr__(self, "tire_ages", ages)
        object.__setattr__(self, "lap_times_ns", durations)


def _require_finite(value: float) -> None:
    if isinstance(value, bool) or not isfinite(value):
        raise ValueError("Trend calculation requires finite numerical values.")


def _publish_metric(value: float) -> float:
    _require_finite(value)
    decimal = Decimal(str(value))
    with localcontext(
        Context(prec=max(50, decimal.adjusted() + 5), rounding=ROUND_HALF_UP)
    ):
        published = float(decimal.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
    _require_finite(published)
    return 0.0 if published == 0 else published


@dataclass(frozen=True)
class StintTrendMetrics:
    observed_pace_trend_seconds_per_lap: float
    median_absolute_residual_seconds: float

    def __post_init__(self) -> None:
        _require_finite(self.observed_pace_trend_seconds_per_lap)
        _require_finite(self.median_absolute_residual_seconds)
        if self.median_absolute_residual_seconds < 0:
            raise ValueError("Residual must be non-negative.")


def _estimate_stint_trend(sample: _ValidatedEstimatorSample) -> StintTrendMetrics:
    """Fit every validated observation; publish only after full-line residuals."""
    if type(sample) is not _ValidatedEstimatorSample:
        raise TypeError("_estimate_stint_trend requires _ValidatedEstimatorSample.")
    x = sample.tire_ages
    y = tuple(ns / 1_000_000_000 for ns in sample.lap_times_ns)
    fitted = theilslopes(y, x, method="joint")
    slope, intercept = float(fitted.slope), float(fitted.intercept)
    _require_finite(slope)
    _require_finite(intercept)
    residuals = []
    for age, observed in zip(x, y, strict=True):
        predicted = intercept + slope * age
        _require_finite(predicted)
        residual = abs(observed - predicted)
        _require_finite(residual)
        residuals.append(residual)
    residual = median(residuals)
    _require_finite(residual)
    return StintTrendMetrics(_publish_metric(slope), _publish_metric(residual))


@dataclass(frozen=True)
class ObservedStintAnalysis(StintQualification):
    """Final result: available means both metrics exist; unavailable means neither."""

    observed_pace_trend_seconds_per_lap: float | None
    median_absolute_residual_seconds: float | None

    def __post_init__(self) -> None:
        super().__post_init__()
        metrics = (
            self.observed_pace_trend_seconds_per_lap,
            self.median_absolute_residual_seconds,
        )
        available = self.unavailability_reason is None
        if any((value is not None) != available for value in metrics):
            raise ValueError("Final status and presence of both metrics must agree.")
        if available:
            StintTrendMetrics(*metrics)

    @property
    def status(self) -> StintAnalysisStatus:
        return (
            StintAnalysisStatus.AVAILABLE
            if self.unavailability_reason is None
            else StintAnalysisStatus.UNAVAILABLE
        )


@dataclass(frozen=True)
class DriverStintAnalysis:
    driver: DriverIdentity
    stints: tuple[ObservedStintAnalysis, ...]
    laps: tuple[StintLapDecision, ...]
    unassigned_lap_count: int


@dataclass(frozen=True)
class SessionStintAnalysis:
    drivers: tuple[DriverStintAnalysis, ...]


def _stint_unavailability(
    stint: ConstructedStint,
    eligible: tuple[StintLapDecision, ...],
    sample: StintSample,
) -> StintUnavailabilityReason | None:
    # These early returns keep all higher metadata blockers out of age validation.
    if stint.metadata_reason is not None:
        return StintUnavailabilityReason.INCONSISTENT_STINT_METADATA
    compound = stint.compound_keys[0] if stint.compound_keys else None
    if compound in STINT_ANALYSIS_POLICY.wet_weather_compounds:
        return StintUnavailabilityReason.WET_WEATHER_COMPOUND
    # Same compound tier: the approved mixed missing/unsupported tie selects missing.
    if any(e.lap.compound is None for e in stint.laps):
        return StintUnavailabilityReason.MISSING_COMPOUND
    if compound not in STINT_ANALYSIS_POLICY.eligible_compounds:
        return StintUnavailabilityReason.UNSUPPORTED_COMPOUND
    age = assess_tire_age_sample(eligible)
    if not age.is_consistent:
        return StintUnavailabilityReason.INCONSISTENT_TIRE_AGE
    if not age.has_minimum_sample:
        minimum = STINT_ANALYSIS_POLICY.minimum_eligible_observations
        unusable = dict(sample.exclusions)[StintLapExclusionReason.UNUSABLE_TIRE_AGE]
        if (
            sample.eligible_observation_count < minimum
            and unusable > 0
            and sample.eligible_observation_count + unusable >= minimum
        ):
            return StintUnavailabilityReason.MISSING_TIRE_AGE
        return StintUnavailabilityReason.INSUFFICIENT_ELIGIBLE_SAMPLE
    return None


def _qualify_stint(
    stint: ConstructedStint, decisions: tuple[StintLapDecision, ...]
) -> _CanonicalStintQualification:
    eligible = tuple(
        d for d in decisions if d.disposition == StintLapDisposition.ELIGIBLE
    )
    counts = Counter(d.primary_exclusion_reason for d in decisions)
    # These are auditable row counts even when metadata blocks the entire stint.
    sample = StintSample(
        total_lap_count=len(decisions),
        eligible_observation_count=len(eligible),
        excluded_observation_count=len(decisions) - len(eligible),
        exclusions=tuple(
            (reason, counts[reason]) for reason in STINT_LAP_EXCLUSION_PRECEDENCE
        ),
        distinct_eligible_tire_age_count=len({d.lap.tyre_life for d in eligible}),
    )
    compound = stint.compound_keys[0] if len(stint.compound_keys) == 1 else None
    recognized = (
        STINT_ANALYSIS_POLICY.eligible_compounds
        + STINT_ANALYSIS_POLICY.wet_weather_compounds
    )
    return _CanonicalStintQualification(
        _issuer=_ESTIMATOR_ISSUER,
        driver_number=stint.driver_number,
        reported_stint=stint.reported_stint,
        reported_compound=stint.reported_compound,
        normalized_compound=compound if compound in recognized else None,
        lap_range=stint.lap_range,
        reported_tire_age_range=stint.reported_tire_age_range,
        eligible_tire_age_range=_range(tuple(d.lap.tyre_life for d in eligible)),
        laps=decisions,
        sample=sample,
        unavailability_reason=_stint_unavailability(stint, eligible, sample),
    )


def _analyze_stint(
    stint: ConstructedStint, decisions: tuple[StintLapDecision, ...]
) -> ObservedStintAnalysis:
    qualification = _qualify_stint(stint, decisions)
    metrics = None
    if qualification.unavailability_reason is None:
        metrics = _estimate_stint_trend(
            _build_validated_estimator_sample(qualification)
        )
    return ObservedStintAnalysis(
        **{f.name: getattr(qualification, f.name) for f in fields(qualification)},
        observed_pace_trend_seconds_per_lap=(
            metrics.observed_pace_trend_seconds_per_lap if metrics else None
        ),
        median_absolute_residual_seconds=(
            metrics.median_absolute_residual_seconds if metrics else None
        ),
    )


def analyze_session_stints(source: SessionFieldInput) -> SessionStintAnalysis:
    """Construct once, qualify each stint, then estimate only validated samples."""
    construction = construct_session_stints(source)
    drivers = []
    for driver in construction.drivers:
        decisions = classify_stint_laps(driver.laps)
        grouped: dict[int, list[StintLapDecision]] = {
            s.reported_stint: [] for s in driver.stints
        }
        for decision in decisions:
            if decision.reported_stint is not None:
                grouped[decision.reported_stint].append(decision)
        stints = tuple(
            _analyze_stint(stint, tuple(grouped[stint.reported_stint]))
            for stint in driver.stints
        )
        drivers.append(
            DriverStintAnalysis(
                driver.driver, stints, decisions, driver.unassigned_lap_count
            )
        )
    return SessionStintAnalysis(tuple(drivers))
