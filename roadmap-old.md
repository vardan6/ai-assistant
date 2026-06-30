# Roadmap — archived (completed work)

> Temporary archive of completed roadmap sections, moved out of `roadmap.md` on
> 2026-06-30 to keep the live roadmap forward-looking. Nothing here is lost — it is
> the verbatim record of finished slices. Authoritative substance for these items
> lives in the code, `docs/design/`, `docs/adr/`, and `progress.md`. The live
> forward plan (WAVE 4 — LangGraph + review-2026-06-30 follow-ups) is in
> `roadmap.md`.

## 1. Finalize the test plan (the contract)

> The **cases** are fully defined — `docs/test-plan.md` §3 is a complete
> per-surface catalog (D/P/I/G/W/AL/M/AN/X + probe cases §3.10 + trap index §3.11),
> with the spec traceability matrix in §2. What remains is making the plan
> *runnable*: pin the expected values, then build the harness. This is the
> measuring stick everything below is verified against, so it goes first. Coverage
> uses the status vocabulary in `docs/requirements/pipeline.md` → "Coverage
> principle" (spec is a floor, not a ceiling; broader mechanisms count as *met by
> superset*).

- [x] **Pin oracle values** (AFK). Extend `scripts/golden_answers.py` to pin every
      `[oracle⁺]` value in `docs/test-plan.md` §3 (A/B/C + X numerics) so catalog
      rows can flip from 🟡 to ✅/➕. We do not invent numbers.
- [x] **Test harness + pass/fail** (AFK). Add fixtures and a harness that replays
      each case through CLI mode, capturing intent + tool chain + answer and
      diffing against the oracle; include the architecture-level rubric assertions
      (rows 1–2: stage separation/composability, per-tool isolation) beyond the
      §3.10 probe cases. Closes out `docs/test-plan.md` §3.12; reconcile the stale
      §1.10 TODO list into §3.12 as part of this.

## 2. Implement & fix

> Two tracks, honest about which is which.
> **New builds** are already decided (ADR 0003, design `architecture.md` →
> "Tool redesign direction" / "Relationship awareness") — they are *implement →
> verify against the oracle*, not gated by triage.
> **Existing-tool fixes** are *baseline run → triage → fix only what's flagged* —
> the tools already work end-to-end, so we measure before rewriting. Spec is a
> floor, not a mandate to rewrite working tools. Build against the profiler tables
> (`docs/dataset-analysis.md`), not assumptions.

### 2a. New builds (implement, then verify)

- [x] **Static schema card** (AFK — ADR 0003). Flatten the FK tree, shared name→id
      resolver, and measure-semantics / vocabulary maps into a static schema card
      in the system prompt, generated from / pointing at the `dataset-analysis.md`
      tables (never hand-copied). Replaces the rejected runtime-graph engine; the
      LLM plans chains in the existing loop, parallelism implicit in FK depth.
- [x] **Shared entity resolver** (AFK). One plant/inverter name→id resolver
      (`region` is a compass label — resolve on `name`/`location`), replacing the
      duplicated match in `tools/common.filter_plant` and `tools/plants._filter_by_plant`.
- [x] **reference_now anchor toggle** (HITL — needs design). Wire the anchor as
      optional/default-on through every time-related query, falling back to wall
      clock when disabled. Currently only documented, not in code.

### 2b. Baseline run → triage (the gate for existing-tool fixes)

- [x] **CLI run + triage** (HITL). Historical 15-case replay subset run on
      2026-06-30 (the then-implemented harness set, not the final initial-task
      15-question gate). Results: 12 works · 1 polish · 2 rework · 0 redesign.
      Flagged cases were `D3` (rework), `G4` (polish), and `X4` (rework); their
      implementation/follow-up now lives in Lane A and Wave 3 integration below.

### 2c. Previously flagged cases to re-verify after redesign

> This section is intentionally collapsed to avoid duplicate roadmap state.
> `D3`, `X4`, and `G4` were implemented in **Lane A** (`A1`/`A2`/`A3`) and
> replayed in the historical subset via `A4`. The remaining live verification
> after the runtime redesign is tracked only in **Wave 3 Integration**:
> `I3` for Gate 1, `I4` for the prior-answer transcript issue, and `I4b` for
> Gate 2. Reopen direct tool fixes only if those later live replays fail.

## 3. Full ReAct agent redesign — completed lanes

> Direction **accepted** 2026-06-30 (ADR 0004): session-aware ReAct with a
> committed LangGraph target runtime. See `docs/design/full-react-agent-redesign.md`.
> The completed Wave 1/1.5/2 lanes and the I1/I2 integration steps are archived
> here; the remaining forward work is in `roadmap.md` (WAVE 4).

### Parallelization map (historical — Waves 1–3)

