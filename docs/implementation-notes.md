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
</content>
