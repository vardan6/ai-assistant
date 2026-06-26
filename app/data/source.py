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
