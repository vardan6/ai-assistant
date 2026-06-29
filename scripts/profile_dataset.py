#!/usr/bin/env python3
"""Profile the solar dataset and emit a markdown validation report.

Single source of truth for "is the data valid and what is its as-of boundary".
Re-run whenever the CSVs change:

    python scripts/profile_dataset.py            # prints report to stdout
    python scripts/profile_dataset.py --write     # also writes docs/dataset-analysis.md

The report covers, per file: row count, date column range (true min/max,
not first/last row -- the files are grouped by entity, not globally sorted),
null counts, value domains for status-like fields, numeric range sanity,
and foreign-key integrity against parent tables.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "input" / "tables-extracted"
DOC_PATH = ROOT / "docs" / "dataset-analysis.md"

# Files whose primary date column is NOT an observation of current state, and
# so must not raise the reference_now anchor. They are still fully profiled in
# the report -- only the anchor calculation skips them.
#   plants.csv      -> commissioned_date: when the plant was built (years ago)
#   maintenance.csv -> scheduled_date:    planned work, can be future-dated
# All other date columns (last_seen, timestamp, created_at, detected_date) are
# real observations and DO count toward the anchor.
NON_OBSERVATION_FILES = {"plants.csv", "maintenance.csv"}

# Primary date column used to define each file's "as-of" boundary.
DATE_COL = {
    "plants.csv": "commissioned_date",
    "inverters.csv": "last_seen",
    "generation_readings.csv": "timestamp",
    "weather_readings.csv": "timestamp",
    "alerts.csv": "created_at",
    "maintenance.csv": "scheduled_date",
    "anomalies.csv": "detected_date",
}

# Curated human descriptions + units per column. This is the only domain
# knowledge in the profiler -- every other column in the data dictionary
# (type, key role, fill) is auto-derived. (description, unit); unit "" = none.
# Unlisted columns still appear in the dictionary with an empty description.
COLUMN_DOCS = {
    "plants.csv": {
        "plant_id": ("Plant identifier", ""),
        "name": ("Plant name", ""),
        "location": ("Site location", ""),
        "region": ("Grid region", ""),
        "latitude": ("Latitude", "°"),
        "longitude": ("Longitude", "°"),
        "capacity_mw": ("Nameplate capacity", "MW"),
        "num_inverters": ("Declared inverter count", ""),
        "panel_type": ("PV panel technology", ""),
        "tracker_type": ("Mounting / tracker type", ""),
        "commissioned_date": ("Grid-connection date", ""),
        "grid_operator": ("Offtaker / grid operator", ""),
        "tariff_usd_per_kwh": ("Feed-in tariff", "USD/kWh"),
        "status": ("Operating state", ""),
    },
    "inverters.csv": {
        "inverter_id": ("Inverter identifier", ""),
        "plant_id": ("Parent plant", ""),
        "manufacturer": ("Inverter maker", ""),
        "model": ("Inverter model", ""),
        "rated_kw": ("Rated AC power", "kW"),
        "string_count": ("PV strings attached", ""),
        "firmware_version": ("Firmware version", ""),
        "serial_number": ("Serial number", ""),
        "install_date": ("Installation date", ""),
        "last_maintenance_date": ("Last service date", ""),
        "status": ("Operating state", ""),
        "last_seen": ("Last telemetry time", ""),
    },
    "generation_readings.csv": {
        "reading_id": ("Row identifier", ""),
        "inverter_id": ("Source inverter", ""),
        "plant_id": ("Source plant", ""),
        "timestamp": ("Reading time", ""),
        "dc_power": ("DC-side power", "kW"),
        "ac_power": ("AC output power", "kW"),
        "expected_ac_power": ("Modelled AC power", "kW"),
        "performance_ratio": ("Actual / expected ratio", ""),
        "dc_voltage": ("DC bus voltage", "V"),
        "ac_frequency_hz": ("Grid frequency", "Hz"),
        "inverter_temp": ("Inverter temperature", "°C"),
        "daily_yield": ("Energy since midnight", "kWh"),
        "total_yield": ("Lifetime cumulative energy", "kWh"),
        "status_flag": ("Operating state", ""),
    },
    "weather_readings.csv": {
        "reading_id": ("Row identifier", ""),
        "plant_id": ("Source plant", ""),
        "timestamp": ("Reading time", ""),
        "ambient_temp": ("Ambient air temperature", "°C"),
        "module_temp": ("PV module temperature", "°C"),
        "irradiation": ("Solar irradiation", "kWh/m²"),
        "poa_irradiance": ("Plane-of-array irradiance", "W/m²"),
        "wind_speed": ("Wind speed", "m/s"),
        "wind_direction": ("Wind direction (compass)", ""),
        "humidity": ("Relative humidity", "%"),
        "cloud_cover_pct": ("Cloud cover", "%"),
        "rainfall_mm": ("Rainfall", "mm"),
    },
    "alerts.csv": {
        "alert_id": ("Alert identifier", ""),
        "plant_id": ("Affected plant", ""),
        "inverter_id": ("Affected inverter", ""),
        "alert_code": ("Alert code", ""),
        "severity": ("Severity level", ""),
        "type": ("Alert category", ""),
        "description": ("Free-text detail", ""),
        "status": ("Open / resolved state", ""),
        "priority": ("Handling priority", ""),
        "created_at": ("Raised time", ""),
        "acknowledged_at": ("Acknowledged time", ""),
        "resolved_at": ("Resolved time", ""),
        "downtime_minutes": ("Downtime caused", "min"),
        "assigned_to": ("Owner / assignee", ""),
    },
    "maintenance.csv": {
        "ticket_id": ("Ticket identifier", ""),
        "plant_id": ("Target plant", ""),
        "inverter_id": ("Target inverter", ""),
        "type": ("Work type", ""),
        "priority": ("Handling priority", ""),
        "status": ("Workflow state", ""),
        "scheduled_date": ("Planned date", ""),
        "started_date": ("Work-start date", ""),
        "completed_date": ("Work-end date", ""),
        "duration_hours": ("Labour duration", "h"),
        "cost_usd": ("Cost", "USD"),
        "parts_replaced": ("Parts replaced", ""),
        "technician": ("Technician", ""),
        "vendor": ("Service vendor", ""),
    },
    "anomalies.csv": {
        "anomaly_id": ("Anomaly identifier", ""),
        "plant_id": ("Affected plant", ""),
        "inverter_id": ("Affected inverter", ""),
        "asset_id": ("Affected asset", ""),
        "asset_type": ("Asset kind", ""),
        "anomaly_type": ("Anomaly category", ""),
        "severity": ("Severity level", ""),
        "cause": ("Root cause", ""),
        "detection_method": ("How detected", ""),
        "temperature_delta_c": ("Temp rise vs normal", "°C"),
        "power_loss_pct": ("Power loss", "%"),
        "estimated_power_loss_kw": ("Estimated power loss", "kW"),
        "detected_date": ("Detection date", ""),
        "status": ("Workflow state", ""),
        "recommended_action": ("Recommended action", ""),
        "resolved_date": ("Resolution date", ""),
        "maintenance_ticket_id": ("Linked maintenance ticket", ""),
        "inspection_id": ("Linked inspection", ""),
    },
}

# Columns whose distinct values we want to enumerate (low-cardinality domains).
DOMAIN_COLS = {
    "plants.csv": ["status", "region"],
    "inverters.csv": ["status"],
    "generation_readings.csv": ["status_flag"],
    "alerts.csv": ["status", "severity", "type"],
    "maintenance.csv": ["status", "priority", "type"],
    "anomalies.csv": ["status", "anomaly_type", "cause", "severity"],
}

# Numeric columns to range-check, with optional sane bounds (lo, hi).
# A value outside bounds is flagged, not corrected.
NUMERIC_RANGE = {
    "plants.csv": {"capacity_mw": (0, None), "tariff_usd_per_kwh": (0, 1)},
    "generation_readings.csv": {
        "ac_power": (0, None),
        "dc_power": (0, None),
        "performance_ratio": (0, 1.2),
        "ac_frequency_hz": (45, 55),
    },
    "weather_readings.csv": {
        "irradiation": (0, None),
        "humidity": (0, 100),
        "cloud_cover_pct": (0, 100),
    },
    "anomalies.csv": {"power_loss_pct": (0, 100)},
}

# Foreign keys: (child_col, parent_file, parent_col). Empty values skipped.
FOREIGN_KEYS = {
    "inverters.csv": [("plant_id", "plants.csv", "plant_id")],
    "generation_readings.csv": [
        ("inverter_id", "inverters.csv", "inverter_id"),
        ("plant_id", "plants.csv", "plant_id"),
    ],
    "weather_readings.csv": [("plant_id", "plants.csv", "plant_id")],
    "alerts.csv": [
        ("plant_id", "plants.csv", "plant_id"),
        ("inverter_id", "inverters.csv", "inverter_id"),
    ],
    "maintenance.csv": [
        ("plant_id", "plants.csv", "plant_id"),
        ("inverter_id", "inverters.csv", "inverter_id"),
    ],
    "anomalies.csv": [
        ("inverter_id", "inverters.csv", "inverter_id"),
        ("plant_id", "plants.csv", "plant_id"),
    ],
}

# Primary key per file (for uniqueness checks).
PK_COL = {
    "plants.csv": "plant_id",
    "inverters.csv": "inverter_id",
    "generation_readings.csv": "reading_id",
    "weather_readings.csv": "reading_id",
    "alerts.csv": "alert_id",
    "maintenance.csv": "ticket_id",
    "anomalies.csv": "anomaly_id",
}

# Time-series files: (entity_col, timestamp_col) for cadence / coverage checks.
TIMESERIES = {
    "generation_readings.csv": ("inverter_id", "timestamp"),
    "weather_readings.csv": ("plant_id", "timestamp"),
}

# Columns that accumulate and must be monotonic non-decreasing per entity over
# time: (entity_col, timestamp_col, value_col). A decrease = sensor reset/error.
CUMULATIVE = {
    "generation_readings.csv": ("inverter_id", "timestamp", "total_yield"),
}

# Column null-rate at/above which we try to explain the nulls as an advisory.
NULL_ADVISORY_THRESHOLD = 0.05

# Vocabulary the demo questions use as filters. The coverage map probes whether
# each term exists as an exact category value, only as a substring of one, or not
# at all -- catching empty-result traps (e.g. "in progress" vs stored `in_progress`,
# "hotspot" also living inside "multi hotspot").
DEMO_TERMS = [
    "online", "offline", "fault", "active", "maintenance",
    "critical", "major", "minor", "warning",
    "open", "resolved", "acknowledged",
    "in progress", "scheduled", "done",
    "hotspot", "soiling", "shading",
]

# Per-metric reducer + the trap a Type-B tool must respect. Curated: this is the
# spec the aggregation tools implement against. (reducer, gotcha).
MEASURE_SEMANTICS = {
    "generation_readings.daily_yield": (
        "max per (inverter, day), then sum across inverters / mean across days",
        "Cumulative *within* a day, resets at midnight. Never SUM raw rows — take "
        "each inverter's daily max first.",
    ),
    "generation_readings.total_yield": (
        "diff: last − first per inverter over the window",
        "Lifetime cumulative (monotonic). Window energy = end − start, never sum/mean.",
    ),
    "generation_readings.performance_ratio": (
        "mean, excluding nulls",
        "Empty at night (no power). Filter nulls before averaging; do not zero-fill.",
    ),
    "generation_readings.ac_power": (
        "mean (instantaneous kW)",
        "Spot power; zeros are legitimate night rows. Mean over readings, not sum.",
    ),
    "alerts.mttr": (
        "mean(resolved_at − created_at)",
        "Only resolved alerts have resolved_at; open alerts are excluded by construction.",
    ),
    "anomalies.estimated_power_loss_kw": (
        "sum for fleet impact, mean for typical severity",
        "Per-anomaly estimate. Sum across open anomalies = current loss exposure.",
    ),
}

# Feasibility map: what the dataset can and cannot answer. Drives refuse-vs-compute
# decisions in the tool layer. (question, derivable?, basis-or-missing).
DERIVABILITY = [
    ("Plant / inverter current status", True, "status fields + reference_now snapshot"),
    ("Avg daily yield per plant / window", True, "generation_readings.daily_yield"),
    ("Performance-ratio ranking", True, "generation_readings.performance_ratio"),
    ("Mean time to resolve alerts", True, "alerts.created_at / resolved_at"),
    ("Open anomalies by type / cause / plant", True, "anomalies + entity resolver"),
    ("Weather snapshot per plant", True, "weather_readings @ anchor"),
    ("Revenue lost from downtime", False,
     "needs downtime→lost-kWh→tariff bridge; no per-inverter outage energy exists. Refuse."),
    ("Forecast / future generation", False, "dataset is historical & frozen; no forward data."),
]

DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def parse_date(v: str):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def load(name: str) -> list[dict]:
    with open(DATA_DIR / name, newline="") as fh:
        return list(csv.DictReader(fh))


def col_values(rows, col):
    return [r[col] for r in rows if col in r and r[col] != ""]


def to_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def numeric_cols(rows):
    """Columns whose non-empty values are >=90% float-parseable."""
    cols = []
    for c in rows[0]:
        vals = col_values(rows, c)
        if vals and sum(to_float(v) is not None for v in vals) >= 0.9 * len(vals):
            cols.append(c)
    return cols


def norm_term(s):
    """Fold case, underscores, hyphens and spaces so 'in progress'=='in_progress'."""
    return " ".join(str(s).lower().replace("_", " ").replace("-", " ").split())


def infer_type(rows, col):
    """Coarse storage type for the data dictionary: id/ts/date/int/float/cat/text."""
    vals = col_values(rows, col)
    if not vals:
        return "—"
    if col.endswith("_id"):
        return "id"
    if sum(parse_date(v) is not None for v in vals) >= 0.9 * len(vals):
        return "ts" if any(":" in v for v in vals) else "date"
    floats = [to_float(v) for v in vals]
    if sum(x is not None for x in floats) >= 0.9 * len(vals):
        return "int" if all(x == int(x) for x in floats if x is not None) else "float"
    distinct = len(set(vals))
    return "cat" if distinct <= 12 and distinct < 0.5 * len(vals) else "text"


def key_role(f, col):
    """PK / FK->parent annotation for a column, or '' if neither."""
    if PK_COL.get(f) == col:
        return "PK"
    for child_col, parent_file, _ in FOREIGN_KEYS.get(f, []):
        if child_col == col:
            return f"FK→{parent_file.replace('.csv', '')}"
    return ""


def levenshtein_le1(a, b):
    """True if edit distance between a and b is exactly 1 (typo candidate)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    # one insertion/deletion: longer must contain shorter with one char skipped
    lo, hi = (a, b) if len(a) < len(b) else (b, a)
    for i in range(len(hi)):
        if hi[:i] + hi[i + 1:] == lo:
            return True
    return False


