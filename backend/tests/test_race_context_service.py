"""Offline service orchestration and passive central-result projection."""

import ast
import importlib
import importlib.util
import inspect
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from pydantic import ValidationError

from app.analytics import race_context_analytics as analytics
from app.data import f1_data
from app.models import race_context_models as public
from app.services import session_support
from app.services.pace_service import DriverNotFoundError

SELECTORS = (2025, "italian-grand-prix", "race")
SOURCE = (2025, "Italian Grand Prix", "Race")


def service():
    name = "app.services.race_context_service"
    assert importlib.util.find_spec(name) is not None, "Group E service is missing"
    return importlib.import_module(name)


def invoke(module, operation, driver="4", selectors=SELECTORS):
    if operation == "session":
        return module.load_session_race_context(*selectors)
    return module.load_driver_race_context(*selectors, driver)


@pytest.fixture
def source_session(race_context_session_factory, pace_session_factory):
    source = race_context_session_factory()
    return pace_session_factory(laps=source.laps, results=source.results)


@pytest.fixture
def projection_inputs(source_session):
    inputs = f1_data.map_race_context_inputs(source_session)
    template = inputs.lap_rows[1]

    def value(ns):
        return analytics.NormalizedValue(analytics.NormalizedValueState.AVAILABLE, ns)

    absent = analytics.NormalizedValue(analytics.NormalizedValueState.ABSENT)
    rows = [inputs.lap_rows[0]]
    # Leading exit and complete entry collide publicly, while exact order differs.
    for number, entry, exit_, generated in (
        (1, None, 1_100_000, False),
        (2, 1_200_000, None, False),
        (3, None, 2_600_000, False),
        (4, 5_000_000, None, False),
        (5, 6_000_000, None, False),
        (6, None, 7_000_000, False),
        (7, 8_000_000, None, False),
        (8, 9_000_000, None, True),
    ):
        rows.append(
            replace(
                template,
                source_occurrence=number + 1,
                lap_number=value(number),
                lap_completion_time_ns=value(number * 100_000_000_000),
                pit_entry_time_ns=value(entry) if entry is not None else absent,
                pit_exit_time_ns=value(exit_) if exit_ is not None else absent,
                provider_generated=generated,
                reported_compound="HARD" if number < 3 else "SOFT",
                reported_stint=1 if number < 3 else 2,
            )
        )
    invalid = replace(
        template,
        driver_number="27",
        source_occurrence=10,
        lap_number=analytics.NormalizedValue(analytics.NormalizedValueState.INVALID),
        pit_entry_time_ns=absent,
        pit_exit_time_ns=absent,
    )
    extra = replace(
        inputs.participants[2],
        identity=analytics.RaceContextParticipantIdentity("10"),
        result_evidence_status=analytics.EvidenceStatus.CONFLICTING,
        classified_position=None,
    )
    nonnumeric = replace(extra, identity=analytics.RaceContextParticipantIdentity("A"))
    inputs = replace(
        inputs,
        participants=(*inputs.participants, extra, nonnumeric),
        lap_rows=(*rows, invalid, replace(invalid, source_occurrence=11)),
    )
    field = analytics.analyze_race_context(inputs)
    return inputs, f1_data.map_session_summary(source_session), field


def install_pipeline(monkeypatch, source, inputs, summary, field):
    trace = Mock()
    collaborators = (
        (
            session_support,
            "resolve_supported_session",
            Mock(wraps=session_support.resolve_supported_session),
        ),
        (f1_data, "load_session", Mock(return_value=source)),
        (f1_data, "map_race_context_inputs", Mock(return_value=inputs)),
        (f1_data, "map_session_summary", Mock(return_value=summary)),
        (analytics, "analyze_race_context", Mock(return_value=field)),
    )
    for owner, name, mock in collaborators:
        trace.attach_mock(mock, name)
        monkeypatch.setattr(owner, name, mock)
    return trace


def assert_pipeline(trace, source, inputs):
    assert trace.mock_calls == [
        call.resolve_supported_session(*SELECTORS),
        call.load_session(*SOURCE),
        call.map_race_context_inputs(source),
        call.map_session_summary(source),
        call.analyze_race_context(inputs),
    ]
    assert trace.map_race_context_inputs.call_args.args[0] is source
    assert trace.map_session_summary.call_args.args[0] is source
    assert trace.analyze_race_context.call_args.args[0] is inputs


