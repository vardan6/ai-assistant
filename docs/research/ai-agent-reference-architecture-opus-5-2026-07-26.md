# AI agents — reference architecture

> **Merged:** 2026-07-26 by Claude Opus 5 (`claude-opus-5`), via Claude Code.
> Reasoning effort not exposed to the agent; recover from the session transcript
> if it matters.
> **Research date of underlying material:** 2026-07-25.
> **Status:** Research and reference. Not a decision, requirement, or plan.
> Adopting anything here is a separate decision belonging in `docs/adr/` or
> `roadmap.md`.

## What this document is

The settled layer — what a production-grade agent runtime looks like when the
sources agree. It covers the loop, context and memory, tools, control flow,
reliability, cost, observability, safety, and evaluation.

**It carries no numbers and no external links.** Every measured claim cites
`ai-agent-evidence-base-opus-5-2026-07-26.md` as `[EB §n]`. If you want to check
a figure or follow a source, go there.

| Companion | Read it for |
|---|---|
| `ai-agent-evidence-base-opus-5-2026-07-26.md` | The numbers and every source |
| `ai-agent-platform-feature-surface-opus-5-2026-07-26.md` | MCP, skills, subagents, hooks, GUI — the extension points |
| `ai-agent-hierarchical-decomposition-opus-5-2026-07-26.md` | Splitting a problem into sub-goals — a live design question, not settled |

§13 records where the source documents genuinely disagreed. Those are not
resolved here; they are marked so you can decide with the disagreement visible.

### Provenance

| Source document (now in `docs/archive/`) | Model | Effort | Contributed |
|---|---|---|---|
| `ai-agent-architecture-attributes-gpt-5-6-2026-07-25.md` | GPT-5.6 | low | §1–§4, §6–§11, §12 blueprint |
| `ai-agent-implementation-attributes-opus-5-2026-07-25.md` | Claude Opus 5 | medium | §14 checklist, §5, §7, §8, §9, §10 |
| `ai-agent-dynamic-context-loop-platform-perspectives-gpt-5-6-2026-07-25.md` | GPT-5.6 | low | §3 projections, §4 constrained graph, §5 layers |
| `ai-agent-dynamic-context-smart-graph-feature-surface-opus-5-2026-07-25.md` | Claude Opus 5 | medium | §3 four-region layout, §4 taxonomy, §6 routing |
| `ai-agent-harness-benchmarks-context-economics-opus-5-2026-07-25.md` | Claude Opus 5 | medium | Evidence anchors throughout |

---

## §0 The one-paragraph version

An agent is a loop that lets a model choose actions until a goal is met. Almost
everything that separates a good implementation from a bad one is **not** in the
loop — it is in the quality of the tools, the discipline of what enters the
context window, the ability to recover when a step fails, and the existence of a
measurement rig that tells you whether a change helped. Teams consistently
over-invest in orchestration frameworks and under-invest in evaluation and tool
design, which is the inverse of what determines outcomes. The one published
source-level teardown of a production coding agent reaches the same conclusion
structurally: the core is a simple while-loop, and most of the code is the
systems around it `[EB §8.1]`.

The central design principle:

> Keep the world outside the model, keep an accurate working set inside it, and
> give the model cheap ways to inspect the world whenever necessary.

Large context remains useful as headroom and for genuinely global reasoning. It
should not become the agent's database, filesystem, event log, or workflow
engine.

---

## §1 The shape of the runtime

The recommended default is a **durable, stateful, mostly single-agent runtime**:
a strong reasoning model as controller, a simple observe–decide–act–verify loop,
deterministic code around predictable operations, tools and knowledge loaded only
when needed, and durable external state behind a small curated working context.

```text
User / trigger
      │
      ▼
┌──────────────────────────────┐
│ Intent + risk + task router  │
└──────────────┬───────────────┘
               ▼
┌────────────────────────────────────────┐
│ Durable task state                     │
│ goal, constraints, plan, progress,     │
│ decisions, artifacts, side effects     │
└──────────────┬─────────────────────────┘
               ▼
┌────────────────────────────────────────┐
│ Context compiler                       │
│ instructions + current state + recent  │
│ events + retrieved evidence + tools    │
└──────────────┬─────────────────────────┘
               ▼
┌────────────────────────────────────────┐
│ Reasoning agent                        │
│ decide → act → observe → verify        │
└──────┬─────────────┬─────────────┬─────┘
       ▼             ▼             ▼
 Tool discovery   Sandboxed     Knowledge /
 and APIs         execution     memory search
       │             │             │
       └─────────────┴─────────────┘
                     ▼
             Typed observations
                     ▼
┌────────────────────────────────────────┐
│ Policy and verification layer          │
│ tests, assertions, approvals, budgets  │
└──────────────┬─────────────────────────┘
               ├── success ─────────────► final result
               ├── recoverable failure ─► loop
               ├── missing authority ───► user
               └── long wait ───────────► checkpoint / pause
```

**The graph should primarily represent durable state transitions.** It should not
force every reasoning step through a permanent collection of specialized agents.

### Essential qualities