```text
WAVE 1 (3 parallel sessions — no shared files)
  Lane A  Data-tool fixes ............ owns app/tools/*, scripts/golden_answers.py
  Lane B  Conversation-state plumbing  owns app/ai/session_store.py, app/ai/context_budget.py(new)
  Lane D  Multi-turn test harness ..... owns app/case_replay.py, tests/fixtures/*, docs/test-plan.md

WAVE 1.5 (gate, merged before Lane C)
  Lane C-contract  Freeze the AgentContext interface ... owns docs/design/* (interface block)

WAVE 2 (after Lane B + C-contract merge)
  Lane C  Agent runtime / graph + nodes  owns app/pipeline.py, app/ai/agent_graph.py(new),
                                              app/ai/turn_router.py(new)

WAVE 3 (after all lanes merge — single session, sequential)
  Integration + test gates ... owns app/server.py wiring + runs all suites
```

Rule for the agents (still applies to WAVE 4): **a lane/thread may be picked up by
any session and run to completion independently as long as its `needs:` are
merged.** Do not edit files outside your lane's `owns:` list; if you need a change
there, leave a note for the Integration step instead of editing across lanes.

### Lane A — Data-tool fixes

- [x] **A1 · D3 combined type+cause filter** (AFK). Fix so `type=hotspot AND
      cause=soiling` returns the 2 matching inverters, not plant-level totals
      (9, 7, 55). Assert D3: 2 inverters; numbers 2.0, 7.0, 55.0.
- [x] **A2 · X4 plant-level PR aggregation** (AFK). Fix plant-level worst-PR
      ranking. Assert X4: "Rajasthan", ≈ 0.9077.
- [x] **A3 · G4 inverter ID display** (AFK, polish). Map numeric inverter IDs to
      `inv_<plant>_<seq>`. Assert G4: text "inv_4137001_04". Pin the canonical
      casing here so multi-turn golden answers (Lane D) match.
- [x] **A4 · Historical replay-subset re-run** (AFK). Re-run the historical
      15-case replay subset; confirm all pass. This closed the old pre-gate
      roadmap §2c check, but it is not the same as the later Gate 1 initial-task
      15-question rerun.

### Lane B — Conversation-state plumbing

- [x] **B1 · Bounded history loader** (AFK). Add a recency-window loader: count
      cap + total budget + per-message truncation marker, newest-first, always
      keep the latest message. Port rover's three-tier shape
      (`AI_CONTEXT_MESSAGE_LIMIT=40`, `_HISTORY_CHAR_BUDGET=16000`,
      `_SINGLE_MESSAGE_CHAR_LIMIT=4000`) as named constants. Unit-test in
      isolation. See design → "Session context & evidence strategy".
- [x] **B2 · History projection (no raw rows)** (AFK). Expose a projection that
      returns only `{role, content}` per message for prompt re-feed; never the
      stored `metadata` payload. Guard-test that no raw tool JSON leaks.
- [x] **B3 · Full evidence persistence + fingerprint** (AFK). Keep storing full
      tool evidence on assistant `metadata` (cards/replay already use it) and add
      a dataset/config fingerprint so reconciliation can detect stale evidence.

### Lane C — Agent runtime / graph

- [x] **C0 · Freeze AgentContext interface** (HITL gate · WAVE 1.5). Write the
      `load_session_context() -> AgentContext` signature + `turn_kind` enum +
      `prior_answer_verdict` schema into the design doc so Lanes B and C build to
      the same contract. Small, must merge before C1.
- [x] **C1 · Turn router + single classification call** (AFK). One call returns
      `{turn_kind, intent}`. Route smalltalk/command/meta to tool-free branches;
      route out_of_scope **inside** the data branch (not as a pre-classify
      short-circuit — that is the bug that swallowed "your answer was wrong").
- [x] **C2 · Follow-up resolver node** (AFK). Produce a standalone
      `resolved_question` from prior turns; expose it in trace metadata.
- [x] **C3 · Dispute/reconciliation node** (AFK · needs A merged). Detect
      correction turns, re-run focused tools fresh, emit structured
      `prior_answer_verdict` (correct/wrong/incomplete) + referenced claim.
- [x] **C4 · LangGraph skeleton** (AFK). Assemble C1–C3 + B's loader as graph
      nodes behind the existing chat API; preserve the `TraceEvent`
      streaming contract; `SessionStore` stays canonical.
      *Note (2026-06-30 review): this delivered a graph-state dataclass +
      `graph_nodes` plan metadata, NOT a real LangGraph `StateGraph` runtime. The
      actual LangGraph build is forward work — see `roadmap.md` WAVE 4 T1-LG.*

### Lane D — Multi-turn test harness

- [x] **D1 · Multi-turn transcript format + fixtures** (AFK). Define the
      multi-turn replay format and author the D3 sequence + follow-up, dispute,
      prior-answer, and context-resolved-ambiguity cases.
- [x] **D2 · Verdict-based assertions** (AFK · needs C0 schema, A3 casing).
      Assert on structured `prior_answer_verdict` + intent + tool chain +
      numerics — never on free-form reconciliation prose.

### Integration + gates (completed steps)

- [x] **I1 · Wire graph behind API** (AFK). Connect Lane C's runtime into
      `server.py`; keep API contracts and trace streaming stable.
- [x] **I2 · Unit + integration pass** (AFK). Full suite (tool, pipeline,
      server/session, CLI, case-replay). Fix or explicitly triage every
      regression.
