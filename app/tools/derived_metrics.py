"""Derived metric tools for Type B aggregation questions."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .common import clamp_limit, filter_exact, filter_plant
from .registry import ToolContext, ToolRegistry, ToolSpec

_WINDOWS = {"today", "last_week", "this_month", "last_30_days", "all_time"}
_AGGREGATE_BY = {"plant", "inverter"}
_AC_POWER_GROUPS = {"overall", "plant", "inverter"}
_AC_POWER_REDUCERS = {"mean", "max"}
_MTTR_GROUPS = {"overall", "severity", "plant", "inverter"}
_MAINTENANCE_GROUPS = {"overall", "status", "priority", "type", "plant", "inverter"}
_COMPLETED_MAINTENANCE_STATUSES = {"done", "completed"}
_DC_VOLTAGE_FILTERS = {"zero", "nonzero"}


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
    sort_order: str = "desc",
    dc_voltage: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    frame = context.data.table("generation_readings")
    frame = filter_plant(frame, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = _filter_window(frame, "timestamp", window, context)
    dc_voltage_filter = _normalize_dc_voltage_filter(dc_voltage)
    if dc_voltage_filter == "zero":
        frame = frame[frame["dc_voltage"].fillna(0) == 0]
    elif dc_voltage_filter == "nonzero":
        frame = frame[frame["dc_voltage"].fillna(0) != 0]
    if frame.empty:
        return _empty_metric("performance_ratio", window=window, aggregate_by=aggregate_by)
    frame = frame[frame["performance_ratio"].notna()]
    if frame.empty:
        return {
            **_empty_metric("performance_ratio", window=window, aggregate_by=aggregate_by),
            "matched_readings": 0,
            "verdict": "undefined",
            "reason": "No non-null performance_ratio readings exist in the selected window.",
        }

    group = _normalize_group(aggregate_by, default="inverter")
    ascending = str(sort_order or "desc").strip().lower() == "asc"
    limit = clamp_limit(limit, default=5, maximum=20)

    if group == "plant":
        results = (
            frame.groupby("plant_id", dropna=False)["performance_ratio"]
            .agg(avg_performance_ratio="mean", reading_count="count")
            .reset_index()
            .sort_values("avg_performance_ratio", ascending=ascending)
            .head(limit)
        )
        return {
            "ok": True,
            "metric": "performance_ratio",
            "window": _normalize_window(window),
            "aggregate_by": group,
            "sort_order": "asc" if ascending else "desc",
            "dc_voltage": dc_voltage_filter or "any",
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
        .sort_values("avg_performance_ratio", ascending=ascending)
        .head(limit)
    )
    inverter_meta = context.data.table("inverters")[["inverter_id", "plant_id"]].copy()
    merged = results.merge(inverter_meta, on="inverter_id", how="left")
    return {
        "ok": True,
        "metric": "performance_ratio",
        "window": _normalize_window(window),
        "aggregate_by": group,
        "sort_order": "asc" if ascending else "desc",
        "dc_voltage": dc_voltage_filter or "any",
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
    status: str | None = None,
    alert_type: str | None = None,
    window: str = "all_time",
    aggregate_by: str = "overall",
    limit: int | None = None,
) -> dict[str, Any]:
    frame = context.data.table("alerts")
    status, severity = _coerce_alert_status_filter(status=status, severity=severity)
    frame = filter_plant(frame, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = filter_exact(frame, "status", status)
    frame = filter_exact(frame, "severity", severity)
    frame = filter_exact(frame, "type", alert_type)
    frame = frame[frame["resolved_at"].notna() & frame["created_at"].notna()].copy()
    frame = _filter_window(frame, "resolved_at", window, context)
    if frame.empty:
        extra: dict[str, Any] = {"matched_alerts": 0}
        if status and status.strip().lower() != "resolved":
            extra.update(
                {
                    "verdict": "no_inputs",
                    "reason": "MTTR requires resolved_at; open or unresolved alerts have no resolved_at timestamp.",
                    "status": status.strip().lower(),
                }
            )
        return _empty_metric("mttr", window=window, aggregate_by=aggregate_by, **extra)

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


def maintenance_cost_metric(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    maintenance_type: str | None = None,
    window: str = "all_time",
    aggregate_by: str = "overall",
    limit: int | None = None,
) -> dict[str, Any]:
    return _maintenance_metric(
        context,
        metric="maintenance_cost",
        plant=plant,
        inverter=inverter,
        status=status,
        priority=priority,
        maintenance_type=maintenance_type,
        window=window,
        aggregate_by=aggregate_by,
        limit=limit,
    )


def maintenance_duration_metric(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    maintenance_type: str | None = None,
    window: str = "all_time",
    aggregate_by: str = "overall",
    limit: int | None = None,
) -> dict[str, Any]:
    return _maintenance_metric(
        context,
        metric="maintenance_duration",
        plant=plant,
        inverter=inverter,
        status=status,
        priority=priority,
        maintenance_type=maintenance_type,
        window=window,
        aggregate_by=aggregate_by,
        limit=limit,
    )


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


def ac_power_metric(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    window: str = "last_week",
    aggregate_by: str = "overall",
    reducer: str = "mean",
    limit: int | None = None,
) -> dict[str, Any]:
    frame = context.data.table("generation_readings")
    frame = filter_plant(frame, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = _filter_window(frame, "timestamp", window, context)
    frame = frame[frame["ac_power"].notna()].copy()

    group = _normalize_ac_power_group(aggregate_by)
    reducer = _normalize_ac_power_reducer(reducer)
    if frame.empty:
        return _empty_metric(
            "ac_power",
            window=window,
            aggregate_by=group,
            reducer=reducer,
            unit="kW",
        )

    base = {
        "ok": True,
        "metric": "ac_power",
        "unit": "kW",
        "window": _normalize_window(window),
        "aggregate_by": group,
        "reducer": reducer,
        "matched_readings": int(len(frame)),
        "window_start": _iso(frame["timestamp"].min()),
        "window_end": _iso(frame["timestamp"].max()),
    }
    limit = clamp_limit(limit, default=5, maximum=20)

    if group == "overall":
        if reducer == "mean":
            return {
                **base,
                "results": [
                    {
                        "mean_ac_power_kw": float(frame["ac_power"].mean()),
                        "reading_count": int(len(frame)),
                    }
                ],
            }
        peak_row = frame.loc[frame["ac_power"].idxmax()]
        return {
            **base,
            "results": [_ac_power_peak_item(context, peak_row, reading_count=int(len(frame)))],
        }

    if reducer == "mean":
        if group == "plant":
            results = (
                frame.groupby("plant_id", dropna=False)["ac_power"]
                .agg(mean_ac_power_kw="mean", reading_count="count")
                .reset_index()
                .sort_values("mean_ac_power_kw", ascending=False)
                .head(limit)
            )
            return {
                **base,
                "results": [
                    {
                        "plant_id": _id_string(row["plant_id"]),
                        "plant_name": _plant_name(context, row["plant_id"]),
                        "mean_ac_power_kw": float(row["mean_ac_power_kw"]),
                        "reading_count": int(row["reading_count"]),
                    }
                    for _, row in results.iterrows()
                ],
            }

        results = (
            frame.groupby("inverter_id", dropna=False)["ac_power"]
            .agg(mean_ac_power_kw="mean", reading_count="count")
            .reset_index()
            .sort_values("mean_ac_power_kw", ascending=False)
            .head(limit)
        )
        inverter_meta = context.data.table("inverters")[["inverter_id", "plant_id"]].copy()
        merged = results.merge(inverter_meta, on="inverter_id", how="left")
        return {
            **base,
            "results": [
                {
                    "inverter_id": str(row["inverter_id"]),
                    "plant_id": _id_string(row["plant_id"]),
                    "mean_ac_power_kw": float(row["mean_ac_power_kw"]),
                    "reading_count": int(row["reading_count"]),
                }
                for _, row in merged.iterrows()
            ],
        }

    if group == "plant":
        counts = (
            frame.groupby("plant_id", dropna=False)
            .size()
            .reset_index(name="reading_count")
        )
        peaks = frame.loc[frame.groupby("plant_id", dropna=False)["ac_power"].idxmax()].copy()
        ranked = (
            peaks.merge(counts, on="plant_id", how="left")
            .sort_values("ac_power", ascending=False)
            .head(limit)
        )
        return {
            **base,
            "results": [
                {
                    "plant_id": _id_string(row["plant_id"]),
                    "plant_name": _plant_name(context, row["plant_id"]),
                    "inverter_id": str(row["inverter_id"]),
                    **_ac_power_peak_fields(row),
                    "reading_count": int(row["reading_count"]),
                }
                for _, row in ranked.iterrows()
            ],
        }

    counts = frame.groupby("inverter_id", dropna=False).size().reset_index(name="reading_count")
    peaks = frame.loc[frame.groupby("inverter_id", dropna=False)["ac_power"].idxmax()].copy()
    ranked = (
        peaks.merge(counts, on="inverter_id", how="left")
        .sort_values("ac_power", ascending=False)
        .head(limit)
    )
    return {
        **base,
        "results": [
            {
                "inverter_id": str(row["inverter_id"]),
                "plant_id": _id_string(row["plant_id"]),
                **_ac_power_peak_fields(row),
                "reading_count": int(row["reading_count"]),
            }
            for _, row in ranked.iterrows()
        ],
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
                "Rank average performance ratio over a dataset-anchored time window by plant or inverter. "
                "Use sort_order='asc' to find the worst performer; sort_order='desc' (default) for the best. "
                "Use dc_voltage='zero' for night/zero-DC questions; performance_ratio is undefined there."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
                    "inverter": {"type": "string", "description": "Filter by inverter_id."},
                    "window": {"type": "string", "enum": sorted(_WINDOWS), "description": "Dataset-anchored time window."},
                    "aggregate_by": {"type": "string", "enum": sorted(_AGGREGATE_BY), "description": "Return plant- or inverter-level aggregates."},
                    "sort_order": {"type": "string", "enum": ["asc", "desc"], "description": "Sort order: 'desc' (default) returns highest PR first (best), 'asc' returns lowest PR first (worst)."},
                    "dc_voltage": {"type": "string", "enum": sorted(_DC_VOLTAGE_FILTERS), "description": "Optional DC-voltage filter. Use 'zero' for night/no-generation readings; use 'nonzero' for daylight/generating readings."},
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
                "filtered by severity, plant, inverter, status, or alert type. Do not use for total downtime; "
                "use the alerts tool's total_downtime_minutes for downtime_minutes sums."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
                    "inverter": {"type": "string", "description": "Filter by inverter_id."},
                    "severity": {"type": "string", "description": "Filter by alert severity."},
                    "status": {"type": "string", "description": "Filter by alert status. For status='open', MTTR has no inputs because open alerts have no resolved_at timestamp."},
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
            name="maintenance_cost",
            description=(
                "Compute maintenance spend from maintenance tickets, optionally filtered by plant, inverter, "
                "status, priority, or work type."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
                    "inverter": {"type": "string", "description": "Filter by inverter_id."},
                    "status": {"type": "string", "description": "Filter by maintenance status."},
                    "priority": {"type": "string", "description": "Filter by maintenance priority."},
                    "maintenance_type": {"type": "string", "description": "Filter by maintenance work type."},
                    "window": {"type": "string", "enum": sorted(_WINDOWS), "description": "Dataset-anchored time window based on completed, started, or scheduled date."},
                    "aggregate_by": {"type": "string", "enum": sorted(_MAINTENANCE_GROUPS), "description": "How to group the maintenance aggregate."},
                    "limit": {"type": "integer", "description": "Maximum number of grouped results to return (1-20)."},
                },
                "additionalProperties": False,
            },
            handler=maintenance_cost_metric,
        )
    )
    registry.register(
        ToolSpec(
            name="maintenance_duration",
            description=(
                "Compute mean maintenance duration from maintenance tickets, optionally filtered by plant, inverter, "
                "status, priority, or work type."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
                    "inverter": {"type": "string", "description": "Filter by inverter_id."},
                    "status": {"type": "string", "description": "Filter by maintenance status."},
                    "priority": {"type": "string", "description": "Filter by maintenance priority."},
                    "maintenance_type": {"type": "string", "description": "Filter by maintenance work type."},
                    "window": {"type": "string", "enum": sorted(_WINDOWS), "description": "Dataset-anchored time window based on completed, started, or scheduled date."},
                    "aggregate_by": {"type": "string", "enum": sorted(_MAINTENANCE_GROUPS), "description": "How to group the maintenance aggregate."},
                    "limit": {"type": "integer", "description": "Maximum number of grouped results to return (1-20)."},
                },
                "additionalProperties": False,
            },
            handler=maintenance_duration_metric,
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
    registry.register(
        ToolSpec(
            name="ac_power",
            description=(
                "Compute AC output power over a dataset-anchored window. Supports mean and max reducers "
                "across overall, plant, or inverter aggregates."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
                    "inverter": {"type": "string", "description": "Filter by inverter_id."},
                    "window": {"type": "string", "enum": sorted(_WINDOWS), "description": "Dataset-anchored time window."},
                    "aggregate_by": {"type": "string", "enum": sorted(_AC_POWER_GROUPS), "description": "Return one overall result or grouped plant/inverter aggregates."},
                    "reducer": {"type": "string", "enum": sorted(_AC_POWER_REDUCERS), "description": "Aggregation reducer: mean for average AC power, max for peak AC power."},
                    "limit": {"type": "integer", "description": "Maximum number of ranked results to return (1-20)."},
                },
                "additionalProperties": False,
            },
            handler=ac_power_metric,
        )
    )


def _empty_metric(metric: str, *, window: str, aggregate_by: str, **extra: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "metric": metric,
        "window": _normalize_window(window),
        "aggregate_by": aggregate_by,
        **extra,
        "results": [],
    }


def _normalize_window(window: str | None) -> str:
    value = str(window or "all_time").strip().lower()
    return value if value in _WINDOWS else "all_time"


def _normalize_group(aggregate_by: str | None, *, default: str) -> str:
    value = str(aggregate_by or default).strip().lower()
    return value if value in _AGGREGATE_BY else default


def _normalize_dc_voltage_filter(value: str | None) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in _DC_VOLTAGE_FILTERS else ""


def _normalize_ac_power_group(aggregate_by: str | None) -> str:
    value = str(aggregate_by or "overall").strip().lower()
    return value if value in _AC_POWER_GROUPS else "overall"


def _normalize_ac_power_reducer(reducer: str | None) -> str:
    value = str(reducer or "mean").strip().lower()
    return value if value in _AC_POWER_REDUCERS else "mean"


def _normalize_mttr_group(aggregate_by: str | None) -> str:
    value = str(aggregate_by or "overall").strip().lower()
    return value if value in _MTTR_GROUPS else "overall"


def _coerce_alert_status_filter(*, status: str | None, severity: str | None) -> tuple[str | None, str | None]:
    if status:
        return status, severity
    candidate = str(severity or "").strip().lower()
    if candidate in {"open", "resolved", "acknowledged"}:
        return candidate, None
    return status, severity


def _normalize_maintenance_group(aggregate_by: str | None) -> str:
    value = str(aggregate_by or "overall").strip().lower()
    return value if value in _MAINTENANCE_GROUPS else "overall"


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


def _ac_power_peak_item(context: ToolContext, row: pd.Series, *, reading_count: int) -> dict[str, Any]:
    return {
        "plant_id": _id_string(row["plant_id"]),
        "plant_name": _plant_name(context, row["plant_id"]),
        "inverter_id": str(row["inverter_id"]),
        **_ac_power_peak_fields(row),
        "reading_count": reading_count,
    }


def _ac_power_peak_fields(row: pd.Series) -> dict[str, Any]:
    ac_power_kw = float(row["ac_power"])
    return {
        "ac_power_kw": ac_power_kw,
        "max_ac_power_kw": ac_power_kw,
        "timestamp": _iso(row["timestamp"]),
    }


def _maintenance_metric(
    context: ToolContext,
    *,
    metric: str,
    plant: str | None,
    inverter: str | None,
    status: str | None,
    priority: str | None,
    maintenance_type: str | None,
    window: str,
    aggregate_by: str,
    limit: int | None,
) -> dict[str, Any]:
    frame = context.data.table("maintenance").copy()
    frame = filter_plant(frame, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = filter_exact(frame, "status", status)
    frame = filter_exact(frame, "priority", priority)
    frame = filter_exact(frame, "type", maintenance_type)
    frame = _prepare_maintenance_window(frame)
    frame = _filter_window(frame, "_window_date", window, context)
    if frame.empty:
        return _empty_metric(metric, window=window, aggregate_by=aggregate_by)

    group = _normalize_maintenance_group(aggregate_by)
    limit = clamp_limit(limit, default=5, maximum=20)
    completed_mask = frame["status"].astype(str).str.lower().isin(_COMPLETED_MAINTENANCE_STATUSES)
    base = {
        "ok": True,
        "metric": metric,
        "window": _normalize_window(window),
        "aggregate_by": group,
        "matched_tickets": int(len(frame)),
        "window_start": _iso(frame["_window_date"].min()),
        "window_end": _iso(frame["_window_date"].max()),
    }

    if group == "overall":
        return {
            **base,
            "results": [_maintenance_result_item(metric, frame, completed_mask=completed_mask)],
        }

    group_column = _maintenance_group_column(group)
    grouped = []
    for raw_value, subset in frame.groupby(group_column, dropna=False):
        subset_completed = subset["status"].astype(str).str.lower().isin(_COMPLETED_MAINTENANCE_STATUSES)
        item = {
            _maintenance_label_key(group): _id_string(raw_value),
            **_maintenance_result_item(metric, subset, completed_mask=subset_completed),
            "matched_tickets": int(len(subset)),
        }
        if group == "plant" and item["plant_id"] is not None:
            item["plant_name"] = _plant_name(context, item["plant_id"])
        grouped.append(item)

    grouped.sort(key=lambda item: _maintenance_sort_key(metric, item), reverse=True)
    return {
        **base,
        "results": grouped[:limit],
    }


def _prepare_maintenance_window(frame: pd.DataFrame) -> pd.DataFrame:
    frame["_window_date"] = frame["completed_date"]
    frame["_window_date"] = frame["_window_date"].fillna(frame["started_date"])
    frame["_window_date"] = frame["_window_date"].fillna(frame["scheduled_date"])
    return frame


def _maintenance_group_column(group: str) -> str:
    if group == "plant":
        return "plant_id"
    if group == "inverter":
        return "inverter_id"
    return group


def _maintenance_label_key(group: str) -> str:
    if group == "plant":
        return "plant_id"
    if group == "inverter":
        return "inverter_id"
    return group


def _maintenance_result_item(metric: str, frame: pd.DataFrame, *, completed_mask: pd.Series) -> dict[str, Any]:
    if metric == "maintenance_cost":
        return {
            "total_cost_usd": float(frame["cost_usd"].fillna(0).sum()),
            "completed_tickets": int(completed_mask.sum()),
        }
    duration = frame["duration_hours"].dropna()
    return {
        "mean_duration_hours": float(duration.mean()) if not duration.empty else None,
        "completed_tickets": int(completed_mask.sum()),
    }


def _maintenance_sort_key(metric: str, item: dict[str, Any]) -> float:
    if metric == "maintenance_cost":
        return float(item["total_cost_usd"])
    value = item["mean_duration_hours"]
    return float(value) if value is not None else float("-inf")
