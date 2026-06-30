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

**Two distinct failures hide under "D3 replay" — keep them separate.**

1. A *conversation-state* failure (the subject of this design): turns 3–6 above
   were answered as standalone prompts because no session history reaches
   `Pipeline.answer`.
2. A *single-turn tool/filter* failure (roadmap §2c, still open): the combined
   `type=hotspot AND cause=soiling` filter returns plant-level totals (9, 7, 55)
   instead of the 2 matching inverters.

Whether turn-2's wrong answer was (1) or (2) is **not yet settled** — it may be a
final-answer/checker formatting issue rather than a filter defect, and needs live
re-verification. This matters because the reconciliation node below can only be
right if the evidence it reconciles against is right. **The §2c tool fixes
(D3/X4/G4) are a prerequisite of the multi-turn reconciliation oracle, not
parallel work** (see "Thin implementation slices" → slice 0).

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

The reference de-risks exactly one thing: **session messages as first-class
input state**. It does **not** de-risk LangGraph — rover has no `StateGraph` to
copy. The LangGraph step below is a *new* bet justified by the reusable-template
goal, not by the reference. Treat "bounded session history + tool traces" as
proven by rover, and "LangGraph control flow" as an unproven addition gated by
ADR 0004.

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
- `prior_answer_verdict`: for dispute/correction turns — `correct`, `wrong`, or
  `incomplete`, plus the referenced prior claim and the predicate that produced
  it. This is the **structured assertion target** for multi-turn tests; do not
  rely on diffing free-form reconciliation prose.
- `answer`
- `stop_reason`
- `trace_events`

`turn_kind` is the **router**; the existing A/B/C `intent` only matters once a
turn is routed to the data path. To bound per-turn cost, a single classification
call should return both `turn_kind` and `intent` rather than running two
classifiers.

### Frozen AgentContext contract (C0)

WAVE 1.5 freezes the handoff between Lane B (session/context loading) and Lane C
(graph/runtime). Lane C must build against this contract rather than reaching
into `SessionStore` ad hoc.

```python
from typing import Literal, TypedDict

TurnKind = Literal[
    "data_question",
    "follow_up",
    "dispute_correction",
    "clarification",
    "prior_answer_meta",
    "smalltalk",
    "command",
    "out_of_scope",
]

PriorAnswerVerdictStatus = Literal["correct", "wrong", "incomplete"]


class PromptHistoryMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class SessionHistoryMessage(TypedDict, total=False):
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    metadata: dict


class PriorAnswerVerdict(TypedDict, total=False):
    status: PriorAnswerVerdictStatus
    referenced_message_id: int
    referenced_claim: str
    predicate_summary: str
    explanation: str
    tool_names: list[str]
    entity_ids: list[str]
    numbers: list[float]
    evidence_fingerprint_sha256: str


class AgentContext(TypedDict):
    session_id: str
    latest_user_message: str
    history_window: list[SessionHistoryMessage]
    prompt_history: list[PromptHistoryMessage]


def load_session_context(session_id: str, latest_user_message: str) -> AgentContext: ...
```

Contract notes:

- `history_window` is the bounded, chronological message window returned by
  `SessionStore.load_history_window()`. It may include assistant `metadata`
  because reconciliation may need stored evidence pointers or fingerprints, but
  Lane C must never inject this raw metadata into a model prompt.
- `prompt_history` is the prose-only projection returned by
  `SessionStore.load_prompt_history()`. It is the only history form that may be
  re-fed to the model.
- `latest_user_message` is passed separately even when it is also the newest
  entry in `history_window`; the graph should not recover it by indexing into
  the history list.
- `load_session_context()` owns the budget policy (`AI_CONTEXT_MESSAGE_LIMIT`,
  `AI_CONTEXT_HISTORY_CHAR_BUDGET`, `AI_CONTEXT_SINGLE_MESSAGE_CHAR_LIMIT`).
  Lane C consumes the bounded result; it does not decide its own history window.

`turn_kind` is now frozen to the following routing semantics:

- `data_question` — standalone data request; proceed through the data/tool path.
- `follow_up` — context-dependent refinement of a prior data turn; resolve to a
  standalone question before selecting tools.
- `dispute_correction` — user challenges a prior answer; route to
  reconciliation before final synthesis.
- `clarification` — assistant still lacks a safe referent or parameter after
  context resolution; stop with a targeted clarification.
- `prior_answer_meta` — ask about what the assistant or user said earlier;
  answer from session history without calling data tools unless the turn
  explicitly requests a re-check.
- `smalltalk` — greeting/chitchat handled on the tool-free path.
- `command` — chat control or non-domain command handled on the tool-free path.
- `out_of_scope` — genuine domain/data refusal after routing, not a pre-router
  shortcut.

`prior_answer_verdict` is frozen as the structured reconciliation payload:

- `status` — required verdict label: `correct`, `wrong`, or `incomplete`.
- `referenced_message_id` — assistant message under review when one is
  identifiable from session history.
- `referenced_claim` — concise natural-language claim being judged.
- `predicate_summary` — standalone restatement of the checked predicate or
  question.
