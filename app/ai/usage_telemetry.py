"""Usage/timing normalization shared across providers and surfaces."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class UsageSnapshot:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    def add(self, other: "UsageSnapshot") -> "UsageSnapshot":
        return UsageSnapshot(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
        )

    @property
    def cache_hit_rate(self) -> float:
        cache_total = self.cache_read_tokens + self.cache_creation_tokens
        if cache_total <= 0:
            return 0.0
        return self.cache_read_tokens / cache_total

    def as_dict(self) -> dict[str, int | float]:
        payload = asdict(self)
        payload["cache_hit_rate"] = self.cache_hit_rate
        return payload


@dataclass(slots=True)
class TelemetrySummary:
    started_at: str
    finished_at: str
    elapsed_ms: int
    intent_model: str = ""
    synthesis_model: str = ""
    intent_usage: UsageSnapshot = field(default_factory=UsageSnapshot)
    synthesis_usage: UsageSnapshot = field(default_factory=UsageSnapshot)
    tool_iteration_count: int = 0
    turn_latency_ms: float = 0.0

    @property
    def total_usage(self) -> UsageSnapshot:
        return self.intent_usage.add(self.synthesis_usage)

    def as_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_ms": self.elapsed_ms,
            "intent_model": self.intent_model,
            "synthesis_model": self.synthesis_model,
            "intent_usage": self.intent_usage.as_dict(),
            "synthesis_usage": self.synthesis_usage.as_dict(),
            "total_usage": self.total_usage.as_dict(),
            "tool_iteration_count": self.tool_iteration_count,
            "turn_latency_ms": self.turn_latency_ms,
        }


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def usage_from_response(response: Any) -> UsageSnapshot:
    usage = getattr(response, "usage_metadata", None)
    if not isinstance(usage, dict):
        metadata = getattr(response, "response_metadata", None)
        if isinstance(metadata, dict):
            candidate = metadata.get("token_usage") or metadata.get("usage") or metadata.get("usage_metadata")
            if isinstance(candidate, dict):
                usage = candidate
    if not isinstance(usage, dict):
        return UsageSnapshot()

    input_tokens = _first_int(usage, "input_tokens", "prompt_tokens", "input_token_count")
    output_tokens = _first_int(usage, "output_tokens", "completion_tokens", "output_token_count")
    total_tokens = _first_int(usage, "total_tokens", "total_token_count")
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    details = usage.get("input_token_details") or {}
    cache_read_tokens = _first_int(details, "cache_read")
    cache_creation_tokens = _cache_creation_tokens(details)
    return UsageSnapshot(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens,
    )


def model_name_from_model(model: Any) -> str:
    return str(
        getattr(model, "model_name", None)
        or getattr(model, "model", None)
        or getattr(model, "model_id", None)
        or ""
    )


def _first_int(payload: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = payload.get(key)
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _cache_creation_tokens(details: dict[str, Any]) -> int:
    specific_total = _first_int(details, "ephemeral_5m_input_tokens") + _first_int(details, "ephemeral_1h_input_tokens")
    if specific_total > 0:
        return specific_total
    return _first_int(details, "cache_creation")
