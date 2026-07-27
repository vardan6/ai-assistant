# Hierarchical decomposition and isolated reasoning for AI agents — 2026

> **Authored:** 2026-07-25 23:21 (+04) by GPT-5.6 (`gpt-5.6-sol`), reasoning
> effort: low, via Codex CLI 0.145.0. Verified against the Codex session
> rollout (`019f9a93`, `reasoning_effort: low` throughout), which supersedes the
> self-reported "system-managed / not exposed" line below.  
> **Research date:** 2026-07-25  
> **Model:** Codex (GPT-5)  
> **Reasoning effort:** System-managed; exact setting not exposed to the agent  
> **Scope:** Multi-level problem decomposition, isolated subproblem contexts,
> recursive refinement, tool-supported evidence gathering, dependency-aware
> scheduling, and final synthesis in modern AI agents.  
> **Status:** Research and architectural guidance. This is not a project
> decision, requirement, or implementation plan.

## Executive answer

Yes. The proposed pattern is already implemented in research systems,
production research agents, agent frameworks, and modern coding assistants.
It appears under several related names:

- problem or task decomposition
- least-to-most reasoning
- self-ask
- decomposed prompting
- planner–executor architecture
- orchestrator–worker architecture
- hierarchical agents
- recursive decomposition
- task-DAG execution
- Tree of Thoughts
- Graph of Thoughts
- context-decoupled planning and execution
- multi-agent research
- recursive language models

These names do not all describe the same mechanism. A complete implementation
combines three distinct operations:

1. **Decompose:** turn a high-level problem into explicit questions,
   dependencies, and success conditions.
2. **Isolate:** solve each question with its own small, relevant context and
   local loop.
3. **Compose:** validate and combine the resulting artifacts into higher-level
   conclusions.

The recommended design is a **hierarchical decomposition runtime with isolated
context frames and evidence-bearing synthesis**.

It should not blindly split every task. Decomposition has coordination cost,
and incorrect decomposition can destroy dependencies that a single model call
would have handled naturally. The runtime should decompose only when the
expected gain in focus, parallelism, retrieval quality, verification, or model
routing exceeds that cost.

## The proposed reasoning pattern

The user's example can be represented as:

```text
High-level objective
    |
    +-- Question A
    |       |
    |       +-- A.1
    |       +-- A.2
    |       +-- A.3
    |       |
    |       +-- synthesize answer A
    |
    +-- Question B
    |       |
    |       +-- iterative LLM calls
    |       +-- selected tool calls
    |       +-- synthesize answer B
    |
    +-- Question C
            |
            +-- local investigation
            +-- synthesize answer C

Answers A + B + C
    |
    +-- cross-check dependencies and contradictions
    +-- retrieve missing evidence if necessary
    +-- final reasoning, decision, or implementation
```

Each node may have:

- a different objective
- a different context
- a different model
- a different reasoning effort
- different tools and permissions
- a local token and time budget
- its own children
- a structured output contract
- independent verification

The graph is discovered progressively. The controller does not need to know all
lower-level questions before work begins.

## Terminology

### Goal

The user-visible outcome to achieve.

### Question

An uncertainty whose answer affects the solution.

### Task

Work that produces an artifact or changes the environment.

### Subgoal

An intermediate state required for the parent goal.

### Context frame

The bounded input assembled for one model invocation or local worker loop.

### Artifact

A durable output such as a finding, decision, file, patch, dataset, test result,
or evidence bundle.

### Dependency

A relationship indicating that one question or task requires another result.

### Synthesis

The operation that combines child results into a parent-level conclusion.

### Refinement

Further decomposition of a node whose current formulation is not directly
solvable.

### Blackboard

External shared state containing task structure, artifacts, evidence,
decisions, and progress without copying every detail into every model context.

## Existing approaches

### Least-to-most prompting

Least-to-most prompting first decomposes a difficult problem into simpler
subproblems and then solves them sequentially. Answers to earlier subproblems
are made available to later ones.[^least-to-most]

It closely matches:

```text
identify questions
    -> answer first question
    -> use its answer for the next question
    -> compose the final answer
```

Strengths:

- explicit dependency ordering
- improved compositional generalization in its evaluated tasks
- simple implementation

Limitations:

- usually assumes a mostly linear sequence
- may accumulate prior answers into a growing context
- decomposition quality determines solution quality

### Self-ask

Self-ask makes the model explicitly generate follow-up questions, answer them,
and then answer the original question. It can route follow-up questions to a
search engine or other external tool.[^self-ask]

This directly supports:

```text
Question:
    Is a follow-up needed?
    -> formulate follow-up
    -> retrieve or reason
    -> store intermediate answer
    -> repeat
    -> produce final answer
```

Self-ask is useful when required subquestions cannot be enumerated in advance.

### Decomposed prompting

Decomposed prompting separates a complex task into modular subtask prompts.
Different subtasks can use specialized prompts or symbolic modules such as
information retrieval.[^decomposed-prompting]

Its architectural contribution is important: decomposition does not merely
produce a longer chain of thought inside one prompt. It creates modular
components with distinct interfaces.

### Planner–executor

A planner produces tasks or a plan; executors perform them. The planner may
then revise the remaining plan based on actual results.

This reduces the need for a high-capability model to participate in every
low-level action. The planner can operate at high abstraction while workers
use focused contexts.

### ReWOO

ReWOO separates planning from tool observations. It plans tool dependencies
before execution, performs tool work, and then uses collected evidence for
synthesis. In its reported HotpotQA experiment it achieved five-times token
efficiency and a four-percentage-point accuracy improvement over the compared
baseline.[^rewoo]

It is useful when:

- tool dependencies can be predicted in advance
- intermediate observations do not require immediate semantic replanning
- repeated planner calls would be wasteful

It is less suitable when each tool result fundamentally changes what should be
done next.

### LLMCompiler

LLMCompiler represents function calls as an execution plan and schedules
dependency-ready operations in parallel. Its major components are:

- function-calling planner
- task-fetching and scheduling unit
- parallel executor

The paper reports latency, cost, and accuracy gains over ReAct on its evaluated
tasks.[^llmcompiler]

This is close to compiling an LLM-generated plan into an executable task DAG.

### As-needed recursive decomposition

ADaPT decomposes a task only when the current executor cannot solve it. This
creates multi-level task trees whose depth adapts to task difficulty and model
capability.[^adapt]

This avoids always decomposing to a predetermined depth.

The key policy is:

```text
try to solve atomically
    |
    +-- success -> return artifact
    |
    +-- insufficient information -> retrieve or ask
    |
    +-- still too complex -> decompose into children
```

### Tree of Thoughts

Tree of Thoughts explores several candidate reasoning paths, evaluates them,
and can look ahead or backtrack.[^tree-of-thoughts]

It addresses a different need from ordinary task decomposition:

- task decomposition separates parts of a problem
- Tree of Thoughts explores alternative solutions to the same problem

Use it when early reasoning choices are uncertain and alternatives can be
scored. Do not use it by default: generating and evaluating many branches can
be expensive.

### Graph of Thoughts

Graph of Thoughts treats intermediate model outputs as graph nodes that can be
combined, refined, or connected through dependency edges.[^graph-of-thoughts]

It supports:

- multiple answers feeding one synthesis
- one answer being refined by several operations
- feedback cycles
- aggregation of parallel reasoning

This is conceptually close to the proposed architecture, but production agents
also need durable execution, tools, permissions, budgets, and side-effect
handling beyond the thought graph itself.

### Context-decoupled hierarchical agents

CoDA describes a shared LLM operating in two contextually isolated roles:

- a high-level planner using concise strategic context
- a low-level executor using an ephemeral tool-interaction workspace

This is a direct research example of separating abstraction levels and context
windows rather than passing the complete history between them.[^coda]

### Recursive context-aware planning

ReCAP uses recursive planning, executes the next subtask, and refines remaining
work while reinjecting structured parent information. Its design bounds active
context relative to recursion depth rather than carrying a flat complete
history.[^recap]

