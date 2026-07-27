# Audit — agent implementation vs. modern practice

Audit date: 2026-07-25 · Commit `d80b1cf` · Branch `agent-redesign`
Re-anchored: 2026-07-27 (rubric change only; no code changed between those dates)

> **Scope and boundary.** This audits the runtime against
> `docs/research/ai-agent-reference-architecture-opus-5-2026-07-26.md` **§14**
> ("RA §14") — 54 attributes. Evidence for any claim is
> `ai-agent-evidence-base-opus-5-2026-07-26.md`, cited `[EB §n]`.
>
> This document reports **status only**. Scope and targets are
> `docs/requirements/agent-attributes.md`; sequencing is `roadmap.md`.
>
> It is deliberately **complementary** to `docs/reviews/agent-quality-review.md`,
> which remains the **review-of-record for agent-runtime quality**. Where that
> review already owns a finding, this document **points** to it and does not
> restate or re-litigate it (§2). New findings are §3.
>
> **Rubric change — read before comparing to an earlier copy.** This audit
> originally used `ai-agent-implementation-attributes-opus-5-2026-07-25.md`
> (49 attributes), now superseded and moved to `docs/archive/`. That document
> contributed no citations to the evidence base and is no longer a valid anchor.
> RA §14 adds five attributes and **renumbers the C series**:
>
> | Old ID | Old meaning | Now |
> |---|---|---|
> | C3 | Compaction | **C4** (structured compaction) |
> | C4 | Stable cacheable prefix | **C5** |
> | C5 | Just-in-time retrieval | **C6** |
> | C6 | Curated, revisable tool exposure | **C7** |
>
> New attributes: **C3** tool-result clearing · **C8** hybrid retrieval ·
> **E7** side-effect ledger · **G6** warm infrastructure · **I5** containment
> over prompting. All IDs below are RA §14 IDs. Findings N1–N12 are unchanged in
> substance; only their attribute references were remapped. The five new
> attributes are assessed in §3a.

---

## 1. Verdict

The project is **strong exactly where most agent projects are weak**, and weak
in areas that are cheap to fix but currently absent entirely.

Its evaluation rig (A1–A3) and tool layer (B1–B4) are better than typical
production agents. Its reliability layer (E1–E3, E5) does not exist at all —
there is not a single retry, timeout, or backoff in the AI path. And it carries
a substantial layer of per-question Python (H2) that inflates eval scores
without improving the agent (A4).

The already-known structural issue — an acyclic graph whose decisive choices
happen before the only loop — is owned by the review-of-record and tracked as
AR-2…AR-5. This audit does not re-file it.

**Category scores:**

| Category | Score | Comment |
|---|---|---|
| A. Evaluation | ●●●○○ | Oracle + trajectory assertions are excellent; A3, A4, A5 absent |
| B. Tools | ●●●●○ | Structured, bounded, errors-as-data, validated |
| C. Context | ●●○○○ | History budgeted rigorously; in-loop growth unbounded; no clearing (C3) |
| D. Control flow | ●●○○○ | Known; owned by review-of-record, tracked AR-2…AR-5 |
| E. Reliability | ●○○○○ | **Nothing.** No retry, no timeout, no cancellation |
| F. Observability | ●●●○○ | Good per-stage attribution; no IDs, no persistence |
| G. Cost | ●●●○○ | Caching landed; no enforcement, no result cache, no parallelism |
| H. Discipline | ●●○○○ | Per-question branches are the dominant issue |
| I. Safety | ●●●●● | Read-only tools over trusted CSVs — correctly minimal; I5 satisfied by construction |

Two scores moved on re-anchoring, both because the rubric grew rather than
because code changed. **A** dropped: A3 (CI regression gates) was not separately
assessed originally and is absent — there is no `.github/workflows`, and the
replay suite runs only by hand via `run-case-replay.sh`. **C** dropped: the new
C3 (tool-result clearing) is absent, and RA §13 ranks it *ahead* of compaction
as the primary context mechanism `[EB §2.2]`.

---

## 2. Already owned — not re-filed here

