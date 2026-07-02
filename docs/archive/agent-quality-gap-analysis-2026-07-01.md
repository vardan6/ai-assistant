# Agent quality / token / runtime — gap analysis (2026-07-01)

> Session artifact. Captures the requirement statement and the code-grounded gap
> analysis so the next session can continue without re-deriving it.
> Requirements now live canonically in `docs/requirements/agent-quality.md`
> (R1 quality > R2 token efficiency > R3 runtime). This file is the *status*
> snapshot behind that doc.

## Requirements captured (corrected from user statement)

1. **R1 — Response quality (top priority).** Best possible answers from a modern,
   high-quality ReAct-loop agent on LangChain + LangGraph. Quality is never
   traded away for R2 or R3.
2. **R2 — Token efficiency.** At equal quality, be very token-efficient. Do not
   front-load the whole context; load gradually, on demand, piece by piece.
3. **R3 — Runtime / reasoning speed / loop efficiency.** Pre-loading a *small*
   amount of context is encouraged when it raises answer quality, saves loop
   iterations, or improves tool discoverability — even at the cost of a larger
   initial context, since fewer iterations can lower total token usage.

Priority resolution: **R1 > R2 > R3.**

## Status matrix

### R1 — Response quality

| Item | Status | Evidence |
|---|---|---|
| LangChain tool-calling ReAct loop | Implemented | `app/ai/agent_loop.py` (`MAX_TOOL_ITERATIONS = 6`) |
| LangGraph `StateGraph` runtime, wired | Implemented | `app/ai/agent_graph.py:363` (`StateGraph`), `compile_runtime_graph`; `pipeline.py:429` compile, `:442` `runtime.invoke`. ADR 0004 |
| Session-aware multi-turn (follow-up / dispute / reconciliation / `prior_answer_verdict`) | Implemented | `turn_router.py`, `agent_graph.py` |
| Explicit intent classification (A/B/C), one call `{turn_kind, intent}` | Implemented | `intent_*`, `pipeline.py` |
| End-to-end quality verification | **Open** | Gate 2 not clean on fresh port; `activeContext.md` next step `G2-FIX-11`; `roadmap.md` `G-INT2/3` open |

### R2 — Token efficiency

| Lever | Status | Notes |
|---|---|---|
| Tool gating (never bind all 7 tables) | Implemented | ADR 0002; `gated` default vs `bind_all` |
| Bounded history (count cap / char budget / per-message cap) | Implemented | three-tier budget, `agent_graph.py` |
| Re-feed prose only, never raw rows / stored evidence | Implemented | history projection |
| **Prompt caching (`cache_control`)** | **Documented but NOT implemented** | ADR 0002 assumes Anthropic caching erases ~90% of tool-def + system-prompt cost. `cache_control` appears nowhere in `app/`. Schema card (`pipeline.py:159/363`) is re-sent uncached every iteration. Biggest R2 gap. |
| **Progressive / on-demand loading ("piece by piece")** | **Not built, not planned** | Schema card + gated tool subset loaded up-front per turn. No lazy disclosure (per-table schema section, summary-then-drill-down). This is the core R2 ask and has no mechanism or roadmap slice. |

### R3 — Runtime / loop efficiency

| Lever | Status | Notes |
|---|---|---|
| Local fast-path before any model call | Implemented | `route_local_turn` (smalltalk / ambiguous plant / commands) |
| Schema card front-loaded to cut discovery iterations | Implemented | ADR 0003 — the R3 trade already taken (FK tree + resolver + measure card → correct 2-hop chain + parallel siblings without discovery loops) |
| One classification call, not two | Implemented | bounds per-turn cost |
| Iteration cap | Implemented | `MAX_TOOL_ITERATIONS = 6` |
| Iteration / latency as a measured target | Missing | `usage_telemetry` tracks tokens only; no iteration-count or latency budget/gate |

## Conflicts flagged (code is truth)

1. **`langgraph` used + installed but missing from `requirements.txt`.**
   `agent_graph.py:8` imports it; runs in `.venv`; not declared. Reproducibility
   gap for the reusable-template goal.
2. **ADR 0002's token rationale depends on prompt caching that does not exist.**
   The "tokens are negligible, caching erases ~90%" argument is currently
   unbacked in code.

## Net summary

- **Considered & implemented:** LangGraph ReAct runtime, session-awareness,
  intent gating, bounded history, prose-only re-feed, fast-path, schema-card
  front-loading (the R3 trade).
- **Documented but not implemented:** prompt caching (ADR 0002).
- **Missing / not planned:** true progressive on-demand context loading (core R2),
  iteration/latency measurement, `langgraph` in `requirements.txt`, end-to-end
  quality verification (Gate 2 open).

## Proposed next-session actions (not yet started)

- [ ] Add `langgraph` to `requirements.txt` (quick, unblocks reproducibility).
- [ ] Implement Anthropic prompt caching (`cache_control`) for system prompt +
      schema card + tool defs; measure hit rate. Closes the ADR 0002 gap. Use the
      `claude-api` skill (it mandates caching).
- [ ] Design an R2 progressive-loading slice: lazy per-table schema-card sections
      keyed to selected tools; consider summary-first-then-drill-down. New ADR if
      it changes the ADR 0003 front-load stance.
- [ ] Add iteration-count + latency to telemetry as an R3 measured target.
- [ ] Sequence the above against the open WAVE 4 Gate 2 work (`G2-FIX-11`,
      `G-INT2/3`) — quality verification (R1) stays ahead of R2/R3 tuning.
