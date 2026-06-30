# Design — full ReAct agent redesign

> Proposed direction for replacing the current per-request tool loop with a
> conversation-aware, modern ReAct agent runtime.

## Trigger

Replay D3 exposed a core agent gap:

1. User asked: "Which inverters have open hotspot anomalies caused by soiling?"
2. Assistant answered a global anomaly query.
3. User followed up: "please doublecheck for 4137001"
4. Assistant answered a broad plant-health summary instead of rechecking the same
   predicate constrained to plant `4137001`.
5. User said: "So your initial answer was wrong."
6. Assistant returned the generic dataset out-of-scope refusal.

The last answer is the decisive failure. The user was not asking a new dataset
question; they were challenging the previous answer. The system treated the
message as a standalone prompt because session history is persisted only after
the pipeline answers. Prior turns are not loaded into intent classification or
synthesis.

## Current gap

The current loop is only a single-request ReAct-like loop:

```text
latest user question
  -> intent classification
  -> bind selected tools
  -> model/tool iterations inside this one request
  -> final answer
  -> append turn to session store
```

That is not enough for a modern conversational agent. It can use tools within a
request, but it cannot reliably:

- resolve follow-ups such as "doublecheck for 4137001";
- understand disagreement/correction turns such as "your initial answer was wrong";
- compare a new result against an earlier answer;
- answer questions about the previous conversation;
- preserve tool outputs as evidence across turns;
- decide whether the right action is answer, re-run tools, ask a clarifying
  question, or acknowledge/correct a prior answer.

## Reference finding

The remote rover reference project also uses a LangChain hand-rolled tool loop,
not a LangGraph `StateGraph`. However, its chat service passes bounded recent
messages into the model and then invokes the agent runtime with those messages.
The useful reference pattern is not "copy the old loop exactly"; it is:

- session messages are first-class input state;
- messages are trimmed to a context budget before invocation;
- prompt/context snapshots are injected as separate system context;
- tool runtime receives session-scoped context;
- traces, tool calls, and stop reasons are stored on the assistant message.

Our current implementation copied the simple loop shape but lost the
conversation-state path that makes follow-ups possible.

## Target behavior

The assistant should behave as one continuous agent inside a chat session:

- Every non-command chat turn is evaluated with bounded recent conversation
  history and relevant prior tool evidence.
- Follow-up questions are rewritten or resolved against prior turns before data
  tools are called.
- Disputes and corrections trigger a reconciliation path: identify the previous
  claim, identify the predicate that produced it, re-run or inspect the relevant
  evidence, then state whether the prior answer was right, wrong, or incomplete.
- The agent can answer meta-conversation questions when the answer is in session
  history.
- Ambiguous references should be resolved from context when safe; otherwise ask
  a narrow clarification.
- Dataset refusals are used only for genuinely unanswerable dataset requests,
  not for conversation-management turns.

For the D3 replay, the expected reconciliation is:

```text
The initial global answer was for open hotspot anomalies caused by soiling:
anomaly ids 7 and 55, on INV_4135001_09 and INV_4136001_08.

For plant 4137001, there are open hotspot anomalies, but their causes are
physical internal and shading, not soiling. So the initial global answer was
not wrong; the later double-check answer was wrong because it answered a broad
plant-health question instead of rechecking the same filter for 4137001.
```

## Proposed architecture

Move from `Pipeline.answer(question)` to a session-aware agent invocation:

```text
session_id + latest user message
  -> load bounded session state
  -> classify turn kind
  -> resolve/rewrite contextual question when needed
  -> build agent state
  -> run ReAct graph/tool loop
  -> validate/refine answer against tool evidence
  -> persist user + assistant messages with trace/evidence metadata
```

### Agent state

The runtime state should include:

- `session_id`
- `messages`: bounded recent user/assistant messages
- `latest_user_message`
- `turn_kind`: data question, follow-up, dispute/correction, clarification,
  smalltalk, command/meta, out-of-scope
- `resolved_question`: standalone version of the latest user request when needed
- `intent`
- `tool_policy`: gated, bind_all, or future mode
- `tool_calls`
- `evidence`: selected prior tool results and current tool results
- `answer`
- `stop_reason`
- `trace_events`

### Graph shape

Use LangGraph for the agent runtime once dependencies and project constraints are
accepted:

```text
load_session_context
  -> classify_turn
  -> maybe_resolve_followup
  -> select_tools
  -> agent_reasoning
  -> execute_tools
  -> should_continue?
       yes -> agent_reasoning
       no  -> reconcile_or_synthesize
  -> persist_turn
```

The graph is not a replacement for data tools. Tools still own aggregation and
return structured dicts. The graph owns conversation state, routing, loop
control, evidence reconciliation, and stop conditions.

### LangChain/LangGraph split

- LangChain remains the model/tool abstraction layer.
- LangGraph should own state transitions, durable control flow, loop edges,
  retry/stop behavior, and checkpointer integration if used.
- Existing `ToolRegistry` and tool handlers should remain independently
  testable and callable.
- Existing intent classification can become one graph node rather than an
  external prelude.

## Design implications

This proposed direction supersedes the narrow "no LangGraph" decision in ADR
0001 if accepted. ADR 0001 was reasonable for the initial graded deliverable,
but it optimized for a small single-request pipeline. The user's current product
goal is broader: a reusable modern AI-agent template with real conversational
agent behavior.

ADR 0003's schema-card decision can still stand. A LangGraph runtime does not
require a runtime relationship-graph engine for the CSV schema. The static
schema card can remain the way the agent learns dataset relationships, while
LangGraph handles conversation and ReAct control flow.

## Thin implementation slices

1. Session-aware prompt path: load bounded prior messages before answering and
   pass them to intent/synthesis. No LangGraph yet. Verify D3 follow-up and
   dispute behavior improves.
2. Follow-up resolver node: turn "doublecheck for 4137001" into a standalone
   constrained question using prior turns.
3. Dispute/reconciliation node: handle "that was wrong" by comparing prior
   claims with current evidence instead of running the generic out-of-scope
   path.
4. LangGraph runtime skeleton: introduce a graph behind the existing API with
   the same tool registry and trace payloads.
5. Evidence persistence: store compact tool evidence with assistant messages and
   make it available to later reconciliation turns.
6. Full replay suite: add multi-turn cases for follow-up, correction, prior
   answer inspection, and context-resolved ambiguity.

## Open questions

- Should LangGraph be mandatory, or should the first session-aware slices land
  before the dependency switch?
- Should prior tool results be stored in full, compacted, or summarized for
  future turns?
- How large should the session context budget be per provider?
- Should intent classification be preserved as a required explicit node for
  every turn, including meta-conversation turns?
- Should the UI expose "resolved question" and "evidence used" in the agent
  activity panel?