These are real, and deliberately **not** findings of this audit. Canonical owner
in each case is `docs/reviews/agent-quality-review.md` (findings F1–F7) with
forward work in `roadmap.md`.

| Rubric | Issue | Owner |
|---|---|---|
| D1, D2 | Graph is a strict DAG; loop does not own the decisions | review-of-record F1 → AR-3/AR-5 |
| C7, D2 | `_select_tool_names` is a pre-loop gate, not a revisable prior | F2 → **AR-3** |
| D2 | `out_of_scope` refusal fires before evidence gathering | F3 → **AR-2** |
| H2 (partial) | Phrase-matched `follow_up` special-casing | F4/F5 → **AR-4** |
| — | Graph recompiled per request | F7 → **AR-5** |

Reading note: AR-2 and AR-3 together resolve most of category D. An audit of
this codebase *after* AR-2…AR-5 land would score D differently, and this
document should not be read as arguing against that sequence.

---

## 3. New findings

Ordered by severity. None of these appear in the review-of-record or `roadmap.md`.

### N1 — No resilience on model calls (E1, E2, E3) · **High**

`grep -n "retry\|backoff\|timeout\|max_retries" app/ai/*.py app/pipeline.py`
returns **nothing**. Both model invocations are bare:

- `agent_loop.py:94` — `bound_model.invoke(messages)`
- `intent_service.py:81` / `:97` — `model.invoke(...)`

A transient 429 or 503 from any provider aborts the entire turn. The exception
propagates to the generic handler at `server.py:247` and surfaces as an opaque
failure. There is no timeout either, so a hung provider connection hangs the
request indefinitely.

This is the cheapest high-value gap in the codebase: bounded retry with
exponential backoff and jitter, retryable-vs-terminal classification, and
per-call timeouts. It is independent of the AR track and could land at any time.

### N2 — Context budget is not enforced where growth actually happens (C1, C2) · **High**

`context_budget.py` enforces a careful three-tier budget on conversation history
(40 messages / 16 000 chars / 4 000 chars per message). The loop's own message
list has **no equivalent**: `agent_loop.py:143` appends a full
`json.dumps(result)` per tool call, across up to 6 iterations × N calls, with no
cap on serialized size and no cumulative ceiling.

Per-tool `clamp_limit(default=5, maximum=20)` (`tools/common.py`) mitigates this
substantially and is why it has not yet bitten. But it is opt-in per tool and
bounds *rows*, not bytes, and nothing bounds the accumulated list. The rigor
applied to inputs should apply to the thing that grows.

### N3 — Per-question Python substitutes for agent capability (H2, A4) · **High**

Distinct from AR-4, which covers `follow_up` phrase-matching only. Three
mechanisms in `pipeline.py` encode individual question shapes in code:

| Mechanism | Location | Behavior |
|---|---|---|
| `_maybe_override_weather_answer` | `pipeline.py:760` | **Discards the model's answer** and re-renders from `latest_reading` |
| `_maybe_override_inverter_count_answer` | `pipeline.py:857` | Replaces answer for `"how many inverters does … have?"` |
| `_build_question_guidance` | `pipeline.py:631` | Injects exact tool arguments for named questions |
| `_normalize_tool_args_for_question` | `pipeline.py:698` | Patches tool args by substring-matching the question |

`_build_question_guidance` for `performance_ratio` specifies literal argument
values (`aggregate_by="plant", sort_order="asc", window="last_week"`) and which
result element to read. That is the agent's job encoded as a lookup table.

The structural test from H2 — *when a new question shape fails, does fixing it
require new Python?* — currently answers **yes**.

The compounding problem is A4: these overrides raise Gate scores without raising
capability, so **the eval currently overstates the agent**. Recommended
measurement, independent of any refactor: run the replay suite with the override
layer disabled and record both numbers. The delta is the size of the debt.

To be fair to the code: these are honest, well-contained, non-fabricating
stopgaps — every value they emit comes from a tool result already in
`tool_calls`. The concern is that they are untracked debt, not that they were
wrong to write.