### Recursive models

Recent recursive-model research treats self-invocation as a core primitive:
the model can call isolated child instances to solve subproblems and then
compose their results. The theoretical motivation is that recursive
decomposition can keep active context much smaller than a single flat
sequence.[^recursive-models]

The practical implementation still needs strict recursion limits, budgets,
typed results, and verification.

## Production use

### Anthropic Research

Anthropic's production research system uses a lead agent to plan research and
create parallel subagents. Each subagent has its own context window, explores a
focused portion of the problem, and returns a condensed result to the lead.
Anthropic describes this as a form of compression: detailed exploration occurs
outside the lead context, and only important tokens return.[^anthropic-research]

This demonstrates several requested properties:

- high-level orchestration
- dynamic subquestion generation
- separate worker contexts
- parallel exploration
- evidence collection
- compressed return artifacts
- final synthesis by a lead agent

Anthropic reports a 90.2% improvement over a single-agent baseline on its
internal research evaluation. This result is specific to that evaluation and
does not imply that multi-agent architecture is universally superior.

### OpenAI Deep Research

OpenAI Deep Research creates a research plan, performs multi-step search and
analysis, refines queries, aggregates sources, and produces a cited
synthesis.[^openai-deep-research][^openai-research]

Public documentation does not expose every internal scheduling or context
implementation detail, but the product behavior demonstrates:

- planning
- subquestion-oriented investigation
- iterative retrieval
- source evaluation
- synthesis
- user steering and interruption

### Modern coding agents

Coding agents commonly use the same pattern in less explicit form:

```text
understand task
    -> inspect project instructions
    -> identify relevant modules
    -> investigate likely cause
    -> implement a bounded change
    -> run focused tests
    -> inspect failure
    -> revise
    -> run broader verification
    -> summarize
```

Modern subagent systems can isolate repository investigation, test-log
analysis, security review, or documentation lookup from the main coding
context.

## The recommended architecture

### Overview

```text
User objective
      |
      v
+------------------------+
| Goal interpreter       |
| contract + constraints |
+-----------+------------+
            |
            v
+------------------------+
| Decomposition planner  |
| questions + tasks      |
+-----------+------------+
            |
            v
+------------------------+
| Graph admission        |
| validate + budget      |
+-----------+------------+
            |
            v
+--------------------------------------------------+
| Dependency-aware scheduler                       |
|                                                  |
|  branch A             branch B          branch C |
|  local context        local context     local ctx |
|  recursive loop       tools + model     one call  |
+-------+-------------------+------------------+-----+
        |                   |                  |
        v                   v                  v
   artifact A          artifact B         artifact C
        |                   |                  |
        +-------------------+------------------+
                            |
                            v
                  +--------------------+
                  | Integration pass   |
                  | conflicts + gaps   |
                  +---------+----------+
                            |
                  missing evidence?
                     |             |
                    yes            no
                     |             |
                refine graph       v
                              final verifier
                                   |
                                   v
                             final response
```

### Separate control state from reasoning content

The runtime owns:

- graph structure
- task status
- dependencies
- budgets
- retry counts
- permissions
- side-effect records
- artifact locations
- trace identifiers

The LLM owns probabilistic decisions:

- how to decompose
- which uncertainty matters
- what evidence is relevant
- whether a result answers the local question
- how child results affect strategy
- how to synthesize conclusions

Do not ask the LLM to remember the authoritative graph in prose.

### Typed node model

```yaml
id: investigate_cache_behavior
kind: question
parent_id: design_token_efficiency
objective: Determine how caching affects dynamic context construction
why_needed: Required to compare one large call with several smaller calls
dependencies:
  - identify_provider_cache_semantics
context_profile: provider_research
executor_profile:
  model_tier: balanced
  reasoning_effort: medium
  tools:
    - web_search
    - web_open
budgets:
  input_tokens: 12000
  output_tokens: 1500
  calls: 5
  wall_time_seconds: 180
completion_contract:
  output_schema: ResearchFinding
  requires_sources: true
  minimum_independent_sources: 2
status: ready
```

