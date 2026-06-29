# Test plan

> Behavioural test plan for the assistant pipeline. Scope and intent come from
> `docs/solar_interview_task.md`; the correctness oracle is
> `docs/golden-answers.md`; dataset facts behind expected answers live in
> `docs/dataset-analysis.md`.
>
> **Status:** §1 captures the task document verbatim (cases, requirements,
> rubric, non-goals). §2 is the **spec traceability matrix** — every task item
> with a status indicator (✅/➕/🟡/🔧/⛔) and the case(s) proving it. §3 is the
> **full per-surface case catalog** (plants…anomalies + cross-cutting), exceeding
> the spec's A/B/C examples. The former **[oracle⁺]** placeholders are now pinned
> in `docs/golden-answers.md`; the replay harness and rubric checks live in
> `app/case_replay.py` + `scripts/cli_case_replay.py`. **CLI target:** every case
> in this plan (51 behavioural + 5 structural probes) is meant to run through CLI
> replay; 15 cases have replay specs today (listed in §3.12). Still pending: the
> live full-catalog replay against the real chat stack.

---

## 1. Test cases extracted from the task document

All cases below are taken verbatim or near-verbatim from
`docs/solar_interview_task.md`. Nothing here is invented; each row cites its
location in that document. Three groups:

- **D1–D6** — the suggested demo questions (the canonical demo set the debrief
  walks through).
- **A/B/C** — the illustrative example questions listed under each intent type.
- **R1–R5** — the pipeline-requirement deliverables, which are themselves
  testable obligations rather than single questions.

Expected-answer columns reference the oracle (`golden-answers.md`) only for the
demo questions, which are the ones the task pins to specific outcomes. The other
rows assert *behaviour* (correct intent, correct tool selection, refusal), with
concrete expected values to be filled in section 2.

### 1.1 Demo questions (task §"Suggested test questions for the demo")

| ID | Question | Intent | Expected behaviour | Oracle |
|----|----------|--------|--------------------|--------|
| D1 | Which plant is offline and what is the associated open alert? | A (+ chain) | Identify the offline plant and join its open alert(s). | `golden-answers.md` Q1 |
| D2 | What was the average daily yield of Rajasthan Solar Park last week? | B (+ chain) | Resolve plant name→id, aggregate daily_yield over last week. | `golden-answers.md` Q2 |
| D3 | Which inverters have open hotspot anomalies caused by soiling? | C | Exact filter `status=open ∧ anomaly_type=hotspot ∧ cause=soiling`. | `golden-answers.md` Q3 |
| D4 | What is the mean time to resolve a critical alert? | B | MTTR over resolved critical alerts only. | `golden-answers.md` Q4 |
| D5 | What's the weather like at the Gujarat plant today? | A/B (+ chain) | Resolve "Gujarat plant"→id, weather snapshot at anchor. | `golden-answers.md` Q5 |
| D6 | How much revenue did we lose from Tamil Nadu's downtime this month? | out-of-scope | **Refuse cleanly** — no hallucinated number. (Task marks this intentionally unanswerable.) | `golden-answers.md` Q6 |

### 1.2 Type-A examples — current state (task §"Type A")

| ID | Question | Intent | Expected behaviour |
|----|----------|--------|--------------------|
| A1 | Which plants are currently offline? | A | Filter plants by current status = offline. |
| A2 | How many inverters are in fault right now? | A | Count inverters with status = fault (exact). |
| A3 | What open critical alerts exist? | A | Filter alerts by status = open ∧ severity = critical. |

### 1.3 Type-B examples — statistics & trends (task §"Type B")

| ID | Question | Intent | Expected behaviour |
|----|----------|--------|--------------------|
| B1 | What is the average daily yield per plant over the last week? | B | Per-plant daily_yield aggregation over last-week window. |
| B2 | Which inverter has the highest performance ratio? | B | Rank inverters by mean performance_ratio (nulls excluded). |
| B3 | What is the mean time to resolve an alert? | B | MTTR over all resolved alerts. |

### 1.4 Type-C examples — anomaly lookup (task §"Type C")