### N4 — Reconciliation verdict is not sound (H4) · **Medium-high, correctness**

`_extract_numbers` (`agent_graph.py:517`) harvests **every** number recursively
from tool result dicts — metrics, counts, IDs, numeric-looking strings — into
one flat bag. `_classify_verdict` (`agent_graph.py:555`) then decides
`correct` / `wrong` / `incomplete` by set subset and disjointness over that bag.

Consequences:
- `correct` can be produced by coincidental overlap of semantically unrelated
  numbers (a matched-count of 3 in both answers).
- `wrong` can be produced by an incidental change (a row count moving) while
  the disputed claim is unchanged.

The verdict is user-visible on `dispute_correction` turns, which is precisely
where correctness matters most. It should compare **typed, field-addressed
claims**, not an untyped numeric bag. Note the entity-ID path is sound — it is
the numeric path that is not.

### N5 — No parallel tool execution (G5) · **Medium**

`agent_loop.py:108` iterates `tool_calls` sequentially. No `asyncio`,
`ThreadPoolExecutor`, or `concurrent` anywhere in `app/`. When a model emits
independent calls in one step — the `alerts` + `inverters` pattern that
`_build_question_guidance` explicitly instructs it to produce — they serialize.
Tools are pure reads over in-memory pandas, so this is safe to parallelize.
Wall-clock win, no token cost.

### N6 — No tool result cache (G4) · **Medium**

Not present anywhere in `app/`. Worth flagging specifically because
`docs/design/architecture.md` lists `ai/tool_result_cache.py` in its "modules to
carry over" table — it was never carried over. Either implement it or correct
the table; right now the design doc asserts a component that does not exist.

### N7 — No cancellation (E5) · **Medium**

`/api/chat/stream` (`server.py:590`) streams, but nothing aborts an in-flight
loop on client disconnect. An abandoned request continues consuming provider
tokens through all remaining iterations.

### N8 — Intent uses prose-parsing instead of structured output (H3) · **Medium**

`intent_service.py:106` strips code fences with regex, finds a JSON object with
`re.search(r"\{.*\}", ...)`, parses, validates, and on failure spends **a full
extra round-trip** on repair (`:88`). Every provider in the registry supports
structured outputs or schema-constrained tool calls. This is paid cost and
latency for a problem the provider solves natively.

### N9 — Cost is accounted but never enforced (G2) · **Low-medium**

`UsageSnapshot` / `TelemetrySummary` measure tokens, cache reads/writes, and
hit rate accurately. Nothing consumes them as a **limit** — no per-turn or
per-session ceiling, no behavior on breach. `MAX_TOOL_ITERATIONS = 6` is the
only real bound, and it is a proxy for cost, not a measure of it.

### N10 — No correlation IDs or persisted traces (F1, F2) · **Low-medium**

`TraceEvent` carries `kind`, `timestamp`, `iteration`, `tool_name`, `latency_ms`
— but no turn, session, or trace ID, and events live only for the request.
Offline aggregate failure analysis is not possible. No OpenTelemetry (F6).

### N11 — `TurnKind` declared twice (H1) · **Low**

Independent duplicate `Literal` definitions at `agent_graph.py:10` and
`turn_router.py:15`. No import relationship; nothing prevents drift. Note AR-4
will touch `turn_router.py` — worth collapsing then rather than as its own slice.

### N12 — `_invoke_agent_loop_compat` reflects on every turn (H1) · **Low**

`pipeline.py:509` calls `inspect.signature(run_agent_loop)` per request to
filter kwargs against whatever loop implementation is installed. Runtime
reflection to tolerate multiple versions of first-party code is a smell; if it
exists only for the replay harness, the harness should adapt instead.

---

## 3a. The five attributes new in RA §14

Assessed at the same commit. Only C3 produces a finding of consequence.

### N13 — No tool-result clearing (C3) · **High**

The single most load-bearing addition in the new rubric, and absent. Nothing in
`app/ai/` drops or replaces stale tool output once it has entered the loop's
message list — the only `.clear()` in the AI path is `evict_model_cache`
(`provider_registry.py:37`), which is unrelated.

