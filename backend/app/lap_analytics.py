"""Deterministic race-pace analysis of application-owned immutable inputs."""

from collections import Counter
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Context, Decimal, localcontext
from enum import StrEnum

MINIMUM_LAP_TIME_NS = 500_000
POLICY_ID = "representative-race-pace-v1"
MINIMUM_REPRESENTATIVE_LAPS = 5


class LapExclusionReason(StrEnum):
    INVALID_TIMING = "invalid_timing"
    LAP_ONE_START = "lap_one_start"
    PIT_IN = "pit_in"
    PIT_OUT = "pit_out"
    DISRUPTED_STATUS = "disrupted_status"
    ANOMALOUS_PACE = "anomalous_pace"


class DisruptiveTrackStatus(StrEnum):
    YELLOW = "yellow"
    SAFETY_CAR = "safety_car"
    RED_FLAG = "red_flag"
    VIRTUAL_SAFETY_CAR = "virtual_safety_car"
    VIRTUAL_SAFETY_CAR_ENDING = "virtual_safety_car_ending"


DISRUPTIVE_STATUS_CODES = tuple(zip(("2", "4", "5", "6", "7"), DisruptiveTrackStatus))
EXCLUSION_PRECEDENCE = tuple(LapExclusionReason)


@dataclass(frozen=True)
class RacePacePolicy:
    policy_id: str = POLICY_ID
    primary_metric: str = "median"
    consistency_metric: str = "population_standard_deviation"
    minimum_representative_laps: int = MINIMUM_REPRESENTATIVE_LAPS
    anomalous_pace_threshold_percent: int = 120
    anomalous_pace_comparison: str = "strictly_greater_than"
    anomalous_pace_reference: str = "driver_fastest_after_structural_status_exclusions"
    timing_unit: str = "milliseconds"
    rounding: str = "half_up"
    ranking_method: str = "competition"
    tie_basis: str = "published_median_milliseconds"
    tie_display_order: str = "driver_number_ascending_numeric"
    is_accurate_used_for_exclusion: bool = False
    track_conditions_adjusted: bool = False
    exclusion_precedence: tuple[LapExclusionReason, ...] = EXCLUSION_PRECEDENCE
    disruptive_track_statuses: tuple[DisruptiveTrackStatus, ...] = tuple(
        DisruptiveTrackStatus
    )


RACE_PACE_POLICY = RacePacePolicy()


@dataclass(frozen=True)
class DriverIdentity:
    driver_number: str
    abbreviation: str | None = None
    full_name: str | None = None
    team_name: str | None = None


@dataclass(frozen=True)
class SourceLap:
    source_order: int
    driver_number: str
    lap_number: int | None
    lap_time_ns: int | None
    pit_in: bool = False
    pit_out: bool = False
    track_status_codes: tuple[str, ...] | None = None
    is_accurate: bool | None = None
    compound: str | None = None

    def __post_init__(self) -> None:
        if self.lap_time_ns is not None and (
            type(self.lap_time_ns) is not int or self.lap_time_ns < MINIMUM_LAP_TIME_NS
        ):
            raise ValueError("SourceLap requires normalized duration or None.")
        if self.lap_number is not None and (
            type(self.lap_number) is not int or self.lap_number <= 0
        ):
            raise ValueError("SourceLap requires normalized lap number or None.")


@dataclass(frozen=True)
class SessionFieldInput:
    participants: tuple[DriverIdentity, ...]
    laps: tuple[SourceLap, ...]


@dataclass(frozen=True)
class ClassifiedLap:
    lap: SourceLap
    primary_exclusion_reason: LapExclusionReason | None
    disruptive_statuses: tuple[DisruptiveTrackStatus, ...]


def classify_driver_laps(laps: tuple[SourceLap, ...]) -> tuple[ClassifiedLap, ...]:
    """Classify every row once; Compound and IsAccurate never cause exclusion."""
    structural = []
    for lap in laps:
        disruptions = tuple(
            status
            for code, status in DISRUPTIVE_STATUS_CODES
            if code in (lap.track_status_codes or ())
        )
        reason = None
        if lap.lap_time_ns is None or lap.lap_number is None:
            reason = LapExclusionReason.INVALID_TIMING
        elif lap.lap_number == 1:
            reason = LapExclusionReason.LAP_ONE_START
        elif lap.pit_in:
            reason = LapExclusionReason.PIT_IN
        elif lap.pit_out:
            reason = LapExclusionReason.PIT_OUT
        elif disruptions:
            reason = LapExclusionReason.DISRUPTED_STATUS
        structural.append(ClassifiedLap(lap, reason, disruptions))
    eligible = [
        decision.lap.lap_time_ns
        for decision in structural
        if decision.primary_exclusion_reason is None
    ]
    fastest = min(eligible) if eligible else None
    classified = []
    for decision in structural:
        reason = decision.primary_exclusion_reason
        # Exact 120% comparison; this v1 heuristic is not condition-aware.
        if (
            reason is None
            and decision.lap.lap_time_ns * 100
            > fastest * RACE_PACE_POLICY.anomalous_pace_threshold_percent
        ):
            reason = LapExclusionReason.ANOMALOUS_PACE
        classified.append(
            ClassifiedLap(decision.lap, reason, decision.disruptive_statuses)
        )
    return tuple(
        sorted(
            classified,
            key=lambda item: (
                item.lap.lap_number is None,
                item.lap.lap_number or 0,
                item.lap.source_order,
            ),
        )
    )


