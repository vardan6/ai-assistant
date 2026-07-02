from datetime import datetime
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


def test_performance_ratio_sort_asc_returns_worst_plant_first():
    # A2 fix: sort_order="asc" puts lowest-PR plant first (Rajasthan, ≈0.9077)
    registry = build_registry()
    result = registry.invoke(
        "performance_ratio",
        {"window": "last_week", "aggregate_by": "plant", "sort_order": "asc", "limit": 1},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["sort_order"] == "asc"
    first = result["results"][0]
    assert first["plant_name"] == "Rajasthan Solar Park"
    assert isclose(first["avg_performance_ratio"], 0.9077, rel_tol=0, abs_tol=5e-4)


def test_performance_ratio_inverter_result_exposes_inverter_id():
    # A3 fix: inverter-level results must include inverter_id (not just plant_id)
    registry = build_registry()
    result = registry.invoke(
        "performance_ratio",
        {"window": "all_time", "aggregate_by": "inverter", "sort_order": "desc", "limit": 1},
        _ctx(),
    )
    assert result["ok"] is True
    top = result["results"][0]
    assert "inverter_id" in top
    assert top["inverter_id"] == "INV_4137001_04"
    assert isclose(top["avg_performance_ratio"], 0.9519, rel_tol=0, abs_tol=5e-4)


def test_performance_ratio_returns_undefined_verdict_when_window_has_only_null_pr_readings():
    registry = build_registry()
    result = registry.invoke(
        "performance_ratio",
        {"window": "today", "aggregate_by": "plant"},
        ToolContext(
            data=PandasDataSource(load_config().csv_dir),
            reference_now=lambda: datetime.fromisoformat("2026-06-22T05:30:00"),
        ),
    )
    assert result["ok"] is True
    assert result["matched_readings"] == 0
    assert result["verdict"] == "undefined"
    assert "No non-null performance_ratio readings" in result["reason"]
    assert result["results"] == []


def test_performance_ratio_zero_dc_filter_returns_undefined_for_night_readings():
    registry = build_registry()
    result = registry.invoke(
        "performance_ratio",
        {"window": "today", "aggregate_by": "plant", "dc_voltage": "zero"},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["matched_readings"] == 0
    assert result["verdict"] == "undefined"
    assert result["results"] == []


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


def test_mttr_open_alerts_returns_no_input_verdict():
    registry = build_registry()
    result = registry.invoke(
        "mttr",
        {"status": "open", "aggregate_by": "overall"},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["verdict"] == "no_inputs"
    assert result["matched_alerts"] == 0
    assert "resolved_at" in result["reason"]
    assert result["results"] == []


def test_mttr_coerces_status_value_passed_as_severity():
    registry = build_registry()
    result = registry.invoke(
        "mttr",
        {"severity": "open", "aggregate_by": "overall"},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["verdict"] == "no_inputs"
    assert result["status"] == "open"
    assert result["results"] == []


def test_maintenance_cost_sums_done_ticket_spend():
    registry = build_registry()
    result = registry.invoke(
        "maintenance_cost",
        {"status": "done", "aggregate_by": "overall"},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["matched_tickets"] == 12
    assert result["results"][0]["completed_tickets"] == 12
    assert isclose(result["results"][0]["total_cost_usd"], 41715.0, rel_tol=0, abs_tol=1e-9)


def test_maintenance_duration_matches_completed_ticket_average():
    registry = build_registry()
    result = registry.invoke(
        "maintenance_duration",
        {"status": "done", "aggregate_by": "overall"},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["matched_tickets"] == 12
    assert result["results"][0]["completed_tickets"] == 12
    assert isclose(result["results"][0]["mean_duration_hours"], 4.9333333333333345, rel_tol=0, abs_tol=1e-9)


def test_ac_power_mean_matches_dataset_last_week_average_for_inverter():
    registry = build_registry()
    result = registry.invoke(
        "ac_power",
        {
            "inverter": "INV_4135001_01",
            "window": "last_week",
            "aggregate_by": "inverter",
            "reducer": "mean",
        },
        _ctx(),
    )
    assert result["ok"] is True
    assert result["reducer"] == "mean"
    assert result["unit"] == "kW"
    first = result["results"][0]
    assert first["inverter_id"] == "INV_4135001_01"
    assert first["plant_id"] == "4135001"
    assert first["reading_count"] == 155
    assert isclose(first["mean_ac_power_kw"], 593.1005806451611, rel_tol=0, abs_tol=1e-9)


def test_ac_power_mean_ranks_plants_for_last_week():
    registry = build_registry()
    result = registry.invoke(
        "ac_power",
        {"window": "last_week", "aggregate_by": "plant", "reducer": "mean", "limit": 1},
        _ctx(),
    )
    assert result["ok"] is True
    first = result["results"][0]
    assert first["plant_id"] == "4137001"
    assert first["plant_name"] == "Tamil Nadu PV Plant"
    assert first["reading_count"] == 996
    assert isclose(first["mean_ac_power_kw"], 607.0383534136545, rel_tol=0, abs_tol=1e-9)


def test_ac_power_max_overall_returns_peak_row_for_this_month():
    registry = build_registry()
    result = registry.invoke(
        "ac_power",
        {"window": "this_month", "aggregate_by": "overall", "reducer": "max"},
        _ctx(),
    )
    assert result["ok"] is True
    assert result["reducer"] == "max"
    first = result["results"][0]
    assert first["plant_id"] == "4135001"
    assert first["plant_name"] == "Rajasthan Solar Park"
    assert first["inverter_id"] == "INV_4135001_03"
    assert first["timestamp"] == "2026-06-18T13:00:00"
    assert isclose(first["ac_power_kw"], 2505.92, rel_tol=0, abs_tol=1e-9)
    assert isclose(first["max_ac_power_kw"], 2505.92, rel_tol=0, abs_tol=1e-9)


def test_registry_returns_structured_error_for_unknown_tool_kwargs():
    registry = build_registry()
    result = registry.invoke(
        "generation_readings",
        {"window": "last_week", "aggregate_by": "overall"},
        _ctx(),
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_arguments"
    assert result["error"]["tool"] == "generation_readings"
    assert result["error"]["unknown_args"] == ["aggregate_by", "window"]
    assert "Unknown arguments for tool 'generation_readings'" in result["error"]["message"]


def test_last_week_window_can_fall_back_to_wall_clock():
    registry = build_registry()
    result = registry.invoke(
        "daily_yield",
        {"plant": "Rajasthan Solar Park", "window": "last_week", "aggregate_by": "plant"},
        ToolContext(
            data=PandasDataSource(load_config().csv_dir),
            reference_now=lambda: datetime.fromisoformat("2026-06-30T12:00:00"),
        ),
    )
    assert result["ok"] is True
    assert result["results"] == []


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
    assert answer.intent_meta["turn_kind"] == "out_of_scope"
    assert calls == ["intent"]


def test_pipeline_refuses_forecast_generation_with_historical_data_message(monkeypatch):
    pipeline = Pipeline(load_config())

    class StubIntentService:
        def parse(self, user_prompt, *, model, context_summary=""):  # noqa: ARG002
            return {
                "intent": {
                    "types": ["B"],
                    "entities": {
                        "plants": ["Rajasthan"],
                        "inverters": [],
                        "alerts": [],
                        "anomalies": [],
                        "maintenance": [],
                    },
                    "time_range": "next_week",
                    "metric": "generation",
                    "out_of_scope": True,
                    "confidence": 0.98,
                    "summary": "Forecast next week's generation for Rajasthan",
                },
                "parse_errors": [],
                "provider_name": "fake-intent-model",
                "latency_ms": 1,
                "fast_path": "",
            }

    def fake_resolve_provider(config, *, purpose, provider_id="", secret_resolver=None):  # noqa: ARG001
        return SimpleNamespace(model=object())

    pipeline._intent_service = StubIntentService()
    monkeypatch.setattr("app.pipeline.resolve_provider", fake_resolve_provider)

    answer = pipeline.answer("Forecast next week's generation for Rajasthan.")

    assert "can't answer" in answer.answer
    assert "historical/observed generation data" in answer.answer
    assert "not forecast data" in answer.answer
    assert answer.tool_calls == []
    assert answer.intent_meta["turn_kind"] == "out_of_scope"
