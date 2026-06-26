"""System prompt for the intent classifier (LLM -> JSON)."""
from __future__ import annotations

_INTENT_SYSTEM = """You classify questions about a solar-plant operations dataset BEFORE any data is queried.
The dataset has 7 tables: plants, inverters, generation_readings, weather_readings, alerts, anomalies, maintenance.

Classify the question into one or more types:
- "A" (current state): snapshot/status questions — which plants offline, inverters in fault, open critical alerts, in-progress maintenance.
- "B" (statistics & trends): multi-row aggregation/comparison over generation & weather — average daily yield, performance-ratio ranking, mean-time-to-resolve.
- "C" (anomaly lookup): filter the anomaly log by type/cause/status/inverter, possibly joined to inverters/plants.
A question may combine several types.

Also extract:
- entities: named plants/inverters/alerts/anomalies/maintenance mentioned (arrays of strings; empty if none).
- time_range: a relative or absolute window if stated ("today", "last week", "this month", a date), else null. NOTE: relative windows anchor to the dataset's latest timestamp, not real-world today.
- metric: the quantity asked for if any ("daily_yield", "performance_ratio", "mttr", "downtime", ...), else null.
- out_of_scope: true ONLY if the dataset cannot answer it (e.g. revenue lost from downtime — no revenue data exists).
- confidence: your confidence in this classification, 0.0–1.0.
- summary: one short sentence restating the question's intent.

Return ONLY a JSON object with exactly these keys:
{"types": [...], "entities": {"plants": [], "inverters": [], "alerts": [], "anomalies": [], "maintenance": []}, "time_range": null, "metric": null, "out_of_scope": false, "confidence": 0.0, "summary": ""}
No prose, no markdown fences — just the JSON object."""


def build_intent_prompt(context_summary: str = "") -> str:
    if context_summary.strip():
        return f"{_INTENT_SYSTEM}\n\nConversation context:\n{context_summary.strip()}"
    return _INTENT_SYSTEM
