# Three perspectives: token efficiency, the dynamic smart graph, and the feature surface — July 2026

> **Authored:** 2026-07-25 23:15 (+04) by Claude Opus 5 (`claude-opus-5`),
> reasoning effort: medium, via Claude Code.
> **Research date:** 2026-07-25
> **Method:** Web survey of 2026 primary sources (arXiv, vendor engineering
> docs, benchmark reports). Quantitative claims are sourced inline.
> **Status:** Research and reference. Not a decision, requirement, or plan.
> Adopting anything here is a separate decision belonging in `docs/adr/` or
> `roadmap.md`.
>
> **Siblings:**
> - `agent-harness-benchmarks-and-context-economics-2026-07.md` — the measured
>   effect sizes (harness spread, compaction costs, cache economics). Read that
>   for numbers; this document is about *architecture per perspective*.
> - `best-ai-agent-architecture-summer-2026.md` — broad architectural survey.
> - `dynamic-agent-loop-and-platform-perspectives-2026.md` — earlier treatment
>   of dynamic context and platform completeness.
> - `modern-agent-implementation-attributes.md` — checkable attributes.

## The short answers

Three questions were asked. The literature answers all three affirmatively, and
in each case the approaches are already implemented and published.

1. **Can the agent feed a different context to the LLM on every call?** Yes —
   and this is the *dominant* 2026 architecture, not an exotic one. The context
   window is reframed as a **projection**, not storage.
2. **Can the graph itself be smart, dynamic, and not fixed-size?** Yes. A
   published taxonomy separates static templates → construct-then-execute →
   **in-execution editing**, with named systems in each category. A
   meta-level LLM designing the workflow (your "brain at higher abstraction")
   is the Designer/Executor split, implemented in DyFlow.
3. **Different LLMs per abstraction layer, piece by piece?** Yes — model
   routing and cascades, plus hybrid graphs mixing probabilistic LLM nodes with
   deterministic code nodes (HyEvo: **19× cost and 16× latency reduction**).

---

# Perspective A — Token efficiency: same quality, fewer tokens

## A.1 The reframe that makes this tractable

The key architectural move, stated most cleanly by Zylos:

> *"The context window is not storage; it is a **projection** — a temporary,
> purpose-built view assembled from substrate on demand."*

This separates two things that naive agents conflate:

| Layer | Lifetime | Size |
|---|---|---|
| **Persistent substrate** | All state between calls | Unbounded |
| **Ephemeral projection** | One inference call | Small, purpose-built |

