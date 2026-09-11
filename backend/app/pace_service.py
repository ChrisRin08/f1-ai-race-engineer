"""One-snapshot application orchestration and pace response projections."""

from dataclasses import asdict

from app import f1_data, lap_analytics
from app.models import SessionSummary
from app.pace_models import (
    AnalyticsDriverIdentity,
    AnalyticsSessionContext,
    DriverPaceAnalysisResponse,
    DriverPaceComparisonResponse,
    DriverPaceComparisonResult,
    DriverPaceSummary,
    ExclusionCounts,
    LapClassification,
    LapSample,
    PaceMetrics,
    RepresentativeRacePacePolicy,
    SessionPaceAnalysisResponse,
)


class DriverNotFoundError(LookupError):
    """The requested canonical driver number is absent from source results."""


def load_driver_pace(
    year: int, event_name: str, session_name: str, driver_number: str
) -> DriverPaceAnalysisResponse:
    summary, field = _load_analysis(year, event_name, session_name)
    driver = _find_driver(field, driver_number)
    return DriverPaceAnalysisResponse(
        context=_context(summary),
        policy=_policy(),
        driver=_driver_summary(summary, driver),
        laps=[_lap_response(lap) for lap in driver.laps],
        source=summary.source,
    )


def load_session_pace(
    year: int, event_name: str, session_name: str
) -> SessionPaceAnalysisResponse:
    summary, field = _load_analysis(year, event_name, session_name)
    return SessionPaceAnalysisResponse(
        context=_context(summary),
        policy=_policy(),
        drivers=[_driver_summary(summary, driver) for driver in field.drivers],
        source=summary.source,
    )


def load_pace_comparison(
    year: int, event_name: str, session_name: str, driver_a: str, driver_b: str
) -> DriverPaceComparisonResponse:
    summary, field = _load_analysis(year, event_name, session_name)
    a = _find_driver(field, driver_a)
    b = _find_driver(field, driver_b)
    if a.metrics is None or b.metrics is None:
        comparison = DriverPaceComparisonResult(
            status="insufficient_data",
            delta_ms=None,
            outcome=None,
            faster_driver_number=None,
        )
    else:
        # Both operands are already published by the single field analysis.
        delta = a.metrics.median_lap_time_ms - b.metrics.median_lap_time_ms
        outcome = "tied"
        winner = None
        if delta < 0:
            outcome, winner = "driver_a_faster", driver_a
        elif delta > 0:
            outcome, winner = "driver_b_faster", driver_b
        comparison = DriverPaceComparisonResult(
            status="available",
            delta_ms=delta,
            outcome=outcome,
            faster_driver_number=winner,
        )
    return DriverPaceComparisonResponse(
        context=_context(summary),
        policy=_policy(),
        driver_a=_driver_summary(summary, a),
        driver_b=_driver_summary(summary, b),
        comparison=comparison,
        source=summary.source,
    )


def _load_analysis(
    year: int, event_name: str, session_name: str
) -> tuple[SessionSummary, lap_analytics.SessionFieldAnalysis]:
    session = f1_data.load_session(year, event_name, session_name)
    inputs = f1_data.map_lap_inputs(session)
    summary = f1_data.map_session_summary(session)
    return summary, lap_analytics.analyze_session_field(inputs)


def _find_driver(
    field: lap_analytics.SessionFieldAnalysis, driver_number: str
) -> lap_analytics.DriverAnalysis:
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
    return driver


def _driver_summary(
    summary: SessionSummary, analysis: lap_analytics.DriverAnalysis
) -> DriverPaceSummary:
    sample = analysis.sample
    return DriverPaceSummary(
        driver=AnalyticsDriverIdentity(**asdict(analysis.driver)),
        status="available" if analysis.metrics is not None else "insufficient_data",
        policy_id=lap_analytics.POLICY_ID,
        sample=LapSample(
            source_lap_count=sample.source_lap_count,
            representative_lap_count=sample.representative_lap_count,
            excluded_lap_count=sample.excluded_lap_count,
            exclusions=ExclusionCounts(**dict(sample.exclusions)),
        ),
        metrics=PaceMetrics(**asdict(analysis.metrics)) if analysis.metrics else None,
        rank=analysis.rank,
        tied=analysis.tied,
        delta_to_best_ms=analysis.delta_to_best_ms,
        source=summary.source,
    )


def _context(summary: SessionSummary) -> AnalyticsSessionContext:
    return AnalyticsSessionContext(
        year=summary.year,
        event=summary.event,
        session=summary.session,
        circuit=summary.circuit,
    )


def _policy() -> RepresentativeRacePacePolicy:
    return RepresentativeRacePacePolicy.model_validate(
        asdict(lap_analytics.RACE_PACE_POLICY)
    )


def _lap_response(decision: lap_analytics.ClassifiedLap) -> LapClassification:
    lap = decision.lap
    return LapClassification(
        source_order=lap.source_order,
        lap_number=lap.lap_number,
        lap_time_ms=(
            lap_analytics.publish_milliseconds(lap.lap_time_ns)
            if lap.lap_time_ns is not None
            else None
        ),
        classification="representative"
        if decision.primary_exclusion_reason is None
        else "excluded",
        primary_exclusion_reason=decision.primary_exclusion_reason,
        track_status_codes=list(lap.track_status_codes)
        if lap.track_status_codes is not None
        else None,
        disruptive_statuses=list(decision.disruptive_statuses),
        is_accurate=lap.is_accurate,
        compound=lap.compound,
    )
