# Dynamic agent loops, context efficiency, and platform completeness — 2026

> **Authored:** 2026-07-25 23:06 (+04) by GPT-5.6 (`gpt-5.6-sol`), reasoning
> effort: low, via Codex CLI 0.145.0. Attribution recovered from the Codex
> session rollout on 2026-07-25 23:2x, not self-reported by the original run.  
> **Research date:** 2026-07-25  
> **Model:** Codex (GPT-5)  
> **Reasoning effort:** System-managed; exact setting not exposed to the agent  
> **Scope:** Dynamic context construction, adaptive hierarchical agent
> orchestration, total token efficiency, and the feature surface expected from
> a modern coding/chat agent platform.  
> **Status:** Research and architectural guidance. This is not a project
> decision, requirement, or implementation plan.

## Summary

Three independent perspectives should be used when evaluating a modern agent:

1. **Cognitive efficiency**
   - Preserve the same quality while using fewer total tokens, calls, time,
     and money.
   - Dynamically construct context for each inference rather than replaying a
     complete transcript.

2. **Agent intelligence**
   - Use an adaptive loop that can plan, decompose, schedule, revise, verify,
     recover, and stop.
   - Generate execution topology dynamically while keeping its operations
     typed, constrained, and inspectable.

3. **Platform completeness**
   - Support skills, subagents, MCP, hooks, plugins, memory, sandboxes,
     permissions, settings, graphical controls, tracing, and provider
     portability.

An agent can be strong on one axis and weak on another. Feature richness does
not guarantee efficiency. An intelligent loop does not guarantee reliability.
A token-efficient runtime may still provide an inadequate user experience.

The recommended combined design is an **adaptive hierarchical agent runtime**:
a high-level controller maintains the global strategy, generates a constrained
task graph, and gives each worker only the local context needed for its task.

## Perspective 1: cognitive and token efficiency

### Dynamic context for every call

An agent does not need to send the same context on every LLM request. Each call
can and generally should receive a separately compiled context:

```text
Context for call N =
    stable policy
  + current role
  + local objective
  + relevant global constraints
  + selected state
  + retrieved evidence
  + relevant tools
  + requested output contract
```

Different calls should receive different projections of the same durable state.

| Call | Context supplied |
|---|---|
| Strategic planner | Goal, constraints, progress, risk, budgets, capability categories |
| Code investigator | Local question, repository map, relevant files and symbols |
| Implementation worker | Change contract, selected files, coding rules, test command |
| Test analyst | Test failures, changed-file list, expected behavior |
| Security reviewer | Diff, threat model, security requirements |
| Final synthesizer | Verified results, decisions, caveats, artifact references |

The planner does not need raw test logs. The test analyst does not need the
entire user conversation. The final synthesizer does not need every exploratory
shell command.

Gemini CLI uses independent subagent context loops: a specialist performs work
in its own context and returns a compact result to the parent, preventing the
main history from absorbing all intermediate activity.[^gemini-subagents]

### Context as projections rather than transcripts

Preserve complete information outside the model and create task-specific
projections:

```text
Complete durable state
    +-- strategic projection
    +-- implementation projection
    +-- retrieval projection
    +-- verification projection
    +-- user-facing projection
```

This is analogous to database views. The underlying information remains
available, but each consumer sees only the fields it requires.

A context compiler should apply:

- relevance filtering
- permission filtering
- freshness filtering
- deduplication
- abstraction-level selection
- explicit token budgets
- retrieval and reranking
- bounded recency retention
- stable-prefix construction
- source and artifact references
- compression appropriate to the consuming model

### Total-token efficiency

Splitting one large call into many small calls does not automatically reduce
tokens.

One large call might consume:

```text
40,000 input + 4,000 output = 44,000 tokens
```

Ten small calls that each repeat 6,000 input tokens and produce 500 output
tokens consume:

```text
10 * (6,000 + 500) = 65,000 tokens
```

The small-call version may be slower and more expensive despite its smaller
per-call contexts.

The correct objective is:

> Minimize total resource consumption subject to passing the same quality,
> safety, and reliability thresholds.

Measure:

```text
total input tokens
+ total output tokens
+ reasoning tokens
+ cache-write cost
+ cache-read cost
+ failed and retried calls
+ routing and evaluator calls
```

