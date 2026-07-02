from app.config import load_config
from app.data import PandasDataSource
from app.tools import ToolContext, build_registry


def _ctx() -> ToolContext:
    return ToolContext(data=PandasDataSource(load_config().csv_dir))


def test_alerts_tool_returns_downtime_aggregates_for_matched_frame():
    registry = build_registry()

    result = registry.invoke("alerts", {"status": "resolved"}, _ctx())

    assert result["ok"] is True
    assert result["matched"] == 25
    assert result["total_downtime_minutes"] == 31836.0
    assert result["downtime_record_count"] == 25


def test_alerts_tool_downtime_aggregates_follow_other_filters():
    registry = build_registry()

    result = registry.invoke("alerts", {"status": "resolved", "plant": "Rajasthan"}, _ctx())

    assert result["ok"] is True
    assert result["matched"] == 13
    assert result["total_downtime_minutes"] == 12520.0
    assert result["downtime_record_count"] == 13
    assert "total_alerts" not in result
    assert result["total_alerts_all_plants"] == 29
    assert all(row["plant_id"] == 4135001 for row in result["alerts"])
