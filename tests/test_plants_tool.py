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


def test_shared_plant_resolver_matches_location_alias():
    registry = build_registry()
    result = registry.invoke("plants", {"plant": "Gujarat plant"}, _ctx())
    assert result["matched"] == 1
    assert result["plants"][0]["plant_id"] == 4136001


def test_shared_plant_resolver_does_not_match_region_label():
    registry = build_registry()
    result = registry.invoke("plants", {"plant": "West"}, _ctx())
    assert result["matched"] == 0


def test_weather_tool_uses_shared_plant_resolver():
    registry = build_registry()
    result = registry.invoke("weather_readings", {"plant": "Gujarat plant", "limit": 1}, _ctx())
    assert result["matched"] > 0
    assert result["recent_readings"][0]["plant_id"] == 4136001


def test_unknown_tool_returns_error_dict():
    registry = build_registry()
    result = registry.invoke("nope", {}, _ctx())
    assert result["ok"] is False
    assert "Unknown tool" in result["error"]
