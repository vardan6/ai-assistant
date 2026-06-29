"""Shared helpers for concise, structured table tools."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .registry import ToolContext

_GENERIC_PLANT_TOKENS = {"plant", "solar", "farm", "park", "pv", "site"}


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
    matched_ids = resolve_plant_ids(context, plant)
    if not matched_ids:
        matched_ids = [str(plant).strip().lower()]
    return frame[frame["plant_id"].astype(str).str.lower().isin(matched_ids)]


def resolve_plant_ids(context: ToolContext, plant: str | None) -> list[str]:
    if not plant:
        return []
    needle = _normalize_text(plant)
    if not needle:
        return []
    plant_frame = context.data.table("plants")
    exact_matches: list[str] = []
    fuzzy_matches: list[str] = []
    query_tokens = _meaningful_tokens(needle)
    for _, row in plant_frame.iterrows():
        plant_id = str(row["plant_id"]).strip()
        plant_id_norm = plant_id.lower()
        name_norm = _normalize_text(row.get("name"))
        location_norm = _normalize_text(row.get("location"))
        if needle in {plant_id_norm, name_norm, location_norm}:
            exact_matches.append(plant_id)
            continue
        if not query_tokens:
            continue
        haystack_tokens = _meaningful_tokens(f"{name_norm} {location_norm}")
        if query_tokens.issubset(haystack_tokens):
            fuzzy_matches.append(plant_id)
    return exact_matches or fuzzy_matches


def resolve_inverter_ids(context: ToolContext, inverter: str | None) -> list[str]:
    if not inverter:
        return []
    needle = _normalize_text(inverter)
    if not needle:
        return []
    frame = context.data.table("inverters")
    exact = frame["inverter_id"].astype(str).str.lower() == needle
    if exact.any():
        return frame.loc[exact, "inverter_id"].astype(str).tolist()
    contains = frame["inverter_id"].astype(str).str.lower().str.contains(re.escape(needle), regex=True)
    return frame.loc[contains, "inverter_id"].astype(str).tolist()


def filter_exact(frame: pd.DataFrame, column: str, value: str | int | None) -> pd.DataFrame:
    if value is None or column not in frame.columns:
        return frame
    needle = str(value).strip().lower()
    return frame[frame[column].astype(str).str.lower() == needle]


def clamp_limit(limit: int | None, *, default: int = 5, maximum: int = 20) -> int:
    if limit is None:
        return default
    return max(1, min(maximum, int(limit)))


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _meaningful_tokens(value: str) -> set[str]:
    return {token for token in value.split() if token and token not in _GENERIC_PLANT_TOKENS}