| Quality | Best implementation |
|---|---|
| Goal fidelity | Explicit goal, constraints, acceptance criteria, and definition of done held **outside** the transcript |
| Situational awareness | Inspect the actual environment before acting; never rely solely on remembered descriptions |
| Autonomy | Continue through normal, reversible work without constant approval |
| Restraint | Ask when authority, intent, credentials, or an irreversible choice is genuinely missing |
| Tool competence | Narrow, typed, well-documented tools with unambiguous names and failure semantics |
| Recoverability | Checkpoint after meaningful state transitions; resume without repeating committed side effects |
| Verification | Test or inspect the resulting environment rather than reviewing generated text |
| Context discipline | Assemble a fresh working context for each inference instead of replaying everything |
| Evidence discipline | Preserve sources, tool results, file locations, versions, timestamps, uncertainty |
| Efficiency | Minimize unnecessary model turns, output tokens, tool schemas, model-visible intermediate data |
| Adaptability | Select models, reasoning depth, tools, and verification effort by difficulty and risk |
| Observability | Trace model turns, retrieval, tool calls, cost, latency, failures, approvals, state changes |
| Security | Treat retrieved content and tool output as untrusted data; contain the agent's capabilities |

### §1.1 If the topology is dynamic, constrain it

The best graph is neither a permanently fixed workflow nor an unconstrained graph
invented by an LLM. The middle position — and the one §13 argues for — is a
**constrained dynamic graph**: the model chooses strategy and topology; the
runtime owns operational correctness, permissions, scheduling, persistence, and
budgets.

```text
LLM proposes strategy and typed tasks
             ▼
Runtime validates the proposed graph
             ▼
Deterministic scheduler executes ready tasks
             ▼
Workers return structured results
             ▼
Controller receives progress and exceptions
             ▼
Controller revises, expands, or terminates the graph
```

An **unconstrained** generated graph can reference nonexistent capabilities,
create cycles or unresolved dependencies, decompose excessively, spend more
coordinating than executing, duplicate tasks, route sensitive data incorrectly,
invoke overly powerful agents, declare completion without verification, and
become impossible to replay or debug.

The fix is that the controller emits a **typed intermediate representation** the
runtime can check, rather than free-form instructions:

```yaml
strategy:
  objective: Repair the authentication regression
  success_conditions:
    - Affected test passes
    - Existing authentication suite passes

tasks:
  - id: investigate
    capability: code.investigate      # must exist in the registry
    context_profile: repository_analysis
    model_profile: balanced
    inputs: { question: Locate the regression and demonstrate its cause }
    depends_on: []
  - id: implement
    capability: code.modify
    context_profile: local_implementation
    model_profile: frontier
    depends_on: [investigate]
  - id: verify
    capability: code.verify
    context_profile: verification
    model_profile: fast
    depends_on: [implement]

revision_policy:
  on_test_failure: return_to_controller
  maximum_revisions: 3
```

**What the runtime validates before executing anything:** capabilities exist in
the registry · dependencies are acyclic · required inputs are available ·
permissions are sufficient · parallel tasks are actually independent · mutations
have approval and idempotency policies · the plan fits time, token, and monetary
budgets · every mutation has corresponding verification · stopping conditions are
machine-checkable.

> **Dynamic topology, constrained vocabulary.** Let the model compose *registered
> capabilities*; do not let it invent executable primitives.

### §1.2 Abstraction levels

A useful separation of concerns, whether or not the topology is dynamic. Each
level runs on a different cadence, which is the point — the expensive level
should not run on every file read.

| Level | Role | Holds | Runs when |
|---|---|---|---|
| **L0 Constitution** | Mostly static | Safety policy, authorization boundaries, operating principles, communication behavior | Never changes within a session — belongs in the stable cached prefix (§3.2) |
| **L1 Mission controller** | Global strategy | Goal, constraints, definition of done, strategy, risk, budget, progress, unresolved decisions | Task begins · stage completes · worker reports an exception · evidence contradicts the plan · strategy must be revised · completion may have been reached. **Not before every shell command** |
| **L2 Stage planner** | One stage → a bounded task graph | Only global facts relevant to its stage | Per stage: research, diagnose, implement, verify, review, deliver |
| **L3 Specialist worker** | One local objective | Local objective, required constraints, selected evidence, restricted tools, return contract, local budget | Per task; may own a short tool-use loop |
| **L4 Deterministic executor** | Mechanics | Tool composition, pagination, file operations, data transformation, polling, validation, retries, scheduling | Constantly — and **normally without an LLM** (§5) |
| **L5 Independent verifier** | Checks environment against criteria | Intended result and observable evidence; **not** the generator's reasoning | Before completion claims — omitting the generator's rationale reduces self-confirmation `[EB §5]` |

Each level declares its required context rather than receiving whatever
accumulated. The runtime — not the worker — constructs the model input from that
declaration:

```yaml
context_profile:
  include:  [local_goal, relevant_constraints, selected_files,
             dependency_outputs, recent_failures]
  retrieve:
    - query: authentication middleware
      sources: [code, decisions]
      maximum_tokens: 6000
  exclude:  [unrelated_conversation, raw_successful_tool_logs,
             private_state_from_other_workers]
  recent_tool_events: 4
  maximum_input_tokens: 12000
  output_schema: InvestigationResult
```

### §1.3 Approaches, not fixed personas

Reusable **approaches** are more powerful than a permanent roster of named
agents. An approach describes *when and how* to act, and the controller selects
one based on the situation — it may instantiate no subagent, one specialist, or a
temporary set of parallel workers.

