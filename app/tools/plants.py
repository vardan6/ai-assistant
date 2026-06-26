"""Plants tool — Type A status/snapshot questions about the 3 plants.

Also doubles as a `plant_id`/`name` resolver for multi-step chains later. Returns
a structured dict; aggregation (status counts) is done here in pandas.
"""
from __future__ import annotations

from typing import Any

from .common import clean, counts, records
from .registry import ToolContext, ToolRegistry

# Fields surfaced to the model — operational, not every CSV column.
_PLANT_FIELDS = [
    "plant_id",
    "name",
    "location",
    "region",
    "capacity_mw",
    "num_inverters",
    "status",
    "grid_operator",
]

PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "description": "Filter to plants with this status (e.g. 'active', 'maintenance', 'offline').",
        },
        "plant": {
            "type": "string",
            "description": "Filter to a single plant by plant_id or (case-insensitive) name.",
        },
    },
    "additionalProperties": False,
}


def plants_status(context: ToolContext, status: str | None = None, plant: str | None = None) -> dict[str, Any]:
    frame = context.data.table("plants")
    total = int(len(frame))

    if plant:
        frame = _filter_by_plant(frame, plant)
    if status:
        frame = frame[frame["status"].str.lower() == status.strip().lower()]

    status_counts = counts(context.data.table("plants"), "status")
    return {
        "ok": True,
        "total_plants": total,
        "status_counts": status_counts,
        "matched": int(len(frame)),
        "plants": records(frame, _PLANT_FIELDS),
    }


def _filter_by_plant(frame: pd.DataFrame, plant: str) -> pd.DataFrame:
    needle = str(plant).strip().lower()
    by_id = frame["plant_id"].astype(str).str.lower() == needle
    by_name = frame["name"].astype(str).str.lower() == needle
    return frame[by_id | by_name]


def _clean(value: Any) -> Any:
    return clean(value)


def register(registry: ToolRegistry) -> None:
    registry.register(
        _make_spec(),
    )


def _make_spec():
    from .registry import ToolSpec

    return ToolSpec(
        name="plants",
        description=(
            "Look up solar plants and their operational status. Use for questions about "
            "which plants are active/in maintenance/offline, plant capacity, or to resolve "
            "a plant name to its plant_id. Returns status counts and matching plant records."
        ),
        parameters=PARAMETERS,
        handler=plants_status,
    )
