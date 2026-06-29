# ADR 0003 — Static schema card over a runtime relationship-graph engine

**Status:** accepted · 2026-06-30
**Extends:** ADR 0001 (no LangGraph `StateGraph`). 0001 settled the *framework*
("no graph library"); this ADR settles the *planning mechanism* ("how the agent
discovers and orders its tool chain").

## Context

A question recurred across several planning rounds, phrased different ways each
time. Stated cleanly:

> **Do we need a relationship graph that the agent traverses at runtime to plan
> its tool-call chain — so that, given a question, it walks the data
> relationships to decide which tools to call, in what order, and which can run
> in parallel?**

Adjacent questions that belong to the same decision:

- *Should tool chains be pre-orchestrated per case from the data relationships,
  or planned by the LLM during the agent (ReAct) loop?*
- *How do we "plant" the parent/child relationships and the name→column /
  name→id resolvers into the agent's context so it builds reliable chains and
  high-quality output?*
- *Which tool calls can run in parallel?*

Countervailing goal the user raised: this repo is meant to seed a **reusable,
universal AI-agent template**, so a real graph engine is attractive for
*future-proofing* even if this dataset doesn't need it — **provided it does not
reduce output quality**.

### Facts that decide it

- The relationship topology is **fixed, public, and two levels deep** — a tree,
  not an unknown branching graph:
  `plants → inverters → {generation_readings, anomalies}`, and
  `plants → {weather_readings, alerts, maintenance}` (alerts/maintenance also
  carry an optional `inverter_id`). See `dataset-analysis.md`
  §"Foreign-key integrity" / §"Join cardinality".
- The longest legitimate chain is **2 hops** (resolve a plant/inverter
  name → id, then query a child table). The task itself only asks to
  "demonstrate at least one 2-step chain."
- Everything a runtime graph traversal would *compute* is already **statically
  known and pre-computed** in `dataset-analysis.md`: the FK edges, the
  name→id resolver (with the `region`-is-a-compass-label trap), the
  measure-semantics reducers, and the vocabulary/exact-match map.

## Decision

**Flatten the fixed relationship graph into a static "schema card" injected into
the system prompt, and let the LLM plan the chain at runtime in the existing
tool-calling loop.** Do **not** build a runtime graph engine that the
orchestrator traverses to pre-plan chains.

The schema card is the graph, expressed as text the model reads once. It carries
exactly three things, all already derived in `dataset-analysis.md`:

1. **FK edges** — the two-level tree above, so "anomalies for Rajasthan" is
   understood as resolve-plant→id then filter-anomalies.
2. **The entity resolver fact** — names resolve against `name`/`location`, not
   `region` (a compass label). One shared resolver owns this.
3. **Measure semantics + vocabulary map** — per-measure reducer
   (`daily_yield` = per-inverter daily max then sum; `total_yield` = window
   diff; `performance_ratio` = null-excluding mean) and exact-match strings
   (`fault` ≠ inside `inverter_fault`).

**Parallelism falls out of FK depth, not a separate planner:** siblings under
one already-resolved parent are independent (alerts + weather + inverter-status
for a resolved plant can fan out in parallel and be gathered); a child-of-child
query is sequential because it needs the parent id first. The model parallelizes
naturally once the card tells it which calls share an input versus depend on an
output; no graph engine is required to expose this.

## Alternatives rejected

- **Runtime relationship-graph engine the orchestrator traverses to pre-plan
  chains.** Over-engineering for a fixed 2-hop tree: it adds a planning/traversal
  layer (new failure surface, harder debrief walkthrough) to solve a routing
  problem the schema card solves with prompt text. It risks *lowering* output
  quality (more moving parts between intent and answer) for no reliability gain
  on this dataset — and the user's own constraint is "drop it if it reduces
  output quality." Conflicts with ADR 0001's direction of a hand-rolled loop.
- **Pre-orchestrated per-case chains** (hard-code the tool sequence for each
  known question shape). Brittle and combinatorial; defeats the point of an
  agent loop and does not generalize to the broader query set we want to cover.

## Consequences

- The "graph" the user kept asking about exists — as the schema card and the
  shared resolver — but at **author/prompt time**, not as a runtime engine. This
  is the answer to "how do we plant the relationships so chains are reliable."
- **Future-proofing is preserved without building the engine now.** The static
  edge/resolver/measure metadata is the exact input a graph engine would consume.
  If a *later, deeper* dataset (many levels, unknown topology) genuinely needs
  runtime traversal, that metadata is promotable into an engine then — and only
  if it demonstrably improves output quality. Revisiting is an **open question**,
  not a backlog commitment (tracked in `roadmap.md` / `activeContext.md`).
- The schema-card contents become a concrete authoring task: assemble points
  1–3 into the system prompt from the `dataset-analysis.md` tables (single
  source of truth; the card points at / is generated from them, not a hand-kept
  copy).
- Reinforces the gating design (ADR 0002): the card tells the model the edges;
  generous resolver inclusion guarantees the id-resolution hop is always
  available.
