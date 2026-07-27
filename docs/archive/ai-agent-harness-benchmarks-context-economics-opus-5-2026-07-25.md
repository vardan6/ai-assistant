# Agent harness benchmarks and context economics — July 2026

> **Authored:** 2026-07-25 23:13 (+04) by Claude Opus 5 (`claude-opus-5`),
> reasoning effort: medium, via Claude Code.
> **Research date:** 2026-07-25
> **Method:** Web survey of 2026 primary sources (vendor engineering blogs,
> arXiv, benchmark reports). Every quantitative claim below is sourced.
> **Scope:** The measured, numeric side of agent design — harness effect sizes,
> context-control cost/quality tradeoffs, cache economics, verification
> reliability.
> **Status:** Research and reference. Not a decision, requirement, or plan.
> Adopting anything here is a separate decision belonging in `docs/adr/` or
> `roadmap.md`.
>
> **Siblings — read for the complementary angle, not a repeat:**
> - `best-ai-agent-architecture-summer-2026.md` — broad architectural survey.
> - `dynamic-agent-loop-and-platform-perspectives-2026.md` — dynamic context
>   construction, hierarchical orchestration, platform feature surface.
> - `modern-agent-implementation-attributes.md` — checkable attributes,
>   project-independent, no external citations.
>
> This document deliberately carries the numbers those three do not.

## Executive conclusion

The harness — not the model — is now the dominant variable in agent quality,
and its effect size is large enough to swamp model choice. But harness gains do
not transfer across models, so the only reliable method is empirical
calibration against your own model and task set.

On context: the 2026 evidence contradicts the intuition that more resident
context is safer. Aggressively dropping stale tool output measured *better*
solve rates at roughly half the cost. Stale context is not neutral ballast.

---

## 1. Harness effect sizes

