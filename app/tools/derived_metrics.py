"""Derived metric tools for Type B aggregation questions."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .common import clamp_limit, filter_exact, filter_plant
from .registry import ToolContext, ToolRegistry, ToolSpec

_WINDOWS = {"today", "last_week", "this_month", "last_30_days", "all_time"}
_AGGREGATE_BY = {"plant", "inverter"}
_MTTR_GROUPS = {"overall", "severity", "plant", "inverter"}


def daily_yield_metric(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    window: str = "last_week",
    aggregate_by: str = "plant",
    limit: int | None = None,
) -> dict[str, Any]:
    frame = context.data.table("generation_readings")
    frame = filter_plant(frame, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = _filter_window(frame, "timestamp", window, context)
    if frame.empty:
        return _empty_metric("daily_yield", window=window, aggregate_by=aggregate_by)

    frame = frame.assign(day=frame["timestamp"].dt.normalize())
    group = _normalize_group(aggregate_by, default="plant")
    limit = clamp_limit(limit, default=5, maximum=20)

    if group == "plant":
        per_day = (
            frame.groupby(["plant_id", "day", "inverter_id"], dropna=False)["daily_yield"]
            .max()
            .groupby(["plant_id", "day"], dropna=False)
            .sum()
            .reset_index(name="daily_yield_total")
        )
        results = (
            per_day.groupby("plant_id", dropna=False)["daily_yield_total"]
            .agg(avg_daily_yield="mean", days="count")
            .reset_index()
            .sort_values("avg_daily_yield", ascending=False)
            .head(limit)
        )
        return {
            "ok": True,
            "metric": "daily_yield",
            "window": _normalize_window(window),
            "aggregate_by": group,
            "matched_readings": int(len(frame)),
            "window_start": _iso(frame["timestamp"].min()),
            "window_end": _iso(frame["timestamp"].max()),
            "results": [
                {
                    "plant_id": _id_string(row["plant_id"]),
                    "plant_name": _plant_name(context, row["plant_id"]),
                    "avg_daily_yield": float(row["avg_daily_yield"]),
                    "days": int(row["days"]),
                }
                for _, row in results.iterrows()
            ],
        }

    per_day = (
        frame.groupby(["inverter_id", "day"], dropna=False)["daily_yield"]
        .max()
        .reset_index(name="daily_yield_total")
    )
    results = (
        per_day.groupby("inverter_id", dropna=False)["daily_yield_total"]
        .agg(avg_daily_yield="mean", days="count")
        .reset_index()
        .sort_values("avg_daily_yield", ascending=False)
        .head(limit)
    )
    inverter_meta = context.data.table("inverters")[["inverter_id", "plant_id"]].copy()
    merged = results.merge(inverter_meta, on="inverter_id", how="left")
    return {
        "ok": True,
        "metric": "daily_yield",
        "window": _normalize_window(window),
        "aggregate_by": group,
        "matched_readings": int(len(frame)),
        "window_start": _iso(frame["timestamp"].min()),
        "window_end": _iso(frame["timestamp"].max()),
        "results": [
            {
                "inverter_id": str(row["inverter_id"]),
                "plant_id": _id_string(row["plant_id"]),
                "avg_daily_yield": float(row["avg_daily_yield"]),
                "days": int(row["days"]),
            }
            for _, row in merged.iterrows()
        ],
    }


def performance_ratio_metric(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    window: str = "last_week",
    aggregate_by: str = "inverter",
    limit: int | None = None,
) -> dict[str, Any]:
    frame = context.data.table("generation_readings")
    frame = filter_plant(frame, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = _filter_window(frame, "timestamp", window, context)
    frame = frame[frame["performance_ratio"].notna()]
    if frame.empty:
        return _empty_metric("performance_ratio", window=window, aggregate_by=aggregate_by)

    group = _normalize_group(aggregate_by, default="inverter")
    limit = clamp_limit(limit, default=5, maximum=20)

    if group == "plant":
        results = (
            frame.groupby("plant_id", dropna=False)["performance_ratio"]
            .agg(avg_performance_ratio="mean", reading_count="count")
            .reset_index()
            .sort_values("avg_performance_ratio", ascending=False)
            .head(limit)
        )
        return {
            "ok": True,
            "metric": "performance_ratio",
            "window": _normalize_window(window),
            "aggregate_by": group,
            "matched_readings": int(len(frame)),
            "window_start": _iso(frame["timestamp"].min()),
            "window_end": _iso(frame["timestamp"].max()),
            "results": [
                {
                    "plant_id": _id_string(row["plant_id"]),
                    "plant_name": _plant_name(context, row["plant_id"]),
                    "avg_performance_ratio": float(row["avg_performance_ratio"]),
                    "reading_count": int(row["reading_count"]),
                }
                for _, row in results.iterrows()
            ],
        }

    results = (
        frame.groupby("inverter_id", dropna=False)["performance_ratio"]
        .agg(avg_performance_ratio="mean", reading_count="count")
        .reset_index()
        .sort_values("avg_performance_ratio", ascending=False)
        .head(limit)
    )
    inverter_meta = context.data.table("inverters")[["inverter_id", "plant_id"]].copy()
    merged = results.merge(inverter_meta, on="inverter_id", how="left")
    return {
        "ok": True,
        "metric": "performance_ratio",
        "window": _normalize_window(window),
        "aggregate_by": group,
        "matched_readings": int(len(frame)),
        "window_start": _iso(frame["timestamp"].min()),
        "window_end": _iso(frame["timestamp"].max()),
        "results": [
            {
                "inverter_id": str(row["inverter_id"]),
                "plant_id": _id_string(row["plant_id"]),
                "avg_performance_ratio": float(row["avg_performance_ratio"]),
                "reading_count": int(row["reading_count"]),
            }
            for _, row in merged.iterrows()
        ],
    }


def mttr_metric(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    window: str = "all_time",
    aggregate_by: str = "overall",
    limit: int | None = None,
) -> dict[str, Any]:
    frame = context.data.table("alerts")
    frame = filter_plant(frame, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = filter_exact(frame, "severity", severity)
    frame = filter_exact(frame, "type", alert_type)
    frame = frame[frame["resolved_at"].notna() & frame["created_at"].notna()].copy()
    frame = _filter_window(frame, "resolved_at", window, context)
    if frame.empty:
        return _empty_metric("mttr", window=window, aggregate_by=aggregate_by)

    frame["mttr_hours"] = (frame["resolved_at"] - frame["created_at"]).dt.total_seconds() / 3600.0
    group = _normalize_mttr_group(aggregate_by)
    limit = clamp_limit(limit, default=5, maximum=20)

    if group == "overall":
        return {
            "ok": True,
            "metric": "mttr",
            "unit": "hours",
            "window": _normalize_window(window),
            "aggregate_by": group,
            "matched_alerts": int(len(frame)),
            "window_start": _iso(frame["resolved_at"].min()),
            "window_end": _iso(frame["resolved_at"].max()),
            "results": [{
                "mean_time_to_resolve_hours": float(frame["mttr_hours"].mean()),
                "resolved_alerts": int(len(frame)),
            }],
        }

    group_column = "type"
    label_key = "label"
    if group == "severity":
        group_column = "severity"
        label_key = "severity"
    elif group == "plant":
        group_column = "plant_id"
        label_key = "plant_id"
    elif group == "inverter":
        group_column = "inverter_id"
        label_key = "inverter_id"

    results = (
        frame.groupby(group_column, dropna=False)["mttr_hours"]
        .agg(mean_time_to_resolve_hours="mean", resolved_alerts="count")
        .reset_index()
        .sort_values("mean_time_to_resolve_hours", ascending=True)
        .head(limit)
    )
    payload: list[dict[str, Any]] = []
    for _, row in results.iterrows():
        item = {
            label_key: _id_string(row[group_column]),
            "mean_time_to_resolve_hours": float(row["mean_time_to_resolve_hours"]),
            "resolved_alerts": int(row["resolved_alerts"]),
        }
        if group == "plant" and item["plant_id"] is not None:
            item["plant_name"] = _plant_name(context, item["plant_id"])
        payload.append(item)
    return {
        "ok": True,
        "metric": "mttr",
        "unit": "hours",
        "window": _normalize_window(window),
        "aggregate_by": group,
        "matched_alerts": int(len(frame)),
        "window_start": _iso(frame["resolved_at"].min()),
        "window_end": _iso(frame["resolved_at"].max()),
        "results": payload,
    }


def total_yield_metric(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    window: str = "this_month",
    aggregate_by: str = "plant",
    limit: int | None = None,
) -> dict[str, Any]:
    frame = context.data.table("generation_readings")
    frame = filter_plant(frame, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = _filter_window(frame, "timestamp", window, context)
    if frame.empty:
        return _empty_metric("total_yield", window=window, aggregate_by=aggregate_by)

    group = _normalize_group(aggregate_by, default="plant")
    limit = clamp_limit(limit, default=5, maximum=20)
    per_inverter = (
        frame.sort_values("timestamp")
        .groupby(["plant_id", "inverter_id"], dropna=False)["total_yield"]
        .agg(first="first", last="last", reading_count="count")
        .reset_index()
    )
    per_inverter["total_yield"] = per_inverter["last"] - per_inverter["first"]
    if group == "plant":
        results = (
            per_inverter.groupby("plant_id", dropna=False)
            .agg(total_yield=("total_yield", "sum"), reading_count=("reading_count", "sum"))
            .reset_index()
        )
    else:
        results = per_inverter[["plant_id", "inverter_id", "total_yield", "reading_count"]]
    results = results.sort_values("total_yield", ascending=False).head(limit)
    payload: list[dict[str, Any]] = []
    for _, row in results.iterrows():
        item = {
            "plant_id": _id_string(row["plant_id"]),
            "plant_name": _plant_name(context, row["plant_id"]),
            "total_yield": float(row["total_yield"]),
            "reading_count": int(row["reading_count"]),
        }
        if group == "inverter":
            item["inverter_id"] = str(row["inverter_id"])
        payload.append(item)
    return {
        "ok": True,
        "metric": "total_yield",
        "window": _normalize_window(window),
        "aggregate_by": group,
        "matched_readings": int(len(frame)),
        "window_start": _iso(frame["timestamp"].min()),
        "window_end": _iso(frame["timestamp"].max()),
        "results": payload,
    }


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="daily_yield",
            description=(
                "Compute average daily yield from generation readings. Uses per-inverter daily maxima, "
                "then aggregates by plant or inverter over a dataset-anchored time window."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
                    "inverter": {"type": "string", "description": "Filter by inverter_id."},
                    "window": {"type": "string", "enum": sorted(_WINDOWS), "description": "Dataset-anchored time window. If the user asks for yield without an explicit window, use last_week."},
                    "aggregate_by": {"type": "string", "enum": sorted(_AGGREGATE_BY), "description": "Return plant- or inverter-level aggregates."},
                    "limit": {"type": "integer", "description": "Maximum number of ranked results to return (1-20)."},
                },
                "additionalProperties": False,
            },
            handler=daily_yield_metric,
        )
    )
    registry.register(
        ToolSpec(
            name="performance_ratio",
            description=(
                "Rank average performance ratio over a dataset-anchored time window by plant or inverter."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
                    "inverter": {"type": "string", "description": "Filter by inverter_id."},
                    "window": {"type": "string", "enum": sorted(_WINDOWS), "description": "Dataset-anchored time window."},
                    "aggregate_by": {"type": "string", "enum": sorted(_AGGREGATE_BY), "description": "Return plant- or inverter-level aggregates."},
                    "limit": {"type": "integer", "description": "Maximum number of ranked results to return (1-20)."},
                },
                "additionalProperties": False,
            },
            handler=performance_ratio_metric,
        )
    )
    registry.register(
        ToolSpec(
            name="mttr",
            description=(
                "Compute mean time to resolve operational alerts from created_at to resolved_at, optionally "
                "filtered by severity, plant, inverter, or alert type."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
                    "inverter": {"type": "string", "description": "Filter by inverter_id."},
                    "severity": {"type": "string", "description": "Filter by alert severity."},
                    "alert_type": {"type": "string", "description": "Filter by alert type."},
                    "window": {"type": "string", "enum": sorted(_WINDOWS), "description": "Dataset-anchored time window based on resolved_at."},
                    "aggregate_by": {"type": "string", "enum": sorted(_MTTR_GROUPS), "description": "How to group the MTTR result."},
                    "limit": {"type": "integer", "description": "Maximum number of grouped results to return (1-20)."},
                },
                "additionalProperties": False,
            },
            handler=mttr_metric,
        )
    )
    registry.register(
        ToolSpec(
            name="total_yield",
            description=(
                "Compute generated energy from cumulative total_yield readings as last minus first "
                "over a dataset-anchored window, grouped by plant or inverter. Use for total energy generated."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
                    "inverter": {"type": "string", "description": "Filter by inverter_id."},
                    "window": {"type": "string", "enum": sorted(_WINDOWS), "description": "Dataset-anchored time window."},
                    "aggregate_by": {"type": "string", "enum": sorted(_AGGREGATE_BY), "description": "Return plant- or inverter-level aggregates."},
                    "limit": {"type": "integer", "description": "Maximum number of ranked results to return (1-20)."},
                },
                "additionalProperties": False,
            },
            handler=total_yield_metric,
        )
    )


def _empty_metric(metric: str, *, window: str, aggregate_by: str) -> dict[str, Any]:
    return {
        "ok": True,
        "metric": metric,
        "window": _normalize_window(window),
        "aggregate_by": aggregate_by,
        "results": [],
    }


def _normalize_window(window: str | None) -> str:
    value = str(window or "all_time").strip().lower()
    return value if value in _WINDOWS else "all_time"


def _normalize_group(aggregate_by: str | None, *, default: str) -> str:
    value = str(aggregate_by or default).strip().lower()
    return value if value in _AGGREGATE_BY else default


def _normalize_mttr_group(aggregate_by: str | None) -> str:
    value = str(aggregate_by or "overall").strip().lower()
    return value if value in _MTTR_GROUPS else "overall"


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


def _plant_name(context: ToolContext, plant_id: str | int) -> str | None:
    plants = context.data.table("plants")
    matches = plants[plants["plant_id"].astype(str) == _id_string(plant_id)]
    if matches.empty:
        return None
    return str(matches.iloc[0]["name"])


def _iso(value: pd.Timestamp | Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _id_string(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
