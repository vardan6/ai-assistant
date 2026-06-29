"""DataSource interface — the swappable boundary between tools and storage.

Tools depend only on this protocol, never on pandas/CSV/SQLite directly, so the
backing store can change later (SQLite/DuckDB) without touching the tool layer.
The pandas implementation lives in `pandas_source.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

import pandas as pd

# The seven canonical tables, one per CSV.
TABLE_NAMES: tuple[str, ...] = (
    "plants",
    "inverters",
    "generation_readings",
    "weather_readings",
    "alerts",
    "anomalies",
    "maintenance",
)

# Canonical CSV schema required for runtime-safe dataset activation.
REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "plants": (
        "plant_id",
        "name",
        "location",
        "region",
        "latitude",
        "longitude",
        "capacity_mw",
        "num_inverters",
        "panel_type",
        "tracker_type",
        "commissioned_date",
        "grid_operator",
        "tariff_usd_per_kwh",
        "status",
    ),
    "inverters": (
        "inverter_id",
        "plant_id",
        "manufacturer",
        "model",
        "rated_kw",
        "string_count",
        "firmware_version",
        "serial_number",
        "install_date",
        "last_maintenance_date",
        "status",
        "last_seen",
    ),
    "generation_readings": (
        "reading_id",
        "inverter_id",
        "plant_id",
        "timestamp",
        "dc_power",
        "ac_power",
        "expected_ac_power",
        "performance_ratio",
        "dc_voltage",
        "ac_frequency_hz",
        "inverter_temp",
        "daily_yield",
        "total_yield",
        "status_flag",
    ),
    "weather_readings": (
        "reading_id",
        "plant_id",
        "timestamp",
        "ambient_temp",
        "module_temp",
        "irradiation",
        "poa_irradiance",
        "wind_speed",
        "wind_direction",
        "humidity",
        "cloud_cover_pct",
        "rainfall_mm",
    ),
    "alerts": (
        "alert_id",
        "plant_id",
        "inverter_id",
        "alert_code",
        "severity",
        "type",
        "description",
        "status",
        "priority",
        "created_at",
        "acknowledged_at",
        "resolved_at",
        "downtime_minutes",
        "assigned_to",
    ),
    "anomalies": (
        "anomaly_id",
        "plant_id",
        "inverter_id",
        "asset_id",
        "asset_type",
        "anomaly_type",
        "severity",
        "cause",
        "detection_method",
        "temperature_delta_c",
        "power_loss_pct",
        "estimated_power_loss_kw",
        "detected_date",
        "status",
        "recommended_action",
        "resolved_date",
        "maintenance_ticket_id",
        "inspection_id",
    ),
    "maintenance": (
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
        "parts_replaced",
        "technician",
        "vendor",
    ),
}


@runtime_checkable
class DataSource(Protocol):
    """Read-only access to the solar dataset, aggregation done by callers."""

    def table(self, name: str) -> pd.DataFrame:
        """Return the named table as a DataFrame. Raises KeyError if unknown."""
        ...

    def dataset_today(self) -> datetime:
        """The dataset's max reading timestamp.

        Relative time windows ("today", "last week") anchor here, NOT to
        wall-clock time — the CSVs are the full, frozen dataset.
        """
        ...