### Typed result model

```yaml
node_id: investigate_cache_behavior
status: answered
summary: Static prefixes can be reused while dynamic stage context is appended
claims:
  - text: Cache matching depends on stable prompt prefixes
    confidence: high
    evidence_ids: [openai_prompt_cache, gemini_implicit_cache]
artifacts:
  - id: openai_prompt_cache
    uri: https://example.invalid/source
open_questions:
  - How should cache keys be partitioned at high request volume?
recommendation:
  - Keep constitution and stable tool summaries before stage-local context
```

The parent receives this compact result rather than the child's entire
conversation.

## Decomposition policies

### When to decompose

Decompose when one or more apply:

- the task contains separable questions
- different sources or tools are required
- different expertise or models are beneficial
- the working set would otherwise become too large
- branches can run independently
- independent verification is valuable
- one subproblem is blocking progress
- the task spans multiple abstraction levels
- the current worker repeatedly fails
- success criteria can be divided into independently checkable parts

### When not to decompose

Keep the task together when:

- it is directly solvable in one call
- the parts are tightly coupled
- each branch would need almost the same complete context
- synthesis would be harder than direct reasoning
- the cost of coordinating branches exceeds their value
- latency is more important than marginal accuracy
- side effects require strict sequential control
- decomposition would obscure a small, coherent change

### Atomicity test

A node is sufficiently atomic when a selected executor can likely finish it
within:

- one bounded reasoning objective
- one coherent working context
- a small tool-use loop
- one output contract
- one verification method

A node does not have to map to one LLM call. It may own a short local loop.

### As-needed recursion

Prefer adaptive recursion:

```text
attempt local solution
    |
    +-- enough evidence and confidence -> verify and return
    |
    +-- missing external information -> retrieve
    |
    +-- local task remains too broad -> create children
    |
    +-- missing user decision -> pause and ask
```

Set limits for:

- maximum depth
- maximum children per node
- maximum total nodes
- maximum active branches
- maximum repeated decomposition
- total tokens, cost, and time

## Context isolation

### Parent frame

Contains:

- global goal
- global constraints
- current strategy
- compact child statuses
- accepted child conclusions
- conflicts and open questions

It should not contain:

- raw child tool logs
- every document read by children
- exploratory child reasoning
- rejected hypotheses unless globally relevant

### Child frame

Contains:

- local objective
- why the objective matters
- relevant parent constraints
- dependency outputs
- selected evidence
- local tools
- output schema
- local budget

It should not automatically contain sibling histories.

### Synthesis frame

Contains:

- original goal and acceptance criteria
- structured child outputs
- citations and evidence references
- contradictions
- missing coverage
- required final format

It may retrieve underlying artifacts when a summary is insufficient.

### Verification frame

Contains:

- claim or artifact to verify
- success criteria
- observable environment state
- relevant tests or sources

Where possible, omit the generator's persuasive rationale so the verifier
forms a more independent judgment.

## Scheduling

### Sequential branches

Use when later questions depend on earlier answers:

```text
A -> B(A) -> C(A, B) -> synthesis
```

This is least-to-most reasoning.

### Parallel branches

Use when questions are independent:

```text
        +-> A -+
root ---+-> B -+-> synthesis
        +-> C -+
```

Each branch can use an isolated context and potentially a different model.

### Hybrid scheduling

Most real problems require both:

```text
        +-> A1 -> A2 -+
root ---+-> B --------+-> integrate -> gap D -> final
        +-> C1 -> C2 -+
```

The scheduler should dispatch every ready node whose dependencies are satisfied
and whose concurrency, permission, and budget constraints permit execution.

### Speculative work

The runtime may begin a likely branch before an upstream decision completes if:

- probability of usefulness is high
- the branch is read-only
- cost is low
- cancellation is supported
- its result cannot create an external side effect

## Iteration within a subproblem

A child node may use several calls:

```text
local orient
    -> generate candidate answer
    -> identify missing evidence
    -> retrieve or use tools
    -> revise
    -> verify
    -> emit compact artifact
```

