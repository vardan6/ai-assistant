"""Pipeline — the orchestration brain wired end to end.

question -> [smalltalk fast-path?] -> intent classification (explicit, logged)
         -> agent tool-calling loop -> answer with explicit degradation.

Tool gating (gated | bind_all) and derived-metric tools arrive in later slices;
the tool list is selected per request from explicit intent.
"""
from __future__ import annotations

import inspect
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .ai import (
    IntentService,
    TelemetrySummary,
    ToolCallRecord,
    TraceEvent,
    UsageSnapshot,
    resolve_provider,
    run_agent_loop,
)
from .ai.agent_graph import (
    apply_prior_answer_verdict,
    apply_turn_routing,
    build_agent_graph_state,
    compile_runtime_graph,
    derive_turn_interpretation,
    last_assistant_message,
    latest_metric_context,
    PipelineRuntimeState,
    recent_plant_name,
    summarize_prompt_history,
)
from .ai.agent_traces import make_trace_event
from .ai.turn_router import build_tool_free_reply, infer_turn_kind, is_tool_free_turn, route_local_turn
from .ai.usage_telemetry import model_name_from_model, utc_now_iso
from .config import AppConfig
from .data import PandasDataSource
from .schema_card import build_schema_card
from .tools import ToolContext, build_registry

_OUT_OF_SCOPE_REPLY = (
    "I can't answer that from this dataset. The available data covers plants, inverters, generation, "
    "weather, alerts, anomalies, and maintenance, but not the missing business inputs needed to compute it."
)
_ITERATION_LIMIT_REPLY = (
    "I couldn't complete that request within the tool step budget. Please try a narrower question "
    "or specify the plant, inverter, metric, or time range."
)
DEFAULT_GATING_MODE = "gated"
GATING_MODES = {"gated", "bind_all"}
_ALWAYS_ON_TOOLS = {"plants", "inverters"}
_TYPE_TOOL_MAP = {
    "A": {"plants", "inverters", "alerts", "maintenance"},
    "B": {
        "plants",
        "inverters",
        "alerts",
        "anomalies",
        "generation_readings",
        "weather_readings",
        "daily_yield",
        "total_yield",
        "performance_ratio",
        "mttr",
        "maintenance_cost",
        "maintenance_duration",
        "ac_power",
    },
    "C": {"plants", "inverters", "anomalies"},
}
_METRIC_TOOL_MAP = {
    "ac_power": {"ac_power"},
    "anomalies": {"anomalies"},
    "daily_yield": {"daily_yield"},
    "maintenance_cost": {"maintenance_cost"},
    "maintenance_duration": {"maintenance_duration"},
    "mttr": {"mttr"},
    "downtime": {"alerts"},
    "performance_ratio": {"performance_ratio"},
    "power_loss": {"anomalies"},
    "tariff_usd_per_kwh": {"plants"},
    "total_yield": {"total_yield"},
    "weather": {"weather_readings"},
}


def _build_synthesis_prompt(
    dataset_today: str,
    reference_now: str,
    *,
    use_reference_now_anchor: bool,
    schema_card: str,
    intent: dict[str, Any],
) -> str:
    time_note = (
        f"Treat \"today\" / \"now\" / relative windows as anchored to the dataset's latest "
        f"timestamp: {dataset_today}. This is NOT the real-world date.\n"
        if use_reference_now_anchor
        else (
            f"Treat \"today\" / \"now\" / relative windows as real-world wall clock time: {reference_now}. "
            f"Do NOT anchor them to the dataset's latest timestamp ({dataset_today}).\n"
        )
    )
    guidance = _build_question_guidance(intent)
    return (
        "You are a solar-plant operations assistant. Answer questions about the dataset using "
        "ONLY the tools provided. Aggregations are computed by the tools — never invent numbers.\n"
        f"{time_note}"
        "If the tools return no data, or the dataset cannot answer the question, say so clearly "
        "and explain what is missing. Never fabricate values. Be concise and factual.\n"
        "When tool results include matched counts, status_counts, IDs, latest readings, or ranked results, "
        "include the requested key counts and identifiers in the answer. For weather questions about today/now, "
        "prefer the latest reading values over all-window averages.\n"
        f"{guidance}\n\n"
        f"{schema_card}"
    )


@dataclass(slots=True)
class PipelineAnswer:
    answer: str
    intent: dict[str, Any]
    intent_meta: dict[str, Any]
    prior_answer_verdict: dict[str, Any] | None = None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    trace_events: list[TraceEvent] = field(default_factory=list)
    gating_mode: str = DEFAULT_GATING_MODE
    bound_tools: list[str] = field(default_factory=list)
    fast_path: str = ""
    iterations: int = 0
    stop_reason: str = ""
    provider_id: str = ""
    telemetry: TelemetrySummary = field(default_factory=lambda: TelemetrySummary(
        started_at=utc_now_iso(),
        finished_at=utc_now_iso(),
        elapsed_ms=0,
    ))


