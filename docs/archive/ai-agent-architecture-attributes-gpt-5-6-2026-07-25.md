# Best AI-agent architecture and attributes — summer 2026

> **Authored:** 2026-07-25 22:52 (+04) by GPT-5.6 (`gpt-5.6-sol`), reasoning
> effort: low, via Codex CLI 0.145.0. Attribution recovered from the Codex
> session rollout on 2026-07-25 23:2x, not self-reported by the original run.  
> **Research date:** 2026-07-25  
> **Model:** Codex (GPT-5)  
> **Reasoning effort:** System-managed; exact setting not exposed to the agent  
> **Scope:** General-purpose coding, chat, research, tool-using, and
> computer-use agents.  
> **Status:** Research and architectural guidance, not a project decision,
> requirement, or implementation plan.

## Executive conclusion

The best general-purpose agent is not a giant prompt attached to a complicated
multi-agent graph. It is a durable, stateful, mostly single-agent runtime with:

- a strong reasoning model acting as the controller
- a simple observe–decide–act–verify loop
- deterministic code around predictable operations
- tools and knowledge loaded only when needed
- a small, curated working context backed by durable external state
- code execution for filtering data and composing tool operations
- checkpointing, resumability, idempotency, and side-effect tracking
- adaptive model and reasoning selection
- verification based on observable results rather than self-confidence
- sandboxing, least privilege, and risk-based approval gates
- complete tracing and continuous task-level evaluation

The central design principle is:

> Keep the world outside the model, keep an accurate working set inside it,
> and give the model cheap ways to inspect the world whenever necessary.

Large context remains useful as headroom and for genuinely global reasoning.
It should not become the agent's database, filesystem, event log, or workflow
engine.

## Recommended architecture

```text
User / trigger
      |
      v
+------------------------------+
| Intent + risk + task router  |
+--------------+---------------+
               |
               v
+----------------------------------------+
| Durable task state                     |
| goal, constraints, plan, progress,     |
| decisions, artifacts, side effects     |
+--------------+-------------------------+
               |
               v
+----------------------------------------+
| Context compiler                       |
| instructions + current state + recent  |
| events + retrieved evidence + tools    |
+--------------+-------------------------+
               |
               v
+----------------------------------------+
| Reasoning agent                        |
| decide -> act -> observe -> verify     |
+------+-------------+-------------+-----+
       |             |             |
       v             v             v
 Tool discovery   Sandboxed     Knowledge/
 and APIs         execution     memory search
       |             |             |
       +-------------+-------------+
                     |
                     v
             Typed observations
                     |
                     v
+----------------------------------------+
| Policy and verification layer          |
| tests, assertions, approvals, budgets  |
+--------------+-------------------------+
               +-- success -> final result
               +-- recoverable failure -> loop
               +-- missing authority -> user
               +-- long wait -> checkpoint/pause
```

The graph should primarily represent durable state transitions. It should not
force every reasoning step through a permanent collection of specialized
agents.

Anthropic's production guidance favors simple, composable patterns and adding
complexity only when evaluation demonstrates a gain. Its distinction is useful:
deterministic workflows for known paths and model-directed agents for genuinely
open-ended paths.[^anthropic-effective-agents]

## Essential qualities

| Quality | Best implementation |
|---|---|
| Goal fidelity | Maintain an explicit goal, constraints, acceptance criteria, and definition of done outside the transcript. |
| Situational awareness | Inspect the actual environment before acting; do not rely solely on remembered descriptions. |
| Autonomy | Continue through normal, reversible work without constant approval. |
| Restraint | Ask when authority, intent, credentials, or an irreversible choice is genuinely missing. |
| Tool competence | Use narrow, typed, well-documented tools with unambiguous names and failure semantics. |
| Recoverability | Checkpoint after meaningful state transitions and resume without repeating committed side effects. |
| Verification | Test or inspect the resulting environment rather than merely reviewing generated text. |
| Context discipline | Assemble a fresh working context for each inference instead of replaying everything. |
| Evidence discipline | Preserve sources, tool results, file locations, versions, timestamps, and uncertainty. |
| Efficiency | Minimize unnecessary model turns, output tokens, tool schemas, and model-visible intermediate data. |
| Adaptability | Select models, reasoning depth, tools, and verification effort according to difficulty and risk. |
| Observability | Trace model turns, retrieval, tool calls, cost, latency, failures, approvals, and state changes. |
| Security | Treat retrieved content and tool output as untrusted data and contain the agent's capabilities. |

