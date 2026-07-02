# Implementation notes

> Sparse: durable invariants/contracts/gotchas only. Not a mirror of the code.

- **Dataset "today" = max reading timestamp (~2026-06-22), not wall-clock.** All relative time
  windows ("today", "last week", "this month") must anchor to the dataset max timestamp. The CSVs
  are the full, frozen dataset.
- **Secrets never live in config.** Config JSON holds `secret_ref` only; raw API keys live in the
  SQLite `SecretStore` (`auth_mode: stored_secret`) or env vars (`auth_mode: env_var`).
- **Data-quality advisories are profiler-derived, not hardcoded.** `scripts/profile_dataset.py`
  regenerates `docs/dataset-analysis.md` on each data change; its "Tool advisories" section is
  authoritative for null-vs-zero columns (e.g. `performance_ratio` empty ⟺ no power → filter, never
  zero-fill), lifecycle nulls (`resolved_at`/`downtime_minutes` only on resolved alerts), and
  silent-downtime inverters. Aggregation tools must honour these or numbers will be wrong.
- **Silent inverter detection is generation-feed recency, not status text.** For I4/current-state
  questions, an inverter is silent when its latest `generation_readings.timestamp` is earlier than
  `effective_now` (normally the dataset anchor), regardless of the `inverters.status` string.
- **Profiler doubles as the tool-design oracle.** Beyond validation, `docs/dataset-analysis.md`
  carries the entity resolver index, vocabulary coverage map (exact stored strings for every demo
  filter word — `in_progress` not "in progress", `region` is a compass label not the state), the
  measure-semantics table (`daily_yield`=daily max, `total_yield`=diff, `performance_ratio`=mean
  ex-null), and the derivable/non-derivable feasibility map (revenue-loss = refuse). Build tools
  against these, not against assumptions about the column names. `scripts/golden_answers.py`
  (→ `docs/golden-answers.md`) is the **independent correctness oracle**: it computes the demo
  answers straight from the CSVs (not via the tools), so redesigned tools can be asserted against
  it. Re-run both after any data change.
- **No raw CSV rows in any LLM prompt.** Tools aggregate in pandas and return structured dicts.
- **Tool gating is per-request** (`gated` | `bind_all`) — only the `bind_tools` list differs; the
  loop is identical. Gated must always include `plants`/`inverters` resolvers.
- **Dataset settings are backend-path driven.** `data.csv_dir` + optional `data.csv_files` resolve
  to one concrete file path per canonical table before dataset load; uploads only populate managed
  backend files and write those paths back into config.
- **Dataset reloads are atomic for new requests only.** Rebuild the pipeline only after validating
  the full resolved dataset; keep the old pipeline alive for in-flight requests and on failed
  reload attempts.
- **Aggregates are deterministic in tools, never synthesized.** Sums/means/maxes (downtime,
  maintenance cost/duration, anomaly power-loss, AC-power mean/max) must be computed in pandas and
  returned as fields; do not let the LLM sum a possibly-truncated record list. Add **general,
  composable** aggregates, not one bespoke reducer per eval question — that overfits the replay
  oracle. Rationale + change set: `docs/archive/gate2-failure-triage-2026-07-01.md`.
- **MTTR is mean resolved-alert duration, not downtime.** Open/unresolved alerts have no
  `resolved_at`, so `mttr(status="open")` returns a structured `verdict="no_inputs"` result. Total
  downtime questions use `alerts.total_downtime_minutes`, not `mttr`.
- **`total_*` is fleet-wide; `matched` is the filtered count.** Entity tools expose both; under a
  plant/inverter filter only `matched` (and `*_ids`) describe the filtered set. Never label
  `total_alerts`/`total_tickets` as a plant-local total — that field-name adjacency caused the X1
  wrong-totals bug. Prefer not emitting `total_*` next to `matched` when a filter is applied.