class Pipeline:
    """Holds the loaded dataset + tool registry; one instance per process."""

    def __init__(
        self,
        config: AppConfig,
        *,
        secret_resolver: Callable[[str], str] | None = None,
        session_store: Any | None = None,
    ):
        self._config = config
        self._secret_resolver = secret_resolver
        self._session_store = session_store
        self._data = PandasDataSource(config.resolved_csv_paths())
        self._registry = build_registry()
        self._intent_service = IntentService()
        self._schema_card = build_schema_card()

    @property
    def dataset_today(self):
        return self._data.dataset_today()

    @property
    def reference_now(self) -> datetime:
        return self._resolve_reference_now()

    def _resolve_reference_now(self) -> datetime:
        if self._config.use_reference_now_anchor:
            return self._data.dataset_today()
        return datetime.now().replace(microsecond=0)

    @property
    def tool_registry(self):
        return self._registry

    def answer(
        self,
        question: str,
        *,
        provider_id: str = "",
        gating_mode: str = DEFAULT_GATING_MODE,
        session_id: str = "",
        history_window: list[dict[str, Any]] | None = None,
        prompt_history: list[dict[str, str]] | None = None,
        event_handler: Callable[[TraceEvent], None] | None = None,
    ) -> PipelineAnswer:
        started_at = utc_now_iso()
        started = time.perf_counter()
        trace_events: list[TraceEvent] = []
        normalized_gating = _normalize_gating_mode(gating_mode)
        reference_now = self.reference_now

        def emit(event: TraceEvent) -> None:
            trace_events.append(event)
            if event_handler is not None:
                event_handler(event)

        def emit_graph_event(event: TraceEvent) -> None:
            if event_handler is not None:
                event_handler(event)

        def graph_node(name: str, message: str, fn: Callable[[PipelineRuntimeState], dict[str, Any]]):
            def wrapped(runtime_state: PipelineRuntimeState) -> dict[str, Any]:
                emit_graph_event(make_trace_event("graph_node_started", message, details={"node": name}))
                update = fn(runtime_state)
                emit_graph_event(make_trace_event("graph_node_finished", message, details={"node": name}))
                return update
            return wrapped

        def load_session_context_node(runtime_state: PipelineRuntimeState) -> dict[str, Any]:
            agent_state = build_agent_graph_state(
                runtime_state["question"],
                session_id=session_id,
                session_store=self._session_store,
                history_window=history_window,
                prompt_history=prompt_history,
            )
            return {"agent_state": agent_state}

        def route_local_node(runtime_state: PipelineRuntimeState) -> dict[str, Any]:
            agent_state = runtime_state["agent_state"]
            emit(make_trace_event("intent_started", "Classifying intent"))
            fast_path_env = route_local_turn(runtime_state["question"], prompt_history=agent_state.prompt_history)
            if fast_path_env is None:
                return {}
            intent = fast_path_env["intent"]
            agent_state = apply_turn_routing(
                agent_state,
                intent=intent,
                turn_kind=fast_path_env["turn_kind"],
                fast_path=fast_path_env["fast_path"],
            )
            intent_meta = {
                "provider_name": "",
                "latency_ms": 0,
                "parse_errors": fast_path_env["parse_errors"],
                "fast_path": agent_state.fast_path,
                "turn_kind": agent_state.turn_kind,
                "resolved_question": agent_state.resolved_question,
                "session_id": session_id,
                "graph_nodes": agent_state.graph_nodes,
            }
            emit(make_trace_event("intent_finished", "Intent classified", details={
                "types": intent.get("types", []),
                "metric": intent.get("metric", ""),
                "out_of_scope": bool(intent.get("out_of_scope", False)),
                "turn_kind": agent_state.turn_kind,
                "resolved_question": agent_state.resolved_question,
            }))
            return {
                "agent_state": agent_state,
                "intent": intent,
                "intent_meta": intent_meta,
                "intent_usage": UsageSnapshot(),
                "intent_model_name": "",
                "fast_path": agent_state.fast_path,
            }

        def classify_intent_node(runtime_state: PipelineRuntimeState) -> dict[str, Any]:
            agent_state = runtime_state["agent_state"]
            intent_resolved = resolve_provider(
                self._config, purpose="intent", provider_id=provider_id, secret_resolver=self._secret_resolver,
            )
            intent_model = intent_resolved.model
            context_summary = summarize_prompt_history(agent_state.prompt_history)
            intent_env = self._intent_service.parse(runtime_state["question"], model=intent_model, context_summary=context_summary)
            intent = intent_env["intent"]
            fast_path = intent_env.get("fast_path", "")
            turn_kind = infer_turn_kind(runtime_state["question"], intent=intent, prompt_history=agent_state.prompt_history)
            intent = _backfill_static_lookup_intent(intent, question=runtime_state["question"])
            if turn_kind == "follow_up":
                intent = _backfill_follow_up_intent(
                    intent,
                    question=runtime_state["question"],
                    prompt_history=agent_state.prompt_history,
                )
            agent_state = apply_turn_routing(agent_state, intent=intent, turn_kind=turn_kind, fast_path=fast_path)
            intent_usage = UsageSnapshot(**intent_env.get("usage", {}))
            intent_meta = {
                "provider_name": intent_env.get("provider_name", ""),
                "latency_ms": intent_env.get("latency_ms", 0),
                "parse_errors": intent_env.get("parse_errors", []),
                "fast_path": agent_state.fast_path,
                "turn_kind": agent_state.turn_kind,
                "resolved_question": agent_state.resolved_question,
                "session_id": session_id,
                "graph_nodes": agent_state.graph_nodes,
            }
            if agent_state.resolved_question:
                emit(make_trace_event(
                    "follow_up_resolved",
                    "Resolved follow-up question against recent session context",
                    details={"resolved_question": agent_state.resolved_question},
                ))
            emit(make_trace_event("intent_finished", "Intent classified", details={
                "types": intent.get("types", []),
                "metric": intent.get("metric", ""),
                "out_of_scope": bool(intent.get("out_of_scope", False)),
                "turn_kind": agent_state.turn_kind,
                "resolved_question": agent_state.resolved_question,
            }))
            return {
                "agent_state": agent_state,
                "intent": intent,
                "intent_meta": intent_meta,
                "intent_usage": intent_usage,
                "intent_model_name": model_name_from_model(intent_model),
                "fast_path": agent_state.fast_path,
            }

        def interpret_session_turn_node(runtime_state: PipelineRuntimeState) -> dict[str, Any]:
            agent_state = runtime_state["agent_state"]
            interpretation = derive_turn_interpretation(agent_state, gating_mode=normalized_gating)
            agent_state.turn_interpretation = interpretation
            emit(make_trace_event(
                "session_turn_interpreted",
                "Interpreted session turn",
                details={
                    "turn_action": interpretation.get("turn_action", ""),
                    "turn_kind": agent_state.turn_kind,
                    "tool_policy": interpretation.get("tool_policy", ""),
                },
            ))
            return {"agent_state": agent_state, "turn_interpretation": interpretation}

        def tool_free_reply_node(runtime_state: PipelineRuntimeState) -> dict[str, Any]:
            agent_state = runtime_state["agent_state"]
            answer = (
                _build_prior_answer_meta_reply(
                    runtime_state["question"],
                    prompt_history=agent_state.prompt_history,
                    history_window=agent_state.history_window,
                )
                if agent_state.turn_kind == "prior_answer_meta"
                else build_tool_free_reply(agent_state.turn_kind, fast_path=agent_state.fast_path)
            )
            stop_reason = (
                "final_answer"
                if agent_state.turn_kind == "prior_answer_meta" or agent_state.fast_path == "ambiguous_plant"
                else "fast_path"
            )
            return {"answer": answer, "stop_reason": stop_reason, "fast_path": agent_state.fast_path}

        def out_of_scope_reply_node(runtime_state: PipelineRuntimeState) -> dict[str, Any]:
            return {
                "answer": _build_out_of_scope_reply(
                    runtime_state["intent"],
                    question=runtime_state["question"],
                ),
                "stop_reason": "out_of_scope",
                "fast_path": runtime_state["agent_state"].fast_path,
            }

        def run_tool_loop_node(runtime_state: PipelineRuntimeState) -> dict[str, Any]:
            agent_state = runtime_state["agent_state"]
            intent = runtime_state["intent"]
            tool_names, used_gating_fallback = _select_tool_names(
                intent,
                gating_mode=normalized_gating,
                available_tools=self._registry.names(),
            )
            if used_gating_fallback:
                emit(make_trace_event(
                    "gating_fallback",
                    "Intent classification was empty; using the minimal safe tool subset",
                    details={"tool_names": tool_names, "gating_mode": normalized_gating},
                ))
            synth_resolved = resolve_provider(
                self._config, purpose="synthesis", provider_id=provider_id, secret_resolver=self._secret_resolver,
            )
            synth = synth_resolved.model
            emit(make_trace_event("synthesis_started", "Starting synthesis", details={"tool_names": tool_names}))
            result = _invoke_agent_loop_compat(
                synth,
                system_prompt=_build_synthesis_prompt(
                    self.dataset_today.isoformat(),
                    reference_now.isoformat(),
                    use_reference_now_anchor=self._config.use_reference_now_anchor,
                    schema_card=self._schema_card,
                    intent=intent,
                ),
                user_prompt=agent_state.resolved_question or runtime_state["question"],
                registry=self._registry,
                context=ToolContext(data=self._data, reference_now=lambda: reference_now),
                tool_names=tool_names,
                prompt_history=agent_state.prompt_history,
                tool_args_transform=lambda name, args: _normalize_tool_args_for_question(
                    name=name,
                    args=args,
                    intent=intent,
                    question=agent_state.resolved_question or runtime_state["question"],
                ),
                event_handler=emit,
            )
            answer = _maybe_override_weather_answer(
                answer=result.answer,
                question=agent_state.resolved_question or runtime_state["question"],
                intent=intent,
                tool_calls=result.tool_calls,
                use_reference_now_anchor=self._config.use_reference_now_anchor,
                plant_name_for_id=lambda plant_id: _plant_name_for_id(self._data, plant_id),
            )
            answer = _maybe_override_inverter_count_answer(
                answer=answer,
                question=agent_state.resolved_question or runtime_state["question"],
                tool_calls=result.tool_calls,
                plant_name_for_id=lambda plant_id: _plant_name_for_id(self._data, plant_id),
            )
            answer = _maybe_annotate_single_plant_answer(
                answer=answer,
                tool_calls=result.tool_calls,
                plant_name_for_id=lambda plant_id: _plant_name_for_id(self._data, plant_id),
            )
            if result.stop_reason == "iteration_limit" and not answer.strip():
                answer = _ITERATION_LIMIT_REPLY
                emit(make_trace_event(
                    "synthesis_degraded",
                    "Synthesis stopped at the iteration limit",
                    details={"stop_reason": result.stop_reason},
                ))
            return {
                "answer": answer,
                "stop_reason": result.stop_reason,
                "tool_calls": result.tool_calls,
                "bound_tools": tool_names,
                "iterations": result.iterations,
                "synthesis_usage": result.usage,
                "synthesis_model_name": result.model_name or model_name_from_model(synth),
                "tool_iteration_count": result.tool_iteration_count,
                "turn_latency_ms": result.turn_latency_ms,
                "fast_path": agent_state.fast_path,
            }

        def reconcile_prior_answer_node(runtime_state: PipelineRuntimeState) -> dict[str, Any]:
            agent_state = apply_prior_answer_verdict(
                runtime_state["agent_state"],
                predicate_summary=runtime_state["agent_state"].resolved_question or runtime_state["question"],
                tool_calls=runtime_state.get("tool_calls", []),
            )
            prior_answer_verdict = agent_state.prior_answer_verdict
            if prior_answer_verdict is not None:
                emit(make_trace_event(
                    "reconciliation_finished",
                    "Re-checked the prior answer against fresh tool evidence",
                    details={
                        "status": prior_answer_verdict.get("status", ""),
                        "referenced_message_id": prior_answer_verdict.get("referenced_message_id", 0),
                        "tool_names": prior_answer_verdict.get("tool_names", []),
                    },
                ))
            return {"agent_state": agent_state, "prior_answer_verdict": prior_answer_verdict}

        runtime = compile_runtime_graph(
            load_session_context_node=graph_node("load_session_context", "Loading session context", load_session_context_node),
            route_local_node=graph_node("route_local", "Routing local fast-paths", route_local_node),
            classify_intent_node=graph_node("classify_intent", "Classifying intent and turn kind", classify_intent_node),
            interpret_session_turn_node=graph_node("interpret_session_turn", "Interpreting session turn", interpret_session_turn_node),
            tool_free_reply_node=graph_node("tool_free_reply", "Producing tool-free reply", tool_free_reply_node),
            out_of_scope_reply_node=graph_node("out_of_scope_reply", "Producing out-of-scope reply", out_of_scope_reply_node),
            run_tool_loop_node=graph_node("run_tool_loop", "Running synthesis tool loop", run_tool_loop_node),
            reconcile_prior_answer_node=graph_node(
                "reconcile_prior_answer",
                "Reconciling prior answer against fresh evidence",
                reconcile_prior_answer_node,
            ),
        )
        runtime_state = runtime.invoke({
            "question": question,
            "provider_id": provider_id,
            "gating_mode": normalized_gating,
        })
        agent_state = runtime_state["agent_state"]
        return PipelineAnswer(
            answer=runtime_state.get("answer", ""),
            intent=runtime_state.get("intent", {}),
            intent_meta=runtime_state.get("intent_meta", {}),
            prior_answer_verdict=runtime_state.get("prior_answer_verdict"),
            tool_calls=list(runtime_state.get("tool_calls", [])),
            trace_events=trace_events,
            gating_mode=normalized_gating,
            bound_tools=list(runtime_state.get("bound_tools", [])),
            fast_path=agent_state.fast_path,
            iterations=int(runtime_state.get("iterations", 0)),
            stop_reason=str(runtime_state.get("stop_reason", "")),
            provider_id=provider_id,
            telemetry=_telemetry(
                started_at=started_at,
                started=started,
                intent_model=str(runtime_state.get("intent_model_name", "")),
                synthesis_model=str(runtime_state.get("synthesis_model_name", "")),
                intent_usage=runtime_state.get("intent_usage", UsageSnapshot()),
                synthesis_usage=runtime_state.get("synthesis_usage", UsageSnapshot()),
                tool_iteration_count=int(runtime_state.get("tool_iteration_count", 0)),
                turn_latency_ms=float(runtime_state.get("turn_latency_ms", 0.0)),
            ),
        )


