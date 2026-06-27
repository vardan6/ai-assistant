"""Pipeline — the orchestration brain wired end to end.

question -> [smalltalk fast-path?] -> intent classification (explicit, logged)
         -> agent tool-calling loop -> refusal-guarded answer.

Tool gating (gated | bind_all) and derived-metric tools arrive in later slices;
the tool list is selected per request from explicit intent.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
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
from .ai.usage_telemetry import model_name_from_model, utc_now_iso
from .config import AppConfig
from .data import PandasDataSource
from .tools import ToolContext, build_registry

_SMALLTALK_REPLY = "Hi! I can answer questions about the solar plants, inverters, generation, alerts, anomalies, and maintenance. What would you like to know?"
_OUT_OF_SCOPE_REPLY = (
    "I can't answer that from this dataset. The available data covers plants, inverters, generation, "
    "weather, alerts, anomalies, and maintenance, but not the missing business inputs needed to compute it."
)
DEFAULT_GATING_MODE = "gated"
GATING_MODES = {"gated", "bind_all"}
_ALWAYS_ON_TOOLS = {"plants", "inverters"}
_TYPE_TOOL_MAP = {
    "A": {"plants", "inverters", "alerts", "maintenance"},
    "B": {"plants", "inverters", "generation_readings", "weather_readings", "daily_yield", "performance_ratio", "mttr"},
    "C": {"plants", "inverters", "anomalies"},
}


def _build_synthesis_prompt(dataset_today: str) -> str:
    return (
        "You are a solar-plant operations assistant. Answer questions about the dataset using "
        "ONLY the tools provided. Aggregations are computed by the tools — never invent numbers.\n"
        f"Treat \"today\" / \"now\" / relative windows as anchored to the dataset's latest "
        f"timestamp: {dataset_today}. This is NOT the real-world date.\n"
        "If the tools return no data, or the dataset cannot answer the question, say so clearly "
        "and explain what is missing. Never fabricate values. Be concise and factual."
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
        self._data = PandasDataSource(config.csv_dir)
        self._registry = build_registry()
        self._intent_service = IntentService()
        self._context = ToolContext(data=self._data)

    @property
    def dataset_today(self):
        return self._data.dataset_today()

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

        def emit(event: TraceEvent) -> None:
            trace_events.append(event)
            if event_handler is not None:
                event_handler(event)

        # 1) Intent classification (explicit + inspectable). Use the intent
        #    routing purpose so a cheaper/local model can be used here later.
        emit(make_trace_event("intent_started", "Classifying intent"))
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

        # 2) Smalltalk short-circuits before any tool/LLM synthesis.
        if fast_path == "smalltalk":
            return PipelineAnswer(
                answer=_SMALLTALK_REPLY,
                intent=intent,
                intent_meta=intent_meta,
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

        # 3) Tool-calling loop for synthesis.
        tool_names = select_tool_names(intent, gating_mode=normalized_gating, available_tools=self._registry.names())
        synth_resolved = resolve_provider(
            self._config, purpose="synthesis", provider_id=provider_id,
            secret_resolver=self._secret_resolver,
        )
        synth = synth_resolved.model
        emit(make_trace_event("synthesis_started", "Starting synthesis", details={"tool_names": tool_names}))
        result = run_agent_loop(
            synth,
            system_prompt=_build_synthesis_prompt(self.dataset_today.isoformat()),
            user_prompt=question,
            registry=self._registry,
            context=self._context,
            tool_names=tool_names,
            event_handler=emit,
        )
        return PipelineAnswer(
            answer=result.answer,
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
    mode = _normalize_gating_mode(gating_mode)
    available = set(available_tools)
    if mode == "bind_all":
        return [name for name in available_tools if name in available]

    types = intent.get("types")
    if not isinstance(types, list) or not types:
        return [name for name in available_tools if name in available]

    selected = set(_ALWAYS_ON_TOOLS)
    for intent_type in types:
        selected.update(_TYPE_TOOL_MAP.get(str(intent_type), set()))
    return [name for name in available_tools if name in selected and name in available]


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
