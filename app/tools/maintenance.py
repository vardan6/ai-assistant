"""Maintenance tool."""
from __future__ import annotations

from typing import Any

from .common import counts, filter_exact, filter_plant, records
from .registry import ToolContext, ToolRegistry, ToolSpec

_FIELDS = [
    "ticket_id",
    "plant_id",
    "inverter_id",
    "type",
    "priority",
    "status",
    "scheduled_date",
    "started_date",
    "completed_date",
    "duration_hours",
    "cost_usd",
    "technician",
    "vendor",
]

PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "plant": {"type": "string", "description": "Filter by plant_id or plant name."},
        "inverter": {"type": "string", "description": "Filter by inverter_id."},
        "status": {"type": "string", "description": "Filter by maintenance status."},
        "priority": {"type": "string", "description": "Filter by maintenance priority."},
        "type": {"type": "string", "description": "Filter by maintenance type."},
    },
    "additionalProperties": False,
}


def maintenance_lookup(
    context: ToolContext,
    plant: str | None = None,
    inverter: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    type: str | None = None,
) -> dict[str, Any]:
    source = context.data.table("maintenance")
    filters_applied = any(value is not None for value in (plant, inverter, status, priority, type))
    frame = filter_plant(source, context, plant)
    frame = filter_exact(frame, "inverter_id", inverter)
    frame = filter_exact(frame, "status", status)
    frame = filter_exact(frame, "priority", priority)
    frame = filter_exact(frame, "type", type)
    payload = {
        "ok": True,
        "matched": int(len(frame)),
        "status_counts": counts(frame, "status"),
        "priority_counts": counts(frame, "priority"),
        "maintenance": records(frame, _FIELDS),
    }
    total_key = "total_tickets_all_plants" if filters_applied else "total_tickets"
    payload[total_key] = int(len(source))
    return payload


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="maintenance",
            description=(
                "Look up maintenance work by plant, inverter, status, priority, or work type. "
                "Returns structured ticket records and summary counts."
            ),
            parameters=PARAMETERS,
            handler=maintenance_lookup,
        )
    )