def select_tool_names(intent: dict[str, Any], *, gating_mode: str, available_tools: list[str]) -> list[str]:
    tool_names, _ = _select_tool_names(intent, gating_mode=gating_mode, available_tools=available_tools)
    return tool_names


def _invoke_agent_loop_compat(model: Any, /, **kwargs: Any) -> Any:
    signature = inspect.signature(run_agent_loop)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return run_agent_loop(model, **kwargs)

    supported_kwargs = {
        name: value
        for name, value in kwargs.items()
        if name in signature.parameters
    }
    return run_agent_loop(model, **supported_kwargs)


def _select_tool_names(
    intent: dict[str, Any], *, gating_mode: str, available_tools: list[str]
) -> tuple[list[str], bool]:
    mode = _normalize_gating_mode(gating_mode)
    if mode == "bind_all":
        return list(available_tools), False

    types = intent.get("types")
    if not isinstance(types, list) or not types:
        selected = set(_ALWAYS_ON_TOOLS)
        return [name for name in available_tools if name in selected], True

    selected = set(_ALWAYS_ON_TOOLS)
    metric_selected = _select_metric_tools(intent)
    if metric_selected and set(str(t) for t in types) == {"B"}:
        selected.update(metric_selected)
        return [name for name in available_tools if name in selected], False
    for intent_type in types:
        selected.update(_TYPE_TOOL_MAP.get(str(intent_type), set()))
    return [name for name in available_tools if name in selected], False