```yaml
name: hypothesis_driven_debugging
when:
  - observed behavior differs from expectation
  - evidence is incomplete
procedure:
  - reproduce
  - localize
  - form competing hypotheses
  - run discriminating checks
  - repair the smallest demonstrated cause
  - test affected and adjacent behavior
stop_when:
  - cause is demonstrated
  - fix passes required checks
```

A working catalog: repository reconnaissance · documentation-first investigation ·
search–extract–synthesize · generate–critique–revise · plan–execute–replan ·
differential diagnosis · constraint solving · risk-based approval · API-first
computer interaction · test-driven repair · parallel independent research ·
adversarial review · escalation after repeated failure.

**Approaches use progressive disclosure like everything else**: the catalog holds
name plus a short applicability description; full instructions, resources,
scripts, and constraints load only after selection. This is the same mechanism as
skills — see the platform document.

### §1.4 When to add a second agent

The best default is one capable controller plus tools and deterministic workflow
nodes. Add specialized agents only when independent work can run in parallel · a
separate context prevents contamination · a different model or permission
boundary is materially useful · independent generation and evaluation improve
*measured* quality · or organizational/security isolation requires it.

**Avoid conversational "agent societies"** where agents repeatedly talk to each
other. They multiply tokens, latency, inconsistency, and error propagation.

A production graph, if you build one, needs: durable checkpoints · pause and
resume · error-classified retry policies · idempotent nodes · compensation for
partial mutations · human interrupts · state inspection and replay · versioned
workflow definitions · migration of in-flight state · dead-letter handling ·
per-node time, token, and cost budgets. General-purpose durable workflow engines
may serve better than an LLM-specific graph API when those semantics — rather
than the LLM integration — are the main requirement `[EB §6.6]`.

---

## §2 The loop

Eight phases. The distinguishing property is that it is **genuinely cyclic** — if
the graph is a DAG that calls a model once and formats the output, it is a
pipeline with a model in it, not an agent.

**1. Orient** — interpret the request, load durable task state, inspect relevant
environment state, identify uncertainty, permissions, budgets, and success
criteria.

**2. Compile context** — assemble only what is useful for the *next* inference:
stable instructions, the current task contract, a compact progress ledger, recent
useful actions, retrieved evidence, currently relevant tool definitions. See §3.

**3. Choose the next smallest useful action** — answer directly when no external
action is necessary; use ordinary code for deterministic computation; use a tool
for environmental information or effects; delegate only when independent parallel
work justifies its coordination cost.

**4. Execute** — batch independent reads; use a sandboxed program for joins,
filtering, polling, pagination, and conditional tool workflows; assign
idempotency keys to externally visible mutations.

**5. Observe** — return structured observations: status, changed resources,
durable identifiers, errors with retry classification, artifact references,
compact evidence. **Large raw results are stored externally, not copied into
context.**

**6. Verify** — compare the resulting environment against acceptance criteria.
Run tests, inspect files, query the API, observe the UI. An agent judging its own
output from inside the trajectory that produced it entangles verification with
self-justification `[EB §5]`. If a test can be run, run it. Use an independent
evaluator only where its cost produces measured improvement.

**7. Update durable state** — record progress, decisions, remaining work,
committed side effects, verification evidence. Compact the working context when it
becomes noisy.

**8. Terminate correctly** — finish only after verification; pause durably for
long waits; ask the user only for genuinely missing decisions or authority; stop
at budget, policy, or safety boundaries.

### Control-flow properties the loop must have

- **Decisions must be revisable.** Any decision made *before* the loop — tool
  selection, refusal, routing — is unrecoverable if the loop cannot revisit it.
  Pre-loop classification should produce a **prior, not a gate**. Refusals in
  particular belong after evidence gathering, not as a pre-filter.
- **Explicit verification before answering**, with an edge back into action. This
  is the difference between failing gracefully and confidently answering from
  empty results.
- **Bounded iteration with informative exhaustion** — a hard cap, a distinct
  terminal state when hit, and telemetry on how often. Frequent limit-hits
  indicate a tool or prompt defect, not a cap set too low.
- **Progress detection** — detect repeated identical tool calls and oscillation
  and break out. Repeating the same action without new evidence is a loop defect,
  not persistence.
- **Deliberate state semantics** — last-write-wins channels are fine for a DAG and
  wrong for a cyclic graph, where accumulation across revisits needs explicit
  reducers. Retrofitting cycles onto last-write-wins state is a recurring source
  of subtle bugs.
- **Explicit limits** on elapsed time, model turns, repeated failures, token
  spend, tool calls, and irreversible actions.

---

## §3 Context and memory

### §3.1 The reframe: context as projection, not storage

The move that makes everything else tractable:

> The context window is not storage. It is a **projection** — a temporary,
> purpose-built view assembled from durable substrate on demand.

| Layer | Lifetime | Size |
|---|---|---|
| **Persistent substrate** | All state between calls | Unbounded |
| **Ephemeral projection** | One inference call | Small, purpose-built |

Once separated, "keep context small" and "don't lose information" stop being in
tension. Nothing is lost — it is in substrate. Only the projection is small.
Measured effect: roughly an order of magnitude per call before caching `[EB §2.5]`.

Different calls receive different projections of the same durable state:

| Call | Context supplied |
|---|---|
| Strategic planner | Goal, constraints, progress, risk, budgets, capability categories |
| Code investigator | Local question, repository map, relevant files and symbols |
| Implementation worker | Change contract, selected files, coding rules, test command |
| Test analyst | Test failures, changed-file list, expected behavior |
| Security reviewer | Diff, threat model, security requirements |
| Final synthesizer | Verified results, decisions, caveats, artifact references |

