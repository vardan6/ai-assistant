"""Inverters tool."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .common import counts, filter_exact, filter_plant, records
from .registry import ToolContext, ToolRegistry, ToolSpec

_FIELDS = [
    "inverter_id",
    "plant_id",
    "manufacturer",
    "model",
    "rated_kw",
    "string_count",
    "firmware_version",
    "status",
    "last_maintenance_date",
    "last_seen",
    "generation_last_timestamp",
    "is_silent_by_generation",
]

PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
        "inverter": {"type": "string", "description": "Filter by inverter_id."},
        "status": {"type": "string", "description": "Filter by inverter status (online, fault, offline)."},
    },
    "additionalProperties": False,
}


def inverter_status(context: ToolContext, plant: str | None = None, inverter: str | None = None, status: str | None = None) -> dict[str, Any]:
    source = context.data.table("inverters")
    frame = filter_plant(source, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = _annotate_generation_recency(frame, context)
    frame = filter_exact(frame, "status", status)
    silent = frame[frame["is_silent_by_generation"]]
    anchor = context.effective_now()
    return {
        "ok": True,
        "total_inverters": int(len(source)),
        "matched": int(len(frame)),
        "status_counts": counts(frame, "status"),
        "silent_anchor": anchor.isoformat(),
        "silent_threshold_rule": "generation_last_timestamp < effective_now",
        "silent_count": int(len(silent)),
        "silent_inverter_ids": silent["inverter_id"].astype(str).tolist(),
        "inverters": records(frame, _FIELDS),
    }


def _annotate_generation_recency(frame: pd.DataFrame, context: ToolContext) -> pd.DataFrame:
    if frame.empty:
        annotated = frame.copy()
        annotated["generation_last_timestamp"] = pd.Series(dtype="datetime64[ns]")
        annotated["is_silent_by_generation"] = pd.Series(dtype="bool")
        return annotated

    generation = context.data.table("generation_readings")
    latest = (
        generation.groupby("inverter_id", as_index=False)["timestamp"]
        .max()
        .rename(columns={"timestamp": "generation_last_timestamp"})
    )
    annotated = frame.merge(latest, on="inverter_id", how="left")
    anchor = pd.Timestamp(context.effective_now())
    annotated["is_silent_by_generation"] = (
        annotated["generation_last_timestamp"].isna()
        | (annotated["generation_last_timestamp"] < anchor)
    )
    return annotated


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="inverters",
            description=(
                "Look up inverters and their operating status. Use for faulted/offline/online "
                "inverter questions or to resolve inverter ids within a plant."
            ),
            parameters=PARAMETERS,
            handler=inverter_status,
        )
    )