def explain_nulls(rows, col):
    """Best plain-language reason a column is empty, or None.

    Tries (1) co-occurrence with another numeric column being 0 (e.g. night-time),
    then (2) alignment with a low-cardinality status value (lifecycle nulls).
    """
    is_null = [r.get(col, "") == "" for r in rows]
    null_rows = [r for r, n in zip(rows, is_null) if n]
    full_rows = [r for r, n in zip(rows, is_null) if not n]
    if not null_rows or not full_rows:
        return None

    # (1) zero co-occurrence: null <=> some other numeric column == 0
    best_zero = None
    for m in numeric_cols(rows):
        if m == col:
            continue
        purity = sum(1 for r in null_rows if to_float(r.get(m, "")) == 0) / len(null_rows)
        discrim = 1 - sum(1 for r in full_rows if to_float(r.get(m, "")) == 0) / len(full_rows)
        if purity >= 0.9 and discrim >= 0.9 and (best_zero is None or purity > best_zero[1]):
            best_zero = (m, purity)
    if best_zero:
        return f"empty ⟺ `{best_zero[0]}`=0 (filter out, do not treat as 0)"

    # (2) status alignment: null <=> status == some value
    best_status = None
    for s in rows[0]:
        if s == col:
            continue
        domain = set(col_values(rows, s))
        if not (2 <= len(domain) <= 8) or any(to_float(v) is not None for v in domain):
            continue
        for v in domain:
            align = sum(1 for r, n in zip(rows, is_null) if (r.get(s, "") == v) == n) / len(rows)
            if best_status is None or align > best_status[2]:
                best_status = (s, v, align)
    if best_status and best_status[2] >= 0.9:
        s, v, _ = best_status
        return f"empty ⟺ `{s}`=`{v}` (only the complement rows are valid for this column)"
    return None


