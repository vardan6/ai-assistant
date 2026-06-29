from types import SimpleNamespace

import pytest

from app.ai import AgentResult, UsageSnapshot, run_agent_loop
from app.ai.intent_schema import coerce_intent
from app.config import load_config
from app.data import PandasDataSource
from app.pipeline import Pipeline, _build_synthesis_prompt, select_tool_names
from app.schema_card import build_schema_card
from app.tools import ToolContext, build_registry


@pytest.fixture(scope="module")
def registry():
    return build_registry()


@pytest.fixture(scope="module")
def ctx():
    return ToolContext(data=PandasDataSource(load_config().csv_dir))


@pytest.mark.parametrize(
    ("tool_name", "args", "count_key"),
    [
        ("plants", {"status": "offline"}, "matched"),
        ("inverters", {"status": "fault"}, "matched"),
        ("alerts", {"severity": "critical"}, "matched"),
        ("anomalies", {"plant": "Tamil Nadu PV Plant"}, "matched"),
        ("maintenance", {"status": "in_progress"}, "matched"),
        ("generation_readings", {"plant": "Rajasthan Solar Park", "limit": 2}, "matched"),
        ("weather_readings", {"plant": "4135001", "limit": 2}, "matched"),
    ],
)
def test_per_table_tools_return_structured_dicts(registry, ctx, tool_name, args, count_key):
    result = registry.invoke(tool_name, args, ctx)
    assert result["ok"] is True
    assert result[count_key] > 0


def test_gated_tool_selection_uses_generous_subset_and_resolvers(registry):
    available = registry.names()
    assert select_tool_names({"types": ["A"]}, gating_mode="gated", available_tools=available) == [
        "alerts", "inverters", "maintenance", "plants"
    ]
    assert select_tool_names({"types": ["B"]}, gating_mode="gated", available_tools=available) == [
        "alerts",
        "anomalies",
        "daily_yield",
        "performance_ratio",
        "mttr",
        "total_yield",
        "generation_readings",
        "inverters",
        "plants",
        "weather_readings",
    ]
    assert select_tool_names({"types": ["C"]}, gating_mode="gated", available_tools=available) == [
        "anomalies", "inverters", "plants"
    ]
    assert select_tool_names(
        {"types": ["B"], "metric": "tariff_usd_per_kwh", "summary": "Highest feed-in tariff"},
        gating_mode="gated",
        available_tools=available,
    ) == ["inverters", "plants"]
    assert select_tool_names(
        {"types": ["B"], "metric": "performance_ratio", "summary": "Which plant is performing worst right now?"},
        gating_mode="gated",
        available_tools=available,
    ) == ["performance_ratio", "inverters", "plants"]
    assert select_tool_names({"types": []}, gating_mode="gated", available_tools=available) == [
        "inverters", "plants"
    ]
    assert select_tool_names({"types": ["C"]}, gating_mode="bind_all", available_tools=available) == available


def test_synthesis_prompt_includes_generated_schema_card():
    prompt = _build_synthesis_prompt(
        "2026-06-22T10:00:00",
        "2026-06-22T10:00:00",
        use_reference_now_anchor=True,
        schema_card=build_schema_card(),
        intent={"types": ["B"], "metric": "tariff_usd_per_kwh"},
    )

    assert 'timestamp: 2026-06-22T10:00:00. This is NOT the real-world date.' in prompt
    assert "Schema card (generated from docs/dataset-analysis.md" in prompt
    assert "## Join cardinality (fan-out)" in prompt
    assert "## Entity resolver index" in prompt
    assert "## Vocabulary coverage map" in prompt
    assert "## Measure semantics (aggregation rules)" in prompt
    assert "feed-in tariff questions" in prompt


def test_synthesis_prompt_can_switch_relative_time_to_wall_clock():
    prompt = _build_synthesis_prompt(
        "2026-06-22T10:00:00",
        "2026-06-30T12:00:00",
        use_reference_now_anchor=False,
        schema_card=build_schema_card(),
        intent={"types": ["B"], "metric": "performance_ratio"},
    )

    assert 'real-world wall clock time: 2026-06-30T12:00:00' in prompt
    assert "Do NOT anchor them to the dataset's latest timestamp (2026-06-22T10:00:00)." in prompt
    assert 'window="last_week"' in prompt


def test_intent_coercion_recovers_metric_from_question_phrases():
    intent = coerce_intent(
        {
            "types": ["B"],
            "entities": {},
            "time_range": None,
            "metric": "",
            "out_of_scope": False,
            "confidence": 0.7,
            "summary": "",
        },
        question="Which plant has the highest feed-in tariff?",
    )

    assert intent["metric"] == "tariff_usd_per_kwh"
    assert intent["types"] == ["B"]


def test_loop_supports_resolver_then_anomalies_chain(registry, ctx):
    class ScriptedModel:
        def __init__(self):
            self._responses = [
                SimpleNamespace(content="", tool_calls=[{"name": "plants", "args": {"plant": "Tamil Nadu PV Plant"}, "id": "call_1"}]),
                SimpleNamespace(content="", tool_calls=[{"name": "anomalies", "args": {"plant": "4137001", "status": "open"}, "id": "call_2"}]),
                SimpleNamespace(content="Tamil Nadu PV Plant has open anomalies.", tool_calls=[]),
            ]
            self._i = 0
            self.bound_schemas = None

        def bind_tools(self, schemas):
            self.bound_schemas = schemas
            return self

        def invoke(self, messages):  # noqa: ARG002
            resp = self._responses[self._i]
            self._i += 1
            return resp

    model = ScriptedModel()
    result = run_agent_loop(
        model,
        system_prompt="sys",
        user_prompt="show open anomalies for Tamil Nadu PV Plant",
        registry=registry,
        context=ctx,
        tool_names=select_tool_names({"types": ["C"]}, gating_mode="gated", available_tools=registry.names()),
    )
    assert [call.name for call in result.tool_calls] == ["plants", "anomalies"]
    assert result.answer == "Tamil Nadu PV Plant has open anomalies."
    assert [schema["function"]["name"] for schema in model.bound_schemas] == ["anomalies", "inverters", "plants"]


