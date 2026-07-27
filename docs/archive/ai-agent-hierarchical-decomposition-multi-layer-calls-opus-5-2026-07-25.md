# Hierarchical decomposition and multi-layer LLM calls — prior art and reference design

> **Authored:** 2026-07-25 23:23 (+04) by Claude Opus 5 (`claude-opus-5`),
> reasoning effort: medium, via Claude Code.
> **Research date:** 2026-07-25
> **Method:** Web survey of primary sources (arXiv, vendor engineering writeups,
> framework documentation). Quantitative claims sourced inline.
> **Question answered:** Is the pattern — decompose into 3–4 sub-goals, answer
> each with its own small LLM calls at its own abstraction level, iterate back
> to revise earlier sub-answers, then tool calls, then final synthesis —
> already implemented in modern agents?
> **Status:** Research and reference. Not a decision, requirement, or plan.
>
> **Siblings:** `agent-perspectives-dynamic-context-smart-graph-feature-surface-2026-07.md`
> (dynamic graph taxonomy, projection, routing) ·
> `agent-harness-benchmarks-and-context-economics-2026-07.md` (measured costs) ·
> `best-ai-agent-architecture-summer-2026.md` · `dynamic-agent-loop-and-platform-perspectives-2026.md`
> · `modern-agent-implementation-attributes.md`

---

## Verdict

**Yes — every individual stage of the described pattern is implemented, named,
published, and in production.** The pattern is not speculative. It has roughly
fifteen years of pre-LLM lineage (blackboard systems, hierarchical task
networks) and four years of LLM-specific literature.

Three qualifications that matter for design:

1. **The stages are named separately and are usually implemented separately.**
   Assembling all of them into one runtime — decomposition + per-subgoal
   abstraction layers + back-revision + tool phase + synthesis — is *less*
   standardized than any single stage. That composition is where genuine design
   work remains.
2. **One stage is materially under-supported: revising an earlier sub-answer
   after later sub-answers arrive.** Most published pipelines are forward-only.
   The mechanism that supports it is the **blackboard**, which is
   well-established but not the default in mainstream agent frameworks.
3. **The strongest published evidence for orchestrator-worker decomposition
   explicitly excludes coding.** Anthropic's own finding: these systems "excel
   at problems that can be divided into parallel strands of research, but are
   **less effective for tightly interdependent tasks such as coding**." Since
   this project is a coding/chat agent, that caveat is load-bearing, not a
   footnote.

---

## 1. The described pattern, mapped to prior art

