# Review — current implementation, roadmap, active context, docs

Review date: 2026-06-30
Independent re-validation: 2026-06-30 (second pass against the working tree)

> **Validation status:** All 10 findings were independently re-checked against the
> current code and confirmed accurate. Line references resolve, the cited bugs are
> real, and the recommendations are sound. The second pass adjusted two severities,
> added one finding (#11), and appended a concrete implementation plan. See
> **"Independent validation & final opinion"** at the end. Nothing from the original
> review was removed — annotations are additive.

Scope:

- Current working tree implementation and tests.
- `activeContext.md`, `roadmap.md`, `progress.md`.
- Updated docs under `README.md`, `docs/requirements/`, `docs/design/`,
  `docs/adr/`, `docs/test-plan.md`, and `docs/implementation-notes.md`.

Verification performed:

- `python -m compileall app scripts` using the checked local interpreter: pass.
- Temporary venv at `/tmp/aregi-review-venv`: installed `requirements.txt` +
  `pytest`, then ran `python -m pytest -q`: **81 passed, 1 warning**.
- `python -m app.case_replay --help` in the temporary venv: pass.
- `scripts/golden_answers.py` in the temporary venv: pass.

Local environment note:

- The checked `.venv` is not currently usable for runtime/test verification:
  `.venv/bin/python -m pytest` reports `No module named pytest`,
  `.venv/bin/python scripts/golden_answers.py` reports `No module named pandas`,
  and `.venv/bin/pip` reports `No module named pip`.

## Triage

Must fix now (re-validated → 3): #1, #2, #6

| # | Finding | Risk | Value | Effort | Priority | Reason |
|---|---------|------|-------|--------|----------|--------|
| 1 | Web UI ignores the configured gated default and sends `bind_all` | high | high | low | must_fix_now | Violates ADR 0002 / grading requirement that default submission path is gated |
| 2 | D5 weather answer still relies on prompt preference instead of deterministic latest-reading selection | high | high | med | must_fix_now | Active Gate 1 blocker; model can keep choosing summary averages |
| 3 | `MT-PRIOR-ANSWER` stop-reason contract is known to fail (`fast_path` vs `final_answer`) | med | high | low | should_fix_before_phase_complete | Blocks gate2b transcript replay after Gate 1 |
| 4 | D3 dispute fixture contradicts the design target, and verdict classification is string-overlap based | high | high | med | should_fix_before_phase_complete | Can mark a correct prior answer wrong; undermines reconciliation oracle |
| 5 | Silent-inverter case I4 is documented as code reconciliation but no tool computes the silent count | med | high | med | should_fix_before_phase_complete | Leaves aggregation to the LLM over records, contrary to aggregation-in-code requirement |
| 6 | Config import/UI response drops `use_reference_now_anchor`; frontend can display/persist the wrong anchor setting | **high** (re-validated, up from med) | high | low | **must_fix_now** | A later UI save persists `false`, flipping `effective_now` to wall-clock and breaking every dataset-anchored oracle answer — blast radius is the whole gate suite, not a checkbox |
| 7 | Replay R3 probe claims to assert output-to-arg chaining, but current harness mostly checks tool-name subsequences | med | med | med | should_fix_before_phase_complete | A replay pass can miss wrong resolver-to-child arguments |
| 8 | Roadmap/test-plan/README contain stale or contradictory state | low | med | low | backlog | Documentation drift will misroute the next agent/operator but is not a runtime bug |
| 9 | `requirements.txt` omits `pytest` even though README test instructions require it | low | med | low | backlog | Fresh install from README cannot run `python -m pytest -q` without an extra package |
| 10 | Durable docs contain stray `</content>` / `</invoke>` tags | low | low | low | backlog | Cosmetic but reduces trust in docs hygiene |
| 11 | Oracle checks rely on small-integer `required_numbers` and answer-text substrings; coincidental matches can pass a wrong answer (added in re-validation) | med | med | med | should_fix_before_phase_complete | Strengthens the same orchestration-proof gap as #5/#7 — assert on tool-result fields, not just rendered prose |

## Findings

### 1. Web UI defaults every chat request to `bind_all`

Evidence:

- `app/web/assets/app.js:30` initializes `state.gatingMode` to `"bind_all"`.
- `app/web/assets/app.js:785`, `app/web/assets/app.js:1520`,
  `app/web/assets/app.js:2308`, and `app/web/assets/app.js:2623` all force
  `"bind_all"` during startup, UI settings save, persisted UI snapshot, and config
  import.
- Chat requests send this value directly at `app/web/assets/app.js:1621-1626`.
- Backend/CLI defaults are `gated`, but the primary Web UI path is not.

Why it matters:

- ADR 0002 says `gated` is the submission/default path and `bind_all` is the
  optional max-accuracy path.
- The graded requirement explicitly says the orchestrator must not load all seven
  tables on every question. A default Web UI `bind_all` path creates a demo risk.

Recommendation:

- Initialize `state.gatingMode` from `state.ui.default_gating_mode`.
- Persist the real `state.gatingMode`, not a hard-coded value.
- After saving/importing UI config, set chat gating to the returned default unless
  there is an explicit per-request override control.
- Add a frontend or server API test proving the Web UI default request uses
  `gated`.

### 2. D5 latest-weather fix is still partial

Evidence:

- Active context explicitly says D5 is failing because answers use summary
  averages instead of `weather_readings.latest_reading`
  (`activeContext.md:8-14`, `activeContext.md:32-33`).
- The weather tool exposes both `latest_reading` and `summary`
  (`app/tools/weather_readings.py:99-117`).
- The pipeline prompt only asks the model to "prefer" latest readings
  (`app/pipeline.py:93-95`, `app/pipeline.py:530-533`).

Why it matters:

- The expected D5 oracle is snapshot values: 26.04, 46.24, 799.34.
- Leaving final selection to the model is exactly the source of the live drift.

Recommendation:

- Make the weather snapshot path deterministic. Options:
  - Add a `mode="snapshot"` / `snapshot_only=true` argument to
    `weather_readings`.
  - Split weather snapshot and weather summary into separate tools.
  - Post-process D5-style `today`/`now` weather answers from the tool result
    before final synthesis.
- Add a focused test that fails if the final answer contains same-day averages
  instead of `latest_reading`.

### 3. Prior-answer recall stop reason blocks gate2b

Evidence:

- Active context calls this out as the next blocker after D5
  (`activeContext.md:10`, `activeContext.md:18`).
- Roadmap I4 says the prior-answer recall branch should return `final_answer`
  instead of `fast_path` (`roadmap.md:195-199`).
- `ReplayTurnSpec.expected_stop_reason` defaults to `final_answer`
  (`app/case_replay.py:127-128`).
- The tool-free prior-answer branch returns `stop_reason="fast_path"`
  (`app/pipeline.py:274-293`).

Recommendation:

- Normalize `prior_answer_meta` to `final_answer`, or make the transcript fixture
  explicitly expect `fast_path` if that is the intended durable contract.
- Prefer `final_answer`: this path is a valid answer from session state, not a
  local smalltalk/empty fast path.

### 4. D3 dispute contract contradicts design and verdict logic is weak

Evidence:

- The design says the initial D3 global answer is **not wrong**; the later
  double-check answer was wrong (`docs/design/full-react-agent-redesign.md:105-115`).
- The fixture requires the structured verdict to contain `"wrong"`
  (`tests/fixtures/multi_turn/d3-dispute.json:24-26`).
- The current verdict status uses string containment between prior answer text
  and current evidence IDs/numbers (`app/ai/agent_graph.py:402-418`), not a real
  comparison of prior predicate vs fresh result.

Why it matters:

- This can train the harness to accept the wrong reconciliation outcome.
- The current heuristic can mark a correct prior answer wrong or incomplete just
  because wording omitted some IDs/numbers.

Recommendation:

- Decide the intended dispute fixture:
  - If the user only asks "that answer looks wrong" after the baseline D3 answer,
    expected status should be `correct` or `incomplete`, not `wrong`.
  - If the fixture intends to catch the later broad plant-health answer, include
    that intermediate wrong answer in the transcript.
- Replace string-overlap verdicting with structured comparison against the prior
  answer's stored tool call/result metadata when available, and a fresh re-run
  of the same predicate.

### 5. I4 silent-inverter coverage is not implemented as code aggregation

Evidence:

- Test plan I4 expects `inverters ⨝ generation last_seen vs anchor` and count 16
  (`docs/test-plan.md:263`).
- Dataset analysis says silent entities must be treated as offline/excluded from
  latest averages (`docs/dataset-analysis.md:418`).
- `inverters` returns status counts and 30 inverter records, but no
  `silent_count`, `silent_inverter_ids`, or anchor-aware stale-feed reducer
  (`app/tools/inverters.py:33-44`).
- Gate replay only requires answer text/number for I4 (`app/case_replay.py:294-300`),
  so a model could pass by inferring from records instead of a code aggregate.

Recommendation:

- Add a current-state/silent-feed reducer in code, either in `inverters` or a
  dedicated current-state tool.
- Return explicit `silent_count`, `silent_inverter_ids`, anchor timestamp, and
  threshold rule.
- Assert the tool result, not only final answer text.

### 6. Config import can lose the reference-now toggle in UI state

Evidence:

- `/api/settings/ui` returns `use_reference_now_anchor`
  (`app/server.py:295-318`).
- `/api/settings/config` import response omits it from `ui`
  (`app/server.py:523-526`).
- Frontend assigns `state.ui = response.ui || state.ui`
  (`app/web/assets/app.js:2618-2621`), then renders
  `Boolean(state.ui.use_reference_now_anchor)`
  (`app/web/assets/app.js:1359-1363`).

Why it matters:

- After config import, the checkbox can render false even when backend config is
  true. A later UI save can persist the wrong anchor setting.

Recommendation:

- Include `use_reference_now_anchor` in the config-import response `ui` payload.
- Add an endpoint test for config import preserving/rendering all UI fields.

### 7. Replay structure probes are weaker than the test plan says

Evidence:

- Test plan says R3-trace should assert the resolved id from step 1 appears as
  an arg in step 2 (`docs/test-plan.md:331-339`).
- `evaluate_payload()` currently checks required tool-name subsequences, bound
  tool subsequences, trace kind subsequences, final text, and final numbers
  (`app/case_replay.py:693-759`).
- It does not generally assert that a resolver output was used in a downstream
  tool call argument.

Recommendation:

- Extend `ReplaySpec` with argument assertions, e.g.
  `required_tool_args=[{"tool":"anomalies","args":{"plant":"4135001"}}]`.
- For D2/C3/AN6/D5, assert the resolved plant id/name is used downstream.
- For D5, assert `weather_readings` is called with `window="today"` and Gujarat.

### 8. Documentation state is stale in several places

Examples:

- `README.md:10-16` still describes "Phase 0" and "One plants tool", while the
  current implementation has seven table tools, derived tools, sessions, Web UI,
  settings, and replay gates.
- `docs/test-plan.md:446-450` says Gate 1 still needs to be represented, but
  `app/case_replay.py:15-31` already defines `GATE1_CASE_IDS`.
- `README.md:181-186` describes Gate 2 as only 36 canonical behavioural cases;
  `docs/test-plan.md:422-436` and `app/case_replay.py:77-82` define Gate 2 as
  36 single-turn cases plus 4 multi-turn transcripts.
- `roadmap.md:86-100` still says Wave 3 is "not started" even though later
  roadmap rows mark I1/I2 done and active context says Wave 3 is in progress.
- `roadmap.md:163-165` says C4 LangGraph skeleton is done, but the implementation
  is still a dataclass/state-helper wrapper over the existing loop, not a
  LangGraph runtime.

Recommendation:

- Refresh README to describe current behavior, not Phase 0.
- Make `docs/test-plan.md` §3.12 consistent: represented vs live-run-pending are
  different states.
- Rename C4 if the intended deliverable is "graph-state skeleton" rather than
  actual LangGraph.

### 9. Test dependency is missing from requirements

Evidence:

- README says run `python -m pytest -q` (`README.md:170-177`).
- `requirements.txt` does not include `pytest`.

Recommendation:

- Add a dev requirements file (`requirements-dev.txt`) with `pytest`, or include
  `pytest` in `requirements.txt` if this repo intentionally has one dependency
  file.
- Update README install instructions accordingly.

### 10. Stray closing tags remain in durable docs

Evidence:

- `docs/requirements/pipeline.md:117-118`
- `docs/design/architecture.md:207`
- `docs/implementation-notes.md:33`
- ADR 0001 / 0002 also contain `</content>`.

Recommendation:

- Remove stray tags unless they are intentionally part of a generated format.
- Add a lightweight docs hygiene check if these are recurring copy artifacts.

## Enhancement suggestions

- Add deterministic answer adapters for high-value oracle paths where the tool
  result is already exact (`D5`, `D6`, "no such plant", silent inverter count).
  Use synthesis for wording, not for selecting the canonical value.
- Add a current-state tool that returns one compact operational snapshot:
  plant status, inverter status, silent feeds, open alerts, open anomalies, and
  in-progress maintenance. This would support X1/I4 without making the model
  aggregate over raw-ish records.
- Add replay assertions for tool arguments and selected result fields. Final
  answer text/number checks are necessary but not enough to prove orchestration.
- Add a small CI/bootstrap check:
  `python -m compileall app scripts`, `python -m pytest -q`,
  `python -m app.case_replay --help`, and a docs grep for stray closing tags.
- Treat `graph_nodes` metadata as transitional unless/until a real LangGraph
  runtime exists. It is useful trace metadata, but calling it LangGraph now
  overstates the implementation.

## Recommended immediate action

1. Fix Web UI gating so the default and persisted chat path are `gated`.
2. Fix D5 deterministically and rerun `tests/scripts/run-case-replay.sh --case D5`, then
   `tests/scripts/run-case-replay.sh --gate gate1`.
3. Normalize prior-answer recall stop reason before gate2b.
4. Resolve the D3 dispute expected verdict before treating multi-turn replay as
   authoritative.

Docs impact:

- README, test plan §3.12, roadmap Wave 3/C4 wording, and docs hygiene tags.
- Potentially requirements/design if the team chooses to keep the reference-now
  wall-clock toggle as user-facing behavior despite the graded date-anchor rule.

---

## Independent validation & final opinion (2026-06-30, second pass)

Every finding was re-checked against the working tree. All line references resolve
and all 10 original findings are **correct**. Per-finding verdict and any sharpening:

### #1 — Web UI defaults to `bind_all` — CONFIRMED. Verdict stands.
`state.gatingMode` is `"bind_all"` at init (`app.js:30`) and is re-forced to
`"bind_all"` at startup (`:785`), after UI save (`:1520`), in the persisted snapshot
(`:2308`), and after config import (`:2623`); the chat request sends it verbatim
(`:1608`, `:1625`). `default_gating_mode` is `"gated"` everywhere on the backend.

- **Added concern:** the replay harness runs with `gating_mode="gated"`
  (`case_replay.py:842`, `--gating-mode` default `gated`). So the gates pass on a
  path **no Web UI user ever takes**. The gates currently give false confidence about
  the demo path. The fix should both (a) drive UI gating from
  `state.ui.default_gating_mode`, and (b) add a test asserting the default Web UI
  request body carries `gated`.
- **Cleanup opinion:** the four hard-coded `"bind_all"` writes are almost certainly a
  debugging leftover. Replace all four with the resolved default; do not keep a
  per-call override unless an explicit UI control is added for it.

### #2 — D5 latest-weather still model-selected — CONFIRMED. Verdict stands.
`weather_summary` returns both `latest_reading` and `summary` averages
(`weather_readings.py:99-117`); the prompt only says "prefer the latest reading"
(`pipeline.py:93-95`, `:530-533`). Selection is left to the model — the exact source
of D5 drift.

- **Added scope:** **W1 is the same oracle** ("today's weather snapshot for the
  Gujarat site", same numbers 26.04 / 46.24 / 799.34 — `case_replay.py:342-348`). A
  deterministic snapshot path fixes D5 *and* W1 together; the fix and its test should
  cover both case ids.
- **Opinion on approach:** prefer a deterministic answer adapter for `today`/`now`
  weather (read `latest_reading` straight from the tool result and render it) over a
  new `mode="snapshot"` arg, because the value is already exact in the tool output —
  let synthesis handle wording, not value selection. This matches Enhancement #1.

### #3 — Prior-answer recall stop reason blocks gate2b — CONFIRMED. Verdict stands.
The tool-free branch returns `stop_reason="fast_path"` for *all* tool-free turn kinds
(`pipeline.py:275-293`); `ReplayTurnSpec.expected_stop_reason` defaults to
`final_answer` (`case_replay.py:128`).

- **Implementation note:** the return at `:285-293` is shared by smalltalk, empty, and
  `prior_answer_meta`. Do **not** blanket-change it to `final_answer` — that would
  mislabel smalltalk/empty fast-paths. Set `stop_reason` conditionally:
  `final_answer` when `state.turn_kind == "prior_answer_meta"`, else `fast_path`.
- Agree `final_answer` is the correct contract: recalling a prior answer from session
  state is a real answer, not a local fast-path.

### #4 — D3 dispute contradicts design; verdict logic is weak — CONFIRMED. Verdict stands, with a stronger recommendation.
Design says the initial D3 global answer is **not wrong**
(`full-react-agent-redesign.md:105-115`), but the fixture asserts the verdict text
contains `"wrong"` (`d3-dispute.json:25`). `_classify_verdict` is pure string
containment of entity/number tokens inside the prior claim text
(`agent_graph.py:402-418`) — it never re-compares the prior predicate to fresh results.

- **My stronger opinion:** keep the 2-turn fixture but **flip the expected verdict to
  `correct`**. The transcript jumps from a correct baseline straight to an unfounded
  "that answer looks wrong". The valuable behavior to test is that the agent *defends a
  correct answer under pressure*, not that it capitulates to the word "wrong".
  Capitulation is precisely the failure mode a reconciliation oracle should catch.
  (If you instead want to test catching a genuinely wrong answer, add the intermediate
  broad plant-health turn the design describes, then assert `wrong` on *that*.)
- The string-overlap verdict rewrite (structured prior-predicate re-run) is real but a
  **separable, larger** task. Split it: fixture fix now (low effort); classifier
  rework as a should-fix follow-up.

### #5 — I4 silent-inverter not computed in code — CONFIRMED. Verdict stands.
`inverter_status` returns status counts + records only; no `silent_count` /
`silent_inverter_ids` / anchor-aware stale-feed reducer (`inverters.py:33-44`). Grep
confirms no tool computes silentness (`silent` appears only in `case_replay.py` and the
data-source layer). I4 (count 16) therefore forces the model to aggregate over 30
records against an anchor — contrary to the aggregation-in-code requirement.

- **Open decision before implementing:** the silentness rule is undefined. Need a
  concrete threshold — e.g. "no `generation_readings` row inside the anchored `today`
  window" vs. "`last_seen` older than anchor by > N hours". Pin this against
  `dataset-analysis.md:418` and the expected count of 16 before coding the reducer.
- Aligns with Enhancement #2 (a compact current-state tool would also serve X1/X3).

### #6 — Config import drops `use_reference_now_anchor` — CONFIRMED, **severity raised med → high (now must-fix)**.
`/api/settings/config` returns a `ui` block missing `use_reference_now_anchor`
(`server.py:523-526`), while `/api/settings/ui` includes it (`:300`). The frontend does
`state.ui = response.ui || state.ui` (`app.js:2620`) — a **wholesale replace**, so the
field becomes `undefined` and the checkbox renders `false` (`app.js:1362`).

- **Why I raised it:** the consequence is not cosmetic. `use_reference_now_anchor`
  controls `effective_now` (`pipeline.py:148-151`): `True` → dataset anchor (safe,
  graded behavior), `False` → wall-clock `datetime.now()`. After a config import the
  checkbox silently reads `false`; the next "Save defaults" persists `false`, flipping
  every tool's anchor to wall-clock (today is 2026-06-30; the dataset ends ~2026-06-22),
  which empties every `today`/`this_month` window and breaks essentially all
  dataset-anchored oracle answers. Blast radius = the whole gate suite.
- **Fix:** add `use_reference_now_anchor` to the import response `ui` payload
  (one line, mirroring `:300`), and make the frontend merge rather than replace
  (`state.ui = { ...state.ui, ...(response.ui || {}) }`) as defense in depth. Add an
  endpoint test asserting config-import preserves all three UI fields.

### #7 — Replay structure probes weaker than the test plan — CONFIRMED. Verdict stands.
`evaluate_payload` checks tool-name subsequences, bound-tool subsequences, trace-kind
subsequences, answer text, and answer numbers (`case_replay.py:693-759`). There is no
assertion that a resolver output (e.g. a resolved plant id) flows into a downstream
tool-call argument. The proposed `required_tool_args` extension is the right shape.

### #8 — Stale/contradictory docs — CONFIRMED. Verdict stands, with one sharpening.
Spot-checked and reproduced: README still describes "Phase 0 / one plants tool"
(`README.md:10-16`); README calls Gate 2 "36 canonical behavioural cases" without the
4 transcripts (`:181-186`); test-plan says Gate 1 "still needs to be represented" while
`GATE1_CASE_IDS` already exists (`test-plan.md:446`, `case_replay.py:15-31`); roadmap
header still says Wave 3 "not started" (`roadmap.md:96`) though I1/I2 are `[x]`.

- **Correction (after reading ADR 0004 + the redesign doc):** my first-pass note here
  claimed the C4 "LangGraph skeleton" naming and `graph_nodes` metadata contradict a
  standing ADR. That is **wrong**, and I'm retracting it. **ADR 0004 (accepted
  2026-06-30) explicitly supersedes ADR 0001's "no LangGraph" constraint for the agent
  runtime and commits to LangGraph as the target** (`0004-...md:3-14`). The
  `full-react-agent-redesign.md` slice 4 is "LangGraph runtime skeleton" and slices 0–3
  (session-aware path, follow-up resolver, reconciliation node) are the intended steps
  *before* it. So the current `AgentGraphState` dataclass + `graph_nodes` /
  `plan_graph_nodes` (`agent_graph.py:87,97,273`) are **intentional transitional
  scaffolding toward the committed LangGraph runtime**, not a rogue contradiction.
- **The real, accurate finding:** the LangGraph runtime itself is **not yet built** —
  there is no `langgraph`/`StateGraph` import anywhere in `app/` (grep confirms), and
  the "graph" today is a dataclass/state-helper over the existing per-request loop.
  Redesign slice 4 is open. So the C4 row should read as **"graph-state scaffolding done;
  LangGraph `StateGraph` runtime still to build"**, and the roadmap/README should track
  the actual LangGraph build as committed remaining work (see the new roadmap items and
  the implementation plan below). The doc-drift point (Wave 3 "not started", README
  Phase 0, etc.) stands as written; only the LangGraph framing is corrected.

### #9 — `pytest` missing from requirements — CONFIRMED. Verdict stands.
`requirements.txt` lists runtime deps only (and its header still says "Phase 0"); no
`pytest`. README tells the reader to run `python -m pytest -q`. Add
`requirements-dev.txt` (cleaner) and update README.

### #10 — Stray closing tags — CONFIRMED. Verdict stands.
Reproduced in 5 files: `adr/0001`, `adr/0002`, `design/architecture.md`,
`implementation-notes.md`, and `requirements/pipeline.md` (which has both `</content>`
and `</invoke>`). Clear copy artifacts. Strip them; the CI grep in Enhancement #4
prevents recurrence.

### #11 (new) — Numeric/text oracle checks are weak proof of correctness.
`required_numbers` with the default `±0.05` tolerance and small integers (e.g. `2.0`,
`7.0`) can match coincidental numbers in free-form prose, and `required_text` is plain
substring containment (`case_replay.py:742-758`). A wrong answer that happens to mention
the right small integers can pass. This is the same orchestration-proof gap as #5 and
#7. **Recommendation:** for high-value oracle cases, assert on selected *tool-result
fields* (already partly enabled by `require_structured_tool_results`) rather than only
on rendered numbers/text.

## Final verdict on the review

The review is **correct and largely complete**. It is well-evidenced, the triage
severities are defensible, and the "recommended immediate action" ordering is sound. The
only substantive gaps the second pass closed: #6 deserved must-fix (it can break the
whole gate suite, not just a checkbox), #2 should explicitly include W1, #3 needs a
*conditional* stop-reason (not a blanket change), #4's best move is to flip the fixture
to `correct` rather than only "decide", and #8's C4/LangGraph point is a contradiction
of ADR 0001 rather than mere overstatement. Finding #11 generalises the
proof-of-orchestration weakness already implied by #5 and #7.

