# Requirements — AI-agent quality, token efficiency, and runtime

> Finished behavior, constraints, and priority ordering for the agent runtime
> itself. Complements `pipeline.md` (what the assistant answers) by stating *how
> well* the agent must reason. Decision rationale lives in
> `docs/adr/0002` (tool gating), `0003` (schema card), and `0004` (LangGraph ReAct).

## Goal

Build a best-in-class ReAct-loop agent on **LangChain + LangGraph**. LangChain
owns model/tool integration; LangGraph owns conversation state and control flow.
The agent must satisfy three requirements, in strict priority order.

## R1 — Response quality (highest priority)

The agent must produce the best possible answers, using modern, high-quality
approaches to ReAct-loop and agent design, implementation, and architecture.
Quality is never sacrificed for R2 or R3.

- Explicit, inspectable intent classification before data access, treated as a
  **revisable prior — not an irreversible gate**. When the initial gated tool
  subset proves insufficient, the runtime may widen the bound tools mid-loop
  (still never binding all tables) rather than failing or refusing.
- Session-aware multi-turn reasoning: resolve follow-ups, corrections, and
  challenges against prior turns rather than treating each turn as standalone.
  Every non-command, non-smalltalk turn is interpreted with bounded session
  state **before** tool selection or refusal; a later turn is never answered as
  a standalone prompt.
- Refusal (out-of-scope) is a **final outcome after** session-aware
  interpretation, never a classifier shortcut taken before context is considered.
- Reconcile a new result against a prior claim when the user disputes an answer.
- Aggregation in code; never hallucinate a number; refuse cleanly when a request
  is genuinely unanswerable.

## R2 — Token efficiency (second priority)

At equal answer quality, the agent must be highly token-efficient. It must
**not front-load the whole context** to inflate token usage; context should be
loaded **gradually and on demand — piece by piece** — in a deliberate,
efficient way.

- Do not bind or load information the current turn does not need.
- Load conversation history under a bounded recency budget, newest first.
- Re-feed only prose answers as history; never re-inject raw tool rows or full
  stored evidence into a later prompt.
- Prefer progressive disclosure of schema/tool detail over sending everything up
  front, whenever it does not cost answer quality.

## R3 — Runtime, reasoning speed, and loop efficiency (third priority)

The agent should minimise latency and ReAct-loop iterations.

- **Deliberate exception to R2:** pre-loading a *small* amount of information is
  encouraged when it raises final-answer quality, saves loop iterations, or
  improves tool discoverability. This is allowed even though it grows the initial
  context, because fewer iterations can lower total token usage — especially when
  it serves final-answer quality (R1), which always wins.
- Short-circuit trivial turns (greetings, commands) before any model call.
- Bound the maximum tool-iteration count per turn.

## Priority resolution

When the three requirements conflict: **R1 > R2 > R3.** A change that pre-loads a
small, high-value context to cut iterations (R3) at a slight cost to raw
front-loaded tokens (R2) is acceptable and preferred when it protects or improves
answer quality (R1). The static schema card (ADR 0003) is the canonical example
of this trade already taken.

## Acceptance criteria

- The runtime is a LangGraph state machine over an explicit agent state, with
  LangChain as the model/tool layer. The graph **owns the loop**: it can
  re-plan, widen tool policy, and retry within a turn — not a one-pass DAG that
  delegates the only iteration to a downstream function after decisions are made.
- Every non-command, non-smalltalk turn passes through a session-aware
  interpretation step **before** tool selection or refusal.
- Tool selection is intent-gated by default; the orchestrator never binds all
  tables on every turn (see `pipeline.md`, ADR 0002). Gating is a **revisable
  policy** the runtime can widen mid-loop; refusal is emitted only after the
  interpretation step.
- Conversation history is bounded by a documented three-tier budget.
- No raw CSV rows and no stored raw evidence reach any model prompt.
- Trivial turns resolve on a local fast-path with zero model calls.
- Per-turn tool iterations are capped and traced.

## Non-goals

- No RAG / retrieval / embeddings (see `pipeline.md`).
- No runtime data-relationship graph engine; relationships ship as the static
  schema card (ADR 0003).