This matters more than its novelty suggests. Dropping stale tool output measured
both **cheaper and better** than retaining full context `[EB §2.2]`, and RA §13
resolves a source disagreement in its favor, ranking clearing *ahead* of
compaction as the primary mechanism. Stale context is not neutral ballast.

Closely related to N2 but not the same: N2 asks for a **ceiling** on the
accumulating list; N13 asks that superseded entries be **removed** below that
ceiling. Doing only N2 caps the damage; doing N13 avoids it. They should land
together, and after AR-3 — which widens tool exposure mid-loop and therefore
increases exactly what needs clearing.

### The other four

| Attribute | State | Assessment |
|---|---|---|
| **C8** hybrid retrieval | ●●○○○ | No retrieval layer exists — tools are structured queries over nine in-memory CSVs. Correct for the product; scoped as Learning-class in `agent-attributes.md`. Not a finding. |
| **E7** side-effect ledger | ●○○○○ | No side effects exist to record. Unimplementable without a fixture. Not a finding. |
| **G6** warm infrastructure | ●●●●○ | Largely satisfied already: `PandasDataSource._load` eager-loads and validates every CSV at construction (`pandas_source.py:45`), and `provider_registry` caches model handles. No cold-start path in the request. |
| **I5** containment over prompting | ●●●●● | Satisfied **by construction**. The read-only tool surface is containment in exactly the sense `[EB §10.2]` recommends — capability limited rather than behavior requested. Worth stating explicitly so a later slice does not trade it away for flexibility without noticing. |

---

## 4. What is genuinely strong

Not padding — these are the attributes most agent projects lack, and they should
survive any refactor.

**A1/A2 — the evaluation rig is the best thing in the codebase.**
`scripts/golden_answers.py` computes expected answers **directly from the CSVs,
independent of the app's tools**, which is a true oracle rather than a
self-consistency check. `case_replay.py` then asserts on the *trajectory*:
required tool arguments (`RequiredToolArgs`), required result field paths
(`RequiredToolResultField`), and tool-call subsequences — plus multi-turn
transcript fixtures. Most teams never build this.

**B1–B4 — the tool layer is disciplined.** Structured dicts only, never prose;
`clamp_limit(default=5, maximum=20)`; `ToolRegistry.invoke` catches every
exception and returns errors as data; argument validation against the handler's
real Python signature with actionable messages for unknown args.

**C5/G1 — prompt caching is correctly applied.** `system_blocks_with_cache` plus
a breakpoint on the final tool schema, with registry-ordered tool lists keeping
the prefix stable. ADR 0005's choice to keep the static schema card preserves
that prefix — the right call for cache economics.

**F3/F4 — per-stage attribution is above average.** Usage split by
intent vs synthesis, `tool_iteration_count`, `turn_latency_ms`, and cache
read/creation with a derived hit rate, including the Anthropic TTL-split form.

**E4 — the degradation ladder is deliberate.** Intent repair → gating fallback →
tool errors as data → iteration-limit reply → scoped out-of-scope replies. The
gap is that it covers *logic* failures thoroughly and *infrastructure* failures
not at all (N1).

**I — safety is correctly proportional.** Read-only tools over trusted local
CSVs. Approval gates, sandboxing, and injection defenses would be
over-engineering. Not a gap.

---

## 5. Proposed correction to the review-of-record

`docs/reviews/agent-quality-review.md` § "Graded status matrix" has two rows
that no longer match the code as of `d80b1cf`:

| Row | States | Actual |
|---|---|---|
| Prompt caching (`cache_control`) | "Not implemented" | **Implemented** — AQ-2, commit `2a28fca` |
| Iteration/latency telemetry | "Missing" | **Implemented** — AQ-3, commit `76eecb9` |

A third row, "`langgraph` in `requirements.txt` — Missing", is also resolved:
`langgraph` is present in `requirements.txt`.

