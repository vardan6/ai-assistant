"""Pandas DataSource — loads the 7 CSVs into memory once at startup.

All aggregation happens in the tool layer (pandas), never by handing raw rows to
the model. This class only owns loading + the dataset-today anchor.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from .source import TABLE_NAMES

# Columns parsed as datetimes per table, so tools get real timestamps. Only the
# columns that exist are parsed; missing ones are ignored.
_DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "plants": ("commissioned_date",),
    "inverters": ("install_date", "last_maintenance_date", "last_seen"),
    "generation_readings": ("timestamp",),
    "weather_readings": ("timestamp",),
    "alerts": ("created_at", "acknowledged_at", "resolved_at"),
    "anomalies": ("detected_date", "resolved_date"),
    "maintenance": ("scheduled_date", "started_date", "completed_date"),
}

# Tables whose timestamp column defines "now" for the dataset.
_READING_TABLES: tuple[str, ...] = ("generation_readings", "weather_readings")


class PandasDataSource:
    """In-memory pandas-backed implementation of the DataSource protocol."""

    def __init__(self, csv_dir: str | Path):
        self._csv_dir = Path(csv_dir)
        self._tables: dict[str, pd.DataFrame] = {}
        self._dataset_today: datetime | None = None
        self._load()

    def _load(self) -> None:
        for name in TABLE_NAMES:
            csv_path = self._csv_dir / f"{name}.csv"
            if not csv_path.exists():
                raise FileNotFoundError(f"Missing dataset CSV: {csv_path}")
            frame = pd.read_csv(csv_path)
            for column in _DATE_COLUMNS.get(name, ()):  # parse known date columns
                if column in frame.columns:
                    frame[column] = pd.to_datetime(frame[column], errors="coerce")
            self._tables[name] = frame
        self._dataset_today = self._compute_dataset_today()

    def _compute_dataset_today(self) -> datetime:
        latest: pd.Timestamp | None = None
        for name in _READING_TABLES:
            frame = self._tables.get(name)
            if frame is None or "timestamp" not in frame.columns:
                continue
            column_max = frame["timestamp"].max()
            if pd.isna(column_max):
                continue
            if latest is None or column_max > latest:
                latest = column_max
        if latest is None:
            raise ValueError("Could not determine dataset_today: no reading timestamps found.")
        return latest.to_pydatetime()

    def table(self, name: str) -> pd.DataFrame:
        if name not in self._tables:
            raise KeyError(f"Unknown table: {name!r}. Known: {', '.join(TABLE_NAMES)}")
        # Return a copy so tools can mutate freely without corrupting the cache.
        return self._tables[name].copy()

    def dataset_today(self) -> datetime:
        assert self._dataset_today is not None  # set in _load
        return self._dataset_today
