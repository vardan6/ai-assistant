# AI agents — evidence base

> **Merged:** 2026-07-26 by Claude Opus 5 (`claude-opus-5`), via Claude Code.
> Reasoning effort not exposed to the agent; recover from the session transcript
> if it matters.
> **Research date of underlying material:** 2026-07-25.
> **Status:** Research and reference. Not a decision, requirement, or plan.
> Adopting anything here is a separate decision belonging in `docs/adr/` or
> `roadmap.md`.

## What this document is

**Every quantitative claim and every external source for the AI-agent research
set lives here, and only here.** The three companion documents state positions
and cite into this one using the notation `[EB §n]`.

| Companion | Owns |
|---|---|
| `ai-agent-reference-architecture-opus-5-2026-07-26.md` | What to build — the loop, context, tools, reliability, cost, safety |
| `ai-agent-platform-feature-surface-opus-5-2026-07-26.md` | Extension points — MCP, skills, subagents, hooks, GUI |
| `ai-agent-hierarchical-decomposition-opus-5-2026-07-26.md` | The decomposition pattern — prior art, contracts, failure modes |

This document states no architecture and makes no recommendation. It reports
what was measured, by whom, and on what.

**How to read a number here.** Almost every figure below comes from a specific
model on a specific benchmark in a specific harness. §1 establishes that harness
effects do not transfer across models — which means these numbers are *evidence
that an effect exists and roughly how large it can be*, not values you should
expect to reproduce. §11 lists where the evidence is genuinely thin.

### Provenance

| Source document (now in `docs/archive/`) | Model | Effort | Contributed |
|---|---|---|---|
| `ai-agent-harness-benchmarks-context-economics-opus-5-2026-07-25.md` | Claude Opus 5 | medium | Spine — §1–§5, §10, §11 |
| `ai-agent-hierarchical-decomposition-multi-layer-calls-opus-5-2026-07-25.md` | Claude Opus 5 | medium | §7 decomposition evidence |
| `ai-agent-dynamic-context-smart-graph-feature-surface-opus-5-2026-07-25.md` | Claude Opus 5 | medium | §2.5, §2.6, §6, §8 |
| `ai-agent-architecture-attributes-gpt-5-6-2026-07-25.md` | GPT-5.6 | low | §2.7, §3.3, §9, vendor sources |
| `ai-agent-dynamic-context-loop-platform-perspectives-gpt-5-6-2026-07-25.md` | GPT-5.6 | low | §2.8, §7.10, framework sources |
| `ai-agent-hierarchical-decomposition-isolated-reasoning-gpt-5-6-2026-07-25.md` | GPT-5.6 | low | §7.2, §7.4, foundational papers |
| `ai-agent-implementation-attributes-opus-5-2026-07-25.md` | Claude Opus 5 | medium | None — carried no citations by design |
| `ai-agent-session-record-unattributed-2026-07-25.md` | Unrecorded | Unrecorded | §4.1, §8.1 — merged 2026-07-27; leads only, all claims re-verified against primary sources |

---

## §1 Harness effect sizes

The harness — not the model — is now the dominant variable in agent quality, and
its effect size is large enough to swamp model choice.