def _select_metric_tools(intent: dict[str, Any]) -> set[str]:
    metric = str(intent.get("metric") or "").strip().lower()
    summary = str(intent.get("summary") or "").strip().lower()
    if metric in _METRIC_TOOL_MAP:
        return set(_METRIC_TOOL_MAP[metric])
    if "feed-in tariff" in summary or "feed in tariff" in summary:
        return {"plants"}
    if "performing worst" in summary or "performing best" in summary:
        return {"performance_ratio"}
    return set()


def _backfill_follow_up_intent(
    intent: dict[str, Any],
    *,
    question: str,
    prompt_history: list[dict[str, str]] | None,
) -> dict[str, Any]:
    clean = str(question or "").strip().lower()
    metric_context = latest_metric_context(prompt_history, plant_name=recent_plant_name(prompt_history))
    if not metric_context:
        metric_context = latest_metric_context(prompt_history)
    if not metric_context:
        return intent

    patched = dict(intent)
    types = [str(value) for value in patched.get("types", []) if str(value)]
    if "B" not in types:
        patched["types"] = [*types, "B"]

    if not str(patched.get("metric") or "").strip():
        if "performance ratio" in metric_context:
            patched["metric"] = "performance_ratio"
        elif "yield" in metric_context or "energy" in metric_context:
            patched["metric"] = "daily_yield"
        elif "weather" in metric_context or "cloud cover" in metric_context:
            patched["metric"] = "weather"
        elif "feed-in tariff" in metric_context or "feed in tariff" in metric_context:
            patched["metric"] = "tariff_usd_per_kwh"
        elif "mean time" in metric_context or "mttr" in metric_context:
            patched["metric"] = "mttr"

    if patched.get("metric") in {"performance_ratio", "daily_yield", "weather", "tariff_usd_per_kwh", "mttr"}:
        patched["out_of_scope"] = False

    return patched