The child owns this temporary history. Only its structured artifact returns to
the parent.

Use a new call when:

- new evidence materially changes the question
- an independent critic is warranted
- a cheaper extractor can process raw material
- the current call would otherwise exceed its context budget

Use code rather than another LLM call for deterministic transformations.

## Model routing by abstraction

Different levels can use different models:

| Layer | Suggested model profile |
|---|---|
| Goal interpretation | Strong, instruction-faithful |
| Strategic decomposition | Strongest available when task is complex |
| Routine extraction | Small or fast model |
| Search-query generation | Fast model |
| Local coding | Strong coding model |
| Data transformation | Deterministic code first |
| Independent review | Strong model, potentially a different family |
| Final synthesis | Strong model with evidence-rich context |

Routing must be evaluated. A cheap worker that returns an incorrect artifact can
make downstream synthesis more expensive than using a strong model initially.

## Evidence and provenance

Every child conclusion should identify:

- source or environment observation
- retrieval time
- applicable scope
- confidence
- contradictions
- whether the evidence is direct or inferred

The synthesis layer should never receive unsupported prose as if it were a
verified fact.

For coding tasks, evidence can include:

- file paths and symbols
- commit identifiers
- command and exit status
- failing and passing test names
- diff hashes
- screenshots
- API responses

## Synthesis

Synthesis is not ordinary summarization.

It should:

1. Map each child result to the parent question.
2. Check that all parent success criteria are covered.
3. Resolve or expose contradictions.
4. Distinguish evidence from inference.
5. Detect dependency mismatches.
6. Identify missing information.
7. Trigger additional nodes if evidence is insufficient.
8. Produce a conclusion at the parent's abstraction level.

The synthesis result should be reusable as a child artifact of the next level.

### Hierarchical information compression

```text
raw sources and logs
    -> evidence records
    -> child findings
    -> branch conclusions
    -> strategic decision
    -> user-facing result
```

Each layer reduces detail while retaining references back to the underlying
artifacts. This prevents irreversible information loss.

## Error recovery

Classify failures:

- **execution failure:** a tool or service failed
- **evidence failure:** required information was not found
- **reasoning failure:** result contradicts known facts
- **decomposition failure:** children do not collectively answer the parent
- **integration failure:** child results conflict
- **budget failure:** additional work exceeds limits
- **authority failure:** user input or approval is required

Recovery actions:

- retry transient execution failures
- reformulate retrieval for evidence failures
- use an independent solver for reasoning failures
- revise the task graph for decomposition failures
- create a conflict-resolution node for integration failures
- degrade scope or ask the user for budget failures
- pause durably for authority failures

Do not restart the entire problem unless durable state is corrupt.

## Token and latency controls

Track resource usage by:

- root task
- branch
- node
- model
- context category
- retrieval
- tool output
- synthesis
- verification

Useful metrics:

- total tokens per successful task
- tokens by abstraction layer
- repeated prefix tokens
- cache-read ratio
- child-result compression ratio
- useful-evidence density
- calls per completed node
- decomposition overhead
- branch cancellation rate
- synthesis rework
- parallel speedup

### Branch admission

Before creating a branch, estimate:

```text
expected value =
    probability branch changes or validates result
  * value of improved correctness
  + expected parallel latency reduction
  + expected context reduction
  - model and tool cost
  - coordination cost
  - synthesis complexity
```

The estimate need not be numerically precise. Its purpose is to prevent
unbounded "thinking for the sake of thinking."

## Verification

Verification should occur at two levels.

### Local verification

Does the child result satisfy its node contract?

Examples:

- Does the cited source support the claim?
- Does the focused test pass?
- Does the query return the required fields?
- Does the result obey its schema?

### Global verification

Does the integrated result satisfy the root contract?

Examples:

- Are all user questions answered?
- Do child results contradict each other?
- Does the complete test suite relevant to the change pass?
- Were all requested constraints preserved?
- Were side effects authorized and recorded?

