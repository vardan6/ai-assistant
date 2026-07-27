# Requirements — agent attribute scope

> **What this document is.** The single place where general agent research
> becomes *this project's* scope. It takes the 54 attributes of the reference
> checklist and assigns each one a **scope class** and a **target level**.
>
> It states targets, not status. Current status is
> `docs/reviews/agent-implementation-audit.md`; sequencing is `roadmap.md`.
> Priority ordering (R1 quality > R2 token > R3 runtime) is `agent-quality.md`.

## The three layers

This project deliberately keeps general research and project scope apart,
because the research is reusable and the scope is not.

| Layer | Question | Home |
|---|---|---|
| **Research** | What does a good agent look like, in general? | `docs/research/`, sources in `docs/archive/` |
| **Scope** (this doc) | Which of that applies *here*, and to what level? | `docs/requirements/agent-attributes.md` |
| **Status** | What is actually built right now? | `docs/reviews/agent-implementation-audit.md` |
| **Plan** | What do we do next, in what order? | `roadmap.md` |

`docs/research/` is **project-independent by rule**. Nothing about this codebase
belongs there, and nothing there is a commitment. The canonical checklist is
`ai-agent-reference-architecture-opus-5-2026-07-26.md` §14 ("RA §14"); every
attribute ID below refers to it. Evidence for any claim is
`ai-agent-evidence-base-opus-5-2026-07-26.md` (cited `[EB §n]`).

## Scoping doctrine

**This is a learning and prototyping project.** Over-engineering is a sanctioned
goal, not a smell. That inverts the usual filter: the reference architecture's
own advice is to add complexity only when evaluation demonstrates a gain
`[EB §10.3]`, and to ablate harness complexity as models improve `[EB §10.1]`.
That advice is correct for production and deliberately **not** the rule here.

The cost of ignoring it is real, so it is paid explicitly rather than silently:

1. **Learning work must not distort the product's evaluation.** The failure mode
   is already present in this codebase — per-question overrides raise Gate
   scores without raising capability (audit N3), so the eval overstates the
   agent. Any attribute built for study must be measurable *separately* from
   the real answer path.
2. **Invented surface area must be gated off by default.** Some attributes
   cannot be exercised at all without inventing a scenario this project does not
   have. Building those is legitimate; letting them run in the default path is
   not.

### Scope classes

| Class | Meaning | Rule |
|---|---|---|
| **C — Core** | Real value to this project as a product. | Implement to target. Judged by the replay suite. |
| **L — Learning** | Little production value here; built to understand the technique. | Implement to target, but must be independently switchable and must not change default-path behavior without a recorded eval delta. |
| **S — Synthetic** | Cannot be exercised without inventing a scenario the project lacks (a mutating tool, a hostile input, a tenant boundary). | Requires a **fixture scenario** declared in the slice. Off by default. Never counted in the product's Gate scores. |

Target levels use the audit's five-point scale: ●●●●● fully realized ·
●○○○○ absent.

---

## Attribute scope table

Marks: **Now** is the audit's assessment at commit `d80b1cf`. **Target** is what
this project commits to. **PV / LV** are production value and learning value in
*this* project (H/M/L). Where an attribute is owned by an existing track, the
owner is named and this document does not restate the finding.

### A — Evaluation

| # | Attribute | Class | Now | Target | PV | LV | Note |
|---|---|---|---|---|---|---|---|
| A1 | Independent oracle | C | ●●●●● | ●●●●● | H | H | `scripts/golden_answers.py` computes from CSVs independently of the tools. Protect this. |
| A2 | Trajectory assertions | C | ●●●●● | ●●●●● | H | H | `case_replay.py` asserts tool args, result field paths, subsequences. |
| A3 | CI regression gates | C | ●○○○○ | ●●●●○ | H | M | No `.github/workflows`. Replay is manual via `run-case-replay.sh`. |
| A4 | Harness-fitting isolated from capability | C | ●○○○○ | ●●●●● | H | H | **Gates everything else.** Audit N3 — override layer inflates scores. |
| A5 | Cost/latency as eval metrics | C | ●●○○○ | ●●●●○ | M | M | Telemetry is accurate but is not an eval assertion. |

### B — Tools

| # | Attribute | Class | Now | Target | PV | LV | Note |
|---|---|---|---|---|---|---|---|
| B1 | Structured tool results | C | ●●●●● | ●●●●● | H | M | Structured dicts only, never prose. |
| B2 | Bounded tool output | C | ●●●●○ | ●●●●● | H | M | `clamp_limit` bounds **rows, not bytes**, and is opt-in per tool. |
| B3 | Errors as data | C | ●●●●● | ●●●●● | H | M | `ToolRegistry.invoke` catches all and returns errors as data. |
| B4 | Argument validation | C | ●●●●● | ●●●●● | H | M | Validated against the handler's real signature. |
| B5 | Few, non-overlapping tools | C | ●●●●○ | ●●●●● | M | M | Nine tool modules; `derived_metrics.py` is large enough to re-check for overlap. |
| B6 | Side-effect declaration | S | ●○○○○ | ●●●○○ | L | M | Every tool is a pure read. Needs a fixture mutating tool to mean anything. |