def _backfill_static_lookup_intent(intent: dict[str, Any], *, question: str) -> dict[str, Any]:
    clean = str(question or "").strip().lower()
    should_force_a = "nameplate capacity" in clean or (
        clean.startswith("how many inverters does ")
        and (" have?" in clean or clean.endswith(" have"))
    )
    if not should_force_a:
        return intent

    patched = dict(intent)
    types = [str(value) for value in patched.get("types", []) if str(value)]
    if "A" not in types:
        patched["types"] = ["A", *types]
    return patched


def _build_prior_answer_meta_reply(
    question: str,
    *,
    prompt_history: list[dict[str, str]] | None,
    history_window: list[dict[str, Any]] | None,
) -> str:
    clean = str(question or "").strip().lower()
    plant_name = recent_plant_name(prompt_history)
    if "plant" in clean and plant_name:
        return f"That was {plant_name}."

    last_answer = last_assistant_message(history_window)
    if last_answer is not None:
        content = str(last_answer.get("content", "")).strip()
        if content:
            return content

    return (
        "I couldn't find a prior answer in this session. Restate the data question "
        "you want me to check."
    )


def _build_question_guidance(intent: dict[str, Any]) -> str:
    metric = str(intent.get("metric") or "").strip().lower()
    types = {str(value) for value in intent.get("types", [])}
    guidance: list[str] = []
    if metric == "tariff_usd_per_kwh":
        guidance.append(
            "- For feed-in tariff questions, use the plants tool and rank plant records by tariff_usd_per_kwh."
        )
    if metric == "performance_ratio":
        guidance.append(
            '- For "performing worst right now", call performance_ratio with aggregate_by="plant", sort_order="asc", window="last_week" (unless the user specifies a window). '
            'The first result in the response is the worst plant. Report the plant_name and avg_performance_ratio from that first result.'
        )
        guidance.append(
            '- For "best inverter on performance ratio" (or "tops the fleet"), call performance_ratio with aggregate_by="inverter", sort_order="desc", window="all_time". '
            'Report the inverter_id (not plant_id) from the first result, in lowercase (e.g. inv_4137001_04).'
        )
        guidance.append(
            '- For "performance ratio at night" or zero-DC/no-generation PR questions, call performance_ratio with dc_voltage="zero". '
            'If the tool returns verdict="undefined", answer that night-time performance ratio is undefined rather than refusing.'
        )
    if metric == "total_yield":
        guidance.append(
            "- For total energy generated questions, use total_yield over the requested window instead of raw reading averages."
        )
    if metric == "mttr":
        guidance.append(
            '- For MTTR questions, call the mttr tool before answering. For "open alerts", call mttr with status="open" '
            'and use the returned verdict/reason; open alerts have no resolved_at timestamp and therefore no MTTR inputs.'
        )
    if metric == "downtime":
        guidance.append(
            '- For total downtime questions, call alerts with status="resolved" when the user asks about resolved alerts. '
            "Use total_downtime_minutes from the alerts result. Do not use mttr; MTTR is mean resolution time, not downtime_minutes."
        )
    if metric == "alerts_and_anomalies" or ("A" in types and "C" in types):
        guidance.append(
            '- For child-to-sibling inverter chains such as "the inverter in fault, what alert and anomalies", '
            'first call inverters with status="fault". Then copy the exact inverter_id from that result into both '
            'alerts(inverter=...) and anomalies(inverter=...). Do not use "*" or "all" for the downstream inverter filter. '
            'For "what anomalies does it have", do not add an anomaly status filter unless the user explicitly asks for open, active, or unresolved anomalies.'
        )
    if metric == "weather" or ("A" in types and "B" in types):
        guidance.append(
            "- For weather questions about today/now, use weather_readings and prefer the latest reading in the anchored window."
        )
    if "A" in types and "B" not in types:
        guidance.append(
            "- When a question asks for inverters matching a status condition PLUS an alert condition "
            "(e.g. 'online inverters with open alerts'), call alerts and inverters separately, "
            "then list ALL inverter IDs from 'matched_inverter_ids' in the alerts response. "
            "Report the total alert count from 'matched'. Do not query inverters one by one."
        )
    if "C" in types or metric == "anomalies":
        guidance.append(
            "- For anomaly queries that combine status + anomaly_type + cause (e.g. 'open hotspot caused by soiling'), "
            "pass ALL three criteria in a SINGLE anomalies tool call. Do not call the tool once per criterion. "
            "The tool applies all filters together and returns only the matching records. "
            "Start your answer by restating the anomaly type and cause (e.g. 'N hotspot anomalies caused by soiling match'), "
            "using the integer from 'matched' as N. "
            "Then list the inverter IDs from 'matched_inverter_ids' and include the anomaly_ids."
        )
    if not guidance:
        return ""
    return "Question-specific guidance:\n" + "\n".join(guidance)