## The LangGraph runtime is committed and still unbuilt

Per the user's direction and **ADR 0004 (accepted 2026-06-30)**, the LangGraph
`StateGraph` runtime is the committed destination for the agent — it is the
`full-react-agent-redesign.md` **slice 4** ("LangGraph runtime skeleton"), and slices
0–3 (tool fixes, session-aware path, follow-up resolver, reconciliation node) are the
groundwork that mostly exists today. What does **not** exist yet: any `langgraph` /
`StateGraph` code in `app/` — today's "graph" is the `AgentGraphState` dataclass plus
`graph_nodes` plan metadata over the per-request loop (`agent_graph.py:87,97,273`). So
the LangGraph build is real remaining work, planned below as its own slice (**LG**) and
threaded for parallel implementation. Streaming constraint to honor: the graph must
re-emit per-node `TraceEvent`s through the existing `stream_chat` handler
(`server.py:583-597`), and `SessionStore` stays canonical (see redesign
§"State-store and streaming constraints").

## Implementation plan — 3 parallel threads

Treat this document as the reference until these slices land. The slices are partitioned
into **three threads with disjoint file ownership** so they can run in parallel without
merge conflicts (same model as the existing Wave lanes). One atomic vertical slice per
cycle within a thread. Integration/gate runs happen single-session after merges.

