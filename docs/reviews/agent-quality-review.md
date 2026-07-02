# Agent-quality review — of record

> **Single review-of-record for agent runtime quality.** Supersedes and absorbs
> three now-archived session artifacts (`docs/archive/`):
> `agent-quality-gap-analysis-2026-07-01.md`,
> `langgraph-agent-runtime-review-2026-07-02.md`,
> `gate2-failure-triage-2026-07-01.md`.
>
> **Scope:** analysis, evidence, and the *why* behind the agent-runtime
> decisions. This is **not** a status tracker. Live status and next work live in
> `roadmap.md` + `activeContext.md`; completed history in `progress.md`;
> requirements/design/decisions in the canonical docs pointed to below. Where a
> decision became durable, this file **points** to its canonical owner rather
> than restating it.

## Canonical owners (where the decisions now live)

| Fact | Owner |
|---|---|
| Requirements, priority R1 > R2 > R3, acceptance criteria | `docs/requirements/agent-quality.md` |
| Reconciled control-flow target (interpret-turn node, graph-owned loop) | `docs/design/full-react-agent-redesign.md` → "Reconciled control-flow target (2026-07-02)" |
| LangGraph runtime decision, revisit conditions | `docs/adr/0004-proposed-full-react-langgraph-agent.md` |
| Tool gating decision | `docs/adr/0002-tool-gating-toggle.md` |
| Static schema card decision | `docs/adr/0003-static-schema-card-over-runtime-graph.md` |
| Forward work (AR-1…AR-5, AQ-1…AQ-4, Gate 2 verify) | `roadmap.md` |
| Live status / next atomic step | `activeContext.md` |

## Adjudicating evidence — the G6 transcript

A three-turn replay (`Average performance ratio at night.` → `yes please` →
`night = 19:00–06:00 … re-check closest window`) degraded turn over turn: a
reasonable first answer, then a generic capability menu, then a context-free
refusal.

Root finding: **this is a behavioral reset, not a context reset.** Session
history *is* loaded and threaded into synthesis (`agent_loop.py` appends prior
turns; the intent classifier even re-captured the night-PR intent) — but it does
not reach the routing/refusal decision, which happens *before* session-aware
interpretation. The model does not lose the context; it fails to act on it.
Switching provider/model between turns makes it *look* like amnesia but is not
the cause.

Two structural defects this exposes:
1. No terminal "undefined" answer for PR-at-night (PR is null with no irradiance).
   Fixed by **G2-FIX-9** (roadmap): an explicit `undefined`/empty verdict when a
   window has zero non-null PR readings — no hardcoded "night" keyword.
2. No "the user is answering my clarifying question" contract: a follow-up
   re-classifies from scratch and can fall back to a generic menu instead of
   re-running the original intent. Addressed by the **AR** track (roadmap).

## Two prior reviews and the conflict between them

- The **gap analysis** (2026-07-01) scored the runtime as an R1/R2/R3 *status
  snapshot* and marked session-aware multi-turn and the LangGraph runtime
  **Implemented**.
- The **runtime review** (2026-07-02) scored the *same code* as an acyclic
  wrapper whose decisive choices (routing, gating, refusal) run before the only
  real loop, and filed F1–F7 with `must_fix_now` classifications.

They cite the same `compile_runtime_graph` and reach opposite verdicts because
they apply different bars: **existence** ("does the mechanism exist?" → done) vs
**decision-ownership/robustness** ("does it own the decision and recover?" →
brittle). Verified against code: `compile_runtime_graph` is a strict DAG
(`load_session_context → route_local → classify_intent →
{tool_free | out_of_scope | run_tool_loop} → (opt) reconcile → END`) with no
edge back into routing/classification; `_select_tool_names` and the
`out_of_scope` branch both sit before `run_tool_loop`.

## Six conflicts, resolved under the quality-first rule

Decision rule: **maximize answer quality (R1); R2/R3 apply only when they cost no
quality; "LangGraph or whatever is better" means adopt whatever gives the graph
session-first interpretation, in-loop recovery, and inspectable decisions.**
Consequence: any verdict scored as an *existence check* or an *R3 efficiency win*
cannot outrank an R1 defect in the same code. That resolves all six toward the
runtime review.