def _normalize_tool_args_for_question(
    *,
    name: str,
    args: dict[str, Any],
    intent: dict[str, Any],
    question: str,
) -> dict[str, Any]:
    normalized = dict(args)
    metric = str(intent.get("metric") or "").strip().lower()
    clean = str(question or "").strip().lower()

    if name == "alerts" and metric == "downtime" and "resolved alert" in clean:
        normalized.setdefault("status", "resolved")
    elif name == "mttr" and metric == "mttr" and "open alert" in clean:
        normalized["status"] = "open"
    elif name == "maintenance_cost" and metric == "maintenance_cost":
        if any(term in clean for term in ("done tickets", "completed maintenance", "completed tickets")):
            normalized.setdefault("status", "done")
    elif name == "maintenance_duration" and metric == "maintenance_duration":
        if any(term in clean for term in ("completed maintenance", "completed tickets", "done tickets")):
            normalized.setdefault("status", "done")

    return normalized


def _normalize_gating_mode(gating_mode: str) -> str:
    mode = str(gating_mode or DEFAULT_GATING_MODE).strip().lower()
    if mode not in GATING_MODES:
        raise ValueError(f"Unknown gating_mode {gating_mode!r}. Expected one of: {sorted(GATING_MODES)}")
    return mode


def _build_out_of_scope_reply(intent: dict[str, Any], *, question: str = "") -> str:
    metric = str(intent.get("metric") or "").strip().lower()
    if metric in {"revenue", "revenue_loss", "lost_revenue", "downtime_revenue"}:
        return (
            "I can't calculate revenue loss from this dataset because it does not include the business "
            "inputs needed for that number, such as contractual downtime assumptions or lost-energy valuation."
        )
    if _is_forecast_generation_question(intent, question):
        return (
            "I can't answer that from this dataset because it contains historical/observed generation data, "
            "not forecast data for future periods."
        )
    return _OUT_OF_SCOPE_REPLY


