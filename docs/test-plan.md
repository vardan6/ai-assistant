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
> the spec's A/B/C examples. Still owed: pinning every **[oracle⁺]** value,
> fixtures, harness, and pass/fail criteria (§3.12). Open `[TODO]`s in §1.10.

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
- Section 2 (to follow) will attach concrete expected values to A/B/C rows and
  the R-obligations, drawing on `golden-answers.md` and the Type-A snapshot /
  measure-semantics tables in `dataset-analysis.md`.

### 1.7 Evaluation criteria (task §"Evaluation criteria")

The five-row rubric the task grades against. Each criterion is mapped to the
test IDs that should prove it. Where we don't yet have the means to assert a
criterion, it is marked **[TODO — not yet in the plan]** rather than left
implied.

| Criterion | What the task looks for | Proven by | Status |
|-----------|-------------------------|-----------|--------|
| Pipeline structure | Intent classification separate from data fetching and from LLM synthesis; stages composable. | R1, R2 | **[TODO]** No test yet asserts stage separation/composability as such — needs an architecture-level assertion, not just per-question checks. |
| Tool design | Tools narrowly scoped, testable in isolation, return structured data (not prose). | R2 | **[TODO]** Per-tool isolation tests + a "returns structured data, not prose" assertion not yet specified. |
| Aggregation correctness | Numbers computed in code, not estimated by the LLM. | B1, B2, B3, D2, D4, R4 | Partly covered — values come from `golden-answers.md`; the "no raw CSV rows in final prompt" check (R4) still needs a concrete assertion mechanism. **[TODO on R4 mechanism]** |
| Multi-step reasoning | Orchestrator chains tool calls where one output informs the next. | R3, D1, D2, D5, C3 | Covered by the chain cases; explicit "output-of-one-feeds-next" trace assertion **[TODO]**. |
| Failure handling | Degrades gracefully on ambiguous or unanswerable questions. | R5, D6 | D6 (unanswerable) covered by oracle Q6; **ambiguous** (as distinct from unanswerable) has no test case yet **[TODO]**. |

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

### 1.10 Open items / still to work on

Consolidated list of everything flagged above that the plan does not yet answer:

- **[TODO]** Section 2: concrete expected values for A1–A3, B1–B3, C1–C3 and the
  R-obligations.
- **[TODO]** Assertion for "pipeline structure" — stage separation /
  composability (R1, R2 / rubric row 1).
- **[TODO]** Per-tool isolation tests and a "structured data, not prose"
  assertion (R2 / rubric row 2).
- **[TODO]** Concrete mechanism to verify "no raw CSV rows in the final LLM
  prompt" (R4 / rubric row 3).
- **[TODO]** Explicit trace assertion that one tool's output feeds the next in a
  chain (R3 / rubric row 4).
- **[TODO]** An **ambiguous** (not merely unanswerable) test case for graceful
  degradation (R5 / rubric row 5).
- **[TODO]** Section 2+: fixtures, test harness, and pass/fail criteria.

---

## 2. Spec traceability — every task item, with status

> Goal: see at a glance whether each obligation from `solar_interview_task.md` is
> covered, and by which case. **Coverage principle** (`docs/requirements/pipeline.md`):
> the spec is a *floor, not a ceiling* — a broader/more universal mechanism that
> subsumes a narrow ask counts as **met by superset (➕)**, not a gap. We never
> drop below the spec; we may rise above it, with justification.

**Status legend** — ✅ Covered (verified vs oracle) · ➕ Met by superset (broader
mechanism, verified) · 🟡 Working (implemented, not yet CLI-verified) · 🔧 Needs
work · ⛔ Refuse by design.

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
| Pipeline structure (stages separate/composable) | R1, R2, R4-probe | 🟡 | architecture-level assertion still owed (§1.7 TODO). |
| Tool design (narrow, isolated, structured) | R2-unit per surface | 🟡 | per-tool isolation tests owed. |
| Aggregation correctness | golden Q2/Q4 + B*/G* vs oracle | 🟡 | values from `golden-answers.md`; extend oracle for A/B/C. |
| Multi-step reasoning | D1/D2/D5/C3/AN6/X3 + trace assertion | 🟡 | "output-of-one-feeds-next" trace assertion owed. |
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
| P1 | Which plants are currently offline? | A | plants(status=offline) | [Tamil Nadu PV Plant] (1) | exact status |
| P2 | List all plants and their status. | A | plants(all) | Rajasthan=active, Gujarat=maintenance, Tamil Nadu=offline | — |
| P3 | What is the nameplate capacity of the Gujarat plant? | A+chain | resolve "Gujarat"→id → plants.capacity_mw | 18.5 MW | region≠state name resolution |
| P4 | Which plant has the highest feed-in tariff? | B(min) | plants rank tariff_usd_per_kwh | [oracle⁺] (max 0.052) | tiny table, still aggregate in code |
| P5 | How many inverters does Rajasthan have? | A+chain | resolve→id → inverters count | 10 | declared vs actual both = 10 |