## The agentic loop

A strong general-purpose agent loop has eight phases.

### 1. Orient

- Interpret the request.
- Load durable task state.
- Inspect relevant environment state.
- Identify uncertainty, permissions, budgets, and success criteria.

### 2. Compile context

Assemble only what is useful for the next inference:

- stable instructions
- the current task contract
- a compact progress ledger
- recent useful actions
- retrieved evidence
- currently relevant tool definitions

### 3. Choose the next smallest useful action

- Answer directly when no external action is necessary.
- Use ordinary code for deterministic computation.
- Use a tool for environmental information or effects.
- Delegate only when independent parallel work justifies its coordination cost.

### 4. Execute

- Batch independent reads.
- Use a sandboxed program for joins, filtering, polling, pagination, and
  conditional tool workflows.
- Assign idempotency keys to externally visible mutations.

### 5. Observe

Return structured observations:

- status
- changed resources
- durable identifiers
- errors and retry classification
- artifact references
- compact evidence

Large raw results should be stored externally rather than copied into the
model's context.

### 6. Verify

- Compare the resulting environment with the acceptance criteria.
- Run tests, inspect files, query the API, or observe the UI.
- Use an independent evaluator only when its additional cost produces a
  measured quality improvement.

### 7. Update durable state

Record progress, decisions, remaining work, committed side effects, and
verification evidence. Compact the working context when it becomes noisy.

### 8. Terminate correctly

- Finish only after verification.
- Pause durably for long waits.
- Ask the user only for genuinely missing decisions or authority.
- Stop at budget, policy, or safety boundaries.

The loop should enforce explicit limits for elapsed time, model turns, repeated
failures, token spend, tool calls, and irreversible actions. Repeating the same
action without new evidence is a loop defect, not persistence.

## Context and memory architecture

The best design separates several kinds of state instead of calling all of
them "memory."

### Immutable instructions

Keep small, versioned policies and behavioral rules. Preserve a stable prompt
prefix to maximize caching.

### Structured task state

Use an authoritative state object rather than prose chat history:

```yaml
goal:
constraints: []
acceptance_criteria: []
current_phase:
completed_steps: []
open_questions: []
decisions: []
artifact_references: []
side_effect_ledger: []
failure_history: []
budget:
```

This object is the primary source for pause, resume, and recovery.

### Recent working memory

Retain the latest useful messages and a bounded number of recent tool
interactions. Remove repetitive command output and obsolete intermediate
reasoning.

A June 2026 enterprise-agent study found that retaining five recent tool
interactions plus summarization beat full history in its tested workflow:
higher completion with roughly 63% fewer tokens. This is promising but
task-specific evidence, not a universal five-call rule.[^less-context]

### Episodic event log

Maintain an append-only record of actions and observations for:

- debugging
- audit
- replay
- rebuilding summaries
- recovering from compaction mistakes

The log should not automatically be inserted into every prompt.

### Semantic knowledge

Store stable facts, user preferences, project decisions, domain documentation,
and validated procedures. Every item should carry provenance, scope, and
validity or freshness information.

### Artifact store

Keep files, logs, datasets, screenshots, large tool responses, generated
reports, and build output outside the prompt. Put compact metadata and stable
references in context.

### Retrieval indexes

Use retrieval methods together:

