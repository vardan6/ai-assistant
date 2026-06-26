"""Tool layer. `build_registry()` wires every available tool into one registry."""
from __future__ import annotations

from . import alerts, anomalies, derived_metrics, generation_readings, inverters, maintenance, plants, weather_readings
from .registry import ToolContext, ToolRegistry, ToolSpec

__all__ = ["ToolContext", "ToolRegistry", "ToolSpec", "build_registry"]


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    alerts.register(registry)
    anomalies.register(registry)
    derived_metrics.register(registry)
    generation_readings.register(registry)
    inverters.register(registry)
    maintenance.register(registry)
    plants.register(registry)
    weather_readings.register(registry)
    return registry
