# Research — attributes of a modern AI-agent implementation

> **Authored:** 2026-07-25 22:36 (+04) by Claude Opus 5 (`claude-opus-5`),
> reasoning effort: medium, via Claude Code. Attribution recovered from the
> session transcript on 2026-07-25 23:2x, not self-reported by the original run.
>
> **Scope:** general reference, project-independent. What distinguishes a
> production-grade agent implementation from a demo, expressed as attributes
> that can be checked. Contains no claims about this project — for the audit of
> this codebase see `docs/reviews/agent-implementation-audit.md`.
>
> **Status:** research/reference. Not a decision record, not a requirement, not
> a plan. Nothing here is committed to. Adopting any attribute is a separate
> decision that belongs in `docs/adr/` or `roadmap.md`.

---

## The one-paragraph version

An agent is a loop that lets a model choose actions until a goal is met.
Almost everything that separates a good implementation from a bad one is
**not** in the loop — it is in the quality of the tools, the discipline of what
enters the context window, the ability to recover when a step fails, and the
existence of a measurement rig that tells you whether a change helped. Teams
consistently over-invest in orchestration frameworks and under-invest in
evaluation and tool design, which is the inverse of what determines outcomes.

---

## A. Evaluation and measurement

The highest-leverage attribute, and the one most often absent. Without it every
other improvement is a guess.

### A1. An independent oracle

Expected answers must be derived **independently of the agent's own machinery**
— computed from source data by separate code, or human-labeled. An oracle built
from the agent's own tools tests self-consistency, not correctness, and moves
whenever the tools move.

### A2. Trajectory evaluation, not just final-answer matching

Final-string comparison cannot distinguish "right answer for the right reason"
from "right answer by luck". Assert on the path:

- which tools were called, and in what order
- the *arguments* they were called with
- specific fields present in tool results
- iteration count (a correct answer that took 6 turns is a defect)

An agent that reaches the right answer via the wrong trajectory will fail the
next, slightly different question. Trajectory assertions catch that; string
matching does not.

### A3. Regression gates in CI

Eval runs on every change, with a pass threshold, and blocks merge. Agent
quality regresses silently and invisibly — prompt edits have non-local effects.

### A4. Separating harness-fitting from capability

Every hardcoded special case, answer override, or question-specific prompt
injection inflates eval scores **without** improving the agent. A mature setup
can report the score with such compensations disabled, so the true model-driven
baseline is visible. Otherwise the eval measures the scaffolding, and the number
rises while generalization falls.

### A5. Cost and latency as first-class eval metrics

Report tokens, cost, and wall-clock per case alongside correctness. A change
that raises accuracy 2% and cost 300% is usually a bad trade, and is invisible
if only accuracy is tracked.

---

## B. Tool design

Tools, not prompts, are the agent's real interface to the world. Tool quality
dominates model quality in most failure analyses.

### B1. Structured results, never prose

Tools return typed dicts. Prose forces the model to re-parse, hallucinate
around ambiguity, and re-derive numbers it should have been handed.

### B2. Bounded output

Every tool caps rows/bytes returned, with an explicit limit parameter and a
hard maximum. Unbounded tool output is the most common cause of context
exhaustion mid-loop.

### B3. Errors as data, never exceptions

A failing tool returns `{ok: false, error: ...}` into the conversation. An
exception that escapes kills the turn; an error *in the transcript* is
something the model can read, understand, and route around. Error messages
should be actionable by a model — say what was wrong and what valid input looks
like.

### B4. Argument validation at the boundary

Validate against the real handler signature and reject unknown arguments with a
clear message. Models routinely invent plausible parameters.

### B5. Few, well-named, non-overlapping tools

Overlapping tools ("get_data" vs "query_data") produce systematic
mis-selection. Descriptions are prompt surface — they deserve prompt-level care.
Consolidate rather than proliferate.

### B6. Idempotency and side-effect declaration

Read-only tools are safe to retry, cache, and parallelize. Mutating tools must
be marked, and generally need confirmation and idempotency keys. The safety
machinery an agent needs is proportional to what its tools can actually do.

---

## C. Context engineering

The context window is the agent's working memory and its scarcest resource.
Every token should be there deliberately.

### C1. Budgets enforced where growth happens

Budgeting conversation history but not tool results is a common half-measure —
tool output is usually what actually grows. Enforce caps on the accumulating
message list *inside* the loop, not only on inputs to it.

### C2. Truncation that preserves the informative end

When trimming, keep the part that carries the conclusion (usually the tail) and
mark the elision explicitly so the model knows information was removed rather
than inferring it never existed.

### C3. Compaction for long horizons

Beyond a threshold, summarize completed work and drop raw intermediates, rather
than truncating blindly. Preserve decisions and results; discard the reasoning
that produced them.

