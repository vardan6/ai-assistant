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
        "window": {
            "type": "string",
            "enum": ["today", "last_week", "this_month", "last_30_days", "all_time"],
            "description": "Dataset-anchored time window.",
        },
        "aggregate_by": {
            "type": "string",
            "enum": ["overall", "plant"],
            "description": "Return one overall summary or rank plant-level summaries.",
        },
        "limit": {"type": "integer", "description": "How many recent readings to include (1-20)."},
    },
    "additionalProperties": False,
}


def weather_summary(
    context: ToolContext,
    plant: str | None = None,
    window: str = "all_time",
    aggregate_by: str = "overall",
    limit: int | None = None,
) -> dict[str, Any]:
    frame = filter_plant(context.data.table("weather_readings"), context, plant)
    frame = _filter_window(frame, "timestamp", window, context)
    frame = frame.sort_values("timestamp", ascending=False)
    limited = clamp_limit(limit)
    group = str(aggregate_by or "overall").strip().lower()
    if group == "plant":
        results = (
            frame.groupby("plant_id", dropna=False)
            .agg(
                avg_ambient_temp=("ambient_temp", "mean"),
                avg_module_temp=("module_temp", "mean"),
                avg_irradiation=("irradiation", "mean"),
                avg_poa_irradiance=("poa_irradiance", "mean"),
                avg_wind_speed=("wind_speed", "mean"),
                avg_humidity=("humidity", "mean"),
                avg_cloud_cover_pct=("cloud_cover_pct", "mean"),
                total_rainfall_mm=("rainfall_mm", "sum"),
                reading_count=("reading_id", "count"),
            )
            .reset_index()
            .sort_values("avg_cloud_cover_pct", ascending=False)
            .head(limited)
        )
        return {
            "ok": True,
            "window": _normalize_window(window),
            "aggregate_by": "plant",
            "matched": int(len(frame)),
            "latest_timestamp": _latest_timestamp(frame),
            "results": [
                {
                    "plant_id": _id_string(row["plant_id"]),
                    "plant_name": _plant_name(context, row["plant_id"]),
                    "avg_ambient_temp": _clean_float(row["avg_ambient_temp"]),
                    "avg_module_temp": _clean_float(row["avg_module_temp"]),
                    "avg_irradiation": _clean_float(row["avg_irradiation"]),
                    "avg_poa_irradiance": _clean_float(row["avg_poa_irradiance"]),
                    "avg_wind_speed": _clean_float(row["avg_wind_speed"]),
                    "avg_humidity": _clean_float(row["avg_humidity"]),
                    "avg_cloud_cover_pct": _clean_float(row["avg_cloud_cover_pct"]),
                    "total_rainfall_mm": _clean_float(row["total_rainfall_mm"]),
                    "reading_count": int(row["reading_count"]),
                }
                for _, row in results.iterrows()
            ],
        }
    return {
        "ok": True,
        "window": _normalize_window(window),
        "aggregate_by": "overall",
        "matched": int(len(frame)),
        "latest_timestamp": _latest_timestamp(frame),
        "summary": {
            "avg_ambient_temp": _avg(frame, "ambient_temp"),
            "avg_module_temp": _avg(frame, "module_temp"),
            "avg_irradiation": _avg(frame, "irradiation"),
            "avg_poa_irradiance": _avg(frame, "poa_irradiance"),
            "avg_wind_speed": _avg(frame, "wind_speed"),
            "avg_humidity": _avg(frame, "humidity"),
            "avg_cloud_cover_pct": _avg(frame, "cloud_cover_pct"),
            "total_rainfall_mm": _sum(frame, "rainfall_mm"),
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


def _sum(frame: pd.DataFrame, column: str) -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    value = frame[column].sum()
    if pd.isna(value):
        return None
    return float(value)


def _filter_window(frame: pd.DataFrame, column: str, window: str | None, context: ToolContext) -> pd.DataFrame:
    if column not in frame.columns:
        return frame
    start, end = _window_bounds(context, window)
    if start is not None:
        frame = frame[frame[column] >= start]
    if end is not None:
        frame = frame[frame[column] <= end]
    return frame


def _window_bounds(context: ToolContext, window: str | None) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    anchor = pd.Timestamp(context.effective_now())
    mode = _normalize_window(window)
    if mode == "today":
        return anchor.normalize(), anchor
    if mode == "last_week":
        return (anchor - pd.Timedelta(days=6)).normalize(), anchor
    if mode == "this_month":
        return anchor.replace(day=1).normalize(), anchor
    if mode == "last_30_days":
        return (anchor - pd.Timedelta(days=29)).normalize(), anchor
    return None, None


def _normalize_window(window: str | None) -> str:
    value = str(window or "all_time").strip().lower()
    return value if value in {"today", "last_week", "this_month", "last_30_days", "all_time"} else "all_time"


def _plant_name(context: ToolContext, plant_id: str | int) -> str | None:
    plants = context.data.table("plants")
    matches = plants[plants["plant_id"].astype(str) == _id_string(plant_id)]
    if matches.empty:
        return None
    return str(matches.iloc[0]["name"])


def _id_string(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _clean_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="weather_readings",
            description=(
                "Summarize weather readings for a plant. Returns aggregate weather metrics and "
                "a small recent-reading sample. Supports dataset-anchored windows and plant ranking "
                "by average cloud cover."
            ),
            parameters=PARAMETERS,
            handler=weather_summary,
        )
    )