@pytest.mark.parametrize("operation", ["session", "driver"])
def test_provider_identifiers_come_from_shared_policy(
    monkeypatch, source_session, projection_inputs, operation
):
    module = service()
    inputs, summary, field = projection_inputs
    trace = install_pipeline(monkeypatch, source_session, inputs, summary, field)
    identifiers = (2030, "Controlled provider event", "Controlled provider session")
    trace.resolve_supported_session.side_effect = None
    trace.resolve_supported_session.return_value = identifiers
    invoke(module, operation)
    trace.resolve_supported_session.assert_called_once_with(*SELECTORS)
    trace.load_session.assert_called_once_with(*identifiers)
    trace.map_race_context_inputs.assert_called_once_with(source_session)
    trace.map_session_summary.assert_called_once_with(source_session)
    trace.analyze_race_context.assert_called_once_with(inputs)


@pytest.mark.parametrize("operation", ["session", "driver"])
@pytest.mark.parametrize(
    "selectors",
    [
        (2024, "italian-grand-prix", "race"),
        (2025, "monaco-grand-prix", "race"),
        (2025, "italian-grand-prix", "qualifying"),
        (2025, "Italian-Grand-Prix", "race"),
        SOURCE,
    ],
)
def test_unsupported_selectors_block_all_provider_work(
    monkeypatch, operation, selectors
):
    module = service()
    trace = install_pipeline(monkeypatch, object(), object(), object(), object())
    with pytest.raises(
        module.SessionNotSupportedError, match="The requested session is not supported"
    ):
        invoke(module, operation, selectors=selectors)
    assert trace.mock_calls == [call.resolve_supported_session(*selectors)]


@pytest.mark.parametrize("operation", ["session", "driver"])
def test_one_pipeline_projects_the_complete_central_result(
    monkeypatch, source_session, projection_inputs, operation
):
    module = service()
    inputs, summary, field = projection_inputs
    trace = install_pipeline(monkeypatch, source_session, inputs, summary, field)
    for name in (
        "analyze_lap_contexts",
        "analyze_complete_pit_visits",
        "analyze_pit_evidence",
    ):
        monkeypatch.setattr(
            analytics, name, Mock(side_effect=AssertionError("View-specific analytics"))
        )
    result = invoke(module, operation)
    assert_pipeline(trace, source_session, inputs)
    assert result.context.event == summary.event
    assert result.context.session == summary.session
    assert result.context.circuit == summary.circuit
    assert result.context.year == summary.year
    assert result.source == summary.source
    if operation == "session":
        assert isinstance(result, public.SessionRaceContextResponse)
        assert [item.driver.driver_number for item in result.participants] == [
            "1",
            "4",
            "10",
            "27",
            "A",
        ]
        assert all(
            set(item.model_dump())
            == {
                "driver",
                "classification",
                "latest_lap_context",
                "pit_evidence_counts",
                "unassociated_evidence_count",
            }
            for item in result.participants
        )
        selected = result.participants[1]
    else:
        assert isinstance(result, public.DriverRaceContextResponse)
        selected = result.participant
        expected = field.participants[1]
        assert [lap.lap_number for lap in result.lap_contexts] == [
            lap.lap_number for lap in expected.lap_contexts
        ]
        assert [item.state for item in result.pit_evidence] == [
            item.state for item in expected.pit_evidence
        ]
        assert set(item.state for item in result.pit_evidence) == set(
            public.PitEvidenceState
        )
        for actual, domain in zip(
            result.pit_evidence, expected.pit_evidence, strict=True
        ):
            assert actual.source_boundary_count == domain.source_boundary_count
            assert actual.entry_session_time_ms == domain.entry_session_time_ms
            assert actual.exit_session_time_ms == domain.exit_session_time_ms
            assert actual.entry_to_exit_elapsed_ms == domain.entry_to_exit_elapsed_ms
            assert actual.reported_compound_changed == domain.reported_compound_changed
            assert actual.reported_stint_changed == domain.reported_stint_changed
    assert selected.latest_lap_context.lap_number == 7
    assert selected.pit_evidence_counts.total == len(field.participants[1].pit_evidence)
    assert selected.classification.completed_laps == 53
    assert (
        selected.latest_lap_context.track_status.track_statuses
        == field.participants[1].latest_lap_context.track_status.statuses
    )


