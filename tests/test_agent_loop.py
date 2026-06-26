from types import SimpleNamespace

from app.ai import run_agent_loop
from app.config import load_config
from app.data import PandasDataSource
from app.tools import ToolContext, build_registry


class ScriptedModel:
    """Fake chat model that plays a fixed sequence of responses.

    First call asks to invoke the `plants` tool; second call (after seeing the
    tool result) returns a final answer with no tool calls.
    """

    def __init__(self):
        self._responses = [
            SimpleNamespace(content="", tool_calls=[{"name": "plants", "args": {"status": "offline"}, "id": "call_1"}]),
            SimpleNamespace(content="One plant is offline: Tamil Nadu PV Plant.", tool_calls=[]),
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


def _ctx() -> ToolContext:
    return ToolContext(data=PandasDataSource(load_config().csv_dir))


def test_loop_executes_tool_then_answers():
    model = ScriptedModel()
    registry = build_registry()
    result = run_agent_loop(
        model,
        system_prompt="sys",
        user_prompt="which plants are offline?",
        registry=registry,
        context=_ctx(),
    )
    assert result.stop_reason == "final_answer"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "plants"
    assert result.tool_calls[0].result["matched"] == 1
    assert "offline" in result.answer.lower()
    # Tool schemas were bound to the model.
    assert model.bound_schemas
    assert "plants" in [schema["function"]["name"] for schema in model.bound_schemas]