- `explanation` — concise rationale for the verdict.
- `tool_names` — tools consulted during the re-check.
- `entity_ids` — stable identifiers surfaced by the verdict, such as plant,
  inverter, or anomaly ids.
- `numbers` — numeric claims that support the verdict and that replay may assert
  on without scraping prose.
- `evidence_fingerprint_sha256` — fingerprint of the evidence context used for
  the verdict when available.

Rules for this object:

- Emit it only for `dispute_correction` turns and related "was your previous
  answer right?" meta turns. Omit it for ordinary data answers.
- The assistant's free-form answer may paraphrase the result, but tests should
  bind to this object rather than to reconciliation wording.
- Lane D may keep schema-tolerant assertions temporarily, but Lane C should emit
  these exact top-level keys so replay, UI cards, and future audits all read the
  same payload.

### Graph shape

Use LangGraph for the agent runtime once dependencies and project constraints are
accepted:

```text
load_session_context
  -> classify_turn
       smalltalk/command  -> fast_path_answer        -> persist_turn
       meta/prior-answer  -> answer_from_history      -> persist_turn
       out_of_scope       -> refuse                   -> persist_turn
       data/follow-up/
       dispute            -> maybe_resolve_followup
                             -> select_tools
                             -> agent_reasoning
                             -> execute_tools
                             -> should_continue?
                                  yes -> agent_reasoning
                                  no  -> reconcile_or_synthesize
                             -> persist_turn
```

Two routing rules are load-bearing:

- The **local pattern fast-path runs before `classify_turn`** and before any
  model call: trivial greetings/smalltalk and `ambiguous_plant` short-circuit on
  a local match (today's `_local_fast_path`), preserving the "smalltalk
  short-circuits before the LLM/tools" requirement. `classify_turn` and its
  `{turn_kind, intent}` call only run for turns the local fast-path did not
  catch.
- The graph must have a **tool-free branch** (`answer_from_history`,
  `fast_path_answer`). Smalltalk, command/meta, and "what did you say earlier?"
  turns must never be forced through `execute_tools`. (`fast_path_answer` here is
  the local short-circuit above; `answer_from_history` is the model-backed
  meta/prior-answer path.)
- The `out_of_scope` refusal must live **inside** the data branch, downstream of
  `classify_turn` — never as a pre-`classify_turn` short-circuit. In the current
  code the refusal returns the moment `intent.out_of_scope is True`
  (`pipeline.py:222`), which is exactly what swallowed "So your initial answer
  was wrong." Dispute/correction turns must be routed before that guard runs.

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

0. Tool-defect prerequisite: land roadmap §2c (D3/X4/G4) and re-verify D3 live
   first. The reconciliation oracle's golden answer (anomaly ids 7 and 55 on two
   inverters) is only achievable once the combined type+cause filter returns the
   right subset. Skipping this makes every later reconciliation reconcile against
   wrong evidence.
1. Session-aware prompt path: load bounded prior messages before answering and
   pass them to intent/synthesis. No LangGraph yet. Verify D3 follow-up and
   dispute behavior improves. **History projection is part of this slice, not a
   later one:** the persisted assistant payload stores the full answer envelope
   (tool results, traces) in `metadata_json`. Following the remote-rover pattern
   (see "Session context & evidence strategy"), re-feed only the assistant's
   prose `content` for history messages — never the raw stored `metadata`
   payload — or you reintroduce raw rows into the prompt and break the graded
   "no raw CSV rows in the final LLM prompt" constraint. `resolved_question` is
   carried as separate agent state, not concatenated into the re-fed history.
2. Follow-up resolver node: turn "doublecheck for 4137001" into a standalone
   constrained question using prior turns.
3. Dispute/reconciliation node: handle "that was wrong" by comparing prior
   claims with current evidence instead of running the generic out-of-scope
   path.
4. LangGraph runtime skeleton: introduce a graph behind the existing API with
   the same tool registry and trace payloads.
