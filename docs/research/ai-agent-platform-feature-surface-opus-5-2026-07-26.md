# AI agents — platform feature surface

> **Merged:** 2026-07-26 by Claude Opus 5 (`claude-opus-5`), via Claude Code.
> Reasoning effort not exposed to the agent; recover from the session transcript
> if it matters.
> **Research date of underlying material:** 2026-07-25.
> **Status:** Research and reference. Not a decision, requirement, or plan.
> Adopting anything here is a separate decision belonging in `docs/adr/` or
> `roadmap.md`.

## What this document is

The **extension points** a modern agent platform is expected to expose — MCP,
skills, subagents, hooks, plugins, sessions, permissions, and the GUI that
configures them. It is separated from the reference architecture because it is a
different kind of knowledge: not *how the loop works*, but *what plugs into it,
what each thing costs, and how they compose*.

Two audiences:
- Building a platform → this is the capability checklist and the composition
  rules.
- Building *on* a platform → this is the map of which mechanism to reach for.

**It carries no numbers and no external links.** Measured claims cite
`ai-agent-evidence-base-opus-5-2026-07-26.md` as `[EB §n]`; the context-cost
figures live at `[EB §8]`.

| Companion | Read it for |
|---|---|
| `ai-agent-reference-architecture-opus-5-2026-07-26.md` | The loop these features plug into |
| `ai-agent-evidence-base-opus-5-2026-07-26.md` | Numbers and sources |
| `ai-agent-hierarchical-decomposition-opus-5-2026-07-26.md` | Sub-goal decomposition as a pattern |

### Provenance

| Source document (now in `docs/archive/`) | Model | Effort | Contributed |
|---|---|---|---|
| `ai-agent-dynamic-context-smart-graph-feature-surface-opus-5-2026-07-25.md` | Claude Opus 5 | medium | §1, §2, §3, §5, §6 |
| `ai-agent-dynamic-context-loop-platform-perspectives-gpt-5-6-2026-07-25.md` | GPT-5.6 | low | §4 capability checklists, §5 settings tiers, §6 |
| `ai-agent-architecture-attributes-gpt-5-6-2026-07-25.md` | GPT-5.6 | low | §3.3 MCP security |

---

## §0 The organizing idea

Every extension point below is the same move in a different costume: **hold a
cheap reference, resolve it only on demand.** Skills disclose knowledge in three
levels. Tool search defers schemas. Subagents isolate exploration behind a
summary. Hooks cost nothing until they fire. Code nodes remove steps from
inference entirely.

The second organizing idea is a design rule, not a mechanism:

> **Enforcement belongs in structure, not prose.** An instruction is a request; a
> hook is a guarantee. Structure survives context growth; prose dilutes as the
> window fills.

Everything in §2 follows from those two.

---

## §1 The extension points and what each one costs

The second column is the part usually missed. Anyone can list the features; the
cost model is what determines whether a platform is usable at scale. Figures at
`[EB §8]`.

| Feature | What it does | Context cost |
|---|---|---|
| **Project rules / `CLAUDE.md`** | Persistent per-session instructions; can be path-scoped | Loaded at session start, **full content, every request**. The most expensive thing on this list per byte — keep it short |
| **Skills** | Markdown knowledge + invocable workflows; auto-loaded when relevant | Descriptions at start, **full content only on use**. Can be configured to cost **zero** until explicitly invoked |
| **Subagents** | Own loop, isolated context, returns a summary | Isolated from the main session; own input/output tokens. Returns a small summary rather than its trajectory `[EB §2.7]` |
| **Agent teams** | Multiple independent sessions with peer-to-peer messaging and a shared task list | **Highest cost** — each teammate is a full instance |
| **MCP** | Connect external services and tools | Tool **names** at start, **schemas deferred**. Without deferral this is the single largest context waste measured `[EB §2.6]` |
| **Code intelligence (LSP)** | Symbol navigation, live type errors | Low — and **net-negative**, since symbol lookup replaces file reads |
| **Hooks** | Fire on lifecycle events; run shell, HTTP, prompt, or subagent | **Zero unless the hook returns output** |
| **Plugins / marketplaces** | Packaging layer bundling skills + hooks + subagents + MCP | Packaging only |
| **Artifacts** | Publish session output as a standalone interactive page | Output channel |

**Read the table as a budget.** Rules and un-deferred MCP schemas are paid on
every single request; everything else is paid on use or not at all. That ordering
should drive where knowledge lives.

---

## §2 The distinctions that actually matter

These are the design decisions behind the feature list, not trivia. Getting them
wrong produces a platform that has every feature and still doesn't work.

