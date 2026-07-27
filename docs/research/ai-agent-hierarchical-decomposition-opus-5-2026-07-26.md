# AI agents — hierarchical decomposition

> **Merged:** 2026-07-26 by Claude Opus 5 (`claude-opus-5`), via Claude Code.
> Reasoning effort not exposed to the agent; recover from the session transcript
> if it matters.
> **Research date of underlying material:** 2026-07-25.
> **Status:** Research and reference. **Not a decision, requirement, or plan.**
> Adopting anything here is a separate decision belonging in `docs/adr/` or
> `roadmap.md`.

## What this document is

The pattern: **break a problem into 3–5 sub-goals, answer each with its own small
LLM calls at its own abstraction level, iterate back to revise earlier
sub-answers, then do tool work, then synthesize.**

This document is kept separate from the reference architecture for one reason:
**that architecture is settled and this is not.** The two source documents
disagree about how enthusiastically to adopt this — one blueprints a full
hierarchical runtime, the other documents a 15× cost multiplier and a published
finding that the strongest evidence for it *excludes coding*. Merging it into the
architecture doc would make a live question read as a decision.

Read it as: *here is the pattern, here is exactly what has been demonstrated,
here is what it costs, here is what remains genuinely open.*

**It carries no numbers and no external links.** Measured claims cite
`ai-agent-evidence-base-opus-5-2026-07-26.md` as `[EB §n]`; the decomposition
evidence is `[EB §7]`.

| Companion | Read it for |
|---|---|
| `ai-agent-reference-architecture-opus-5-2026-07-26.md` | The runtime this would sit inside — projection, routing, verification, budgets |
| `ai-agent-evidence-base-opus-5-2026-07-26.md` | Every figure and source below |
| `ai-agent-platform-feature-surface-opus-5-2026-07-26.md` | Subagents as the platform primitive for isolation |

### Provenance

| Source document (now in `docs/archive/`) | Model | Effort | Contributed |
|---|---|---|---|
| `ai-agent-hierarchical-decomposition-isolated-reasoning-gpt-5-6-2026-07-25.md` | GPT-5.6 | low | §2 terminology, §5 policies, §6 frames, §7 scheduling, §8 synthesis, §9 recovery, §10 verification, §11 risks, §12 blueprint |
| `ai-agent-hierarchical-decomposition-multi-layer-calls-opus-5-2026-07-25.md` | Claude Opus 5 | medium | §1 verdict, §3 prior-art map, §4 contract, §5 control rules, §11 failure modes, §13 open questions |

Where the two disagree, §13 says so explicitly.

---

## §1 Verdict

**Every individual stage of the pattern is implemented, named, published, and in
production.** It is not speculative. It has roughly fifteen years of pre-LLM
lineage (blackboard systems, hierarchical task networks) and four years of
LLM-specific literature `[EB §7]`.

Three qualifications that determine whether you should build it:

1. **The stages are named separately and usually implemented separately.**
   Assembling all of them into one runtime — decomposition + per-sub-goal
   abstraction layers + back-revision + tool phase + synthesis — is *less*
   standardized than any single stage. **No benchmark measures a composition like
   this** `[EB §11]`. That composition is where the genuine design work, and the
   genuine risk, both live.

2. **One stage is materially under-supported: revising an earlier sub-answer
   after later sub-answers arrive.** Most published pipelines are forward-only.
   The mechanism that supports it is the **blackboard**, which is well-established
   but not the default in mainstream agent frameworks `[EB §7.7]`.

3. **The strongest published evidence for orchestrator-worker decomposition
   explicitly excludes coding.** Anthropic's own finding: these systems *"excel at
   problems that can be divided into parallel strands of research, but are less
   effective for tightly interdependent tasks such as coding"* `[EB §7.6]`. For a
   coding or chat agent, that caveat is load-bearing, not a footnote.

**The one rule to take even if you take nothing else:** attempt the task
directly first, decompose only on failure. This is ADaPT, it has the highest
evidence and lowest cost of anything in this document `[EB §7.3]`, and it is the
principled answer to "the meta-level calls must pay for themselves."

---

## §2 Vocabulary

Precision here prevents most of the confusion downstream — these words get used
interchangeably and they are not interchangeable.