def _is_forecast_generation_question(intent: dict[str, Any], question: str) -> bool:
    text = " ".join(
        str(part or "")
        for part in (
            question,
            intent.get("summary"),
            intent.get("metric"),
            intent.get("time_range"),
        )
    ).lower()
    forecast_terms = ("forecast", "predict", "projection", "next week", "future")
    generation_terms = ("generation", "yield", "power", "energy")
    return any(term in text for term in forecast_terms) and any(term in text for term in generation_terms)


def _maybe_override_weather_answer(
    *,
    answer: str,
    question: str,
    intent: dict[str, Any],
    tool_calls: list[ToolCallRecord],
    use_reference_now_anchor: bool,
    plant_name_for_id: Callable[[Any], str | None],
) -> str:
    if not use_reference_now_anchor or not _is_anchored_weather_snapshot_question(question, intent):
        return answer

    latest_reading, latest_timestamp = _latest_weather_snapshot(tool_calls)
    if latest_reading is None:
        return answer

    return _render_weather_snapshot_answer(
        latest_reading=latest_reading,
        latest_timestamp=latest_timestamp,
        plant_name=plant_name_for_id(latest_reading.get("plant_id")),
    )


def _is_anchored_weather_snapshot_question(question: str, intent: dict[str, Any]) -> bool:
    clean = str(question or "").strip().lower()
    if not any(token in clean for token in ("today", "now", "right now", "current", "snapshot")):
        return False

    metric = str(intent.get("metric") or "").strip().lower()
    summary = str(intent.get("summary") or "").strip().lower()
    if metric == "weather" or "weather" in summary:
        return True
    return any(token in clean for token in ("weather", "temperature", "irradiation", "wind", "humidity", "rainfall", "cloud"))


def _latest_weather_snapshot(tool_calls: list[ToolCallRecord]) -> tuple[dict[str, Any] | None, str]:
    for call in reversed(tool_calls):
        if call.name != "weather_readings":
            continue
        result = call.result if isinstance(call.result, dict) else {}
        latest_reading = result.get("latest_reading")
        if not isinstance(latest_reading, dict) or not latest_reading:
            continue
        if str(result.get("aggregate_by") or "overall").strip().lower() != "overall":
            continue
        return latest_reading, str(result.get("latest_timestamp") or latest_reading.get("timestamp") or "").strip()
    return None, ""


def _render_weather_snapshot_answer(
    *,
    latest_reading: dict[str, Any],
    latest_timestamp: str,
    plant_name: str | None,
) -> str:
    plant_id = _normalized_plant_id(latest_reading.get("plant_id"))
    site = plant_name or (f"Plant {plant_id}" if plant_id else f"Plant {latest_reading.get('plant_id')}")
    if plant_name and plant_id:
        site = f"{plant_name} ({plant_id})"
    metrics = [
        ("ambient", latest_reading.get("ambient_temp"), "C"),
        ("module", latest_reading.get("module_temp"), "C"),
        ("irradiation", latest_reading.get("irradiation"), "W/m2"),
        ("POA", latest_reading.get("poa_irradiance"), "W/m2"),
        ("wind", latest_reading.get("wind_speed"), "m/s"),
        ("humidity", latest_reading.get("humidity"), "%"),
        ("cloud cover", latest_reading.get("cloud_cover_pct"), "%"),
        ("rainfall", latest_reading.get("rainfall_mm"), "mm"),
    ]
    details = ", ".join(
        f"{label} {_format_weather_value(value)} {unit}"
        for label, value, unit in metrics
        if _format_weather_value(value)
    )
    timestamp_note = f" at {latest_timestamp}" if latest_timestamp else ""
    return f"{site} weather snapshot{timestamp_note}: {details}."