**Skill vs. subagent.** A skill is *reusable content* loaded into a context; a
subagent is *context isolation*. Choose by whether you need to share knowledge or
to keep work out of the main window. They compose — a subagent can preload
skills, and a skill can run in an isolated fork.

**Hook vs. prompt instruction.** *An instruction like "never edit `.env`" in a
rules file or a skill is a request, not a guarantee. A pre-tool-use hook that
blocks the edit is enforcement.* **If a rule must hold every time, it is a hook,
not a prompt.** Same structural-guarantee principle as permission modes.

**Subagent vs. agent team.** Subagents report only to the parent; teammates
message *each other* and self-coordinate via shared state. Teams are for
competing hypotheses and genuine discussion; subagents for "I only need the
result." Teams are the most expensive construct on the platform — reach for them
last.

**MCP vs. skill.** MCP provides the *connection and tools*; the skill provides
the *judgment* for when and how to use them. Pairing them is the documented
pattern — MCP connects the database, the skill teaches the schema and query
patterns.

**MCP is an interoperability layer, not an orchestration engine.** It connects
the agent with capabilities; it does not decide strategy. Platforms that blur
this end up with orchestration logic scattered across server definitions.

**Layering and precedence.** Get this specified explicitly, per feature type,
because the intuitive answer differs by feature:

| Feature | Layering behavior |
|---|---|
| Rules files | **Additive** across levels |
| Skills, subagents | **Override by name** (managed > user > project) |
| MCP servers | Override, local > project > user |
| Hooks | **Merge** — all matching hooks fire regardless of source |

---

## §3 Capability checklists

What "complete" means per area. Use as a gap analysis, not a mandate — most of
these earn their place only at a certain scale.

### §3.1 Agent intelligence

Tool-use loop · planning and replanning · dynamic task graphs · parallel tool
calls · model routing · reasoning-effort routing · specialist delegation ·
independent verification · reflection triggered by evidence or failure · explicit
stopping criteria.

### §3.2 Context and memory

Per-call dynamic context · token budgets by stage · prompt caching · compaction ·
recent-event pruning · hybrid retrieval · durable semantic memory · episodic
history · user preferences · artifact storage · provenance and freshness ·
**a context-debugging interface**.

The last one is underrated and is what §5.4 is about.

### §3.3 Tools and MCP

**Tools:** filesystem and shell · structured code editing · browser and computer
use · web search · code execution · image and document tools · custom function
tools · deferred tool loading · namespaces · programmatic tool composition ·
typed errors · idempotency.

**MCP transport and lifecycle:** local stdio servers · remote HTTP servers ·
OAuth · credential vaults · capability negotiation · deferred tool discovery ·
server health and lifecycle · connection reuse · automatic reconnection · ability
to disconnect idle servers · resource and prompt support · sampling and
elicitation where supported.

**MCP isolation and accounting:** tool-level permissions · per-agent MCP
isolation · audit and per-server token accounting.

**MCP security** — these are requirements, not options `[EB §10.2]`:

- validate token audience
- prohibit token passthrough
- obtain per-client consent
- use least-privilege scopes
- defend against confused-deputy attacks
- prevent server-side request forgery
- **treat server tool descriptions and returned content as untrusted input**

That last item is the one most often missed: a tool *description* is prompt
surface supplied by a third party.

### §3.4 Skills

`SKILL.md`-style progressive disclosure · built-in, organization, user, and
project scopes · scripts, templates, references, and assets · versioning ·
dependencies · installation review and trust · lazy loading · usage telemetry ·
skill-specific evaluation · provider-neutral packaging where possible.

**Even skill metadata consumes context.** Attach only what a task needs, and
provide a way to suppress a third-party skill's description without editing its
file.

Scripts bundled with a skill are *executed*, and only their output enters
context — which buys determinism as well as tokens `[EB §2.7]`.

### §3.5 Subagents

Independent context · restricted tools · per-agent model selection · per-agent
MCP servers · maximum turns, time, tokens, and cost · parallel invocation ·
structured return contracts · cancellation · recursion limits · permission
isolation · remote agent-to-agent support · trace correlation.

**Subagents should be exposed to the parent as typed capabilities.** Unlimited
shared-chat participation creates context duplication and weak boundaries.

### §3.6 Hooks

Lifecycle events worth exposing: session start and end · before and after context
compilation · before and after model calls · before tool selection · before and
after tool execution · before mutation · before compaction · after retrieval ·
before delegation · after worker completion · before final response ·
notifications and errors.

Hooks should be typed · observable · time-limited · parallel where safe · able to
add context or metadata · able to reject or rewrite a proposed action · and
**unable to bypass the core security policy**.

