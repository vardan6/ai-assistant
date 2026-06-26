"""Inverters tool."""
from __future__ import annotations

from typing import Any

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
    frame = filter_exact(frame, "status", status)
    return {
        "ok": True,
        "total_inverters": int(len(source)),
        "matched": int(len(frame)),
        "status_counts": counts(frame, "status"),
        "inverters": records(frame, _FIELDS),
    }


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
