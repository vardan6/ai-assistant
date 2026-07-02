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

    def invoke(self, messages):
        self.last_messages = list(messages)
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


def test_loop_threads_prior_history_into_messages():
    """Prior turns must reach the synthesis model so pronouns ('its') resolve.

    Regression for MT-D2: 'what is its id?' after a Rajasthan Solar Park turn must
    not lose the prior-turn referent.
    """
    model = ScriptedModel()
    # No tool call needed; answer straight away from threaded context.
    model._responses = [SimpleNamespace(content="4135001", tool_calls=[])]
    registry = build_registry()
    history = [
        {"role": "user", "content": "average daily yield of Rajasthan Solar Park last week?"},
        {"role": "assistant", "content": "Rajasthan Solar Park averaged 123354.2 over 7 days."},
    ]
    run_agent_loop(
        model,
        system_prompt="sys",
        user_prompt="what is its id?",
        registry=registry,
        context=_ctx(),
        prompt_history=history,
    )
    contents = [getattr(m, "content", "") for m in model.last_messages]
    # System prompt, both prior turns, then the current question — in order.
    assert "sys" in contents[0]
    assert any("Rajasthan Solar Park" in c for c in contents[1:-1])
    assert contents[-1] == "what is its id?"
    types = [type(m).__name__ for m in model.last_messages]
    assert types[0] == "SystemMessage"
    assert types[-1] == "HumanMessage"
    assert "AIMessage" in types  # prior assistant turn preserved as AIMessage
