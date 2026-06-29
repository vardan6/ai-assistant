# Golden answers (demo questions)

_Computed directly from the CSVs by `scripts/golden_answers.py` on 2026-06-29 23:21. Independent of the app tools — use as the correctness oracle. Re-run after any data change._

**reference_now:** `2026-06-22 10:00:00`


## Q1 offline plant + open alert

```json
{
  "offline_plants": [
    {
      "plant": "Tamil Nadu PV Plant",
      "open_alerts": [
        {
          "alert_id": "1",
          "severity": "critical",
          "type": "grid_disconnection",
          "description": "Plant disconnected from grid"
        }
      ]
    }
  ]
}
```

## Q2 avg daily yield Rajasthan last week

```json
{
  "plant": "Rajasthan Solar Park",
  "window": "2026-06-16..2026-06-22",
  "days_covered": 7,
  "avg_plant_daily_yield_kwh": 123354.2
}
```

## Q3 open hotspot anomalies caused by soiling

```json
{
  "filter": "status=open AND anomaly_type=hotspot (exact) AND cause=soiling",
  "count": 2,
  "anomaly_ids": [
    "7",
    "55"
  ],
  "note": "empty result is the correct answer if the intersection has no rows"
}
```

## Q4 mean time to resolve critical alert

```json
{
  "severity": "critical",
  "resolved_count": 6,
  "mean_time_to_resolve_hours": 6.3
}
```

## Q5 weather at Gujarat today

```json
{
  "plant": "Gujarat Solar Farm",
  "as_of": "2026-06-22 10:00:00",
  "reading": {
    "ambient_temp": 26.04,
    "module_temp": 46.24,
    "irradiation": 799.34,
    "wind_speed": 5.29,
    "humidity": 89.5,
    "cloud_cover_pct": 6.5,
    "rainfall_mm": 0.0
  }
}
```

## Q6 revenue lost from Tamil Nadu downtime (unanswerable)

```json
{
  "answerable": false,
  "reason": "Revenue lost from downtime needs per-inverter outage energy (lost kWh) \u00d7 tariff. The data has downtime_minutes only on alerts and no lost-energy column, so the kWh bridge cannot be built. Correct behaviour: refuse, do not fabricate a number."
}
```
