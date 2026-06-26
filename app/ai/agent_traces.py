"""Structured trace events for CLI/server surfaces."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .usage_telemetry import utc_now_iso


@dataclass(slots=True)
class TraceEvent:
    kind: str
    timestamp: str
    message: str
    iteration: int = 0
    tool_name: str = ""
    latency_ms: int = 0
    ok: bool | None = None
    details: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_trace_event(
    kind: str,
    message: str,
    *,
    iteration: int = 0,
    tool_name: str = "",
    latency_ms: int = 0,
    ok: bool | None = None,
    details: dict[str, Any] | None = None,
) -> TraceEvent:
    return TraceEvent(
        kind=kind,
        timestamp=utc_now_iso(),
        message=message,
        iteration=iteration,
        tool_name=tool_name,
        latency_ms=latency_ms,
        ok=ok,
        details=details,
    )
