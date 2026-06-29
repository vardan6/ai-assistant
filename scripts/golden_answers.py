#!/usr/bin/env python3
"""Golden answers for the demo questions — an independent correctness oracle.

Computes the expected answer to each suggested demo question *directly from the
CSVs*, deliberately NOT through the app's tools. The redesigned tools can then be
asserted against these numbers (aggregation-correctness criterion), and a drift
here flags a data change worth re-profiling.

    python scripts/golden_answers.py            # print the answer key
    python scripts/golden_answers.py --write    # also write docs/golden-answers.md

Reducers follow the "Measure semantics" table in docs/dataset-analysis.md:
daily_yield = per-inverter daily max; MTTR = mean(resolved-created); etc.
Time is anchored to reference_now (max observation timestamp), not wall clock.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "input" / "tables-extracted"
DOC_PATH = ROOT / "docs" / "golden-answers.md"

# Date columns that count toward the reference_now anchor (real observations).
OBSERVATION_DATES = {
    "generation_readings.csv": "timestamp",
    "weather_readings.csv": "timestamp",
    "alerts.csv": "created_at",
    "anomalies.csv": "detected_date",
    "inverters.csv": "last_seen",
}
DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def parse_date(v):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except (ValueError, TypeError):
            continue
    return None


def load(name):
    with open(DATA_DIR / name, newline="") as fh:
        return list(csv.DictReader(fh))


def fnum(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def reference_now(tables):
    best = None
    for f, col in OBSERVATION_DATES.items():
        for r in tables[f]:
            d = parse_date(r.get(col, ""))
            if d and (best is None or d > best):
                best = d
    return best


def plant_id_by_hint(tables, hint):
    """Resolve a loose plant hint against name/location (not region)."""
    h = hint.lower()
    for p in tables["plants.csv"]:
        if h in p["name"].lower() or h in p["location"].lower():
            return p["plant_id"], p["name"]
    return None, None


def q1_offline_plant_and_alert(tables):
    offline = [p for p in tables["plants.csv"] if p["status"].lower() == "offline"]
    out = []
    for p in offline:
        alerts = [a for a in tables["alerts.csv"]
                  if a["plant_id"] == p["plant_id"] and a["status"].lower() == "open"]
        out.append({
            "plant": p["name"],
            "open_alerts": [
                {"alert_id": a["alert_id"], "severity": a["severity"],
                 "type": a["type"], "description": a["description"]}
                for a in alerts
            ],
        })
    return {"offline_plants": out}


def q2_avg_daily_yield(tables, anchor, hint="Rajasthan"):
    pid, name = plant_id_by_hint(tables, hint)
    start = (anchor - timedelta(days=6)).replace(hour=0, minute=0, second=0)
    # per (inverter, day) daily max, then sum across inverters per day, mean over days
    by_inv_day = defaultdict(float)
    for r in tables["generation_readings.csv"]:
        if r["plant_id"] != pid:
            continue
        d = parse_date(r["timestamp"])
        y = fnum(r.get("daily_yield"))
        if d is None or y is None or not (start <= d <= anchor):
            continue
        key = (r["inverter_id"], d.date())
        by_inv_day[key] = max(by_inv_day[key], y)
    per_day = defaultdict(float)
    for (_inv, day), y in by_inv_day.items():
        per_day[day] += y
    days = sorted(per_day)
    avg = statistics.mean(per_day.values()) if per_day else None
    return {
        "plant": name, "window": f"{start.date()}..{anchor.date()}",
        "days_covered": len(days),
        "avg_plant_daily_yield_kwh": round(avg, 1) if avg is not None else None,
    }


def q3_open_hotspot_soiling(tables):
    hits = [a for a in tables["anomalies.csv"]
            if a["status"].lower() == "open"
            and a["anomaly_type"].lower() == "hotspot"      # exact, excludes 'multi hotspot'
            and a["cause"].lower() == "soiling"]
    return {
        "filter": "status=open AND anomaly_type=hotspot (exact) AND cause=soiling",
        "count": len(hits),
        "anomaly_ids": [a["anomaly_id"] for a in hits],
        "note": "empty result is the correct answer if the intersection has no rows",
    }


def q4_mttr_critical(tables):
    hours = []
    for a in tables["alerts.csv"]:
        if a["severity"].lower() != "critical":
            continue
        c, r = parse_date(a.get("created_at", "")), parse_date(a.get("resolved_at", ""))
        if c and r:
            hours.append((r - c).total_seconds() / 3600)
    return {
        "severity": "critical",
        "resolved_count": len(hours),
        "mean_time_to_resolve_hours": round(statistics.mean(hours), 1) if hours else None,
    }


def q5_weather_today(tables, anchor, hint="Gujarat"):
    pid, name = plant_id_by_hint(tables, hint)
    rows = [(parse_date(r["timestamp"]), r) for r in tables["weather_readings.csv"]
            if r["plant_id"] == pid]
    rows = [(d, r) for d, r in rows if d and d <= anchor]
    if not rows:
        return {"plant": name, "reading": None}
    d, r = max(rows, key=lambda x: x[0])
    fields = ["ambient_temp", "module_temp", "irradiation", "wind_speed",
              "humidity", "cloud_cover_pct", "rainfall_mm"]
    return {
        "plant": name, "as_of": d.isoformat(sep=" "),
        "reading": {k: fnum(r.get(k)) for k in fields},
    }


def q6_revenue_loss(_tables):
    return {
        "answerable": False,
        "reason": "Revenue lost from downtime needs per-inverter outage energy (lost kWh) "
                  "× tariff. The data has downtime_minutes only on alerts and no lost-energy "
                  "column, so the kWh bridge cannot be built. Correct behaviour: refuse, "
                  "do not fabricate a number.",
    }


def build():
    tables = {f: load(f) for f in
              ["plants.csv", "inverters.csv", "generation_readings.csv",
               "weather_readings.csv", "alerts.csv", "maintenance.csv", "anomalies.csv"]}
    anchor = reference_now(tables)
    answers = {
        "reference_now": anchor.isoformat(sep=" "),
        "Q1 offline plant + open alert": q1_offline_plant_and_alert(tables),
        "Q2 avg daily yield Rajasthan last week": q2_avg_daily_yield(tables, anchor),
        "Q3 open hotspot anomalies caused by soiling": q3_open_hotspot_soiling(tables),
        "Q4 mean time to resolve critical alert": q4_mttr_critical(tables),
        "Q5 weather at Gujarat today": q5_weather_today(tables, anchor),
        "Q6 revenue lost from Tamil Nadu downtime (unanswerable)": q6_revenue_loss(tables),
    }
    return answers


def render(answers):
    import json
    lines = ["# Golden answers (demo questions)\n",
             f"_Computed directly from the CSVs by `scripts/golden_answers.py` on "
             f"{datetime.now():%Y-%m-%d %H:%M}. Independent of the app tools — use as the "
             "correctness oracle. Re-run after any data change._\n",
             f"**reference_now:** `{answers['reference_now']}`\n"]
    for q, a in answers.items():
        if q == "reference_now":
            continue
        lines.append(f"\n## {q}\n")
        lines.append("```json")
        lines.append(json.dumps(a, indent=2, default=str))
        lines.append("```")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write docs/golden-answers.md")
    args = ap.parse_args()
    answers = build()
    report = render(answers)
    if args.write:
        DOC_PATH.write_text(report)
        print(f"wrote {DOC_PATH.relative_to(ROOT)}", file=sys.stderr)
    print(report)


if __name__ == "__main__":
    main()