| # | Subsystem | Gap analysis | Runtime review | Resolved (quality-first) |
|---|---|---|---|---|
| 1 | Multi-turn session-awareness | Implemented | F4/F5: not first-class, phrase-matched smell | Review — the #1 quality defect; G6 is the proof. Not done. |
| 2 | LangGraph runtime | "wired = Implemented" | F1: acyclic wrapper, not the loop | "Wired" ≠ done. Graph must own a cyclic, recoverable loop. |
| 3 | Single pre-loop classifier | R3 win ("one call, not two") | F2: R1 liability (unrecoverable early gate) | **Load-bearing.** Reclassify as R1 defect. Keep classifier as a *revisable prior*, not an irreversible gate — widen tools mid-loop, never bind all tables. |
| 4 | `out_of_scope` timing | (implied clean) | F3: fires too early | Review — refusal becomes a *final* outcome after interpretation. |
| 5 | R1 maturity | "done except Gate-2 verification" | root cause: "halfway between two architectures" | Adopt "mid-migration": R1 is structurally incomplete, not merely unverified. |
| 6 | Per-request compile | evidence-of-done | F7: recompiled-per-request smell (`defer`) | Symptom of #2, not independent. Fixed for free once the graph owns the loop (roadmap AR-5). |

Conflict #3 is the load-bearing one: the same mechanism was filed under R3 (a
win) and R1 (a defect). Because R1 > R2 > R3 is the project's own ordering, the
R1 framing wins automatically. The resolution is **"prior, not gate"**: keep the
cheap classification and the ADR 0003 front-loaded card (they cost no quality and
save iterations), but remove their *finality* so the loop can widen the bound
tool subset when the initial gate proves insufficient.

## Graded status matrix (replaces the old binary "Implemented")

| Capability | Graded verdict | Evidence |
|---|---|---|
| LangGraph StateGraph exists and is wired | Present | `agent_graph.py` `compile_runtime_graph` |
| Graph *owns* the loop (re-plan / widen / retry) | **Not decision-owning** → AR track | strict DAG, no back-edge |
| Session-aware multi-turn | **Mechanism present, not decision-owning** | history reaches synthesis, not routing/refusal (G6) |
| Intent classification | Present, but an irreversible gate → should be a prior | `_select_tool_names` pre-loop |
| `out_of_scope` refusal | Present, but too early | conditional edge before `run_tool_loop` |
| Bounded history / prose-only re-feed | Implemented | three-tier budget, history projection |
| Local fast-path (smalltalk/command) | Implemented | `route_local_turn` |
| Prompt caching (`cache_control`) | Not implemented | R2 gap → roadmap AQ-2 |
| Progressive / on-demand schema loading | Not built | core R2 ask → roadmap AQ-4 |
| Iteration/latency telemetry | Missing | R3 measured target → roadmap AQ-3 |
| `langgraph` in `requirements.txt` | Missing | imported/installed, undeclared → roadmap AQ-1 |

## Resolved direction (canonical: design doc)

All six conflicts collapse into one decision, now recorded in
`docs/design/full-react-agent-redesign.md`: introduce a session-aware
`interpret_session_turn` node that every non-command turn passes through *before*
tool selection or refusal; make tool-gating and refusal **revisable outcomes of a
cyclic graph**; keep the classifier and schema card as cheap priors; stay on
LangGraph but make it own the loop. Sliced forward as **AR-1…AR-5** in
`roadmap.md`, HITL-gated on `/review-triage` accepting F1–F5 as `must_fix_now`.

## Out of scope of this reconciliation

- **R2 (token efficiency)** — prompt caching and progressive schema-card loading
  are untouched here and remain the separate AQ track (`roadmap.md` AQ-2/AQ-4).
  The runtime review is explicitly silent on R2; do not treat it as covering R2.

## Residual from the Gate 2 triage (now archived)

The per-oracle Gate 2 triage drove ten `G2-FIX` slices, all landed. Remaining
work is tracked canonically in `roadmap.md`, not here:
- **G2-FIX-11** — fresh-port Gate 2 verification (open, HITL).
- Matcher-only cases (`AL6`, `X5`, `X7`) — resolved by matcher relaxation
  (`G2-FIX-10`), no assistant-wording changes.
- Any residual `X3` behavior question — see `activeContext.md` open questions.
