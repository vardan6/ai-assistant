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
from .ai.agent_traces import make_trace_event
from .ai.intent_schema import make_empty_intent
from .ai.smalltalk import is_smalltalk
from .ai.usage_telemetry import model_name_from_model, utc_now_iso
from .config import AppConfig
from .data import PandasDataSource
from .schema_card import build_schema_card
from .tools import ToolContext, build_registry

_SMALLTALK_REPLY = "Hi! I can answer questions about the solar plants, inverters, generation, alerts, anomalies, and maintenance. What would you like to know?"
_EMPTY_PROMPT_REPLY = "Please ask a question about the solar operations dataset."
_AMBIGUOUS_PLANT_REPLY = "Which plant do you mean? The dataset has Rajasthan Solar Park, Gujarat Solar Farm, and Tamil Nadu PV Plant."
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
        fast_path_env = _local_fast_path(question)
        if fast_path_env is not None:
            intent = fast_path_env["intent"]
            fast_path = fast_path_env["fast_path"]
            intent_meta = {
                "provider_name": "",
                "latency_ms": 0,
                "parse_errors": fast_path_env["parse_errors"],
                "fast_path": fast_path,
            }
            emit(make_trace_event("intent_finished", "Intent classified", details={
                "types": intent.get("types", []),
                "metric": intent.get("metric", ""),
                "out_of_scope": bool(intent.get("out_of_scope", False)),
            }))
            return PipelineAnswer(
                answer=_fast_path_answer(fast_path),
                intent=intent,
                intent_meta=intent_meta,
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
        intent_env = self._intent_service.parse(question, model=intent_model)
        intent = intent_env["intent"]
        fast_path = intent_env.get("fast_path", "")
        intent_usage = UsageSnapshot(**intent_env.get("usage", {}))

        intent_meta = {
            "provider_name": intent_env.get("provider_name", ""),
            "latency_ms": intent_env.get("latency_ms", 0),
            "parse_errors": intent_env.get("parse_errors", []),
            "fast_path": fast_path,
        }
        emit(make_trace_event("intent_finished", "Intent classified", details={
            "types": intent.get("types", []),
            "metric": intent.get("metric", ""),
            "out_of_scope": bool(intent.get("out_of_scope", False)),
        }))

        # 3) Explicit out-of-scope questions short-circuit before synthesis.
        if intent.get("out_of_scope") is True:
            return PipelineAnswer(
                answer=_build_out_of_scope_reply(intent),
                intent=intent,
                intent_meta=intent_meta,
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

        # 4) Tool-calling loop for synthesis.
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
            user_prompt=question,
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
        return PipelineAnswer(
            answer=answer,
            intent=intent,
            intent_meta=intent_meta,
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
            '- For "performing worst/best right now", use performance_ratio aggregated by plant over window="last_week" unless the user gives another window, and state that metric explicitly.'
        )
    if metric == "total_yield":
        guidance.append(
            "- For total energy generated questions, use total_yield over the requested window instead of raw reading averages."
        )
    if metric == "weather" or ("A" in types and "B" in types):
        guidance.append(
            "- For weather questions about today/now, use weather_readings and prefer the latest reading in the anchored window."
        )
    if "C" in types or metric == "anomalies":
        guidance.append(
            "- For anomaly answers, if the anomalies tool returns anomaly_ids, include those ids in the final answer."
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


def _local_fast_path(question: str) -> dict[str, Any] | None:
    clean = str(question or "").strip()
    clean_lower = clean.lower()
    if not clean:
        return {
            "intent": make_empty_intent(),
            "parse_errors": ["empty prompt"],
            "fast_path": "empty",
        }

    if clean_lower in {"how is the plant doing?", "how is the plant doing"}:
        intent = make_empty_intent()
        intent["summary"] = "Ambiguous plant status question"
        intent["confidence"] = 1.0
        return {
            "intent": intent,
            "parse_errors": [],
            "fast_path": "ambiguous_plant",
        }

    if not is_smalltalk(clean):
        return None

    intent = make_empty_intent()
    intent["summary"] = "Smalltalk / greeting"
    intent["confidence"] = 1.0
    return {
        "intent": intent,
        "parse_errors": [],
        "fast_path": "smalltalk",
    }


def _fast_path_answer(fast_path: str) -> str:
    if fast_path == "smalltalk":
        return _SMALLTALK_REPLY
    if fast_path == "ambiguous_plant":
        return _AMBIGUOUS_PLANT_REPLY
    return _EMPTY_PROMPT_REPLY


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
