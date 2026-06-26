"""Generation readings tool."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .common import clamp_limit, counts, filter_exact, filter_plant, records
from .registry import ToolContext, ToolRegistry, ToolSpec

_FIELDS = [
    "reading_id",
    "timestamp",
    "plant_id",
    "inverter_id",
    "ac_power",
    "expected_ac_power",
    "performance_ratio",
    "daily_yield",
    "status_flag",
]

PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
        "inverter": {"type": "string", "description": "Filter by inverter_id."},
        "status_flag": {"type": "string", "description": "Filter by reading status flag."},
        "limit": {"type": "integer", "description": "How many recent readings to include (1-20)."},
    },
    "additionalProperties": False,
}


def generation_summary(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    status_flag: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    source = context.data.table("generation_readings")
    frame = filter_plant(source, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = filter_exact(frame, "status_flag", status_flag)
    frame = frame.sort_values("timestamp", ascending=False)
    limited = clamp_limit(limit)
    return {
        "ok": True,
        "matched": int(len(frame)),
        "latest_timestamp": _latest_timestamp(frame),
        "status_counts": counts(frame, "status_flag"),
        "summary": {
            "avg_ac_power": _avg(frame, "ac_power"),
            "avg_expected_ac_power": _avg(frame, "expected_ac_power"),
            "avg_performance_ratio": _avg(frame, "performance_ratio"),
            "avg_daily_yield": _avg(frame, "daily_yield"),
        },
        "recent_readings": records(frame, _FIELDS, limit=limited),
    }


def _latest_timestamp(frame: pd.DataFrame) -> str | None:
    if frame.empty or "timestamp" not in frame.columns:
        return None
    return frame.iloc[0]["timestamp"].isoformat()


def _avg(frame: pd.DataFrame, column: str) -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    value = frame[column].mean()
    if pd.isna(value):
        return None
    return float(value)


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="generation_readings",
            description=(
                "Summarize generation readings by plant or inverter. Returns aggregate metrics and "
                "a small recent-reading sample, never raw CSV text."
            ),
            parameters=PARAMETERS,
            handler=generation_summary,
        )
    )