OpenAI reports that leaner prompts improved evaluation results in an internal
coding-agent sample while reducing total tokens by 41–66%. It also recommends
workload-specific ablation rather than assuming that prompt reduction will
always help.[^openai-model-guidance]

### When another LLM call is justified

Create a separate call when it provides at least one of these benefits:

- isolates a large amount of temporary context
- allows a cheaper model to perform the operation
- enables independent work to execute concurrently
- supplies meaningfully independent judgment
- benefits from a specialized prompt
- compresses a large investigation into a small structured artifact
- requires different tools or permissions
- prevents local details from contaminating the controller's context

Do not create an LLM call for:

- simple conditionals
- parsing a known structure
- sorting, filtering, joining, counting, or deduplication
- schema validation
- mechanical state transitions
- polling and retry timing
- selecting an obvious deterministic route

Those operations belong in ordinary code.

### Stable and dynamic context regions

A practical prompt layout is:

```text
Stable cached prefix
    constitution
    universal operating rules
    tool namespace summaries
    durable output conventions

Dynamic stage prefix
    worker role
    stage rules
    output schema

Retrieved working set
    local task
    relevant constraints
    selected evidence
    recent useful observations
```

Put stable information first and changing information last. This preserves
prefix-cache reuse while allowing each stage to receive a different working
set.

OpenAI tool search follows this principle by injecting dynamically discovered
tools at the end of the context to preserve the cached prefix.[^openai-tool-search]

## Perspective 2: the adaptive agent loop

### Constrained dynamic graphs

The best graph is neither a permanently fixed workflow nor an unconstrained
graph invented entirely by an LLM.

It is a constrained dynamic graph:

```text
LLM proposes strategy and typed tasks
             |
             v
Runtime validates the proposed graph
             |
             v
Deterministic scheduler executes ready tasks
             |
             v
Workers return structured results
             |
             v
Controller receives progress and exceptions
             |
             v
Controller revises, expands, or terminates graph
```

The LLM chooses the strategy and topology. The runtime owns operational
correctness, permissions, scheduling, persistence, and budgets.

### Why not let an LLM invent everything?

An unconstrained generated graph can:

- reference nonexistent capabilities
- create cycles or unresolved dependencies
- decompose work excessively
- spend more resources coordinating than executing
- duplicate tasks
- route sensitive data incorrectly
- invoke overly powerful agents
- declare completion without verification
- become impossible to replay or debug

Instead, the controller should generate a typed intermediate representation:

```yaml
strategy:
  objective: Repair the authentication regression
  success_conditions:
    - Affected test passes
    - Existing authentication suite passes

tasks:
  - id: investigate
    capability: code.investigate
    context_profile: repository_analysis
    model_profile: balanced
    inputs:
      question: Locate the regression and demonstrate its cause
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

The runtime validates:

- capabilities exist in the registry
- dependencies are acyclic
- required inputs are available
- permissions are sufficient
- parallel tasks are actually independent
- mutations have approval and idempotency policies
- the plan fits time, token, and monetary budgets
- mutations have corresponding verification
- stopping conditions are machine-checkable

LangGraph supports dynamic routing through commands and conditional
transitions, while leaving state schemas, validation, and execution semantics
to the application.[^langgraph-graph]

### Hierarchical abstraction

A strong implementation separates six levels.

#### Level 0: constitution

Mostly static:

- safety policy
- authorization boundaries
- general operating principles
- communication behavior

This belongs in the stable cached prefix.

#### Level 1: mission controller

Maintains:

- user goal
- constraints
- definition of done
- overall strategy
- risk
- budget
- progress
- unresolved decisions

It runs when:

- a task begins
- a stage completes
- a worker reports an exception
- evidence contradicts the plan
- the strategy must be revised
- completion may have been reached

It should not run before every shell command or file read.

#### Level 2: stage planner

Turns one strategic stage into a bounded task graph:

- research
- diagnose
- implement
- verify
- review
- deliver

It receives only global facts relevant to its stage.

#### Level 3: specialist worker

Receives:

- one local objective
- required constraints
- selected evidence
- restricted tools
- a structured return contract
- a local resource budget

It may have its own short tool-use loop.

#### Level 4: deterministic executor

Performs:

- tool composition
- API pagination
- file operations
- data transformation
- polling
- validation
- retries
- scheduling

This level should normally not use an LLM.

#### Level 5: independent verifier

Checks the environment against success criteria. It should see the intended
result and observable evidence, but does not always need the generator's
reasoning. This reduces self-confirmation.

### Context profiles

Each dynamic task should declare its required context:

```yaml
context_profile:
  include:
    - local_goal
    - relevant_constraints
    - selected_files
    - dependency_outputs
    - recent_failures
  retrieve:
    - query: authentication middleware
      sources: [code, decisions]
      maximum_tokens: 6000
  exclude:
    - unrelated_conversation
    - raw_successful_tool_logs
    - private_state_from_other_workers
  recent_tool_events: 4
  maximum_input_tokens: 12000
  output_schema: InvestigationResult
