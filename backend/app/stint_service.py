"""One-snapshot stint orchestration; all analytical decisions are projected."""

from dataclasses import asdict

from app import f1_data, lap_analytics, stint_analytics
from app.pace_models import AnalyticsDriverIdentity, AnalyticsSessionContext
from app.pace_service import DriverNotFoundError
from app.stint_models import (
    DriverTireStintAnalysisResponse,
    DriverTireStintSummary,
    ObservationalLimitations,
    ObservedStintSummary,
    ObservedTireStintPolicy,
    PositiveIntegerRange,
    SessionTireStintAnalysisResponse,
    StintExclusionCounts,
    StintSample,
    TireStintLapEvidence,
)


def load_session_tire_stints(
    year: int, event_name: str, session_name: str
) -> SessionTireStintAnalysisResponse:
    session = f1_data.load_session(year, event_name, session_name)
    inputs = f1_data.map_lap_inputs(session)
    summary = f1_data.map_session_summary(session)
    field = stint_analytics.analyze_session_stints(inputs)
    return SessionTireStintAnalysisResponse(
        context=AnalyticsSessionContext(
            year=summary.year,
            event=summary.event,
            session=summary.session,
            circuit=summary.circuit,
        ),
        policy=_policy(),
        limitations=_limitations(),
        # Complete analytics already retains the roster and canonical ordering.
        drivers=tuple(_driver_summary(driver) for driver in field.drivers),
        source=summary.source,
    )


def load_driver_tire_stints(
    year: int, event_name: str, session_name: str, driver_number: str
) -> DriverTireStintAnalysisResponse:
    session = f1_data.load_session(year, event_name, session_name)
    inputs = f1_data.map_lap_inputs(session)
    summary = f1_data.map_session_summary(session)
    field = stint_analytics.analyze_session_stints(inputs)
    driver = next(
        (
            driver
            for driver in field.drivers
            if driver.driver.driver_number == driver_number
        ),
        None,
    )
    if driver is None:
        raise DriverNotFoundError("The requested driver is not in the session results.")
    return DriverTireStintAnalysisResponse(
        context=AnalyticsSessionContext(
            year=summary.year,
            event=summary.event,
            session=summary.session,
            circuit=summary.circuit,
        ),
        policy=_policy(),
        limitations=_limitations(),
        driver=_driver_summary(driver),
        laps=tuple(_lap_response(decision) for decision in driver.laps),
        source=summary.source,
    )


def _policy() -> ObservedTireStintPolicy:
    values = asdict(stint_analytics.STINT_ANALYSIS_POLICY)
    # Internal publication_unit describes the slope; the contract spells out
    # its age axis and names the residual's unit separately.
    del values["publication_unit"]
    values.update(
        trend_unit="seconds_per_lap_of_reported_tire_age", residual_unit="seconds"
    )
    # Sorting is presentation only: members of each frozenset remain one tier.
    values["availability_precedence"] = tuple(
        tuple(sorted(tier)) for tier in values["availability_precedence"]
    )
    return ObservedTireStintPolicy.model_validate(values)


def _limitations() -> ObservationalLimitations:
    return ObservationalLimitations(
        interpretation="observational_association",
        isolated_physical_tire_wear=False,
        unadjusted_for=(
            "fuel_load_or_burn",
            "traffic",
            "track_evolution",
            "driver_tire_management",
            "changing_environmental_conditions",
            "other_unmodeled_race_effects",
        ),
        description=(
            "This observed pace trend is an unadjusted association and is not an "
            "estimate of isolated physical tire wear."
        ),
    )


def _range_response(
    value: stint_analytics.PositiveIntegerRange | None,
) -> PositiveIntegerRange | None:
    return PositiveIntegerRange(**asdict(value)) if value is not None else None


def _stint_summary(
    stint: stint_analytics.ObservedStintAnalysis,
) -> ObservedStintSummary:
    sample = stint.sample
    return ObservedStintSummary(
        driver_number=stint.driver_number,
        reported_stint=stint.reported_stint,
        reported_compound=stint.reported_compound,
        normalized_compound=stint.normalized_compound,
        lap_range=_range_response(stint.lap_range),
        reported_tire_age_range=_range_response(stint.reported_tire_age_range),
        eligible_tire_age_range=_range_response(stint.eligible_tire_age_range),
        sample=StintSample(
            total_lap_count=sample.total_lap_count,
            eligible_observation_count=sample.eligible_observation_count,
            excluded_observation_count=sample.excluded_observation_count,
            distinct_eligible_tire_age_count=sample.distinct_eligible_tire_age_count,
            exclusions=StintExclusionCounts(**dict(sample.exclusions)),
        ),
        status=stint.status,
        unavailability_reason=stint.unavailability_reason,
        observed_pace_trend_seconds_per_lap=stint.observed_pace_trend_seconds_per_lap,
        median_absolute_residual_seconds=stint.median_absolute_residual_seconds,
    )


def _driver_summary(
    driver: stint_analytics.DriverStintAnalysis,
) -> DriverTireStintSummary:
    return DriverTireStintSummary(
        driver=AnalyticsDriverIdentity(**asdict(driver.driver)),
        stints=tuple(_stint_summary(stint) for stint in driver.stints),
        unassigned_lap_count=driver.unassigned_lap_count,
    )


def _lap_response(decision: stint_analytics.StintLapDecision) -> TireStintLapEvidence:
    lap = decision.lap
    return TireStintLapEvidence(
        lap_number=lap.lap_number,
        lap_time_ms=(
            lap_analytics.publish_milliseconds(lap.lap_time_ns)
            if lap.lap_time_ns is not None
            else None
        ),
        disposition=decision.disposition,
        reported_stint=decision.reported_stint,
        reported_compound=lap.compound,
        reported_tire_age=lap.tyre_life,
        pit_in=lap.pit_in,
        pit_out=lap.pit_out,
        track_status_codes=lap.track_status_codes,
        disruptive_statuses=decision.disruptive_statuses,
        is_accurate=lap.is_accurate,
        provider_generated=lap.provider_generated,
        primary_exclusion_reason=decision.primary_exclusion_reason,
        unassigned_reason=decision.unassigned_reason,
    )