### 3.3 Inverters (I) — Type A / status reconciliation

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| I1 | How many inverters are in fault right now? | A | inverters(status=`fault` exact) | **1** (INV_4135001_10) | `fault` is inside `inverter_fault`/`sensor_fault` — exact only |
| I2 | How many inverters are offline? | A | inverters(status=offline) | 15 | — |
| I3 | Which inverters at Tamil Nadu are not online? | A+chain | resolve→id → inverters(plant_id, status≠online) | all 12 offline | whole-plant outage |
| I4 | Which inverters are silently not reporting (offline by data, not just status)? | A (superset) | inverters ⨝ generation last_seen vs anchor | 16 silent (e.g. INV_4136001_06…) | **status field alone insufficient** — combine signals (cross-table reconciliation) |
| I5 | Show inverters that are "online" in status but have an open alert. | A+chain | inverters(status=online) ∥ alerts(status=open) join | [oracle⁺] | status disagreement surface |

### 3.4 Generation readings (G) — Type B / measure semantics

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| G1 | Avg daily yield per plant over last week. | B | daily_yield agg group_by plant, window last_week | Rajasthan 123354.2; others [oracle⁺] | per-inverter daily-max, not raw sum |
| G2 | Total energy generated by Rajasthan this month. | B+chain | resolve→id → total_yield diff over window | [oracle⁺] | `total_yield` = last−first, never sum/mean |
| G3 | Average AC power for INV_4135001_01 last 7 days. | B | generation(inverter, window) mean ac_power | [oracle⁺] | mean of spot kW; night zeros are legitimate |
| G4 | Which inverter has the highest performance ratio? | B | generation mean PR (nulls excluded) ranked | [oracle⁺] | exclude null PR (⟺ dc_voltage=0); don't zero-fill |
| G5 | What was the peak AC power across the fleet this month? | B | generation max ac_power, window | [oracle⁺] (≤2510 kW range) | max vs mean reducer |
| G6 | Average performance ratio at night. | B (degrade) | generation PR where dc_voltage=0 | ⛔/empty: PR undefined at night | the null-semantics trap surfaced as a question |

### 3.5 Weather (W) — Type A snapshot / Type B trend

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| W1 | What's the weather at Gujarat today? | A+chain | resolve→id → weather @ anchor | = D5 values | anchor day |
| W2 | Average irradiation at Rajasthan last week. | B+chain | resolve→id → weather mean irradiation, window | [oracle⁺] | mean over readings |
| W3 | Which plant had the highest cloud cover this month? | B | weather group_by plant, max/mean cloud_cover | [oracle⁺] (≤58.8%) | group + reduce in code |
| W4 | Was there any rainfall at Tamil Nadu this week? | A/B+chain | resolve→id → weather sum/any rainfall_mm | [oracle⁺] | int column; sum vs any |

### 3.6 Alerts (AL) — Type A state / Type B MTTR

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| AL1 | What open critical alerts exist? | A | alerts(status=open ∧ severity=critical) | includes alert `1` (Tamil Nadu); full count [oracle⁺] | open∧critical intersection |
| AL2 | How many alerts are currently open? | A | alerts(status=open) | 4 | — |
| AL3 | Show all alerts for Rajasthan. | A+chain | resolve→id → alerts(plant_id) | [oracle⁺] (plant has 10) | join on resolved id |
| AL4 | What is the total downtime caused by resolved alerts? | B | alerts(resolved) sum downtime_minutes | [oracle⁺] | downtime_minutes ⟺ not-open; open rows have none |
| AL5 | Mean time to resolve an alert (all severities). | B | alerts(resolved) MTTR | [oracle⁺] (critical subset=6.3h) | open alerts excluded by construction |
| AL6 | What is the MTTR for open alerts? | B (degrade) | — | ⛔/empty: open alerts have no resolved_at | lifecycle null is structural, not missing |