**Applied 2026-07-27.** All three rows are corrected in
`docs/reviews/agent-quality-review.md`, which carries a dated note pointing back
here. This section is retained as the provenance of that edit.

---

## 6. Triage — effort, risk, value

Input to `roadmap.md`, which owns sequencing. **Effort** is implementation size
(S ≤ half a session · M ≈ one session · L > one session). **Risk** is the chance
of breaking working behavior. **Value** is production value in this project —
learning value is scored separately in `docs/requirements/agent-attributes.md`,
because the two diverge sharply here.

| # | Finding | Attr | Effort | Risk | Value | Note |
|---|---|---|---|---|---|---|
| N1 | No retry / timeout / backoff | E1–E3 | S | **Low** | **High** | Best ratio in the codebase. Additive, no behavior change on the happy path. |
| N5 | No parallel tool execution | G5 | S | Low | Med | Pure reads over in-memory pandas. Wall-clock only, no token cost. |
| N10 | No correlation IDs / traces | F1, F2 | S | Low | High | Additive. Unlocks offline failure analysis, which every later slice benefits from. |
| N11 | `TurnKind` declared twice | H1 | S | Low | Low | Fold into AR-4, which already touches `turn_router.py`. |
| N8 | Prose-parsing for intent | H3 | M | Low | High | Removes a full repair round-trip. Providers solve this natively. |
| N6 | No tool result cache | G4 | M | Low | Med | Either build it or correct `docs/design/architecture.md`, which asserts it exists. |
| N9 | Cost measured, never enforced | G2 | M | Low | Med | Telemetry is already accurate; only the ceiling is missing. |
| N7 | No cancellation | E5 | M | Med | Med | Touches the streaming path. |
| N2 | In-loop context budget | C1, C2 | M | Med | High | **More urgent after AR-3.** |
| N13 | No tool-result clearing | C3 | M | Med | High | Land with N2, after AR-3. |
| N4 | Reconciliation verdict unsound | H4, D3 | M | **Med-high** | High | User-visible on disputes. Needs typed field-addressed claims, not a numeric bag. |
| N12 | Runtime reflection per turn | H1 | S | Med | Low | Risk is in the replay harness coupling, not the code. |
| N3 | Per-question Python | H2, A4 | **L** | **High** | **High** | Gated by its own measurement step — see below. |

**Two entries are not findings but enabling work**, and both belong in the plan:

| Item | Attr | Effort | Risk | Value | Note |
|---|---|---|---|---|---|
| A3 · CI regression gates | A3 | S | Low | High | No `.github/workflows` today. Cheap, and makes every other slice's regression claim automatic rather than manual. |
| S-class fixture tool | B6, E6, E7, I3, I4 | M | Med | — | Enabling slice for six Synthetic attributes. Gated off by default, excluded from Gate scoring. Zero production value by design. |

### The ordering constraint that dominates

**N3's measurement step gates the honesty of every number above.** Running the
replay suite with the override layer disabled establishes the true capability
baseline. Until that exists, A4 is violated: the eval overstates the agent, so
any "value" claimed for a slice is measured against an inflated baseline, and an
AR slice that genuinely improves the agent may show no movement because the
override layer was already supplying the score.

It is effort **S** — a flag and two recorded numbers — and it is separable from
the **L**-effort removal of the overrides themselves. Do the measurement first;
schedule the removal on its own.

---

## 7. Sequencing observation

Not a plan — `roadmap.md` owns sequencing. One observation on ordering:

**N1 (retries/timeouts) and N5 (parallel tools) are independent of the AR
track** and touch only `agent_loop.py`. They could land at any point without
interacting with AR-2…AR-5.

**N2 (in-loop context budget) and N13 (tool-result clearing) become more urgent
after AR-3**, which widens tool exposure mid-loop and therefore increases both
the accumulated tool output and the amount of it that goes stale.

**N3's measurement step — running the replay suite with overrides disabled — is
worth doing before AR-2/AR-3**, because it establishes the true capability
baseline those slices will be judged against. Without it, an AR slice that
genuinely improves the agent may show no eval movement, because the override
layer was already supplying the score.
