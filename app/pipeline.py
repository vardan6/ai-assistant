"""Pipeline — the orchestration brain wired end to end.

question -> [smalltalk fast-path?] -> intent classification (explicit, logged)
         -> agent tool-calling loop -> answer with explicit degradation.

Tool gating (gated | bind_all) and derived-metric tools arrive in later slices;
the tool list is selected per request from explicit intent.
"""
from __future__ import annotations

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
from .ai.agent_graph import build_prior_answer_verdict, resolve_follow_up_question, summarize_prompt_history
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
    "B": {"plants", "inverters", "alerts", "anomalies", "generation_readings", "weather_readings", "daily_yield", "total_yield", "performance_ratio", "mttr"},
    "C": {"plants", "inverters", "anomalies"},
}
_METRIC_TOOL_MAP = {
    "anomalies": {"anomalies"},
    "daily_yield": {"daily_yield"},
    "mttr": {"mttr"},
    "performance_ratio": {"performance_ratio"},
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

    def __init__(self, config: AppConfig, *, secret_resolver: Callable[[str], str] | None = None):
        self._config = config
        self._secret_resolver = secret_resolver
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

        # 1) Local fast-paths must short-circuit before provider/model resolution.
        emit(make_trace_event("intent_started", "Classifying intent"))
        fast_path_env = route_local_turn(question, prompt_history=prompt_history)
        if fast_path_env is not None:
            intent = fast_path_env["intent"]
            fast_path = fast_path_env["fast_path"]
            turn_kind = fast_path_env["turn_kind"]
            intent_meta = {
                "provider_name": "",
                "latency_ms": 0,
                "parse_errors": fast_path_env["parse_errors"],
                "fast_path": fast_path,
                "turn_kind": turn_kind,
                "resolved_question": "",
                "session_id": session_id,
            }
            emit(make_trace_event("intent_finished", "Intent classified", details={
                "types": intent.get("types", []),
                "metric": intent.get("metric", ""),
                "out_of_scope": bool(intent.get("out_of_scope", False)),
                "turn_kind": turn_kind,
                "resolved_question": "",
            }))
            return PipelineAnswer(
                answer=build_tool_free_reply(turn_kind, fast_path=fast_path),
                intent=intent,
                intent_meta=intent_meta,
                prior_answer_verdict=None,
                trace_events=trace_events,
                gating_mode=normalized_gating,
                fast_path=fast_path,
                stop_reason="final_answer" if fast_path == "ambiguous_plant" else "fast_path",
                provider_id=provider_id,
                telemetry=_telemetry(
                    started_at=started_at,
                    started=started,
                    intent_model="",
                    intent_usage=UsageSnapshot(),
                ),
            )

        # 2) Intent classification (explicit + inspectable). Use the intent
        #    routing purpose so a cheaper/local model can be used here later.
        intent_resolved = resolve_provider(
            self._config, purpose="intent", provider_id=provider_id,
            secret_resolver=self._secret_resolver,
        )
        intent_model = intent_resolved.model
        context_summary = summarize_prompt_history(prompt_history)
        intent_env = self._intent_service.parse(question, model=intent_model, context_summary=context_summary)
        intent = intent_env["intent"]
        fast_path = intent_env.get("fast_path", "")
        turn_kind = infer_turn_kind(question, intent=intent, prompt_history=prompt_history)
        resolved_question = ""
        if turn_kind == "follow_up":
            resolved_question = resolve_follow_up_question(question, prompt_history)
        intent_usage = UsageSnapshot(**intent_env.get("usage", {}))

        intent_meta = {
            "provider_name": intent_env.get("provider_name", ""),
            "latency_ms": intent_env.get("latency_ms", 0),
            "parse_errors": intent_env.get("parse_errors", []),
            "fast_path": fast_path,
            "turn_kind": turn_kind,
            "resolved_question": resolved_question,
            "session_id": session_id,
        }
        if resolved_question:
            emit(make_trace_event(
                "follow_up_resolved",
                "Resolved follow-up question against recent session context",
                details={"resolved_question": resolved_question},
            ))
        emit(make_trace_event("intent_finished", "Intent classified", details={
            "types": intent.get("types", []),
            "metric": intent.get("metric", ""),
            "out_of_scope": bool(intent.get("out_of_scope", False)),
            "turn_kind": turn_kind,
            "resolved_question": resolved_question,
        }))

        # 3) Route tool-free branches before the data/tool path.
        if is_tool_free_turn(turn_kind):
            return PipelineAnswer(
                answer=build_tool_free_reply(turn_kind, fast_path=fast_path),
                intent=intent,
                intent_meta=intent_meta,
                prior_answer_verdict=None,
                trace_events=trace_events,
                gating_mode=normalized_gating,
                fast_path=fast_path,
                stop_reason="fast_path",
                provider_id=provider_id,
                telemetry=_telemetry(
                    started_at=started_at,
                    started=started,
                    intent_model=model_name_from_model(intent_model),
                    intent_usage=intent_usage,
                ),
            )

        # 4) Explicit out-of-scope only short-circuits inside the data branch.
        if turn_kind == "out_of_scope" and intent.get("out_of_scope") is True:
            return PipelineAnswer(
                answer=_build_out_of_scope_reply(intent),
                intent=intent,
                intent_meta=intent_meta,
                prior_answer_verdict=None,
                trace_events=trace_events,
                gating_mode=normalized_gating,
                fast_path=fast_path,
                stop_reason="out_of_scope",
                provider_id=provider_id,
                telemetry=_telemetry(
                    started_at=started_at,
                    started=started,
                    intent_model=model_name_from_model(intent_model),
                    intent_usage=intent_usage,
                ),
            )

        # 5) Tool-calling loop for synthesis.
        tool_names, used_gating_fallback = _select_tool_names(intent, gating_mode=normalized_gating, available_tools=self._registry.names())
        if used_gating_fallback:
            emit(make_trace_event(
                "gating_fallback",
                "Intent classification was empty; using the minimal safe tool subset",
                details={"tool_names": tool_names, "gating_mode": normalized_gating},
            ))
        synth_resolved = resolve_provider(
            self._config, purpose="synthesis", provider_id=provider_id,
            secret_resolver=self._secret_resolver,
        )
        synth = synth_resolved.model
        emit(make_trace_event("synthesis_started", "Starting synthesis", details={"tool_names": tool_names}))
        result = run_agent_loop(
            synth,
            system_prompt=_build_synthesis_prompt(
                self.dataset_today.isoformat(),
                reference_now.isoformat(),
                use_reference_now_anchor=self._config.use_reference_now_anchor,
                schema_card=self._schema_card,
                intent=intent,
            ),
            user_prompt=resolved_question or question,
            registry=self._registry,
            context=ToolContext(data=self._data, reference_now=lambda: reference_now),
            tool_names=tool_names,
            event_handler=emit,
        )
        answer = result.answer
        if result.stop_reason == "iteration_limit" and not answer.strip():
            answer = _ITERATION_LIMIT_REPLY
            emit(make_trace_event(
                "synthesis_degraded",
                "Synthesis stopped at the iteration limit",
                details={"stop_reason": result.stop_reason},
            ))
        prior_answer_verdict = None
        if turn_kind == "dispute_correction":
            prior_answer_verdict = build_prior_answer_verdict(
                history_window=history_window,
                predicate_summary=resolved_question or question,
                tool_calls=result.tool_calls,
            )
            emit(make_trace_event(
                "reconciliation_finished",
                "Re-checked the prior answer against fresh tool evidence",
                details={
                    "status": prior_answer_verdict.get("status", ""),
                    "referenced_message_id": prior_answer_verdict.get("referenced_message_id", 0),
                    "tool_names": prior_answer_verdict.get("tool_names", []),
                },
            ))
        return PipelineAnswer(
            answer=answer,
            intent=intent,
            intent_meta=intent_meta,
            prior_answer_verdict=prior_answer_verdict,
            tool_calls=result.tool_calls,
            trace_events=trace_events,
            gating_mode=normalized_gating,
            bound_tools=tool_names,
            fast_path=fast_path,
            iterations=result.iterations,
            stop_reason=result.stop_reason,
            provider_id=provider_id,
            telemetry=_telemetry(
                started_at=started_at,
                started=started,
                intent_model=model_name_from_model(intent_model),
                synthesis_model=result.model_name or model_name_from_model(synth),
                intent_usage=intent_usage,
                synthesis_usage=result.usage,
            ),
        )


def select_tool_names(intent: dict[str, Any], *, gating_mode: str, available_tools: list[str]) -> list[str]:
    tool_names, _ = _select_tool_names(intent, gating_mode=gating_mode, available_tools=available_tools)
    return tool_names


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
    if metric == "total_yield":
        guidance.append(
            "- For total energy generated questions, use total_yield over the requested window instead of raw reading averages."
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


def _normalize_gating_mode(gating_mode: str) -> str:
    mode = str(gating_mode or DEFAULT_GATING_MODE).strip().lower()
    if mode not in GATING_MODES:
        raise ValueError(f"Unknown gating_mode {gating_mode!r}. Expected one of: {sorted(GATING_MODES)}")
    return mode


def _build_out_of_scope_reply(intent: dict[str, Any]) -> str:
    metric = str(intent.get("metric") or "").strip().lower()
    if metric in {"revenue", "revenue_loss", "lost_revenue", "downtime_revenue"}:
        return (
            "I can't calculate revenue loss from this dataset because it does not include the business "
            "inputs needed for that number, such as contractual downtime assumptions or lost-energy valuation."
        )
    return _OUT_OF_SCOPE_REPLY

def _telemetry(
    *,
    started_at: str,
    started: float,
    intent_model: str,
    intent_usage: UsageSnapshot,
    synthesis_model: str = "",
    synthesis_usage: UsageSnapshot | None = None,
) -> TelemetrySummary:
    return TelemetrySummary(
        started_at=started_at,
        finished_at=utc_now_iso(),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        intent_model=intent_model,
        synthesis_model=synthesis_model,
        intent_usage=intent_usage,
        synthesis_usage=synthesis_usage or UsageSnapshot(),
    )
