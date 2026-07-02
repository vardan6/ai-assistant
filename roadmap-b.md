# Roadmap

> Thin vertical slices, each independently verifiable. **Forward-looking only.**
> Completed slices are logged in `progress.md`. Requirements live in
> `docs/requirements/`, design in `docs/design/`, decisions in `docs/adr/`.
> Tags: **AFK** = can proceed autonomously · **HITL** = needs a human decision/review.

## Where we are

Waves 1–3 (data-tool fixes, conversation-state plumbing, turn-router +
reconciliation nodes, multi-turn harness, runtime behind the API) and the WAVE 4
G2-FIX behavior fixes are done — history in `progress.md`. A LangGraph
`StateGraph` runtime is wired, but graded as a **non-decision-owning wrapper**,
not yet the session-first agent loop (`docs/reviews/agent-quality-review.md`).

Remaining forward work: run the forward slices as **three parallel threads**
(A/B/C) that own disjoint files, converging on the integration gates.

## Shared prerequisite gate (blocks thread landing)

> R1 verification stays ahead of R2/R3 tuning (`docs/requirements/agent-quality.md`).
> `G2-FIX-11` is clean. Threads may be *developed* on separate branches in
> parallel, but honour the entry gates below before landing decision-graph
> changes to `main`. Triage source:
> `docs/archive/gate2-failure-triage-2026-07-01.md`.

- [x] **G2-FIX-11 · Fresh Gate 2 verification** (HITL). Re-run Gate 2 on a clean
      port; confirm real-fix cases pass and only accepted matcher cases remain.

## Parallel threads

> Three threads sized for concurrent work in separate sessions/branches. Each
> lists **Owns** (files it edits), **Entry gate**, **Order** (internal), and
> **Coordination** (cross-thread seams to reconcile before landing). File
> ownership is disjoint except the two coordination seams called out in
> Threads B and C. Requirements: `docs/requirements/agent-quality.md`
> (R1 quality > R2 token > R3 runtime).

### Thread A — Agent-runtime rework (R1, critical path)

> Owns: `app/ai/agent_graph.py`, `app/ai/turn_router.py`, `app/ai/intent_prompt.py`,
> `app/ai/intent_schema.py`, and the decision paths of `app/ai/agent_loop.py`.
> Order: AR-1 → AR-2 → AR-3 → AR-4 → AR-5 (internally sequential — each builds on
> the interpretation node). Design target:
> `docs/design/full-react-agent-redesign.md` → "Reconciled control-flow target
> (2026-07-02)"; findings F1–F7 in `docs/reviews/agent-quality-review.md`.
>
> **Entry gate (HITL):** Gate 2 (`G2-FIX-11`) clean, then run `/review-triage` on
> `docs/reviews/agent-quality-review.md` and accept F1–F5 as `must_fix_now`. This
> is R1 architecture work, so it sequences ahead of Threads B/C's R2/R3 tuning but
> after the shared gate. Resolved under the quality-first rule: the review's
> decision-ownership bar outranks the older "Implemented" scoring of
> `compile_runtime_graph`.

- [ ] **AR-1 · `interpret_session_turn` node, minimal end-to-end** (AFK after
      gate). Add one session-aware node all non-command/non-smalltalk turns pass
      through *before* tool selection or refusal; it emits
      `{turn_action, resolved_request, intent, tool_policy}` and initially
      delegates to the existing `run_agent_loop`. Verify: the G6 follow-ups
      ("yes please", "night = 19:00–06:00 …") continue the original intent
      instead of resetting to a menu/generic refusal.
- [ ] **AR-2 · Refusal after interpretation** (AFK). Move the `out_of_scope`
      branch to a final outcome *after* `interpret_session_turn`, never a
      pre-loop classifier shortcut. Verify: an in-scope conversational turn is
      never answered with a standalone dataset refusal.
- [ ] **AR-3 · Revisable tool policy (widen mid-loop)** (AFK). Let the graph
      widen the bound tool subset when the gated selection proves insufficient
      (still never binding all tables). Verify: a turn the classifier under-gated
      still reaches the right tool without a fresh user prompt.
- [ ] **AR-4 · Retire phrase-matched `follow_up` special-casing** (AFK). Fold the
      hand-coded follow-up resolution behind the interpretation node; keep only a
      deterministic ambiguity safety net. Verify with adversarial multi-turn
      tests: equivalent second-turn phrasings produce the same graph decision
      without phrase-specific patches (F6).
