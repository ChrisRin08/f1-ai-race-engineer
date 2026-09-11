"""Strict public contracts for representative race-pace analytics."""

from collections import Counter
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from app.lap_analytics import (
    MINIMUM_REPRESENTATIVE_LAPS,
    DisruptiveTrackStatus,
    LapExclusionReason,
)
from app.models import (
    CircuitSummary,
    ContractModel,
    EventSummary,
    SessionIdentity,
    SourceProvenance,
)

DRIVER_NUMBER_PATTERN = r"^[1-9][0-9]*$"
DriverNumber = Annotated[str, Field(pattern=DRIVER_NUMBER_PATTERN)]
PositiveInteger = Annotated[int, Field(strict=True, ge=1)]
NonNegativeInteger = Annotated[int, Field(strict=True, ge=0)]
PolicyId = Literal["representative-race-pace-v1"]


class RepresentativeRacePacePolicy(ContractModel):
    model_config = ConfigDict(frozen=True)

    policy_id: PolicyId
    primary_metric: Literal["median"]
    consistency_metric: Literal["population_standard_deviation"]
    minimum_representative_laps: Literal[5]
    anomalous_pace_threshold_percent: Literal[120]
    anomalous_pace_comparison: Literal["strictly_greater_than"]
    anomalous_pace_reference: Literal[
        "driver_fastest_after_structural_status_exclusions"
    ]
    timing_unit: Literal["milliseconds"]
    rounding: Literal["half_up"]
    ranking_method: Literal["competition"]
    tie_basis: Literal["published_median_milliseconds"]
    tie_display_order: Literal["driver_number_ascending_numeric"]
    is_accurate_used_for_exclusion: Literal[False]
    track_conditions_adjusted: Literal[False]
    exclusion_precedence: tuple[
        Literal["invalid_timing"],
        Literal["lap_one_start"],
        Literal["pit_in"],
        Literal["pit_out"],
        Literal["disrupted_status"],
        Literal["anomalous_pace"],
    ]
    disruptive_track_statuses: tuple[
        Literal["yellow"],
        Literal["safety_car"],
        Literal["red_flag"],
        Literal["virtual_safety_car"],
        Literal["virtual_safety_car_ending"],
    ]


class AnalyticsSessionContext(ContractModel):
    year: int
    event: EventSummary
    session: SessionIdentity
    circuit: CircuitSummary


class AnalyticsDriverIdentity(ContractModel):
    driver_number: DriverNumber
    abbreviation: str | None
    full_name: str | None
    team_name: str | None


class LapClassification(ContractModel):
    source_order: PositiveInteger
    lap_number: PositiveInteger | None
    lap_time_ms: PositiveInteger | None
    classification: Literal["representative", "excluded"]
    primary_exclusion_reason: LapExclusionReason | None
    track_status_codes: (
        Annotated[
            list[Annotated[str, Field(pattern=r"^[0-9]$")]],
            Field(json_schema_extra={"uniqueItems": True}),
        ]
        | None
    )
    disruptive_statuses: list[DisruptiveTrackStatus] = Field(
        json_schema_extra={"uniqueItems": True}
    )
    is_accurate: bool | None
    compound: str | None

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        representative = self.classification == "representative"
        if representative != (self.primary_exclusion_reason is None):
            raise ValueError("Excluded laps require exactly one primary reason.")
        missing_timing = self.lap_number is None or self.lap_time_ms is None
        if missing_timing != (
            self.primary_exclusion_reason == LapExclusionReason.INVALID_TIMING
        ):
            raise ValueError("Missing timing identity requires invalid_timing.")
        for values in (self.track_status_codes, self.disruptive_statuses):
            if values is not None and len(values) != len(set(values)):
                raise ValueError("Status diagnostics must be unique.")
        return self


class ExclusionCounts(ContractModel):
    invalid_timing: NonNegativeInteger
    lap_one_start: NonNegativeInteger
    pit_in: NonNegativeInteger
    pit_out: NonNegativeInteger
    disrupted_status: NonNegativeInteger
    anomalous_pace: NonNegativeInteger


class LapSample(ContractModel):
    source_lap_count: NonNegativeInteger
    representative_lap_count: NonNegativeInteger
    excluded_lap_count: NonNegativeInteger
    exclusions: ExclusionCounts

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if (
            self.source_lap_count
            != self.representative_lap_count + self.excluded_lap_count
        ):
            raise ValueError(
                "Source count must equal representative plus excluded counts."
            )
        if self.excluded_lap_count != sum(self.exclusions.model_dump().values()):
            raise ValueError("Primary exclusion counts must sum to the excluded count.")
        return self


class PaceMetrics(ContractModel):
    median_lap_time_ms: PositiveInteger
    mean_lap_time_ms: PositiveInteger
    fastest_lap_time_ms: PositiveInteger
    population_standard_deviation_ms: NonNegativeInteger