def test_pipeline_smalltalk_fast_path_skips_provider_resolution(monkeypatch):
    pipeline = Pipeline(load_config())

    def boom(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("provider resolution should not run for smalltalk")

    monkeypatch.setattr("app.pipeline.resolve_provider", boom)

    result = pipeline.answer("hello")

    assert result.answer.startswith("Hi!")
    assert result.fast_path == "smalltalk"
    assert result.stop_reason == "fast_path"
    assert [event.kind for event in result.trace_events] == ["intent_started", "intent_finished"]


def test_pipeline_empty_prompt_fast_path_skips_provider_resolution(monkeypatch):
    pipeline = Pipeline(load_config())

    def boom(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("provider resolution should not run for empty prompts")

    monkeypatch.setattr("app.pipeline.resolve_provider", boom)

    result = pipeline.answer("   ")

    assert result.answer == "Please ask a question about the solar operations dataset."
    assert result.fast_path == "empty"
    assert result.intent_meta["parse_errors"] == ["empty prompt"]
    assert result.stop_reason == "fast_path"


def test_pipeline_replaces_empty_iteration_limit_answer(monkeypatch):
    pipeline = Pipeline(load_config())

    class StubIntentService:
        def parse(self, user_prompt, *, model, context_summary=""):  # noqa: ARG002
            return {
                "intent": {
                    "types": ["A"],
                    "entities": {"plants": [], "inverters": [], "alerts": [], "anomalies": [], "maintenance": []},
                    "time_range": "today",
                    "metric": "status",
                    "out_of_scope": False,
                    "confidence": 0.9,
                    "summary": "Plant status",
                },
                "parse_errors": [],
                "provider_name": "fake-intent-model",
                "latency_ms": 5,
                "fast_path": "",
                "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            }

    def fake_resolve_provider(config, *, purpose, provider_id="", secret_resolver=None):  # noqa: ARG001
        return SimpleNamespace(model=SimpleNamespace(model_name=f"{purpose}-model"))

    def fake_run_agent_loop(model, *, system_prompt, user_prompt, registry, context, tool_names, event_handler=None):  # noqa: ARG001
        return AgentResult(
            answer="",
            tool_calls=[],
            iterations=6,
            stop_reason="iteration_limit",
            trace_events=[],
            usage=UsageSnapshot(),
            elapsed_ms=15,
            model_name="synthesis-model",
        )

    pipeline._intent_service = StubIntentService()
    monkeypatch.setattr("app.pipeline.resolve_provider", fake_resolve_provider)
    monkeypatch.setattr("app.pipeline.run_agent_loop", fake_run_agent_loop)

    result = pipeline.answer("Which plants are offline?")

    assert result.stop_reason == "iteration_limit"
    assert result.answer == (
        "I couldn't complete that request within the tool step budget. Please try a narrower question "
        "or specify the plant, inverter, metric, or time range."
    )
    assert [event.kind for event in result.trace_events] == [
        "intent_started",
        "intent_finished",
        "synthesis_started",
        "synthesis_degraded",
    ]


def test_pipeline_emits_trace_for_gated_empty_classification_fallback(monkeypatch):
    pipeline = Pipeline(load_config())

    class StubIntentService:
        def parse(self, user_prompt, *, model, context_summary=""):  # noqa: ARG002
            return {
                "intent": {
                    "types": [],
                    "entities": {"plants": [], "inverters": [], "alerts": [], "anomalies": [], "maintenance": []},
                    "time_range": "",
                    "metric": "",
                    "out_of_scope": False,
                    "confidence": 0.0,
                    "summary": "",
                },
                "parse_errors": ["could not parse intent"],
                "provider_name": "fake-intent-model",
                "latency_ms": 5,
                "fast_path": "",
                "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            }

    def fake_resolve_provider(config, *, purpose, provider_id="", secret_resolver=None):  # noqa: ARG001
        return SimpleNamespace(model=SimpleNamespace(model_name=f"{purpose}-model"))

    def fake_run_agent_loop(model, *, system_prompt, user_prompt, registry, context, tool_names, event_handler=None):  # noqa: ARG001
        assert tool_names == ["inverters", "plants"]
        return AgentResult(
            answer="I couldn't classify that cleanly, so I checked the plant and inverter records first.",
            tool_calls=[],
            iterations=1,
            stop_reason="final_answer",
            trace_events=[],
            usage=UsageSnapshot(),
            elapsed_ms=15,
            model_name="synthesis-model",
        )

    pipeline._intent_service = StubIntentService()
    monkeypatch.setattr("app.pipeline.resolve_provider", fake_resolve_provider)
    monkeypatch.setattr("app.pipeline.run_agent_loop", fake_run_agent_loop)

    result = pipeline.answer("Tell me what is going on")

    assert result.bound_tools == ["inverters", "plants"]
    assert [event.kind for event in result.trace_events] == [
        "intent_started",
        "intent_finished",
        "gating_fallback",
        "synthesis_started",
    ]
