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
    frame = filter_plant(source, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = filter_exact(frame, "status", status)
    frame = filter_exact(frame, "severity", severity)
    frame = filter_exact(frame, "type", type)
    return {
        "ok": True,
        "total_alerts": int(len(source)),
        "matched": int(len(frame)),
        "alert_ids": [int(value) for value in frame["alert_id"].tolist()] if "alert_id" in frame.columns else [],
        "status_counts": counts(frame, "status"),
        "severity_counts": counts(frame, "severity"),
        "alerts": records(frame, _FIELDS),
    }


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="alerts",
            description=(
                "Look up operational alerts by plant, inverter, severity, status, or alert type. "
                "Returns structured alert records and summary counts."
            ),
            parameters=PARAMETERS,
            handler=alerts_lookup,
        )
    )