1. exact identifiers and paths
2. metadata filters such as tenant, project, source, permissions, version, and
   time
3. lexical or BM25 search for names, error messages, code symbols, and exact
   terminology
4. embeddings for conceptual similarity
5. graph or relationship lookup for dependency questions
6. reranking after broad retrieval
7. agentic search when query reformulation or reference-following is necessary

Embeddings alone are insufficient for exact code symbols, recent state,
negative constraints, permissions, and temporal questions.

Anthropic describes the same shift from bulk preloading toward just-in-time
context: retain lightweight references such as paths, URLs, and stored queries,
then let the agent fetch their contents when relevant.[^anthropic-context]

### Compaction

Compaction must preserve:

- goal and constraints
- user commitments
- decisions and rationale
- current plan and progress
- unresolved failures
- artifact identifiers
- external side effects
- evidence required for later verification

It should remove:

- superseded plans
- repeated observations
- verbose successful command output
- full documents available by reference
- exploration that produced no durable conclusion

Modern APIs provide native compaction that carries important state into a
smaller representation. OpenAI's Responses API supports threshold-based
server-side compaction and explicit standalone compaction.[^openai-compaction]

Compaction is lossy by nature. Preserve the original event log and artifacts
outside the model so the agent can recover omitted detail.

## Tools and token efficiency

Do not expose hundreds of complete tool schemas on every model call.

Use progressive disclosure:

1. Initially show tool namespaces and concise descriptions.
2. Let the model search for the relevant capability.
3. Inject only selected schemas.
4. Keep large tool results in the execution environment.
5. Return a filtered result or artifact reference to the model.

OpenAI's tool-search design defers tool definitions and injects discovered tools
at the end so the cached prefix survives. Its documentation recommends coherent
namespaces, generally containing fewer than ten functions.[^openai-tool-search]

For large tool ecosystems, expose tools as code APIs inside a sandbox. The
agent can write one program that:

- paginates
- filters and aggregates
- joins multiple APIs
- implements branches and retries
- polls until a condition changes
- returns only the relevant result

In Anthropic's published example, on-demand code-based MCP discovery reduced
tool-related context from 150,000 to 2,000 tokens. This is an example rather
than a universal expected reduction, but it demonstrates the architectural
benefit.[^anthropic-code-mcp]

Every tool should provide:

- narrow semantics
- typed inputs and outputs
- clear preconditions and side effects
- stable error codes
- timeouts and cancellation
- idempotency support
- compact default output with optional detail levels
- pagination and server-side filtering
- artifact handles for large output
- machine-verifiable success conditions

Tool design is often more important than clever prompting.

## Speed and cost

The fastest high-quality agent reduces sequential model round trips.

### Stable cached prefixes

Put system instructions, durable policies, examples, and stable tool summaries
first. Put user-specific and rapidly changing content last. Exact-prefix
caching is used by current OpenAI and Gemini APIs.[^openai-cache][^gemini-cache]

Measure cache reads and writes rather than merely enabling caching. A poor
prompt layout or excessive variation in tool schemas can silently destroy the
hit rate.

### Persistent and warm infrastructure

Reuse, where isolation rules permit:

- HTTP/2 or gRPC connections
- database pools
- MCP sessions
- WebSockets
- authenticated browser sessions
- language servers and repository indexes
- warm sandboxes

Start inference before provisioning expensive execution environments. Anthropic
reports substantial time-to-first-token improvements after separating its
model harness from execution environments and provisioning them only when
needed.[^anthropic-managed]

### Parallel work

- Execute independent reads and retrieval in parallel.
- Batch independent tool calls in one model turn.
- Run inexpensive policy checks concurrently when it is safe to cancel later
  work if a check fails.
- Do not parallelize mutations that depend on ordering or shared state.

### Move deterministic control flow out of the model

Do not spend a model round trip on every:

- `if` statement
- loop
- join
- pagination step
- polling interval
- validation rule
- formatting operation

Use code execution or ordinary application code.

### Adaptive model and reasoning routing

Use fast, inexpensive models for:

- classification
- extraction
- simple summarization
- routine tool selection
- deterministic-format transformations

Escalate to the strongest suitable model for:

- ambiguous planning
- hard debugging
- cross-source synthesis
- important review
- recovery from repeated failure

Likewise, use low reasoning effort for routine actions and high effort only
when uncertainty, impact, or complexity requires it. The router must be
evaluated: routing mistakes can cost more than always using one strong model.

### Fewer generated tokens and requests

Generated tokens are commonly the slowest portion of inference. Use concise
model-facing observations, compact schemas, bounded final answers, and one
request for tightly coupled reasoning that would degrade if split.

OpenAI summarizes latency optimization as: process tokens faster, generate
fewer tokens, use fewer input tokens, make fewer requests, parallelize, reduce
perceived waiting, and avoid defaulting to an LLM.[^openai-latency]

### Streaming and background execution

Stream useful progress or partial results for interactive work. Long reasoning
jobs should survive client disconnections and complete through polling,
webhooks, or workflow callbacks.[^openai-background]

## Graph and multi-agent design

The best default is one capable controller plus tools and deterministic
workflow nodes.

Add specialized agents only when:

- independent work can run in parallel
- separate context prevents contamination
- a different model or permission boundary is materially useful
- independent generation and evaluation improve measured quality
- organizational or security isolation requires it

Avoid conversational "agent societies" where agents repeatedly talk to each
other. They multiply tokens, latency, inconsistency, and error propagation.

For long-running creative or coding work, planner–executor–evaluator structures
can help when evaluation criteria are concrete. Anthropic demonstrated gains
from structured artifacts and evaluator feedback, while warning that harness
complexity becomes obsolete as models improve and should be regularly
ablated.[^anthropic-harness]

A production graph needs:

- durable checkpoints
- pause and resume
- error-classified retry policies
- idempotent nodes
- compensation for partial mutations
- human interrupts
- state inspection and replay
- versioned workflow definitions
- migration of in-flight state
- dead-letter handling
- per-node time, token, and cost budgets

LangGraph provides checkpoints, interrupts, state history, and fault-tolerant
execution. Temporal, Dapr, or Restate may be stronger choices when
general-purpose durable workflow semantics are the main requirement rather
than an LLM-specific graph API.[^langgraph-persistence][^openai-durable]

## Coding-agent properties

A coding agent should:

- search before reading entire repositories
- read narrow file ranges and expand on demand
- use language servers, symbol indexes, dependency graphs, AST search, and
  version-control history
- maintain a task ledger separate from chat
- edit incrementally
- run the smallest relevant test first and then broader verification
- inspect existing user changes and preserve unrelated work
- compare the final diff with requirements and architectural decisions
- treat test passage as necessary but not always sufficient
- use browser or visual inspection where behavior is user-facing
- preserve exact build, test, lint, and runtime evidence
- report what was verified and what was not

Repository instructions should use progressive disclosure: a small routing
document at the root with deeper domain instructions loaded only for the area
being changed.

## Computer-use properties

A computer-use agent should prefer, in order:

1. a purpose-built structured API
2. an application SDK or command line
3. DOM and accessibility-tree interaction
4. vision-based GUI interaction

Vision remains necessary for unsupported applications, but is slower and less
reliable. The agent should continuously re-observe after actions rather than
assuming the UI changed as expected.

The limitation remains severe. OSWorld 2.0 reports only 20.6% full completion
for its best evaluated setup on very long real-world workflows. Important
failure modes included losing constraints, missing changing information,
guessing instead of asking, and skipping verification.[^osworld2]

Claims of a "professional computer operator" therefore need task-specific,
end-to-end evidence rather than success on short demos.

## Reliability and durable execution

