"""Shared helpers for concise, structured table tools."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .registry import ToolContext


def clean(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in frame.columns:
        return {}
    series = frame[column].dropna()
    if series.empty:
        return {}
    return {str(k): int(v) for k, v in series.value_counts().items()}


def records(frame: pd.DataFrame, fields: list[str], *, limit: int | None = None) -> list[dict[str, Any]]:
    columns = [c for c in fields if c in frame.columns]
    if limit is not None:
        frame = frame.head(limit)
    out: list[dict[str, Any]] = []
    for _, row in frame[columns].iterrows():
        out.append({c: clean(row[c]) for c in columns})
    return out


def filter_plant(frame: pd.DataFrame, context: ToolContext, plant: str | None) -> pd.DataFrame:
    if not plant or "plant_id" not in frame.columns:
        return frame
    needle = str(plant).strip().lower()
    plant_frame = context.data.table("plants")
    by_id = plant_frame["plant_id"].astype(str).str.lower() == needle
    by_name = plant_frame["name"].astype(str).str.lower() == needle
    matched_ids = plant_frame.loc[by_id | by_name, "plant_id"].astype(str).tolist()
    if not matched_ids:
        matched_ids = [needle]
    return frame[frame["plant_id"].astype(str).str.lower().isin(matched_ids)]


def filter_exact(frame: pd.DataFrame, column: str, value: str | int | None) -> pd.DataFrame:
    if value is None or column not in frame.columns:
        return frame
    needle = str(value).strip().lower()
    return frame[frame[column].astype(str).str.lower() == needle]


def clamp_limit(limit: int | None, *, default: int = 5, maximum: int = 20) -> int:
    if limit is None:
        return default
    return max(1, min(maximum, int(limit)))
