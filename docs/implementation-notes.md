# Implementation notes

> Sparse: durable invariants/contracts/gotchas only. Not a mirror of the code.

- **Dataset "today" = max reading timestamp (~2026-06-22), not wall-clock.** All relative time
  windows ("today", "last week", "this month") must anchor to the dataset max timestamp. The CSVs
  are the full, frozen dataset.
- **Secrets never live in config.** Config JSON holds `secret_ref` only; raw API keys live in the
  SQLite `SecretStore` (`auth_mode: stored_secret`) or env vars (`auth_mode: env_var`).
- **No raw CSV rows in any LLM prompt.** Tools aggregate in pandas and return structured dicts.
- **Tool gating is per-request** (`gated` | `bind_all`) — only the `bind_tools` list differs; the
  loop is identical. Gated must always include `plants`/`inverters` resolvers.
</content>
