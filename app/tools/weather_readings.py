"""Weather readings tool."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .common import clamp_limit, filter_plant, records
from .registry import ToolContext, ToolRegistry, ToolSpec

_FIELDS = [
    "reading_id",
    "timestamp",
    "plant_id",
    "ambient_temp",
    "module_temp",
    "irradiation",
    "poa_irradiance",
    "wind_speed",
    "humidity",
    "cloud_cover_pct",
    "rainfall_mm",
]

PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
        "limit": {"type": "integer", "description": "How many recent readings to include (1-20)."},
    },
    "additionalProperties": False,
}


def weather_summary(context: ToolContext, plant: str | None = None, limit: int | None = None) -> dict[str, Any]:
    frame = filter_plant(context.data.table("weather_readings"), context, plant)
    frame = frame.sort_values("timestamp", ascending=False)
    limited = clamp_limit(limit)
    return {
        "ok": True,
        "matched": int(len(frame)),
        "latest_timestamp": _latest_timestamp(frame),
        "summary": {
            "avg_ambient_temp": _avg(frame, "ambient_temp"),
            "avg_module_temp": _avg(frame, "module_temp"),
            "avg_irradiation": _avg(frame, "irradiation"),
            "avg_poa_irradiance": _avg(frame, "poa_irradiance"),
            "avg_wind_speed": _avg(frame, "wind_speed"),
            "avg_humidity": _avg(frame, "humidity"),
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
            name="weather_readings",
            description=(
                "Summarize weather readings for a plant. Returns aggregate weather metrics and "
                "a small recent-reading sample."
            ),
            parameters=PARAMETERS,
            handler=weather_summary,
        )
    )