Once separated, "keep context small" and "don't lose information" stop being in
tension. Nothing is lost — it's in substrate. Only the *projection* is small.
[Zylos — Dynamic context assembly and projection](https://zylos.ai/research/2026-03-17-dynamic-context-assembly-projection-llm-agent-runtimes)

## A.2 The canonical four-region projection layout

Ordered deliberately for cache behavior:

1. **Pinned region** (stable, cached) — system instructions, tool definitions,
   persona
2. **Session summary** (static per session) — compressed prior work and decisions
3. **Retrieved region** (dynamic) — semantically relevant substrate chunks
4. **Recent raw** (last N turns) — uncompressed recent work, current observation

**Any dynamic content inserted early invalidates all downstream cache entries.**
That single constraint determines the ordering. (ibid.)

## A.3 Measured cost of the reframe

| Approach | Cost per call (Sonnet 4.6 @ $3/MTok) |
|---|---|
| Naive: dump 100K tokens of history | **$0.30** |
| Hybrid: 8K compressed + 8K retrieved | **~$0.02** |

**12.5× reduction before caching.** Adding caching (write 1.25×, read 0.1×): at
10× reuse, **~78% further reduction on pinned regions**. (ibid.)

## A.4 Assembly strategy comparison

| Strategy | Latency | Token cost | Fidelity | Complexity |
|---|---|---|---|---|
| Sliding window | ~0ms | Low | Poor | Low |
| Vector retrieval (RAC) | 20–100ms | Medium | 85–95% recall | High |
| Hierarchical summarization | Async | Low | Lossy | Medium |
| **Hybrid pinned + retrieved** | 20–100ms | Low–Medium | **High** | High |

(ibid.)

## A.5 Placement matters as much as volume

Given lost-in-the-middle (Liu et al. 2023):

- Critical information at prompt **start or end**, never middle.
- **Short retrieved chunks (~50 tokens)** beat long documents.
- **Interleave sources by decreasing relevance** rather than batching by source.
- Structural markers (XML tags) for localization.

Same token budget, materially different quality. This is free efficiency. (ibid.)

## A.6 Tool-definition bloat is the largest single waste

Concrete measurement: **20 MCP servers ≈ 916 tools ≈ 138,000 tokens** of
definitions — two-thirds of a 200K window consumed before the first user query
is read.

The fix, shipped by Anthropic in January 2026 as the **Tool Search Tool** (BM25
internally): when tool definitions exceed a threshold, most are **deferred** —
withheld from the request. The model receives a single `ToolSearch` tool and
loads definitions on demand.

| Measurement | Result |
|---|---|
| Tool Search Tool: context preserved | **191,300 tokens** vs 122,800 traditional (**85% reduction**) |
| Speakeasy, dynamic toolsets | **96.7% token reduction** |
| Semantic selection | Expose **3–5 relevant tools** instead of 50–100+ |

[Anthropic — Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use) ·
[Speakeasy — 100× token reduction with dynamic toolsets](https://www.speakeasy.com/blog/100x-token-reduction-dynamic-toolsets/) ·
[BM25 vs TF-IDF vs hybrid for MCP tool discovery](https://www.stackone.com/blog/mcp-tool-search-bm25-tfidf-hybrid/) ·
[Vector-based MCP tool selection (2603.20313)](https://arxiv.org/pdf/2603.20313)

**This is the same progressive-disclosure principle applied to tools rather than
knowledge** — and it is the highest-yield token optimization available, because
the waste is pure overhead paid on every single call.

---

# Perspective B — The dynamic, smart agent graph

This is the substantive part of the question, and the answer is that the field
has moved exactly where the question points.

## B.1 The published taxonomy

IBM's survey — *From Static Templates to Dynamic Runtime Graphs* — organizes the
space along a static/dynamic axis:

**Static optimization** (structure fixed offline)
- *Offline template search*: AFlow, ADAS — search a constrained design space
  before execution
- *Node-level optimization*: DSPy, OPRO — refine components, fixed scaffold
- *Joint structure + configuration*: Maestro — topology and settings together
- *Verifiability*: MermaidFlow, VFlow — safety constraints in generation

**Dynamic optimization** (structure determined at runtime)
- *Selection & pruning*: **AgentDropout, MasRouter** — drop agents, prune
  communication paths at runtime
- *Construct-then-execute*: **AutoFlow, G-Designer** — build a query-specific
  workflow before running it
- *In-execution editing*: **DyFlow, MetaGen** — modify workflow topology *as
  execution proceeds*

[IBM — Awesome agentic workflow optimization (survey)](https://github.com/IBM/awesome-agentic-workflow-optimization)

**Your description maps to "in-execution editing"** — the most dynamic
category, and the least mature.

## B.2 The Designer/Executor split — the "brain at higher abstraction"

**DyFlow** implements precisely the architecture described in the question: a
meta-level LLM that reasons about *approach* rather than about the task.

- **Designer** (LLM): analyzes the task, generates the workflow
- **Executor**: runs it while monitoring performance signals

At each step the Designer decides **which operators to invoke next, how to
compose their outputs, and whether to adapt the workflow based on intermediate
results.** Workflow generation is treated as an agentic reasoning problem in its
own right. Reported: outperforms static baselines on reasoning-heavy tasks
(math, QA), better cross-task generalization, efficiency gains from adaptive
operator selection — with the advantage largest when problem complexity varies
or several solution strategies could apply.
[DyFlow (2509.26062)](https://arxiv.org/pdf/2509.26062)

## B.3 Meta-agents that improve their own graph

**HyEvo** adds the reflect-then-generate loop: the meta-agent diagnoses failures
by reading execution logs, learns from high-performing reference workflows,
formulates a natural-language diagnosis, then jointly optimizes **topology and
node semantics**.

Its second idea is the one most relevant to token efficiency: **heterogeneous
atomic synthesis** — mixing *probabilistic LLM nodes* for semantic reasoning
with *deterministic code nodes* for rule-based execution, offloading predictable
operations out of LLM inference entirely.

| HyEvo result | Value |
|---|---|
| GSM8K | 93.36% |
| MATH | 53.91% |
| HumanEval | 93.89% |
| Inference cost reduction | **up to 19×** |
| Execution latency reduction | **up to 16×** |

(vs. the SOTA open-source baseline.)
[HyEvo (2603.19639)](https://arxiv.org/pdf/2603.19639)

**Read that as: the largest efficiency win came from deciding which steps
shouldn't be LLM calls at all.** That is the strongest available answer to
"same quality, fewer tokens."

Related self-evolving systems: [EvoAgentX](https://www.alphaxiv.org/overview/2507.03616v2),
[SEW: self-evolving agentic workflows for code generation (2505.18646)](https://arxiv.org/pdf/2505.18646),
[Autogenesis (2604.15034)](https://arxiv.org/pdf/2604.15034),
[AOrchestra — automating sub-agent creation],
[Workflow-R1 — RL for multi-turn workflow construction],
[AgentConductor — topology evolution for competition-level code generation].
At the harness layer, **Meta-Harness** (Lee et al. 2026) casts harness design
itself as a search problem driven by a high-capacity LLM.

## B.4 Stage-aware context — different context per node, by construction

Once the graph is dynamic, context becomes a function of graph position:

> Phases and nodes give the LLM static context. Each phase carries general
> knowledge about its objective and signals which kinds of granular context are
> relevant at that stage; **each node receives a focused subset tailored to its
> analytical viewpoint.** The agent additionally needs dynamic,
> situation-specific information at each step.

Selection is via **dynamic tool dispatch** — summarizers, retrieval engines, and
memory lookups activate selectively based on query nature and system state, and
retrieved content is ranked, compressed, and packed into a structured prompt.
[Zylos — Dynamic context assembly](https://zylos.ai/research/2026-03-17-dynamic-context-assembly-projection-llm-agent-runtimes) ·
[Sourcegraph — Context engineering](https://sourcegraph.com/blog/context-engineering)

**Retrieval scoring (from Stanford's Generative Agents), tripartite:**

```
score = α·recency + β·importance + γ·relevance
```

- **recency** — exponential time decay
- **importance** — LLM-assessed significance, 1–10 scale
- **relevance** — cosine similarity to the current query

This exists specifically to fix the failure where naive recency windows drop
crucial older events. (Zylos, ibid.)

## B.5 The agent managing its own context — VISTA

The most direct implementation of "the agent is smart about its own context."
The paper's diagnosis: **frontier models are proprioceptively blind to their own
context** — they cannot perceive block size, recency, or access history from the
prompt alone, so they cannot make good keep-or-drop decisions.

VISTA (*Visible Internal State for Tool Agents*) adds three things:

1. **Dashboard** — per-block metadata: token usage, recency, access history,
   remaining budget
2. **Archive/recovery** — externalize blocks as exact payloads under stable
   handles (lossless)
3. **Workspace** — working memory as **typed, addressable blocks**, not an
   append-only transcript

Context actions join the tool space: `archive(S, ρ)`, `read(h, q)`,
`delete(S)`.

| Benchmark | VISTA | Baselines |
|---|---|---|
| LOCA-Bench (million-token) | **50.7%** | Claude Code 42.7%, ReAct 22.7% |
| BrowseComp-Plus (100K) | **58.0%** | 52.0% strongest baseline |
| GAIA (short trajectories) | 73.3% | Claude Code 73.9% (competitive) |

Two findings matter most: **gains grow with context pressure**, and the approach
**transfers across four model backbones without training.** On short tasks it
provides no advantage — the overhead only pays off under pressure.
[VISTA / latent context managers (2606.30005)](https://arxiv.org/html/2606.30005)

## B.6 Different LLMs per abstraction layer

Mature and well-characterized:

- **Cascades**: the prompt flows through increasingly capable models, stopping
  as soon as a quality threshold is met. Cheap models handle easy cases;
  escalation only on a difficulty or confidence signal.
- **Layered practice**: a cheap rule-based pass for obvious cases → an
  embedding/classifier pass for the ambiguous middle → at-inference cascade for
  the hard tail. Pre-request rules are cheapest, at-inference cascades most
  accurate, post-response retry is the safety net.
- **Routing raises quality, not just lowers cost**: a well-designed router can
  outperform the single most capable model by exploiting per-model strengths.
- The framing that closes the loop with §B.2: *"the intelligence increasingly
  lives in the orchestration — in the router, the planner, the quality
  evaluator — rather than in any single model."*

[Dynamic model routing and cascading: a survey (2603.04445)](https://arxiv.org/html/2603.04445v2) ·
[Is escalation worth it? Decision-theoretic characterization of LLM cascades (2605.06350)](https://arxiv.org/pdf/2605.06350) ·
[Unified approach to routing and cascading](https://files.sri.inf.ethz.ch/website/papers/dekoninck2024cascaderouting.pdf) ·
[LLM model routing in 2026](https://www.digitalapplied.com/blog/llm-model-routing-2026-cost-quality-optimization-engineering-guide)

Natural layer assignment for a coding/chat agent:

| Layer | Model class | Rationale |
|---|---|---|
| Meta / Designer | Frontier | Approach selection is the highest-leverage, lowest-volume decision |
| Planning, edits | Frontier | Correctness-critical |
| Search, exploration, classification, routing | Small/fast | High volume, verifiable output |
| Summarization, compaction | Mid | Structured, templated |
| Deterministic steps | **No model** — code node | HyEvo's 19× lever |

## B.7 The honest counterweight

Four caveats the same literature raises:

1. **Harness gains do not transfer across models.** Harness-Bench found choices
   helping one model are neutral or harmful on another. A clever graph tuned for
   one model is unvalidated on the next. ([2605.27922](https://arxiv.org/pdf/2605.27922))
2. **The meta-level LLM call is itself latency and tokens.** The Designer call
   must be cheaper than the waste it avoids. On short tasks it isn't — exactly
   what VISTA's GAIA result shows.
3. **Most dynamic-workflow results are on reasoning/QA/code-generation
   benchmarks** (GSM8K, MATH, HumanEval), not multi-hour repository work. The
   transfer to long-horizon coding is *plausible, not demonstrated*.
4. **The pragmatic default still stands**: a single agent loop with good
   observability will reveal whether coordination is needed *before* the
   coordination layer is built. Dynamic topology multiplies the state space you
   must debug; the counter-pressure is the 12-factor discipline — stateless
   reducer `f(events) -> next_action`, explicitly constructed context, and
   deterministic replay.
   [Zylos — Graph orchestration in production](https://zylos.ai/research/2026-04-14-graph-based-agent-workflow-orchestration-production/) ·
   [12-Factor Agents](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md)

**Synthesis.** The defensible version of "very smart dynamic graph" is: a small
fixed *outer* loop that is boring, replayable, and observable; **dynamism in
what each node sees (projection) and which node runs next (dispatch), not in
inventing arbitrary topology every turn**; a meta-level Designer call invoked
only when the situation is genuinely ambiguous; and deterministic code nodes
wherever the step is predictable. That captures most of the measured upside
while staying debuggable.

---

# Perspective C — Feature surface of a modern agent platform

The reference implementation to match, as documented by Anthropic, is the union
of these extension points. Each one plugs into a different part of the loop, and
each has a distinct context cost — the second column is the part usually missed.

## C.1 Extension points and their context cost

| Feature | What it does | When it loads / context cost |
|---|---|---|
| **CLAUDE.md / rules** | Persistent per-session context; `.claude/rules/` can be path-scoped | Session start, **full content, every request**. Keep under 200 lines |
| **Skills** | Markdown knowledge + invocable workflows (`/name`); auto-loaded when relevant | Descriptions at start, **full content on use**. `disable-model-invocation: true` → **zero** until invoked |
| **Subagents** | Own loop, isolated context, returns a summary | Isolated from main session; own input/output tokens |
| **Agent teams** | Multiple independent sessions, **peer-to-peer messaging**, shared task list | Highest cost — each teammate is a full instance. Experimental, off by default |
| **MCP** | Connect external services/tools | Tool **names** at start, **schemas deferred**; tool search on by default |
| **Code intelligence (LSP)** | Symbol navigation, live type errors | Low — and **net-negative**, since symbol lookup replaces file reads |
| **Hooks** | Fire on lifecycle events; run shell, HTTP, prompt, or subagent | **Zero unless the hook returns output** |
| **Plugins / marketplaces** | Packaging layer bundling skills + hooks + subagents + MCP; namespaced | Packaging only |
| **Artifacts** | Publish session output as an interactive private web page | Output channel |

[Claude Code — Extend Claude Code](https://code.claude.com/docs/en/features-overview)

## C.2 The distinctions that actually matter

These are the design decisions behind the feature list, not trivia:

- **Skill vs. subagent** — a skill is *reusable content* loaded into a context;
  a subagent is *context isolation*. Choose by whether you need to share
  knowledge or to keep work out of the main window. They compose: a subagent can
  preload skills (`skills:` field); a skill can run isolated via `context: fork`.
- **Hook vs. prompt instruction** — *"an instruction like 'never edit .env' in
  CLAUDE.md or a skill is a request, not a guarantee. A PreToolUse hook that
  blocks the edit is enforcement."* **If a rule must hold every time, it is a
  hook, not a prompt.** This is the same structural-guarantee principle as
  permission modes.
- **Subagent vs. agent team** — subagents report only to the parent; teammates
  message *each other* and self-coordinate via a shared task list. Teams are for
  competing hypotheses and genuine discussion; subagents for "I only need the
  result."
- **MCP vs. skill** — MCP provides the *connection and tools*; the skill
  provides the *judgment* for when and how to use them. Pairing them is the
  documented pattern (MCP connects the database; the skill teaches the schema
  and query patterns).
- **Layering rules** — CLAUDE.md files are **additive** across levels; skills
  and subagents **override by name** (managed > user > project); MCP servers
  override local > project > user; **hooks merge** — all matching hooks fire
  regardless of source.

## C.3 Session, safety, and execution features

| Feature | Behavior |
|---|---|
| **Checkpoints / rewind** | Snapshot before every file-editing tool call; restore code, conversation, or both; survives restart/resume. **Does not undo external side effects** (API calls, DB writes) and does not replace git |
| **Plan mode** | Read-only exploration producing a proposal before anything executes |
| **Permission modes** | Default asks per write/command; other modes trade oversight for speed. Auto Mode (research preview) uses a **separate Sonnet 4.6 classifier** to pre-screen each action — safe proceeds, risky blocked or escalated |
| **Sandboxing** | 2026 default workflow: plan in IDE → agents execute locally in a sandbox → CI + PR review before merge |
| **Background tasks** | Long shell commands via `run_in_background`; agent polls output without blocking the conversation |
| **Surfaces** | CLI, desktop app, web, IDE extensions (VS Code, JetBrains) |
| **SDK / programmatic** | Agent SDK for building custom agents on the same loop |

[Claude Code 2026 feature guide](https://www.marktechpost.com/2026/06/14/claude-code-guide-2026-25-features-with-examples-demo/) ·
[Checkpoints and rewind](https://theaiarchitects.com/blog/claude-code-checkpoints) ·
[Best agentic coding workflow 2026](https://kilo.ai/articles/beyond-autocomplete)

## C.4 GUI and configurability

The observable expectations in 2026, from the feature landscape:

- **Per-server MCP cost visibility** (`/mcp` shows connection status *and token
  cost per server*) — surfacing token economics to the user, not hiding them.
- **Automatic reconnection** for remote MCP servers; ability to disconnect idle
  servers.
- **Skill visibility overrides from settings** (`skillOverrides`) — controlling
  a third-party skill's context cost without editing its file.
- **Rewind menu** — pick a point, restore code / conversation / both.
- **Settings layering** across managed policy → user → project → plugin, with
  documented precedence per feature type.
- **Interactive context-window view** showing how features combine in a live
  session.

The pattern across all six: **the user configures token economics and
enforcement, not just model and API key.** Exposing what consumes context, and
letting the user override it, is itself the modern feature.

## C.5 Feature parity is an active competitive axis

Not theoretical — competing agents are explicitly tracking this surface:
qwen-code has an open issue titled *"Bring subagent system to feature parity
with Claude Code"*; opencode has *"Skills 2.0 — Subagents, Dynamic Context
Injection, and Advanced Skill Capabilities."* The named seven-category surface
(CLAUDE.md, Skills, Subagents, Agent Teams, Plugins, Hooks, MCP Servers) has
become the de facto checklist.
[qwen-code #2409](https://github.com/QwenLM/qwen-code/issues/2409) ·
[opencode #17791](https://github.com/anomalyco/opencode/issues/17791) ·
[Skills vs Tools vs MCP vs Subagents vs Hooks](https://dev.to/miaoshuyo/skills-vs-tools-vs-mcp-vs-subagents-vs-hooks-2026-ultimate-comparison-kpi)

---

## Where the three perspectives converge

They are not independent, and the same principle drives all three:

**Progressive disclosure is the unifying mechanism.** Skills disclose knowledge
in three levels. Tool search defers tool schemas. Projection assembles context
per call. Subagents isolate exploration. Code nodes remove steps from inference
entirely. In every case the move is identical: *hold a cheap reference, resolve
it only on demand.*

**Enforcement belongs in structure, not prose.** Hooks over instructions,
permission modes over "please don't," code nodes over "carefully compute."
Structure survives context growth; prose dilutes.

**The remaining open problem** is that dynamic-graph results are demonstrated on
short reasoning benchmarks while the demand is long-horizon repository work —
and harness gains don't transfer across models. Anything adopted from Perspective
B needs measurement on your own tasks and your own model before it can be
trusted.

---

## Source index

**Context projection and token efficiency:**
[Zylos — Dynamic context assembly and projection](https://zylos.ai/research/2026-03-17-dynamic-context-assembly-projection-llm-agent-runtimes) ·
[Sourcegraph — Context engineering](https://sourcegraph.com/blog/context-engineering) ·
[mem0 — Context engineering guide](https://mem0.ai/blog/context-engineering-ai-agents-guide) ·
[Anthropic — Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use) ·
[Speakeasy — dynamic toolsets](https://www.speakeasy.com/blog/100x-token-reduction-dynamic-toolsets/) ·
[StackOne — BM25/TF-IDF/hybrid tool discovery](https://www.stackone.com/blog/mcp-tool-search-bm25-tfidf-hybrid/) ·
[Microsoft — mcp-cli dynamic tool discovery](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/mcp-vs-mcp-cli-dynamic-tool-discovery-for-token-efficient-ai-agents/4494272) ·
[Vector-based MCP tool selection (2603.20313)](https://arxiv.org/pdf/2603.20313)

**Dynamic graphs and meta-agents:**
[IBM survey — static templates to dynamic runtime graphs](https://github.com/IBM/awesome-agentic-workflow-optimization) ·
[DyFlow (2509.26062)](https://arxiv.org/pdf/2509.26062) ·
[HyEvo (2603.19639)](https://arxiv.org/pdf/2603.19639) ·
[VISTA / state proprioception (2606.30005)](https://arxiv.org/html/2606.30005) ·
[GraphFlow (2605.22566)](https://arxiv.org/html/2605.22566) ·
[EvoAgentX](https://www.alphaxiv.org/overview/2507.03616v2) ·
[SEW (2505.18646)](https://arxiv.org/pdf/2505.18646) ·
[Autogenesis (2604.15034)](https://arxiv.org/pdf/2604.15034) ·
[Meta-Agent-Workflow (ACM WWW'25 companion)](https://dl.acm.org/doi/10.1145/3701716.3715247) ·
[Harness-Bench (2605.27922)](https://arxiv.org/pdf/2605.27922) ·
[Zylos — Graph orchestration in production](https://zylos.ai/research/2026-04-14-graph-based-agent-workflow-orchestration-production/) ·
[12-Factor Agents](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md)

**Routing and cascades:**
[Dynamic model routing and cascading survey (2603.04445)](https://arxiv.org/html/2603.04445v2) ·
[Is escalation worth it? (2605.06350)](https://arxiv.org/pdf/2605.06350) ·
[Unified routing and cascading (ETH SRI)](https://files.sri.inf.ethz.ch/website/papers/dekoninck2024cascaderouting.pdf) ·
[LLM model routing 2026](https://www.digitalapplied.com/blog/llm-model-routing-2026-cost-quality-optimization-engineering-guide) ·
[Multi-model routing orchestration 2026](https://mindra.co/blog/multi-model-routing-llm-orchestration-2026)

**Feature surface:**
[Claude Code — Extend Claude Code](https://code.claude.com/docs/en/features-overview) ·
[Claude Code 2026 guide — 25 features](https://www.marktechpost.com/2026/06/14/claude-code-guide-2026-25-features-with-examples-demo/) ·
[Checkpoints and rewind](https://theaiarchitects.com/blog/claude-code-checkpoints) ·
[Beyond autocomplete — agentic coding workflow 2026](https://kilo.ai/articles/beyond-autocomplete) ·
[Skills vs Tools vs MCP vs Subagents vs Hooks](https://dev.to/miaoshuyo/skills-vs-tools-vs-mcp-vs-subagents-vs-hooks-2026-ultimate-comparison-kpi) ·
[Understanding Claude Code's full stack](https://alexop.dev/posts/understanding-claude-code-full-stack/) ·
[qwen-code subagent parity #2409](https://github.com/QwenLM/qwen-code/issues/2409) ·
[opencode Skills 2.0 #17791](https://github.com/anomalyco/opencode/issues/17791)