### C — Context

| # | Attribute | Class | Now | Target | PV | LV | Note |
|---|---|---|---|---|---|---|---|
| C1 | Budgets where growth happens | C | ●●○○○ | ●●●●● | H | H | Audit N2 — history budgeted, in-loop accumulation is not. |
| C2 | Informative truncation | C | ●●●○○ | ●●●●○ | M | M | Mark elisions so the model knows information was removed. |
| C3 | Tool-result clearing | C | ●○○○○ | ●●●●○ | H | H | **New in RA §14.** Measured cheaper *and* better than retaining `[EB §2.2]`; RA §13 rules it ahead of compaction. Nothing in `app/ai/` clears stale results. |
| C4 | Structured compaction | L | ●○○○○ | ●●●○○ | L | H | Sessions are short; not needed as a product. High learning value — use a fixed template, never free-form `[EB §2.3]`. |
| C5 | Stable cacheable prefix | C | ●●●●● | ●●●●● | H | H | AQ-2 + ADR 0005. **Tension with C6/C7 — see below.** |
| C6 | Just-in-time retrieval | C | ●●●○○ | ●●●●○ | M | H | Schema card; ADR 0005 chose the static path deliberately. |
| C7 | Curated, revisable tool exposure | C | ●●○○○ | ●●●●● | H | H | Owned by **AR-3**. |
| C8 | Hybrid retrieval, not embeddings alone | L | ●●○○○ | ●●●○○ | L | H | Tools are structured queries over nine CSVs — no lexical or semantic retrieval layer exists or is needed. This is where the whole of `[EB §4, §4.1]` would land if prototyped. |

### D — Control flow

| # | Attribute | Class | Now | Target | PV | LV | Note |
|---|---|---|---|---|---|---|---|
| D1 | Cyclic loop | C | ●●○○○ | ●●●●● | H | H | Owned by **AR-2…AR-5** (review-of-record F1). |
| D2 | Revisable decisions | C | ●●○○○ | ●●●●● | H | H | Owned by **AR-2/AR-3**. |
| D3 | Verification before answering | C | ●●●○○ | ●●●●● | H | H | Reconciliation exists; audit N4 — the numeric verdict is unsound. |
| D4 | Bounded iteration | C | ●●●●● | ●●●●● | H | L | `MAX_TOOL_ITERATIONS = 6`. |
| D5 | Progress detection | C | ●○○○○ | ●●●●○ | M | H | No state-hash dedup, no per-cycle improvement check `[EB §5]`. |
| D6 | Deliberate state semantics | C | ●●●○○ | ●●●●○ | M | M | Sharpen once AR-2…AR-5 own the loop. |

### E — Reliability

| # | Attribute | Class | Now | Target | PV | LV | Note |
|---|---|---|---|---|---|---|---|
| E1 | Retry with backoff + jitter | C | ●○○○○ | ●●●●● | H | M | Audit N1 — **cheapest high-value gap in the codebase.** |
| E2 | Retryable vs terminal classification | C | ●○○○○ | ●●●●● | H | M | Audit N1. |
| E3 | Timeouts at every level | C | ●○○○○ | ●●●●● | H | M | Audit N1 — a hung provider hangs the request indefinitely. |
| E4 | Degradation ladders | C | ●●●●○ | ●●●●● | H | M | Thorough for logic failures, absent for infrastructure failures. |
| E5 | Cancellation | C | ●○○○○ | ●●●●○ | M | M | Audit N7 — abandoned streams keep consuming tokens. |
| E6 | Idempotency for retried side effects | S | ●○○○○ | ●●●○○ | L | H | No mutations exist. Pairs with B6's fixture tool. |
| E7 | Authoritative side-effect ledger | S | ●○○○○ | ●●●○○ | L | H | **New in RA §14.** Same fixture. |

### F — Observability

| # | Attribute | Class | Now | Target | PV | LV | Note |
|---|---|---|---|---|---|---|---|
| F1 | Correlation IDs | C | ●○○○○ | ●●●●● | H | M | Audit N10 — `TraceEvent` has no turn/session/trace ID. |
| F2 | Persisted traces | C | ●○○○○ | ●●●●○ | H | H | Audit N10 — events die with the request; no offline failure analysis. |
| F3 | Per-stage attribution | C | ●●●●○ | ●●●●● | H | M | Above average already. |
| F4 | Cache metrics | C | ●●●●● | ●●●●● | H | M | Incl. the Anthropic TTL-split form. |
| F5 | Streaming progress events | C | ●●●○○ | ●●●●○ | M | M | `/api/chat/stream` exists. |
| F6 | Standard instrumentation | L | ●○○○○ | ●●●○○ | L | H | No OpenTelemetry. Little product value at this size; high learning value. |

### G — Cost

