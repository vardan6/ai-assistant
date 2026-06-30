# ADR 0004 — Full ReAct LangGraph agent runtime

**Status:** accepted · 2026-06-30
**Supersedes:** ADR 0001's "no LangGraph graph" constraint for the agent runtime
only.
**Keeps:** ADR 0003's static schema-card approach for dataset relationships.

> **Decision recorded:** LangGraph is the committed target runtime, not a
> deferred maybe. The first session-aware slices may still land on the existing
> loop as incremental steps, but the destination is the LangGraph state machine.
> The two caveats below (D3 attribution, reference does not de-risk LangGraph)
> are retained as **revisit conditions**, not blockers: if early slices show the
> hand-rolled loop already covers the behavior cleanly, re-open the scope of how
> much graph machinery is worth it — but the default direction is LangGraph.

## Context

The current implementation has a per-request tool-calling loop. It can iterate
over model/tool calls inside one request, but it does not load previous chat
turns into the next request. Session history is persisted for display/resume,
not used as agent state.

This caused a visible failure:

- "please doublecheck for 4137001" was answered as a broad plant-health request
  instead of a contextual recheck of the previous anomaly predicate.
- "So your initial answer was wrong" was answered with the generic dataset
  out-of-scope refusal, because the system did not treat it as a challenge about
  a previous answer.

The user now wants the project to behave like a modern AI agent with a complete
ReAct loop and asked to plan around LangChain and LangGraph.

Two caveats bound this decision and must not be lost:

- **The turn-2 failure attribution is not fully settled.** It may be a
  conversation-state defect (this ADR's subject) or a single-turn tool/filter
  defect already tracked in roadmap §2c, or a final-answer formatting issue. The
  reconciliation behavior proposed here only produces correct output if the §2c
  tool fixes land first. This ADR does not claim D3 is purely an orchestration
  defect.
- **The reference does not de-risk LangGraph.** `remote-rover` uses a hand-rolled
  LangChain loop with no `StateGraph`; it validates "session messages as
  first-class state," nothing more. LangGraph is a new bet justified by the
  reusable-template goal, not by prior art in this codebase.

## Decision

Propose replacing the current pipeline-centered ReAct loop with a
session-aware LangGraph agent runtime.

The runtime should make conversation state explicit and route each turn through
nodes for context loading, turn classification, follow-up resolution, tool
selection, ReAct model/tool iteration, reconciliation, synthesis, and
persistence.

LangChain remains the model/tool integration layer. LangGraph owns state and
control flow.

## Relationship to ADR 0003

ADR 0003 (accepted) rejected a runtime relationship-graph engine, partly on the
rationale that it "conflicts with ADR 0001's direction of a hand-rolled loop."
Accepting this ADR softens that specific premise: control flow moves to
LangGraph. ADR 0003's *data-model* decision is untouched — the static schema card
and structured tools remain how the agent learns dataset relationships. The only
thing revisited is the hand-rolled-loop framing for **conversation control**, not
the rejection of a runtime data-relationship engine.

## Non-decision

This ADR does not propose a runtime data-relationship graph for the CSV schema.
ADR 0003 remains valid: the dataset's fixed FK tree, vocabulary rules, and
measure semantics are supplied through the static schema card and structured
tools. LangGraph is for agent state and loop orchestration, not for replacing
the data model.

## Alternatives

- Keep the current single-request hand-rolled loop and add a few heuristics.
  This is likely insufficient: it may patch "doublecheck" but will keep failing
  broader meta-conversation and correction turns.
- Add bounded prior messages to the current loop but avoid LangGraph. This is a
  useful first slice and may be kept as an intermediate step, but it does not
  give the explicit state machine the user wants for a reusable agent template.
- Port the remote rover loop wholesale. Rejected: rover is domain-heavy. The
  reusable pattern is bounded session messages plus tool traces, not the rover
  domain stack.

## Consequences

- Existing API contracts can remain stable while the backend runtime changes.
- Tests must expand from single-turn oracle replay to multi-turn replay.
- Trace metadata should expose graph nodes, resolved question, tool evidence,
  and stop reason.
- The roadmap should pause broad existing-tool polish until the agent-runtime
  direction is accepted, because some failures are orchestration defects rather
  than tool defects — but the §2c tool fixes (D3/X4/G4) are a prerequisite of
  the reconciliation oracle and should land regardless of this decision.
- Multi-turn tests must assert on a structured `prior_answer_verdict`
  (correct/wrong/incomplete) rather than on free-form reconciliation prose.
- Re-injected session history must be projected to strip raw tool rows;
  `SessionStore` stays canonical if a LangGraph checkpointer is added.