The planner does not need raw test logs. The test analyst does not need the
entire user conversation. The synthesizer does not need every exploratory shell
command.

A context compiler applies: relevance filtering, permission filtering, freshness
filtering, deduplication, abstraction-level selection, explicit token budgets,
retrieval and reranking, bounded recency retention, stable-prefix construction,
source and artifact references, and compression appropriate to the consuming
model.

### §3.2 The four-region projection layout

Ordered deliberately, and the ordering is forced by cache behavior — **any
dynamic content inserted early invalidates every downstream cache entry**
`[EB §3.2]`.

1. **Pinned** (stable, cached) — constitution, system instructions, universal
   operating rules, tool namespace summaries, durable output conventions
2. **Session summary** (static per session) — compressed prior work and decisions
3. **Retrieved** (dynamic) — semantically relevant substrate chunks, stage rules,
   worker role, output schema
4. **Recent raw** (last N turns) — uncompressed recent work, current observation

Placement inside the projection matters as much as volume: critical information
at start or end and never the middle, short retrieved chunks over long documents,
sources interleaved by decreasing relevance, structural markers for localization
`[EB §2.1]`. Same token budget, materially different quality — this is free.

### §3.3 Seven kinds of state, not one thing called "memory"

| Kind | Contents | Rule |
|---|---|---|
| **Immutable instructions** | Small versioned policies and behavioral rules | Stable prefix; never varies within a session |
| **Structured task state** | Goal, constraints, acceptance criteria, phase, completed steps, open questions, decisions, artifact refs, side-effect ledger, failure history, budget | The authoritative object for pause, resume, recovery — **not** prose chat history |
| **Recent working memory** | Latest useful messages, bounded recent tool interactions | Remove repetitive command output and obsolete intermediate reasoning |
| **Episodic event log** | Append-only actions and observations | For debugging, audit, replay, rebuilding summaries, recovering from compaction mistakes. **Not** auto-inserted into prompts |
| **Semantic knowledge** | Stable facts, user preferences, project decisions, domain docs, validated procedures | Every item carries provenance, scope, and freshness |
| **Artifact store** | Files, logs, datasets, screenshots, large tool responses, build output | Compact metadata and stable references go in context; contents stay out |
| **Retrieval indexes** | See §3.5 | — |

### §3.4 Budgets, truncation, compaction, clearing

The order of preference is the reverse of most implementations' instincts.

1. **Budgets enforced where growth happens.** Budgeting conversation history but
   not tool results is a common half-measure — tool output is usually what
   actually grows. Enforce caps on the accumulating message list *inside* the
   loop, not only on inputs to it.
2. **Tool-result clearing is the primary mechanism.** Dropping stale tool output
   measured both cheaper *and* better than retaining full context `[EB §2.2]`.
   Stale context is not neutral ballast.
3. **Deterministic cleanup before any model call** — dedup identical tool
   outputs, purge resolved errors, canonicalize verbose responses. Zero model
   cost `[EB §2.4]`.
4. **Truncation preserves the informative end** and marks the elision explicitly,
   so the model knows information was removed rather than inferring it never
   existed.
5. **Compaction last, and structured.** Trigger well before exhaustion; use a
   fixed template rather than free-form summarization `[EB §2.3]`. Compaction is
   lossy by nature — preserve the original event log and artifacts outside the
   model so omitted detail is recoverable.

This escalation ladder is not theoretical: a shipped implementation stages five
layers in exactly this cheapest-first order, from pointer substitution through
history trimming to full auto-compaction, with **cache-awareness built into the
compression layer** rather than bolted on `[EB §8.1]`.

Compaction must **preserve**: goal and constraints, user commitments, decisions
and rationale, current plan and progress, unresolved failures, artifact
identifiers, external side effects, evidence required for later verification.

It should **remove**: superseded plans, repeated observations, verbose successful
command output, full documents available by reference, exploration that produced
no durable conclusion.

**Externalize at creation, not at extraction.** Write long-lived facts to durable
memory when they are produced, rather than mining them out of a dying context
during compaction `[EB §2.4]`. This is the difference between lossless and lossy.

### §3.5 Retrieval

Use methods together, selected by query shape:

1. exact identifiers and paths
2. metadata filters — tenant, project, source, permissions, version, time
3. lexical / BM25 for names, error messages, code symbols, exact terminology
4. embeddings for conceptual similarity
5. graph or relationship lookup for dependency questions
6. reranking after broad retrieval
7. agentic search when query reformulation or reference-following is needed

**Embeddings alone are insufficient** for exact code symbols, recent state,
negative constraints, permissions, and temporal questions. For code specifically,
an LLM driving lexical search in a loop beats a frozen embedding index on a
repository that changes every commit — and results should be verified against
disk `[EB §4]`.

Shipping products split on this: one reference implementation defaults to live
agentic search with no index, another to an automatic incremental cloud index
with Merkle-tree change detection `[EB §4.1]`. If you build an index, reject or
accept it on **staleness and privacy** grounds — embedding cost is negligible
against the loop's own model calls.

### §3.6 Just-in-time retrieval, and its honest tension with caching

Hold lightweight identifiers — file paths, queries, URLs — and resolve contents at
runtime rather than front-loading `[EB §2.7]`.