### 3.7 Maintenance (M) — Type A workflow

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| M1 | What maintenance is in progress? | A | maintenance(status=`in_progress`) | 4 | exact `in_progress` (underscore) |
| M2 | What maintenance is scheduled? | A | maintenance(status=`scheduled` exact) | 3 | `scheduled` ≠ `scheduled_repair` (that's anomalies) |
| M3 | Total maintenance cost on done tickets. | B | maintenance(status=done) sum cost_usd | [oracle⁺] | only completed have meaningful cost |
| M4 | Average duration of completed maintenance. | B | maintenance mean duration_hours | [oracle⁺] | duration null on scheduled — exclude |
| M5 | Which inverters at Gujarat have maintenance in progress? | A+chain | resolve→id → maintenance(plant_id, status=in_progress) | [oracle⁺] (Gujarat=3 in progress) | inverter_id sometimes null on maintenance |

### 3.8 Anomalies (AN) — Type C lookup

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| AN1 | Which inverters have open hotspot anomalies? | C | anomalies(type=`hotspot` exact ∧ status=open) | [oracle⁺] (hotspot total 16) | `hotspot` ≠ `multi hotspot` |
| AN2 | What anomalies are caused by soiling? | C | anomalies(cause=soiling) | 8 | — |
| AN3 | How many open anomalies are there fleet-wide? | C | anomalies(status=open) | 28 | — |
| AN4 | Total estimated power loss from open anomalies. | B/C | anomalies(status=open) sum estimated_power_loss_kw | [oracle⁺] | sum for fleet exposure, mean for typical |
| AN5 | List critical anomalies and their recommended action. | C | anomalies(severity=critical) | 18 rows, with recommended_action | — |
| AN6 | Summarise all unresolved anomalies for Rajasthan. | C+chain | resolve "Rajasthan"→`4135001` → anomalies(plant_id, status≠resolved) | open subset = 7 (snapshot); unresolved total [oracle⁺] | "unresolved" = open+monitoring+scheduled_repair, not just `open`; the task's named chain |
| AN7 | Which anomalies are linked to a maintenance ticket? | C | anomalies(maintenance_ticket_id not null) | ~2 (96% null) | mostly-null link column |

### 3.9 Cross-cutting / chains / degradation (X)

| ID | Question | Intent | Chain | Expected | Trap |
|----|----------|--------|-------|----------|------|
| X1 | Give me a full health summary of the Gujarat plant. | A+B+C+chain | resolve→id → (inverters status ∥ alerts open ∥ anomalies open ∥ maintenance in_progress ∥ weather) gather | Gujarat: 5/3/0 inv, 1 open alert, 8 open anomalies, 3 maint | **parallel fan-out** under one resolved parent |
| X2 | Compare Rajasthan and Tamil Nadu on open anomalies and yield. | B+C+chain | resolve both → (anomalies ∥ daily_yield) per plant, compare | Raj 7 / TN 13 open anomalies; yields [oracle⁺] | multi-entity parallel chain |
| X3 | For the inverter in fault, what alert and anomalies does it have? | A+C+chain | inverters(status=fault)→INV_4135001_10 → alerts ∥ anomalies | alert + anomalies for that inverter [oracle⁺] | **child→sibling** chain (resolve via status, not name) |
| X4 | Which plant is performing worst right now? | B (superset) | rank plants by PR / yield / open-issue load | [oracle⁺] | "worst" is underspecified → define metric, state it |
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

### 3.12 Still owed in later sections

- **[TODO]** Extend `scripts/golden_answers.py` to pin every **[oracle⁺]** value
  (A/B/C and X numerics) so the catalog flips from 🟡 to ✅/➕ on the CLI run.
- **[TODO]** Fixtures + harness + pass/fail criteria (replay each case through
  CLI mode, capture intent + tool chain + answer, diff against oracle).
- **[TODO]** Architecture-level assertions for rubric rows 1–2 (stage
  separation/composability; per-tool isolation) beyond the probe cases.