That last constraint matters: a hook system powerful enough to enforce policy is
powerful enough to disable it.

Demonstrated uses beyond blocking: RAG-based tool filtering, dynamic memory
injection, pre-compaction capture.

### §3.7 Extensions and plugins

An extension should be able to package skills · subagents · hooks · MCP servers ·
commands · policies · UI components · configuration schemas · secret declarations
· migrations · evaluations.

**Extensions must not inherit the user's complete environment or all
credentials.** Required secrets and capabilities are explicitly declared, and
namespaced to avoid collision.

### §3.8 Safety and governance

Sandboxing · network policy · filesystem policy · tool and command rules ·
risk-based approvals · secret management · data-retention controls · audit logs ·
organization policies · per-agent permissions · prompt-injection controls · budget
limits · emergency cancellation.

### §3.9 Developer experience

SDK · CLI · API · headless operation · streaming · structured output · session
resume · replay · test harness · mock tools · local-model support · multi-provider
support · import and export of configuration and traces.

---

## §4 Session, safety, and execution features

| Feature | Behavior and the catch |
|---|---|
| **Checkpoints / rewind** | Snapshot before every file-editing tool call; restore code, conversation, or both; survives restart. **Does not undo external side effects** (API calls, DB writes) and does not replace version control |
| **Plan mode** | Read-only exploration producing a proposal before anything executes |
| **Permission modes** | Default asks per write/command; other modes trade oversight for speed. A classifier-screened mode pre-screens each action — safe proceeds, risky blocked or escalated |
| **Sandboxing** | The 2026 default workflow: plan in the IDE → agents execute locally in a sandbox → CI and PR review before merge |
| **Background tasks** | Long shell commands run detached; the agent polls output without blocking the conversation |
| **Surfaces** | CLI, desktop app, web, IDE extensions |
| **SDK / programmatic** | Building custom agents on the same loop |

The checkpoint caveat is the important one. Checkpoints restore *your*
filesystem; they do not un-send an email. Reversibility of side effects is the
runtime's side-effect ledger's job, not the checkpoint system's.

---

## §5 GUI and configuration

A rich GUI is valuable, but exposing every internal parameter directly produces a
confusing and fragile product. Three tiers plus an observability surface.

### §5.1 Basic

Model profile (fast / balanced / strongest) · autonomy level · approval behavior ·
maximum budget · internet access · memory enabled · preferred response detail ·
enabled extensions.

### §5.2 Advanced

Model by task type · reasoning effort · context budget · compaction threshold ·
parallelism · maximum turns · retry limits · sandbox and network access · skills,
MCP servers, hooks, and subagents · data retention · caching policy.

### §5.3 Expert

Context profiles · retrieval weights · reranker configuration · dynamic-routing
policy · graph admission rules · models per capability · tool-schema visibility ·
hook ordering · custom agent definitions · provider-specific parameters ·
trace-capture policy · experimental features.

### §5.4 Runtime observability — the part that distinguishes a platform

Settings alone are not enough. The GUI should expose the **runtime's own
understanding**:

- current goal and strategy
- the generated task graph; active, blocked, and completed tasks
- **context contents and token allocation** — an interactive context-window view
- **why** a source, skill, tool, or subagent was selected
- model and reasoning level used by each call
- token, latency, and cost breakdown — including **per-MCP-server token cost**
- pending approvals
- artifacts and changed resources
- checkpoints and resume controls
- trace replay and graph time travel

**The pattern across all of these: the user configures token economics and
enforcement, not just model and API key.** Exposing what consumes context, and
letting the user override it, is itself the modern feature. It is also what makes
an adaptive agent understandable rather than mysterious — which is the
precondition for trusting it with more autonomy.

---

## §6 Why the surface is converging

This is not a theoretical checklist. Competing agents are explicitly tracking
each other's extension surface — open issues in rival projects are titled things
like *"bring the subagent system to feature parity"* and *"Skills 2.0 — subagents,
dynamic context injection, and advanced skill capabilities"* `[EB §8]`.

The seven-category surface — **project rules, skills, subagents, agent teams,
plugins, hooks, MCP servers** — has become the de facto checklist, and equivalent
constructs now exist across multiple vendors' CLIs and managed-agent platforms
`[EB §8]`.

Two consequences worth holding onto:

1. **Feature presence is table stakes; the cost model is the differentiator.**
   Everyone will have skills. Not everyone will make a skill cost zero tokens
   until invoked, or show per-server token cost in the UI.
2. **Composition rules are the hard part** (§2). A platform with all seven
   categories and no documented precedence, no isolation guarantees, and no
   enforcement story is a pile of features, not a platform.