@pytest.mark.parametrize("number", ["1", "4", "10", "27", "A"])
def test_session_and_detail_share_summary_facts(
    monkeypatch, source_session, projection_inputs, number
):
    module = service()
    inputs, summary, field = projection_inputs
    trace = install_pipeline(monkeypatch, source_session, inputs, summary, field)
    compact = module.load_session_race_context(*SELECTORS)
    assert_pipeline(trace, source_session, inputs)
    trace.reset_mock()
    detail = module.load_driver_race_context(*SELECTORS, number)
    assert_pipeline(trace, source_session, inputs)
    expected = next(
        item for item in compact.participants if item.driver.driver_number == number
    )
    assert detail.participant == expected
    assert detail.context == compact.context and detail.source == compact.source
    if number in ("10", "27", "A"):
        assert detail.participant.latest_lap_context is None
        assert detail.lap_contexts == detail.pit_evidence == ()
        assert detail.participant.pit_evidence_counts.total == 0
        assert detail.participant.unassociated_evidence_count == (
            2 if number == "27" else 0
        )


@pytest.mark.parametrize("operation", ["session", "driver"])
def test_projects_published_values_not_exact_recalculation(
    monkeypatch, source_session, projection_inputs, operation
):
    module = service()
    inputs, summary, field = projection_inputs
    selected = field.participants[1]
    first = replace(selected.lap_contexts[0], equal_distance_time_deficit_ms=12345)
    pits = tuple(
        replace(item, entry_to_exit_elapsed_ms=777)
        if item.state == analytics.PitEvidenceState.COMPLETE
        else item
        for item in selected.pit_evidence
    )
    selected = replace(
        selected, lap_contexts=(first, *selected.lap_contexts[1:]), pit_evidence=pits
    )
    field = replace(
        field, participants=(field.participants[0], selected, *field.participants[2:])
    )
    install_pipeline(monkeypatch, source_session, inputs, summary, field)
    result = invoke(module, operation)
    if operation == "driver":
        assert result.lap_contexts[0].equal_distance_time_deficit_ms == 12345
        assert (
            next(
                item.entry_to_exit_elapsed_ms
                for item in result.pit_evidence
                if item.state == "complete"
            )
            == 777
        )
        assert result.lap_contexts[-1].provider_generated is True
    else:
        assert result.participants[1].latest_lap_context.lap_number == 7


def test_compact_projection_reads_counts_and_latest_directly(
    monkeypatch, source_session, projection_inputs
):
    module = service()
    inputs, summary, field = projection_inputs
    selected = field.participants[1]
    # A collaborator stub distinguishes direct projection from recount/reselection.
    supplied = SimpleNamespace(
        **dict(
            vars(selected),
            latest_lap_context=None,
            pit_evidence_counts=analytics.PitEvidenceCounts(11, 12, 13, 14, 15, 65),
        )
    )
    field = SimpleNamespace(
        participants=(field.participants[0], supplied, *field.participants[2:])
    )
    trace = install_pipeline(monkeypatch, source_session, inputs, summary, field)
    compact = module.load_session_race_context(*SELECTORS)
    assert_pipeline(trace, source_session, inputs)
    assert compact.participants[1].latest_lap_context is None
    assert compact.participants[1].pit_evidence_counts.model_dump() == {
        "total": 65,
        "complete": 11,
        "unpaired_entry": 12,
        "unpaired_exit": 13,
        "conflicting": 14,
        "unavailable": 15,
    }
    trace.reset_mock()
    # Driver-detail validation must reject mismatched counts, never repair them.
    with pytest.raises(ValidationError, match="Summary counts must match"):
        module.load_driver_race_context(*SELECTORS, "4")
    assert_pipeline(trace, source_session, inputs)