```

The runtime—not the worker—constructs the model input from this declaration.

### Approaches rather than fixed personas

Reusable approaches are more powerful than a permanent chain of named agents.

An approach describes when and how to act:

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

Other approaches include:

- repository reconnaissance
- documentation-first investigation
- search–extract–synthesize
- generate–critique–revise
- plan–execute–replan
- differential diagnosis
- constraint solving
- risk-based approval
- API-first computer interaction
- test-driven repair
- parallel independent research
- adversarial review
- escalation after repeated failure

The controller selects an approach based on the current situation. The
approach may instantiate no subagent, one specialist, or a temporary collection
of parallel workers.

Approaches should use progressive disclosure:

```text
Initial catalog:
    name + short applicability description

After selection:
    full instructions + resources + scripts + constraints
```

This is the same basic principle used by modern agent skills.

### Existing implementations and research

Parts of this architecture already exist:

- **LangGraph:** dynamic commands, conditional routing, subgraphs,
  checkpointing, interrupts, replay, and durable state.
- **Microsoft AutoGen:** model-based selection of the next specialist from the
  current context and agent descriptions.[^autogen-selector]
- **Google ADK:** code-first orchestration, sessions, memory, callbacks,
  plugins, MCP, evaluation, and long-running execution.
- **OpenAI Agents SDK:** agents-as-tools, handoffs, sessions, guardrails,
  tracing, approval interruption, and durable-execution integrations.
- **Claude Managed Agents:** versioned agents containing model, system prompt,
  tools, MCP, skills, multi-agent delegation, sandboxes, sessions, and event
  streams.[^claude-agent-setup]

Research uses terms such as:

- LLM-as-scheduler
- meta-controller
- adaptive orchestration
- dynamic model routing
- planner–executor
- hierarchical agents
- context-aware routing
- graph-generating agents
- learned orchestration

A 2026 ACL paper describes an LLM scheduler that dynamically decides whether
specialist stages such as refinement, verification, or testing should run
instead of following a fixed workflow.[^llm-scheduler]

CASTER reports context-aware model routing that matched strong-model success
rates while reducing inference cost in its evaluated domains. It is promising
research evidence rather than a universal production guarantee.[^caster]

OpenAI's Programmatic Tool Calling lets a model write JavaScript that invokes
several tools and processes intermediate results in a hosted runtime. It is
appropriate for bounded tool-heavy stages that do not require fresh semantic
judgment after every result.[^openai-model-guidance]

These code-execution approaches are important: a smart graph does not require
an LLM at every node. Frequently the model should generate a bounded program
and allow ordinary computation to perform many operations.

## Perspective 3: platform feature completeness

Platform completeness should be evaluated separately from the intelligence and
efficiency of the loop.

### Agent intelligence

- tool-use loop
- planning and replanning
- dynamic task graphs
- parallel tool calls
- model routing
- reasoning-effort routing
- specialist delegation
- independent verification
- reflection triggered by evidence or failure
- explicit stopping criteria

### Context and memory

- per-call dynamic context
- token budgets by stage
- prompt caching
- compaction
- recent-event pruning
- hybrid retrieval
- durable semantic memory
- episodic history
- user preferences
- artifact storage
- provenance and freshness
- context-debugging interface

### Tools

- filesystem and shell
- structured code editing
- browser and computer use
- web search
- code execution
- image and document tools
- custom function tools
- deferred tool loading
- namespaces
- programmatic tool composition
- typed errors
- idempotency

### MCP

MCP should be a first-class capability:

- local stdio servers
- remote HTTP servers
- OAuth
- credential vaults
- capability negotiation
- deferred MCP tool discovery
- server health and lifecycle
- tool-level permissions
- per-agent MCP isolation
- resource and prompt support
- sampling and elicitation where supported
- connection reuse
- audit and token accounting
- prompt-injection defenses
- confused-deputy defenses
- prohibition of token passthrough
- SSRF defenses

MCP is an interoperability layer, not an orchestration engine. It connects the
agent with capabilities; it does not decide the strategy.

Claude Managed Agents separates reusable MCP server declarations from
session-specific credentials stored in vaults.[^claude-mcp]

### Skills

A complete skill system should support:

- `SKILL.md`-style progressive disclosure
- built-in, organization, user, and project scopes
- scripts, templates, references, and assets
- versioning
- dependencies
- installation review and trust
- lazy loading
- usage telemetry
- skill-specific evaluation
- provider-neutral packaging where possible

Claude Managed Agents and Gemini CLI expose skills as on-demand domain
capability bundles. Claude notes that even skill metadata consumes context and
recommends attaching only the skills needed for a task.[^claude-skills][^gemini-skills]

### Subagents

A modern subagent system should support:

- independent context
- restricted tools
- per-agent model selection
- per-agent MCP servers
- maximum turns, time, tokens, and cost
- parallel invocation
- structured return contracts
- cancellation
- recursion limits
- permission isolation
- remote Agent-to-Agent support
- trace correlation

Subagents should be exposed to the parent as typed capabilities. Unlimited
shared-chat participation creates unnecessary context duplication and weak
boundaries.

Gemini CLI supports separate subagent context, model selection, restricted
tools, isolated MCP configuration, limits, policies, and remote A2A
delegation.[^gemini-subagents]

### Hooks

Provide lifecycle hooks for:

- session start and end
- before and after context compilation
- before and after model calls
- before tool selection
- before and after tool execution
- before mutation
- before compaction
- after retrieval
- before delegation
- after worker completion
- before final response
- notifications and errors

Hooks should be:

- typed
- observable
- time-limited
- parallel where safe
- able to add context or metadata
- able to reject or rewrite a proposed action
- unable to bypass the core security policy

Gemini CLI's hook surface includes model, agent, tool, session, and
pre-compression events, and its documentation demonstrates RAG-based tool
filtering and dynamic memory injection.[^gemini-hooks]

### Extensions and plugins

An extension should be able to package:

- skills
- subagents
- hooks
- MCP servers
- commands
- policies
- UI components
- configuration schemas
- secret declarations
- migrations
- evaluations

Extensions should not inherit the user's complete environment or all
credentials. Required secrets and capabilities should be explicitly declared.

Gemini CLI extensions currently package commands, hooks, skills, subagents,
policies, MCP configuration, and user-supplied settings.[^gemini-extensions]

### Safety and governance

- sandboxing
- network policy
- filesystem policy
- tool and command rules
- risk-based approvals
- secret management
- data-retention controls
- audit logs
- organization policies
- per-agent permissions
- prompt-injection controls
- budget limits
- emergency cancellation

### Developer experience

- SDK
- CLI
- API
- headless operation
- streaming
- structured output
- session resume
- replay
- test harness
- mock tools
- local-model support
- multi-provider support
- import and export of configuration and traces

## GUI and settings

A rich GUI is valuable, but exposing every internal parameter directly creates
a confusing and fragile product. Configuration should have three levels.

### Basic settings

- model profile: fast, balanced, strongest
- autonomy level
- approval behavior
- maximum budget
- Internet access
- memory enabled
- preferred response detail
- enabled extensions

### Advanced settings

- model by task type
- reasoning effort
- context budget
- compaction threshold
- parallelism
- maximum turns
- retry limits
- sandbox and network access
- skills, MCP servers, hooks, and subagents
- data retention
- caching policy

### Expert settings

- context profiles
- retrieval weights
- reranker configuration
- dynamic-routing policy
- graph admission rules
- models per capability
- tool-schema visibility
- hook ordering
- custom agent definitions
- provider-specific parameters
- trace-capture policy
- experimental features

### Runtime observability

The GUI should expose not only settings but also the runtime's understanding:

- current goal and strategy
- generated dynamic graph
- active, blocked, and completed tasks
- context contents and token allocation
- why a source, skill, tool, or subagent was selected
- model and reasoning level used by each call
- token, latency, and cost breakdown
- pending approvals
- artifacts and changed resources
- checkpoints and resume controls
- trace replay and graph time travel

This makes an adaptive agent understandable rather than mysterious.

## Recommended architecture

```text
                         +--------------------+
                         | Mission controller |
                         | strongest model    |
                         +---------+----------+
                                   |
                             typed strategy
                                   |
                         +---------v----------+
                         | Graph compiler     |
                         | validate + budget  |
                         +---------+----------+
                                   |
                              runnable tasks
                +------------------+------------------+
                |                  |                  |
                v                  v                  v
        Research worker     Coding worker      Review worker
        small context       local context      evidence context
        routed model        strong model       independent model
                |                  |                  |
                +------------------+------------------+
                                   |
                                   v
                         Durable blackboard
                     state + events + artifacts
                                   |
                         +---------v----------+
                         | Mission controller |
                         | revise or finish   |
                         +--------------------+