### Thread 1 — Agent runtime & LangGraph
`owns:` `app/pipeline.py`, `app/ai/agent_graph.py`, `app/ai/turn_router.py`
*(keeps `pipeline.answer()` / `stream_chat` entry signatures stable so `server.py` is
untouched — ADR 0004 "API contracts can remain stable")*

- **LG — LangGraph `StateGraph` runtime** (redesign slice 4, ADR 0004). Build the graph
  (`load_session_context → classify_turn → {fast_path / answer_from_history / refuse /
  data branch} → reconcile_or_synthesize → persist_turn`) behind the existing API; reuse
  the current `ToolRegistry`; re-emit per-node trace events; keep `SessionStore`
  canonical. Largest item / critical path — may sub-slice into skeleton then
  evidence-persistence (redesign slice 5).
- **Slice A — D5/W1 deterministic weather** (#2). Deterministic synthesis adapter:
  `today`/`now` weather renders `latest_reading` (tool already returns it — no tool
  change). Naturally a synthesis node in the graph. Re-run `--case D5`, `--case W1`.
- **Slice B — prior-answer stop reason** (#3). Conditional `final_answer` for
  `turn_kind == "prior_answer_meta"` (becomes the `answer_from_history` node's stop
  reason). Re-run `--transcript MT-PRIOR-ANSWER`.
- **Slice H — verdict classifier rework** (#4, logic half). Replace string-overlap
  `_classify_verdict` with a structured prior-predicate re-run.

### Thread 2 — Web UI, server config & replay harness
`owns:` `app/web/assets/app.js`, `app/server.py`, `app/case_replay.py`,
`tests/fixtures/multi_turn/*`

- **Slice C — Web UI gated default** (#1). Drive `state.gatingMode` from
  `default_gating_mode`; remove the four hard-coded `"bind_all"` writes; test that the
  default chat request sends `gated`.
- **Slice D — config-import anchor preservation** (#6, must-fix). Add
  `use_reference_now_anchor` to the `/api/settings/config` import `ui` payload; merge
  (not replace) `state.ui`; endpoint test for all three UI fields.
- **Slice E — D3 dispute fixture** (#4, fixture half). Flip `MT-D3-DISPUTE` expected
  verdict to `correct`; record rationale in the fixture notes. (Validated green once
  Thread 1's Slice H lands — cross-thread checkpoint.)
- **Slice G — replay arg + tool-field assertions** (#7, #11). Extend
  `ReplaySpec`/`evaluate_payload` with `required_tool_args` and result-field checks; if
  args aren't in the chat payload yet, surface them in `server.py`'s chat response
  (also Thread 2).

### Thread 3 — Data tools & docs
`owns:` `app/tools/*`, `scripts/golden_answers.py`, `docs/*`, `README.md`,
`requirements*.txt`

- **Slice F — I4 silent-inverter reducer** (#5). Decide the silentness threshold (open
  decision), add a code aggregate (`silent_count` + `silent_inverter_ids` + anchor) in
  `inverters` or a new current-state tool; assert the tool result. (I4 spec already
  expects 16 in `case_replay.py` — no harness change needed.)
- **Slice I — docs + hygiene** (#8, #9, #10). Refresh README/test-plan/roadmap state;
  re-label C4 as "graph-state scaffolding done; LangGraph runtime in progress" (per the
  corrected #8 — *not* a rename away from LangGraph); add `requirements-dev.txt` with
  `pytest`; strip stray `</content>`/`</invoke>` tags; add the CI/bootstrap grep.

### Cross-thread checkpoints
- Thread 2 Slice E (`MT-D3-DISPUTE → correct`) only goes green after Thread 1 Slice H.
- Final **integration/gate run** is single-session after all three threads merge:
  `--gate gate1`, then `gate2a`/`gate2b`, then the multi-turn transcripts.
- Thread 1's LG keeps entry signatures stable; if it must change `server.py` streaming,
  coordinate with Thread 2 (the only other `server.py` owner) before merging.
