"""Bare iterative tool-calling loop.

Distilled from the reference `gcs_server/ai/agent_loop.py` — same shape (bind
tools, invoke, execute tool_calls, append ToolMessages, repeat until the model
answers), minus rover policy tiers/terminal tools. Tools are bound per call so
gating (Slice 4) is just a different `tool_names` list — the loop is identical.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .agent_traces import TraceEvent, make_trace_event
from .usage_telemetry import UsageSnapshot, model_name_from_model, usage_from_response
from ..tools import ToolContext, ToolRegistry

MAX_TOOL_ITERATIONS = 6


@dataclass(slots=True)
class ToolCallRecord:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]
    iteration: int
    latency_ms: int


@dataclass(slots=True)
class AgentResult:
    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    iterations: int = 0
    stop_reason: str = ""
    trace_events: list[TraceEvent] = field(default_factory=list)
    usage: UsageSnapshot = field(default_factory=UsageSnapshot)
    elapsed_ms: int = 0
    model_name: str = ""


def run_agent_loop(
    model: Any,
    *,
    system_prompt: str,
    user_prompt: str,
    registry: ToolRegistry,
    context: ToolContext,
    tool_names: list[str] | None = None,
    event_handler: Callable[[TraceEvent], None] | None = None,
) -> AgentResult:
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

    schemas = registry.bind_schemas(tool_names)
    bound_model = model.bind_tools(schemas) if schemas else model

    messages: list[Any] = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    executed: list[ToolCallRecord] = []
    trace_events: list[TraceEvent] = []
    final_response = None
    stop_reason = "iteration_limit"
    iterations = 0
    usage = UsageSnapshot()
    model_name = model_name_from_model(model)
    loop_started = time.perf_counter()

    for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
        iterations = iteration
        _emit(
            trace_events,
            event_handler,
            make_trace_event("model_invoke_started", "Invoking synthesis model", iteration=iteration),
        )
        final_response = bound_model.invoke(messages)
        usage = usage.add(usage_from_response(final_response))
        messages.append(final_response)

        tool_calls = getattr(final_response, "tool_calls", None) or []
        if not tool_calls:
            stop_reason = "final_answer"
            _emit(
                trace_events,
                event_handler,
                make_trace_event("model_final_answer", "Model returned a final answer", iteration=iteration),
            )
            break

        for call in tool_calls:
            name = str(call.get("name") or "").strip()
            args = call.get("args") if isinstance(call.get("args"), dict) else {}
            call_id = str(call.get("id") or name)

            started = time.perf_counter()
            _emit(
                trace_events,
                event_handler,
                make_trace_event(
                    "tool_started",
                    f"Calling tool '{name}'",
                    iteration=iteration,
                    tool_name=name,
                    details={"args": args},
                ),
            )
            result = registry.invoke(name, args, context)
            latency_ms = int((time.perf_counter() - started) * 1000)

            executed.append(ToolCallRecord(name=name, args=args, result=result, iteration=iteration, latency_ms=latency_ms))
            _emit(
                trace_events,
                event_handler,
                make_trace_event(
                    "tool_finished",
                    f"Tool '{name}' completed",
                    iteration=iteration,
                    tool_name=name,
                    latency_ms=latency_ms,
                    ok=bool(result.get("ok", True)),
                ),
            )
            messages.append(ToolMessage(
                content=json.dumps(result, separators=(",", ":"), sort_keys=True, default=str),
                tool_call_id=call_id,
                name=name,
            ))

    answer = _final_text(final_response)
    return AgentResult(
        answer=answer,
        tool_calls=executed,
        iterations=iterations,
        stop_reason=stop_reason,
        trace_events=trace_events,
        usage=usage,
        elapsed_ms=int((time.perf_counter() - loop_started) * 1000),
        model_name=model_name,
    )


def _final_text(response: Any) -> str:
    if response is None:
        return ""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    # Some providers return a list of content blocks.
    if isinstance(content, list):
        parts = [str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in content]
        return "".join(parts).strip()
    return str(content).strip()


def _emit(
    collected: list[TraceEvent],
    event_handler: Callable[[TraceEvent], None] | None,
    event: TraceEvent,
) -> None:
    collected.append(event)
    if event_handler is not None:
        event_handler(event)