| Term | Meaning |
|---|---|
| **Goal** | The user-visible outcome to achieve |
| **Question** | An uncertainty whose answer affects the solution |
| **Task** | Work that produces an artifact or changes the environment |
| **Sub-goal** | An intermediate state required for the parent goal |
| **Context frame** | The bounded input assembled for one model invocation or worker loop |
| **Artifact** | A durable output — finding, decision, file, patch, dataset, test result, evidence bundle |
| **Dependency** | A relationship indicating one question or task requires another's result |
| **Synthesis** | Combining child results into a parent-level conclusion |
| **Refinement** | Further decomposition of a node not directly solvable as stated |
| **Blackboard** | External shared state holding task structure, artifacts, evidence, decisions, and progress — without copying every detail into every model context |

Three distinct operations, often conflated into "decomposition":

1. **Decompose** — turn a high-level problem into explicit questions,
   dependencies, and success conditions.
2. **Isolate** — solve each question with its own small relevant context and
   local loop.
3. **Compose** — validate and combine the resulting artifacts into higher-level
   conclusions.

A complete implementation needs all three. Most partial implementations do (1)
and (2) and treat (3) as summarization, which is where they fail (§8).

---

## §3 The pattern, mapped to prior art

Nothing in the description is unprecedented. The value is in the composition and
in the operating rules governing it.

| Step in the pattern | Established name | Evidence |
|---|---|---|
| Break into 3–5 sub-goals *without solving them* | **Least-to-Most prompting** | `[EB §7.2]` |
| Route each sub-goal to a specialized handler | **Decomposed Prompting (DecomP)** | `[EB §7.2]` |
| Decompose *further* only when a sub-goal proves too hard | **ADaPT** (as-needed decomposition) | `[EB §7.3]` |
| Keep high-level goals unpolluted by low-level detail | **Task-decoupled planning** | `[EB §7.2]` |
| Answer each sub-question with separate small calls, own context | **Recursive/hierarchical decomposition**; per-call **projection** | `[EB §7.1]`, `[EB §2.5]` |
| One shared model in isolated planner/executor roles | **CoDA** | `[EB §7.8]` |
| Bound active context by recursion depth, not flat history | **ReCAP**, recursive language models | `[EB §7.8]` |
| Plan all steps up front, defer tool results via placeholders | **ReWOO** | `[EB §7.4]` |
| Tool calls as a dependency graph, executed in parallel | **LLMCompiler** | `[EB §7.5]` |
| Run 3–5 sub-investigations in parallel, isolated contexts | **Orchestrator-worker** | `[EB §7.6]` |
| **Return to sub-question 1 after seeing answers 2 and 3** | **Blackboard architecture** | `[EB §7.7]` |
| Explore alternative solutions to the *same* problem | **Tree of Thoughts / Graph of Thoughts** | `[EB §7.8]` |
| Spawn a new specialist when decomposition reveals a gap | **TDAG** | `[EB §7.8]` |
| Final reasoning over collected results, plus a separate citation pass | **Synthesis pass** | `[EB §7.6]` |

**Two of these are commonly confused.** Task decomposition separates *parts of a
problem*. Tree of Thoughts explores *alternative solutions to the same problem*.
They solve different needs and cost differently — ToT is expensive and is not a
default `[EB §7.8]`.

The production data points are real: Anthropic's Research system and OpenAI Deep
Research both implement orchestrator-worker with isolated sub-agent contexts,
parallel exploration, compressed return artifacts, and lead-agent synthesis
`[EB §7.6]`. Coding agents already use a less explicit form of the same shape —
understand task → identify relevant modules → investigate cause → implement
bounded change → run focused tests → inspect failure → revise → broader
verification → summarize.

---

## §4 Reference design

Five layers, each with a defined contract.

```
L0  INTAKE          raw request + first-pass attempt
        │           ← ADaPT: if this succeeds, stop. Do not decompose.
        ▼
L1  DECOMPOSER      emit 3-5 typed sub-goals + dependency edges
        │           (Least-to-Most: decompose, do NOT solve)
        ▼
L2  BLACKBOARD      durable typed store: sub-goals, partial answers,
    (substrate)     hypotheses, constraints, evidence, open questions
        │
        ├──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
L3  SUB-SOLVERS    solver(sg1)    solver(sg2)    solver(sg3)     ← parallel where
    each: own projection, own model tier, own tools,               deps allow
          own abstraction level, ADaPT recursion on failure
        │              │              │              │
        └──────────────┴──────────────┴──────────────┘
        │  writes partial answers + confidence + raised constraints
        ▼
L2' REVISION GATE   do later answers invalidate an earlier one?
        │           if yes → re-open that sub-goal (bounded)
        ▼
L4  TOOL PHASE      dependency DAG, parallel execution (LLMCompiler-style),
        │           results land on the blackboard as typed artifacts
        ▼
L5  SYNTHESIS       final reasoning over verified results
        │           + separate verification / citation pass
        ▼
      OUTPUT
```