5. Evidence persistence: store **full** tool evidence (tool_calls, results,
   trace, stop_reason, usage) on the assistant message `metadata` — this is what
   the per-message token/usage cards and replay already consume. Do **not**
   compact or summarize it for storage. Tag each evidence record with a
   dataset/config fingerprint so a later reconciliation turn can tell whether the
   stored evidence is still valid for the active dataset (the app supports live
   dataset switching). Reconciliation does not re-feed stored evidence into the
   prompt; it reads the fingerprint + stored verdict inputs and, when it needs
   numbers, **re-runs the relevant tool fresh** (rover's model). Pre-feature
   turns simply have no stored evidence and fall back to a fresh re-run.
6. Full replay suite: add multi-turn cases for follow-up, correction, prior
   answer inspection, and context-resolved ambiguity. Assert on the structured
   `prior_answer_verdict` (+ intent + tool chain + numerics), not on
   reconciliation prose.

## Testing gates (post-redesign)

These mirror the roadmap track and are restated here so the committed design is
self-sufficient:

- Unit + integration pass: tool unit tests, pipeline, server/session, CLI, and
  case-replay tests; fix or explicitly triage every regression.
- Single-turn CLI replay passes: first re-run the initial-task 15-question gate
  (`D1–D6`, `A1–A3`, `B1–B3`, `C1–C3`); then run the remaining 36 canonical
  behavioural cases from the 51-case catalog. The 2b historical 15-case replay
  subset is invalidated because the runtime changed.
- Multi-turn CLI replay pass: run the new multi-turn suite against the oracle.

## State-store and streaming constraints

- `SessionStore` (sqlite) stays the **canonical** conversation store. If a
  LangGraph checkpointer is introduced it is ephemeral/per-invocation; it must
  not become a second source of truth that can diverge from displayed history.
- The streaming contract must be preserved: `stream_chat` runs the answer in a
  daemon thread and emits `TraceEvent`s via `event_handler`
  (`server.py:583-597`). A graph runtime must re-emit per-node trace events
  through the same handler, or the UI activity panel regresses. This is an
  integration cost, not a free consequence of "API contracts stay stable."

## Session context & evidence strategy (from remote-rover)

These were open questions; resolved by reading rover's `chat_service.py` /
`session_store.py`, which already solve them and are the proven reference.

**Context budget — recency window, not "send everything" (resolved).** Rover
uses a three-tier bound and we adopt the same shape:

1. **Count cap** — load at most the last N messages
   (`AI_CONTEXT_MESSAGE_LIMIT = 40` in rover).
2. **Total budget** — walk newest→oldest, keep messages until a total budget is
   hit, drop oldest first (`AI_CONTEXT_HISTORY_CHAR_BUDGET = 16000`).
3. **Per-message cap** — truncate a single oversized message with an explicit
   `[earlier message truncated for context budget]` marker rather than dropping
   it (`AI_CONTEXT_SINGLE_MESSAGE_CHAR_LIMIT = 4000`); always keep the most
   recent message.

Rationale: unbounded "whole session" history blows the context window, raises
cost, and drags stale turns into answers. Recency-bounded with graceful
truncation is the quality choice. Start with rover's numbers as a single global
default expressed as named constants; promote to per-provider budgets later only
if a provider's window/cost demands it (named constants make this a one-line
change, not a redesign).

**Evidence — store full, re-feed only prose (resolved).** Rover stores the full
tool evidence (tool_calls, trace, stop_reason, usage) on the assistant message
`meta`, but `_to_langchain_messages` re-feeds only each message's prose
`content`. Raw tool JSON is never re-injected into a later prompt; the current
turn's tools are run fresh and injected as system context for that turn only.

This dissolves the "full vs compact vs summarized" question:

- **Full** evidence is persisted (powers the per-message token/usage cards,
  replay, and audit) — nothing is thrown away.
- **Prompts stay clean** — only the assistant's natural-language answer is
  carried forward as history, so the "no raw rows in prompt" rule holds for free.
- **Reconciliation re-runs tools** rather than re-reading stale stored rows, so a
  recheck is always against live data for the active dataset.

So the user keeps full visibility on the cards *and* the prompt stays clean —
both, not a trade-off. No user-facing compaction toggle is needed.

## Resolved decisions (were open questions)

**Classification is always-on, but only *after* the local fast-path
(resolved).** Ordering, top to bottom:

1. **Local fast-path stays first** — trivial greetings/smalltalk and the
   `ambiguous_plant` case short-circuit on a local pattern match with **no model
   call**, exactly as today (`pipeline.py` `_local_fast_path`). This preserves
   the requirement "Greetings/smalltalk short-circuit before the LLM/tools
   (fast-path)." The new graph does not move smalltalk behind an LLM call.
2. **For every remaining turn, one classification call runs** and returns
   `{turn_kind, intent}`. It is a dedicated, explicit, inspectable step (emitted
   in trace metadata) — *not* inference folded into the synthesis prompt — so it
   satisfies "explicit intent classification before querying data, not silently
   inferred inside one prompt." `turn_kind` routes; the A/B/C `intent` is still
   produced and logged for data turns.

   This is broader than the literal A/B/C spec but **covers it by superset**
   (see requirements → "Coverage principle"): data turns still get explicit,
   inspectable A/B/C classification before any tool runs; non-data turns
   (dispute, meta) gain correct routing the narrow spec never addressed. No
   contradiction with the task — a strict improvement.

**Expose `resolved_question` and evidence in the activity panel (resolved:
yes).** Show the resolved/standalone question and the tool calls/evidence used
in the existing agent activity panel. This is additive template/demo value, not
graded UI polish, so it does not conflict with the "no production UI polish
required" non-goal; it directly serves the "presentable template / debrief
walkthrough" goal. Lands in Integration (I5).

**Context budget: one global default now (resolved).** Use rover's three-tier
numbers as named constants; promote to per-provider budgets only when a second
provider with a materially different window/price is added. Restated here so it
is no longer carried as open.

## Open questions

None blocking. Future revisit (tracked, not committed): per-provider context
budgets if/when a second provider demands them; promoting the static schema card
to a runtime engine only if a deeper dataset ever needs it (ADR 0003).
