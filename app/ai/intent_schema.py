"""Intent schema — the explicit, logged classification produced before any tool runs.

Shape (design/architecture.md): types A/B/C (combinable), extracted entities,
time_range, metric, out_of_scope, confidence, plus a short summary. This is the
graded "explicit intent classification" artifact — it must be inspectable.
"""
from __future__ import annotations

from typing import Any

VALID_TYPES = {"A", "B", "C"}
_ENTITY_KEYS = ("plants", "inverters", "alerts", "anomalies", "maintenance")


def make_empty_intent() -> dict[str, Any]:
    return {
        "types": [],
        "entities": {key: [] for key in _ENTITY_KEYS},
        "time_range": None,
        "metric": None,
        "out_of_scope": False,
        "confidence": 0.0,
        "summary": "",
    }


def validate_intent(data: dict[str, Any]) -> list[str]:
    """Return a list of schema violations; empty means valid."""
    errors: list[str] = []

    types = data.get("types")
    if not isinstance(types, list):
        errors.append("'types' must be a list")
    else:
        bad = [t for t in types if t not in VALID_TYPES]
        if bad:
            errors.append(f"'types' has invalid values: {bad} (allowed: A/B/C)")

    if "entities" in data and not isinstance(data["entities"], dict):
        errors.append("'entities' must be an object")

    if not isinstance(data.get("out_of_scope", False), bool):
        errors.append("'out_of_scope' must be a boolean")

    confidence = data.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
        errors.append("'confidence' must be a number in [0, 1]")

    return errors


def coerce_intent(data: dict[str, Any]) -> dict[str, Any]:
    """Merge a parsed dict onto the empty shape so every field is present."""
    base = make_empty_intent()
    if isinstance(data.get("types"), list):
        base["types"] = [t for t in data["types"] if t in VALID_TYPES]
    if isinstance(data.get("entities"), dict):
        for key in _ENTITY_KEYS:
            value = data["entities"].get(key)
            if isinstance(value, list):
                base["entities"][key] = [str(v) for v in value]
    if data.get("time_range") is not None:
        base["time_range"] = str(data["time_range"])
    if data.get("metric") is not None:
        base["metric"] = str(data["metric"])
    base["out_of_scope"] = bool(data.get("out_of_scope", False))
    try:
        base["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        base["confidence"] = 0.0
    base["summary"] = str(data.get("summary", ""))
    return base