### §4.1 Separate control state from reasoning content

**The runtime owns:** graph structure, task status, dependencies, budgets, retry
counts, permissions, side-effect records, artifact locations, trace identifiers.

**The model owns:** how to decompose, which uncertainty matters, what evidence is
relevant, whether a result answers the local question, how child results affect
strategy, how to synthesize.

> Never ask the model to remember the authoritative graph in prose.

### §4.2 The sub-goal contract

The single most important design object. Typed and explicit — this is what keeps
layers decoupled and what enables scheduling.

```yaml
subgoal:
  id: sg-1
  question:                    # self-contained; the thing to answer
  why_needed:                  # why the parent needs it
  abstraction:  strategic | structural | local | mechanical
  depends_on:   [sg-0]         # enables the parallel DAG
  provides:     [contract]     # what later sub-goals may rely on
  model_tier:   frontier | mid | small | none(code)
  tools_allowed: [...]         # least privilege per sub-goal
  context_spec:                # the projection, NOT the whole transcript
    include:    [goal, constraints, sg-0.answer, files:auth/*]
    retrieve:
      - query: authentication middleware
        sources: [code, decisions]
        maximum_tokens: 6000
    exclude:    [raw_tool_logs, user_chat_history, sibling_histories]
    recent_tool_events: 4
  budget:
    max_calls:  3
    max_tokens: 8000
    max_depth:  2              # ADaPT recursion limit
    wall_time_seconds: 180
  answer_schema:
    answer:       str
    confidence:   float
    evidence_ids: [str]        # provenance is mandatory
    invalidates:  [subgoal_id] # ← the back-revision trigger
    raised_constraints: [str]
    open_questions: [str]
  completion_contract:
    requires_sources: true
    minimum_independent_sources: 2
  status: proposed | admitted | waiting | ready | running |
          needs_refinement | integrating | verifying | answered |
          reopened | blocked | waiting_for_user | failed | abandoned
```

Three fields carry disproportionate weight:

- **`invalidates`** — this is what makes back-revision *declarative* rather than a
  vague "reconsider everything" pass. A sub-solver that discovers something
  contradicting an earlier answer names it; the revision gate reopens exactly that
  node, not the whole plan. **This field is a proposal, not a cited standard** —
  see §13.
- **`context_spec`** — the per-call projection. Each sub-solver receives a
  purpose-built view, not the accumulated transcript. This is where the token
  savings actually come from.
- **`depends_on`** — emit sub-goals with **explicit dependencies, not as a flat
  list.** A flat list forces sequential execution; a dependency list lets the
  scheduler extract parallelism for free `[EB §7.5]`. Cheap at design time,
  expensive to retrofit.

### §4.3 The result contract

The parent receives this, never the child's conversation:

```yaml
node_id: sg-1
status: answered
summary: Static prefixes can be reused while dynamic stage context is appended
claims:
  - text: Cache matching depends on stable prompt prefixes
    confidence: high
    evidence_ids: [openai_prompt_cache, gemini_implicit_cache]
    kind: direct | inferred
artifacts:
  - id: openai_prompt_cache
    uri: <stable handle into the artifact store>
open_questions:
  - How should cache keys be partitioned at high request volume?
invalidates: []
```

### §4.4 What each layer must *not* see

Enforced by `context_spec`. This table is where the token savings live.

| Layer | Must not receive |
|---|---|
| **Decomposer** | Raw file contents, tool logs |
| **Sub-solver** | Other sub-goals' internal reasoning; the full user conversation; sibling histories |
| **Revision gate** | Full sub-solver transcripts — only answers, confidences, raised constraints |
| **Tool phase** | Reasoning text of any kind |
| **Synthesizer** | Exploratory dead ends, raw shell output |
| **Verifier** | The generator's persuasive rationale, where it can be omitted |

The last row is deliberate: omitting the generator's reasoning from the verifier
reduces self-confirmation `[EB §5]`.

---

## §5 Control rules