Long-running agents should be implemented like distributed systems.

Required properties include:

- append-only events or an equivalent audit trail
- explicit state machines
- transactional or idempotent mutations
- retry classification: transient, recoverable, user-correctable, policy, and
  terminal
- exponential backoff and jitter for transient failures
- deadlines and cancellation propagation
- leases or ownership for concurrent workers
- heartbeats for long operations
- reconciliation after uncertain tool outcomes
- unique operation IDs
- recovery from process, network, and model failures
- durable waits that consume no active compute

The model should not be responsible for remembering whether a payment, email,
deployment, deletion, or other side effect has already occurred. The runtime's
side-effect ledger is authoritative.

## Security and permissions

The strongest design contains capability rather than relying only on permission
prompts.

Use:

- sandboxed filesystems and processes
- network egress allowlists
- per-tool and per-resource authorization
- short-lived, narrowly scoped credentials
- separation between read and write tools
- automatic approval for low-risk, bounded actions
- human confirmation for consequential, ambiguous, or irreversible actions
- prompt-injection scanning and untrusted-data labeling
- secret redaction from prompts, logs, and traces
- audit logs and side-effect receipts
- CPU, memory, time, network, and spend limits

Anthropic reports that users approved approximately 93% of traditional
permission prompts, illustrating approval fatigue. Its current guidance
emphasizes containment—limiting what an agent is capable of doing—even when
behavioral defenses fail.[^anthropic-containment]

For MCP integrations:

- validate token audience
- prohibit token passthrough
- obtain per-client consent
- use least-privilege scopes
- defend against confused-deputy attacks
- prevent server-side request forgery
- treat server tool descriptions and returned content as untrusted

These requirements are covered by the MCP security guidance.[^mcp-security]

## Observability

Capture a trace for every end-to-end task with spans for:

- routing
- context assembly
- retrieval queries and selected results
- model requests
- tool discovery
- tool execution
- guardrails and approvals
- state transitions
- verification
- retries and recovery

Record:

- task and trace IDs
- model and prompt versions
- input, cached-input, reasoning, and output tokens
- latency by stage
- tool arguments and compact outputs, subject to privacy policy
- retrieved source IDs and scores
- context composition and token allocation
- cache hits and misses
- side effects
- final outcome and grader results

Sensitive model and tool data must be optional, redacted, access-controlled, and
subject to retention limits.

## Evaluating what is "best"

Do not optimize only accuracy or token count. Measure the Pareto frontier
across:

- verified task-completion rate
- partial progress
- human correction rate
- constraint violations
- unsafe or unauthorized actions
- false claims of completion
- recovery rate after tool failure
- input, cached-input, reasoning, and output tokens
- cost per successful task rather than cost per request
- wall-clock time and time to first useful result
- number of model turns and tool calls
- context utilization
- retrieval precision and recall
- cache-hit rate
- repeated or redundant actions
- resume correctness after interruption
- side-effect duplication
- user satisfaction and human time saved

Evaluate full trajectories in real environments with repeated stochastic runs.
Combine deterministic graders, state-based checks, model graders, and selective
human review. Anthropic's 2026 evaluation guidance similarly recommends
multiple grader types for complex agents.[^anthropic-evals]

Every architectural addition should survive an ablation:

> Does removing this component measurably reduce quality, safety, reliability,
> or efficiency on representative tasks?

If not, remove it. Agent harness assumptions age quickly as models improve.

## Recommended summer-2026 blueprint

For a new general-purpose coding, chat, research, or computer-use agent:

1. Use one strong controller agent.
2. Keep a typed task-state object and append-only event log.
3. Run it through a durable workflow engine with checkpoints.
4. Compile context under explicit token budgets before each inference.
5. Use hybrid lexical, vector, and metadata retrieval with reranking.
6. Load files, knowledge, skills, and tools just in time.
7. Organize tools into namespaces and defer detailed schemas.
8. Provide a sandboxed code-execution layer for tool composition.
9. Store large output in an artifact store.
10. Keep prompt prefixes stable and measure cache behavior.
11. Reuse safe connections and warm execution resources.
12. Route models and reasoning effort according to measured task difficulty.
13. Parallelize independent reads and batch independent tool calls.
14. Verify mutations through tests or observable postconditions.
15. Back risk-based approvals with real capability containment.
16. Trace, replay, and continuously evaluate complete task trajectories.
17. Add planner, evaluator, or parallel agents only when ablation tests prove
    their value.

This architecture should outperform a design that places everything into a
very large prompt and lets several agents converse. It is more reliable,
economical, fast, debuggable, secure, and maintainable, while retaining the
ability to load a large amount of clean context for the particular reasoning
steps that genuinely need it.

## Anti-patterns

- Treating the full conversation transcript as authoritative state.
- Preloading the entire repository, knowledge base, or tool catalog.
- Using vector search as the only retrieval mechanism.
- Summarizing without retaining recoverable source artifacts.
- Making the model perform deterministic loops and data processing.
- Creating a multi-agent graph before establishing a single-agent baseline.
- Using an LLM judge as the only verification method.
- Retrying uncertain external mutations without idempotency.
- Trusting tool success strings without checking resulting state.
- Relying on frequent approval prompts as the primary security boundary.
- Measuring cost per call instead of cost per successful task.
- Optimizing token count while ignoring additional calls and lost accuracy.
- Keeping stale harness complexity after a model upgrade.
- Claiming completion without observable verification.

## Sources

[^anthropic-effective-agents]: Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents?lang=en-US), 2024-12-19.
[^anthropic-context]: Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), 2025-09-29.
[^less-context]: Lodha et al., [Less Context, Better Agents: Efficient Context Engineering for Long-Horizon Tool-Using LLM Agents](https://arxiv.org/abs/2606.10209), 2026-06-08.
[^openai-compaction]: OpenAI, [Compaction](https://developers.openai.com/api/docs/guides/compaction), accessed 2026-07-25.
[^openai-tool-search]: OpenAI, [Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search), accessed 2026-07-25.
[^anthropic-code-mcp]: Anthropic, [Code execution with MCP: building more efficient AI agents](https://www.anthropic.com/engineering/code-execution-with-mcp), 2025-11-04.
[^openai-cache]: OpenAI, [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching), accessed 2026-07-25.
[^gemini-cache]: Google, [Gemini 2.5 models now support implicit caching](https://developers.googleblog.com/en/gemini-2-5-models-now-support-implicit-caching/), 2025-05-08.
[^anthropic-managed]: Anthropic, [Scaling Managed Agents: Decoupling the brain from the hands](https://www.anthropic.com/engineering/managed-agents), 2026-04-08.
[^openai-latency]: OpenAI, [Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization), accessed 2026-07-25.
[^openai-background]: OpenAI, [Background mode](https://developers.openai.com/api/docs/guides/background), accessed 2026-07-25.
[^anthropic-harness]: Anthropic, [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps), 2026-03-24.
[^langgraph-persistence]: LangChain, [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence), accessed 2026-07-25.
[^openai-durable]: OpenAI, [Agents SDK: running agents and durable execution integrations](https://openai.github.io/openai-agents-python/running_agents/), accessed 2026-07-25.
[^osworld2]: Yuan et al., [OSWorld 2.0: Benchmarking Computer Use Agents on Long-Horizon Real-World Tasks](https://arxiv.org/abs/2606.29537), 2026-06-28.
[^anthropic-containment]: Anthropic, [How we contain Claude across products](https://www.anthropic.com/engineering/how-we-contain-claude), 2026.
[^mcp-security]: Model Context Protocol, [Security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices), accessed 2026-07-25.
[^anthropic-evals]: Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), 2026-01-09.
