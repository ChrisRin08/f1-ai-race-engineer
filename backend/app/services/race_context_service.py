"""One-snapshot race-context orchestration and passive public projections."""

from app.analytics import race_context_analytics as analytics
from app.data import f1_data
from app.models import race_context_models as models
from app.models.pace_models import AnalyticsSessionContext
from app.models.session_models import SessionSummary
from app.services import session_support
from app.services.pace_service import DriverNotFoundError


class SessionNotSupportedError(LookupError):
    """The requested selectors are outside the established session boundary."""


def load_session_race_context(
    year: int, event: str, session: str
) -> models.SessionRaceContextResponse:
    summary, analysis = _load_analysis(year, event, session)
    return models.SessionRaceContextResponse(
        context=_context(summary),
        participants=tuple(_participant(item) for item in analysis.participants),
        source=summary.source,
    )


def load_driver_race_context(
    year: int, event: str, session: str, driver_number: str
) -> models.DriverRaceContextResponse:
    summary, analysis = _load_analysis(year, event, session)
    participant = next(
        (
            item
            for item in analysis.participants
            if item.identity.driver_number == driver_number
        ),
        None,
    )
    if participant is None:
        raise DriverNotFoundError("The requested driver is not in the session results.")
    return models.DriverRaceContextResponse(
        context=_context(summary),
        participant=_participant(participant),
        lap_contexts=tuple(_lap_context(lap) for lap in participant.lap_contexts),
        pit_evidence=tuple(_pit_evidence(item) for item in participant.pit_evidence),
        source=summary.source,
    )


def _load_analysis(
    year: int, event: str, session: str
) -> tuple[SessionSummary, analytics.SessionRaceContextAnalysis]:
    source_identifiers = session_support.resolve_supported_session(year, event, session)
    if source_identifiers is None:
        raise SessionNotSupportedError("The requested session is not supported.")
    snapshot = f1_data.load_session(*source_identifiers)
    inputs = f1_data.map_race_context_inputs(snapshot)
    summary = f1_data.map_session_summary(snapshot)
    return summary, analytics.analyze_race_context(inputs)


def _context(summary: SessionSummary) -> AnalyticsSessionContext:
    return AnalyticsSessionContext(
        year=summary.year,
        event=summary.event,
        session=summary.session,
        circuit=summary.circuit,
    )


def _participant(
    participant: analytics.ParticipantRaceContextAnalysis,
) -> models.SessionRaceContextParticipant:
    identity = participant.identity
    classification = participant.classification
    counts = participant.pit_evidence_counts
    return models.SessionRaceContextParticipant(
        driver=models.RaceContextParticipantIdentity(
            driver_number=identity.driver_number,
            abbreviation=identity.abbreviation,
            full_name=identity.full_name,
            team_name=identity.team_name,
        ),
        classification=models.RaceClassificationContext(
            evidence_status=classification.evidence_status,
            source_evidence_count=classification.source_evidence_count,
            finish_position=classification.finish_position,
            classified_position=classification.classified_position,
            status=classification.status,
            completed_laps=classification.completed_laps,
        ),
        latest_lap_context=(
            _lap_context(participant.latest_lap_context)
            if participant.latest_lap_context is not None
            else None
        ),
        pit_evidence_counts=models.PitEvidenceCounts(
            total=counts.total,
            complete=counts.complete,
            unpaired_entry=counts.unpaired_entry,
            unpaired_exit=counts.unpaired_exit,
            conflicting=counts.conflicting,
            unavailable=counts.unavailable,
        ),
        unassociated_evidence_count=participant.unassociated_evidence_count,
    )


def _lap_context(lap: analytics.ConsolidatedLapContext) -> models.LapCompletionContext:
    leader = lap.leader_reference
    return models.LapCompletionContext(
        driver_number=lap.driver_number,
        lap_number=lap.lap_number,
        evidence_status=lap.evidence_status,
        source_evidence_count=lap.source_evidence_count,
        lap_completion_session_time_ms=lap.completion_time_ms,
        lap_completion_position=lap.completion_position,
        track_status=models.TrackStatusContext(
            availability=lap.track_status.availability,
            track_statuses=lap.track_status.statuses,
            is_disrupted=lap.track_status.is_disrupted,
        ),
        provider_generated=lap.provider_generated,
        reported_compound=lap.reported_compound,
        reported_stint=lap.reported_stint,
        leader_reference=(
            models.LeaderReference(
                driver_number=leader.driver_number,
                lap_number=leader.lap_number,
                lap_completion_session_time_ms=leader.completion_time_ms,
            )
            if leader is not None
            else None
        ),
        laps_behind_status=lap.laps_behind_status,
        laps_behind=lap.laps_behind,
        equal_distance_time_deficit_status=lap.equal_distance_time_deficit_status,
        equal_distance_time_deficit_ms=lap.equal_distance_time_deficit_ms,
    )


def _lap_reference(
    reference: analytics.LapContextReference | None,
) -> models.LapContextReference | None:
    return (
        models.LapContextReference(
            driver_number=reference.driver_number, lap_number=reference.lap_number
        )
        if reference is not None
        else None
    )


def _pit_boundary(boundary: analytics.PitBoundary) -> models.PitBoundaryEvidence:
    return models.PitBoundaryEvidence(
        kind=boundary.kind,
        evidence_status=boundary.evidence_status,
        source_evidence_count=boundary.source_evidence_count,
        lap_number=boundary.lap_number,
        entry_session_time_ms=(
            boundary.session_time_ms
            if boundary.kind == analytics.PitBoundaryKind.ENTRY
            else None
        ),
        exit_session_time_ms=(
            boundary.session_time_ms
            if boundary.kind == analytics.PitBoundaryKind.EXIT
            else None
        ),
        lap_context_reference=_lap_reference(boundary.lap_context_reference),
    )


def _pit_transition(
    context: analytics.PitTransitionContext | None,
) -> models.PitTransitionContext | None:
    return (
        models.PitTransitionContext(
            availability=context.availability,
            lap_context_reference=_lap_reference(context.lap_context_reference),
            reported_compound=context.reported_compound,
            reported_stint=context.reported_stint,
        )
        if context is not None
        else None
    )


def _pit_evidence(evidence: analytics.PitLaneEvidence) -> models.PitLaneEvidence:
    return models.PitLaneEvidence(
        state=evidence.state,
        boundaries=tuple(_pit_boundary(boundary) for boundary in evidence.boundaries),
        source_boundary_count=evidence.source_boundary_count,
        entry_lap_number=evidence.entry_lap_number,
        exit_lap_number=evidence.exit_lap_number,
        entry_session_time_ms=evidence.entry_session_time_ms,
        exit_session_time_ms=evidence.exit_session_time_ms,
        entry_to_exit_elapsed_ms=evidence.entry_to_exit_elapsed_ms,
        entry_context=_pit_transition(evidence.entry_context),
        exit_context=_pit_transition(evidence.exit_context),
        reported_compound_changed=evidence.reported_compound_changed,
        reported_stint_changed=evidence.reported_stint_changed,
    )