def _format_weather_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value).strip()


def _plant_name_for_id(data: PandasDataSource, plant_id: Any) -> str | None:
    if plant_id is None:
        return None
    plants = data.table("plants")
    matches = plants[plants["plant_id"].astype(str) == str(plant_id)]
    if matches.empty:
        return None
    return str(matches.iloc[0]["name"]).strip() or None


def _maybe_override_inverter_count_answer(
    *,
    answer: str,
    question: str,
    tool_calls: list[ToolCallRecord],
    plant_name_for_id: Callable[[Any], str | None],
) -> str:
    clean = str(question or "").strip().lower()
    if not (
        clean.startswith("how many inverters does ")
        and (" have?" in clean or clean.endswith(" have"))
    ):
        return answer

    for call in reversed(tool_calls):
        if call.name != "inverters" or not isinstance(call.result, dict):
            continue
        matched = call.result.get("matched")
        if not isinstance(matched, int):
            continue
        plant_id = _single_result_plant_id(call.result)
        if plant_id is None:
            continue
        plant_name = plant_name_for_id(plant_id) or f"Plant {plant_id}"
        return f"{plant_name} has {matched} inverters."

    return answer


def _single_result_plant_id(result: dict[str, Any]) -> str | None:
    inverters = result.get("inverters")
    if not isinstance(inverters, list) or not inverters:
        return None

    plant_ids = {
        _normalized_plant_id(item.get("plant_id"))
        for item in inverters
        if isinstance(item, dict)
    }
    plant_ids.discard(None)
    if len(plant_ids) != 1:
        return None
    return str(next(iter(plant_ids)))


def _maybe_annotate_single_plant_answer(
    *,
    answer: str,
    tool_calls: list[ToolCallRecord],
    plant_name_for_id: Callable[[Any], str | None],
) -> str:
    plant_ids = sorted({
        plant_id
        for call in tool_calls
        for plant_id in _extract_plant_ids(call.args) | _extract_plant_ids(call.result)
        if plant_id
    })
    if len(plant_ids) != 1:
        return answer

    plant_id = plant_ids[0]
    if _answer_mentions_plant_id(answer, plant_id):
        return answer

    plant_name = plant_name_for_id(plant_id)
    if plant_name:
        pattern = re.compile(rf"\b{re.escape(plant_name)}\b", re.IGNORECASE)
        if pattern.search(answer):
            return pattern.sub(f"{plant_name} ({plant_id})", answer, count=1)

    answer = answer.rstrip()
    if answer.endswith("."):
        return f"{answer} Plant ID: {plant_id}."
    return f"{answer} Plant ID: {plant_id}."


def _extract_plant_ids(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "plant_id":
                normalized = _normalized_plant_id(nested)
                if normalized:
                    found.add(normalized)
            found.update(_extract_plant_ids(nested))
        return found
    if isinstance(value, list):
        for item in value:
            found.update(_extract_plant_ids(item))
    return found


def _answer_mentions_plant_id(answer: str, plant_id: str) -> bool:
    patterns = (
        rf"\({re.escape(plant_id)}\)",
        rf"\bplant_id\b\D*{re.escape(plant_id)}\b",
        rf"\bplant id\b\D*{re.escape(plant_id)}\b",
    )
    return any(re.search(pattern, answer, flags=re.IGNORECASE) for pattern in patterns)


def _normalized_plant_id(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()

def _telemetry(
    *,
    started_at: str,
    started: float,
    intent_model: str,
    intent_usage: UsageSnapshot,
    synthesis_model: str = "",
    synthesis_usage: UsageSnapshot | None = None,
    tool_iteration_count: int = 0,
    turn_latency_ms: float = 0.0,
) -> TelemetrySummary:
    return TelemetrySummary(
        started_at=started_at,
        finished_at=utc_now_iso(),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        intent_model=intent_model,
        synthesis_model=synthesis_model,
        intent_usage=intent_usage,
        synthesis_usage=synthesis_usage or UsageSnapshot(),
        tool_iteration_count=tool_iteration_count,
        turn_latency_ms=turn_latency_ms,
    )