### C4. Stable prefixes for cache economics

Order context most-stable-first (system prompt → tool schemas → static
reference → history → current turn). Providers cache prefixes; any early
variation invalidates everything after it. A per-request timestamp near the top
of a system prompt can silently destroy the entire cache benefit.

### C5. Just-in-time retrieval over preloading

Load references on demand rather than stuffing everything in upfront — but
weigh this against C4, since dynamic loading fragments the cacheable prefix.
This is a genuine tension, not a solved question.

### C6. Curated tool exposure

Bind only plausibly relevant tools per turn. Large tool sets measurably degrade
selection accuracy. The critical constraint: narrowing must remain **revisable**
mid-loop, or a wrong early guess becomes an unrecoverable failure.

---

## D. Control flow and recovery

### D1. A genuinely cyclic loop

The defining property of an agent. If the graph is a DAG that calls a model
once and formats the output, it is a pipeline with a model in it. The loop must
be able to return to earlier decisions.

### D2. Decisions must be revisable

Any decision made *before* the loop — tool selection, refusal, routing — is
unrecoverable if the loop cannot revisit it. Pre-loop classification should
produce a **prior**, not a gate. Refusals in particular should be a considered
outcome after evidence gathering, not a pre-filter.

### D3. Explicit verification before answering

A checkpoint that asks "does the evidence actually answer the question?" with
an edge back into action. This is the difference between an agent that fails
gracefully and one that confidently answers from empty results.

### D4. Bounded iteration with informative exhaustion

A hard cap, plus a distinct terminal state when hit, plus telemetry on how
often. Frequent limit-hits indicate a tool or prompt defect, not a cap that is
too low.

### D5. Progress detection

Detect repeated identical tool calls and oscillation, and break out. Without it
agents burn their entire budget re-calling the same failing tool.

### D6. State semantics chosen deliberately

Last-write-wins channels are fine for a DAG and wrong for a cyclic graph, where
accumulation across revisits needs explicit reducers. Retrofitting cycles onto
last-write-wins state is a common source of subtle bugs.

---

## E. Reliability

The least glamorous section and usually the difference between "works in demo"
and "works".

### E1. Retries with exponential backoff and jitter

Model APIs return 429s and 5xxs routinely. An agent without retry logic fails
turns for reasons entirely unrelated to its design. Jitter matters — synchronized
retries cause thundering herds.

### E2. Retryable vs terminal classification

Retry 429/500/502/503/504 and timeouts. Never retry 400/401/403 or content
violations — that burns budget on a guaranteed failure.

### E3. Timeouts at every level

Per model call, per tool call, per turn. A hung provider connection with no
timeout hangs the request indefinitely and holds resources.

### E4. Degradation ladders

Each failure has a defined fallback: repair a malformed response, fall back to
a safe default, return a partial answer with an explicit caveat. Never raise a
stack trace at a user.

### E5. Cancellation

Client disconnect aborts in-flight model and tool calls. Without it, abandoned
requests keep spending money.

### E6. Idempotency for retried side effects

Retrying a mutating call must not double-apply it.

---

## F. Observability

### F1. Correlation IDs

A trace/turn/session ID on every event, propagated to tool calls and provider
requests. Without it, production debugging is guesswork.

### F2. Persisted traces

Traces stored beyond the request, queryable offline. Real failure analysis
happens after the fact and in aggregate; per-request in-memory events cannot
support it.

### F3. Per-stage attribution

Tokens, cost, and latency broken down by phase (classification vs synthesis vs
per-tool), not just a turn total. Aggregates hide the expensive stage.

### F4. Cache effectiveness metrics

Cache reads vs writes vs hit rate. Prompt caching is easy to configure and easy
to silently break; without measurement nobody notices it stopped working.

### F5. Streaming progress

Emit structured events (step started, tool called, result received) rather than
only tokens, so a UI can show real progress and a human can intervene.

### F6. Standard instrumentation

OpenTelemetry spans, or an LLM-observability platform. Custom event formats do
not integrate with existing production tooling.

---

## G. Cost control

### G1. Prompt caching, correctly applied

Cache breakpoints on the stable prefix — system prompt and tool schemas.
Typically the single largest cost reduction available in a multi-turn agent.

### G2. Enforced budgets, not just accounting

Measuring tokens is not controlling them. Hard caps per turn and per session,
with defined behavior on breach.

### G3. Model tiering

Cheap models for classification and routing; expensive models for synthesis.
Routing every step to the most capable model is the default and is usually
wrong.

### G4. Result caching

Cache deterministic tool results within and across turns. Agents re-call the
same tool constantly, especially after a retry or a re-plan.

### G5. Parallel execution