| Step in the description | Established name | Key reference |
|---|---|---|
| Break the problem into 3–4 sub-goals without solving them first | **Least-to-Most prompting** | [2205.10625](https://arxiv.org/pdf/2205.10625) |
| Route each sub-goal to a specialized handler/module | **Decomposed Prompting (DecomP)** | [DecomP overview](https://www.emergentmind.com/topics/decomposed-prompting) |
| Decompose *further* only when a sub-goal proves too hard | **ADaPT** (as-needed decomposition) | [2311.05772](https://arxiv.org/pdf/2311.05772) |
| Keep high-level goals from being polluted by low-level detail | **Task-decoupled planning** | [2601.07577](https://arxiv.org/pdf/2601.07577) |
| Answer sub-question 1, 2, 3 with separate small calls, each with its own context | **Recursive/hierarchical decomposition**; per-call **projection** | [2511.14772 survey](https://arxiv.org/pdf/2511.14772); [Zylos projection](https://zylos.ai/research/2026-03-17-dynamic-context-assembly-projection-llm-agent-runtimes) |
| Plan all steps up front, defer tool results via placeholders | **ReWOO** | [2305.18323](https://arxiv.org/pdf/2305.18323) |
| Tool calls as a dependency graph, executed in parallel | **LLMCompiler** | [2312.04511](https://arxiv.org/pdf/2312.04511) |
| Run 3–5 sub-investigations in parallel, isolated contexts | **Orchestrator-worker** | [Anthropic multi-agent research system](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them) |
| **Return to sub-question 1 after seeing answers 2 and 3** | **Blackboard architecture** | [2507.01701](https://arxiv.org/pdf/2507.01701), [2510.01285](https://arxiv.org/pdf/2510.01285) |
| Spawn a new specialist when decomposition reveals a gap | **TDAG** (dynamic decomposition + agent generation) | [TDAG, Neural Networks 2025](https://www.sciencedirect.com/science/article/abs/pii/S0893608025000796) |
| Final reasoning and clarification over collected results | **Synthesis pass** (+ separate citation pass) | Anthropic, ibid. |

Nothing in the description is unprecedented. The value is in the composition
and in the operating rules governing it.

---

## 2. The building blocks in detail

### 2.1 Decomposition structures — the taxonomy

The test-time-scaling survey organizes all of this by **subproblem structure**,
which is the right frame for choosing between options:

| Structure | Mechanism | Combination method | Best for |
|---|---|---|---|
| **Sequential** | Ordered steps, each builds on the last | Direct output chaining | Procedural/cumulative reasoning (CoT, Least-to-Most) |
| **Parallel** | Independent subproblems solved simultaneously | Voting, verification | Verification, self-consistency |
| **Tree** | Branching states with backtracking | Search (MCTS, A*) | Creative problem-solving, planning |
| **Graph** | Arbitrary interdependencies between subproblems | Search over the graph | Multi-step planning, coordination |
| **Recursive/hierarchical** | Subdivide into similar smaller problems at different abstraction levels | Compositional assembly | **Compositional reasoning and tool use** |

[Test-time scaling: a survey from a subproblem structure perspective (2511.14772)](https://arxiv.org/pdf/2511.14772)

The described pattern is **recursive/hierarchical with graph-shaped revision
edges** — the last row plus back-edges. The survey confirms the hierarchical row
is the one aligned with tool use, which is the relevant regime for a coding
agent.

### 2.2 Least-to-Most — decompose before solving

The foundational move, and the one the description starts with: **prompt the
model to break the problem into sub-problems *without solving them*, then solve
sequentially**, appending each answer to the prompt for the next. Reported gains
on symbolic manipulation, compositional generalization, and math.
[2205.10625](https://arxiv.org/pdf/2205.10625)

Design note: the separation of "decompose" from "solve" is the point. A model
asked to do both at once entangles them — which is precisely the failure the
task-decoupled planning paper names (§2.4).

### 2.3 DecomP — heterogeneous handlers per sub-task

DecomP upgrades Least-to-Most in the direction the description implies: it
introduces **notations representing program state** so that sub-tasks can be
dispatched to **heterogeneous modules** — a shared library of prompting-based
LLMs, each specialized to one sub-problem type. Sub-tasks can be handled by
different specialists rather than the same generalist prompt.

This is the mechanism for "different LLMs for different layers of abstraction":
the module registry is where model choice per sub-task lives.
[Decomposed prompting](https://www.emergentmind.com/topics/decomposed-prompting) ·
[Advanced decomposition techniques](https://learnprompting.org/docs/advanced/decomposition/introduction)

### 2.4 Task-decoupled planning — "do not fix lower-level questions"

This paper addresses exactly the concern stated in the question: **entangled
planning**, where task planning and action execution become intertwined, causing
inefficient exploration and difficulty decomposing objectives.

The architecture separates:
- **High-level task planning** — semantic decomposition
- **Low-level action execution** — concrete behavioral implementation
- The layers stay **independent yet coordinated through intermediate
  representations**

Critically: **feedback loops enable plan refinement without full replanning.**
Reported improvements on long-horizon benchmarks in success rate and planning
efficiency.
[Beyond Entangled Planning (2601.07577)](https://arxiv.org/pdf/2601.07577)

**This is the formal justification for the instinct that high-level goals should
not be committed to low-level answers.** The intermediate representation is the
contract between layers, and it is what lets a lower layer fail or change
without invalidating the upper plan.

### 2.5 ADaPT — decompose recursively, but only on failure

The most important result for cost control, because it makes decomposition
**conditional rather than unconditional**:

- An LLM **executor** attempts the sub-task.
- A self-generated **success heuristic** judges completion.
- On failure, the **planner** recursively decomposes that sub-task further and
  the controller calls itself.

So the tree deepens *only where the executor actually failed* — depth adapts to
both task complexity and the executor model's capability.

| Benchmark | Improvement over ReAct / Plan-and-Execute |
|---|---|
| ALFWorld | **+28.3 pts** (absolute) |
| WebShop | **+27 pts** |
| TextCraft | **+33 pts** |

[ADaPT (2311.05772)](https://arxiv.org/pdf/2311.05772) ·
[ACL Findings NAACL 2024](https://aclanthology.org/2024.findings-naacl.264/)

**Adopt this rule.** Fixed-depth decomposition pays the full decomposition cost
on every task including easy ones; ADaPT pays it only where needed, and the
paper's own analysis establishes that multilevel decomposition matters *and*
that it should adapt to executor capability.

### 2.6 ReWOO — decouple reasoning from observation

Directly relevant to the "tool calls come later" part of the description.

Instead of an LLM call after every tool use (ReAct), ReWOO plans **all** steps
up front using **placeholders** (`#E1`, `#E2`) for results not yet obtained,
executes the tools, then integrates.

**Result: 2 LLM calls (plan + integrate) regardless of the number of tools.**

The cost saving is structural — the observation text never re-enters a reasoning
prompt, so context doesn't grow with tool count.
[ReWOO (2305.18323)](https://arxiv.org/pdf/2305.18323) ·
[NVIDIA NeMo Agent Toolkit — ReWOO agent](https://docs.nvidia.com/nemo/agent-toolkit/1.2/workflows/about/rewoo-agent.html) ·
[Agent Patterns — ReWOO](https://agent-patterns.readthedocs.io/en/stable/patterns/rewoo.html)

Tradeoff to weigh honestly: planning blind (before any observation) is brittle
when the environment is unknown. ReWOO suits *predictable* tool sequences; a
codebase you haven't explored yet is not that. The hybrid is to use ReWOO-style
batching **within** a sub-goal whose shape is already known.

### 2.7 LLMCompiler — sub-tasks as a parallel DAG

The execution-layer counterpart:

- **Planner** streams a **DAG of tasks**, each with a tool, arguments, and
  dependency list.
- **Task Fetching Unit** schedules and dispatches each task the moment its
  dependencies resolve.

Reported **3.6× speedup**, exceeding plan-and-execute, ReWOO, and native
parallel tool calling, while reducing redundant LLM calls.
[LLMCompiler (2312.04511)](https://arxiv.org/pdf/2312.04511) ·
[LangChain — plan-and-execute agents](https://blog.langchain.com/planning-agents/)

**Design consequence:** sub-goals should be emitted with **explicit
dependencies**, not as a flat list. A flat list forces sequential execution; a
dependency list lets the scheduler extract parallelism for free. This is a
cheap decision at design time and expensive to retrofit.

### 2.8 Orchestrator-worker — the production data point

Anthropic's Research system is the best-documented production instance:

- Lead agent plans, spawns **3–5 specialized subagents in parallel**, each with
  **its own context window, tools, and trajectory**
- Parallelism at **two levels**: parallel subagents, and parallel tool calls
  within each subagent
- A **separate citation pass** after synthesis

| Metric | Value |
|---|---|
| vs. single-agent Claude Opus 4 (internal eval) | **+90.2%** |
| Token cost | **~15× a normal chat** |
| Research time reduction on complex queries | **up to 90%** |

[Anthropic — when to use multi-agent systems](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them) ·
[ByteByteGo breakdown](https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent) ·
[ZenML LLMOps database entry](https://www.zenml.io/llmops-database/building-a-multi-agent-research-system-for-complex-information-tasks)

**The 15× multiplier is the honest price of this pattern**, and it justifies the
architecture only when outcome value clearly exceeds it. Note the separate
citation pass — a deliberate choice to make one verifiable concern its own
layer rather than folding it into synthesis.

### 2.9 Blackboard — the mechanism for revising earlier sub-answers

This is the answer to the part of the description that forward-only pipelines
cannot express: *"based on these three answers, do one more iteration to answer
the first sub-question."*

A **blackboard** is a shared, globally accessible structured workspace holding
the problem definition, all intermediate partial solutions, active hypotheses,
and goal criteria. It **incrementally accumulates** hypotheses, constraints, and
partial results, all visible to every participant.

Properties that matter here:

- **Indirect coordination** — agents interact through shared state, not by
  messaging each other. Adding a revision step doesn't require rewiring
  anything.
- **Opportunistic control** — a central agent posts a request; specialists
  monitoring the board decide whether they can contribute. Control order is not
  fixed in advance.
- **Write–Critique–Refine loop** over the shared state, with adversarial
  perspectives cross-checking; reported to reduce hallucination.
- Suited to problems where **structure emerges during computation** — which is
  exactly the case when answering sub-questions 2 and 3 changes what
  sub-question 1 means.

[Exploring advanced LLM multi-agent systems based on blackboard architecture (2507.01701)](https://arxiv.org/pdf/2507.01701) ·
[LLM-based multi-agent blackboard system for information discovery (2510.01285)](https://arxiv.org/pdf/2510.01285) ·
[PatchBoard — schema-grounded state mutation for auditable collaboration (2605.29313)](https://arxiv.org/pdf/2605.29313) ·
[ARIADNE — blackboard-driven MCTS for competitive program generation (2605.02431)](https://arxiv.org/pdf/2605.02431) ·
[Theater of Mind — cognitive architecture based on Global Workspace Theory (2604.08206)](https://arxiv.org/html/2604.08206v1)

**PatchBoard is worth specific attention** for an implementation: schema-grounded
*state mutation* gives the revision step an auditable, typed form rather than
free-text overwriting — which is what makes back-revision debuggable instead of
chaotic.

### 2.10 TDAG — generating the specialist when the gap appears

Dynamic task decomposition paired with **agent generation**: rather than routing
sub-tasks to a fixed roster, the system generates the specialist the
decomposition calls for. Positioned explicitly as a mitigation for **error
propagation in fixed decomposition schemes**.
[TDAG](https://www.sciencedirect.com/science/article/abs/pii/S0893608025000796) ·
[Dynamic task decomposition](https://www.emergentmind.com/topics/dynamic-task-decomposition)

---

## 3. Reference design

Synthesizing the above into an architecture that can actually be built. Five
layers, each with a defined contract.

### 3.1 Layer structure

```
L0  INTAKE          raw request + first-pass answer/analysis
        │
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
        │           + separate verification/citation pass
        ▼
      OUTPUT
```

### 3.2 The sub-goal contract

The single most important design object. Make it typed and explicit — this is
what keeps layers decoupled (§2.4) and what enables scheduling (§2.7).

```yaml
subgoal:
  id: sg-1
  question:        # the thing to answer, self-contained
  abstraction:     strategic | structural | local | mechanical
  depends_on:      [sg-0]        # enables the parallel DAG
  provides:        [contract]    # what later sub-goals may rely on
  model_tier:      frontier | mid | small | none(code)
  tools_allowed:   [...]         # least privilege per sub-goal
  context_spec:    # the projection, NOT the whole transcript
    include:       [goal, constraints, sg-0.answer, files:auth/*]
    exclude:       [raw_tool_logs, user_chat_history]
  budget:
    max_calls:     3
    max_tokens:    8000
    max_depth:     2             # ADaPT recursion limit
  answer_schema:   # structured output contract
    answer:        str
    confidence:    float
    invalidates:   [subgoal_id]  # ← the back-revision trigger
    raised_constraints: [str]
  status:          open | answered | reopened | abandoned
```

Two fields carry disproportionate weight:

- **`invalidates`** — this is what makes back-revision *declarative* rather than
  a vague "reconsider everything" pass. A sub-solver that discovers something
  contradicting an earlier answer names it. The revision gate then reopens
  exactly that node, not the whole plan.
- **`context_spec`** — the per-call projection. Each sub-solver receives a
  purpose-built view (see the projection model in the sibling doc), not the
  accumulated transcript.

### 3.3 Control rules

**When to decompose at all**
- Task spans multiple files/modules or multiple distinct concerns → yes
- Single localized change with a clear acceptance test → no; decomposition
  overhead exceeds its value
- Uncertain → attempt directly first, decompose on failure (ADaPT)

**When to recurse deeper**
- Only on **executor failure** or explicit low confidence (ADaPT). Never
  unconditionally.
- Hard depth cap (2–3). Depth is where error propagation compounds.

**When to reopen an earlier sub-goal**
- A later answer sets `invalidates: [sg-N]`, **or**
- A later answer raises a constraint contradicting `sg-N`'s stated assumptions
- **Bound it**: max one reopen per sub-goal per cycle, max N reopens total.
  Without a cap this is an infinite loop — the same safeguard the verification
  literature requires (max iterations, per-cycle improvement check, state-hash
  dedup).

**When to spend an LLM call at all**
Do *not* spend one on: conditionals, parsing known structures, sorting,
filtering, joining, counting, dedup, schema validation, mechanical state
transitions, obvious deterministic routing. These are code. This is the same
lever that gave HyEvo its 19× cost reduction — deciding which nodes shouldn't
be inference at all.

**Model tier per layer**
Decomposer and synthesizer: frontier (low volume, high leverage). Sub-solvers:
match tier to sub-goal difficulty. Revision gate: mid tier — it's a
classification, not an essay. Mechanical steps: no model.

### 3.4 What each layer must *not* see

Enforced by `context_spec`, this is where the token savings come from:

| Layer | Must not receive |
|---|---|
| Decomposer | Raw file contents, tool logs |
| Sub-solver | Other sub-goals' internal reasoning; the full user conversation |
| Revision gate | Full sub-solver transcripts — only answers, confidences, raised constraints |
| Tool phase | Reasoning text of any kind |
| Synthesizer | Exploratory dead ends, raw shell output |

---

## 4. Failure modes — read before adopting

The literature on when this pattern *hurts* is as substantial as the literature
on when it helps.

### 4.1 Decomposition quality is the dominant failure source

**Specification and system design issues — including task misinterpretation and
poor decomposition — account for ~41.8% of all multi-agent system failures.**
Sub-tasks sliced too granular or too broad leave downstream solvers with
unfinishable work. Unlike human teams, LLM sub-agents cannot ask clarifying
questions mid-task, cannot read between the lines, and cannot self-correct when
coordination breaks down.
[Why multi-agent LLM systems fail](https://futureagi.substack.com/p/why-do-multi-agent-llm-systems-fail) ·
[The compounding errors problem](https://www.zartis.com/the-compounding-errors-problem-why-multi-agent-systems-fail-and-the-architecture-that-fixes-it/)

**Implication:** the decomposer is the highest-risk component, not the solvers.
Give it the strongest model and evaluate it independently.

### 4.2 Error propagation

If an early sub-task fails, the error propagates and the whole task fails.
Sequential dependency chains multiply this. Mitigations: explicit confidence on
every sub-answer, the revision gate, dependency edges that make propagation
paths visible, and TDAG-style dynamic re-decomposition.
[TDAG](https://www.sciencedirect.com/science/article/abs/pii/S0893608025000796) ·
[Understanding the planning of LLM agents: a survey (2402.02716)](https://arxiv.org/pdf/2402.02716)

### 4.3 Decomposition overhead is real and sometimes decisive

Decomposing requires additional reasoning and generation — extra time and
compute. For tasks split into dozens of sub-tasks, planning becomes constrained
by context length, causing **forgetting of the planning trajectory**.

The arithmetic from the sibling document is worth restating, because it is the
counterargument to "many small calls are always cheaper":

```
One large call:     40,000 in + 4,000 out            =  44,000 tokens
Ten small calls:    10 × (6,000 in + 500 out)        =  65,000 tokens
```

Repeated per-call preamble can make the decomposed version **more** expensive
and slower. Decomposition saves tokens only when each sub-call's context is
genuinely *narrower*, not merely *separate*.

### 4.4 The coding caveat

Anthropic's finding, stated plainly: orchestrator-worker systems "excel at
problems that can be divided into parallel strands of research, but are **less
effective for tightly interdependent tasks such as coding**."

Code changes share state — types, call sites, invariants — so sub-goals are
rarely independent. For a coding agent, this argues for:

- **Decomposition along genuinely separable axes** (investigate auth ‖
  investigate logging), not along artificially split edit tasks
- **Sequential, contract-mediated** implementation once investigation is done
- Reserving parallel workers for **read-only exploration**, where isolation is
  the point and interdependence is low

### 4.5 The 15× multiplier

Orchestrator-worker cost ≈ 15× a normal chat. It buys +90.2% on research-style
tasks. It does not automatically buy anything on tasks that don't decompose.
Measure before assuming.

---

## 5. What is genuinely open

Honest assessment of where this design goes beyond established practice:

1. **Back-revision is not standard.** Blackboards support it; mainstream agent
   frameworks default to forward-only pipelines. The `invalidates` field above
   is a reasonable design, but it is a proposal, not a cited standard.
2. **No benchmark measures compositions like this.** Published results are
   per-technique (ADaPT on ALFWorld, LLMCompiler on parallel tool calls,
   orchestrator-worker on research). The combined pipeline's behavior on
   long-horizon repository work is unmeasured.
3. **Harness gains don't transfer across models** (Harness-Bench). Decomposition
   granularity that suits one model will not suit another — ADaPT's own finding
   that decomposition should adapt to *executor capability* says the same thing
   from the other direction.
4. **The meta-level calls must pay for themselves.** Decomposer + revision gate
   + synthesis are pure overhead on tasks that a single call would have solved.
   The ADaPT rule — attempt first, decompose on failure — is the principled
   answer, and it should be the default.

**Recommended adoption order**, cheapest and best-evidenced first:

1. ADaPT-style conditional recursion (highest evidence, lowest cost)
2. Typed sub-goal contracts with dependency edges (enables everything else)
3. Per-sub-goal context projection (the token win)
4. Parallel tool DAG (the latency win)
5. Blackboard + revision gate (the novel part — build last, measure hardest)

---

## Source index

**Decomposition:**
[Least-to-Most (2205.10625)](https://arxiv.org/pdf/2205.10625) ·
[Decomposed prompting](https://www.emergentmind.com/topics/decomposed-prompting) ·
[ADaPT (2311.05772)](https://arxiv.org/pdf/2311.05772) ·
[ADaPT project page](https://allenai.github.io/adaptllm/) ·
[Task-decoupled planning (2601.07577)](https://arxiv.org/pdf/2601.07577) ·
[Test-time scaling subproblem survey (2511.14772)](https://arxiv.org/pdf/2511.14772) ·
[Divide-and-conquer prompting effectiveness (2402.05359)](https://arxiv.org/pdf/2402.05359) ·
[Advanced decomposition techniques](https://learnprompting.org/docs/advanced/decomposition/introduction)

**Plan/execute and parallelism:**
[ReWOO (2305.18323)](https://arxiv.org/pdf/2305.18323) ·
[LLMCompiler (2312.04511)](https://arxiv.org/pdf/2312.04511) ·
[LangChain plan-and-execute agents](https://blog.langchain.com/planning-agents/) ·
[NVIDIA NeMo — ReWOO agent](https://docs.nvidia.com/nemo/agent-toolkit/1.2/workflows/about/rewoo-agent.html)

**Orchestration and shared state:**
[Anthropic — when to use multi-agent systems](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them) ·
[ByteByteGo — how Anthropic built it](https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent) ·
[Blackboard multi-agent systems (2507.01701)](https://arxiv.org/pdf/2507.01701) ·
[Blackboard system for information discovery (2510.01285)](https://arxiv.org/pdf/2510.01285) ·
[PatchBoard (2605.29313)](https://arxiv.org/pdf/2605.29313) ·
[ARIADNE (2605.02431)](https://arxiv.org/pdf/2605.02431) ·
[Global Workspace cognitive architecture (2604.08206)](https://arxiv.org/html/2604.08206v1) ·
[TDAG](https://www.sciencedirect.com/science/article/abs/pii/S0893608025000796)

**Failure modes:**
[Why multi-agent LLM systems fail](https://futureagi.substack.com/p/why-do-multi-agent-llm-systems-fail) ·
[Compounding errors problem](https://www.zartis.com/the-compounding-errors-problem-why-multi-agent-systems-fail-and-the-architecture-that-fixes-it/) ·
[Planning of LLM agents: a survey (2402.02716)](https://arxiv.org/pdf/2402.02716) ·
[Collaboration, failure attribution, self-evolution in LLM-MAS (2605.14892)](https://arxiv.org/pdf/2605.14892) ·
[SHIELDA — structured exception handling (2508.07935)](https://arxiv.org/pdf/2508.07935) ·
[Harness-Bench (2605.27922)](https://arxiv.org/pdf/2605.27922)
