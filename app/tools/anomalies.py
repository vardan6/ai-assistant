"""Anomalies tool."""
from __future__ import annotations

from typing import Any

from .common import counts, filter_exact, filter_plant, records
from .registry import ToolContext, ToolRegistry, ToolSpec

_FIELDS = [
    "anomaly_id",
    "plant_id",
    "inverter_id",
    "asset_id",
    "asset_type",
    "anomaly_type",
    "severity",
    "cause",
    "detection_method",
    "power_loss_pct",
    "estimated_power_loss_kw",
    "detected_date",
    "status",
    "recommended_action",
    "resolved_date",
    "maintenance_ticket_id",
]

PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
        "inverter": {"type": "string", "description": "Filter by inverter_id."},
        "status": {
            "type": "string",
            "description": "Filter by anomaly status. Use 'unresolved' for unresolved/current anomalies; it includes open, monitoring, and scheduled_repair.",
        },
        "severity": {"type": "string", "description": "Filter by anomaly severity."},
        "anomaly_type": {"type": "string", "description": "Filter by anomaly type."},
        "cause": {"type": "string", "description": "Filter by anomaly cause."},
    },
    "additionalProperties": False,
}


def anomalies_lookup(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    anomaly_type: str | None = None,
    cause: str | None = None,
) -> dict[str, Any]:
    source = context.data.table("anomalies")
    frame = filter_plant(source, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = _filter_status(frame, status)
    frame = filter_exact(frame, "severity", severity)
    frame = filter_exact(frame, "anomaly_type", _normalize_anomaly_type(anomaly_type))
    frame = filter_exact(frame, "cause", cause)
    status_counts = counts(frame, "status")
    return {
        "ok": True,
        "total_anomalies": int(len(source)),
        "matched": int(len(frame)),
        "anomaly_ids": [int(value) for value in frame["anomaly_id"].tolist()] if "anomaly_id" in frame.columns else [],
        "status_counts": status_counts,
        "severity_counts": counts(frame, "severity"),
        "summary": {
            "matched": int(len(frame)),
            "status_counts": status_counts,
        },
        "anomalies": records(frame, _FIELDS),
    }


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="anomalies",
            description=(
                "Look up anomaly log entries by plant, inverter, status, severity, anomaly type, "
                "or cause. Returns concise structured anomaly records."
            ),
            parameters=PARAMETERS,
            handler=anomalies_lookup,
        )
    )


def _filter_status(frame, status: str | None):
    if not status:
        return frame
    value = status.strip().lower()
    if value in {"unresolved", "active"}:
        return frame[frame["status"].astype(str).str.lower() != "resolved"]
    return filter_exact(frame, "status", status)


def _normalize_anomaly_type(anomaly_type: str | None) -> str | None:
    if not anomaly_type:
        return anomaly_type
    value = anomaly_type.strip().lower()
    if "multi hotspot" in value:
        return "multi hotspot"
    if "hotspot" in value:
        return "hotspot"
    return anomaly_type