A set of locally correct answers can still compose into an incorrect global
answer. Self-ask research calls this the compositionality gap.[^self-ask]

## Evaluation

Compare at least these baselines:

1. one strong model call with full clean context
2. one agent using a conventional ReAct loop
3. fixed planner–executor workflow
4. adaptive hierarchical decomposition
5. adaptive decomposition with model routing

Measure:

- verified task success
- partial success
- constraint adherence
- decomposition quality
- child correctness
- synthesis correctness
- total tokens
- model calls
- tool calls
- wall-clock latency
- cost per successful task
- retry and recovery rate
- false completion rate

### Required ablations

- no context isolation
- no recursion
- no parallelism
- no independent verifier
- one model for every layer
- no tool-use code execution
- full child histories instead of artifacts
- fixed decomposition depth
- no replanning

The architecture is justified only when its measured gains exceed orchestration
overhead.

## Risks and failure modes

### Incorrect decomposition

The planner divides a tightly coupled problem into apparently independent
branches.

Mitigation:

- explicit dependency modeling
- integration checks
- allow workers to report hidden dependencies

### Over-decomposition

The graph contains many trivial nodes and coordination dominates work.

Mitigation:

- atomicity tests
- minimum expected value for new branches
- depth and node limits
- combine mechanically related operations

### Under-decomposition

One worker receives a broad task and accumulates a large noisy context.

Mitigation:

- context-budget triggers
- failure-triggered decomposition
- inspect worker progress and evidence density

### Summary corruption

A child artifact omits a detail needed later.

Mitigation:

- structured outputs
- provenance links
- retain original artifacts
- allow parent retrieval into child evidence

### Error propagation

An incorrect early answer becomes an assumption for every dependent node.

Mitigation:

- confidence and evidence fields
- independent verification at high-impact boundaries
- invalidate and recompute descendants when a dependency changes

### Synthesis failure

All child answers are individually plausible, but their composition is wrong.

Mitigation:

- dependency-aware synthesis
- contradiction checks
- global acceptance tests
- independent integration review

### Coordination token explosion

Worker prompts and handoffs cost more than a direct solution.

Mitigation:

- stable cached prefixes
- compact typed artifacts
- deterministic scheduling
- model routing
- admission policy
- total-token evaluation

### Premature finalization

The controller sees several completed children and assumes the root goal is
complete.

Mitigation:

- machine-readable coverage matrix
- explicit root acceptance criteria
- final verifier

## Implementation blueprint

### Core services

1. **Goal interpreter**
   - Produces the root contract.

2. **Capability registry**
   - Lists valid worker, tool, skill, and model capabilities.

3. **Decomposition planner**
   - Produces typed questions and tasks.

4. **Graph validator**
   - Checks dependencies, permissions, budgets, and completion coverage.

5. **Scheduler**
   - Runs dependency-ready nodes with bounded concurrency.

6. **Context compiler**
   - Produces a stage-specific context frame.

7. **Worker runtime**
   - Runs a bounded local LLM/tool loop.

8. **Artifact and evidence store**
   - Preserves full results outside model context.

9. **Blackboard**
   - Holds graph state, decisions, progress, and compact accepted findings.

10. **Synthesis engine**
    - Integrates child artifacts and identifies gaps.

11. **Verifier**
    - Checks local and root contracts.

12. **Trace and budget service**
    - Records calls, tokens, cost, latency, and decisions.

### Minimum viable version

Start with:

- one controller model
- one worker model
- typed sequential task lists
- isolated worker contexts
- structured worker results
- artifact references
- one synthesis pass
- strict token, call, depth, and time limits
- local and final verification

Then add, only when evaluation supports them:

- dependency DAGs
- parallel scheduling
- recursive decomposition
- multi-model routing
- alternative-path search
- learned routing
- remote subagents

### Recommended node lifecycle

```text
proposed
    -> admitted
    -> waiting_for_dependencies
    -> ready
    -> running
    -> needs_refinement
       -> children proposed
       -> waiting_for_children
    -> integrating
    -> verifying
    -> completed

Exceptional:
    blocked
    waiting_for_user
    failed_retryable
    failed_terminal
    cancelled
```

