from app.config import load_config
from app.data import PandasDataSource
from app.tools import ToolContext, build_registry


def _ctx() -> ToolContext:
    return ToolContext(data=PandasDataSource(load_config().csv_dir))


def test_maintenance_tool_renames_fleet_total_under_filters():
    registry = build_registry()

    result = registry.invoke("maintenance", {"status": "done"}, _ctx())

    assert result["ok"] is True
    assert result["matched"] == 12
    assert "total_tickets" not in result
    assert result["total_tickets_all_plants"] == 19


def test_maintenance_tool_keeps_total_tickets_when_unfiltered():
    registry = build_registry()

    result = registry.invoke("maintenance", {}, _ctx())

    assert result["ok"] is True
    assert result["matched"] == 19
    assert result["total_tickets"] == 19
    assert "total_tickets_all_plants" not in result
