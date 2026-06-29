from __future__ import annotations

from types import SimpleNamespace

from app.ai import run_agent_loop
from app.case_replay import ReplaySpec, build_replay_specs, evaluate_payload
from app.config import load_config
from app.data import PandasDataSource
from app.pipeline import Pipeline
from app.tools import ToolContext, build_registry
from scripts.golden_answers import build as build_oracle


def test_golden_answers_pin_section3_values():
    oracle = build_oracle()
    case_oracle = oracle["case_oracle"]

    assert case_oracle["P4"]["answer"] == {
        "plant": "Rajasthan Solar Park",
        "tariff_usd_per_kwh": 0.052,
    }
    assert case_oracle["AL3"]["answer"]["count"] == 15
    assert case_oracle["AN6"]["answer"]["status_counts"] == {
        "monitoring": 3,
        "open": 7,
        "scheduled_repair": 5,
    }
    assert case_oracle["X4"]["answer"]["plant"] == "Rajasthan Solar Park"
    assert case_oracle["X4"]["answer"]["mean_performance_ratio"] == 0.9077


def test_replay_specs_cover_oracle_and_graceful_degradation_cases():
    specs = build_replay_specs()

    assert {"D6", "X6", "AN6", "X4"}.issubset(specs)
    assert specs["D6"].expected_stop_reason == "out_of_scope"
    assert "which plant" in specs["X6"].required_text
    assert specs["AN6"].required_bound_tools == ("anomalies", "inverters", "plants")
    assert specs["AN6"].require_structured_tool_results is True


def test_evaluate_payload_checks_tools_text_and_numbers():
    spec = ReplaySpec(
        case_id="demo",
        question="demo question",
        expected_intent_types=("B", "C"),
        required_tools=("plants", "anomalies"),
        required_text=("rajasthan",),
        required_numbers=(7.0, 123354.2),
        number_tolerance=0.1,
    )
    payload = {
        "answer": "Rajasthan has 7 open anomalies and average daily yield 123354.2 kWh.",
        "intent": {"types": ["B", "C"]},
        "tool_calls": [{"name": "plants"}, {"name": "anomalies"}],
        "stop_reason": "final_answer",
    }

    checks = evaluate_payload(spec, payload)

    assert all(check.ok for check in checks)


def test_evaluate_payload_checks_bound_tools_trace_and_structured_tool_results():
    spec = ReplaySpec(
        case_id="demo",
        question="demo question",
        expected_intent_types=("C",),
        required_bound_tools=("anomalies", "inverters", "plants"),
        required_trace_kinds=("intent_finished", "synthesis_started", "model_invoke_started"),
        require_structured_tool_results=True,
    )
    payload = {
        "answer": "Structured answer.",
        "intent": {"types": ["C"]},
        "tool_calls": [{"name": "anomalies", "result": {"ok": True, "matched": 2}}],
        "bound_tools": ["anomalies", "inverters", "plants"],
        "trace_events": [
            {"kind": "intent_started"},
            {"kind": "intent_finished"},
            {"kind": "synthesis_started"},
            {"kind": "model_invoke_started"},
        ],
        "stop_reason": "final_answer",
    }

    checks = evaluate_payload(spec, payload)

    assert all(check.ok for check in checks)


def test_run_agent_loop_feeds_structured_json_not_raw_rows():
    registry = build_registry()
    ctx = ToolContext(data=PandasDataSource(load_config().csv_dir))
    observed_messages: list[object] = []

    class ScriptedModel:
        def __init__(self):
            self._responses = [
                SimpleNamespace(
                    content="",
                    tool_calls=[{"name": "plants", "args": {"status": "offline"}, "id": "call_1"}],
                ),
                SimpleNamespace(content="Structured answer.", tool_calls=[]),
            ]
            self._index = 0

        def bind_tools(self, schemas):  # noqa: ARG002
            return self

        def invoke(self, messages):
            observed_messages.append(messages[-1])
            response = self._responses[self._index]
            self._index += 1
            return response

    result = run_agent_loop(
        ScriptedModel(),
        system_prompt="sys",
        user_prompt="Which plants are offline?",
        registry=registry,
        context=ctx,
        tool_names=["plants"],
    )

    assert result.answer == "Structured answer."
    tool_message = observed_messages[-1]
    assert tool_message.content.startswith("{")
    assert "\"ok\":true" in tool_message.content
    assert "Tamil Nadu PV Plant" in tool_message.content
    assert ",offline," not in tool_message.content


def test_pipeline_exposes_stage_separated_trace_and_bound_tools(monkeypatch):
    pipeline = Pipeline(load_config())

    class StubIntentService:
        def parse(self, user_prompt, *, model, context_summary=""):  # noqa: ARG002
            return {
                "intent": {
                    "types": ["C"],
                    "entities": {"plants": ["Rajasthan Solar Park"], "inverters": [], "alerts": [], "anomalies": [], "maintenance": []},
                    "time_range": "",
                    "metric": "anomalies",
                    "out_of_scope": False,
                    "confidence": 0.95,
                    "summary": "Unresolved anomalies for Rajasthan Solar Park",
                },
                "parse_errors": [],
                "provider_name": "fake-intent-model",
                "latency_ms": 5,
                "fast_path": "",
                "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            }

    class FakeSynthesisModel:
        def bind_tools(self, schemas):  # noqa: ARG002
            return self

        def invoke(self, messages):  # noqa: ARG002
            return SimpleNamespace(content="Rajasthan has 15 unresolved anomalies.", tool_calls=[])

    def fake_resolve_provider(config, *, purpose, provider_id="", secret_resolver=None):  # noqa: ARG001
        model = SimpleNamespace(model_name="intent-model") if purpose == "intent" else FakeSynthesisModel()
        return SimpleNamespace(model=model)

    pipeline._intent_service = StubIntentService()
    monkeypatch.setattr("app.pipeline.resolve_provider", fake_resolve_provider)

    result = pipeline.answer("Summarise all unresolved anomalies for Rajasthan Solar Park.")

    assert result.bound_tools == ["anomalies", "inverters", "plants"]
    assert result.intent["types"] == ["C"]
    assert [event.kind for event in result.trace_events] == [
        "intent_started",
        "intent_finished",
        "synthesis_started",
        "model_invoke_started",
        "model_final_answer",
    ]
