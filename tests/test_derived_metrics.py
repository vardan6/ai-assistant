from math import isclose
from types import SimpleNamespace

from app.config import load_config
from app.data import PandasDataSource
from app.pipeline import Pipeline
from app.tools import ToolContext, build_registry


def _ctx() -> ToolContext:
    return ToolContext(data=PandasDataSource(load_config().csv_dir))


def test_daily_yield_matches_dataset_last_week_average_for_rajasthan():
    registry = build_registry()
    result = registry.invoke(
        "daily_yield",
        {"plant": "Rajasthan Solar Park", "window": "last_week", "aggregate_by": "plant"},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["results"][0]["plant_name"] == "Rajasthan Solar Park"
    assert result["results"][0]["days"] == 7
    assert isclose(result["results"][0]["avg_daily_yield"], 123354.2, rel_tol=0, abs_tol=1e-6)


def test_performance_ratio_ranks_top_inverter_for_last_week():
    registry = build_registry()
    result = registry.invoke(
        "performance_ratio",
        {"window": "last_week", "aggregate_by": "inverter", "limit": 1},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["results"][0]["inverter_id"] == "INV_4137001_07"
    assert isclose(result["results"][0]["avg_performance_ratio"], 0.955525, rel_tol=0, abs_tol=1e-6)


def test_mttr_matches_critical_alert_mean_time_to_resolve():
    registry = build_registry()
    result = registry.invoke(
        "mttr",
        {"severity": "critical", "aggregate_by": "overall"},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["unit"] == "hours"
    assert isclose(result["results"][0]["mean_time_to_resolve_hours"], 6.34462962962963, rel_tol=0, abs_tol=1e-9)
    assert result["results"][0]["resolved_alerts"] == 6


def test_pipeline_refuses_explicit_out_of_scope_question(monkeypatch):
    pipeline = Pipeline(load_config())

    class StubIntentService:
        def parse(self, user_prompt, *, model, context_summary=""):  # noqa: ARG002
            return {
                "intent": {
                    "types": ["B"],
                    "entities": {"plants": [], "inverters": [], "alerts": [], "anomalies": [], "maintenance": []},
                    "time_range": "this_month",
                    "metric": "revenue_loss",
                    "out_of_scope": True,
                    "confidence": 0.98,
                    "summary": "Revenue loss from downtime",
                },
                "parse_errors": [],
                "provider_name": "fake-intent-model",
                "latency_ms": 1,
                "fast_path": "",
            }

    calls: list[str] = []

    def fake_resolve_provider(config, *, purpose, provider_id="", secret_resolver=None):  # noqa: ARG001
        calls.append(purpose)
        return SimpleNamespace(model=object())

    pipeline._intent_service = StubIntentService()
    monkeypatch.setattr("app.pipeline.resolve_provider", fake_resolve_provider)

    answer = pipeline.answer("How much revenue did we lose from Tamil Nadu's downtime this month?")
    assert "can't calculate revenue loss" in answer.answer
    assert answer.tool_calls == []
    assert answer.bound_tools == []
    assert calls == ["intent"]