### Invalidation

When a child artifact changes:

1. Mark dependent conclusions stale.
2. Cancel dependent work that has not committed useful output.
3. Re-run only affected synthesis and verification nodes.
4. Preserve unrelated completed branches.

This is analogous to incremental build systems.

## Design rules

1. Decompose questions, tasks, and uncertainties explicitly.
2. Keep authoritative graph state outside model conversation history.
3. Give every node one local objective and one output contract.
4. Construct a different context frame for each node.
5. Return structured artifacts rather than full child conversations.
6. Preserve provenance so summaries can be expanded when needed.
7. Use sequential execution for real dependencies and parallel execution for
   independent branches.
8. Recurse only when a node cannot be solved economically at its current
   abstraction.
9. Use models for judgment and code for scheduling and mechanical operations.
10. Verify locally and globally.
11. Replan on evidence, not after every ordinary observation.
12. Optimize total tokens and cost per successful task.
13. Bound recursion, branching, concurrency, calls, time, and money.
14. Require every architectural layer to demonstrate value through ablation.

## Conclusion

The described system is not speculative. Its components have been demonstrated
individually and in production:

- explicit subquestion generation
- sequential least-to-most solution
- recursive decomposition
- isolated worker contexts
- parallel research branches
- tool-backed subproblem solving
- compiled task DAGs
- alternative reasoning search
- context-decoupled planner and executor roles
- hierarchical synthesis

What remains uncommon is a single general-purpose implementation that combines
all of them cleanly while maintaining excellent token efficiency, durability,
security, observability, and user control.

The most promising architecture is not "many agents talking." It is:

> A durable hierarchical computation graph in which models dynamically create
> and solve bounded questions, each question receives a purpose-built context,
> tools produce evidence-bearing artifacts, and higher layers integrate only
> verified results while retaining the ability to retrieve underlying detail.

## Sources

[^least-to-most]: Zhou et al., [Least-to-Most Prompting Enables Complex Reasoning in Large Language Models](https://arxiv.org/abs/2205.10625), 2022.
[^self-ask]: Press et al., [Measuring and Narrowing the Compositionality Gap in Language Models](https://arxiv.org/abs/2210.03350), 2022.
[^decomposed-prompting]: Khot et al., [Decomposed Prompting: A Modular Approach for Solving Complex Tasks](https://openreview.net/pdf?id=_nGgzQjzaRy), ICLR 2023.
[^rewoo]: Xu et al., [ReWOO: Decoupling Reasoning from Observations for Efficient Augmented Language Models](https://arxiv.org/abs/2305.18323), 2023.
[^llmcompiler]: Kim et al., [An LLM Compiler for Parallel Function Calling](https://arxiv.org/abs/2312.04511), 2023.
[^adapt]: Prasad et al., [ADaPT: As-Needed Decomposition and Planning with Language Models](https://arxiv.org/abs/2311.05772), 2023.
[^tree-of-thoughts]: Yao et al., [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601), 2023.
[^graph-of-thoughts]: Besta et al., [Graph of Thoughts: Solving Elaborate Problems with Large Language Models](https://arxiv.org/abs/2308.09687), 2023.
[^coda]: [CoDA: A Context-Decoupled Hierarchical Agent with Reinforcement Learning](https://arxiv.org/abs/2512.12716), 2025.
[^recap]: [ReCAP: Recursive Context-Aware Reasoning and Planning for Large Language Model Agents](https://arxiv.org/abs/2510.23822), 2025.
[^recursive-models]: [Recursive Models for Long-Horizon Reasoning](https://arxiv.org/abs/2603.02112), 2026.
[^anthropic-research]: Anthropic, [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system), 2025-06-13.
[^openai-deep-research]: OpenAI, [Deep research in ChatGPT](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt), accessed 2026-07-25.
[^openai-research]: OpenAI, [Research with ChatGPT](https://openai.com/academy/search-and-deep-research/), accessed 2026-07-25.