| # | Attribute | Class | Now | Target | PV | LV | Note |
|---|---|---|---|---|---|---|---|
| G1 | Prompt caching, correctly applied | C | ●●●●● | ●●●●● | H | H | AQ-2. Largest single cost lever `[EB §3.1]`. |
| G2 | Enforced budgets | C | ●●○○○ | ●●●●○ | M | M | Audit N9 — measured accurately, never enforced. |
| G3 | Model and effort tiering | L | ●○○○○ | ●●●○○ | L | H | `provider_registry.py` supports multiple providers; no tiering by task. |
| G4 | Result caching | C | ●○○○○ | ●●●●○ | M | M | Audit N6 — `docs/design/architecture.md` **asserts a module that does not exist**. Fix code or doc. |
| G5 | Parallel tool execution | C | ●○○○○ | ●●●●● | H | M | Audit N5 — pure reads over in-memory pandas, safe to parallelize. |
| G6 | Warm infrastructure | C | ●●●●○ | ●●●●● | M | L | **New in RA §14.** `PandasDataSource` eager-loads all CSVs at construction; `provider_registry` caches models. Largely satisfied already. |

### H — Discipline

| # | Attribute | Class | Now | Target | PV | LV | Note |
|---|---|---|---|---|---|---|---|
| H1 | Single source of truth | C | ●●○○○ | ●●●●● | M | M | Audit N11 (`TurnKind` declared twice), N12 (runtime reflection per turn). |
| H2 | No per-case branches | C | ●○○○○ | ●●●●● | H | H | Audit N3 — **the dominant issue.** Four mechanisms in `pipeline.py`. |
| H3 | Structured output | C | ●●○○○ | ●●●●● | H | H | Audit N8 — regex prose-parsing plus a repair round-trip for a problem every provider solves natively. |
| H4 | Determinism where possible | C | ●●●○○ | ●●●●○ | H | M | Audit N4. |
| H5 | Versioned prompts | C | ●○○○○ | ●●●●○ | M | M | No prompt versioning; blocks attributing an eval delta to a prompt change. |

### I — Safety

| # | Attribute | Class | Now | Target | PV | LV | Note |
|---|---|---|---|---|---|---|---|
| I1 | Tool output untrusted | C | ●●●●● | ●●●●● | H | L | Trusted local CSVs. |
| I2 | Least privilege | C | ●●●●● | ●●●●● | H | L | Read-only tools. |
| I3 | Human approval for consequential actions | S | ●○○○○ | ●●●○○ | L | M | Nothing consequential exists to approve. Fixture required. |
| I4 | Sandboxing | S | ●○○○○ | ●●○○○ | L | M | No code execution, no shell. Lowest priority of the S class. |
| I5 | Containment over prompting | C | ●●●●● | ●●●●● | H | H | **New in RA §14.** The read-only tool surface *is* containment `[EB §10.2]` — already the right answer, by construction rather than by intent. |

---

## Class totals

| Class | Count | Of which at target |
|---|---|---|
| **C — Core** | 43 | 15 |
| **L — Learning** | 5 | 0 |
| **S — Synthetic** | 6 | 0 |

The **S class needs one enabling slice** before any of its six attributes can be
built: a gated fixture tool with a real side effect (a scratch write), off by
default, excluded from Gate scoring. Without it, B6, E6, E7, I3, and I4 are
unimplementable rather than merely unimplemented.

## Standing tensions

These are not resolvable by choosing once — they are recorded so a future slice
does not silently pick a side.

**C5 stable cache prefix vs. C6/C7 just-in-time and revisable tool exposure.**
RA §3.6 and §13 name this as genuinely unsolved and call it a per-workload
measurement, not a principle. AR-3 widens the bound tool subset mid-loop, which
fragments the prefix AQ-2 and ADR 0005 established. **Decide with a measurement
when AR-3 lands, and record it as an ADR** — do not let it be decided implicitly
by whichever slice ships first. The partial resolution in the research is a small
curated upfront set plus dynamic content appended at the *end* of context, so the
prefix survives `[EB §2.6]`.

**C3 tool-result clearing vs. C4 structured compaction.** RA §13 resolves this in
the general case: clearing first, compaction second `[EB §2.2]`. Recorded here so
C4's learning-class work is never mistaken for the primary mechanism.

**Learning-class work vs. A4.** Every L or S attribute increases harness surface
that A4 must hold constant. The mitigation is the class rule above: independently
switchable, with a recorded eval delta.

## Non-goals

Explicitly out of scope regardless of learning value, because nothing in this
project can exercise them honestly:

- Multi-agent orchestration and hierarchical decomposition
  (`ai-agent-hierarchical-decomposition-*`). The strongest evidence for it
  **explicitly excludes coding** `[EB §7.6]`, and this workload is a single
  short-horizon question-answering loop. Reference material only.
- Computer use `[EB §9]`.
- Dynamic graph rewriting and meta-agent routing `[EB §6]` — evaluated on short
  reasoning benchmarks, not this workload `[EB §11.2]`.
- Vector indexing of the dataset. C8 covers the prototyping interest; a
  production index over nine static CSVs would be strictly worse than the
  current structured tools.
