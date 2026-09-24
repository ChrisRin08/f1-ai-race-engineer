"""Strict public projections of approved observed tire-stint analytics."""

from collections import Counter, defaultdict
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, StrictBool, field_validator, model_validator

from app.lap_analytics import DisruptiveTrackStatus
from app.models import ContractModel, SourceProvenance
from app.pace_models import (
    AnalyticsDriverIdentity,
    AnalyticsSessionContext,
    DriverNumber,
    NonNegativeInteger,
    PositiveInteger,
)
from app.stint_analytics import (
    StintAnalysisStatus,
    StintLapDisposition,
    StintLapExclusionReason,
    StintUnavailabilityReason,
    UnassignedLapReason,
)


class StintContractModel(ContractModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)


class NormalizedTireCompound(StrEnum):
    SOFT = "SOFT"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    INTERMEDIATE = "INTERMEDIATE"
    WET = "WET"


CompoundTier = Annotated[
    tuple[Literal["missing_compound", "unsupported_compound"], ...],
    Field(
        min_length=2,
        max_length=2,
        json_schema_extra={
            "uniqueItems": True,
            "allOf": [
                {"contains": {"const": "missing_compound"}},
                {"contains": {"const": "unsupported_compound"}},
            ],
        },
    ),
]


class ObservedTireStintPolicy(StintContractModel):
    policy_id: Literal["observed-tire-stint-pace-trend-v1"]
    metric: Literal["observed_pace_trend_seconds_per_lap"]
    estimator: Literal["theil_sen"]
    intercept_method: Literal["joint"]
    minimum_eligible_observations: Literal[6]
    minimum_distinct_tire_ages: Literal[6]
    tire_age_axis: Literal["reported_tire_age_laps"]
    trend_unit: Literal["seconds_per_lap_of_reported_tire_age"]
    residual_unit: Literal["seconds"]
    publication_decimal_places: Literal[3]
    rounding: Literal["half_up"]
    eligible_compounds: tuple[Literal["SOFT", "MEDIUM", "HARD"], ...] = Field(
        min_length=3, max_length=3, json_schema_extra={"uniqueItems": True}
    )
    wet_weather_compounds: tuple[Literal["INTERMEDIATE", "WET"], ...] = Field(
        min_length=2, max_length=2, json_schema_extra={"uniqueItems": True}
    )
    lap_exclusion_precedence: tuple[
        Literal["invalid_timing"],
        Literal["lap_one_start"],
        Literal["pit_in"],
        Literal["pit_out"],
        Literal["disrupted_status"],
        Literal["explicitly_inaccurate"],
        Literal["provider_generated"],
        Literal["unusable_tire_age"],
    ]
    availability_precedence: tuple[
        tuple[Literal["inconsistent_stint_metadata"]],
        tuple[Literal["wet_weather_compound"]],
        CompoundTier,
        tuple[Literal["inconsistent_tire_age"]],
        tuple[Literal["missing_tire_age"]],
        tuple[Literal["insufficient_eligible_sample"]],
    ] = Field(
        description=(
            "Ordered tiers; missing_compound and unsupported_compound share one "
            "semantic tier. Their canonical serialization order creates no precedence."
        )
    )

    @field_validator(
        "minimum_eligible_observations",
        "minimum_distinct_tire_ages",
        "publication_decimal_places",
        mode="before",
    )
    @classmethod
    def strict_integer_constants(cls, value):
        if type(value) is not int:
            raise ValueError("Policy counts require integers.")
        return value

    @field_validator("eligible_compounds", "wet_weather_compounds")
    @classmethod
    def unique_compounds(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Policy compounds must be unique.")
        return value

    @field_validator("availability_precedence")
    @classmethod
    def canonical_same_tier(cls, value):
        if len(set(value[2])) != 2:
            raise ValueError("The compound tier requires both semantic outcomes.")
        return (*value[:2], ("missing_compound", "unsupported_compound"), *value[3:])


class ObservationalLimitations(StintContractModel):
    interpretation: Literal["observational_association"]
    isolated_physical_tire_wear: Literal[False]
    unadjusted_for: tuple[
        Literal[
            "fuel_load_or_burn",
            "traffic",
            "track_evolution",
            "driver_tire_management",
            "changing_environmental_conditions",
            "other_unmodeled_race_effects",
        ],
        ...,
    ] = Field(min_length=6, max_length=6, json_schema_extra={"uniqueItems": True})
    description: Literal[
        "This observed pace trend is an unadjusted association and is not an "
        "estimate of isolated physical tire wear."
    ]

    @field_validator("isolated_physical_tire_wear", mode="before")
    @classmethod
    def strict_boolean_constant(cls, value):
        if type(value) is not bool:
            raise ValueError("The limitation flag requires a boolean.")
        return value

    @field_validator("unadjusted_for")
    @classmethod
    def unique_limitations(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Every limitation must appear once.")
        return value


class PositiveIntegerRange(StintContractModel):
    minimum: PositiveInteger
    maximum: PositiveInteger

    @model_validator(mode="after")
    def ordered_bounds(self) -> Self:
        if self.minimum > self.maximum:
            raise ValueError("Range minimum cannot exceed maximum.")
        return self


class StintExclusionCounts(StintContractModel):
    invalid_timing: NonNegativeInteger
    lap_one_start: NonNegativeInteger
    pit_in: NonNegativeInteger
    pit_out: NonNegativeInteger
    disrupted_status: NonNegativeInteger
    explicitly_inaccurate: NonNegativeInteger
    provider_generated: NonNegativeInteger
    unusable_tire_age: NonNegativeInteger


class StintSample(StintContractModel):
    total_lap_count: NonNegativeInteger
    eligible_observation_count: NonNegativeInteger
    excluded_observation_count: NonNegativeInteger
    distinct_eligible_tire_age_count: NonNegativeInteger
    exclusions: StintExclusionCounts

    @model_validator(mode="after")
    def reconciled_counts(self) -> Self:
        if (
            self.total_lap_count
            != self.eligible_observation_count + self.excluded_observation_count
        ):
            raise ValueError("Total must equal eligible plus excluded counts.")
        if self.excluded_observation_count != sum(
            self.exclusions.model_dump().values()
        ):
            raise ValueError("Exclusion counts must sum to the excluded count.")
        if self.distinct_eligible_tire_age_count > self.eligible_observation_count:
            raise ValueError("Distinct ages cannot exceed eligible observations.")
        return self


PublishedTrend = Annotated[
    float, Field(strict=True, allow_inf_nan=False, multiple_of=0.001)
]
PublishedResidual = Annotated[
    float, Field(strict=True, allow_inf_nan=False, ge=0, multiple_of=0.001)
]


class ObservedStintSummary(StintContractModel):
    driver_number: DriverNumber
    reported_stint: PositiveInteger
    reported_compound: str | None = Field(
        description=(
            "Deterministic case-preserved raw/audit representative token; "
            "does not establish trusted compound classification."
        )
    )
    normalized_compound: NormalizedTireCompound | None = Field(
        description=(
            "Trusted recognized compound only when metadata resolves to one "
            "unambiguous normalized key; null for conflicting keys. "
            "Never fall back to reported_compound."
        )
    )
    lap_range: PositiveIntegerRange | None
    reported_tire_age_range: PositiveIntegerRange | None
    eligible_tire_age_range: PositiveIntegerRange | None
    sample: StintSample
    status: StintAnalysisStatus
    unavailability_reason: StintUnavailabilityReason | None
    observed_pace_trend_seconds_per_lap: PublishedTrend | None
    median_absolute_residual_seconds: PublishedResidual | None

    @model_validator(mode="after")
    def availability_consistency(self) -> Self:
        available = self.status == StintAnalysisStatus.AVAILABLE
        if available != (self.unavailability_reason is None):
            raise ValueError("Unavailable stints require exactly one reason.")
        if any(
            (value is not None) != available
            for value in (
                self.observed_pace_trend_seconds_per_lap,
                self.median_absolute_residual_seconds,
            )
        ):
            raise ValueError(
                "Available requires both metrics; unavailable requires neither."
            )
        if available:
            if self.normalized_compound not in (
                NormalizedTireCompound.SOFT,
                NormalizedTireCompound.MEDIUM,
                NormalizedTireCompound.HARD,
            ):
                raise ValueError("Available stints require a trusted slick compound.")
            if (
                self.sample.eligible_observation_count < 6
                or self.sample.distinct_eligible_tire_age_count < 6
            ):
                raise ValueError(
                    "Available stints require at least six eligible observations "
                    "and six distinct eligible tire ages."
                )
        return self


class DriverTireStintSummary(StintContractModel):
    driver: AnalyticsDriverIdentity
    stints: tuple[ObservedStintSummary, ...]
    unassigned_lap_count: NonNegativeInteger

    @model_validator(mode="after")
    def unique_driver_scoped_stints(self) -> Self:
        ids = [stint.reported_stint for stint in self.stints]
        if len(ids) != len(set(ids)):
            raise ValueError("Each reported stint must appear once.")
        if any(
            stint.driver_number != self.driver.driver_number for stint in self.stints
        ):
            raise ValueError("Stint summaries must belong to the selected driver.")
        return self


class TireStintLapEvidence(StintContractModel):
    lap_number: PositiveInteger | None
    lap_time_ms: PositiveInteger | None
    disposition: StintLapDisposition
    reported_stint: PositiveInteger | None
    reported_compound: str | None
    reported_tire_age: PositiveInteger | None
    pit_in: StrictBool
    pit_out: StrictBool
    track_status_codes: (
        Annotated[
            tuple[Annotated[str, Field(pattern=r"^[0-9]$")], ...],
            Field(json_schema_extra={"uniqueItems": True}),
        ]
        | None
    )
    disruptive_statuses: tuple[DisruptiveTrackStatus, ...] = Field(
        json_schema_extra={"uniqueItems": True}
    )
    is_accurate: StrictBool | None
    provider_generated: StrictBool | None
    primary_exclusion_reason: StintLapExclusionReason | None
    unassigned_reason: UnassignedLapReason | None

    @model_validator(mode="after")
    def compatible_disposition(self) -> Self:
        unassigned = self.disposition == StintLapDisposition.UNASSIGNED
        excluded = self.disposition == StintLapDisposition.EXCLUDED
        if unassigned != (self.reported_stint is None) or unassigned != (
            self.unassigned_reason is not None
        ):
            raise ValueError(
                "Only unassigned evidence has no stint and an unassigned reason."
            )
        if excluded != (self.primary_exclusion_reason is not None):
            raise ValueError("Only excluded evidence requires an exclusion reason.")
        if self.disposition == StintLapDisposition.ELIGIBLE and any(
            value is None
            for value in (self.lap_number, self.lap_time_ms, self.reported_tire_age)
        ):
            raise ValueError("Eligible evidence requires timing and reported age.")
        for values in (self.track_status_codes, self.disruptive_statuses):
            if values is not None and len(values) != len(set(values)):
                raise ValueError("Status diagnostics must be unique.")
        return self


class SessionTireStintAnalysisResponse(StintContractModel):
    context: AnalyticsSessionContext
    policy: ObservedTireStintPolicy
    limitations: ObservationalLimitations
    drivers: tuple[DriverTireStintSummary, ...]
    source: SourceProvenance

    @model_validator(mode="after")
    def validate_driver_identities_and_order(self) -> Self:
        driver_numbers = [driver.driver.driver_number for driver in self.drivers]
        if len(driver_numbers) != len(set(driver_numbers)):
            raise ValueError("Session driver numbers must be unique.")
        if driver_numbers != sorted(driver_numbers, key=int):
            raise ValueError("Session driver numbers must already be in numeric order.")
        return self


class DriverTireStintAnalysisResponse(StintContractModel):
    context: AnalyticsSessionContext
    policy: ObservedTireStintPolicy
    limitations: ObservationalLimitations
    driver: DriverTireStintSummary
    laps: tuple[TireStintLapEvidence, ...]
    source: SourceProvenance

    @model_validator(mode="after")
    def reconcile_evidence(self) -> Self:
        # Count every occurrence, including content-equal source rows. These are
        # public accounting checks, not lap classification or trend qualification.
        assigned = defaultdict(list)
        unassigned = 0
        for lap in self.laps:
            if lap.reported_stint is None:
                unassigned += 1
            else:
                assigned[lap.reported_stint].append(lap)
        if unassigned != self.driver.unassigned_lap_count:
            raise ValueError("Unassigned evidence must match its count.")
        if set(assigned) != {stint.reported_stint for stint in self.driver.stints}:
            raise ValueError("Every assigned row must reference one represented stint.")
        for stint in self.driver.stints:
            rows = assigned[stint.reported_stint]
            sample = stint.sample
            reasons = Counter(lap.primary_exclusion_reason for lap in rows)
            ages = {
                lap.reported_tire_age
                for lap in rows
                if lap.disposition == StintLapDisposition.ELIGIBLE
            }
            if (
                len(rows) != sample.total_lap_count
                or reasons[None] != sample.eligible_observation_count
            ):
                raise ValueError(
                    "Assigned and eligible evidence must match sample counts."
                )
            if len(ages) != sample.distinct_eligible_tire_age_count:
                raise ValueError(
                    "Distinct eligible evidence ages must match the count."
                )
            if any(
                reasons[reason] != count
                for reason, count in sample.exclusions.model_dump().items()
            ):
                raise ValueError("Exclusion evidence must match every reason count.")
        return self