- Artificial Analysis launched the first public **Coding Agent Index** in May
  2026 — the first benchmark evaluating full stacks (model + harness pairs)
  rather than models alone.
  [Coding Agent Index 2026](https://medium.com/@wasowski.jarek/coding-agent-index-2026-benchmarking-full-agent-stacks-model-harness-4183305e4b90)
- Reported accuracy gaps across harnesses running comparable models: **up to
  ~6×**. (ibid.)
- **Harness effects are model-specific.** Harness-Bench evaluated instruction
  formatting, examples, system prompts, tool descriptions, and output format
  across multiple frontier models on document, spreadsheet, and
  evidence-auditing workflows. Choices that help one model are neutral or
  harmful on another; there is no universal best harness.
  [Harness-Bench (2605.27922)](https://arxiv.org/pdf/2605.27922)
- The harness is precisely: which tools are exposed, how they are described,
  what auxiliary information accompanies each observation, and how context is
  assembled into the prompt.
  [Interplay of Harness Design and Post-Training (2606.25447)](https://arxiv.org/pdf/2606.25447)
- Automated harness search exists — **Meta-Harness** (Lee et al. 2026): an LLM
  reads candidate harnesses and proposes new ones. This is the logical
  consequence of model-specific tuning being non-transferable. (ibid.)

**This section governs every other section.** A harness improvement validated on
one model is unvalidated on the next. Harness changes must be measured, not
reasoned about.

---

## §2 Context economics

### §2.1 Context rot and placement

- **Context rot is mechanical, not stylistic**: transformer attention is n² over
  pairwise token relations, and training distributions favor shorter sequences.
  Quality degrades as tokens accumulate.
  [Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- **Lost-in-the-middle costs 30+ percentage points** on information placed
  mid-context (Liu et al. 2023).
  [Zylos — Context compaction](https://zylos.ai/research/2026-04-21-agent-context-compaction-long-running-sessions/)
- Placement findings that cost nothing to apply:
  - Critical information at prompt **start or end**, never the middle.
  - **Short retrieved chunks (~50 tokens)** beat long documents.
  - **Interleave sources by decreasing relevance** rather than batching by source.
  - Structural markers (XML tags) aid localization.
- Stated objective: the **smallest set of high-signal tokens that maximizes the
  likelihood of the desired outcome**. (Anthropic, ibid.)

### §2.2 Observation masking — the headline measurement

JetBrains, via a rolling window keeping only the last N tool results:

| Metric | Result vs. full context |
|---|---|
| Cost | **−52%** |
| Solve rate (Qwen3-Coder 480B) | **+2.6 pp** |
| Cost savings (general) | **50%+** |

Cheaper *and* better. This is the single measurement that contradicts the
intuition that more resident context is safer — **stale context is not neutral
ballast**.

Derived best practice: **tool-result clearing as the primary context-control
mechanism, with compaction reserved for preserving reasoning across long
dialogue** — not the other way round.
[Context engineering: memory, compaction, tool clearing](https://tianpan.co/blog/2026-02-26-context-engineering-memory-compaction-tool-clearing)

### §2.3 Compaction — costs and failure modes

- **Trigger at 70–75%** of window (≈150K of 200K). Waiting for 95–98% induces
  "context anxiety" and produces incomplete compressions.
- **Cost per event: 3,000–5,000 output tokens and 5–15s wall-clock**, because it
  requires full-context inference plus summary generation.
- **Naive summarization loses 10–15 pp on complex multi-step tasks; structured
  compaction recovers to within 1–2%** (ACON ablations). Use a fixed template:
  Session Intent / Files Modified / Key Decisions / Next Steps.
- **Artifact tracking is the weakest dimension across all methods** — Factory.ai
  scored file-modification recall at **2.19–2.45 / 5.0**.
- **Compression ratio is a misleading primary metric**: all evaluated methods
  achieved **98–99% compression** while quality scores spanned only
  **3.35–3.70**. Evaluate with probe-based metrics over accuracy, artifact
  tracking, continuity, and instruction-following.
- **Compaction invalidates cached prefixes** — see §3.2 item 4.
- Benchmark gap: LoCoMo (300-turn multi-session) and LongBench (21 long-context
  tasks) measure **single-session recall, not compaction chains**. Sequential
  lossy compressions over multi-day runs are unmeasured.

(All: [Zylos — Context compaction](https://zylos.ai/research/2026-04-21-agent-context-compaction-long-running-sessions/))

Vendor support: OpenAI's Responses API provides threshold-based server-side
compaction and explicit standalone compaction.
[OpenAI — Compaction](https://developers.openai.com/api/docs/guides/compaction)

### §2.4 Cheaper techniques to exhaust before compacting

Ordered by cost, cheapest first:

1. **Deterministic structural cleanup** — dedup identical tool outputs, purge
   resolved errors, canonicalize verbose responses. Zero model cost.
2. **Extractive compression** — LLMLingua-class methods reach **up to 20×
   compression with minimal accuracy loss**. Zero model cost.
3. **Selective eviction** — LRU or attention-weight scoring. Zero added cost,
   but positional gaps can confuse the model and importance scores miss context
   a later sub-task will need.
4. **Summarization compaction** — see §2.3.

**Externalize at creation, not at extraction.** Offload long-lived facts to
external memory when produced, rather than mining them out of a dying context
during compaction. This is the difference between lossless and lossy. (ibid.)

### §2.5 The projection reframe and its measured cost

The architectural move, stated most cleanly by Zylos:

> *"The context window is not storage; it is a **projection** — a temporary,
> purpose-built view assembled from substrate on demand."*

| Approach | Cost per call (Sonnet 4.6 @ $3/MTok) |
|---|---|
| Naive: dump 100K tokens of history | **$0.30** |
| Hybrid: 8K compressed + 8K retrieved | **~$0.02** |

**12.5× reduction before caching.** Adding caching (write 1.25×, read 0.1×): at
10× reuse, **~78% further reduction on pinned regions**.

Assembly strategy comparison:

| Strategy | Latency | Token cost | Fidelity | Complexity |
|---|---|---|---|---|
| Sliding window | ~0ms | Low | Poor | Low |
| Vector retrieval (RAC) | 20–100ms | Medium | 85–95% recall | High |
| Hierarchical summarization | Async | Low | Lossy | Medium |
| **Hybrid pinned + retrieved** | 20–100ms | Low–Medium | **High** | High |

Retrieval scoring from Stanford's Generative Agents, tripartite:
`score = α·recency + β·importance + γ·relevance`, where recency is exponential
time decay, importance is LLM-assessed significance on a 1–10 scale, and
relevance is cosine similarity to the current query. It exists specifically to
fix the failure where naive recency windows drop crucial older events.

(All: [Zylos — Dynamic context assembly and projection](https://zylos.ai/research/2026-03-17-dynamic-context-assembly-projection-llm-agent-runtimes) ·
[Sourcegraph — Context engineering](https://sourcegraph.com/blog/context-engineering))

### §2.6 Tool-definition bloat — the largest single waste

Concrete measurement: **20 MCP servers ≈ 916 tools ≈ 138,000 tokens** of
definitions — two-thirds of a 200K window consumed before the first user query
is read. A smaller but consistent figure from a second source: naively
connecting several MCP servers reaches **90+ tool definitions ≈ 50,000 tokens**
of JSON schema.

The fix, shipped by Anthropic in January 2026 as the **Tool Search Tool** (BM25
internally): when tool definitions exceed a threshold, most are **deferred** —
withheld from the request. The model receives a single `ToolSearch` tool and
loads definitions on demand.

| Measurement | Result |
|---|---|
| Tool Search Tool: context preserved | **191,300 tokens** vs 122,800 traditional (**85% reduction**) |
| Speakeasy, dynamic toolsets | **96.7% token reduction** |
| Semantic selection | Expose **3–5 relevant tools** instead of 50–100+ |
| Anthropic code-execution MCP example | tool context **150,000 → 2,000 tokens** |

The Anthropic code-execution figure is a published example, not a universal
expected reduction.

OpenAI's tool-search design defers tool definitions and **injects discovered
tools at the end** of the context so the cached prefix survives; its
documentation recommends coherent namespaces of generally fewer than ten
functions.

[Anthropic — Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use) ·
[Anthropic — Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) ·
[OpenAI — Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search) ·
[Speakeasy — dynamic toolsets](https://www.speakeasy.com/blog/100x-token-reduction-dynamic-toolsets/) ·
[BM25 vs TF-IDF vs hybrid for MCP tool discovery](https://www.stackone.com/blog/mcp-tool-search-bm25-tfidf-hybrid/) ·
[Vector-based MCP tool selection (2603.20313)](https://arxiv.org/pdf/2603.20313) ·
[Progressive disclosure as a system design pattern](https://www.newsletter.swirlai.com/p/agent-skills-progressive-disclosure)

### §2.7 Just-in-time retrieval and progressive disclosure

- Hold **lightweight identifiers** (file paths, queries, URLs) and resolve at
  runtime. Best practice recommends JIT over front-loading; a hybrid — small
  curated upfront set plus autonomous exploration — is often strongest.
  (Anthropic — Effective context engineering)
- **Sub-agents as context isolation devices**: a specialized agent burns its own
  window and returns a **1,000–2,000 token summary** to the coordinator. (ibid.)
- **Agent Skills — three disclosure levels**: (1) name + description in the
  system prompt, (2) full `SKILL.md` on relevance, (3) bundled reference files
  on demand. Scripts are *executed* and only their output enters context, which
  also buys determinism. Bundled knowledge becomes effectively unbounded without
  inflating every interaction.
  [Anthropic — Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)

### §2.8 Leaner prompts, measured

- OpenAI reports that leaner prompts improved evaluation results in an internal
  coding-agent sample while reducing total tokens by **41–66%**. Its own caveat:
  use workload-specific ablation rather than assuming prompt reduction always
  helps.
  [OpenAI — Model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- A June 2026 enterprise-agent study found that retaining **five recent tool
  interactions plus summarization** beat full history in its tested workflow:
  higher completion with roughly **63% fewer tokens**. Task-specific evidence,
  not a universal five-call rule.
  [Less Context, Better Agents (2606.10209)](https://arxiv.org/abs/2606.10209)

### §2.9 Tool design

- Self-contained, unambiguous, minimal functional overlap. The stated test: *"if
  a human engineer can't definitively say which tool applies, an AI agent can't
  be expected to do better."*
- **Bloated tool sets are among the most common failure modes** observed in
  production.
- Tool results must be token-efficient — return the answer, not the raw dump.

(Anthropic — Effective context engineering)

---

## §3 Caching and cost

### §3.1 Cache economics — the highest-leverage optimization

| Metric | Value |
|---|---|
| Cost savings on cache hit | **85–95%** |
| Latency reduction, cached portion, >10K tokens | **80–90%** |
| Achievable hit rate on agent loops | **60–85%** |
| Resulting per-call cost reduction | **5–12×** |
| Anthropic throughput effect at 80% hit rate | **~5×** (cached input tokens don't count toward rate limits) |

[Prompt caching in 2026](https://www.digitalapplied.com/blog/prompt-caching-2026-cut-llm-costs-engineering-guide) ·
[KV cache optimization 2026](https://www.digitalapplied.com/blog/kv-cache-optimization-techniques-2026-engineering-guide)

Exact-prefix caching is used by current OpenAI and Gemini APIs.
[OpenAI — Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) ·
[Gemini 2.5 implicit caching](https://developers.googleblog.com/en/gemini-2-5-models-now-support-implicit-caching/)

### §3.2 Cache discipline is architecture, not configuration

1. System prefix **byte-for-byte stable**; tool definitions early and unchanging
   (tool defs are cacheable precisely because they rarely change).
2. Push volatile metadata (timestamps, dynamic state) to the **final** user
   message.
3. `cache_control` breakpoints immediately **before** volatile regions.
4. **Compaction creates a hard semantic break that invalidates all cached
   prefixes.** Anthropic's server-side API places a `cache_control` marker on the
   compaction block itself, so system prompt + summary serve from cache
   afterward and only new turns incur fresh processing.
5. **Any dynamic content inserted early invalidates all downstream cache
   entries.** This single constraint determines prompt-region ordering.

[Zylos — Context compaction](https://zylos.ai/research/2026-04-21-agent-context-compaction-long-running-sessions/) ·
[Zylos — Dynamic context assembly](https://zylos.ai/research/2026-03-17-dynamic-context-assembly-projection-llm-agent-runtimes)

### §3.3 Other cost and latency levers

- Agentic tasks make **50–200 LLM calls per task** — this is what converts a
  cheap per-token price into an expensive per-task cost. Optimize per-task.
  [LLM inference optimization](https://www.morphllm.com/llm-inference-optimization)
- **Speculative decoding**: **2–3×** with off-the-shelf draft models, **up to
  5×** optimized, with output mathematically identical to autoregressive
  decoding. (ibid.)
- Parallel independent tool calls per turn; parallel sub-agents for decomposable
  work.
- Role-based model routing: cheap/fast model for search, exploration, and
  classification; frontier model for planning and edits. See §6.5.
- Keep connections warm — persistent tool-server processes, warm sandboxes,
  pooled HTTP/DB connections. Cold starts dominate short tool calls.
- Anthropic reports substantial time-to-first-token improvement after separating
  its model harness from execution environments and provisioning them only when
  needed.
  [Anthropic — Scaling Managed Agents](https://www.anthropic.com/engineering/managed-agents)
- OpenAI's summary of latency optimization: process tokens faster, generate
  fewer tokens, use fewer input tokens, make fewer requests, parallelize, reduce
  perceived waiting, and avoid defaulting to an LLM.
  [OpenAI — Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization) ·
  [OpenAI — Background mode](https://developers.openai.com/api/docs/guides/background)

### §3.4 Reference consumption figures

- A single debugging session consumes **50,000–100,000 tokens**.
- Illustrative session cost (Sonnet, 40K in / 4K out): **~$1.84**.
- Uber: **25% of commits via Claude Code in Q1 2026**.

[Inside the agentic loop](https://dev.to/monuminu/inside-the-agentic-loop-a-deep-technical-dive-into-ai-coding-agents-claude-code-and-the-4pnf)

---

## §4 Retrieval for code

The 2026 consensus is hybrid, with the agent selecting by query shape:

| Approach | Wins on | Fails on |
|---|---|---|
| grep / ripgrep | Exact symbols, small-to-mid repos, one-off lookups; never stale | Conceptual/intent queries |
| Embeddings | "Code related to authentication" over large corpora | **Staleness** — an index over an hourly-changing repo is stale within moments |
| Code-graph / structural | Call graphs, references, localization ([LocAgent](https://arxiv.org/pdf/2503.09089)) | Fuzzy intent |

The load-bearing argument: *an LLM driving ripgrep in a loop beats any frozen
embedding model on a codebase that changes every commit.* Give the agent
lexical, structural, and graph search as tools and **verify results against
disk**.
[Grep replacement is three tools, not one](https://zzet.org/gortex/grep-replacement-for-ai-agents/) ·
[Semantic code search vs grep](https://particula.tech/blog/semantic-code-search-vs-grep-coding-agents)

Embeddings alone are insufficient for exact code symbols, recent state, negative
constraints, permissions, and temporal questions.

### §4.1 What shipping products actually do

The two reference implementations sit at opposite ends, which is the useful part
— both ship, at scale, with incompatible answers.

| | Claude Code | Cursor |
|---|---|---|
| Default | Agentic live search — glob, grep/ripgrep, read, optional LSP | Pre-built semantic index over the workspace |
| Index | None by default; vector retrieval only via optional MCP plugins | Automatic on workspace open, background, incremental |
| Freshness | Always current — searches run against disk | Re-indexed on change; staleness window is real but bounded |
| Persistence | Local `.claude/` + `CLAUDE.md` for project orientation | Cloud vector store |

**Cursor's staleness answer is a Merkle tree.** First-party documentation
describes client-side edits changing only the hashes of the edited file and its
parent directories to the root, so re-indexing walks only divergent branches; the
server filters results against the client's tree, so *"the client can never see
results for code it doesn't already have."*
[Cursor — Securely indexing large codebases](https://cursor.com/blog/secure-codebase-indexing)

> **Verified vs. reported.** The Merkle-tree change detection and hash-based
> server-side filtering above are first-party. Commonly repeated details that the
> first-party post does **not** state — Turbopuffer as the vector store,
> tree-sitter syntax-aware chunking, obfuscated paths and line ranges as stored
> metadata, raw source never persisted, a ~10-minute re-index cadence — come from
> [secondary](https://towardsdatascience.com/how-cursor-actually-indexes-your-codebase/)
> [analyses](https://read.engineerscodex.com/p/how-cursor-indexes-codebases-fast)
> and are plausible but unconfirmed. Treat vendor internals as a moving target.

Two consequences for a build decision. **Embedding cost is not the constraint** —
embedding models are orders of magnitude cheaper than the reasoning models
driving the loop, and indexing cost is dominated by the many LLM calls per task
(§3.4); reject an index on staleness or privacy grounds, not on cost. And
**cloud indexing is a privacy decision, not a performance one** — a fully local
embedding + vector-store pipeline is available and the tradeoff is latency and
index quality, which matters when the codebase is proprietary.

---

## §5 Verification reliability

- **Self-verification bias**: an agent judging its own intermediate output from
  within the same trajectory state that produced it entangles verification with
  self-justification, so flawed outputs get accepted. ICLR 2024 established that
  LLMs cannot reliably self-correct reasoning without an external signal.
- **Extrinsic verification** — an independent critic in an *isolated context*
  producing actionable defect reports — is the documented fix.
- **If a test can be run, run it.** Reserve intrinsic critique for subjective
  polish no test captures.
- Multi-Agent Reflexion (MAR) reduces bias further via diverse critic personas.
- Loop safeguards: max-iteration limits, per-cycle measurable-improvement checks,
  **state-hash deduplication** to detect returning to a prior state.
- The **compositionality gap**: a set of locally correct answers can still
  compose into an incorrect global answer.
  [Self-ask / compositionality gap (2210.03350)](https://arxiv.org/abs/2210.03350)

[Zylos — Reflection and self-evaluation patterns](https://zylos.ai/research/2026-03-06-ai-agent-reflection-self-evaluation-patterns) ·
[ReVeal (2506.11442)](https://arxiv.org/pdf/2506.11442)

---

## §6 Dynamic graphs, meta-agents, and routing

### §6.1 The published taxonomy

IBM's survey — *From Static Templates to Dynamic Runtime Graphs* — organizes the
space along a static/dynamic axis:

**Static optimization** (structure fixed offline)
- *Offline template search*: AFlow, ADAS
- *Node-level optimization*: DSPy, OPRO — refine components, fixed scaffold
- *Joint structure + configuration*: Maestro
- *Verifiability*: MermaidFlow, VFlow — safety constraints in generation

**Dynamic optimization** (structure determined at runtime)
- *Selection & pruning*: **AgentDropout, MasRouter**
- *Construct-then-execute*: **AutoFlow, G-Designer**
- *In-execution editing*: **DyFlow, MetaGen** — modify topology as execution
  proceeds. The most dynamic category, and **the least mature**.

[IBM — Awesome agentic workflow optimization](https://github.com/IBM/awesome-agentic-workflow-optimization)

### §6.2 DyFlow — the Designer/Executor split

A meta-level LLM that reasons about *approach* rather than about the task.
**Designer** (LLM) analyzes the task and generates the workflow; **Executor**
runs it while monitoring performance signals. At each step the Designer decides
which operators to invoke next, how to compose their outputs, and whether to
adapt the workflow based on intermediate results.

Reported: outperforms static baselines on reasoning-heavy tasks (math, QA),
better cross-task generalization, efficiency gains from adaptive operator
selection — advantage largest when problem complexity varies or several solution
strategies could apply.
[DyFlow (2509.26062)](https://arxiv.org/pdf/2509.26062)

### §6.3 HyEvo — heterogeneous atomic synthesis

A meta-agent that diagnoses failures by reading execution logs, learns from
high-performing reference workflows, formulates a natural-language diagnosis,
then jointly optimizes **topology and node semantics**. Its second idea is the
one that matters for cost: mixing *probabilistic LLM nodes* for semantic
reasoning with *deterministic code nodes* for rule-based execution.

| HyEvo result | Value |
|---|---|
| GSM8K | 93.36% |
| MATH | 53.91% |
| HumanEval | 93.89% |
| Inference cost reduction | **up to 19×** |
| Execution latency reduction | **up to 16×** |

(vs. the SOTA open-source baseline.)
[HyEvo (2603.19639)](https://arxiv.org/pdf/2603.19639)

**The largest efficiency win came from deciding which steps shouldn't be LLM
calls at all.**

Related self-evolving systems: [EvoAgentX](https://www.alphaxiv.org/overview/2507.03616v2),
[SEW (2505.18646)](https://arxiv.org/pdf/2505.18646),
[Autogenesis (2604.15034)](https://arxiv.org/pdf/2604.15034),
[GraphFlow (2605.22566)](https://arxiv.org/html/2605.22566),
[Meta-Agent-Workflow (ACM WWW'25)](https://dl.acm.org/doi/10.1145/3701716.3715247).

### §6.4 VISTA — the agent managing its own context

Diagnosis: **frontier models are proprioceptively blind to their own context** —
they cannot perceive block size, recency, or access history from the prompt
alone, so they cannot make good keep-or-drop decisions.

VISTA (*Visible Internal State for Tool Agents*) adds a **dashboard** (per-block
token usage, recency, access history, remaining budget), **archive/recovery**
(externalize blocks as exact payloads under stable handles, lossless), and a
**workspace** (working memory as typed, addressable blocks rather than an
append-only transcript). Context actions join the tool space: `archive(S, ρ)`,
`read(h, q)`, `delete(S)`.

| Benchmark | VISTA | Baselines |
|---|---|---|
| LOCA-Bench (million-token) | **50.7%** | Claude Code 42.7%, ReAct 22.7% |
| BrowseComp-Plus (100K) | **58.0%** | 52.0% strongest baseline |
| GAIA (short trajectories) | 73.3% | Claude Code 73.9% (competitive) |

Two findings matter most: **gains grow with context pressure**, and the approach
**transfers across four model backbones without training**. On short tasks it
provides no advantage — the overhead only pays off under pressure.
[VISTA (2606.30005)](https://arxiv.org/html/2606.30005)

### §6.5 Routing and cascades

- **Cascades**: the prompt flows through increasingly capable models, stopping as
  soon as a quality threshold is met.
- **Layered practice**: cheap rule-based pass for obvious cases → embedding/
  classifier pass for the ambiguous middle → at-inference cascade for the hard
  tail. Pre-request rules are cheapest, at-inference cascades most accurate,
  post-response retry is the safety net.
- **Routing raises quality, not just lowers cost**: a well-designed router can
  outperform the single most capable model by exploiting per-model strengths.
- **CASTER** reports context-aware model routing matching strong-model success
  rates while reducing inference cost in its evaluated domains — research
  evidence, not a production guarantee.
  [CASTER (2601.19793)](https://arxiv.org/abs/2601.19793)
- A 2026 ACL paper describes an **LLM scheduler** that dynamically decides
  whether specialist stages (refinement, verification, testing) run, instead of
  following a fixed workflow.
  [LLM-as-Scheduler, ACL 2026](https://aclanthology.org/2026.acl-long.581.pdf)

[Dynamic model routing and cascading survey (2603.04445)](https://arxiv.org/html/2603.04445v2) ·
[Is escalation worth it? (2605.06350)](https://arxiv.org/pdf/2605.06350) ·
[Unified routing and cascading (ETH SRI)](https://files.sri.inf.ethz.ch/website/papers/dekoninck2024cascaderouting.pdf) ·
[LLM model routing 2026](https://www.digitalapplied.com/blog/llm-model-routing-2026-cost-quality-optimization-engineering-guide) ·
[Multi-model routing orchestration 2026](https://mindra.co/blog/multi-model-routing-llm-orchestration-2026)

### §6.6 Graph vs. loop

A single agent loop with good observability will reveal whether coordination is
needed *before* the coordination layer is built. Graphs earn their keep for four
specific runtime needs — **durable execution, streaming, human-in-the-loop
interrupts, managed memory**. Absent those, the graph is overhead.

The counter-pressure to dynamic topology is the 12-factor discipline: a
**stateless reducer** `f(events) -> next_action`, buying deterministic replay,
testability, pause/resume, and clean handoff; paired with "own your context
window" — construct every LLM call explicitly rather than letting a framework
auto-stuff history.

[Zylos — Graph orchestration in production](https://zylos.ai/research/2026-04-14-graph-based-agent-workflow-orchestration-production/) ·
[12-Factor Agents](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md) ·
[LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) ·
[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) ·
[OpenAI Agents SDK — durable execution](https://openai.github.io/openai-agents-python/running_agents/) ·
[AutoGen Selector Group Chat](https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/selector-group-chat.html)

---

## §7 Hierarchical decomposition

### §7.1 Decomposition structures — the taxonomy

The test-time-scaling survey organizes the space by **subproblem structure**:

| Structure | Mechanism | Combination method | Best for |
|---|---|---|---|
| **Sequential** | Ordered steps, each builds on the last | Direct output chaining | Procedural/cumulative reasoning (CoT, Least-to-Most) |
| **Parallel** | Independent subproblems solved simultaneously | Voting, verification | Verification, self-consistency |
| **Tree** | Branching states with backtracking | Search (MCTS, A*) | Creative problem-solving, planning |
| **Graph** | Arbitrary interdependencies | Search over the graph | Multi-step planning, coordination |
| **Recursive/hierarchical** | Subdivide into similar smaller problems at different abstraction levels | Compositional assembly | **Compositional reasoning and tool use** |

[Test-time scaling survey (2511.14772)](https://arxiv.org/pdf/2511.14772) ·
[Divide-and-conquer prompting effectiveness (2402.05359)](https://arxiv.org/pdf/2402.05359)

### §7.2 Decompose-before-solving

- **Least-to-Most**: prompt the model to break the problem into sub-problems
  *without solving them*, then solve sequentially, appending each answer to the
  prompt for the next. Reported gains on symbolic manipulation, compositional
  generalization, and math. Limitations: assumes a mostly linear sequence; may
  accumulate prior answers into a growing context; decomposition quality
  determines solution quality.
  [Least-to-Most (2205.10625)](https://arxiv.org/abs/2205.10625)
- **Self-ask**: the model explicitly generates follow-up questions, answers them,
  then answers the original. Follow-ups can route to a search engine. Useful
  when required subquestions cannot be enumerated in advance.
  [Self-ask (2210.03350)](https://arxiv.org/abs/2210.03350)
- **Decomposed Prompting (DecomP)**: separates a complex task into modular
  subtask prompts with notations representing program state, so sub-tasks
  dispatch to **heterogeneous modules** — a shared library of specialized
  prompting-based LLMs. This is the mechanism for "different models for different
  layers of abstraction": the module registry is where model choice per sub-task
  lives.
  [DecomP, ICLR 2023](https://openreview.net/pdf?id=_nGgzQjzaRy) ·
  [Overview](https://www.emergentmind.com/topics/decomposed-prompting) ·
  [Advanced decomposition techniques](https://learnprompting.org/docs/advanced/decomposition/introduction)
- **Task-decoupled planning**: addresses **entangled planning**, where task
  planning and action execution become intertwined, causing inefficient
  exploration. Separates high-level semantic decomposition from low-level
  behavioral implementation, kept **independent yet coordinated through
  intermediate representations**. Feedback loops enable plan refinement **without
  full replanning**. Reported improvements on long-horizon benchmarks in success
  rate and planning efficiency.
  [Beyond Entangled Planning (2601.07577)](https://arxiv.org/pdf/2601.07577)

### §7.3 ADaPT — decompose only on failure

An LLM **executor** attempts the sub-task; a self-generated **success heuristic**
judges completion; on failure the **planner** recursively decomposes that
sub-task further and the controller calls itself. The tree deepens *only where
the executor actually failed* — depth adapts to both task complexity and the
executor model's capability.

| Benchmark | Improvement over ReAct / Plan-and-Execute |
|---|---|
| ALFWorld | **+28.3 pts** (absolute) |
| WebShop | **+27 pts** |
| TextCraft | **+33 pts** |

[ADaPT (2311.05772)](https://arxiv.org/pdf/2311.05772) ·
[ACL Findings NAACL 2024](https://aclanthology.org/2024.findings-naacl.264/) ·
[Project page](https://allenai.github.io/adaptllm/)

This is the highest-evidence, lowest-cost result in §7.

### §7.4 ReWOO — decouple reasoning from observation

Instead of an LLM call after every tool use (ReAct), ReWOO plans **all** steps up
front using **placeholders** (`#E1`, `#E2`) for results not yet obtained,
executes the tools, then integrates.

**Result: 2 LLM calls (plan + integrate) regardless of the number of tools.** In
its reported HotpotQA experiment: **5× token efficiency and +4 pp accuracy** over
the compared baseline. The saving is structural — observation text never re-enters
a reasoning prompt, so context doesn't grow with tool count.

Tradeoff: planning blind is brittle when the environment is unknown. ReWOO suits
*predictable* tool sequences; an unexplored codebase is not that.
[ReWOO (2305.18323)](https://arxiv.org/abs/2305.18323) ·
[NVIDIA NeMo — ReWOO agent](https://docs.nvidia.com/nemo/agent-toolkit/1.2/workflows/about/rewoo-agent.html) ·
[Agent Patterns — ReWOO](https://agent-patterns.readthedocs.io/en/stable/patterns/rewoo.html)

### §7.5 LLMCompiler — sub-tasks as a parallel DAG

A **Planner** streams a DAG of tasks, each with a tool, arguments, and dependency
list; a **Task Fetching Unit** schedules and dispatches each task the moment its
dependencies resolve.

Reported **3.6× speedup**, exceeding plan-and-execute, ReWOO, and native parallel
tool calling, while reducing redundant LLM calls.
[LLMCompiler (2312.04511)](https://arxiv.org/abs/2312.04511) ·
[LangChain — planning agents](https://blog.langchain.com/planning-agents/)

### §7.6 Orchestrator-worker — the production data point

Anthropic's Research system is the best-documented production instance: a lead
agent plans and spawns **3–5 specialized subagents in parallel**, each with its
own context window, tools, and trajectory. Parallelism at **two levels**
(parallel subagents, parallel tool calls within each). A **separate citation
pass** after synthesis.

| Metric | Value |
|---|---|
| vs. single-agent Claude Opus 4 (internal eval) | **+90.2%** |
| Token cost | **~15× a normal chat** |
| Research time reduction on complex queries | **up to 90%** |

**The coding caveat, stated by Anthropic:** these systems *"excel at problems
that can be divided into parallel strands of research, but are **less effective
for tightly interdependent tasks such as coding**."*

The +90.2% result is specific to that internal research evaluation and does not
imply multi-agent architecture is universally superior.

[Anthropic — when to use multi-agent systems](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them) ·
[Anthropic — how we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) ·
[ByteByteGo breakdown](https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent) ·
[ZenML LLMOps database](https://www.zenml.io/llmops-database/building-a-multi-agent-research-system-for-complex-information-tasks)

Also in production: **OpenAI Deep Research** creates a research plan, performs
multi-step search and analysis, refines queries, aggregates sources, and produces
a cited synthesis. Internal scheduling details are not public.
[Deep research in ChatGPT](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt) ·
[Research with ChatGPT](https://openai.com/academy/search-and-deep-research/)

### §7.7 Blackboard — the mechanism for revising earlier sub-answers

A **blackboard** is a shared, globally accessible structured workspace holding
the problem definition, all intermediate partial solutions, active hypotheses,
and goal criteria, incrementally accumulated and visible to every participant.

- **Indirect coordination** — agents interact through shared state, not by
  messaging each other. Adding a revision step doesn't require rewiring.
- **Opportunistic control** — a central agent posts a request; specialists
  monitoring the board decide whether they can contribute. Control order is not
  fixed in advance.
- **Write–Critique–Refine loop** over shared state with adversarial perspectives
  cross-checking; reported to reduce hallucination.
- Suited to problems where **structure emerges during computation**.

**PatchBoard** is worth specific attention for implementation: schema-grounded
*state mutation* gives the revision step an auditable, typed form rather than
free-text overwriting.

[Blackboard multi-agent systems (2507.01701)](https://arxiv.org/pdf/2507.01701) ·
[Blackboard for information discovery (2510.01285)](https://arxiv.org/pdf/2510.01285) ·
[PatchBoard (2605.29313)](https://arxiv.org/pdf/2605.29313) ·
[ARIADNE (2605.02431)](https://arxiv.org/pdf/2605.02431) ·
[Theater of Mind / Global Workspace (2604.08206)](https://arxiv.org/html/2604.08206v1)

### §7.8 Adjacent search and recursion structures

- **Tree of Thoughts** — explores several candidate reasoning paths, evaluates
  them, looks ahead and backtracks. Addresses a *different* need: decomposition
  separates parts of a problem; ToT explores alternative solutions to the same
  problem. Expensive; not a default.
  [ToT (2305.10601)](https://arxiv.org/abs/2305.10601)
- **Graph of Thoughts** — intermediate outputs as graph nodes that can be
  combined, refined, or connected by dependency edges; supports aggregation and
  feedback cycles.
  [GoT (2308.09687)](https://arxiv.org/abs/2308.09687)
- **CoDA** — one shared LLM in two contextually isolated roles: a high-level
  planner with concise strategic context, and a low-level executor with an
  ephemeral tool-interaction workspace.
  [CoDA (2512.12716)](https://arxiv.org/abs/2512.12716)
- **ReCAP** — recursive planning that executes the next subtask and refines
  remaining work while reinjecting structured parent information; bounds active
  context relative to recursion depth rather than carrying a flat history.
  [ReCAP (2510.23822)](https://arxiv.org/abs/2510.23822)
- **Recursive language models** — self-invocation as a core primitive: the model
  calls isolated child instances and composes their results. Theoretical
  motivation is keeping active context much smaller than a single flat sequence.
  [Recursive Models for Long-Horizon Reasoning (2603.02112)](https://arxiv.org/abs/2603.02112)
- **TDAG** — dynamic task decomposition paired with **agent generation**: the
  system generates the specialist the decomposition calls for rather than routing
  to a fixed roster. Positioned as a mitigation for error propagation in fixed
  decomposition schemes.
  [TDAG, Neural Networks 2025](https://www.sciencedirect.com/science/article/abs/pii/S0893608025000796) ·
  [Dynamic task decomposition](https://www.emergentmind.com/topics/dynamic-task-decomposition)

### §7.9 Decomposition failure statistics

**Specification and system design issues — including task misinterpretation and
poor decomposition — account for ~41.8% of all multi-agent system failures.**
Sub-tasks sliced too granular or too broad leave downstream solvers with
unfinishable work. Unlike human teams, LLM sub-agents cannot ask clarifying
questions mid-task, cannot read between the lines, and cannot self-correct when
coordination breaks down.

If an early sub-task fails, the error propagates and the whole task fails;
sequential dependency chains multiply this. For tasks split into dozens of
sub-tasks, planning becomes constrained by context length, causing **forgetting
of the planning trajectory**.

[Why multi-agent LLM systems fail](https://futureagi.substack.com/p/why-do-multi-agent-llm-systems-fail) ·
[The compounding errors problem](https://www.zartis.com/the-compounding-errors-problem-why-multi-agent-systems-fail-and-the-architecture-that-fixes-it/) ·
[Planning of LLM agents: a survey (2402.02716)](https://arxiv.org/pdf/2402.02716) ·
[Collaboration, failure attribution, self-evolution in LLM-MAS (2605.14892)](https://arxiv.org/pdf/2605.14892) ·
[SHIELDA — structured exception handling (2508.07935)](https://arxiv.org/pdf/2508.07935)

### §7.10 The decomposition arithmetic

Splitting one large call into many small calls does not automatically reduce
tokens:

```
One large call:     40,000 in + 4,000 out            =  44,000 tokens
Ten small calls:    10 × (6,000 in + 500 out)        =  65,000 tokens
```

Repeated per-call preamble can make the decomposed version **more** expensive and
slower. **Decomposition saves tokens only when each sub-call's context is
genuinely *narrower*, not merely *separate*.**

The correct objective: *minimize total resource consumption subject to passing
the same quality, safety, and reliability thresholds* — measured as total input
+ output + reasoning tokens + cache-write + cache-read + failed/retried calls +
routing and evaluator calls.

---

## §8 Platform feature surface

### §8.1 The Claude Code source teardown — the harness-first measurement

The only peer-reviewed structural analysis of a production coding agent. Liu,
Zhao, Shang & Shen analyzed Claude Code's publicly available TypeScript source
and compared it against two independent open-source agents, **OpenClaw** and
**Hermes Agent**, chosen because they answer the same design questions in
different deployment contexts.
[Dive into Claude Code (2604.14228)](https://arxiv.org/abs/2604.14228)
(v1 2026-04-14, v2 2026-07-02)

**The structural claim**, stated in the abstract: the core is *"a simple
while-loop that calls the model, runs tools, and repeats. Most of the code,
however, lives in the systems around this loop."* Documented subsystems:

| Subsystem | As reported |
|---|---|
| Permission system | **Seven modes** plus an ML-based classifier, evaluated deny-first |
| Compaction | **Five-layer** pipeline (see below) |
| Extensibility | **Four mechanisms** — MCP, plugins, skills, hooks |
| Delegation | Subagent orchestration |
| Persistence | Append-oriented session storage |

The architecture is traced from **five human values** — human decision authority;
safety, security, and privacy; reliable execution; capability amplification;
contextual adaptability — through **thirteen design principles** to concrete
implementation choices.

**The five compaction layers**, in escalation order: budget reduction (replace
oversized raw tool output with reference pointers) → *Snip* (trim older,
less-relevant history) → *Microcompact* (fine-grained, **cache-aware**
compression) → context collapse → auto-compact. This is the progressive
cheapest-first discipline of §2.4 as a shipped implementation, and the
cache-awareness at layer three is the §3.2 constraint made structural.

> **Attribution caution.** The widely circulated figure that **only 1.6% of the
> codebase is AI decision logic and 98.4% is operational infrastructure** comes
> from [secondary commentary](https://arxiviq.substack.com/p/dive-into-claude-code-the-design),
> **not** from the paper's abstract. It is directionally consistent with the
> paper's own structural claim, but the ratio itself is unverified against the
> primary text and should not be quoted as a paper finding without checking.

Two limits on transfer. The analysis is **one system at one version**, and the
paper's own comparison against OpenClaw and Hermes Agent is the point: *the same
design questions produce different answers across deployment contexts.* Read the
subsystem list as an existence proof of what a mature harness contains, not as a
specification. §1 applies here as everywhere — harness effects do not transfer
unexamined.

### §8.2 Context cost per extension point

The second column is the part usually missed. Figures as documented by Anthropic
for Claude Code; treat as the reference implementation, not a universal.

| Feature | When it loads / context cost |
|---|---|
| **CLAUDE.md / rules** | Session start, **full content, every request**. Keep under 200 lines |
| **Skills** | Descriptions at start, **full content on use**. `disable-model-invocation: true` → **zero** until invoked |
| **Subagents** | Isolated from main session; own input/output tokens; returns a 1,000–2,000 token summary (§2.7) |
| **Agent teams** | Highest cost — each teammate is a full instance. Experimental, off by default |
| **MCP** | Tool **names** at start, **schemas deferred**; tool search on by default (§2.6) |
| **Code intelligence (LSP)** | Low — and **net-negative**, since symbol lookup replaces file reads |
| **Hooks** | **Zero unless the hook returns output** |
| **Plugins / marketplaces** | Packaging only |
| **Artifacts** | Output channel |

[Claude Code — Extend Claude Code](https://code.claude.com/docs/en/features-overview) ·
[Claude Code 2026 guide — 25 features](https://www.marktechpost.com/2026/06/14/claude-code-guide-2026-25-features-with-examples-demo/) ·
[Checkpoints and rewind](https://theaiarchitects.com/blog/claude-code-checkpoints) ·
[Understanding Claude Code's full stack](https://alexop.dev/posts/understanding-claude-code-full-stack/) ·
[Skills vs Tools vs MCP vs Subagents vs Hooks](https://dev.to/miaoshuyo/skills-vs-tools-vs-mcp-vs-subagents-vs-hooks-2026-ultimate-comparison-kpi)

**Feature parity is an active competitive axis** — qwen-code has an open issue
*"Bring subagent system to feature parity with Claude Code"*; opencode has
*"Skills 2.0 — Subagents, Dynamic Context Injection, and Advanced Skill
Capabilities."*
[qwen-code #2409](https://github.com/QwenLM/qwen-code/issues/2409) ·
[opencode #17791](https://github.com/anomalyco/opencode/issues/17791)

Vendor documentation for the same surface elsewhere:
[Gemini CLI — Subagents](https://geminicli.com/docs/core/subagents/) ·
[Gemini CLI — Agent Skills](https://geminicli.com/docs/cli/using-agent-skills/) ·
[Gemini CLI — Hooks reference](https://geminicli.com/docs/hooks/reference/) ·
[Gemini CLI — Extension reference](https://geminicli.com/docs/extensions/reference/) ·
[Claude Managed Agents — agent setup](https://platform.claude.com/docs/en/managed-agents/agent-setup) ·
[Claude Managed Agents — MCP connector](https://platform.claude.com/docs/en/managed-agents/mcp-connector) ·
[Claude Managed Agents — Skills](https://platform.claude.com/docs/en/managed-agents/skills)

---

## §9 Computer use

**OSWorld 2.0 reports only 20.6% full completion** for its best evaluated setup
on very long real-world workflows. Named failure modes: losing constraints,
missing changing information, guessing instead of asking, and skipping
verification.
[OSWorld 2.0 (2606.29537)](https://arxiv.org/abs/2606.29537)

Claims of a "professional computer operator" need task-specific, end-to-end
evidence rather than success on short demos.

---

## §10 Evaluation and safety practice

### §10.1 What a credible 2026 evaluation includes

At least: one public repository-repair benchmark, one terminal/tool-use
benchmark, one reliability measure, **and one private task set** — public
benchmarks post-SWE-bench saturation are substantially gamed.
[Coding-agent evaluation harnesses after SWE-bench saturation](https://www.appliedtechnologyindex.com/research/2026-comparative-analysis-coding-agent-evaluation-harnesses-after-swe-bench/)

Anthropic's 2026 evaluation guidance recommends multiple grader types for complex
agents — deterministic graders, state-based checks, model graders, and selective
human review.
[Anthropic — Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

For context handling specifically, use probe-based metrics scoring artifact
tracking and decision continuity — never compression ratio alone (§2.3).

Anthropic's harness-design guidance warns that harness complexity becomes
obsolete as models improve and should be **regularly ablated**.
[Anthropic — Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)

### §10.2 Approval fatigue and containment

Anthropic reports users approved approximately **93% of traditional permission
prompts**. Its current guidance emphasizes **containment** — limiting what an
agent is capable of doing — even when behavioral defenses fail.
[Anthropic — How we contain Claude](https://www.anthropic.com/engineering/how-we-contain-claude)

The structural response to that number is graded authority rather than a single
prompt: seven permission modes plus an ML classifier, evaluated deny-first
`[§8.1]`.

MCP-specific security requirements (token audience validation, no token
passthrough, per-client consent, least-privilege scopes, confused-deputy and SSRF
defenses, treating server tool descriptions and returned content as untrusted):
[MCP — Security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)

### §10.3 Foundational architecture guidance

Anthropic's production guidance favors simple, composable patterns, adding
complexity only when evaluation demonstrates a gain, and distinguishes
deterministic workflows for known paths from model-directed agents for genuinely
open-ended paths.
[Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents?lang=en-US)

---

## §11 Where the evidence is thin

Read this before treating anything above as settled.

1. **Harness gains do not transfer across models** (§1). This is the single
   largest qualifier on the whole document.
2. **Dynamic-graph results are on short reasoning benchmarks.** DyFlow, HyEvo,
   and most of §6 are evaluated on GSM8K, MATH, HumanEval, and QA — not
   multi-hour repository work. Transfer to long-horizon coding is *plausible, not
   demonstrated*.
3. **Meta-level calls are themselves cost.** A Designer or decomposer call must
   be cheaper than the waste it avoids. On short tasks it isn't — exactly what
   VISTA's GAIA result shows (§6.4).
4. **Compaction chains are unmeasured** (§2.3). Existing long-context benchmarks
   test single-session recall, not sequential lossy compression over days.
5. **No benchmark measures composed pipelines.** Results are per-technique
   (ADaPT on ALFWorld, LLMCompiler on parallel tool calls, orchestrator-worker on
   research). A runtime combining decomposition + projection + back-revision +
   tool DAG + synthesis has no published measurement.
6. **Back-revision is not standard.** Blackboards support it; mainstream agent
   frameworks default to forward-only pipelines.
7. **The strongest decomposition evidence explicitly excludes coding** (§7.6).
8. **The source-level teardown is one system at one version** (§8.1). It
   establishes what a mature harness *contains*, not that any subsystem is
   load-bearing — no ablation accompanies it. The paper's own comparison against
   two independent agents is the caveat: the same design questions get different
   answers per deployment context. Vendor internals also move faster than the
   analyses describing them (§4.1).

---

## §12 Documented anti-patterns

Each is a failure mode named in a source above, not a stylistic preference.

**Context**
- Front-loading the repository or knowledge base "just in case" — context rot,
  lost-in-the-middle (§2.1).
- Connecting every available MCP server — 50K–138K tokens of schema before
  reasoning (§2.6).
- Compacting at 95%+ — context anxiety, incomplete compressions (§2.3).
- Reporting compression ratio as the quality metric (§2.3).
- Extracting durable facts at compaction time rather than writing them at
  creation time (§2.4).
- Treating the full conversation transcript as authoritative state.
- Letting a framework assemble context implicitly (§6.6).

**Retrieval and tools**
- Using vector search as the only retrieval mechanism (§4).
- Overlapping tools a human couldn't disambiguate (§2.9).

**Control and verification**
- Self-critique without an external signal — self-verification bias (§5).
- Using an LLM judge as the only verification method.
- Trusting tool success strings without checking resulting state.
- Claiming completion without observable verification.
- Making the model perform deterministic loops and data processing (§6.3).
- Retrying uncertain external mutations without idempotency.

**Architecture and process**
- Building the graph before observability proves it necessary (§6.6).
- Creating a multi-agent graph before establishing a single-agent baseline.
- Relying on frequent approval prompts as the primary security boundary (§10.2).
- Measuring cost per call instead of cost per successful task (§7.10).
- Optimizing token count while ignoring additional calls and lost accuracy.
- Keeping stale harness complexity after a model upgrade (§10.1).
- Summarizing without retaining recoverable source artifacts.

---

## §13 Source index

**Vendor engineering — Anthropic**
[Building effective agents](https://www.anthropic.com/engineering/building-effective-agents?lang=en-US) ·
[Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) ·
[Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) ·
[Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use) ·
[Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) ·
[Scaling Managed Agents](https://www.anthropic.com/engineering/managed-agents) ·
[Harness design for long-running apps](https://www.anthropic.com/engineering/harness-design-long-running-apps) ·
[Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) ·
[When to use multi-agent systems](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them) ·
[Demystifying evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) ·
[How we contain Claude](https://www.anthropic.com/engineering/how-we-contain-claude) ·
[Extend Claude Code](https://code.claude.com/docs/en/features-overview) ·
[Managed Agents: setup](https://platform.claude.com/docs/en/managed-agents/agent-setup) ·
[Managed Agents: MCP connector](https://platform.claude.com/docs/en/managed-agents/mcp-connector) ·
[Managed Agents: Skills](https://platform.claude.com/docs/en/managed-agents/skills)

**Vendor engineering — OpenAI, Google, others**
[OpenAI — Compaction](https://developers.openai.com/api/docs/guides/compaction) ·
[OpenAI — Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search) ·
[OpenAI — Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) ·
[OpenAI — Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization) ·
[OpenAI — Background mode](https://developers.openai.com/api/docs/guides/background) ·
[OpenAI — Model guidance](https://developers.openai.com/api/docs/guides/latest-model) ·
[OpenAI — Agents SDK durable execution](https://openai.github.io/openai-agents-python/running_agents/) ·
[OpenAI — Deep research](https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt) ·
[OpenAI — Research with ChatGPT](https://openai.com/academy/search-and-deep-research/) ·
[Gemini 2.5 implicit caching](https://developers.googleblog.com/en/gemini-2-5-models-now-support-implicit-caching/) ·
[Gemini CLI — Subagents](https://geminicli.com/docs/core/subagents/) ·
[Gemini CLI — Agent Skills](https://geminicli.com/docs/cli/using-agent-skills/) ·
[Gemini CLI — Hooks](https://geminicli.com/docs/hooks/reference/) ·
[Gemini CLI — Extensions](https://geminicli.com/docs/extensions/reference/) ·
[LangGraph — Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) ·
[LangGraph — persistence](https://docs.langchain.com/oss/python/langgraph/persistence) ·
[LangChain — planning agents](https://blog.langchain.com/planning-agents/) ·
[AutoGen — Selector Group Chat](https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/selector-group-chat.html) ·
[Microsoft — mcp-cli dynamic tool discovery](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/mcp-vs-mcp-cli-dynamic-tool-discovery-for-token-efficient-ai-agents/4494272) ·
[NVIDIA NeMo — ReWOO agent](https://docs.nvidia.com/nemo/agent-toolkit/1.2/workflows/about/rewoo-agent.html) ·
[MCP — Security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)

**Vendor engineering — retrieval and indexing**
[Cursor — Securely indexing large codebases](https://cursor.com/blog/secure-codebase-indexing) ·
[How Cursor actually indexes your codebase](https://towardsdatascience.com/how-cursor-actually-indexes-your-codebase/) *(secondary)* ·
[How Cursor indexes codebases fast](https://read.engineerscodex.com/p/how-cursor-indexes-codebases-fast) *(secondary)*

**arXiv and peer-reviewed — harness, context, verification**
[Dive into Claude Code (2604.14228)](https://arxiv.org/abs/2604.14228) ·
[Harness-Bench (2605.27922)](https://arxiv.org/pdf/2605.27922) ·
[Interplay of Harness Design and Post-Training (2606.25447)](https://arxiv.org/pdf/2606.25447) ·
[HarnessBridge (2606.12882)](https://arxiv.org/pdf/2606.12882) ·
[Less Context, Better Agents (2606.10209)](https://arxiv.org/abs/2606.10209) ·
[VISTA (2606.30005)](https://arxiv.org/html/2606.30005) ·
[Agent Skills for LLMs (2602.12430)](https://arxiv.org/html/2602.12430v3) ·
[ReVeal (2506.11442)](https://arxiv.org/pdf/2506.11442) ·
[LocAgent (2503.09089)](https://arxiv.org/pdf/2503.09089) ·
[CORE-Bench code retrieval (2606.11864)](https://arxiv.org/pdf/2606.11864) ·
[OSWorld 2.0 (2606.29537)](https://arxiv.org/abs/2606.29537)

**arXiv and peer-reviewed — decomposition and planning**
[Least-to-Most (2205.10625)](https://arxiv.org/abs/2205.10625) ·
[Self-ask (2210.03350)](https://arxiv.org/abs/2210.03350) ·
[DecomP, ICLR 2023](https://openreview.net/pdf?id=_nGgzQjzaRy) ·
[ReWOO (2305.18323)](https://arxiv.org/abs/2305.18323) ·
[LLMCompiler (2312.04511)](https://arxiv.org/abs/2312.04511) ·
[ADaPT (2311.05772)](https://arxiv.org/pdf/2311.05772) ·
[Tree of Thoughts (2305.10601)](https://arxiv.org/abs/2305.10601) ·
[Graph of Thoughts (2308.09687)](https://arxiv.org/abs/2308.09687) ·
[CoDA (2512.12716)](https://arxiv.org/abs/2512.12716) ·
[ReCAP (2510.23822)](https://arxiv.org/abs/2510.23822) ·
[Recursive Models for Long-Horizon Reasoning (2603.02112)](https://arxiv.org/abs/2603.02112) ·
[Task-decoupled planning (2601.07577)](https://arxiv.org/pdf/2601.07577) ·
[Test-time scaling subproblem survey (2511.14772)](https://arxiv.org/pdf/2511.14772) ·
[Divide-and-conquer prompting (2402.05359)](https://arxiv.org/pdf/2402.05359) ·
[Planning of LLM agents: a survey (2402.02716)](https://arxiv.org/pdf/2402.02716) ·
[TDAG, Neural Networks 2025](https://www.sciencedirect.com/science/article/abs/pii/S0893608025000796)

**arXiv and peer-reviewed — graphs, blackboards, routing**
[IBM — agentic workflow optimization survey](https://github.com/IBM/awesome-agentic-workflow-optimization) ·
[DyFlow (2509.26062)](https://arxiv.org/pdf/2509.26062) ·
[HyEvo (2603.19639)](https://arxiv.org/pdf/2603.19639) ·
[GraphFlow (2605.22566)](https://arxiv.org/html/2605.22566) ·
[EvoAgentX](https://www.alphaxiv.org/overview/2507.03616v2) ·
[SEW (2505.18646)](https://arxiv.org/pdf/2505.18646) ·
[Autogenesis (2604.15034)](https://arxiv.org/pdf/2604.15034) ·
[Meta-Agent-Workflow (ACM WWW'25)](https://dl.acm.org/doi/10.1145/3701716.3715247) ·
[Blackboard multi-agent systems (2507.01701)](https://arxiv.org/pdf/2507.01701) ·
[Blackboard for information discovery (2510.01285)](https://arxiv.org/pdf/2510.01285) ·
[PatchBoard (2605.29313)](https://arxiv.org/pdf/2605.29313) ·
[ARIADNE (2605.02431)](https://arxiv.org/pdf/2605.02431) ·
[Global Workspace cognitive architecture (2604.08206)](https://arxiv.org/html/2604.08206v1) ·
[Dynamic model routing and cascading survey (2603.04445)](https://arxiv.org/html/2603.04445v2) ·
[Is escalation worth it? (2605.06350)](https://arxiv.org/pdf/2605.06350) ·
[Unified routing and cascading (ETH SRI)](https://files.sri.inf.ethz.ch/website/papers/dekoninck2024cascaderouting.pdf) ·
[CASTER (2601.19793)](https://arxiv.org/abs/2601.19793) ·
[LLM-as-Scheduler, ACL 2026](https://aclanthology.org/2026.acl-long.581.pdf) ·
[Vector-based MCP tool selection (2603.20313)](https://arxiv.org/pdf/2603.20313) ·
[LLM-MAS collaboration and failure attribution (2605.14892)](https://arxiv.org/pdf/2605.14892) ·
[SHIELDA (2508.07935)](https://arxiv.org/pdf/2508.07935)

**Practitioner analysis**
[Zylos — Context compaction](https://zylos.ai/research/2026-04-21-agent-context-compaction-long-running-sessions/) ·
[Zylos — Dynamic context assembly and projection](https://zylos.ai/research/2026-03-17-dynamic-context-assembly-projection-llm-agent-runtimes) ·
[Zylos — Graph orchestration in production](https://zylos.ai/research/2026-04-14-graph-based-agent-workflow-orchestration-production/) ·
[Zylos — Reflection and self-evaluation patterns](https://zylos.ai/research/2026-03-06-ai-agent-reflection-self-evaluation-patterns) ·
[12-Factor Agents](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md) ·
[Memory, compaction, tool clearing](https://tianpan.co/blog/2026-02-26-context-engineering-memory-compaction-tool-clearing) ·
[Sourcegraph — Context engineering](https://sourcegraph.com/blog/context-engineering) ·
[mem0 — Context engineering guide](https://mem0.ai/blog/context-engineering-ai-agents-guide) ·
[Inside the agentic loop](https://dev.to/monuminu/inside-the-agentic-loop-a-deep-technical-dive-into-ai-coding-agents-claude-code-and-the-4pnf) ·
[Prompt caching 2026](https://www.digitalapplied.com/blog/prompt-caching-2026-cut-llm-costs-engineering-guide) ·
[KV cache optimization 2026](https://www.digitalapplied.com/blog/kv-cache-optimization-techniques-2026-engineering-guide) ·
[LLM model routing 2026](https://www.digitalapplied.com/blog/llm-model-routing-2026-cost-quality-optimization-engineering-guide) ·
[Multi-model routing orchestration 2026](https://mindra.co/blog/multi-model-routing-llm-orchestration-2026) ·
[Context engineering reliability playbook](https://www.digitalapplied.com/blog/context-engineering-agent-reliability-playbook-2026) ·
[LLM inference optimization](https://www.morphllm.com/llm-inference-optimization) ·
[Grep replacement is three tools](https://zzet.org/gortex/grep-replacement-for-ai-agents/) ·
[Semantic code search vs grep](https://particula.tech/blog/semantic-code-search-vs-grep-coding-agents) ·
[Progressive disclosure as a design pattern](https://www.newsletter.swirlai.com/p/agent-skills-progressive-disclosure) ·
[Coding Agent Index 2026](https://medium.com/@wasowski.jarek/coding-agent-index-2026-benchmarking-full-agent-stacks-model-harness-4183305e4b90) ·
[Evaluation harnesses after SWE-bench saturation](https://www.appliedtechnologyindex.com/research/2026-comparative-analysis-coding-agent-evaluation-harnesses-after-swe-bench/) ·
[Why multi-agent LLM systems fail](https://futureagi.substack.com/p/why-do-multi-agent-llm-systems-fail) ·
[The compounding errors problem](https://www.zartis.com/the-compounding-errors-problem-why-multi-agent-systems-fail-and-the-architecture-that-fixes-it/) ·
[ByteByteGo — how Anthropic built it](https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent) ·
[ZenML LLMOps database](https://www.zenml.io/llmops-database/building-a-multi-agent-research-system-for-complex-information-tasks) ·
[Decomposed prompting overview](https://www.emergentmind.com/topics/decomposed-prompting) ·
[Dynamic task decomposition](https://www.emergentmind.com/topics/dynamic-task-decomposition) ·
[Advanced decomposition techniques](https://learnprompting.org/docs/advanced/decomposition/introduction) ·
[Agent Patterns — ReWOO](https://agent-patterns.readthedocs.io/en/stable/patterns/rewoo.html) ·
[ADaPT project page](https://allenai.github.io/adaptllm/) ·
[Speakeasy — dynamic toolsets](https://www.speakeasy.com/blog/100x-token-reduction-dynamic-toolsets/) ·
[StackOne — MCP tool discovery](https://www.stackone.com/blog/mcp-tool-search-bm25-tfidf-hybrid/) ·
[Claude Code 2026 guide](https://www.marktechpost.com/2026/06/14/claude-code-guide-2026-25-features-with-examples-demo/) ·
[Checkpoints and rewind](https://theaiarchitects.com/blog/claude-code-checkpoints) ·
[Understanding Claude Code's full stack](https://alexop.dev/posts/understanding-claude-code-full-stack/) ·
[Beyond autocomplete](https://kilo.ai/articles/beyond-autocomplete) ·
[Skills vs Tools vs MCP vs Subagents vs Hooks](https://dev.to/miaoshuyo/skills-vs-tools-vs-mcp-vs-subagents-vs-hooks-2026-ultimate-comparison-kpi) ·
[qwen-code #2409](https://github.com/QwenLM/qwen-code/issues/2409) ·
[opencode #17791](https://github.com/anomalyco/opencode/issues/17791)
