# ADR 0004 — Proposed full ReAct LangGraph agent runtime

**Status:** proposed · 2026-06-30
**Supersedes if accepted:** ADR 0001's "no LangGraph graph" constraint for the
agent runtime only.
**Keeps:** ADR 0003's static schema-card approach for dataset relationships.

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

## Decision

Propose replacing the current pipeline-centered ReAct loop with a
session-aware LangGraph agent runtime.

The runtime should make conversation state explicit and route each turn through
nodes for context loading, turn classification, follow-up resolution, tool
selection, ReAct model/tool iteration, reconciliation, synthesis, and
persistence.

LangChain remains the model/tool integration layer. LangGraph owns state and
control flow.

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
  than tool defects.