def group_dates(rows, ent_col, ts_col):
    groups = defaultdict(list)
    for r in rows:
        d = parse_date(r.get(ts_col, ""))
        if d:
            groups[r.get(ent_col, "")].append(d)
    for ds in groups.values():
        ds.sort()
    return groups


def profile():
    files = list(DATE_COL.keys())
    tables = {f: load(f) for f in files}
    parent_keys = {
        f: {col: {r[col] for r in tables[f]} for col in {"plant_id", "inverter_id"} & set(tables[f][0])}
        for f in files
    }

    out: list[str] = []
    w = out.append
    w("# Initial dataset analysis\n")
    w(f"_Generated by `scripts/profile_dataset.py` on {datetime.now():%Y-%m-%d %H:%M}._\n")
    w("> Re-run after any data change. The pipeline's `reference_now` anchor "
      "should equal the global max below, not the wall clock.\n")

    # --- Freshness / range table ---
    w("\n## Date coverage (as-of boundary)\n")
    w("_Row count and date span of each file. The anchor below is derived from the "
      "newest real observation across all files — it defines the dataset's \"now\"._\n")
    w("| File | Rows | Date column | Earliest | Latest |")
    w("|------|-----:|-------------|----------|--------|")
    global_max = None
    for f in files:
        rows = tables[f]
        col = DATE_COL[f]
        dates = [d for d in (parse_date(v) for v in col_values(rows, col)) if d]
        lo = min(dates).isoformat(sep=" ") if dates else "n/a"
        hi = max(dates) if dates else None
        hi_s = hi.isoformat(sep=" ") if hi else "n/a"
        if hi and f not in NON_OBSERVATION_FILES:  # planned/commissioning dates aren't as-of signals
            global_max = hi if global_max is None else max(global_max, hi)
        w(f"| `{f}` | {len(rows)} | `{col}` | {lo} | {hi_s} |")
    w(f"\n**Suggested `reference_now` = `{global_max.isoformat(sep=' ')}`** "
      "(max *observation* timestamp). Excludes planned/future columns "
      f"({', '.join(sorted(NON_OBSERVATION_FILES))}) — e.g. maintenance can be "
      "scheduled past this point, but no real reading exists after it.\n")
    w("The pipeline uses this as its time anchor: all relative-time queries "
      "(\"today\", \"now\", \"last week\", \"this month\") resolve against it, not the "
      "wall clock. The anchor is **optional and enabled by default**; disable it only "
      "when a live feed replaces these CSVs, in which case it falls back to real time.\n")

    # Staleness check: is the newest observation actually today?
    today = datetime.now().date()
    if global_max:
        stale_days = (today - global_max.date()).days
        if stale_days > 0:
            w(f"> ⚠️ **Stale data:** newest observation is `{global_max.date()}`, but "
              f"today is `{today}` — **{stale_days} day(s) old**. With the anchor enabled "
              "(default) this is handled; without it, every \"today/now\" query returns empty.\n")
        elif stale_days == 0:
            w(f"> ✓ Data is current: newest observation is today (`{today}`).\n")
        else:
            w(f"> ⚠️ Newest observation `{global_max.date()}` is in the **future** "
              f"relative to today (`{today}`) — check the source clock.\n")

    # --- Data dictionary ---
    w("\n## Data dictionary\n")
    w("_Every column in every file, in storage order. `File`/`Rows` are shown once "
      "per file group. `Type` is auto-inferred (id, ts=timestamp, date, int, float, "
      "cat=category, text); `Unit` and the plain-language description are curated; "
      "`Key` marks primary keys and foreign keys to a parent table. This is the map a "
      "tool reads to know which column holds what._\n")
    w("| File | Rows | Column | Description | Type | Unit | Key |")
    w("|------|-----:|--------|-------------|------|------|-----|")
    for f in files:
        rows = tables[f]
        docs = COLUMN_DOCS.get(f, {})
        first = True
        for col in rows[0]:
            desc, unit = docs.get(col, ("", ""))
            file_cell = f"`{f}`" if first else ""
            rows_cell = str(len(rows)) if first else ""
            first = False
            role = key_role(f, col)
            w(f"| {file_cell} | {rows_cell} | `{col}` | {desc or '—'} | "
              f"{infer_type(rows, col)} | {unit or ''} | {role} |")

    # --- Null / completeness ---
    w("\n## Completeness\n")
    w("_Empty-cell counts per column (only columns with gaps are listed). Whether a "
      "gap means \"missing\" or \"not applicable\" is decided in Null semantics below._\n")
    for f in files:
        rows = tables[f]
        gaps = []
        for col in rows[0]:
            empties = sum(1 for r in rows if r[col] == "")
            if empties:
                gaps.append(f"`{col}`={empties}")
        w(f"- `{f}`: " + (", ".join(gaps) if gaps else "no empty cells"))

    # --- Value domains ---
    w("\n## Value domains\n")
    w("_Distinct values of each status/category column. \"Top value\" is the most "
      "common (with its row count); \"Breakdown\" lists the rest by descending "
      "frequency. These are the exact strings tool filters must match._\n")
    w("| Column | Distinct | Top value | Breakdown (count) |")
    w("|--------|---------:|-----------|-------------------|")
    for f, cols in DOMAIN_COLS.items():
        for col in cols:
            ranked = Counter(col_values(tables[f], col)).most_common()
            label = f"{f.replace('.csv', '')}.{col}"
            top = f"{ranked[0][0]} ({ranked[0][1]})" if ranked else "—"
            rest = " · ".join(f"{v} {n}" for v, n in ranked[1:]) or "—"
            w(f"| `{label}` | {len(ranked)} | {top} | {rest} |")

    # --- Numeric range sanity ---
    w("\n## Numeric range checks\n")
    w("_Min/max of key numeric columns against sane physical bounds (e.g. a "
      "performance ratio should sit in 0–1.2); the last column counts values that "
      "fall outside those bounds._\n")
    w("| File | Column | Min | Max | Out-of-bounds |")
    w("|------|--------|----:|----:|---------------|")
    for f, checks in NUMERIC_RANGE.items():
        for col, (lo, hi) in checks.items():
            nums = []
            for v in col_values(tables[f], col):
                try:
                    nums.append(float(v))
                except ValueError:
                    pass
            if not nums:
                continue
            bad = sum(1 for n in nums
                      if (lo is not None and n < lo) or (hi is not None and n > hi))
            flag = f"⚠️ {bad}" if bad else "ok"
            w(f"| `{f}` | `{col}` | {min(nums):.3g} | {max(nums):.3g} | {flag} |")

    # --- Foreign-key integrity ---
    w("\n## Foreign-key integrity\n")
    w("_Child rows whose parent key is absent from the parent table (orphans). Any "
      "non-zero count means joins will silently drop rows and aggregates undercount._\n")
    w("| Child file | Child col | Parent | Orphans |")
    w("|------------|-----------|--------|--------:|")
    for f, fks in FOREIGN_KEYS.items():
        for child_col, parent_file, parent_col in fks:
            parent_set = parent_keys[parent_file].get(parent_col, set())
            vals = col_values(tables[f], child_col)
            orphans = sum(1 for v in vals if v not in parent_set)
            flag = f"⚠️ {orphans}" if orphans else "0"
            w(f"| `{f}` | `{child_col}` | `{parent_file}` | {flag} |")

    # advisories accumulates the tool-facing "be careful" lines, surfaced at the end.
    advisories: list[str] = []

    # --- A. Null semantics & lifecycle ---
    w("\n## Null semantics & lifecycle\n")
    w("_Columns empty in at least "
      f"{NULL_ADVISORY_THRESHOLD:.0%} of rows, with the reason the profiler inferred. "
      "An `⟺` rule means the emptiness is **expected** (structural), not missing data — "
      "e.g. a value that only exists once a record reaches a certain status._\n")
    w("| File | Column | Null % | Inferred meaning |")
    w("|------|--------|------:|------------------|")
    any_null = False
    for f in files:
        rows = tables[f]
        for col in rows[0]:
            empties = sum(1 for r in rows if r[col] == "")
            rate = empties / len(rows)
            if rate < NULL_ADVISORY_THRESHOLD:
                continue
            any_null = True
            reason = explain_nulls(rows, col) or "no structural explanation (genuinely missing?)"
            w(f"| `{f}` | `{col}` | {rate:.0%} | {reason} |")
            if "⟺" in reason:
                advisories.append(f"[null] `{f}.{col}`: {reason}")
    if not any_null:
        w("| — | — | — | no columns above threshold |")

    # --- B. Key & count integrity ---
    w("\n## Key & count integrity\n")
    w("_Primary-key uniqueness per file, plus cross-table reconciliation: a plant's "
      "declared inverter count and capacity should match the child rows that sum to "
      "them. A mismatch points to silent corruption or a dropped table._\n")
    w("| Check | Result |")
    w("|-------|--------|")
    for f in files:
        pk = PK_COL.get(f)
        if not pk:
            continue
        vals = [r[pk] for r in tables[f]]
        dupes = len(vals) - len(set(vals))
        res = "unique ✓" if not dupes else f"⚠️ {dupes} duplicate keys"
        w(f"| `{f}` PK `{pk}` | {res} |")
        if dupes:
            advisories.append(f"[pk] `{f}.{pk}` has {dupes} duplicate keys")
    # plants.num_inverters vs actual child counts
    inv_by_plant = defaultdict(int)
    rated_by_plant = defaultdict(float)
    for r in tables["inverters.csv"]:
        inv_by_plant[r["plant_id"]] += 1
        rated_by_plant[r["plant_id"]] += to_float(r.get("rated_kw", "")) or 0
    for p in tables["plants.csv"]:
        pid, name = p["plant_id"], p["name"]
        declared = int(to_float(p.get("num_inverters", "")) or 0)
        actual = inv_by_plant.get(pid, 0)
        ok = declared == actual
        w(f"| `{name}` num_inverters ({declared}) vs actual ({actual}) | "
          f"{'match ✓' if ok else '⚠️ mismatch'} |")
        if not ok:
            advisories.append(f"[reconcile] {name}: num_inverters={declared} but {actual} inverter rows")
        # capacity_mw vs sum(rated_kw)/1000
        cap = to_float(p.get("capacity_mw", "")) or 0
        sum_mw = rated_by_plant.get(pid, 0) / 1000
        cap_ok = abs(cap - sum_mw) <= 0.05 * max(cap, 1)
        w(f"| `{name}` capacity_mw ({cap:g}) vs Σrated_kw/1000 ({sum_mw:.3g}) | "
          f"{'match ✓' if cap_ok else '⚠️ off by >5%'} |")
        if not cap_ok:
            advisories.append(f"[reconcile] {name}: capacity_mw={cap:g} vs Σrated_kw/1000={sum_mw:.3g}")

    # --- C. Categorical hygiene ---
    w("\n## Categorical hygiene\n")
    w("Near-duplicate enum values (whitespace/case variants or edit-distance 1). "
      "Tool filters must match the exact strings below.\n")
    found_dupe = False
    for f, cols in DOMAIN_COLS.items():
        for col in cols:
            vals = sorted(set(col_values(tables[f], col)))
            norm = defaultdict(list)
            for v in vals:
                norm[" ".join(v.lower().split())].append(v)
            for variants in norm.values():
                if len(variants) > 1:
                    found_dupe = True
                    w(f"- ⚠️ `{f}.{col}`: case/space variants {variants}")
                    advisories.append(f"[enum] `{f}.{col}` variants {variants}")
            for i, a in enumerate(vals):
                for b in vals[i + 1:]:
                    if levenshtein_le1(a, b):
                        found_dupe = True
                        w(f"- ⚠️ `{f}.{col}`: possible typo pair ('{a}', '{b}')")
                        advisories.append(f"[enum] `{f}.{col}` possible typo ('{a}','{b}')")
    if not found_dupe:
        w("- no near-duplicate values detected")

    # --- D. Time-series cadence & coverage ---
    w("\n## Time-series cadence & coverage\n")
    w("_Per-entity sampling interval (cadence), the number of gaps wider than 1.5× "
      "that cadence, and duplicate `(entity, timestamp)` rows. \"Silent gaps\" then "
      "lists entities that stopped reporting well before the anchor — likely offline._\n")
    w("| File | Entity | Cadence | Gaps | Dup (entity,ts) |")
    w("|------|--------|---------|-----:|----------------:|")
    silent = []
    for f, (ent_col, ts_col) in TIMESERIES.items():
        groups = group_dates(tables[f], ent_col, ts_col)
        deltas, gaps, dups = [], 0, 0
        for ds in groups.values():
            for a, b in zip(ds, ds[1:]):
                sec = (b - a).total_seconds()
                if sec == 0:
                    dups += 1
                else:
                    deltas.append(sec)
        median = statistics.median(deltas) if deltas else 0
        gaps = sum(1 for s in deltas if median and s > 1.5 * median)
        cad = f"{median / 3600:g}h" if median else "n/a"
        w(f"| `{f}` | `{ent_col}` | {cad} | {gaps} | {dups} |")
        if gaps:
            advisories.append(f"[gap] `{f}`: {gaps} gaps >1.5x the {cad} cadence")
        # silent downtime: entity last reading well before the anchor
        if global_max and median:
            for ent, ds in groups.items():
                behind = (global_max - ds[-1]).total_seconds()
                if behind > 2 * median:
                    silent.append((f, ent, ds[-1], behind / median))
    if silent:
        w("\n**Silent gaps vs anchor** (last reading well before `reference_now`):\n")
        for f, ent, last, n in sorted(silent, key=lambda x: -x[3])[:10]:
            w(f"- ⚠️ `{ent}` ({f}): last reading {last:%Y-%m-%d %H:%M}, ~{n:.0f}x cadence behind")
        if len(silent) > 10:
            w(f"- …and {len(silent) - 10} more")
        names = ", ".join(e for _, e, _, _ in sorted(silent, key=lambda x: -x[3])[:3])
        advisories.append(
            f"[downtime] {len(silent)} entities silent before `reference_now` "
            f"(e.g. {names}); treat as offline, exclude from 'latest' averages")

    # --- E. Distribution & outliers ---
    w("\n## Distribution & outliers\n")
    w("_Spread of key numeric columns. A high zero count is usually night-time rows; "
      "any negative power or yield is a sensor error. Cumulative columns are also "
      "checked for decreases, which should never happen._\n")
    w("| File | Column | Mean | Median | P95 | Zeros | Negatives |")
    w("|------|--------|----:|-------:|----:|------:|----------:|")
    for f, checks in NUMERIC_RANGE.items():
        for col in checks:
            nums = [x for x in (to_float(v) for v in col_values(tables[f], col)) if x is not None]
            if not nums:
                continue
            s = sorted(nums)
            p95 = s[min(len(s) - 1, int(0.95 * len(s)))]
            zeros = sum(1 for x in nums if x == 0)
            negs = sum(1 for x in nums if x < 0)
            neg_s = f"⚠️ {negs}" if negs else "0"
            w(f"| `{f}` | `{col}` | {statistics.mean(nums):.3g} | "
              f"{statistics.median(nums):.3g} | {p95:.3g} | {zeros} | {neg_s} |")
            if negs:
                advisories.append(f"[outlier] `{f}.{col}` has {negs} negative values")
    # monotonicity of cumulative columns
    for f, (ent_col, ts_col, val_col) in CUMULATIVE.items():
        viol = 0
        seqs = defaultdict(list)
        for r in tables[f]:
            d, v = parse_date(r.get(ts_col, "")), to_float(r.get(val_col, ""))
            if d and v is not None:
                seqs[r.get(ent_col, "")].append((d, v))
        for seq in seqs.values():
            seq.sort()
            viol += sum(1 for (_, a), (_, b) in zip(seq, seq[1:]) if b < a - 1e-6)
        w(f"\n- `{f}.{val_col}` monotonicity (per `{ent_col}`): "
          + ("non-decreasing ✓" if not viol else f"⚠️ {viol} decreases"))
        if viol:
            advisories.append(f"[monotonic] `{f}.{val_col}` decreases {viol}x (sensor reset?)")

    # =====================================================================
    # Tool-design analysis: not "is the data valid" but "is it answerable".
    # These sections map question vocabulary -> columns, joins, exact strings,
    # and the reducers/feasibility the tool layer needs.
    # =====================================================================

    def plant_name(pid):
        for p in tables["plants.csv"]:
            if p["plant_id"] == str(pid):
                return p["name"]
        return None

    def rows_for_plant(f, pid):
        return [r for r in tables[f] if r.get("plant_id") == str(pid)]

    # --- Entity resolver index ---
    w("\n## Entity resolver index\n")
    w("_Canonical identity of every plant, for name→id resolution in multi-step "
      "chains. **Note:** `region` is a compass label (`Northwest`/`West`/`South`), "
      "*not* the state — questions like \"the Gujarat plant\" must resolve against "
      "`name`/`location`, not `region`. One shared resolver should own this._\n")
    w("| plant_id | name | region | location | status | inverters |")
    w("|----------|------|--------|----------|--------|----------:|")
    inv_count = Counter(r["plant_id"] for r in tables["inverters.csv"])
    for p in tables["plants.csv"]:
        pid = p["plant_id"]
        w(f"| `{pid}` | {p['name']} | {p['region']} | {p['location']} | "
          f"{p['status']} | {inv_count.get(pid, 0)} |")

    # --- Join cardinality / fan-out ---
    w("\n## Join cardinality (fan-out)\n")
    w("_Children per parent for each foreign key. High fan-out joins (e.g. inverter→"
      "readings) must be pre-aggregated in code, never returned row-by-row. "
      "`Parents w/ 0` flags entities that would vanish from an inner join._\n")
    w("| Relationship | Parents | Children | Min | Median | Max | Parents w/ 0 |")
    w("|--------------|--------:|---------:|----:|-------:|----:|-------------:|")
    for f, fks in FOREIGN_KEYS.items():
        for child_col, parent_file, parent_col in fks:
            parents = parent_keys[parent_file].get(parent_col, set())
            child_counts = Counter(col_values(tables[f], child_col))
            per = [child_counts.get(k, 0) for k in parents]
            if not per:
                continue
            zeros = sum(1 for n in per if n == 0)
            rel = f"`{parent_file.replace('.csv','')}`→`{f.replace('.csv','')}`"
            w(f"| {rel} | {len(parents)} | {sum(per)} | {min(per)} | "
              f"{int(statistics.median(per))} | {max(per)} | {zeros} |")

    # --- Demo-vocabulary coverage map ---
    w("\n## Vocabulary coverage map\n")
    w("_Does each filter word the demo questions use actually exist as a category "
      "value? `✓ exact` = safe literal match; `~ partial` = the word only lives "
      "*inside* a larger value (match with care); `✗ none` = no such value, the "
      "tool will return empty. The exact strings here are what filters must use._\n")
    w("| Term | Match | Found in (column = value × rows) |")
    w("|------|-------|----------------------------------|")
    domain_index: dict[str, list] = defaultdict(list)
    for f, cols in DOMAIN_COLS.items():
        for col in cols:
            for val, n in Counter(col_values(tables[f], col)).items():
                domain_index[norm_term(val)].append((f"{f.replace('.csv','')}.{col}", val, n))
    for term in DEMO_TERMS:
        nt = norm_term(term)
        exact = domain_index.get(nt, [])
        # supersets: the term appears as a whole word inside a larger value
        supers = []
        for key, locs in domain_index.items():
            if key != nt and nt in key.split():
                supers.extend(locs)
        if exact:
            where = ", ".join(f"`{loc}`=`{v}` ({n})" for loc, v, n in exact)
            if supers:
                extra = ", ".join(f"`{v}` ({n})" for _, v, n in supers)
                where += f" — also *inside*: {extra}"
                advisories.append(f"[vocab] '{term}' is exact, but also appears inside {extra}; "
                                  "exact-match or you over/under-count")
            w(f"| `{term}` | ✓ exact | {where} |")
        elif supers:
            where = ", ".join(f"`{loc}`=`{v}` ({n})" for loc, v, n in supers)
            w(f"| `{term}` | ~ partial | {where} |")
            advisories.append(f"[vocab] '{term}' is not an exact value; only inside {where} — "
                              "substring-match deliberately or results are empty")
        else:
            w(f"| `{term}` | ✗ none | not a value in any category column |")

    # --- Per-window population (anchored) ---
    w("\n## Time-window population\n")
    w("_Row counts for each relative window resolved against `reference_now` "
      f"(`{global_max.isoformat(sep=' ') if global_max else 'n/a'}`). Confirms windows "
      "are non-empty and exposes that \"today\" is the **partial anchor day** (readings "
      "only up to the anchor hour), which skews any same-day average._\n")
    if global_max:
        anchor = global_max
        windows = {
            "today": anchor.replace(hour=0, minute=0, second=0),
            "last_week": anchor - timedelta(days=6),
            "this_month": anchor.replace(day=1, hour=0, minute=0, second=0),
            "last_30_days": anchor - timedelta(days=29),
        }
        w("| Window | From | generation rows | weather rows |")
        w("|--------|------|----------------:|-------------:|")
        for name, start in windows.items():
            gen = sum(1 for v in col_values(tables["generation_readings.csv"], "timestamp")
                      if (d := parse_date(v)) and start <= d <= anchor)
            wx = sum(1 for v in col_values(tables["weather_readings.csv"], "timestamp")
                     if (d := parse_date(v)) and start <= d <= anchor)
            w(f"| `{name}` | {start.isoformat(sep=' ')} | {gen} | {wx} |")

    # --- Cross-table status reconciliation ---
    w("\n## Cross-table status reconciliation\n")
    w("_Do the status signals agree? For each non-online inverter, whether it also "
      "has an open alert and whether its generation feed went silent. Disagreement "
      "means a single status field is not enough — the Type-A tool must combine "
      "signals (e.g. \"offline plant **and** its open alert\")._\n")
    w("| Inverter | Plant | inv.status | Open alerts | Last reading | Silent? |")
    w("|----------|-------|-----------|------------:|--------------|---------|")
    gen_last: dict[str, datetime] = {}
    for r in tables["generation_readings.csv"]:
        d = parse_date(r.get("timestamp", ""))
        if d and (r["inverter_id"] not in gen_last or d > gen_last[r["inverter_id"]]):
            gen_last[r["inverter_id"]] = d
    open_alert_by_inv = Counter(
        r["inverter_id"] for r in tables["alerts.csv"]
        if r.get("status", "").lower() == "open" and r.get("inverter_id")
    )
    flagged = 0
    for inv in tables["inverters.csv"]:
        if inv["status"].lower() == "online":
            continue
        flagged += 1
        iid = inv["inverter_id"]
        last = gen_last.get(iid)
        silent = "—"
        if global_max and last:
            behind_h = (global_max - last).total_seconds() / 3600
            silent = f"⚠️ {behind_h:.0f}h behind" if behind_h > 2 else "current"
        w(f"| `{iid}` | {plant_name(inv['plant_id'])} | {inv['status']} | "
          f"{open_alert_by_inv.get(iid, 0)} | "
          f"{last.isoformat(sep=' ') if last else 'none'} | {silent} |")
    if not flagged:
        w("| — | — | all online | — | — | — |")

    # --- Current-state snapshot @ reference_now ---
    w("\n## Current-state snapshot (Type-A ground truth)\n")
    w("_The present picture per plant at `reference_now`: inverter health, open "
      "alerts/anomalies, and in-progress maintenance. This is the answer key for "
      "Type-A questions and a ready-made golden fixture._\n")
    w("| Plant | status | Inverters on/off/fault | Open alerts | Open anomalies | Maint in-progress |")
    w("|-------|--------|------------------------|------------:|---------------:|------------------:|")
    for p in tables["plants.csv"]:
        pid = p["plant_id"]
        inv_st = Counter(r["status"].lower() for r in rows_for_plant("inverters.csv", pid))
        open_al = sum(1 for r in rows_for_plant("alerts.csv", pid)
                      if r.get("status", "").lower() == "open")
        open_an = sum(1 for r in rows_for_plant("anomalies.csv", pid)
                      if r.get("status", "").lower() == "open")
        maint_ip = sum(1 for r in rows_for_plant("maintenance.csv", pid)
                       if r.get("status", "") == "in_progress")
        on_off = f"{inv_st.get('online',0)}/{inv_st.get('offline',0)}/{inv_st.get('fault',0)}"
        w(f"| {p['name']} | {p['status']} | {on_off} | {open_al} | {open_an} | {maint_ip} |")

    # --- Measure semantics (curated) ---
    w("\n## Measure semantics (aggregation rules)\n")
    w("_How each numeric measure must be reduced, and the trap if you don't. Type-B "
      "tools implement against this — getting the reducer wrong is the most likely "
      "source of a confidently-wrong number._\n")
    w("| Measure | Reducer | Gotcha |")
    w("|---------|---------|--------|")
    for key, (reducer, gotcha) in MEASURE_SEMANTICS.items():
        w(f"| `{key}` | {reducer} | {gotcha} |")

    # --- Derivability / feasibility map ---
    w("\n## Derivable vs non-derivable\n")
    w("_What the dataset can and cannot answer. The non-derivable rows are where the "
      "tool layer must **refuse** rather than fabricate — directly serving the "
      "graceful-degradation requirement (e.g. the revenue-loss demo question)._\n")
    w("| Question | Answerable? | Basis / what's missing |")
    w("|----------|-------------|------------------------|")
    for q, ok, basis in DERIVABILITY:
        w(f"| {q} | {'✓ yes' if ok else '✗ no'} | {basis} |")
        if not ok:
            advisories.append(f"[refuse] '{q}' is not answerable: {basis}")

    # --- Consolidated tool advisories ---
    w("\n## Tool advisories (auto-derived)\n")
    w("> Carefulness list for downstream tools. Each line is a condition the "
      "query/aggregation tools should honour on this dataset.\n")
    if advisories:
        for a in advisories:
            w(f"- {a}")
    else:
        w("- none — data is clean against all checks")

    w("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write docs/dataset-analysis.md")
    args = ap.parse_args()
    report = profile()
    if args.write:
        DOC_PATH.write_text(report)
        print(f"wrote {DOC_PATH.relative_to(ROOT)}", file=sys.stderr)
    print(report)


if __name__ == "__main__":
    main()