| ID | Question | Intent | Expected behaviour |
|----|----------|--------|--------------------|
| C1 | Which inverters have open hotspot anomalies? | C | Filter anomalies by status = open ∧ anomaly_type = hotspot (exact). |
| C2 | What anomalies are caused by soiling? | C | Filter anomalies by cause = soiling. |
| C3 | Summarise all unresolved anomalies for Rajasthan Solar Park. | C (+ chain) | Resolve plant name→id, then filter unresolved anomalies — the task's named 2-step chain example. |

### 1.5 Pipeline-requirement obligations (task §"Pipeline requirements")

These are the deliverables the task says are being evaluated. Each is a test
obligation the suite must assert, not a single question.

| ID | Requirement | Assertion | Deliverable (task) |
|----|-------------|-----------|--------------------|
| R1 | Intent classification | Classified intent is explicit and inspectable in output/logs for every question (incl. multi-type). | "show the classified intent in the output or logs" |
| R2 | Tool / function design | Tools are independently callable and testable; the orchestrator does **not** load all seven tables on every question. | "tools must be independently callable and testable" |
| R3 | Multi-step planning | At least one 2-step chain is demonstrated (e.g. resolve plant id → filter anomalies; D2/D5/C3). | "demonstrate at least one 2-step chain" |
| R4 | Aggregation in code | Aggregations computed in code; **no raw CSV rows in the final LLM prompt**. | "no raw CSV rows in the final LLM prompt" |
| R5 | Graceful degradation | At least one ambiguous/out-of-scope question refuses clearly instead of hallucinating (D6). | "Include at least one out-of-scope test question" |

### 1.6 Coverage notes

- The demo set covers all three intent types plus the unanswerable case; D1, D2,
  D5 and C3 also exercise the multi-step chain requirement (R3).
- A2, C1 and D3 specifically exercise **exact-string matching** — `fault`,
  `hotspot` and `scheduled` each appear inside larger category values
  (`inverter_fault`, `multi hotspot`, `scheduled_repair`), so a substring match
  over- or under-counts. See `dataset-analysis.md` §"Vocabulary coverage map".
- D5 and C3/D2 exercise name→id resolution where **region ≠ state** ("Gujarat
  plant" must resolve against `name`/`location`, not `region`). See
  `dataset-analysis.md` §"Entity resolver index".
- §2 attaches a coverage status to the A/B/C rows and the R-obligations; the
  concrete expected values live in §3 and `golden-answers.md`, drawn from the
  Type-A snapshot / measure-semantics tables in `dataset-analysis.md`.

### 1.7 Evaluation criteria (task §"Evaluation criteria")

The five-row rubric the task grades against. Each criterion is mapped to the
test IDs that prove it, with the mechanism that asserts each one.

| Criterion | What the task looks for | Proven by | Status |
|-----------|-------------------------|-----------|--------|
| Pipeline structure | Intent classification separate from data fetching and from LLM synthesis; stages composable. | R1, R2, `tests/test_case_replay.py` | Covered by trace-order assertions (`intent_*` before `synthesis_*` / tool execution) plus replay checks that the bound-tool subset is exposed. |
| Tool design | Tools narrowly scoped, testable in isolation, return structured data (not prose). | R2, R2-unit, `tests/test_case_replay.py`, `tests/test_phase1_pipeline_core.py` | Covered by per-tool isolation tests and replay assertions that tool-call results stay structured dict payloads with `ok` flags. |
| Aggregation correctness | Numbers computed in code, not estimated by the LLM. | B1, B2, B3, D2, D4, R4 | Covered by oracle-backed value assertions and the "no raw CSV rows in final prompt" probe in `tests/test_case_replay.py`. |
| Multi-step reasoning | Orchestrator chains tool calls where one output informs the next. | R3, D1, D2, D5, C3, `tests/test_phase1_pipeline_core.py` | Covered by chain cases plus scripted-loop assertions that a resolver step and downstream tool step execute in sequence. |
| Failure handling | Degrades gracefully on ambiguous or unanswerable questions. | R5, D6, X6 | Covered by the unanswerable refusal and the explicit ambiguous-clarification case. |

### 1.8 Non-goals — out of scope for testing (task §"What you do not need to build")

The task explicitly excludes these. We do **not** write tests against them; they
bound the suite so effort isn't spent here.

- Production-grade UI (a terminal REPL is acceptable).
- Streaming responses.
- Authentication / multi-user support.
- A real-time data feed (the CSVs are the full, frozen dataset).
- Training or fine-tuning any model.

### 1.9 Framing notes (task §"Context" and intro)

- The chat interface itself need not be polished — a simple REPL or minimal web
  form is fine. **Evaluation is entirely on the quality of the pipeline behind
  it.** → The test plan therefore targets pipeline behaviour, not UI polish.
- The seven CSVs are each treated as a logical endpoint the pipeline can query;
  the schema is a two-level hierarchy (plants → inverters → the rest). Full
  schema and FK detail are not restated here — see `dataset-analysis.md`
  §"Data dictionary" and §"Foreign-key integrity".
- "An LLM calling the data directly is not sufficient — the structure around it
  is what matters." → Tests must assert the *structure* (intent → tool
  selection → code aggregation → synthesis), not just final-answer text.