**But this pulls against §3.2.** Dynamic loading fragments the cacheable prefix,
and caching is the single largest cost lever available `[EB §3.1]`. This is a
genuine tension, not a solved question. The partial resolution used in practice:
a **small curated upfront set plus autonomous exploration**, with dynamically
discovered content injected at the *end* of the context so the prefix survives
`[EB §2.6]`.

---

## §4 Tools

Tools, not prompts, are the agent's real interface to the world, and tool quality
dominates model quality in most failure analyses.

### §4.1 Tool contract

Every tool should provide narrow semantics, typed inputs and outputs, clear
preconditions and side effects, stable error codes, timeouts and cancellation,
idempotency support, compact default output with optional detail levels,
pagination and server-side filtering, artifact handles for large output, and
machine-verifiable success conditions.

The attributes that most often distinguish a working agent from a demo:

- **Structured results, never prose.** Prose forces the model to re-parse,
  hallucinate around ambiguity, and re-derive numbers it should have been handed.
- **Bounded output** — every tool caps rows/bytes with an explicit limit
  parameter and a hard maximum. Unbounded tool output is the most common cause of
  context exhaustion mid-loop.
- **Errors as data, never exceptions.** A failing tool returns
  `{ok: false, error: ...}` into the conversation. An exception that escapes kills
  the turn; an error *in the transcript* is something the model can read and route
  around. Error messages should be actionable by a model — say what was wrong and
  what valid input looks like.
- **Argument validation at the boundary** — validate against the real handler
  signature and reject unknown arguments with a clear message. Models routinely
  invent plausible parameters.
- **Few, well-named, non-overlapping tools.** The stated test: *if a human
  engineer can't definitively say which tool applies, an agent can't be expected
  to do better* `[EB §2.9]`. Descriptions are prompt surface and deserve
  prompt-level care. Consolidate rather than proliferate.
- **Idempotency and side-effect declaration.** Read-only tools are safe to retry,
  cache, and parallelize. Mutating tools must be marked and generally need
  confirmation and idempotency keys. The safety machinery an agent needs is
  proportional to what its tools can actually do.

### §4.2 Progressive disclosure of tools

Do not expose hundreds of complete tool schemas on every call. Tool-definition
bloat is the largest single context waste measured, and it is pure overhead paid
on every call `[EB §2.6]`.

1. Show tool namespaces and concise descriptions initially.
2. Let the model search for the relevant capability.
3. Inject only selected schemas — **at the end**, to preserve the cached prefix.
4. Keep large tool results in the execution environment.
5. Return a filtered result or artifact reference to the model.

Namespaces should be coherent and generally hold fewer than ten functions
`[EB §2.6]`.

**Curated exposure must remain revisable.** Binding only plausibly relevant tools
per turn improves selection accuracy, but if the narrowing cannot be widened
mid-loop, a wrong early guess becomes an unrecoverable failure.

### §4.3 Tools as code

For large tool ecosystems, expose tools as code APIs inside a sandbox. The agent
writes one program that paginates, filters and aggregates, joins multiple APIs,
branches and retries, polls until a condition changes, and returns only the
relevant result. Measured reductions are large `[EB §2.6]`.

---

## §5 Do not spend an LLM call on this

The largest single efficiency win in the dynamic-graph literature came from
deciding which steps shouldn't be inference at all `[EB §6.3]`.

**Use ordinary code for:** conditionals, loops, joins, pagination steps, polling
intervals, validation rules, formatting, parsing a known structure, sorting,
filtering, counting, deduplication, schema validation, mechanical state
transitions, and obviously deterministic routing.

**Spend an additional LLM call only when it** isolates a large amount of
temporary context, allows a cheaper model to do the work, enables independent
concurrent work, supplies meaningfully independent judgment, benefits from a
specialized prompt, compresses a large investigation into a small structured
artifact, requires different tools or permissions, or prevents local detail from
contaminating the controller's context.

**Do not ask a model to do arithmetic, filtering, or aggregation a tool can do
exactly.** Models should decide *what* to compute; code should compute it.

---

## §6 Model and effort routing

Different layers can use different models. Routing raises quality as well as
lowering cost — a well-designed router can outperform the single most capable
model by exploiting per-model strengths `[EB §6.5]`.

| Layer | Model class | Rationale |
|---|---|---|
| Goal interpretation | Strong, instruction-faithful | Contract errors propagate everywhere |
| Strategic planning / approach selection | Frontier | Highest-leverage, lowest-volume decision |
| Planning and edits | Frontier | Correctness-critical |
| Search, exploration, classification, routing | Small / fast | High volume, verifiable output |
| Summarization, compaction | Mid | Structured, templated |
| Independent review | Strong, ideally a different family | Independence is the point |
| Final synthesis | Strong, evidence-rich context | Composition errors are expensive |
| Deterministic steps | **No model** — code | The 19× lever `[EB §6.3]` |

The same applies to reasoning effort: low for routine actions, high only where
uncertainty, impact, or complexity requires it.

**The router itself must be evaluated.** A routing mistake can cost more than
always using one strong model, and a cheap worker returning an incorrect artifact
makes downstream synthesis more expensive than doing it properly the first time.

---

## §7 Speed and cost

The fastest high-quality agent reduces sequential model round trips.

- **Stable cached prefixes first.** Caching is the highest-leverage optimization
  available `[EB §3.1]`, and cache discipline is architecture, not configuration
  `[EB §3.2]`. A per-request timestamp near the top of a system prompt silently
  destroys the entire cache benefit. **Measure cache reads, writes, and hit
  rate** — caching is easy to configure and easy to silently break.