- Artificial Analysis launched the first public **Coding Agent Index** in May
  2026 — the first benchmark evaluating full stacks (specific model + harness
  pairs) rather than models alone. The community question shifted from "which
  model is smartest" to "which full stack works in production."
  [Coding Agent Index 2026](https://medium.com/@wasowski.jarek/coding-agent-index-2026-benchmarking-full-agent-stacks-model-harness-4183305e4b90)
- Reported accuracy gaps across harnesses running comparable models: **up to
  ~6×**. (ibid.)
- **Harness effects are model-specific.** Harness-Bench evaluated instruction
  formatting, examples, system prompts, tool descriptions, and output format
  across multiple frontier models on document, spreadsheet, and
  evidence-auditing workflows. Choices that help one model are neutral or
  harmful on another; there is no universal best harness.
  [Harness-Bench](https://arxiv.org/pdf/2605.27922)
- The harness is precisely: which tools are exposed, how they are described,
  what auxiliary information accompanies each observation, and how context is
  assembled into the prompt.
  [Interplay of Harness Design and Post-Training](https://arxiv.org/pdf/2606.25447)
- Automated harness search exists (Meta-Harness, Lee et al. 2026: an LLM reads
  candidate harnesses and proposes new ones), which is the logical consequence
  of model-specific tuning being non-transferable. (ibid.)

**Implication.** Harness changes must be evaluated, not reasoned about. A
harness improvement validated on one model is unvalidated on the next.

## 2. Context economics

### 2.1 Why small-and-clean beats large-and-complete

- **Context rot** is mechanical, not stylistic: transformer attention is n² over
  pairwise token relations, and training distributions favor shorter sequences.
  Quality degrades as tokens accumulate.
  [Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- **Lost-in-the-middle** costs **30+ percentage points** on information placed
  mid-context.
  [Zylos — Context compaction](https://zylos.ai/research/2026-04-21-agent-context-compaction-long-running-sessions/)
- Stated objective: the **smallest set of high-signal tokens that maximizes the
  likelihood of the desired outcome**. (Anthropic, ibid.)

### 2.2 The headline measurement — observation masking

JetBrains, via a rolling window keeping only the last N tool results:

| Metric | Result vs. full context |
|---|---|
| Cost | **−52%** |
| Solve rate (Qwen3-Coder 480B) | **+2.6 pp** |
| Cost savings (general) | **50%+** |

Cheaper *and* better. Current best practice derived from this: **tool-result
clearing as the primary context-control mechanism, with compaction reserved for
preserving reasoning across long dialogue** — not the other way round.
[Context engineering: memory, compaction, tool clearing](https://tianpan.co/blog/2026-02-26-context-engineering-memory-compaction-tool-clearing)

### 2.3 Compaction — costs and failure modes

- **Trigger at 70–75%** of window (≈150K of 200K). Waiting for 95–98% induces
  "context anxiety" and produces incomplete compressions.
- **Cost per event: 3,000–5,000 output tokens and 5–15s wall-clock**, because
  it requires full-context inference plus summary generation.
- **Naive summarization loses 10–15 pp on complex multi-step tasks; structured
  compaction recovers to within 1–2%** (ACON ablations). Use a fixed template:
  Session Intent / Files Modified / Key Decisions / Next Steps.
- **Artifact tracking is the weakest dimension across all methods** — Factory.ai
  scored file-modification recall at **2.19–2.45 / 5.0**.
- **Compression ratio is a misleading primary metric**: all evaluated methods
  achieved **98–99% compression** while quality scores spanned only **3.35–3.70**.
  Evaluate with probe-based metrics over accuracy, artifact tracking,
  continuity, and instruction-following.
- Benchmark gap worth knowing: LoCoMo (300-turn multi-session) and LongBench
  (21 long-context tasks) measure **single-session recall, not compaction
  chains** — sequential lossy compressions over multi-day runs are unmeasured.

(All: [Zylos — Context compaction](https://zylos.ai/research/2026-04-21-agent-context-compaction-long-running-sessions/))

### 2.4 Cheaper techniques to exhaust first

Ordered by cost, cheapest first:

1. **Deterministic structural cleanup** — dedup identical tool outputs, purge
   resolved errors, canonicalize verbose responses. Zero model cost.
2. **Extractive compression** — LLMLingua-class methods reach **up to 20×
   compression with minimal accuracy loss**. Zero model cost.
3. **Selective eviction** — LRU or attention-weight scoring. Zero added cost,
   but positional gaps can confuse the model and importance scores miss context
   that a later sub-task will need.
4. **Summarization compaction** — see 2.3.

**Externalize at creation, not at extraction.** Offload long-lived facts to
external memory when produced, rather than mining them out of a dying context
during compaction. This is the difference between lossless and lossy. (ibid.)

### 2.5 Just-in-time retrieval and progressive disclosure

- Hold **lightweight identifiers** (file paths, queries, URLs) and resolve at
  runtime. Best practice recommends JIT over front-loading; hybrid (small
  curated upfront set + autonomous exploration) is often strongest. (Anthropic)
- **Sub-agents as context isolation devices**: a specialized agent burns its own
  window and returns a **1,000–2,000 token summary** to the coordinator.
  (Anthropic)
- **Agent Skills — three disclosure levels**: (1) name + description in the
  system prompt, (2) full `SKILL.md` on relevance, (3) bundled reference files
  on demand. Scripts are *executed* and only their output enters context, which
  also buys determinism. Bundled knowledge becomes effectively unbounded without
  inflating every interaction.
  [Anthropic — Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- **The counter-example, quantified**: naively connecting several MCP servers
  reaches **90+ tool definitions ≈ 50,000 tokens of JSON schema** before the
  model reasons at all.
  [Progressive disclosure as a system design pattern](https://www.newsletter.swirlai.com/p/agent-skills-progressive-disclosure)

### 2.6 Tool design

- Self-contained, unambiguous, minimal functional overlap. The stated test: *"if
  a human engineer can't definitively say which tool applies, an AI agent can't
  be expected to do better."*
- **Bloated tool sets are among the most common failure modes** observed in
  production.
- Tool results must be token-efficient — return the answer, not the raw dump.

(All: Anthropic — Effective context engineering)

## 3. Retrieval for code

The 2026 consensus is hybrid, with the agent selecting by query shape:

| Approach | Wins on | Fails on |
|---|---|---|
| grep / ripgrep | Exact symbols, small-to-mid repos, one-off lookups; never stale | Conceptual/intent queries |
| Embeddings | "Code related to authentication" over large corpora | **Staleness** — an index over an hourly-changing repo is stale within moments |
| Code-graph / structural | Call graphs, references, localization ([LocAgent](https://arxiv.org/pdf/2503.09089)) | Fuzzy intent |

The load-bearing argument: *an LLM driving ripgrep in a loop beats any frozen
embedding model on a codebase that changes every commit.* Give the agent
lexical, structural, and graph search as tools and **verify results against disk**.
[Grep replacement is three tools, not one](https://zzet.org/gortex/grep-replacement-for-ai-agents/) ·
[Semantic code search vs grep](https://particula.tech/blog/semantic-code-search-vs-grep-coding-agents)

## 4. Verification reliability

- **Self-verification bias**: an agent judging its own intermediate output from
  within the same trajectory state that produced it entangles verification with
  self-justification, so flawed outputs get accepted. ICLR 2024 established that
  LLMs cannot reliably self-correct reasoning without an external signal.
- **Extrinsic verification** — an independent critic in an *isolated context*
  producing actionable defect reports — is the documented fix.
- **If a test can be run, run it.** Reserve intrinsic critique for subjective
  polish no test captures.
- Multi-Agent Reflexion (MAR) reduces bias further via diverse critic personas.
- Loop safeguards: max-iteration limits, per-cycle measurable-improvement
  checks, **state-hash deduplication** to detect returning to a prior state.

[Zylos — Reflection and self-evaluation patterns](https://zylos.ai/research/2026-03-06-ai-agent-reflection-self-evaluation-patterns) ·
[ReVeal: self-evolving code agents via reliable self-verification](https://arxiv.org/pdf/2506.11442)

## 5. Speed and cost economics

### 5.1 Caching is the highest-leverage optimization

| Metric | Value |
|---|---|
| Cost savings on cache hit | **85–95%** |
| Latency reduction, cached portion, >10K tokens | **80–90%** |
| Achievable hit rate on agent loops | **60–85%** |
| Resulting per-call cost reduction | **5–12×** |
| Anthropic throughput effect at 80% hit rate | **~5×** (cached input tokens don't count toward rate limits) |

[Prompt caching in 2026](https://www.digitalapplied.com/blog/prompt-caching-2026-cut-llm-costs-engineering-guide) ·
[KV cache optimization 2026](https://www.digitalapplied.com/blog/kv-cache-optimization-techniques-2026-engineering-guide)

Cache discipline is architecture, not configuration:

1. System prefix **byte-for-byte stable**; tool definitions early and unchanging
   (tool defs are cacheable precisely because they rarely change).
2. Push volatile metadata (timestamps, dynamic state) to the **final** user
   message.
3. `cache_control` breakpoints immediately **before** volatile regions.
4. **Compaction creates a hard semantic break that invalidates all cached
   prefixes.** Anthropic's server-side API places a `cache_control` marker on the
   compaction block itself so system prompt + summary serve from cache
   afterward, and only new turns incur fresh processing.
   [Zylos — Context compaction](https://zylos.ai/research/2026-04-21-agent-context-compaction-long-running-sessions/)

### 5.2 Other levers

- Agentic tasks make **50–200 LLM calls per task** — this is what converts a
  cheap per-token price into an expensive per-task cost. Optimize per-task.
  [LLM inference optimization](https://www.morphllm.com/llm-inference-optimization)
- **Speculative decoding**: **2–3×** with off-the-shelf draft models, **up to
  5×** optimized, with output mathematically identical to autoregressive
  decoding. (ibid.)
- Parallel independent tool calls per turn; parallel sub-agents for decomposable
  work.
- Role-based model routing: cheap/fast model for search, exploration, and
  classification; frontier model for planning and edits.
- Keep connections warm — persistent tool-server processes, warm sandboxes,
  pooled HTTP/DB connections. Cold starts dominate short tool calls.

### 5.3 Reference consumption figures

- A single debugging session consumes **50,000–100,000 tokens**.
- Illustrative session cost (Sonnet, 40K in / 4K out): **~$1.84**.
- Uber: **25% of commits via Claude Code in Q1 2026**.

[Inside the agentic loop](https://dev.to/monuminu/inside-the-agentic-loop-a-deep-technical-dive-into-ai-coding-agents-claude-code-and-the-4pnf)

## 6. Loop and graph structure

- The core cycle is **gather context → act → verify → loop**, with control flow
  that **nests, branches, and retries** rather than running as a linear
  pipeline. No pre-planned full sequence; the next action derives from the last
  observation. (Inside the agentic loop, ibid.)
- **Verifiable acceptance criteria are the loop's exit condition** and the
  single strongest lever on unattended output quality. Weak prompts lack
  measurable goals. (ibid.)
- **Structural guarantees beat prompt instructions**: permission modes and tool
  allowlists survive context growth; prompt-level rules dilute as context fills.
  (ibid.)
- **Stateless reducer** — `f(events) -> next_action` — buys deterministic
  replay, testability, pause/resume, and clean handoff. Paired with "own your
  context window": construct every LLM call explicitly rather than letting a
  framework auto-stuff history.
  [12-Factor Agents](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md)
- **Graph vs. loop**: a single agent loop with good observability will reveal
  whether coordination is needed *before* the coordination layer is built.
  Graphs earn their keep for four specific runtime needs — durable execution,
  streaming, human-in-the-loop interrupts, managed memory. Absent those, the
  graph is overhead.
  [Zylos — Graph-based orchestration in production](https://zylos.ai/research/2026-04-14-graph-based-agent-workflow-orchestration-production/)

## 7. Evaluation

A credible 2026 coding-agent evaluation includes at least: one public
repository-repair benchmark, one terminal/tool-use benchmark, one reliability
measure, **and one private task set** — public benchmarks post-SWE-bench
saturation are substantially gamed.
[Coding agent evaluation harnesses after SWE-bench saturation](https://www.appliedtechnologyindex.com/research/2026-comparative-analysis-coding-agent-evaluation-harnesses-after-swe-bench/)

For context handling specifically, use probe-based metrics scoring artifact
tracking and decision continuity — never compression ratio alone (§2.3).

## 8. Documented anti-patterns

Each is a failure mode named in the sources above, not a stylistic preference:

- Front-loading the repository "just in case" — context rot, lost-in-the-middle.
- Connecting every available MCP server — 50K tokens of schema before reasoning.
- Compacting at 95%+ — context anxiety, incomplete compressions.
- Reporting compression ratio as the quality metric — 98–99% compression tells
  you nothing about the 3.35–3.70 quality spread.
- Self-critique without an external signal — self-verification bias.
- Building the graph before observability proves it necessary.
- Letting a framework assemble context implicitly.
- Overlapping tools a human couldn't disambiguate.
- Extracting durable facts at compaction time rather than writing them at
  creation time.

---

## Source index

Primary (vendor engineering / benchmark):
[Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) ·
[Anthropic — Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) ·
[Coding Agent Index 2026](https://medium.com/@wasowski.jarek/coding-agent-index-2026-benchmarking-full-agent-stacks-model-harness-4183305e4b90) ·
[SWE-bench-saturation harness comparison](https://www.appliedtechnologyindex.com/research/2026-comparative-analysis-coding-agent-evaluation-harnesses-after-swe-bench/)

arXiv:
[Harness-Bench (2605.27922)](https://arxiv.org/pdf/2605.27922) ·
[Interplay of Harness Design and Post-Training (2606.25447)](https://arxiv.org/pdf/2606.25447) ·
[HarnessBridge (2606.12882)](https://arxiv.org/pdf/2606.12882) ·
[ReVeal (2506.11442)](https://arxiv.org/pdf/2506.11442) ·
[LocAgent (2503.09089)](https://arxiv.org/pdf/2503.09089) ·
[CORE-Bench code retrieval (2606.11864)](https://arxiv.org/pdf/2606.11864) ·
[Agent Skills for LLMs (2602.12430)](https://arxiv.org/html/2602.12430v3)

Analysis / practitioner:
[Zylos — Context compaction](https://zylos.ai/research/2026-04-21-agent-context-compaction-long-running-sessions/) ·
[Zylos — Graph orchestration](https://zylos.ai/research/2026-04-14-graph-based-agent-workflow-orchestration-production/) ·
[Zylos — Reflection patterns](https://zylos.ai/research/2026-03-06-ai-agent-reflection-self-evaluation-patterns) ·
[Memory, compaction, tool clearing](https://tianpan.co/blog/2026-02-26-context-engineering-memory-compaction-tool-clearing) ·
[Sourcegraph — Context engineering](https://sourcegraph.com/blog/context-engineering) ·
[12-Factor Agents](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md) ·
[Inside the agentic loop](https://dev.to/monuminu/inside-the-agentic-loop-a-deep-technical-dive-into-ai-coding-agents-claude-code-and-the-4pnf) ·
[Prompt caching 2026](https://www.digitalapplied.com/blog/prompt-caching-2026-cut-llm-costs-engineering-guide) ·
[KV cache optimization 2026](https://www.digitalapplied.com/blog/kv-cache-optimization-techniques-2026-engineering-guide) ·
[LLM inference optimization](https://www.morphllm.com/llm-inference-optimization) ·
[Grep replacement is three tools](https://zzet.org/gortex/grep-replacement-for-ai-agents/) ·
[Semantic search vs grep](https://particula.tech/blog/semantic-code-search-vs-grep-coding-agents) ·
[Progressive disclosure as design pattern](https://www.newsletter.swirlai.com/p/agent-skills-progressive-disclosure) ·
[Context engineering reliability playbook](https://www.digitalapplied.com/blog/context-engineering-agent-reliability-playbook-2026)