```

Important properties:

- The controller operates at a high abstraction level.
- The execution graph is generated and revised at runtime.
- The graph uses a constrained capability vocabulary.
- Every node declares an independent context profile.
- Workers receive small local contexts.
- Raw worker histories do not enter the controller context.
- Models and reasoning effort vary by task difficulty.
- Deterministic code performs mechanical workflows.
- Verification is explicit.
- State and artifacts remain outside the model.
- Token usage is optimized globally rather than per call.
- Actions are traceable and resumable.
- Skills, tools, MCP servers, and subagents use progressive discovery.

This is smart in a useful sense: it adapts strategy and information flow while
keeping execution bounded, inspectable, and measurable. An unrestricted LLM
deciding every operational detail would appear more autonomous but would
usually be less efficient and reliable.

## Design principles

1. **Dynamic context, durable truth.**  
   Vary the model context freely, but keep authoritative state outside it.

2. **Global strategy, local cognition.**  
   Let the controller reason globally and workers reason over small local
   problems.

3. **Dynamic topology, constrained vocabulary.**  
   Let the model compose registered capabilities rather than invent executable
   primitives.

4. **LLMs for judgment, code for mechanics.**  
   Do not pay for probabilistic inference where deterministic execution is
   sufficient.

5. **Optimize total work.**  
   Small contexts are beneficial only when total tokens, calls, latency, and
   retries improve without quality loss.

6. **Verify externally.**  
   Completion is an observable property of the environment, not an agent
   statement.

7. **Progressive disclosure everywhere.**  
   Apply it to knowledge, tools, skills, subagents, policies, and settings.

8. **Complexity must survive ablation.**  
   Remove any controller, worker, evaluator, hook, or graph stage whose value
   cannot be measured.

## Sources

[^gemini-subagents]: Google, [Gemini CLI: Subagents](https://geminicli.com/docs/core/subagents/), updated 2026-06-08.
[^openai-model-guidance]: OpenAI, [Model guidance](https://developers.openai.com/api/docs/guides/latest-model), accessed 2026-07-25.
[^openai-tool-search]: OpenAI, [Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search), accessed 2026-07-25.
[^langgraph-graph]: LangChain, [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), accessed 2026-07-25.
[^autogen-selector]: Microsoft, [AutoGen Selector Group Chat](https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/selector-group-chat.html), accessed 2026-07-25.
[^claude-agent-setup]: Anthropic, [Claude Managed Agents: Define your agent](https://platform.claude.com/docs/en/managed-agents/agent-setup), accessed 2026-07-25.
[^llm-scheduler]: [LLM-as-Scheduler: Agentic Workflow Dynamic Scheduling](https://aclanthology.org/2026.acl-long.581.pdf), ACL 2026.
[^caster]: [CASTER: Context-Aware Strategy for Task Efficient Routing](https://arxiv.org/abs/2601.19793), 2026.
[^claude-mcp]: Anthropic, [Claude Managed Agents: MCP connector](https://platform.claude.com/docs/en/managed-agents/mcp-connector), accessed 2026-07-25.
[^claude-skills]: Anthropic, [Claude Managed Agents: Skills](https://platform.claude.com/docs/en/managed-agents/skills), accessed 2026-07-25.
[^gemini-skills]: Google, [Gemini CLI: Managing Agent Skills](https://geminicli.com/docs/cli/using-agent-skills/), updated 2026-04-30.
[^gemini-hooks]: Google, [Gemini CLI: Hooks reference](https://geminicli.com/docs/hooks/reference/), updated 2026-04-10.
[^gemini-extensions]: Google, [Gemini CLI: Extension reference](https://geminicli.com/docs/extensions/reference/), accessed 2026-07-25.
