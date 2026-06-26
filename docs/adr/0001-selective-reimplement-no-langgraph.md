# ADR 0001 — Selective reimplement from the reference; no LangGraph graph

**Status:** accepted · 2026-06-27

## Context

The user wanted to reuse a prior AI-agent project (`remote-rover/gcs_server`). The init-plan
repeatedly referred to "the graph" and to porting the project wholesale then stripping it.

Investigation found:
- **No LangGraph `StateGraph` exists.** Despite `langgraph` imports, orchestration is a
  hand-rolled langchain tool-calling loop (`ai/agent_loop.py`: `invoke_with_tools` /
  `stream_tool_events`). `graph_runtime`/`graph_state` survive only as stale `.pyc`; sources gone.
- The codebase is large and rover-specific: `tool_registry.py` (126K),
  `mission_execution_service.py` (106K), plus MAVLink/road-graph/replay services.
- A few modules are small, clean, and portable (intent, provider registry, secret store, agent
  loop, telemetry, session store).
- The task is small (2–3h estimate, pipeline-focused) and the repo doubles as a presentable
  template.

## Decision

**Selectively reimplement.** Fresh clean repo; copy the small proven modules verbatim where
useful; write a new tool layer for the 7 CSVs; drop all rover/mission/MAVLink/RAG/chat-mode code.
Do **not** port-then-strip.

## Alternatives rejected

- **Port-then-strip:** `tool_registry.py` and mission services are deeply coupled; would leave
  dead imports and confuse the debrief reviewer.
- **Pattern-only rewrite (copy nothing):** discards proven, working code (JSON-repair, provider
  caching, fast-path) for no benefit.

## Consequences

- Cleanest submission and the best template seed.
- "Graph" framing is dropped throughout; we describe a tool-calling loop instead.
- Reuse list is enumerated in `docs/design/architecture.md`.
</content>
