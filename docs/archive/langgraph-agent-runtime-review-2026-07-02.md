# LangGraph Agent Runtime Review - 2026-07-02

## Scope

This review was triggered by the `Replay G6` chat transcript and the follow-up
architecture concern: the assistant appeared to lose conversation context across
ordinary second and third chat turns.

The review covers the current session-aware LangGraph runtime and ReAct loop:

- `app/ai/agent_graph.py`
- `app/ai/agent_loop.py`
- `app/pipeline.py`
- `app/ai/session_store.py`
- `app/ai/turn_router.py`
- related tests and accepted design docs

This is a review document, not a planning capture. It records code-grounded
findings and recommends what to triage next.

## Executive summary

The current implementation is not yet the modern continuous, session-aware
LangGraph agent described by ADR 0004 and
`docs/design/full-react-agent-redesign.md`.

It does load bounded history and passes prose history into the synthesis model,
but the LangGraph graph is mostly a one-pass wrapper around the older
single-turn pipeline:

```text
load_session_context
  -> route_local
  -> classify_intent
  -> tool_free_reply | out_of_scope_reply | run_tool_loop
  -> optional reconcile_prior_answer
  -> END
```

The only iterative ReAct behavior still lives inside `run_agent_loop()`, and
that loop starts only after the pipeline has already classified the turn,
selected a tool subset, possibly rewritten the question, and possibly refused.
That ordering makes context use brittle. It explains why a first question can
work while a later conversational turn regresses: the graph has session history,
but session history is not first-class control state for every normal turn.

The narrow G6 fix can make that replay pass, but it does not resolve the
architecture issue. The correct next step is to triage this review and replace
the turn-specific follow-up heuristics with a session-aware planning/routing
node that all non-command turns pass through before tool selection or refusal.

## Findings

### F1 - High - The LangGraph runtime is an acyclic wrapper, not the agent loop

Evidence:

- `app/ai/agent_graph.py` defines a `StateGraph`, but `compile_runtime_graph()`
  wires a one-pass flow and ends after `run_tool_loop` or one optional
  reconciliation node.
- `app/ai/agent_loop.py` contains the actual iterative model/tool loop
  (`MAX_TOOL_ITERATIONS = 6`), but it is called from `pipeline.py` only after
  routing, classification, and tool selection have already completed.
- `docs/adr/0004-proposed-full-react-langgraph-agent.md` accepts LangGraph as
  the target runtime for state and control flow, not merely as a wrapper around
  the old pipeline.

Why this matters:

LangGraph is not currently owning the core agent loop decisions. It does not
iterate over plan, tool selection, execution, synthesis, critique, and stop
conditions as graph state. It delegates the only true loop to the old
LangChain-style function after important decisions have already been made.

Impact:

The implementation can pass targeted tests while still behaving unlike a
continuous conversational agent. Each new behavior requires another branch or
heuristic instead of improving the general agent state machine.

Recommended triage:

Classify as `must_fix_now` if the project goal is a reusable modern agent
template. This is the central architecture mismatch.

### F2 - High - Tool selection happens before the smart ReAct loop can recover

Evidence:

- `pipeline.py` runs `IntentService.parse(...)` in `classify_intent_node`.
- `_select_tool_names(...)` then binds a gated subset before calling
  `run_agent_loop(...)`.
- If the classifier returns an empty or wrong metric, the synthesis model either
  receives the wrong tools or a fallback minimal subset.

Why this matters:

The synthesis model is the strongest reasoning step, but it can only call the
tools selected by an earlier classifier. If that classifier misunderstood a
contextual turn, the later ReAct loop cannot discover the missing tool.

This is particularly risky for conversational turns because the classifier gets
only a summarized history context, not a structured session state.

Impact:

Questions can fail for orchestration reasons while appearing to be tool or
model-quality failures. The G6 transcript is one example: the system had a
`performance_ratio` tool path available, but routing and prompt/tool semantics
were too brittle to use it consistently.

Recommended triage:

Classify as `must_fix_now`. Tool gating should become a policy the graph can
revise or safely widen, not an irreversible pre-loop decision.

### F3 - High - Out-of-scope refusal is still too early in the control flow

Evidence:

