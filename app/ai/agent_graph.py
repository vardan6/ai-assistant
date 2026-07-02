"""Lane C agent-context helpers used by the runtime transition."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

TurnKind = Literal[
    "data_question",
    "follow_up",
    "dispute_correction",
    "clarification",
    "prior_answer_meta",
    "smalltalk",
    "command",
    "out_of_scope",
]

PriorAnswerVerdictStatus = Literal["correct", "wrong", "incomplete"]
TurnAction = Literal["use_tools", "tool_free", "refuse"]
GraphNodeName = Literal[
    "load_session_context",
    "route_local",
    "classify_intent",
    "resolve_follow_up",
    "interpret_session_turn",
    "tool_free_reply",
    "out_of_scope_reply",
    "run_tool_loop",
    "reconcile_prior_answer",
]

_PLANT_NAMES = (
    "Rajasthan Solar Park",
    "Gujarat Solar Farm",
    "Tamil Nadu PV Plant",
)
_AMBIGUOUS_PLANT_QUESTIONS = {
    "how is the plant doing?",
    "how is the plant doing",
}
_AFFIRMATIVE_FOLLOW_UPS = {
    "yes",
    "yes please",
    "please",
    "ok",
    "okay",
    "sure",
}
_METRIC_CONTEXT_CUES = (
    "performance ratio",
    "daily yield",
    "total yield",
    "total energy",
    "feed-in tariff",
    "feed in tariff",
    "cloud cover",
    "weather",
    "mean time",
    "mttr",
)


class PromptHistoryMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class SessionHistoryMessage(TypedDict, total=False):
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    metadata: dict[str, Any]


class PriorAnswerVerdict(TypedDict, total=False):
    status: PriorAnswerVerdictStatus
    referenced_message_id: int
    referenced_claim: str
    predicate_summary: str
    explanation: str
    tool_names: list[str]
    entity_ids: list[str]
    numbers: list[float]
    evidence_fingerprint_sha256: str


class TurnInterpretation(TypedDict, total=False):
    turn_action: TurnAction
    resolved_request: str
    intent: dict[str, Any]
    tool_policy: str


class AgentContext(TypedDict):
    session_id: str
    latest_user_message: str
    history_window: list[SessionHistoryMessage]
    prompt_history: list[PromptHistoryMessage]


@dataclass(slots=True)
class AgentGraphState:
    latest_user_message: str
    session_id: str = ""
    history_window: list[SessionHistoryMessage] = field(default_factory=list)
    prompt_history: list[PromptHistoryMessage] = field(default_factory=list)
    turn_kind: TurnKind = "data_question"
    intent: dict[str, Any] = field(default_factory=dict)
    fast_path: str = ""
    resolved_question: str = ""
    prior_answer_verdict: PriorAnswerVerdict | None = None
    graph_nodes: list[GraphNodeName] = field(default_factory=list)
    turn_interpretation: TurnInterpretation = field(default_factory=dict)


class PipelineRuntimeState(TypedDict, total=False):
    question: str
    provider_id: str
    gating_mode: str
    agent_state: AgentGraphState
    intent: dict[str, Any]
    intent_meta: dict[str, Any]
    turn_interpretation: TurnInterpretation
    answer: str
    stop_reason: str
    prior_answer_verdict: PriorAnswerVerdict | None
    tool_calls: list[Any]
    bound_tools: list[str]
    fast_path: str
    iterations: int
    intent_model_name: str
    synthesis_model_name: str
    intent_usage: Any
    synthesis_usage: Any


def load_session_context(store: Any, session_id: str, latest_user_message: str) -> AgentContext:
    return {
        "session_id": session_id,
        "latest_user_message": latest_user_message,
        "history_window": list(store.load_history_window(session_id)),
        "prompt_history": list(store.load_prompt_history(session_id)),
    }


def summarize_prompt_history(prompt_history: list[PromptHistoryMessage] | None, *, limit: int = 4) -> str:
    if not prompt_history:
        return ""
    window = [item for item in prompt_history if item.get("content", "").strip()][-limit:]
    if not window:
        return ""
    return "\n".join(
        f"{item.get('role', 'user')}: {str(item.get('content', '')).strip()}"
        for item in window
    )


def recent_plant_name(prompt_history: list[PromptHistoryMessage] | None) -> str:
    if not prompt_history:
        return ""
    for item in reversed(prompt_history):
        content = str(item.get("content", ""))
        for plant_name in _PLANT_NAMES:
            if plant_name.lower() in content.lower():
                return plant_name
    return ""


def can_resolve_ambiguous_plant(prompt_history: list[PromptHistoryMessage] | None) -> bool:
    return bool(recent_plant_name(prompt_history))


def resolve_follow_up_question(question: str, prompt_history: list[PromptHistoryMessage] | None) -> str:
    clean = " ".join(str(question or "").split()).strip()
    if not clean:
        return ""

    plant_name = recent_plant_name(prompt_history)
    clean_lower = clean.lower()
    previous_user = _latest_message(prompt_history, role="user")
    previous_assistant = _latest_message(prompt_history, role="assistant")

    if clean_lower in _AMBIGUOUS_PLANT_QUESTIONS and plant_name:
        metric_anchor = _latest_metric_anchor(prompt_history, plant_name=plant_name)
        if metric_anchor:
            return f"{metric_anchor} Follow-up: {clean}"
        return f"How is {plant_name} doing?"

    if clean_lower.startswith(("and ", "what about ", "how about ")):
        anchor = previous_user or previous_assistant
        if anchor:
            return f"{anchor} Follow-up: {clean}"

    if clean_lower in _AFFIRMATIVE_FOLLOW_UPS or re.search(r"\b(?:re-?check|closest available|use the closest|using the closest)\b", clean_lower):
        anchor_parts = [part for part in (previous_user, previous_assistant) if part]
        if anchor_parts:
            return " ".join([*anchor_parts, f"Follow-up request: {clean}"])

    if any(token in clean_lower for token in ("those", "that one", "that plant", "same one", "previous", "earlier", "again")):
        anchor_parts = [part for part in (previous_user, previous_assistant) if part]
        if anchor_parts:
            return " ".join([*anchor_parts, f"Follow-up question: {clean}"])

    if prompt_history:
        summary = summarize_prompt_history(prompt_history, limit=3)
        if summary:
            return f"Recent context:\n{summary}\nLatest follow-up: {clean}"
    return clean


def latest_metric_context(prompt_history: list[PromptHistoryMessage] | None, *, plant_name: str = "") -> str:
    anchor = _latest_metric_anchor(prompt_history, plant_name=plant_name)
    return anchor.lower()


def last_assistant_message(history_window: list[SessionHistoryMessage] | None) -> SessionHistoryMessage | None:
    if not history_window:
        return None
    for item in reversed(history_window):
        if item.get("role") == "assistant":
            return item
    return None


def _latest_metric_anchor(prompt_history: list[PromptHistoryMessage] | None, *, plant_name: str = "") -> str:
    if not prompt_history:
        return ""
    for role in ("user", "assistant"):
        for item in reversed(prompt_history):
            if item.get("role") != role:
                continue
            content = str(item.get("content", "")).strip()
            content_lower = content.lower()
            if plant_name and plant_name.lower() not in content_lower:
                continue
            if any(cue in content_lower for cue in _METRIC_CONTEXT_CUES):
                return content
    return ""


def build_prior_answer_verdict(
    *,
    history_window: list[SessionHistoryMessage] | None,
    predicate_summary: str,
    tool_calls: list[Any],
) -> PriorAnswerVerdict:
    referenced = last_assistant_message(history_window)
    referenced_claim = str(referenced.get("content", "")).strip() if referenced else ""
    referenced_message_id = int(referenced["id"]) if referenced and "id" in referenced else 0
    metadata = referenced.get("metadata") if referenced else {}
    evidence_fingerprint = ""
    prior_tool_calls: list[Any] = []
    if isinstance(metadata, dict):
        stored_fingerprint = metadata.get("evidence_fingerprint")
        if isinstance(stored_fingerprint, dict):
            evidence_fingerprint = str(stored_fingerprint.get("sha256", "")).strip()
        stored_tool_calls = metadata.get("tool_calls")
        if isinstance(stored_tool_calls, list):
            prior_tool_calls = stored_tool_calls

    tool_names = [_tool_call_name(call) for call in tool_calls if _tool_call_name(call)]
    entity_ids = _extract_entity_ids(tool_calls)
    numbers = _extract_numbers(tool_calls)
    status = _classify_verdict(prior_tool_calls=prior_tool_calls, fresh_tool_calls=tool_calls)

    verdict: PriorAnswerVerdict = {
        "status": status,
        "referenced_claim": referenced_claim or "No prior assistant answer was available to re-check.",
        "predicate_summary": predicate_summary.strip() or "Re-check the prior claim against fresh tool evidence.",
        "explanation": _verdict_explanation(status, entity_ids=entity_ids, numbers=numbers),
        "tool_names": tool_names,
        "entity_ids": entity_ids,
        "numbers": numbers,
    }
    if referenced_message_id:
        verdict["referenced_message_id"] = referenced_message_id
    if evidence_fingerprint:
        verdict["evidence_fingerprint_sha256"] = evidence_fingerprint
    return verdict


def build_agent_graph_state(
    latest_user_message: str,
    *,
    session_id: str = "",
    session_store: Any | None = None,
    history_window: list[SessionHistoryMessage] | None = None,
    prompt_history: list[PromptHistoryMessage] | None = None,
) -> AgentGraphState:
    if session_id and session_store is not None and (history_window is None or prompt_history is None):
        session_context = load_session_context(session_store, session_id, latest_user_message)
        if history_window is None:
            history_window = session_context["history_window"]
        if prompt_history is None:
            prompt_history = session_context["prompt_history"]
    return AgentGraphState(
        latest_user_message=latest_user_message,
        session_id=session_id,
        history_window=list(history_window or ()),
        prompt_history=list(prompt_history or ()),
    )


def apply_turn_routing(
    state: AgentGraphState,
    *,
    intent: dict[str, Any],
    turn_kind: TurnKind,
    fast_path: str = "",
) -> AgentGraphState:
    state.intent = intent
    state.turn_kind = turn_kind
    state.fast_path = fast_path
    state.resolved_question = (
        resolve_follow_up_question(state.latest_user_message, state.prompt_history)
        if turn_kind == "follow_up"
        else ""
    )
    state.graph_nodes = plan_graph_nodes(
        turn_kind=turn_kind,
        has_session_context=bool(state.session_id and (state.history_window or state.prompt_history)),
        has_fast_path=bool(fast_path),
        out_of_scope=bool(intent.get("out_of_scope")),
        tool_free=turn_kind in {"smalltalk", "command", "clarification", "prior_answer_meta"},
    )
    return state


def apply_prior_answer_verdict(
    state: AgentGraphState,
    *,
    predicate_summary: str,
    tool_calls: list[Any],
) -> AgentGraphState:
    state.prior_answer_verdict = build_prior_answer_verdict(
        history_window=state.history_window,
        predicate_summary=predicate_summary,
        tool_calls=tool_calls,
    )
    return state


def derive_turn_interpretation(state: AgentGraphState, *, gating_mode: str = "gated") -> TurnInterpretation:
    """Derive the typed turn-interpretation payload from already-classified state.

    AR-1 structural insertion: populates from classify_intent/route_local outputs already
    in state without any new LLM call. A future slice will replace this with a
    session-aware semantic interpreter.
    """
    turn_kind = state.turn_kind
    intent = state.intent
    if turn_kind in {"smalltalk", "command", "clarification", "prior_answer_meta"}:
        turn_action: TurnAction = "tool_free"
    elif turn_kind == "out_of_scope" and bool(intent.get("out_of_scope")):
        turn_action = "refuse"
    else:
        turn_action = "use_tools"
    return TurnInterpretation(
        turn_action=turn_action,
        resolved_request=state.resolved_question or state.latest_user_message,
        intent=intent,
        tool_policy=gating_mode,
    )


def plan_graph_nodes(
    *,
    turn_kind: TurnKind,
    has_session_context: bool,
    has_fast_path: bool,
    out_of_scope: bool,
    tool_free: bool,
) -> list[GraphNodeName]:
    nodes: list[GraphNodeName] = []
    if has_session_context:
        nodes.append("load_session_context")
    nodes.append("route_local")
    if has_fast_path:
        nodes.append("tool_free_reply")
        return nodes
    nodes.append("classify_intent")
    if turn_kind == "follow_up":
        nodes.append("resolve_follow_up")
    nodes.append("interpret_session_turn")
    if tool_free:
        nodes.append("tool_free_reply")
        return nodes
    if out_of_scope and turn_kind not in {"follow_up", "dispute_correction"}:
        nodes.append("out_of_scope_reply")
        return nodes
    nodes.append("run_tool_loop")
    if turn_kind == "dispute_correction":
        nodes.append("reconcile_prior_answer")
    return nodes


def compile_runtime_graph(
    *,
    load_session_context_node: Callable[[PipelineRuntimeState], dict[str, Any]],
    route_local_node: Callable[[PipelineRuntimeState], dict[str, Any]],
    classify_intent_node: Callable[[PipelineRuntimeState], dict[str, Any]],
    interpret_session_turn_node: Callable[[PipelineRuntimeState], dict[str, Any]],
    tool_free_reply_node: Callable[[PipelineRuntimeState], dict[str, Any]],
    out_of_scope_reply_node: Callable[[PipelineRuntimeState], dict[str, Any]],
    run_tool_loop_node: Callable[[PipelineRuntimeState], dict[str, Any]],
    reconcile_prior_answer_node: Callable[[PipelineRuntimeState], dict[str, Any]],
):
    graph = StateGraph(PipelineRuntimeState)
    graph.add_node("load_session_context", load_session_context_node)
    graph.add_node("route_local", route_local_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("interpret_session_turn", interpret_session_turn_node)
    graph.add_node("tool_free_reply", tool_free_reply_node)
    graph.add_node("out_of_scope_reply", out_of_scope_reply_node)
    graph.add_node("run_tool_loop", run_tool_loop_node)
    graph.add_node("reconcile_prior_answer", reconcile_prior_answer_node)

    graph.add_edge(START, "load_session_context")
    graph.add_edge("load_session_context", "route_local")
    graph.add_conditional_edges(
        "route_local",
        _route_after_local,
        {
            "tool_free_reply": "tool_free_reply",
            "classify_intent": "classify_intent",
        },
    )
    graph.add_edge("classify_intent", "interpret_session_turn")
    graph.add_conditional_edges(
        "interpret_session_turn",
        _route_after_interpret,
        {
            "tool_free_reply": "tool_free_reply",
            "out_of_scope_reply": "out_of_scope_reply",
            "run_tool_loop": "run_tool_loop",
        },
    )
    graph.add_conditional_edges(
        "run_tool_loop",
        _route_after_tool_loop,
        {
            "reconcile_prior_answer": "reconcile_prior_answer",
            "__end__": END,
        },
    )
    graph.add_edge("tool_free_reply", END)
    graph.add_edge("out_of_scope_reply", END)
    graph.add_edge("reconcile_prior_answer", END)
    return graph.compile()


def _route_after_local(state: PipelineRuntimeState) -> str:
    agent_state = state.get("agent_state")
    if isinstance(agent_state, AgentGraphState) and agent_state.fast_path:
        return "tool_free_reply"
    return "classify_intent"


def _route_after_interpret(state: PipelineRuntimeState) -> str:
    interpretation = state.get("turn_interpretation") or {}
    turn_action = interpretation.get("turn_action", "use_tools")
    if turn_action == "tool_free":
        return "tool_free_reply"
    if turn_action == "refuse":
        return "out_of_scope_reply"
    return "run_tool_loop"


def _route_after_tool_loop(state: PipelineRuntimeState) -> str:
    agent_state = state.get("agent_state")
    if isinstance(agent_state, AgentGraphState) and agent_state.turn_kind == "dispute_correction":
        return "reconcile_prior_answer"
    return "__end__"


def _latest_message(prompt_history: list[PromptHistoryMessage] | None, *, role: str) -> str:
    if not prompt_history:
        return ""
    for item in reversed(prompt_history):
        if item.get("role") == role and str(item.get("content", "")).strip():
            return str(item["content"]).strip()
    return ""


def _extract_entity_ids(tool_calls: list[Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for call in tool_calls:
        result = _tool_call_result(call)
        if not isinstance(result, dict):
            continue
        for key in ("matched_inverter_ids", "anomaly_ids"):
            values = result.get(key)
            if isinstance(values, list):
                for value in values:
                    text = str(value).strip()
                    if text and text not in seen:
                        seen.add(text)
                        found.append(text)
        anomalies = result.get("anomalies")
        if isinstance(anomalies, list):
            for item in anomalies:
                if not isinstance(item, dict):
                    continue
                for field in ("inverter_id", "plant_id", "anomaly_id"):
                    text = str(item.get(field, "")).strip()
                    if text and text not in seen:
                        seen.add(text)
                        found.append(text)
    return found


def _extract_numbers(tool_calls: list[Any]) -> list[float]:
    found: list[float] = []
    seen: set[float] = set()
    for call in tool_calls:
        result = _tool_call_result(call)
        if not isinstance(result, dict):
            continue
        for number in _extract_numbers_from_value(result):
            rounded = round(float(number), 4)
            if rounded not in seen:
                seen.add(rounded)
                found.append(rounded)
    return found


def _extract_numbers_from_value(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, str):
        clean = value.strip().replace(",", "")
        if re.fullmatch(r"-?\d+(?:\.\d+)?", clean):
            return [float(clean)]
        return []
    if isinstance(value, dict):
        numbers: list[float] = []
        for nested in value.values():
            numbers.extend(_extract_numbers_from_value(nested))
        return numbers
    if isinstance(value, list):
        numbers: list[float] = []
        for nested in value:
            numbers.extend(_extract_numbers_from_value(nested))
        return numbers
    return []


def _classify_verdict(*, prior_tool_calls: list[Any], fresh_tool_calls: list[Any]) -> PriorAnswerVerdictStatus:
    prior_entity_ids = {_entity_key(value) for value in _extract_entity_ids(prior_tool_calls)}
    fresh_entity_ids = {_entity_key(value) for value in _extract_entity_ids(fresh_tool_calls)}
    prior_numbers = {_number_key(value) for value in _extract_numbers(prior_tool_calls)}
    fresh_numbers = {_number_key(value) for value in _extract_numbers(fresh_tool_calls)}

    prior_entity_ids.discard("")
    fresh_entity_ids.discard("")
    if not prior_entity_ids and not prior_numbers:
        return "incomplete"
    if not fresh_entity_ids and not fresh_numbers:
        return "incomplete"

    entity_supported = not prior_entity_ids or prior_entity_ids.issubset(fresh_entity_ids)
    number_supported = not prior_numbers or prior_numbers.issubset(fresh_numbers)
    if entity_supported and number_supported:
        return "correct"
    if prior_entity_ids and fresh_entity_ids and prior_entity_ids.isdisjoint(fresh_entity_ids):
        return "wrong"
    if prior_numbers and fresh_numbers and prior_numbers.isdisjoint(fresh_numbers):
        return "wrong"
    return "incomplete"


def _tool_call_name(call: Any) -> str:
    if isinstance(call, dict):
        return str(call.get("name", "")).strip()
    return str(getattr(call, "name", "")).strip()


def _tool_call_result(call: Any) -> Any:
    if isinstance(call, dict):
        return call.get("result")
    return getattr(call, "result", None)


def _entity_key(value: str) -> str:
    return str(value).strip().lower()


def _number_key(value: float) -> float:
    return round(float(value), 4)


def _verdict_explanation(status: PriorAnswerVerdictStatus, *, entity_ids: list[str], numbers: list[float]) -> str:
    if status == "wrong":
        return "Fresh tool evidence did not support the referenced claim."
    if status == "correct":
        return "Fresh tool evidence matched the referenced claim."
    details: list[str] = []
    if entity_ids:
        details.append(f"entity_ids={', '.join(entity_ids[:4])}")
    if numbers:
        details.append(f"numbers={', '.join(str(value) for value in numbers[:4])}")
    suffix = f" Evidence: {'; '.join(details)}." if details else ""
    return f"The prior answer could only be partially checked from the available history.{suffix}"
