from app.config import load_config
from app.data import PandasDataSource
from app.tools import ToolContext, build_registry


def _ctx() -> ToolContext:
    return ToolContext(data=PandasDataSource(load_config().csv_dir))


def test_plants_tool_returns_status_counts():
    registry = build_registry()
    result = registry.invoke("plants", {}, _ctx())
    assert result["ok"] is True
    assert result["total_plants"] == 3
    # Dataset has one active, one maintenance, one offline plant.
    assert result["status_counts"].get("offline") == 1
    assert result["status_counts"].get("active") == 1


def test_plants_filter_by_status():
    registry = build_registry()
    result = registry.invoke("plants", {"status": "offline"}, _ctx())
    assert result["matched"] == 1
    assert result["plants"][0]["status"] == "offline"


def test_plants_filter_by_name_case_insensitive():
    registry = build_registry()
    result = registry.invoke("plants", {"plant": "rajasthan solar park"}, _ctx())
    assert result["matched"] == 1
    assert result["plants"][0]["plant_id"] == 4135001


def test_unknown_tool_returns_error_dict():
    registry = build_registry()
    result = registry.invoke("nope", {}, _ctx())
    assert result["ok"] is False
    assert "Unknown tool" in result["error"]