- **Enforced budgets, not just accounting.** Measuring tokens is not controlling
  them. Hard caps per turn and per session with defined behavior on breach.
- **Optimize cost per successful task, not cost per call.** Agentic tasks make
  many model calls; per-call price is not the unit that matters `[EB §3.3]`.
- **Result caching** — cache deterministic tool results within and across turns.
  Agents re-call the same tool constantly, especially after a retry or re-plan.
- **Parallel work** — execute independent reads and retrieval in parallel; batch
  independent tool calls in one turn; run inexpensive policy checks concurrently
  where later work can be cancelled. **Do not parallelize mutations that depend
  on ordering or shared state.** This is usually the largest wall-clock win
  available for the smallest change.
- **Warm infrastructure** — reuse HTTP/2 or gRPC connections, database pools, MCP
  sessions, WebSockets, authenticated browser sessions, language servers,
  repository indexes, and sandboxes where isolation rules permit. Start inference
  before provisioning expensive execution environments `[EB §3.3]`.
- **Fewer generated tokens.** Generated tokens are commonly the slowest part of
  inference. Concise model-facing observations, compact schemas, bounded final
  answers, and one request for tightly coupled reasoning that would degrade if
  split.
- **Streaming and background execution** — stream useful progress for interactive
  work; long jobs survive client disconnection and complete via polling,
  webhooks, or workflow callbacks.

---

## §8 Reliability and durable execution

Long-running agents should be implemented like distributed systems. This is the
least glamorous section and usually the difference between "works in demo" and
"works."

- **Retries with exponential backoff and jitter.** Model APIs return 429s and
  5xxs routinely; jitter prevents thundering herds.
- **Retryable vs. terminal classification.** Retry 429/500/502/503/504 and
  timeouts. Never retry 400/401/403 or content violations — that burns budget on
  a guaranteed failure. A fuller taxonomy: transient, recoverable,
  user-correctable, policy, terminal.
- **Timeouts at every level** — per model call, per tool call, per turn.
- **Degradation ladders** — each failure has a defined fallback: repair a
  malformed response, fall back to a safe default, return a partial answer with
  an explicit caveat. Never raise a stack trace at a user.
- **Cancellation** — client disconnect aborts in-flight model and tool calls, and
  propagates deadlines. Without it, abandoned requests keep spending money.
- **Idempotency for retried side effects** — retrying a mutating call must not
  double-apply it.

For durable execution specifically: append-only events or an equivalent audit
trail, explicit state machines, transactional or idempotent mutations, leases or
ownership for concurrent workers, heartbeats for long operations, reconciliation
after uncertain tool outcomes, unique operation IDs, recovery from process,
network, and model failures, and durable waits that consume no active compute.

> **The model must never be responsible for remembering whether a payment,
> email, deployment, or deletion has already occurred. The runtime's side-effect
> ledger is authoritative.**

---

## §9 Observability

Capture a trace for every end-to-end task, with spans for routing, context
assembly, retrieval queries and selected results, model requests, tool discovery,
tool execution, guardrails and approvals, state transitions, verification, and
retries.

Record: task and trace IDs propagated to every tool call and provider request;
model and prompt versions; input, cached-input, reasoning, and output tokens;
latency by stage; tool arguments and compact outputs subject to privacy policy;
retrieved source IDs and scores; context composition and token allocation; cache
hits and misses; side effects; final outcome and grader results.

Non-obvious requirements:

- **Persisted traces**, queryable offline. Real failure analysis happens after
  the fact and in aggregate; per-request in-memory events cannot support it.
- **Per-stage attribution** of tokens, cost, and latency — not just a turn total.
  Aggregates hide the expensive stage.
- **Cache effectiveness metrics** as a first-class signal (§7).
- **Streaming structured progress events** (step started, tool called, result
  received), not only tokens, so a UI can show real progress and a human can
  intervene.
- **Standard instrumentation** — OpenTelemetry spans or an LLM-observability
  platform. Custom event formats do not integrate with existing production
  tooling.
- Sensitive model and tool data must be optional, redacted, access-controlled,
  and subject to retention limits.

---

## §10 Safety, proportional to blast radius

Scale this section to what the tools can actually do. Read-only tools over
trusted internal data need very little; tools that write, spend, or send need all
of it.

**The strongest design contains capability rather than relying on permission
prompts.** Users approve the overwhelming majority of prompts they are shown
`[EB §10.2]` — approval fatigue makes prompting a weak boundary.

- **Treat tool output as untrusted input.** Any content originating outside the
  system — web, uploads, third-party APIs, MCP server descriptions — can carry
  injection. Mark provenance and never let retrieved content be interpreted as
  instructions.
- **Least privilege** — scoped, short-lived credentials per tool; separation
  between read and write tools.
- **Human approval for consequential actions** — irreversible or outward-facing
  actions pause for confirmation with enough context shown to make the decision
  meaningful. Automatic approval for low-risk bounded actions.
- **Sandboxing** — isolated filesystems and processes, network egress allowlists,
  CPU/memory/time/network/spend limits for code execution.
- **Secret redaction** from prompts, logs, and traces; audit logs and
  side-effect receipts.

MCP integrations carry additional specific requirements — see the platform
document, and `[EB §10.2]` for the source.

