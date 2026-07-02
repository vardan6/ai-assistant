from app.config import load_config
from app.data import PandasDataSource
from app.tools import ToolContext, build_registry


def _ctx() -> ToolContext:
    return ToolContext(data=PandasDataSource(load_config().csv_dir))


def test_inverters_tool_filters_silent_by_generation():
    registry = build_registry()
    result = registry.invoke("inverters", {"silent_by_generation": True}, _ctx())

    assert result["ok"] is True
    assert result["matched"] == 16
    assert result["silent_count"] == 16
    assert "INV_4135001_10" in result["silent_inverter_ids"]
    assert all(row["is_silent_by_generation"] is True for row in result["inverters"])


def test_inverters_tool_silent_count_is_independent_of_status_filter():
    registry = build_registry()
    result = registry.invoke("inverters", {"status": "offline"}, _ctx())

    assert result["ok"] is True
    assert result["matched"] == 15
    assert result["silent_count"] == 16
    assert "INV_4135001_10" in result["silent_inverter_ids"]
    assert all(row["status"] == "offline" for row in result["inverters"])


def test_inverters_tool_silent_by_generation_takes_precedence_over_status_filter():
    registry = build_registry()
    result = registry.invoke("inverters", {"silent_by_generation": True, "status": "offline"}, _ctx())

    assert result["ok"] is True
    assert result["matched"] == 16
    assert result["silent_count"] == 16
    assert result["ignored_status_filter_for_silent_by_generation"] == "offline"
    assert "INV_4135001_10" in result["silent_inverter_ids"]
    assert any(row["status"] == "fault" for row in result["inverters"])
    assert all(row["is_silent_by_generation"] is True for row in result["inverters"])