### 1.10 Remaining open item

The earlier section-level TODOs are reconciled into the runnable harness and
probe tests. The one material item outstanding is the live replay of the **full**
catalog — all 51 cases + the 5 structural probes — through the configured chat
stack; 15 cases are replay-backed today (roadmap §2b / §3.12).

---

## 2. Spec traceability — every task item, with status

> Goal: see at a glance whether each obligation from `solar_interview_task.md` is
> covered, and by which case. **Coverage principle** (`docs/requirements/pipeline.md`):
> the spec is a *floor, not a ceiling* — a broader/more universal mechanism that
> subsumes a narrow ask counts as **met by superset (➕)**, not a gap. We never
> drop below the spec; we may rise above it, with justification.

**Status legend** — ✅ Covered (verified by an automated test that runs today —
unit/probe/replay) · ➕ Met by superset (broader mechanism, verified the same
way) · 🟡 Working (implemented, not yet confirmed by its own CLI replay) · 🔧
Needs work · ⛔ Refuse by design. *Note:* ✅ means a real automated check passes
now; it does **not** assume the full-catalog CLI run is complete — that run is
the 🟡 cases' target (§3.12).

> Most rows below are **🟡 Working** today: the pipeline (intent → gated tools →
> code aggregation → synthesis) is implemented, but the catalog in §2.3 has not
> yet been replayed through CLI mode. The `cases-first` track (roadmap) flips
> these to ✅/➕ as the CLI run confirms each. Status here is a claim to be
> *proven by the run*, not an assertion that it already passed.

### 2.1 Intent-type examples (task §"What the assistant must handle")

| Spec item | Case(s) | Status | Note |
|-----------|---------|--------|------|
| Type A — "which plants currently offline" | A1, P1 | 🟡 | plants.status=offline (exact). |
| Type A — "how many inverters in fault right now" | A2, I1 | 🟡 | inverters.status=`fault` **exact** (not `inverter_fault`). |
| Type A — "what open critical alerts exist" | A3, AL1 | 🟡 | alerts status=open ∧ severity=critical. |
| Type B — "avg daily yield per plant over last week" | B1, G1 | 🟡 | per-inverter daily-max → sum → mean over days; window anchored. |
| Type B — "which inverter has highest performance ratio" | B2, G4 | 🟡 | mean PR excluding nulls, ranked. |
| Type B — "mean time to resolve an alert" | B3, AL5 | 🟡 | MTTR over resolved alerts only. |
| Type C — "which inverters have open hotspot anomalies" | C1, AN1 | 🟡 | anomaly_type=`hotspot` **exact** ∧ status=open. |
| Type C — "what anomalies are caused by soiling" | C2, AN2 | 🟡 | cause=soiling. |
| Type C — "summarise unresolved anomalies for Rajasthan" | C3, AN6 | 🟡 | chain: resolve plant→id, then filter not-resolved. |
| "A question may be a multi-type combination" | X1, X2 | 🟡 | D1/D5 already mix A+chain; X-series adds explicit A+B+C blends. |

### 2.2 Pipeline requirements (task §"Pipeline requirements")

