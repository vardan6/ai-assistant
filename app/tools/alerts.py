"""Alerts tool."""
from __future__ import annotations

from typing import Any

from .common import counts, filter_exact, filter_plant, records
from .registry import ToolContext, ToolRegistry, ToolSpec

_FIELDS = [
    "alert_id",
    "plant_id",
    "inverter_id",
    "alert_code",
    "severity",
    "type",
    "status",
    "priority",
    "created_at",
    "acknowledged_at",
    "resolved_at",
    "downtime_minutes",
    "assigned_to",
]

PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
        "inverter": {"type": "string", "description": "Filter by inverter_id."},
        "status": {"type": "string", "description": "Filter by alert status."},
        "severity": {"type": "string", "description": "Filter by alert severity."},
        "type": {"type": "string", "description": "Filter by alert type."},
    },
    "additionalProperties": False,
}


def alerts_lookup(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    type: str | None = None,
) -> dict[str, Any]:
    source = context.data.table("alerts")
    filters_applied = any(value is not None for value in (plant, inverter, status, severity, type))
    frame = filter_plant(source, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = filter_exact(frame, "status", status)
    frame = filter_exact(frame, "severity", severity)
    frame = filter_exact(frame, "type", type)
    downtime_series = frame["downtime_minutes"].dropna() if "downtime_minutes" in frame.columns else None
    matched_inverter_ids = (
        [str(v) for v in frame["inverter_id"].dropna().tolist()]
        if "inverter_id" in frame.columns
        else []
    )
    payload = {
        "ok": True,
        "matched": int(len(frame)),
        "alert_ids": [int(value) for value in frame["alert_id"].tolist()] if "alert_id" in frame.columns else [],
        "matched_inverter_ids": matched_inverter_ids,
        "total_downtime_minutes": float(downtime_series.sum()) if downtime_series is not None else 0.0,
        "downtime_record_count": int(len(downtime_series)) if downtime_series is not None else 0,
        "status_counts": counts(frame, "status"),
        "severity_counts": counts(frame, "severity"),
        "alerts": records(frame, _FIELDS),
    }
    total_key = "total_alerts_all_plants" if filters_applied else "total_alerts"
    payload[total_key] = int(len(source))
    return payload


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="alerts",
            description=(
                "Look up operational alerts by plant, inverter, severity, status, or alert type. "
                "Returns structured alert records, summary counts, and total_downtime_minutes. "
                "Use this tool for total downtime questions; MTTR is a separate mean-resolution metric."
            ),
            parameters=PARAMETERS,
            handler=alerts_lookup,
        )
    )