- `pipeline.py` has an `out_of_scope_reply_node`.
- `agent_graph.py` routes to that node when `turn_kind == "out_of_scope"` and
  `intent.out_of_scope` is true.
- ADR 0004 explicitly warns that `out_of_scope` must live inside the data branch
  after turn routing, because the old implementation swallowed correction turns.

Why this matters:

A user message can look out-of-scope as a standalone text string while being
in-scope in the conversation. Examples:

- "yes please"
- "re-check using the closest available window"
- "that was wrong"
- "what about this plant?"

If refusal happens before a session-aware interpretation step, the assistant
will appear to forget context even though messages were persisted.

Impact:

This creates exactly the user-visible failure mode: later turns are handled as
standalone prompts and receive generic dataset refusals.

Recommended triage:

Classify as `must_fix_now`. Refusal should be a final graph outcome after
contextual interpretation, not a classifier shortcut.

### F4 - High - Conversation state is loaded, but it is not first-class graph state

Evidence:

- `SessionStore.load_history_window()` provides bounded chronological history.
- `SessionStore.load_prompt_history()` strips metadata and returns prose-only
  messages.
- `run_agent_loop()` appends `prompt_history` before the current user prompt.
- However, `pipeline.py` uses `summarize_prompt_history(..., limit=4)` for
  intent classification, then independently passes full prompt history to
  synthesis after routing decisions are already made.

Why this matters:

The design says every non-command turn should be evaluated with bounded recent
conversation history. The current code partly does that, but not at the point
where the highest-risk decisions are made:

- turn interpretation
- out-of-scope vs in-scope
- tool policy
- whether to answer from history or re-run tools
- whether to ask a clarification

Impact:

History can be present in the final model prompt but absent from the control
decision that determines whether the final model prompt runs at all.

Recommended triage:

Classify as `must_fix_now`. Introduce one session-aware planner/router node that
receives bounded history and produces the normalized request plus routing
decision for all non-command turns.

### F5 - Medium - `follow_up` is an implementation smell in its current form

Evidence:

- `turn_router.py` uses local phrase patterns to infer `follow_up`.
- `agent_graph.py` has `resolve_follow_up_question()` with hand-coded cases for
  ambiguous plant questions, "what about", pronouns, affirmative replies, and
  "re-check" wording.
- `pipeline.py` then has `_backfill_follow_up_intent(...)` to patch metrics and
  clear false `out_of_scope` in selected cases.

Why this matters:

Follow-up should not be a special quality tier. A second, third, or fourth
message should go through the same intelligent session-aware agent path as a
first message, with history available and relevant. The current special casing
means behavior depends on whether the user's wording matches a local pattern.

Impact:

The system will keep producing brittle regressions:

- "yes please" works only if listed.
- "please check that window" may fail unless listed.
- a semantically equivalent phrase can fall through to standalone behavior.

Recommended triage:

Classify as `must_fix_now` if the goal is agent quality rather than replay
patching. Replace phrase-specific follow-up resolution with a model-backed
session interpretation step plus deterministic safety checks for ambiguous
references.

### F6 - Medium - Tests validate patched branches more than general agent behavior

Evidence:

- `tests/test_agent_loop.py` verifies that prompt history is threaded into
  `run_agent_loop()`.
- `tests/test_phase1_pipeline_core.py` contains targeted tests for resolved
  ambiguity, prior-answer recall, metric backfills, and G6-style recheck.
- These tests are useful, but they mostly assert that specific branch logic is
  called, such as `resolve_follow_up` appearing in `graph_nodes`.

Why this matters:

The tests can pass while the architecture remains brittle. They prove specific
phrases route correctly, not that arbitrary conversational turns are interpreted
with session state before refusal/tool selection.

Impact:

Replay quality may improve case-by-case without increasing confidence in the
agent's general multi-turn behavior.

Recommended triage:

Classify as `should_fix_next`. Add adversarial multi-turn tests where the same
intent is expressed in several different phrasings and the graph must make the
same high-level decision without phrase-specific patches.

### F7 - Medium - The current graph is recompiled per request

Evidence:

- `pipeline.py` builds `runtime = compile_runtime_graph(...)` inside
  `Pipeline.answer(...)`.

Why this matters:

This is probably not the quality failure, but it is a sign that the graph is
being treated as a request-local wrapper rather than a stable runtime with
well-defined state transitions. It also makes later checkpointer or durable
state integration harder to reason about.

Impact:

Potential runtime overhead and weaker architectural boundaries.

Recommended triage:

Classify as `defer` unless profiling shows cost. Fix naturally when the graph is
refactored into a proper runtime component.

## Root cause

The implementation stopped halfway between two architectures:

1. The old architecture: explicit intent classifier -> gated tools -> hand-rolled
   ReAct loop.
2. The accepted target: session-aware LangGraph runtime owns conversation state,
   routing, loop control, reconciliation, stop conditions, and tool policy.

The code now has both, but the old pipeline still owns the decisive choices.
LangGraph mostly records and routes those choices.

That is why adding history did not fully solve context loss. History was loaded,
but it was not made the primary input to the graph's routing and tool policy.

## Design-doc conflict

The current code conflicts with the accepted direction in two durable docs:

- ADR 0004 says LangGraph should own state and control flow for the
  session-aware agent runtime.
- `docs/design/full-react-agent-redesign.md` says every non-command chat turn is
  evaluated with bounded recent conversation history and relevant prior evidence.

The implementation partially satisfies these documents:

- bounded history exists;
- prompt history is prose-only;
- tool traces and evidence metadata exist;
- a `StateGraph` exists;
- multi-turn tests exist.

But it does not yet satisfy the central quality property:

> A normal later chat turn should not require a special "follow-up" patch to be
> interpreted with context.

## Recommended direction

Do not keep adding phrase-level follow-up patches.

Recommended target:

```text
load_session_context
  -> local_command_or_smalltalk_fast_path?
  -> interpret_session_turn
       input: latest user message + bounded prompt history + safe evidence summary
       output:
         - turn_action: answer_from_history | ask_clarification | use_tools | refuse
         - resolved_request
         - intent
         - tool_policy
         - refusal_reason, if any
  -> if use_tools:
       run graph-owned ReAct/tool loop
       allow safe tool-policy widening or retry on tool mismatch
  -> reconcile_or_synthesize
  -> persist_turn
```

Key properties:

- There is no privileged "follow-up quality path"; all non-command turns are
  session-aware.
- `out_of_scope` is not accepted from a standalone classifier until the
  session-aware interpretation step has considered history.
- Tool gating becomes adjustable policy, not a hard pre-loop gate.
- The graph state contains the normalized request, selected tools, executed
  tools, evidence, answer, and stop reason.
- The activity panel can show the resolved request and the graph decision,
  making failures inspectable.

## Suggested review triage

Suggested `/review-triage` classification:

| Finding | Suggested classification |
|---|---|
| F1 - Graph is acyclic wrapper, not agent loop | `must_fix_now` |
| F2 - Tool selection before ReAct recovery | `must_fix_now` |
| F3 - Early out-of-scope refusal | `must_fix_now` |
| F4 - History not first-class control state | `must_fix_now` |
| F5 - Follow-up branch brittleness | `must_fix_now` |
| F6 - Tests validate branches, not general behavior | `should_fix_next` |
| F7 - Graph recompiled per request | `defer` |

## Proposed next action

Run `/review-triage` on this review before changing code.

If the `must_fix_now` findings are accepted, the next implementation should be
one atomic vertical slice:

- add a session-aware `interpret_session_turn` graph node;
- route all non-command, non-smalltalk turns through it;
- delay refusal and tool selection until after that node;
- keep existing `run_agent_loop()` initially, but call it from the new state;
- add multi-turn tests that verify equivalent second-turn phrasings produce the
  same graph decision without phrase-specific routing.

After that lands and is verified, use `/planning-capture` to update durable
design/roadmap docs. Do not update ADR/design first unless the team accepts this
review's triage outcome.

## Non-goals for this review

- This review does not propose changing the CSV data tools or schema-card
  relationship model.
- This review does not require adding a LangGraph checkpointer immediately.
  `SessionStore` remains the canonical conversation store.
- This review does not argue for binding all tools by default. It argues that
  gating should be recoverable or adjustable by the session-aware graph.
- This review does not require rewriting the UI, except to preserve and expose
  trace events for graph decisions.