| # | Requirement | Case(s) | Status | Note |
|---|-------------|---------|--------|------|
| R1 | Explicit, inspectable intent classification | every case (intent column) | 🟡 | classifier logged per question; assert intent appears in trace. |
| R2 | Tools independently callable/testable; **not** all 7 on every question | R2-unit, gating cases | ➕ | gating is a *config toggle* (ADR 0002) — exceeds "select by intent": `gated` default + `bind_all` option. |
| R3 | At least one 2-step chain | D1, D2, D5, C3, AN6, X3 | ➕ | spec asks for *one*; catalog exercises **six** chains across surfaces. |
| R4 | Aggregation in code; no raw CSV rows in final prompt | B*, G*, AL5, R4-probe | 🟡 | tools return structured dicts; R4-probe asserts no raw rows reach the model. |
| R5 | Graceful degradation; ≥1 out-of-scope | D6, X5 (unanswerable), X6 (**ambiguous**) | ➕ | spec asks for *one* out-of-scope; we add an **ambiguous** case too (the §1.10 gap). |

### 2.3 Evaluation rubric (task §"Evaluation criteria")

| Criterion | Proven by | Status | Note |
|-----------|-----------|--------|------|
| Pipeline structure (stages separate/composable) | R1, R2, R4-probe, replay trace probes | ✅ | trace order + bound-tool subset assertions now cover the architecture-level contract. |
| Tool design (narrow, isolated, structured) | R2-unit per surface, replay structured-result probe | ✅ | unit isolation checks and replay assertions cover rubric row 2. |
| Aggregation correctness | golden Q2/Q4 + B*/G* vs oracle | 🟡 | values from `golden-answers.md`; extend oracle for A/B/C. |
| Multi-step reasoning | D1/D2/D5/C3/AN6/X3 + scripted chain tests | ✅ | resolver→downstream-tool sequencing is asserted in the scripted loop tests. |
| Failure handling | D6, X5, X6 | ➕ | adds ambiguous beyond unanswerable. |

### 2.4 Non-goals — **not** tested (task §"What you do not need to build")

UI polish · streaming · auth/multi-user · real-time feed · model training. No
cases target these (see §1.8). The Web UI/CLI we build anyway is template value,
not a graded surface.

---

## 3. Full case catalog (per surface)

> Each case: **question** · **intent** · **expected chain** (tools, in order;
> `∥` = parallelizable siblings) · **expected value/behaviour** · **trap guarded**.
> Concrete numbers are cited from `golden-answers.md` or the `dataset-analysis.md`
> ground-truth tables where those exist; otherwise marked **[oracle⁺]** = the
> oracle script must be extended to pin the value before this flips to ✅. We do
> **not** invent numbers.
>
> The catalog deliberately exceeds the spec's A/B/C examples (Coverage
> principle): it sweeps every surface along single-vs-chained, exact-match traps,
> null/lifecycle traps, and refusal/ambiguous axes.

### 3.1 Demo set (concrete oracle values from `golden-answers.md`)

| ID | Question | Intent | Expected chain | Expected value | Trap |
|----|----------|--------|----------------|----------------|------|
| D1 | Which plant is offline and what is the associated open alert? | A+chain | plants(status=offline) → alerts(plant_id, status=open) | Tamil Nadu PV Plant; open alert id `1`, critical, grid_disconnection | offline plant may have few alerts; join on resolved id |
| D2 | Avg daily yield of Rajasthan last week? | B+chain | resolve "Rajasthan"→`4135001` → daily_yield agg, window last_week | **123354.2 kWh** (7 days covered) | daily_yield = per-inverter daily-max then sum; window anchored to 2026-06-22 |
| D3 | Open hotspot anomalies caused by soiling? | C | anomalies(status=open ∧ type=`hotspot` exact ∧ cause=soiling) | count **2**, ids `7`,`55` | `hotspot` ≠ `multi hotspot`; empty would be a valid answer |
| D4 | Mean time to resolve a critical alert? | B | alerts(severity=critical, resolved) MTTR | **6.3 h** over **6** resolved | open criticals excluded (no resolved_at) |
| D5 | Weather at Gujarat today? | A/B+chain | resolve "Gujarat"→`4136001` → weather @ anchor | ambient 26.04°C, module 46.24, irrad 799.34, wind 5.29, humidity 89.5, cloud 6.5%, rain 0 | "today" = anchor day, not wall clock; region≠state |
| D6 | Revenue lost from Tamil Nadu downtime this month? | out-of-scope | — | ⛔ refuse: no kWh-bridge (downtime→lost-energy×tariff) | must refuse, not fabricate |