Independent tool calls in the same step fan out concurrently. This is latency,
not token cost, but it is often the largest wall-clock win available and is
usually a small change.

---

## H. Engineering discipline

### H1. Single source of truth for types and state

Duplicated enums or state shapes drift. One definition, imported everywhere.

### H2. Behavior from prompts and tools, not per-case branches

The most important structural test: **when a new question shape fails, does
fixing it require new Python?** If yes, the system does not generalize — it is a
lookup table with a model attached. Per-question special cases are legitimate as
a stopgap, but each one should be tracked as debt with a plan to fold it into a
tool contract or prompt, because they accumulate silently and inflate evals
(see A4).

### H3. Structured output over parsing prose

Use native structured-output or tool-call schema enforcement rather than
regex-extracting JSON from prose and repairing it. The repair round-trip is
pure cost for a solved problem.

### H4. Determinism where determinism is possible

Do not ask a model to do arithmetic, filtering, or aggregation a tool can do
exactly. Models should decide *what* to compute; code should compute it.

### H5. Prompts as versioned artifacts

Prompts are load-bearing logic. Version them, diff them, tie eval results to
prompt versions.

---

## I. Safety, proportional to blast radius

Scale this section to what the tools can actually do. Read-only tools over
trusted internal data need very little; tools that write, spend, or send need
all of it.

### I1. Treat tool output as untrusted input

Any content originating outside the system (web, user uploads, third-party
APIs) can carry injection. Mark provenance and never let retrieved content be
interpreted as instructions.

### I2. Least privilege

Scoped credentials per tool. The agent should not hold broader access than its
task requires.

### I3. Human approval for consequential actions

Irreversible or outward-facing actions pause for confirmation, with enough
context shown to make the decision meaningful.

### I4. Sandboxing for code execution

If the agent runs code, it runs isolated with resource limits.

---

## Checklist

| # | Attribute | Category |
|---|---|---|
| A1 | Independent oracle | Evaluation |
| A2 | Trajectory assertions | Evaluation |
| A3 | CI regression gates | Evaluation |
| A4 | Harness-fitting isolated from capability | Evaluation |
| A5 | Cost/latency as eval metrics | Evaluation |
| B1 | Structured tool results | Tools |
| B2 | Bounded tool output | Tools |
| B3 | Errors as data | Tools |
| B4 | Argument validation | Tools |
| B5 | Few, non-overlapping tools | Tools |
| B6 | Side-effect declaration | Tools |
| C1 | Budgets where growth happens | Context |
| C2 | Informative truncation | Context |
| C3 | Compaction | Context |
| C4 | Stable cacheable prefix | Context |
| C5 | Just-in-time retrieval | Context |
| C6 | Curated, revisable tool exposure | Context |
| D1 | Cyclic loop | Control flow |
| D2 | Revisable decisions | Control flow |
| D3 | Verification before answering | Control flow |
| D4 | Bounded iteration | Control flow |
| D5 | Progress detection | Control flow |
| D6 | Deliberate state semantics | Control flow |
| E1 | Retry with backoff + jitter | Reliability |
| E2 | Retryable vs terminal | Reliability |
| E3 | Timeouts | Reliability |
| E4 | Degradation ladders | Reliability |
| E5 | Cancellation | Reliability |
| E6 | Idempotency | Reliability |
| F1 | Correlation IDs | Observability |
| F2 | Persisted traces | Observability |
| F3 | Per-stage attribution | Observability |
| F4 | Cache metrics | Observability |
| F5 | Streaming progress events | Observability |
| F6 | Standard instrumentation | Observability |
| G1 | Prompt caching | Cost |
| G2 | Enforced budgets | Cost |
| G3 | Model tiering | Cost |
| G4 | Result caching | Cost |
| G5 | Parallel tool execution | Cost |
| H1 | Single source of truth | Discipline |
| H2 | No per-case branches | Discipline |
| H3 | Structured output | Discipline |
| H4 | Determinism where possible | Discipline |
| H5 | Versioned prompts | Discipline |
| I1 | Tool output untrusted | Safety |
| I2 | Least privilege | Safety |
| I3 | Human approval | Safety |
| I4 | Sandboxing | Safety |

---

## Priority when starting from nothing

1. **A1–A3** — evaluation first. Everything else is unmeasurable without it.
2. **B1–B4** — tool quality. Larger effect than model choice.
3. **E1–E4** — reliability. Cheap, and the difference between working and not.
4. **D1–D2** — the actual loop, cyclic and revisable.
5. **C1, C4, G1** — context discipline and caching.
6. **F1–F3** — observability, before scale rather than after.
7. Everything else as scale and blast radius demand.

The common failure is starting at 4 (framework and graph topology, the visible
part) and never reaching 1.