### When to decompose at all

**Decompose when** the task contains separable questions · different sources or
tools are required · different expertise or models are beneficial · the working
set would otherwise become too large · branches can run independently ·
independent verification is valuable · one subproblem is blocking progress · the
task spans multiple abstraction levels · the current worker repeatedly fails ·
success criteria divide into independently checkable parts.

**Do not decompose when** it is directly solvable in one call · the parts are
tightly coupled · each branch would need almost the same complete context ·
synthesis would be harder than direct reasoning · coordination cost exceeds value
· latency matters more than marginal accuracy · side effects require strict
sequential control · decomposition would obscure a small coherent change.

**When uncertain: attempt directly first, decompose on failure** `[EB §7.3]`.

### The atomicity test

A node is atomic enough when a selected executor can likely finish it within one
bounded reasoning objective, one coherent working context, a small tool-use loop,
one output contract, and one verification method.

**A node need not map to one LLM call.** It may own a short local loop:

```
local orient → candidate answer → identify missing evidence
             → retrieve / use tools → revise → verify → emit compact artifact
```

The child owns that temporary history. Only its structured artifact returns.

### When to recurse deeper

Only on **executor failure** or explicit low confidence. Never unconditionally.
**Hard depth cap of 2–3** — depth is where error propagation compounds.

Set limits on: maximum depth, maximum children per node, maximum total nodes,
maximum active branches, maximum repeated decomposition, and total tokens, cost,
and time.

### When to reopen an earlier sub-goal

A later answer sets `invalidates: [sg-N]`, **or** raises a constraint
contradicting `sg-N`'s stated assumptions.

**Bound it**: max one reopen per sub-goal per cycle, max N reopens total. Without
a cap this is an infinite loop — the same safeguard the verification literature
requires: max iterations, per-cycle measurable-improvement check, state-hash
deduplication `[EB §5]`.

### Branch admission

Before creating a branch, estimate:

```
expected value =
    probability branch changes or validates the result
  × value of improved correctness
  + expected parallel latency reduction
  + expected context reduction
  − model and tool cost
  − coordination cost
  − synthesis complexity
```

The estimate need not be numerically precise. Its purpose is to prevent unbounded
thinking for the sake of thinking.

### Model tier per layer

Decomposer and synthesizer: **frontier** — low volume, high leverage, and the
decomposer is the highest-risk component in the system (§11.1). Sub-solvers: match
tier to sub-goal difficulty. Revision gate: **mid** — it is a classification, not
an essay. Mechanical steps: **no model**. See the routing table in the reference
architecture.

### When not to spend an LLM call at all

Conditionals, parsing known structures, sorting, filtering, joining, counting,
dedup, schema validation, mechanical state transitions, obvious deterministic
routing. These are code. This is the same lever that produced the largest measured
efficiency win in the workflow-optimization literature — deciding which nodes
shouldn't be inference at all `[EB §6.3]`.

---

## §6 Context isolation

The frames, stated as inclusion/exclusion contracts.

**Parent frame** — global goal, global constraints, current strategy, compact
child statuses, accepted child conclusions, conflicts and open questions.
*Excludes* raw child tool logs, every document children read, exploratory child
reasoning, and rejected hypotheses unless globally relevant.

**Child frame** — local objective, why it matters, relevant parent constraints,
dependency outputs, selected evidence, local tools, output schema, local budget.
*Excludes* sibling histories by default.

**Synthesis frame** — original goal and acceptance criteria, structured child
outputs, citations and evidence references, contradictions, missing coverage,
required final format. *May* retrieve underlying artifacts when a summary proves
insufficient — this escape hatch is what prevents summary corruption (§11.4).

**Verification frame** — claim or artifact to verify, success criteria, observable
environment state, relevant tests or sources. Omit the generator's rationale where
possible.

---

## §7 Scheduling

**Sequential** — when later questions depend on earlier answers. `A → B(A) →
C(A,B) → synthesis`. This is least-to-most.

**Parallel** — when questions are independent. Each branch gets an isolated
context and potentially a different model.

**Hybrid** — most real problems. The scheduler dispatches every ready node whose
dependencies are satisfied and whose concurrency, permission, and budget
constraints permit.

```
        ┌─→ A1 → A2 ─┐
root ───┼─→ B ───────┼─→ integrate → gap D → final
        └─→ C1 → C2 ─┘
```