---

## §11 Engineering discipline

- **Single source of truth for types and state.** Duplicated enums or state
  shapes drift. One definition, imported everywhere.
- **Behavior from prompts and tools, not per-case branches.** The most important
  structural test: **when a new question shape fails, does fixing it require new
  code?** If yes, the system does not generalize — it is a lookup table with a
  model attached. Per-question special cases are legitimate as a stopgap, but each
  should be tracked as debt with a plan to fold it into a tool contract or
  prompt, because they accumulate silently and inflate evals (§12).
- **Structured output over parsing prose.** Use native structured-output or
  tool-call schema enforcement rather than regex-extracting JSON and repairing
  it.
- **Determinism where determinism is possible** (§5).
- **Prompts as versioned artifacts.** Prompts are load-bearing logic. Version
  them, diff them, tie eval results to prompt versions.

---

## §12 Evaluation

Without evaluation every other improvement is a guess. This is the
highest-leverage attribute and the one most often absent.

- **An independent oracle.** Expected answers derived independently of the
  agent's own machinery — computed from source data by separate code, or
  human-labeled. An oracle built from the agent's own tools tests
  self-consistency, not correctness, and moves whenever the tools move.
- **Trajectory evaluation, not just final-answer matching.** Final-string
  comparison cannot distinguish "right answer for the right reason" from "right
  answer by luck." Assert on the path: which tools were called and in what order,
  the *arguments* they were called with, specific fields in tool results, and
  iteration count. An agent that reaches the right answer via the wrong
  trajectory will fail the next, slightly different question.
- **Regression gates in CI** with a pass threshold that blocks merge. Agent
  quality regresses silently; prompt edits have non-local effects.
- **Separate harness-fitting from capability.** Every hardcoded special case,
  answer override, or question-specific prompt injection inflates eval scores
  *without* improving the agent. A mature setup can report the score with such
  compensations disabled. Otherwise the eval measures the scaffolding, and the
  number rises while generalization falls.
- **Cost and latency as first-class eval metrics.** A change that raises accuracy
  2% and cost 300% is usually a bad trade, and is invisible if only accuracy is
  tracked.

Measure the Pareto frontier, not a single number: verified task-completion rate,
partial progress, human correction rate, constraint violations, unsafe actions,
false claims of completion, recovery rate after tool failure, token breakdown by
type, cost per *successful* task, wall-clock and time-to-first-useful-result,
model turns and tool calls, context utilization, retrieval precision and recall,
cache-hit rate, repeated actions, resume correctness after interruption,
side-effect duplication, human time saved.

Evaluate full trajectories in real environments with repeated stochastic runs,
combining deterministic graders, state-based checks, model graders, and selective
human review `[EB §10.1]`. Include at least one **private** task set — public
benchmarks post-saturation are substantially gamed `[EB §10.1]`.

### The ablation rule

> Does removing this component measurably reduce quality, safety, reliability, or
> efficiency on representative tasks?

If not, remove it. Harness assumptions age quickly as models improve, and harness
gains do not transfer across models `[EB §1]` — so every architectural addition
must survive ablation *on your model and your tasks*, and be re-ablated after a
model upgrade.

---

## §13 Where the sources disagree

Four genuine tensions. They are not resolved here.

**1. How dynamic should the graph be?**
The dynamic-workflow literature is enthusiastic: a meta-level Designer LLM that
reasons about approach rather than task, editing topology mid-execution
`[EB §6.1–6.3]`. The counterweight from the same body of evidence: those results
are on short reasoning benchmarks, the meta-call is itself cost, and a single
loop with good observability reveals whether coordination is needed before the
coordination layer is built `[EB §6.6, §11]`.

*The defensible middle:* a small fixed **outer** loop that is boring, replayable,
and observable; **dynamism in what each node sees (projection) and which node
runs next (dispatch), not in inventing arbitrary topology every turn**; a
meta-level call only when the situation is genuinely ambiguous; deterministic
code nodes wherever the step is predictable. This captures most of the measured
upside while staying debuggable.

**2. Build the durable workflow engine early, or late?**
One source recommends running the agent through a durable workflow engine with
checkpoints from the start. The other holds that graphs earn their keep for four
specific runtime needs — durable execution, streaming, human-in-the-loop
interrupts, managed memory — and are overhead absent those `[EB §6.6]`.
Reconcilable by asking whether you have those four needs *now*.

**3. Compaction or tool-result clearing as the primary mechanism?**
The GPT-authored sources treat compaction as the main context-control lever and
describe it in detail. The measured evidence puts **clearing first and compaction
second**, reserved for preserving reasoning across long dialogue `[EB §2.2]`.
Here the evidence should win: this is a direct measurement, not a preference.

**4. Just-in-time retrieval vs. stable cache prefix.**
Both are strongly recommended and they pull against each other (§3.6). One source
names this explicitly as unsolved. Treat it as a per-workload measurement, not a
principle to pick.

---

## §14 Attribute checklist

