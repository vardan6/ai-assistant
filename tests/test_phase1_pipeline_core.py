from types import SimpleNamespace

import pytest

from app.ai import run_agent_loop
from app.config import load_config
from app.data import PandasDataSource
from app.pipeline import select_tool_names
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
        "daily_yield", "performance_ratio", "mttr", "generation_readings", "inverters", "plants", "weather_readings"
    ]
    assert select_tool_names({"types": ["C"]}, gating_mode="gated", available_tools=available) == [
        "anomalies", "inverters", "plants"
    ]
    assert select_tool_names({"types": ["C"]}, gating_mode="bind_all", available_tools=available) == available


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