**Speculative work** — begin a likely branch before an upstream decision completes
only if probability of usefulness is high, the branch is **read-only**, cost is
low, cancellation is supported, and the result cannot create an external side
effect.

**Batching within a sub-goal.** ReWOO-style up-front planning with placeholders
gives two LLM calls regardless of tool count, but planning blind is brittle in an
unexplored environment `[EB §7.4]`. The hybrid: use ReWOO batching **within** a
sub-goal whose shape is already known, and reactive stepping where it isn't.

---

## §8 Synthesis

**Synthesis is not summarization.** Treating it as summarization is the most
common way a decomposed pipeline produces confidently wrong output.

It must:

1. Map each child result to the parent question.
2. Check that all parent success criteria are covered.
3. Resolve or expose contradictions.
4. Distinguish evidence from inference.
5. Detect dependency mismatches.
6. Identify missing information.
7. **Trigger additional nodes when evidence is insufficient** — synthesis has an
   edge back into the graph, not just forward to output.
8. Produce a conclusion at the parent's abstraction level, reusable as a child
   artifact one level up.

### Hierarchical information compression

```
raw sources and logs
    → evidence records
    → child findings
    → branch conclusions
    → strategic decision
    → user-facing result
```

Each layer reduces detail **while retaining references back to the underlying
artifacts.** That back-reference is what makes the compression recoverable rather
than lossy.

### Evidence and provenance

Every child conclusion identifies its source or environment observation,
retrieval time, applicable scope, confidence, contradictions, and whether the
evidence is direct or inferred.

> The synthesis layer should never receive unsupported prose as if it were
> verified fact.

For coding tasks, evidence means file paths and symbols, commit identifiers,
command and exit status, failing and passing test names, diff hashes,
screenshots, API responses.

Note the production pattern worth copying: a **separate citation pass** after
synthesis `[EB §7.6]` — making one verifiable concern its own layer rather than
folding it into synthesis.

---

## §9 Verification, at two levels

**Local** — does the child result satisfy its node contract? Does the cited source
support the claim? Does the focused test pass? Does the query return the required
fields? Does the result obey its schema?

**Global** — does the integrated result satisfy the root contract? Are all user
questions answered? Do child results contradict each other? Does the relevant
test suite pass? Were all constraints preserved? Were side effects authorized and
recorded?

**Both are required, because a set of locally correct answers can compose into an
incorrect global answer.** This is the compositionality gap `[EB §5]`, and it is
the specific failure that decomposition introduces and that a single large call
does not have.

---

## §10 Error recovery

Classify the failure before reacting to it:

| Failure kind | Recovery |
|---|---|
| **Execution** — a tool or service failed | Retry transient failures |
| **Evidence** — required information not found | Reformulate retrieval |
| **Reasoning** — result contradicts known facts | Use an independent solver |
| **Decomposition** — children do not collectively answer the parent | Revise the task graph |
| **Integration** — child results conflict | Create a conflict-resolution node |
| **Budget** — additional work exceeds limits | Degrade scope or ask the user |
| **Authority** — user input or approval required | Pause durably |

> Do not restart the entire problem unless durable state is corrupt.

**Invalidation, when a child artifact changes:** mark dependent conclusions stale
→ cancel dependent work that has not committed useful output → re-run only
affected synthesis and verification nodes → preserve unrelated completed
branches. This is exactly the incremental-build-system discipline, and it is the
right mental model.

---

## §11 Failure modes — read before adopting

The literature on when this pattern *hurts* is as substantial as the literature
on when it helps.

### §11.1 Decomposition quality dominates everything

Specification and system-design issues — including task misinterpretation and
poor decomposition — account for the largest single share of multi-agent system
failures `[EB §7.9]`. Sub-tasks sliced too granular or too broad leave downstream
solvers with unfinishable work. Unlike human teams, LLM sub-agents cannot ask
clarifying questions mid-task, cannot read between the lines, and cannot
self-correct when coordination breaks down.

> **The decomposer is the highest-risk component, not the solvers.** Give it the
> strongest model and evaluate it independently.

**Incorrect decomposition** — a tightly coupled problem split into apparently
independent branches. Mitigate with explicit dependency modeling, integration
checks, and letting workers report hidden dependencies they discover.

**Over-decomposition** — many trivial nodes, coordination dominating work.
Mitigate with the atomicity test, minimum expected value for new branches, depth
and node limits, and combining mechanically related operations.