class DriverPaceSummary(ContractModel):
    driver: AnalyticsDriverIdentity
    status: Literal["available", "insufficient_data"]
    policy_id: PolicyId
    sample: LapSample
    metrics: PaceMetrics | None
    rank: PositiveInteger | None
    tied: bool | None
    delta_to_best_ms: NonNegativeInteger | None
    source: SourceProvenance

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        available = self.status == "available"
        enough_laps = (
            self.sample.representative_lap_count >= MINIMUM_REPRESENTATIVE_LAPS
        )
        if available != enough_laps:
            raise ValueError(
                "Availability must agree with the representative sample size."
            )
        values = (self.metrics, self.rank, self.tied, self.delta_to_best_ms)
        if any((value is not None) != available for value in values):
            raise ValueError("Pace fields must all be present or all be unavailable.")
        return self


class DriverPaceAnalysisResponse(ContractModel):
    context: AnalyticsSessionContext
    policy: RepresentativeRacePacePolicy
    driver: DriverPaceSummary
    laps: list[LapClassification]
    source: SourceProvenance

    @model_validator(mode="after")
    def validate_sample_evidence(self) -> Self:
        sample = self.driver.sample
        if len(self.laps) != sample.source_lap_count:
            raise ValueError("Lap evidence must account for every source row.")
        source_orders = [lap.source_order for lap in self.laps]
        if len(source_orders) != len(set(source_orders)):
            raise ValueError("Lap evidence source orders must be unique.")
        reasons = Counter(lap.primary_exclusion_reason for lap in self.laps)
        if reasons[None] != sample.representative_lap_count:
            raise ValueError("Representative evidence must match its sample count.")
        for reason, count in sample.exclusions.model_dump().items():
            if reasons[reason] != count:
                raise ValueError(
                    "Exclusion evidence must match its primary reason count."
                )
        return self


class SessionPaceAnalysisResponse(ContractModel):
    context: AnalyticsSessionContext
    policy: RepresentativeRacePacePolicy
    drivers: list[DriverPaceSummary]
    source: SourceProvenance

    @model_validator(mode="after")
    def validate_driver_identities(self) -> Self:
        driver_numbers = [driver.driver.driver_number for driver in self.drivers]
        if len(driver_numbers) != len(set(driver_numbers)):
            raise ValueError("Session driver numbers must be unique.")
        return self


class DriverPaceComparisonResult(ContractModel):
    status: Literal["available", "insufficient_data"]
    delta_ms: Annotated[int, Field(strict=True)] | None
    outcome: Literal["driver_a_faster", "driver_b_faster", "tied"] | None
    faster_driver_number: DriverNumber | None

    @model_validator(mode="after")
    def validate_result_state(self) -> Self:
        if self.status == "insufficient_data":
            if any(
                value is not None
                for value in (self.delta_ms, self.outcome, self.faster_driver_number)
            ):
                raise ValueError("Insufficient comparisons cannot publish a result.")
        else:
            if self.delta_ms is None or self.outcome is None:
                raise ValueError("Available comparisons require a delta and outcome.")
            if self.outcome == "tied":
                if self.delta_ms != 0 or self.faster_driver_number is not None:
                    raise ValueError("A tie requires zero delta and no winner.")
            elif (
                self.faster_driver_number is None
                or (self.outcome == "driver_a_faster" and self.delta_ms >= 0)
                or (self.outcome == "driver_b_faster" and self.delta_ms <= 0)
            ):
                raise ValueError("The winner and outcome must agree with delta sign.")
        return self


class DriverPaceComparisonResponse(ContractModel):
    context: AnalyticsSessionContext
    policy: RepresentativeRacePacePolicy
    driver_a: DriverPaceSummary
    driver_b: DriverPaceSummary
    comparison: DriverPaceComparisonResult
    source: SourceProvenance

    @model_validator(mode="after")
    def validate_comparison_availability(self) -> Self:
        available = all(
            driver.status == "available" for driver in (self.driver_a, self.driver_b)
        )
        if available != (self.comparison.status == "available"):
            raise ValueError("Comparison availability must agree with both drivers.")
        if available:
            expected_delta = (
                self.driver_a.metrics.median_lap_time_ms
                - self.driver_b.metrics.median_lap_time_ms
            )
            if self.comparison.delta_ms != expected_delta:
                raise ValueError(
                    "Comparison delta must equal the published median difference."
                )
        if self.comparison.outcome in ("driver_a_faster", "driver_b_faster"):
            winner = (
                self.driver_a
                if self.comparison.outcome == "driver_a_faster"
                else self.driver_b
            )
            if self.comparison.faster_driver_number != winner.driver.driver_number:
                raise ValueError("The named faster driver must match the outcome.")
        return self