### 3.2 Plants (P) — Type A / resolver

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| P1 | Show me every plant that's offline right now. | A | plants(status=offline) | [Tamil Nadu PV Plant] (1) | exact status; reworded twin of A1 |
| P2 | List all plants and their status. | A | plants(all) | Rajasthan=active, Gujarat=maintenance, Tamil Nadu=offline | — |
| P3 | What is the nameplate capacity of the Gujarat plant? | A+chain | resolve "Gujarat"→id → plants.capacity_mw | 18.5 MW | region≠state name resolution |
| P4 | Which plant has the highest feed-in tariff? | B(min) | plants rank tariff_usd_per_kwh | Rajasthan Solar Park at **0.052 USD/kWh** | tiny table, still aggregate in code |
| P5 | How many inverters does Rajasthan have? | A+chain | resolve→id → inverters count | 10 | declared vs actual both = 10 |

### 3.3 Inverters (I) — Type A / status reconciliation

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| I1 | What's the count of inverters currently in a fault state? | A | inverters(status=`fault` exact) | **1** (INV_4135001_10) | `fault` is inside `inverter_fault`/`sensor_fault` — exact only; reworded twin of A2 |
| I2 | How many inverters are offline? | A | inverters(status=offline) | 15 | — |
| I3 | Which inverters at Tamil Nadu are not online? | A+chain | resolve→id → inverters(plant_id, status≠online) | all 12 offline | whole-plant outage |
| I4 | Which inverters are silently not reporting (offline by data, not just status)? | A (superset) | inverters ⨝ generation last_seen vs anchor | 16 silent (e.g. INV_4136001_06…) | **status field alone insufficient** — combine signals (cross-table reconciliation) |
| I5 | Show inverters that are "online" in status but have an open alert. | A+chain | inverters(status=online) ∥ alerts(status=open) join | **1** match: `INV_4135001_05` with open alert `4` | status disagreement surface |

### 3.4 Generation readings (G) — Type B / measure semantics

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| G1 | Per plant, what's the mean daily energy yield over the past week? | B | daily_yield agg group_by plant, window last_week | Rajasthan **123354.2**; Gujarat **68649.9**; Tamil Nadu **151152.5** kWh | per-inverter daily-max, not raw sum; reworded twin of B1 |
| G2 | Total energy generated by Rajasthan this month. | B+chain | resolve→id → total_yield diff over window | **3004224.3 kWh** | `total_yield` = last−first, never sum/mean |
| G3 | Average AC power for INV_4135001_01 last 7 days. | B | generation(inverter, window) mean ac_power | **593.10 kW** | mean of spot kW; night zeros are legitimate |
| G4 | Which inverter tops the fleet on performance ratio? | B | generation mean PR (nulls excluded) ranked | `INV_4137001_04` at **0.9519** | exclude null PR (⟺ dc_voltage=0); don't zero-fill; reworded twin of B2 |
| G5 | What was the peak AC power across the fleet this month? | B | generation max ac_power, window | **2505.92 kW** at `2026-06-18 13:00:00` on `INV_4135001_03` | max vs mean reducer |
| G6 | Average performance ratio at night. | B (degrade) | generation PR where dc_voltage=0 | **Empty + reason** (not a refusal): PR undefined when dc_voltage=0 → return no value and state why | the null-semantics trap surfaced as a question |

### 3.5 Weather (W) — Type A snapshot / Type B trend

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| W1 | What's the weather at Gujarat today? | A+chain | resolve→id → weather @ anchor | = D5 values | anchor day |
| W2 | Average irradiation at Rajasthan last week. | B+chain | resolve→id → weather mean irradiation, window | **253.60 W/m²** | mean over readings |
| W3 | Which plant had the highest cloud cover this month? | B | weather group_by plant, max/mean cloud_cover | Oracle pins **monthly mean** cloud cover: Rajasthan at **23.66%** (peak on same plant **58.8%**) | group + reduce in code |
| W4 | Was there any rainfall at Tamil Nadu this week? | A/B+chain | resolve→id → weather sum/any rainfall_mm | **No**; total rainfall **0.0 mm** | int column; sum vs any |