**Under-decomposition** — one worker with a broad task accumulating a large noisy
context. Mitigate with context-budget triggers, failure-triggered decomposition,
and inspecting worker evidence density.

### §11.2 Error propagation

An incorrect early answer becomes an assumption for every dependent node.
Sequential dependency chains multiply this `[EB §7.9]`. Mitigate with mandatory
confidence and evidence fields, independent verification at high-impact
boundaries, dependency edges that make propagation paths visible, invalidating
and recomputing descendants when a dependency changes, and dynamic
re-decomposition when a gap appears `[EB §7.8]`.

### §11.3 Decomposition overhead is real and sometimes decisive

The arithmetic that refutes "many small calls are always cheaper":

```
One large call:     40,000 in + 4,000 out            =  44,000 tokens
Ten small calls:    10 × (6,000 in + 500 out)        =  65,000 tokens
```

Repeated per-call preamble can make the decomposed version **more** expensive and
slower `[EB §7.10]`.

> **Decomposition saves tokens only when each sub-call's context is genuinely
> *narrower*, not merely *separate*.**

Related: for tasks split into dozens of sub-tasks, planning becomes constrained
by context length, causing forgetting of the planning trajectory `[EB §7.9]`.

**Coordination token explosion** is the systemic version of this — worker prompts
and handoffs costing more than a direct solution. Mitigate with stable cached
prefixes, compact typed artifacts, deterministic scheduling, model routing,
admission policy, and — critically — **total-token evaluation rather than
per-call evaluation**.

### §11.4 Summary corruption

A child artifact omits a detail needed later. Mitigate with structured outputs,
provenance links, retained original artifacts, and allowing the parent to
retrieve into child evidence (§6, synthesis frame).

### §11.5 Synthesis failure and premature finalization

**Synthesis failure** — all child answers individually plausible, composition
wrong. Mitigate with dependency-aware synthesis, contradiction checks, global
acceptance tests, independent integration review.

**Premature finalization** — the controller sees several completed children and
assumes the root goal is complete. Mitigate with a machine-readable coverage
matrix, explicit root acceptance criteria, and a final verifier.

### §11.6 The coding caveat

The most important single item for a coding agent. Anthropic's finding, stated
plainly: orchestrator-worker systems *"excel at problems that can be divided into
parallel strands of research, but are less effective for tightly interdependent
tasks such as coding"* `[EB §7.6]`.

Code changes share state — types, call sites, invariants — so sub-goals are rarely
independent. For a coding agent this argues for:

- **Decomposition along genuinely separable axes** (investigate auth ‖ investigate
  logging), **not** along artificially split edit tasks.
- **Sequential, contract-mediated implementation** once investigation is done.
- **Reserving parallel workers for read-only exploration**, where isolation is the
  point and interdependence is low.

### §11.7 The 15× multiplier

Orchestrator-worker cost is roughly 15× a normal chat. It bought +90.2% on
research-style tasks in its published evaluation `[EB §7.6]`. It does not
automatically buy anything on tasks that don't decompose. **Measure before
assuming.**

---

## §12 Building it

### Minimum viable version

One controller model · one worker model · typed sequential task lists · isolated
worker contexts · structured worker results · artifact references · one synthesis
pass · strict token, call, depth, and time limits · local and final verification.

Add only when evaluation supports it: dependency DAGs · parallel scheduling ·
recursive decomposition · multi-model routing · alternative-path search · learned
routing · remote subagents.

### Core services

1. **Goal interpreter** — produces the root contract
2. **Capability registry** — valid worker, tool, skill, and model capabilities
3. **Decomposition planner** — typed questions and tasks
4. **Graph validator** — dependencies acyclic, permissions sufficient, budgets
   fit, completion coverage machine-checkable
5. **Scheduler** — dependency-ready nodes with bounded concurrency
6. **Context compiler** — stage-specific frames from `context_spec`
7. **Worker runtime** — bounded local LLM/tool loop
8. **Artifact and evidence store** — full results outside model context
9. **Blackboard** — graph state, decisions, progress, accepted findings
10. **Synthesis engine** — integrates artifacts, identifies gaps
11. **Verifier** — local and root contracts
12. **Trace and budget service** — calls, tokens, cost, latency, decisions

### Recommended adoption order

Cheapest and best-evidenced first:

1. **ADaPT-style conditional recursion** — highest evidence, lowest cost
   `[EB §7.3]`