- [ ] **AR-5 · Compile the graph once as a stable runtime** (AFK; low priority) →
      F7. Stop recompiling `compile_runtime_graph` per request once the graph
      owns the loop; a stable component makes later checkpointer/state work
      tractable.

### Thread B — Token & telemetry (R2/R3)

> Owns: `requirements.txt`, `app/ai/provider_registry.py`, `app/ai/usage_telemetry.py`,
> and the telemetry hooks (not decision paths) of `app/ai/agent_loop.py`.
> Order: AQ-1 (anytime) → AQ-2 → AQ-3. Does not touch the decision graph.
>
> **Entry gate:** AQ-1 is trivial and can land anytime (unblocks reproducibility).
> AQ-2/AQ-3 wait until Gate 2 (`G2-FIX-11`) is clean per the R1-first rule.
>
> **Coordination:** AQ-2's `cache_control` boundary wraps the *system prompt +
> schema card + tool defs* prefix as one cached block — reconcile that boundary
> with Thread C's AQ-4 (which makes the card progressive and changes cache
> invalidation) before either lands. AQ-3's telemetry counters live in
> `agent_loop.py` alongside Thread A's edits — keep additive, land after or rebase.

- [x] **AQ-1 · Declare `langgraph` dependency** (AFK). Add `langgraph` to
      `requirements.txt`; it is imported (`app/ai/agent_graph.py`) and installed
      but undeclared. Verify a clean-venv install imports `compile_runtime_graph`.
- [ ] **AQ-2 · Prompt caching for the cached prefix** (AFK) → closes the ADR 0002
      token assumption. Add Anthropic `cache_control` over system prompt + schema
      card + tool defs so they are not recomputed per iteration/turn; surface
      cache hit-rate in `usage_telemetry`. (Use `/claude-api`.)
- [ ] **AQ-3 · Iteration + latency telemetry** (AFK). Add per-turn
      tool-iteration count and latency to `usage_telemetry` as the R3 measured
      target; no budget enforcement yet, just observability.

### Thread C — Schema-card evolution (R2)

> Owns: `app/schema_card.py` and the card-assembly path of `app/pipeline.py`;
> new ADR in `docs/adr/`.
> Order: ADR decision (HITL) → AQ-4 implementation.
>
> **Entry gate (HITL):** AQ-4 **revisits ADR 0003's front-load stance** and needs
> a decision (likely a new ADR) before implementation — the open question below.
> Design/ADR work can begin during the shared gate; implementation waits until
> Gate 2 is clean.
>
> **Coordination:** AQ-4 restructures the cached prefix, so it must sequence
> *after* Thread B's AQ-2 and reconcile the `cache_control` boundary — a
> progressive card breaks a statically cached prefix.

- [ ] **AQ-4 · Progressive schema-card loading** (HITL) → core R2 ask. Design and
      slice lazy, per-table schema-card sections keyed to selected tools
      (summary-first, drill-down on demand). **Revisits ADR 0003's front-load
      stance** — needs a decision (likely a new ADR) before implementation; see
      open question below.

> **Open question (AQ-4):** does progressive schema-card loading improve R2
> without costing R1 answer quality or R3 iteration count? ADR 0003 deliberately
> front-loaded the card to cut discovery loops; decide before building AQ-4.

## Convergence — Integration Gates (after threads merge)

> Final verification once threads A/B/C land. Completed work — G-INT1, all ten
> G2-FIX behavior slices, and the RT1/RT2 merged-branch retest — is logged in
> `progress.md`.

- [ ] **G-INT2 · Gate 1 + Gate 2 CLI replay** (HITL). `./run-case-replay.sh
      --gate gate1`, then `--gate gate2` (or `gate2a`/`gate2b` in parallel): 36
      single-turn cases + 4 multi-turn transcripts (`gate2b` carries the transcripts).
- [ ] **G-INT3 · Manual chat smoke** (HITL). In the Web UI, replay the D3 sequence
      and verify the activity panel shows resolved question, evidence/tool calls, and
      reconciliation outcome.

## Deferred / later

- Additional smalltalk patterns; SQLite/DuckDB `DataSource` impl; cohere provider.