### 3.6 Alerts (AL) — Type A state / Type B MTTR

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| AL1 | List the critical alerts that are still open. | A | alerts(status=open ∧ severity=critical) | **1** open critical alert: `1` at Tamil Nadu (`grid_disconnection`) | open∧critical intersection; reworded twin of A3 |
| AL2 | How many alerts are currently open? | A | alerts(status=open) | 4 | — |
| AL3 | Show all alerts for Rajasthan. | A+chain | resolve→id → alerts(plant_id) | **15** alerts total (`13` resolved, `2` open) | join on resolved id |
| AL4 | What is the total downtime caused by resolved alerts? | B | alerts(resolved) sum downtime_minutes | **31836 minutes** | downtime_minutes ⟺ not-open; open rows have none |
| AL5 | Mean time to resolve an alert, all severities. | B | alerts(resolved) MTTR | **22.16 h** across **25** resolved alerts | open alerts excluded by construction; reworded twin of B3 |
| AL6 | What is the MTTR for open alerts? | B (degrade) | alerts(status=open) MTTR | **Empty + reason** (not a refusal): open alerts have no resolved_at → MTTR has no inputs; say so | lifecycle null is structural, not missing |

### 3.7 Maintenance (M) — Type A workflow

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| M1 | What maintenance is in progress? | A | maintenance(status=`in_progress`) | 4 | exact `in_progress` (underscore) |
| M2 | What maintenance is scheduled? | A | maintenance(status=`scheduled` exact) | 3 | `scheduled` ≠ `scheduled_repair` (that's anomalies) |
| M3 | Total maintenance cost on done tickets. | B | maintenance(status=done) sum cost_usd | **41715 USD** | only completed have meaningful cost |
| M4 | Average duration of completed maintenance. | B | maintenance mean duration_hours | **4.93 h** across **12** completed tickets | duration null on scheduled — exclude |
| M5 | Which inverters at Gujarat have maintenance in progress? | A+chain | resolve→id → maintenance(plant_id, status=in_progress) | **3** tickets: `INV_4136001_06`, `INV_4136001_07`, `INV_4136001_08` | inverter_id sometimes null on maintenance |

### 3.8 Anomalies (AN) — Type C lookup

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| AN1 | Which inverters have hotspot anomalies that are still open? | C | anomalies(type=`hotspot` exact ∧ status=open) | **7** open hotspot anomalies (exact `hotspot`) | `hotspot` ≠ `multi hotspot`; reworded twin of C1 |
| AN2 | Which anomalies have soiling as their cause? | C | anomalies(cause=soiling) | 8 | reworded twin of C2 |
| AN3 | How many open anomalies are there fleet-wide? | C | anomalies(status=open) | 28 | — |
| AN4 | Total estimated power loss from open anomalies. | B/C | anomalies(status=open) sum estimated_power_loss_kw | **1421.42 kW** | sum for fleet exposure, mean for typical |
| AN5 | List critical anomalies and their recommended action. | C | anomalies(severity=critical) | 18 rows, with recommended_action | — |
| AN6 | Give me a rundown of every unresolved anomaly at Rajasthan Solar Park. | C+chain | resolve "Rajasthan"→`4135001` → anomalies(plant_id, status≠resolved) | **15** unresolved total = `7` open + `5` scheduled_repair + `3` monitoring | "unresolved" = open+monitoring+scheduled_repair, not just `open`; the task's named chain (reworded twin of C3) |
| AN7 | Which anomalies are linked to a maintenance ticket? | C | anomalies(maintenance_ticket_id not null) | **2** (anomaly ids `1`,`4`; tickets `6`,`5`) | mostly-null link column (96% null) |

### 3.9 Cross-cutting / chains / degradation (X)

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| X1 | Give me a full health summary of the Gujarat plant. | A+B+C+chain | resolve→id → (inverters status ∥ alerts open ∥ anomalies open ∥ maintenance in_progress ∥ weather) gather | Gujarat: 5/3/0 inv, 1 open alert, 8 open anomalies, 3 maint | **parallel fan-out** under one resolved parent |
| X2 | Compare Rajasthan and Tamil Nadu on open anomalies and yield. | B+C+chain | resolve both → (anomalies ∥ daily_yield) per plant, compare | Rajasthan: `7` open anomalies / **123354.2 kWh** avg daily yield; Tamil Nadu: `13` / **151152.5 kWh** | multi-entity parallel chain |
| X3 | For the inverter in fault, what alert and anomalies does it have? | A+C+chain | inverters(status=fault)→INV_4135001_10 → alerts ∥ anomalies | Fault inverter `INV_4135001_10`; alerts `2`,`16`,`27`; anomalies `4`,`17`,`54` | **child→sibling** chain (resolve via status, not name) |
| X4 | Which plant is performing worst right now? | B (superset) | rank plants by PR / yield / open-issue load | Oracle pins metric = lowest last-week mean PR → Rajasthan at **0.9077** | "worst" is underspecified → define metric, state it |
| X5 | Forecast next week's generation for Rajasthan. | out-of-scope | — | ⛔ refuse: dataset historical & frozen, no forward data | unanswerable (non-derivable) |
| X6 | How is the plant doing? | **ambiguous** | clarify | 🟡 ask which plant (3 exist) — clarify, don't guess | **ambiguous ≠ unanswerable**: ask, don't refuse, don't fabricate |
| X7 | What's the status of plant 9999? | A (empty) | plants(id=9999) | clean "no such plant" | unknown entity → empty, not error |

### 3.10 Requirement-probe cases (assert structure, not just answers)

| ID | Asserts | Mechanism |
|----|---------|-----------|
| R2-unit | each tool callable in isolation, returns a structured dict (not prose), never raw rows | per-tool unit test over `ToolRegistry.invoke` |
| R2-gating | gated mode binds only the intent subset (+ resolvers), not all 7 | inspect bound schema list per intent; compare to `bind_all` |
| R4-probe | no raw CSV rows in the final synthesis prompt | scan the assembled prompt for row-shaped payloads / DataFrame dumps |
| R3-trace | one tool's output feeds the next in a chain | assert the resolved id from step 1 appears as an arg in step 2 (D2/C3/AN6) |
| R1-trace | classified intent is present and inspectable | assert intent object in the trace for every case |

### 3.11 Trap index (coverage of dataset gotchas → guarding case)

| Dataset trap (`dataset-analysis.md`) | Guarded by |
|--------------------------------------|-----------|
| `fault` substring of `inverter_fault`/`sensor_fault` | I1 |
| `hotspot` substring of `multi hotspot` | D3, AN1 |
| `scheduled` substring of `scheduled_repair` | M2 |
| region is a compass label, not state | P3, D5, W1, D2, AN6 |
| `daily_yield` per-inverter daily-max then sum | D2, G1 |
| `total_yield` window diff, never sum | G2 |
| `performance_ratio` null ⟺ dc_voltage=0 | G4, G6 |
| `resolved_at`/`downtime_minutes` ⟺ not-open | D4, AL4, AL6 |
| `started_date` ⟺ not-scheduled; duration null on scheduled | M4 |
| silent inverters offline before anchor | I4 |
| anchor day = "today"/"now", not wall clock | D5, W1, G1 |
| revenue-from-downtime non-derivable | D6 |
| forecast non-derivable | X5 |
| ambiguous (multiple plants) → clarify | X6 |
| unknown entity → empty, not error | X7 |

### 3.12 Harness & oracle status

**Done:**

- Oracle values are pinned in `docs/golden-answers.md` via
  `scripts/golden_answers.py`, including the former `[oracle⁺]` rows.
- The replay harness lives in `app/case_replay.py` with the thin CLI entrypoint
  `scripts/cli_case_replay.py`; it checks intent, tool chain, and answer facts
  against the oracle-backed expectations. Each case run creates a dedicated chat
  session titled `"Replay {case_id}"` (e.g. `"Replay D2"`) so runs are traceable
  in the session store by test-plan ID.
- Replay payload checks also cover the architecture-level metadata exposed by
  the API: bound-tool subsets, stage-ordered trace events, and structured
  tool-call results.
- `tests/test_case_replay.py` and `tests/test_phase1_pipeline_core.py` carry the
  architecture probes for rubric rows 1–2 and the scripted chain/no-raw-row
  checks behind rows 3–4.

**Automated today** (15 replay specs in `app/case_replay.py`): D2, D3, D4, D5,
D6, P4, I5, G2, G4, W3, AL5, AN6, X2, X4, X6.

**Pending — the CLI target is the full catalog:** all 51 behavioural cases + the
5 structural probes (§3.10) are meant to run through CLI replay. The remaining 36
behavioural cases (and the probes) still need replay specs and a live
full-catalog run against the configured chat stack (roadmap §2b).