2. **Typed sub-goal contracts with dependency edges** — enables everything else
3. **Per-sub-goal context projection** — the token win
4. **Parallel tool DAG** — the latency win `[EB §7.5]`
5. **Blackboard + revision gate** — the novel part. Build last, measure hardest.

### Evaluation

Compare against real baselines, not against nothing:

1. one strong model call with full clean context
2. one agent using a conventional ReAct loop
3. fixed planner–executor workflow
4. adaptive hierarchical decomposition
5. adaptive decomposition with model routing

Measure verified task success · partial success · constraint adherence ·
**decomposition quality** · child correctness · synthesis correctness · total
tokens · model calls · tool calls · wall-clock latency · **cost per successful
task** · retry and recovery rate · false completion rate.

Track resource usage by root task, branch, node, model, context category,
retrieval, tool output, synthesis, and verification. Useful derived metrics:
tokens by abstraction layer, repeated prefix tokens, cache-read ratio,
child-result compression ratio, useful-evidence density, calls per completed
node, decomposition overhead, branch cancellation rate, synthesis rework,
parallel speedup.

**Required ablations** — remove each and measure: context isolation · recursion ·
parallelism · the independent verifier · multi-model routing (use one model
everywhere) · tool-use code execution · structured artifacts (pass full child
histories instead) · adaptive depth (use fixed depth) · replanning.

> The architecture is justified only when its measured gains exceed its
> orchestration overhead — on your model and your tasks `[EB §1]`.

---

## §13 What is genuinely open, and where the sources disagree

### Open questions

1. **Back-revision is not standard.** Blackboards support it; mainstream agent
   frameworks default to forward-only pipelines. The `invalidates` field in §4.2
   is a reasonable design, but it is **a proposal, not a cited standard**.
2. **No benchmark measures compositions like this** `[EB §11]`. Published results
   are per-technique. The combined pipeline's behavior on long-horizon repository
   work is unmeasured.
3. **Harness gains don't transfer across models** `[EB §1]`. Decomposition
   granularity that suits one model will not suit another — and ADaPT's own
   finding that decomposition should adapt to *executor capability* says the same
   thing from the other direction.
4. **The meta-level calls must pay for themselves.** Decomposer + revision gate +
   synthesis are pure overhead on tasks a single call would have solved.

### Where the two source documents disagree

**On enthusiasm.** The GPT-5.6 document concludes the pattern is demonstrated and
recommends a full hierarchical decomposition runtime as *"the most promising
architecture."* The Opus 5 document reaches the same factual verdict — every stage
is implemented — but frames adoption around cost and the coding caveat, and
recommends ADaPT-style conditional recursion as the default with the blackboard
built last.

These are compatible on facts and different in posture. The Opus framing is
better supported here for one specific reason: this project is a coding and chat
agent, and the published evidence for orchestrator-worker decomposition
explicitly excludes tightly interdependent coding tasks `[EB §7.6]`. That is a
direct hit on the use case, not a general caution.

**On when to decompose.** The GPT document offers a ten-item "when to decompose"
list (§5) that reads as permissive. The Opus document gives one rule: attempt
first, decompose on failure. Both appear in §5 above, but they point in different
directions on an ambiguous task. **If you must pick one, pick ADaPT** — it is the
higher-evidence position `[EB §7.3]`, and the permissive list is best used as a
*post-hoc check on a decomposition you already decided to make*, not as a trigger.

### The honest bottom line

The described system is not speculative — explicit sub-question generation,
sequential least-to-most solution, recursive decomposition, isolated worker
contexts, parallel research branches, tool-backed sub-problem solving, compiled
task DAGs, context-decoupled planner and executor roles, and hierarchical
synthesis have all been demonstrated individually and in production.

What remains uncommon is a single general-purpose implementation combining all of
them cleanly while maintaining token efficiency, durability, security,
observability, and user control.

The promising version is not "many agents talking." It is:

> A durable hierarchical computation graph in which models dynamically create and
> solve bounded questions, each question receives a purpose-built context, tools
> produce evidence-bearing artifacts, and higher layers integrate only verified
> results while retaining the ability to retrieve underlying detail.

And the honest qualifier on that: **for a coding agent, build it conditionally
(attempt first, decompose on failure), decompose along genuinely separable axes,
reserve parallelism for read-only exploration, and measure the total-token cost
against a single-call baseline before believing any of it.**
