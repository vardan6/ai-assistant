#!/usr/bin/env python3
"""Golden answers for the demo questions and section-3 oracle pins.

Computes the expected answers *directly from the CSVs*, deliberately NOT through
the app tools. This remains the independent correctness oracle for the dataset.

    .venv/bin/python scripts/golden_answers.py
    .venv/bin/python scripts/golden_answers.py --write

Time is anchored to reference_now (max observation timestamp), not wall clock.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "input" / "tables-extracted"
DOC_PATH = ROOT / "docs" / "golden-answers.md"

OBSERVATION_DATES = {
    "generation_readings.csv": "timestamp",
    "weather_readings.csv": "timestamp",
    "alerts.csv": "created_at",
    "anomalies.csv": "detected_date",
    "inverters.csv": "last_seen",
}
TABLE_FILES = tuple(OBSERVATION_DATES) + ("plants.csv", "maintenance.csv")

PARSE_DATES = {
    "generation_readings.csv": ["timestamp"],
    "weather_readings.csv": ["timestamp"],
    "alerts.csv": ["created_at", "acknowledged_at", "resolved_at"],
    "anomalies.csv": ["detected_date", "resolved_date"],
    "inverters.csv": ["last_maintenance_date", "last_seen"],
    "maintenance.csv": ["scheduled_date", "started_date", "completed_date"],
    "plants.csv": ["commissioned_date"],
}


def load_tables() -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for name in TABLE_FILES:
        tables[name] = pd.read_csv(DATA_DIR / name, parse_dates=PARSE_DATES.get(name, []))
    return tables


def reference_now(tables: dict[str, pd.DataFrame]) -> pd.Timestamp:
    candidates = []
    for file_name, column in OBSERVATION_DATES.items():
        frame = tables[file_name]
        if column in frame.columns and frame[column].notna().any():
            candidates.append(frame[column].max())
    if not candidates:
        raise RuntimeError("No observation timestamps found for reference_now.")
    return max(candidates)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _id_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return str(value)


def _round(value: float | int | None, digits: int = 1) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _window_start(anchor: pd.Timestamp, window: str) -> pd.Timestamp:
    if window == "last_week":
        return (anchor - timedelta(days=6)).normalize()
    if window == "this_month":
        return anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unsupported window: {window}")


def _resolve_plant(tables: dict[str, pd.DataFrame], hint: str) -> tuple[str, str]:
    plants = tables["plants.csv"]
    needle = _normalize_text(hint)
    matched = plants[
        plants["name"].map(_normalize_text).str.contains(needle, regex=False)
        | plants["location"].map(_normalize_text).str.contains(needle, regex=False)
        | (plants["plant_id"].astype(str) == hint)
    ]
    if matched.empty:
        raise KeyError(f"Unknown plant hint: {hint}")
    row = matched.iloc[0]
    return str(row["plant_id"]), str(row["name"])


def _plant_name(tables: dict[str, pd.DataFrame], plant_id: str | int) -> str:
    plants = tables["plants.csv"]
    matched = plants[plants["plant_id"].map(_id_text) == _id_text(plant_id)]
    if matched.empty:
        return str(plant_id)
    return str(matched.iloc[0]["name"])


def _daily_yield_per_plant(tables: dict[str, pd.DataFrame], anchor: pd.Timestamp) -> pd.DataFrame:
    frame = tables["generation_readings.csv"]
    start = _window_start(anchor, "last_week")
    frame = frame[(frame["timestamp"] >= start) & (frame["timestamp"] <= anchor)].copy()
    frame["day"] = frame["timestamp"].dt.normalize()
    per_day = (
        frame.groupby(["plant_id", "day", "inverter_id"], dropna=False)["daily_yield"]
        .max()
        .groupby(["plant_id", "day"], dropna=False)
        .sum()
        .reset_index(name="daily_yield_total")
    )
    return (
        per_day.groupby("plant_id", dropna=False)["daily_yield_total"]
        .agg(avg_daily_yield="mean", days="count")
        .reset_index()
        .sort_values("plant_id")
    )


def _unresolved_anomalies(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["status"].str.lower() != "resolved"].copy()


def q1_offline_plant_and_alert(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    plants = tables["plants.csv"]
    alerts = tables["alerts.csv"]
    offline = plants[plants["status"].str.lower() == "offline"]
    payload = []
    for _, plant in offline.iterrows():
        plant_alerts = alerts[
            (alerts["plant_id"].astype(str) == str(plant["plant_id"]))
            & (alerts["status"].str.lower() == "open")
        ]
        payload.append(
            {
                "plant": str(plant["name"]),
                "open_alerts": [
                    {
                        "alert_id": int(row["alert_id"]),
                        "severity": str(row["severity"]),
                        "type": str(row["type"]),
                        "description": str(row["description"]),
                    }
                    for _, row in plant_alerts.iterrows()
                ],
            }
        )
    return {"offline_plants": payload}


def q2_avg_daily_yield(tables: dict[str, pd.DataFrame], anchor: pd.Timestamp, hint: str = "Rajasthan") -> dict[str, Any]:
    plant_id, plant_name = _resolve_plant(tables, hint)
    start = _window_start(anchor, "last_week")
    frame = tables["generation_readings.csv"]
    frame = frame[
        (frame["plant_id"].astype(str) == plant_id)
        & (frame["timestamp"] >= start)
        & (frame["timestamp"] <= anchor)
    ].copy()
    frame["day"] = frame["timestamp"].dt.normalize()
    per_day = (
        frame.groupby(["day", "inverter_id"], dropna=False)["daily_yield"]
        .max()
        .groupby("day", dropna=False)
        .sum()
    )
    return {
        "plant": plant_name,
        "window": f"{start.date()}..{anchor.date()}",
        "days_covered": int(len(per_day)),
        "avg_plant_daily_yield_kwh": _round(per_day.mean(), 1),
    }


def q3_open_hotspot_soiling(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    frame = tables["anomalies.csv"]
    hits = frame[
        (frame["status"].str.lower() == "open")
        & (frame["anomaly_type"].str.lower() == "hotspot")
        & (frame["cause"].str.lower() == "soiling")
    ]
    return {
        "filter": "status=open AND anomaly_type=hotspot (exact) AND cause=soiling",
        "count": int(len(hits)),
        "anomaly_ids": [int(v) for v in hits["anomaly_id"].tolist()],
        "note": "empty result is the correct answer if the intersection has no rows",
    }


def q4_mttr_critical(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    frame = tables["alerts.csv"].copy()
    frame = frame[
        (frame["severity"].str.lower() == "critical")
        & frame["created_at"].notna()
        & frame["resolved_at"].notna()
    ]
    frame["mttr_hours"] = (frame["resolved_at"] - frame["created_at"]).dt.total_seconds() / 3600.0
    return {
        "severity": "critical",
        "resolved_count": int(len(frame)),
        "mean_time_to_resolve_hours": _round(frame["mttr_hours"].mean(), 1),
    }


def q5_weather_today(tables: dict[str, pd.DataFrame], anchor: pd.Timestamp, hint: str = "Gujarat") -> dict[str, Any]:
    plant_id, plant_name = _resolve_plant(tables, hint)
    frame = tables["weather_readings.csv"]
    frame = frame[(frame["plant_id"].astype(str) == plant_id) & (frame["timestamp"] <= anchor)]
    row = frame.sort_values("timestamp").iloc[-1]
    return {
        "plant": plant_name,
        "as_of": row["timestamp"].isoformat(sep=" "),
        "reading": {
            "ambient_temp": _round(row["ambient_temp"], 2),
            "module_temp": _round(row["module_temp"], 2),
            "irradiation": _round(row["irradiation"], 2),
            "wind_speed": _round(row["wind_speed"], 2),
            "humidity": _round(row["humidity"], 1),
            "cloud_cover_pct": _round(row["cloud_cover_pct"], 1),
            "rainfall_mm": _round(row["rainfall_mm"], 1),
        },
    }


def q6_revenue_loss() -> dict[str, Any]:
    return {
        "answerable": False,
        "reason": "Revenue lost from downtime needs outage-energy (lost kWh) × tariff. The data has downtime_minutes only on alerts and no lost-energy bridge, so the number cannot be derived. Correct behaviour: refuse; do not fabricate.",
    }


def build_case_oracle(tables: dict[str, pd.DataFrame], anchor: pd.Timestamp) -> dict[str, dict[str, Any]]:
    plants = tables["plants.csv"]
    inverters = tables["inverters.csv"]
    generation = tables["generation_readings.csv"]
    weather = tables["weather_readings.csv"]
    alerts = tables["alerts.csv"]
    maintenance = tables["maintenance.csv"]
    anomalies = tables["anomalies.csv"]

    rajasthan_id, rajasthan_name = _resolve_plant(tables, "Rajasthan")
    gujarat_id, gujarat_name = _resolve_plant(tables, "Gujarat")
    tamil_id, tamil_name = _resolve_plant(tables, "Tamil Nadu")
    start_week = _window_start(anchor, "last_week")
    start_month = _window_start(anchor, "this_month")

    daily_yield = _daily_yield_per_plant(tables, anchor)
    daily_yield_map = {
        _plant_name(tables, row["plant_id"]): {
            "plant_id": _id_text(row["plant_id"]),
            "avg_daily_yield_kwh": _round(row["avg_daily_yield"], 1),
            "days": int(row["days"]),
        }
        for _, row in daily_yield.iterrows()
    }

    rajasthan_generation_month = generation[
        (generation["plant_id"].astype(str) == rajasthan_id)
        & (generation["timestamp"] >= start_month)
        & (generation["timestamp"] <= anchor)
    ].sort_values(["inverter_id", "timestamp"])
    total_yield_diff = (
        rajasthan_generation_month.groupby("inverter_id", dropna=False)["total_yield"]
        .agg(lambda series: series.iloc[-1] - series.iloc[0])
        .sum()
    )

    inv_4135001_01 = generation[
        (generation["inverter_id"] == "INV_4135001_01")
        & (generation["timestamp"] >= start_week)
        & (generation["timestamp"] <= anchor)
    ]

    performance_ratio = generation[generation["performance_ratio"].notna()]
    best_pr = (
        performance_ratio.groupby("inverter_id", dropna=False)["performance_ratio"]
        .mean()
        .sort_values(ascending=False)
    )
    top_inverter_id = str(best_pr.index[0])
    peak_ac_power = generation[
        (generation["timestamp"] >= start_month) & (generation["timestamp"] <= anchor)
    ]
    peak_ac_row = peak_ac_power.loc[peak_ac_power["ac_power"].idxmax()]

    rajasthan_weather_week = weather[
        (weather["plant_id"].astype(str) == rajasthan_id)
        & (weather["timestamp"] >= start_week)
        & (weather["timestamp"] <= anchor)
    ]
    weather_month = weather[
        (weather["timestamp"] >= start_month) & (weather["timestamp"] <= anchor)
    ]
    cloud_cover_mean = weather_month.groupby("plant_id", dropna=False)["cloud_cover_pct"].mean()
    cloud_cover_max = weather_month.groupby("plant_id", dropna=False)["cloud_cover_pct"].max()
    wet_tamil = weather[
        (weather["plant_id"].astype(str) == tamil_id)
        & (weather["timestamp"] >= start_week)
        & (weather["timestamp"] <= anchor)
    ]

    open_critical_alerts = alerts[
        (alerts["status"].str.lower() == "open")
        & (alerts["severity"].str.lower() == "critical")
    ]
    rajasthan_alerts = alerts[alerts["plant_id"].astype(str) == rajasthan_id].copy()
    resolved_alerts = alerts[alerts["resolved_at"].notna() & alerts["created_at"].notna()].copy()
    resolved_alerts["mttr_hours"] = (
        resolved_alerts["resolved_at"] - resolved_alerts["created_at"]
    ).dt.total_seconds() / 3600.0

    done_maintenance = maintenance[maintenance["status"].str.lower() == "done"]
    completed_maintenance = maintenance[maintenance["duration_hours"].notna()]
    gujarat_in_progress = maintenance[
        (maintenance["plant_id"].astype(str) == gujarat_id)
        & (maintenance["status"].str.lower() == "in_progress")
    ]

    open_hotspots = anomalies[
        (anomalies["status"].str.lower() == "open")
        & (anomalies["anomaly_type"].str.lower() == "hotspot")
    ]
    open_anomalies = anomalies[anomalies["status"].str.lower() == "open"]
    unresolved_rajasthan = _unresolved_anomalies(
        anomalies[anomalies["plant_id"].astype(str) == rajasthan_id]
    )
    open_anomalies_by_plant = (
        open_anomalies.groupby("plant_id", dropna=False)["anomaly_id"].count().to_dict()
    )
    fault_inverter = inverters[inverters["status"].str.lower() == "fault"].iloc[0]
    fault_inverter_id = str(fault_inverter["inverter_id"])
    fault_alerts = alerts[alerts["inverter_id"] == fault_inverter_id]
    fault_anomalies = anomalies[anomalies["inverter_id"] == fault_inverter_id]

    plant_pr_week = (
        generation[
            (generation["timestamp"] >= start_week)
            & (generation["timestamp"] <= anchor)
            & generation["performance_ratio"].notna()
        ]
        .groupby("plant_id", dropna=False)["performance_ratio"]
        .mean()
        .sort_values()
    )
    worst_plant_id = str(plant_pr_week.index[0])
    worst_plant_name = _plant_name(tables, worst_plant_id)

    return {
        "P4": {
            "question": "Which plant has the highest feed-in tariff?",
            "answer": {
                "plant": str(plants.sort_values("tariff_usd_per_kwh", ascending=False).iloc[0]["name"]),
                "tariff_usd_per_kwh": _round(plants["tariff_usd_per_kwh"].max(), 3),
            },
        },
        "I5": {
            "question": 'Show inverters that are "online" in status but have an open alert.',
            "answer": {
                "count": int(
                    len(
                        alerts[
                            (alerts["status"].str.lower() == "open")
                            & alerts["inverter_id"].isin(
                                inverters[inverters["status"].str.lower() == "online"]["inverter_id"]
                            )
                        ]
                    )
                ),
                "items": [
                    {
                        "alert_id": int(row["alert_id"]),
                        "inverter_id": str(row["inverter_id"]),
                        "plant_id": str(row["plant_id"]),
                        "severity": str(row["severity"]),
                        "type": str(row["type"]),
                    }
                    for _, row in alerts[
                        (alerts["status"].str.lower() == "open")
                        & alerts["inverter_id"].isin(
                            inverters[inverters["status"].str.lower() == "online"]["inverter_id"]
                        )
                    ].iterrows()
                ],
            },
        },
        "G1": {
            "question": "Avg daily yield per plant over last week.",
            "answer": daily_yield_map,
        },
        "G2": {
            "question": "Total energy generated by Rajasthan this month.",
            "answer": {
                "plant": rajasthan_name,
                "window": f"{start_month.date()}..{anchor.date()}",
                "total_yield_kwh": _round(total_yield_diff, 1),
            },
        },
        "G3": {
            "question": "Average AC power for INV_4135001_01 last 7 days.",
            "answer": {
                "inverter_id": "INV_4135001_01",
                "window": f"{start_week.date()}..{anchor.date()}",
                "mean_ac_power_kw": _round(inv_4135001_01["ac_power"].mean(), 2),
                "reading_count": int(len(inv_4135001_01)),
            },
        },
        "G4": {
            "question": "Which inverter has the highest performance ratio?",
            "answer": {
                "inverter_id": top_inverter_id,
                "mean_performance_ratio": _round(best_pr.iloc[0], 4),
            },
        },
        "G5": {
            "question": "What was the peak AC power across the fleet this month?",
            "answer": {
                "ac_power_kw": _round(peak_ac_row["ac_power"], 2),
                "plant_id": str(peak_ac_row["plant_id"]),
                "plant": _plant_name(tables, peak_ac_row["plant_id"]),
                "inverter_id": str(peak_ac_row["inverter_id"]),
                "timestamp": peak_ac_row["timestamp"].isoformat(sep=" "),
            },
        },
        "W2": {
            "question": "Average irradiation at Rajasthan last week.",
            "answer": {
                "plant": rajasthan_name,
                "mean_irradiation": _round(rajasthan_weather_week["irradiation"].mean(), 2),
            },
        },
        "W3": {
            "question": "Which plant had the highest cloud cover this month?",
            "answer": {
                "oracle_reducer": "mean",
                "plant": _plant_name(tables, cloud_cover_mean.sort_values(ascending=False).index[0]),
                "monthly_mean_cloud_cover_pct": _round(cloud_cover_mean.max(), 2),
                "monthly_peak_cloud_cover_pct": _round(
                    cloud_cover_max.loc[cloud_cover_mean.sort_values(ascending=False).index[0]],
                    1,
                ),
                "note": "The question is slightly underspecified; the oracle pins the default reducer to monthly mean cloud cover. Peak cloud cover is included for traceability.",
            },
        },
        "W4": {
            "question": "Was there any rainfall at Tamil Nadu this week?",
            "answer": {
                "plant": tamil_name,
                "had_rainfall": bool((wet_tamil["rainfall_mm"] > 0).any()),
                "rainfall_total_mm": _round(wet_tamil["rainfall_mm"].sum(), 1),
            },
        },
        "AL1": {
            "question": "What open critical alerts exist?",
            "answer": {
                "count": int(len(open_critical_alerts)),
                "items": [
                    {
                        "alert_id": int(row["alert_id"]),
                        "plant": _plant_name(tables, row["plant_id"]),
                        "severity": str(row["severity"]),
                        "type": str(row["type"]),
                    }
                    for _, row in open_critical_alerts.iterrows()
                ],
            },
        },
        "AL3": {
            "question": "Show all alerts for Rajasthan.",
            "answer": {
                "plant": rajasthan_name,
                "count": int(len(rajasthan_alerts)),
                "status_counts": {
                    str(key): int(value)
                    for key, value in rajasthan_alerts["status"].value_counts().to_dict().items()
                },
            },
        },
        "AL4": {
            "question": "What is the total downtime caused by resolved alerts?",
            "answer": {
                "total_downtime_minutes": _round(resolved_alerts["downtime_minutes"].sum(), 0),
            },
        },
        "AL5": {
            "question": "Mean time to resolve an alert (all severities).",
            "answer": {
                "mean_time_to_resolve_hours": _round(resolved_alerts["mttr_hours"].mean(), 2),
                "resolved_alerts": int(len(resolved_alerts)),
            },
        },
        "M3": {
            "question": "Total maintenance cost on done tickets.",
            "answer": {
                "total_cost_usd": _round(done_maintenance["cost_usd"].sum(), 0),
            },
        },
        "M4": {
            "question": "Average duration of completed maintenance.",
            "answer": {
                "mean_duration_hours": _round(completed_maintenance["duration_hours"].mean(), 2),
                "completed_tickets": int(len(completed_maintenance)),
            },
        },
        "M5": {
            "question": "Which inverters at Gujarat have maintenance in progress?",
            "answer": {
                "plant": gujarat_name,
                "count": int(len(gujarat_in_progress)),
                "tickets": [
                    {
                        "ticket_id": int(row["ticket_id"]),
                        "inverter_id": str(row["inverter_id"]),
                    }
                    for _, row in gujarat_in_progress.iterrows()
                ],
            },
        },
        "AN1": {
            "question": "Which inverters have open hotspot anomalies?",
            "answer": {
                "count": int(len(open_hotspots)),
                "anomaly_ids": [int(v) for v in open_hotspots["anomaly_id"].tolist()],
                "inverter_ids": [str(v) for v in open_hotspots["inverter_id"].dropna().tolist()],
            },
        },
        "AN4": {
            "question": "Total estimated power loss from open anomalies.",
            "answer": {
                "estimated_power_loss_kw": _round(open_anomalies["estimated_power_loss_kw"].sum(), 2),
            },
        },
        "AN6": {
            "question": "Summarise all unresolved anomalies for Rajasthan.",
            "answer": {
                "plant": rajasthan_name,
                "unresolved_total": int(len(unresolved_rajasthan)),
                "status_counts": {
                    str(key): int(value)
                    for key, value in unresolved_rajasthan["status"].value_counts().to_dict().items()
                },
                "open_subset": int((unresolved_rajasthan["status"].str.lower() == "open").sum()),
            },
        },
        "X2": {
            "question": "Compare Rajasthan and Tamil Nadu on open anomalies and yield.",
            "answer": {
                rajasthan_name: {
                    "open_anomalies": int(open_anomalies_by_plant.get(int(rajasthan_id), 0)),
                    "avg_daily_yield_kwh": daily_yield_map[rajasthan_name]["avg_daily_yield_kwh"],
                },
                tamil_name: {
                    "open_anomalies": int(open_anomalies_by_plant.get(int(tamil_id), 0)),
                    "avg_daily_yield_kwh": daily_yield_map[tamil_name]["avg_daily_yield_kwh"],
                },
            },
        },
        "X3": {
            "question": "For the inverter in fault, what alert and anomalies does it have?",
            "answer": {
                "inverter_id": fault_inverter_id,
                "alerts": [
                    {
                        "alert_id": int(row["alert_id"]),
                        "status": str(row["status"]),
                        "severity": str(row["severity"]),
                        "type": str(row["type"]),
                    }
                    for _, row in fault_alerts.iterrows()
                ],
                "anomalies": [
                    {
                        "anomaly_id": int(row["anomaly_id"]),
                        "status": str(row["status"]),
                        "anomaly_type": str(row["anomaly_type"]),
                        "cause": str(row["cause"]),
                    }
                    for _, row in fault_anomalies.iterrows()
                ],
            },
        },
        "X4": {
            "question": "Which plant is performing worst right now?",
            "answer": {
                "oracle_metric": "lowest mean performance_ratio over the last anchored week",
                "plant": worst_plant_name,
                "plant_id": worst_plant_id,
                "mean_performance_ratio": _round(plant_pr_week.iloc[0], 4),
                "note": "The question is underspecified. The oracle pins a concrete metric so future replays compare against the same interpretation.",
            },
        },
    }


def build() -> dict[str, Any]:
    tables = load_tables()
    anchor = reference_now(tables)
    demos = {
        "Q1 offline plant + open alert": q1_offline_plant_and_alert(tables),
        "Q2 avg daily yield Rajasthan last week": q2_avg_daily_yield(tables, anchor),
        "Q3 open hotspot anomalies caused by soiling": q3_open_hotspot_soiling(tables),
        "Q4 mean time to resolve critical alert": q4_mttr_critical(tables),
        "Q5 weather at Gujarat today": q5_weather_today(tables, anchor),
        "Q6 revenue lost from Tamil Nadu downtime (unanswerable)": q6_revenue_loss(),
    }
    return {
        "reference_now": anchor.isoformat(sep=" "),
        "demo_questions": demos,
        "case_oracle": build_case_oracle(tables, anchor),
    }


def render(answers: dict[str, Any]) -> str:
    lines = [
        "# Golden answers\n",
        f"_Computed directly from the CSVs by `scripts/golden_answers.py` on {datetime.now():%Y-%m-%d %H:%M}. Independent of the app tools — use as the correctness oracle. Re-run after any data change._\n",
        f"**reference_now:** `{answers['reference_now']}`\n",
        "\n## Demo questions\n",
    ]
    for question, payload in answers["demo_questions"].items():
        lines.append(f"\n### {question}\n")
        lines.append("```json")
        lines.append(json.dumps(payload, indent=2, sort_keys=True, default=str))
        lines.append("```")
    lines.append("\n## Section 3 oracle pins\n")
    lines.append("_These entries pin every former `[oracle⁺]` placeholder in `docs/test-plan.md` §3. Where a question is underspecified, the oracle states the reducer/metric it chose so replays stay comparable._\n")
    for case_id in sorted(answers["case_oracle"]):
        payload = answers["case_oracle"][case_id]
        lines.append(f"\n### {case_id} — {payload['question']}\n")
        lines.append("```json")
        lines.append(json.dumps(payload["answer"], indent=2, sort_keys=True, default=str))
        lines.append("```")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write docs/golden-answers.md")
    args = parser.parse_args()
    answers = build()
    report = render(answers)
    if args.write:
        DOC_PATH.write_text(report)
        print(f"wrote {DOC_PATH.relative_to(ROOT)}", file=sys.stderr)
    print(report)


if __name__ == "__main__":
    main()