A compact form for auditing an implementation. Each maps to a section above.

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
| C3 | Tool-result clearing | Context |
| C4 | Structured compaction | Context |
| C5 | Stable cacheable prefix | Context |
| C6 | Just-in-time retrieval | Context |
| C7 | Curated, revisable tool exposure | Context |
| C8 | Hybrid retrieval, not embeddings alone | Context |
| D1 | Cyclic loop | Control flow |
| D2 | Revisable decisions | Control flow |
| D3 | Verification before answering | Control flow |
| D4 | Bounded iteration | Control flow |
| D5 | Progress detection | Control flow |
| D6 | Deliberate state semantics | Control flow |
| E1 | Retry with backoff + jitter | Reliability |
| E2 | Retryable vs terminal classification | Reliability |
| E3 | Timeouts at every level | Reliability |
| E4 | Degradation ladders | Reliability |
| E5 | Cancellation | Reliability |
| E6 | Idempotency for retried side effects | Reliability |
| E7 | Authoritative side-effect ledger | Reliability |
| F1 | Correlation IDs | Observability |
| F2 | Persisted traces | Observability |
| F3 | Per-stage attribution | Observability |
| F4 | Cache metrics | Observability |
| F5 | Streaming progress events | Observability |
| F6 | Standard instrumentation | Observability |
| G1 | Prompt caching, correctly applied | Cost |
| G2 | Enforced budgets | Cost |
| G3 | Model and effort tiering | Cost |
| G4 | Result caching | Cost |
| G5 | Parallel tool execution | Cost |
| G6 | Warm infrastructure | Cost |
| H1 | Single source of truth | Discipline |
| H2 | No per-case branches | Discipline |
| H3 | Structured output | Discipline |
| H4 | Determinism where possible | Discipline |
| H5 | Versioned prompts | Discipline |
| I1 | Tool output untrusted | Safety |
| I2 | Least privilege | Safety |
| I3 | Human approval for consequential actions | Safety |
| I4 | Sandboxing | Safety |
| I5 | Containment over prompting | Safety |

### Priority when starting from nothing

1. **A1–A3** — evaluation first. Everything else is unmeasurable without it.
2. **B1–B4** — tool quality. Larger effect than model choice.
3. **E1–E4** — reliability. Cheap, and the difference between working and not.
4. **D1–D2** — the actual loop, cyclic and revisable.
5. **C1, C3, C5, G1** — context discipline and caching.
6. **F1–F3** — observability, before scale rather than after.
7. Everything else as scale and blast radius demand.

**The common failure is starting at 4** — framework and graph topology, the
visible part — **and never reaching 1.**

---

## §15 Domain notes

### Coding agents

Search before reading entire repositories; read narrow file ranges and expand on
demand; use language servers, symbol indexes, dependency graphs, AST search, and
version-control history; maintain a task ledger separate from chat; edit
incrementally; run the smallest relevant test first, then broader verification;
inspect existing user changes and preserve unrelated work; compare the final diff
against requirements and architectural decisions; treat test passage as necessary
but not always sufficient; use browser or visual inspection where behavior is
user-facing; preserve exact build, test, lint, and runtime evidence; report what
was verified **and what was not**.

Repository instructions should themselves use progressive disclosure: a small
routing document at the root, deeper domain instructions loaded only for the area
being changed.

### Computer use

Prefer, in order: (1) a purpose-built structured API, (2) an application SDK or
command line, (3) DOM and accessibility-tree interaction, (4) vision-based GUI
interaction. Vision remains necessary for unsupported applications but is slower
and less reliable. Re-observe continuously after actions rather than assuming the
UI changed as expected.

**The limitation is severe** — best-evaluated full completion on long real-world
workflows remains around one in five `[EB §9]`. Named failure modes: losing
constraints, missing changing information, guessing instead of asking, skipping
verification. Claims of a "professional computer operator" need task-specific
end-to-end evidence, not short demos.

---

## §16 The blueprint

For a new general-purpose coding, chat, research, or computer-use agent:

1. Use one strong controller agent.
2. Keep a typed task-state object and an append-only event log.
3. Add durable checkpointing when you have one of the four needs listed in
   `[EB §6.6]` — see §13, tension 2.
4. Compile context under explicit token budgets before each inference.
5. Use hybrid lexical, vector, and metadata retrieval with reranking.
6. Load files, knowledge, skills, and tools just in time.
7. Organize tools into namespaces and defer detailed schemas.
8. Provide a sandboxed code-execution layer for tool composition.
9. Store large output in an artifact store.
10. Keep prompt prefixes stable and measure cache behavior.
11. Reuse safe connections and warm execution resources.
12. Clear stale tool results aggressively; compact structurally and late.
13. Route models and reasoning effort by measured task difficulty.
14. Parallelize independent reads and batch independent tool calls.
15. Verify mutations through tests or observable postconditions.
16. Back risk-based approvals with real capability containment.
17. Trace, replay, and continuously evaluate complete task trajectories.
18. Add planner, evaluator, or parallel agents only when ablation proves value.

### Design principles

1. **Dynamic context, durable truth.** Vary the model context freely; keep
   authoritative state outside it.
2. **Global strategy, local cognition.** The controller reasons globally; workers
   reason over small local problems.
3. **Dynamic topology, constrained vocabulary.** Let the model compose registered
   capabilities rather than invent executable primitives.
4. **LLMs for judgment, code for mechanics.**
5. **Optimize total work.** Small contexts help only when total tokens, calls,
   latency, and retries improve without quality loss.
6. **Verify externally.** Completion is an observable property of the
   environment, not an agent statement.
7. **Progressive disclosure everywhere** — knowledge, tools, skills, subagents,
   policies, settings.
8. **Enforcement belongs in structure, not prose.** Structure survives context
   growth; prose dilutes.
9. **Complexity must survive ablation.**