@dataclass(frozen=True)
class PaceMetrics:
    median_lap_time_ms: int
    mean_lap_time_ms: int
    fastest_lap_time_ms: int
    population_standard_deviation_ms: int


def publish_milliseconds(nanoseconds: int | Decimal) -> int:
    """Publish with an isolated decimal context, never clamping a rounded value."""
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
        return int(
            (Decimal(nanoseconds) / 1_000_000).quantize(
                Decimal(1), rounding=ROUND_HALF_UP
            )
        )


def calculate_metrics(durations: tuple[int, ...]) -> PaceMetrics:
    """Aggregate the complete representative sample from exact nanoseconds."""
    if len(durations) < MINIMUM_REPRESENTATIVE_LAPS:
        raise ValueError("Pace metrics require at least five representative laps.")
    if any(
        type(value) is not int or value < MINIMUM_LAP_TIME_NS for value in durations
    ):
        raise ValueError("Pace metrics require normalized usable durations.")
    ordered = sorted(durations)
    count = len(ordered)
    total = sum(ordered)
    with localcontext(Context(prec=50, rounding=ROUND_HALF_UP)):
        median = Decimal(ordered[count // 2])
        if count % 2 == 0:
            median = (median + ordered[count // 2 - 1]) / 2
        mean = Decimal(total) / count
        # Exact integer numerator avoids cancellation in nearly equal lap times.
        variance = Decimal(
            count * sum(value * value for value in ordered) - total * total
        )
        variance /= count * count
        return PaceMetrics(
            publish_milliseconds(median),
            publish_milliseconds(mean),
            publish_milliseconds(ordered[0]),
            publish_milliseconds(variance.sqrt()),
        )


@dataclass(frozen=True)
class LapSample:
    source_lap_count: int
    representative_lap_count: int
    excluded_lap_count: int
    exclusions: tuple[tuple[LapExclusionReason, int], ...]


@dataclass(frozen=True)
class DriverAnalysis:
    driver: DriverIdentity
    laps: tuple[ClassifiedLap, ...]
    sample: LapSample
    metrics: PaceMetrics | None
    rank: int | None = None
    tied: bool | None = None
    delta_to_best_ms: int | None = None


@dataclass(frozen=True)
class SessionFieldAnalysis:
    drivers: tuple[DriverAnalysis, ...]


def analyze_session_field(source: SessionFieldInput) -> SessionFieldAnalysis:
    """Analyze the whole authoritative roster once, including zero-row drivers."""
    grouped: dict[str, list[SourceLap]] = {
        driver.driver_number: [] for driver in source.participants
    }
    for lap in source.laps:
        grouped[lap.driver_number].append(lap)
    drivers = []
    for driver in source.participants:
        decisions = classify_driver_laps(tuple(grouped[driver.driver_number]))
        durations = tuple(
            d.lap.lap_time_ns for d in decisions if d.primary_exclusion_reason is None
        )
        counts = Counter(d.primary_exclusion_reason for d in decisions)
        sample = LapSample(
            len(decisions),
            len(durations),
            len(decisions) - len(durations),
            tuple((reason, counts[reason]) for reason in EXCLUSION_PRECEDENCE),
        )
        metrics = (
            calculate_metrics(durations)
            if len(durations) >= MINIMUM_REPRESENTATIVE_LAPS
            else None
        )
        drivers.append(DriverAnalysis(driver, decisions, sample, metrics))
    drivers.sort(
        key=lambda d: (
            d.metrics is None,
            d.metrics.median_lap_time_ms if d.metrics else 0,
            int(d.driver.driver_number),
        )
    )
    median_counts = Counter(d.metrics.median_lap_time_ms for d in drivers if d.metrics)
    best = min(median_counts, default=None)
    ranked = []
    previous_median = None
    rank = 0
    for position, driver in enumerate(drivers, 1):
        if driver.metrics is not None:
            median = driver.metrics.median_lap_time_ms
            if median != previous_median:
                rank = position
            driver = replace(
                driver,
                rank=rank,
                tied=median_counts[median] > 1,
                delta_to_best_ms=median - best,
            )
            previous_median = median
        ranked.append(driver)
    return SessionFieldAnalysis(tuple(ranked))