@pytest.mark.parametrize("operation", ["session", "driver"])
def test_unavailable_track_context_is_projected_without_invention(
    monkeypatch, source_session, projection_inputs, operation
):
    module = service()
    inputs, summary, field = projection_inputs
    leader = field.participants[0]
    lap = replace(
        leader.lap_contexts[0],
        track_status=analytics.NormalizedTrackStatusEvidence(
            analytics.TrackStatusAvailability.UNAVAILABLE, (), None
        ),
    )
    leader = replace(leader, latest_lap_context=lap, lap_contexts=(lap,))
    field = replace(field, participants=(leader, *field.participants[1:]))
    install_pipeline(monkeypatch, source_session, inputs, summary, field)
    result = invoke(module, operation, driver="1")
    participant = (
        result.participants[0] if operation == "session" else result.participant
    )
    assert participant.latest_lap_context.track_status.model_dump(mode="json") == {
        "availability": "unavailable",
        "track_statuses": [],
        "is_disrupted": None,
    }


def test_unknown_driver_requires_complete_analysis(
    monkeypatch, source_session, projection_inputs
):
    inputs, summary, field = projection_inputs
    trace = install_pipeline(monkeypatch, source_session, inputs, summary, field)
    with pytest.raises(
        DriverNotFoundError, match="The requested driver is not in the session results"
    ):
        invoke(service(), "driver", driver="999")
    assert_pipeline(trace, source_session, inputs)


@pytest.mark.parametrize("operation", ["session", "driver"])
@pytest.mark.parametrize(
    "stage",
    [
        "load_session",
        "map_race_context_inputs",
        "map_session_summary",
        "analyze_race_context",
    ],
)
@pytest.mark.parametrize("error", [f1_data.DataSourceUnavailableError, RuntimeError])
def test_failures_propagate_without_translation_or_retry(
    monkeypatch, source_session, projection_inputs, operation, stage, error
):
    module = service()
    inputs, summary, field = projection_inputs
    trace = install_pipeline(monkeypatch, source_session, inputs, summary, field)
    failure = error("controlled private failure")
    getattr(trace, stage).side_effect = failure
    with pytest.raises(error) as caught:
        invoke(module, operation)
    assert caught.value is failure
    names = [
        "resolve_supported_session",
        "load_session",
        "map_race_context_inputs",
        "map_session_summary",
        "analyze_race_context",
    ]
    assert [entry[0] for entry in trace.mock_calls] == names[: names.index(stage) + 1]


@pytest.mark.parametrize("operation", ["session", "driver"])
def test_real_mappers_and_analytics_compose(monkeypatch, source_session, operation):
    module = service()
    loader = Mock(return_value=source_session)
    monkeypatch.setattr(f1_data, "load_session", loader)
    result = invoke(module, operation)
    loader.assert_called_once_with(*SOURCE)
    if operation == "driver":
        assert result.pit_evidence[0].state == "complete"
        assert result.participant.latest_lap_context.lap_number == 1


@pytest.mark.parametrize("operation", ["session", "driver"])
def test_known_driver_with_only_unavailable_evidence_is_retained(
    monkeypatch, source_session, operation
):
    module = service()
    source_session.laps["FastF1Generated"] = True
    source_session.laps["TrackStatus"] = None
    loader = Mock(return_value=source_session)
    monkeypatch.setattr(f1_data, "load_session", loader)
    result = invoke(module, operation)
    loader.assert_called_once_with(*SOURCE)
    participant = (
        result.participants[1] if operation == "session" else result.participant
    )
    assert participant.driver.driver_number == "4"
    assert participant.latest_lap_context is None
    assert participant.pit_evidence_counts.total == 2
    assert participant.pit_evidence_counts.unavailable == 2
    if operation == "driver":
        assert len(result.lap_contexts) == 1
        assert len(result.pit_evidence) == 2
        assert result.lap_contexts[0].track_status.track_statuses == ()
        assert result.lap_contexts[0].track_status.is_disrupted is None
        assert all(item.state == "unavailable" for item in result.pit_evidence)


def test_service_has_only_orchestration_and_projection_dependencies():
    tree = ast.parse(inspect.getsource(service()))
    imports = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    imports.extend(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any(
        name.startswith(("app.main", "fastapi", "fastf1", "pandas", "numpy"))
        for name in imports
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            assert not (
                isinstance(node.func, ast.Name)
                and node.func.id in {"sorted", "Counter", "round"}
            )
            assert not (
                isinstance(node.func, ast.Attribute)
                and node.func.attr
                in {"sort", "model_construct", "publish_milliseconds"}
            )
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "analytics"
            ):
                assert node.func.attr == "analyze_race_context"
