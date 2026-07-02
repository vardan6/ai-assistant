# Gate 2 Failure Triage - 2026-07-01

## Scope

Fresh artifact reviewed: `gate2-replay-current.txt`.

Fresh result after dependency repair and the P5 inverter-count fix:

- 30 passed
- 14 failed
- 44 total

Confirmed stale failures from the older artifact:

- `P5` now passes.
- `W1` now passes.

This report classifies the remaining failing Gate 2 cases into:

- **real behavior issue** - current assistant/tool behavior is wrong or incomplete.
- **matcher/messaging issue** - behavior is acceptable, but replay expects a brittle phrase or overly narrow text.
- **mixed** - answer contains some correct data but still needs either tool support or more reliable messaging.

## Summary

| Case | Classification | Short Reason |
|---|---|---|
| `I4` | real behavior issue | Query used status-only filtering and missed the silent fault inverter. |
| `G3` | real behavior issue | `generation_readings` does not support windowed AC-power aggregation. |
| `G5` | real behavior issue | Same tool gap: no windowed fleet peak AC-power reducer. |
| `G6` | real behavior issue | Night performance ratio should be treated as undefined, not computed from available daytime/current values. |
| `AL4` | real behavior issue | Downtime sum was computed from incomplete visible records instead of full matched resolved alerts. |
| `AL6` | matcher/messaging issue | Refusal is semantically correct but misses expected phrase `no inputs`. |
| `M3` | real behavior issue | Maintenance cost is derivable, but classifier marked it out-of-scope. |
| `M4` | real behavior issue | Routed to alert MTTR instead of maintenance duration. |
| `AN4` | real behavior issue | Anomaly estimated power loss is derivable, but classifier marked it out-of-scope. |
| `AN7` | mixed | Finds the linked anomaly/ticket IDs but lacks confident filter/count support. |
| `X1` | real behavior issue | Replay flags intent only, but answer also includes wrong fleet totals in a plant summary. |
| `X3` | real behavior issue | Resolved the fault inverter, then used wildcard child lookups and falsely reported no linked records. |
| `X5` | matcher/messaging issue | Correctly refuses forecast, but expected text requires `historical`. |
| `X7` | matcher/messaging issue | Correctly reports no matching plant, but expected text requires `no such plant`. |

## Detailed Findings

### I4 - Silent Inverters

Question: `Which inverters are silently not reporting (offline by data, not just status)?`

Expected:

- Text includes `silent`.
- Number includes `16`.

Observed:

- Answer says 15 silent inverters.
- Tool call was `inverters(status="offline")`.
- Tool result: `matched=15`, `silent_count=15`.

Why this fails:

- The oracle expects silent-by-generation, not just `status=offline`.
- Calling `inverters` without a status filter returns `silent_count=16`.
- The missing inverter is the fault inverter `INV_4135001_10`, which is not `offline` by status but is silent by generation.

Recommended fix:

- Add a deterministic route or tool parameter for silent-by-generation lookups, or prevent the model from satisfying """silent/not reporting""" by applying `status=offline`.
- A direct tool option such as `silent_by_generation=true` would make this robust.

### G3 - Average AC Power Last 7 Days

Question: `Average AC power for INV_4135001_01 last 7 days.`

Expected:

- Text includes `INV_4135001_01`.
- Number includes `593.10`.

Observed:

- Assistant refused because the tool call failed.
- Tool call attempted `generation_readings(inverter="INV_4135001_01", window="last_week", aggregate_by="inverter", limit=20)`.
- Tool result: `TypeError: generation_summary() got an unexpected keyword argument 'window'`.

Why this fails:

- The current `generation_readings` tool schema only supports `plant`, `inverter`, `status_flag`, and `limit`.
- The oracle requires a windowed mean of `ac_power` over `2026-06-16..2026-06-22`.

Recommended fix:

- Add windowed AC-power aggregation support to a deterministic metric tool.
- Required reducer: mean `ac_power`, filter by inverter, filter by anchored `last_week`.

### G5 - Fleet Peak AC Power This Month

Question: `What was the peak AC power across the fleet this month?`

Expected:

- Text includes `INV_4135001_03`.
- Number includes `2505.92`.

Observed:

- Assistant refused because `generation_readings` calls failed.
- Attempted unsupported args: `window`, `aggregate_by`.
- A fallback call also attempted unsupported `aggregate_by`.

Why this fails:

- Same core tool gap as `G3`.
- The oracle requires max `ac_power` over anchored month-to-date, plus the row identity:
  - inverter `INV_4135001_03`
  - plant `Rajasthan Solar Park`
  - timestamp `2026-06-18 13:00:00`
  - value `2505.92`

Recommended fix:

- Add a deterministic generation metric supporting `window=this_month`, `aggregate_by=overall`, and reducer `max_ac_power`.

### G6 - Performance Ratio At Night

Question: `Average performance ratio at night.`

Expected:

- Text includes `undefined`.

Observed:

- Assistant called `performance_ratio(window="today", aggregate_by="plant")`.
- Answer returned current/today plant PR values:
  - Gujarat `0.94895`
  - Rajasthan `0.903555...`

Why this fails:

- The test expects a semantic refusal/qualification: performance ratio at night is undefined because solar expected/actual values are zero or PR is null.
- The model interpreted """night""" loosely and used a normal current/today PR window.

Recommended fix:

- Add a guard for """night performance ratio""" questions.
- Either return a deterministic refusal explaining that PR is undefined at night, or make `performance_ratio` expose a night-window empty/undefined result when the query asks for night.

### AL4 - Total Downtime From Resolved Alerts

Question: `What is the total downtime caused by resolved alerts?`

Expected:

- Number includes `31836`.

Observed:

- Answer says `22,885 minutes`.
- Tool call was `alerts(status="resolved")`.
- Tool result had `matched=25`, but answer appears to have summed incomplete/truncated visible records.

Why this fails:

- CSV/oracle sum of `downtime_minutes` across all resolved alerts is `31836`.
- `alerts` returns records but no precomputed `total_downtime_minutes`.
- Synthesis should not be responsible for summing a potentially truncated record list.

Recommended fix:

- Add aggregate fields to `alerts` for matched results:
  - `total_downtime_minutes`
  - optionally `downtime_record_count`
- Then guide synthesis to use the aggregate field instead of summing records.

### AL6 - MTTR For Open Alerts

Question: `What is the MTTR for open alerts?`

Expected:

- Text includes `no inputs`.
- Text includes `resolved_at`.

Observed:

- Answer correctly refuses the computation.
- It explains MTTR uses `resolved_at - created_at` and open alerts have no `resolved_at`.
- It does not contain the exact phrase `no inputs`.

Why this fails:

- This is a phrase-matching failure, not a substantive behavior failure.

Recommended fix:

- Either relax the replay check to accept equivalent wording, or standardize the refusal to include: `no inputs because open alerts have no resolved_at`.

### M3 - Maintenance Cost On Done Tickets

Question: `Total maintenance cost on done tickets.`

Expected:

- Number includes `41715`.
- Stop reason `final_answer`.

Observed:

- Classifier produced `metric="maintenance_cost"` and `out_of_scope=true`.
- Pipeline returned generic out-of-scope refusal.

Why this fails:

- The requested value is derivable from `maintenance.cost_usd`.
- Correct reducer: filter `maintenance.status=done`, sum `cost_usd`.

Recommended fix:

- Prevent `maintenance_cost` from being classified as out-of-scope.
- Add deterministic maintenance aggregate support for sum `cost_usd` over matched tickets.

### M4 - Average Duration Of Completed Maintenance

Question: `Average duration of completed maintenance.`

Expected:

- Number includes `4.93`.
- Number includes `12`.

Observed:

- Assistant answered alert MTTR:
  - `22.16 hours`
  - `25 resolved alerts`
- Tool call was `mttr(window="all_time", aggregate_by="overall")`.

Why this fails:

- The question is about maintenance tickets, not alert resolution.
- Correct source is `maintenance.duration_hours`.
- Correct reducer: mean non-null duration for completed/done maintenance tickets.
- Oracle expects:
  - `mean_duration_hours=4.93`
  - `completed_tickets=12`

Recommended fix:

- Route maintenance-duration questions to maintenance data, not `mttr`.
- Add maintenance aggregate fields for:
  - `mean_duration_hours`
  - `completed_tickets`

### AN4 - Total Estimated Power Loss From Open Anomalies

Question: `Total estimated power loss from open anomalies.`

Expected:

- Number includes `1421.42`.
- Stop reason `final_answer`.

Observed:

- Classifier produced `metric="power_loss"` and `out_of_scope=true`.
- Pipeline returned generic out-of-scope refusal.

Why this fails:

- The requested metric is directly present as `anomalies.estimated_power_loss_kw`.
- Correct reducer: filter `anomalies.status=open`, sum `estimated_power_loss_kw`.

Recommended fix:

- Prevent anomaly `power_loss` from being marked out-of-scope.
- Add deterministic anomaly aggregate field such as `total_estimated_power_loss_kw`.

### AN7 - Anomalies Linked To Maintenance Tickets

Question: `Which anomalies are linked to a maintenance ticket?`

Expected:

- Count `2`.
- Anomaly IDs `1`, `4`.
- Maintenance ticket IDs `6`, `5`.

Observed:

- Answer identifies:
  - Anomaly `1`, maintenance ticket `6`
  - Anomaly `4`, maintenance ticket `5`
- Answer does not include the count `2`.
- Answer hedges because the tool cannot filter by `maintenance_ticket_id`.

Why this partially fails:

- The substantive records are present in the answer.
- The missing count causes replay failure.
- The model""�s uncertainty is reasonable because the tool schema lacks an explicit `maintenance_ticket_id not null` filter.

Recommended fix:

- Add anomaly filter support for `linked_to_maintenance=true` or `maintenance_ticket_id_present=true`.
- Return deterministic aggregate fields:
  - `matched=2`
  - `anomaly_ids=[1,4]`
  - `maintenance_ticket_ids=[6,5]`

### X1 - Full Health Summary Of Gujarat

Question: `Give me a full health summary of the Gujarat plant.`

Expected:

- Intent includes at least `A`, `B`, and `C`.
- Text includes `gujarat`.
- Numbers include `5`, `3`, `0`, `1`, `8`, `3`.

Observed replay failure:

- Only intent failed: actual intent was `["A"]`.

Deeper behavior issue:

- The answer includes some correct Gujarat plant facts:
  - plant status `maintenance`
  - capacity `18.5 MW`
  - inverters configured `8`
  - inverter status `5 online`, `3 offline`
  - silent inverters `3`
- But it also reports fleet totals inside a Gujarat plant summary:
  - `Total alerts: 29`, while the Gujarat-filtered alerts tool result had `matched=10`.
  - `Total tickets: 19`, while the Gujarat-filtered maintenance tool result had `matched=8`.
- It did not bind or call anomaly/metric tools because intent only classified as Type A.

Why this fails:

- The replay only catches the missing `B` and `C` intent tags, but the answer itself contains wrong summary values due to using `total_alerts` and `total_tickets` fleet fields as if they were plant-local matched counts.

Recommended fix:

- Backfill or classify """full health summary""" as `A+B+C`.
- Include anomalies and key performance/generation context for health summaries.
- In synthesis guidance or deterministic post-processing, prefer `matched` for filtered tool calls; never label `total_*` fleet fields as plant totals.

### X3 - Fault Inverter Alert And Anomalies

Question: `For the inverter in fault, what alert and anomalies does it have?`

Expected:

- Text includes `INV_4135001_10`.
- Alert IDs: `2`, `16`, `27`.
- Anomaly IDs: `4`, `17`, `54`.

Observed:

- Assistant correctly resolved the fault inverter as `INV_4135001_10`.
- Then it called:
  - `alerts(inverter="*", status="*")`
  - `anomalies(inverter="*", status="*")`
- Those wildcard strings were treated as exact values, so both child lookups returned zero.
- Answer falsely said there were no linked alerts or anomalies.

Ground truth from exact calls:

- `alerts(inverter="INV_4135001_10")` returns:
  - alert `2`, open, major, `inverter_fault`
  - alert `16`, resolved, minor, `communication_loss`
  - alert `27`, resolved, critical, `inverter_fault`
- `anomalies(inverter="INV_4135001_10")` returns:
  - anomaly `4`, scheduled repair, `string disconnection`
  - anomaly `17`, scheduled repair, `tracker issue`
  - anomaly `54`, resolved, `string disconnection`

Why this fails:

- This is a child-to-sibling chaining failure. The model found the parent entity but did not pass the resolved inverter ID to the sibling tools.

Recommended fix:

- Add deterministic chaining or guidance: when a prior tool resolves exactly one inverter, subsequent related alert/anomaly/maintenance calls must use that inverter ID.
- Optionally reject literal wildcard args in `filter_exact` or tool validation, because `*` currently means """exact string star,""" not """all""".

### X5 - Forecast Next Week

Question: `Forecast next week's generation for Rajasthan.`

Expected:

- Stop reason `out_of_scope`.
- Text includes `can't answer`.
- Text includes `historical`.

Observed:

- Stop reason is `out_of_scope`.
- Answer correctly says the dataset cannot support the forecast.
- It does not include the word `historical`.

Why this fails:

- This is a matcher/messaging issue. The behavior is acceptable for a negative forecast case.

Recommended fix:

- Prefer relaxing the replay check to accept semantic forecast/data-limitation refusal.
- If exact text is easier, standardize the out-of-scope reply for forecast queries to mention that only historical/observed records are available.

### X7 - Unknown Plant

Question: `What's the status of plant 9999?`

Expected:

- Text includes `no such plant`.

Observed:

- Tool call was `plants(plant="9999")`.
- Tool result had `matched=0`.
- Answer says plant `9999` has zero matching plants and is not present.

Why this fails:

- This is a matcher/messaging issue. The behavior is correct and clear.
- Replay expects one specific phrase.

Recommended fix:

- Prefer relaxing the check to accept `0 matching plants`, `not present`, or equivalent.
- Alternatively standardize no-match plant responses to include the phrase `no such plant`.

## Recommended Fix Order

1. Add deterministic aggregates to tools instead of relying on synthesis arithmetic:
   - generation AC mean/max by window
   - alert downtime sum
   - maintenance cost and duration
   - anomaly power-loss sum and linked-maintenance filtering
2. Fix routing/backfill:
   - `maintenance_cost` is in scope
   - anomaly `power_loss` is in scope
   - """full health summary""" should be `A+B+C`
   - """silent/not reporting""" should not become status-only `offline`
3. Fix child-to-sibling chaining:
   - after resolving one inverter, pass that exact ID to alerts/anomalies/maintenance lookups
   - avoid literal wildcard tool args
4. Update replay text checks for negative cases:
   - `X5`: accept semantic forecast refusal, or require standardized `historical` wording
   - `X7`: accept semantic no-match response, or require standardized `no such plant` wording
   - `AL6`: accept equivalent MTTR-open refusal, or require standardized `no inputs` wording

## Must-Fix vs Matcher-Only

Must fix before considering Gate 2 behavior clean:

- `I4`
- `G3`
- `G5`
- `G6`
- `AL4`
- `M3`
- `M4`
- `AN4`
- `AN7`
- `X1`
- `X3`

Can be addressed by replay matcher or standardized wording:

- `AL6`
- `X5`
- `X7`

---

# Code-Grounded Review Addendum - 2026-07-01

Every claim below was cross-checked against the current implementation
(`app/tools/*.py`, `app/ai/derived_metrics.py`, `app/ai/intent_schema.py`,
`app/ai/intent_prompt.py`, `app/tools/common.py`). This section records the
review verdict: which fixes we **want** (real bugs that generalize and fit the
existing architecture), which we **do not want** as behavior changes
(matcher-only / eval-overfit), and why.

## Verdict table

| Case | Doc classification | Code-checked verdict | Want the fix? |
|---|---|---|---|
| `I4` | real | Real — confirmed | Want |
| `G3` | real | Real (tool gap + unhandled `TypeError`) | Want |
| `G5` | real | Real (same gap as G3) | Want |
| `G6` | real | Real semantics, brittle proposed fix | Want core, not the keyword guard |
| `AL4` | real | Real — confirmed | Want |
| `AL6` | matcher | Matcher only — confirmed | Don't change behavior; fix matcher |
| `M3` | real | Real (classifier + tool gap) | Want |
| `M4` | real | Real (routing + tool gap) | Want |
| `AN4` | real | Real (classifier + tool gap) | Want |
| `AN7` | mixed | Real, small | Want |
| `X1` | real | Real — and worse than doc says | Want (esp. tool-naming bug) |
| `X3` | real | Real — confirmed in `common.py` | Want |
| `X5` | matcher | Matcher only — confirmed | Don't change behavior; fix matcher |
| `X7` | matcher | Matcher only — confirmed | Don't change behavior; fix matcher |

## Architectural anchor

The codebase already has the correct pattern: deterministic metric tools in
`app/ai/derived_metrics.py` (`mttr`, `performance_ratio`, `total_yield`,
`daily_yield`) plus aggregate fields on entity tools (`matched`,
`status_counts`, `silent_count`). Every "want" fix below extends that pattern
rather than inventing a new one — that is why they are low-risk.

## Fixes we WANT (real bugs)

### I4 — silent inverters (16 vs 15)
`app/tools/inverters.py:43` computes `silent = frame[frame["is_silent_by_generation"]]`
*after* `filter_exact(frame, "status", status)` (line 42). With `status="offline"`,
silence is counted only inside the offline subset → 15, dropping the
silent-but-not-offline fault inverter `INV_4135001_10`.
- Fix: add explicit `silent_by_generation: bool` parameter that filters on the
  flag directly; tighten the tool description so "silently not reporting" maps to
  the flag, not `status=offline`. Optionally compute `silent_count` on the
  pre-status frame so an unrelated status filter never narrows it.

### G3 / G5 — windowed AC-power mean/max
Confirmed gap: `app/tools/generation_readings.py:23-32` accepts only
`plant/inverter/status_flag/limit`, and `derived_metrics.py` has no `ac_power`
reducer. The model invents `window`/`aggregate_by`, which reach
`generation_summary()` as unexpected kwargs → raw `TypeError` → refusal.
- Fix: add an `ac_power` metric to `derived_metrics.py` (mean and max over a
  dataset-anchored window; `aggregate_by` overall/plant/inverter), mirroring the
  existing metrics.
- Independent hardening: tool dispatch should reject unknown args gracefully
  instead of surfacing a raw `TypeError` as a user-facing refusal. This bug
  recurs on any unknown kwarg regardless of the new metric.

### AL4 — downtime sum (31836 vs 22885)
`app/tools/alerts.py` returns full records and `matched` but no downtime
aggregate, so synthesis sums records by hand — unreliable, especially under
context-budget truncation of the record list.
- Fix: add `total_downtime_minutes` (and `downtime_record_count`) to the alerts
  payload, alongside the existing `status_counts`/`severity_counts`.

### M3 / AN4 — derivable metrics marked out-of-scope
Two root causes: (1) `app/ai/intent_prompt.py:17` enumerates derivable metrics
but omits `cost`, `power_loss`, `duration`; (2) `intent_prompt.py:18` defines
out-of-scope only by example. So the LLM concludes maintenance cost / anomaly
power loss are not computable, even though `maintenance.cost_usd`
(`app/tools/maintenance.py:22`) and `anomalies.estimated_power_loss_kw`
(`app/tools/anomalies.py:24`) exist.
- Fix (a): add aggregates — `maintenance` sum `cost_usd`; `anomalies` sum
  `estimated_power_loss_kw`.
- Fix (b): extend the classifier prompt's metric enumeration to name these as
  in-scope. Both parts required.

### M4 — maintenance duration routed to alert MTTR
The model picked `mttr` (which reads the `alerts` table, `derived_metrics.py:192`)
for "average duration of completed maintenance," whose real source is
`maintenance.duration_hours`. No maintenance metric tool exists.
- Fix: the same new maintenance aggregate — add `mean_duration_hours` +
  `completed_tickets`; nudge routing so "maintenance duration" ≠ "alert MTTR".
  M3 and M4 collapse into one maintenance-aggregate capability.

### AN7 — anomalies linked to a maintenance ticket (missing count)
`app/tools/anomalies.py` already returns `matched` and `anomaly_ids`, but cannot
filter on "has a maintenance_ticket_id." The model found the rows but hedged and
dropped the count.
- Fix: add a `linked_to_maintenance: bool` filter. `matched=2` and
  `anomaly_ids=[1,4]` then fall out of existing aggregate fields for free.

### X3 — literal `"*"` wildcard
Confirmed in `app/tools/common.py:90-94`: `filter_exact` lowercases the value and
does exact equality, so `inverter="*"` matches the literal string `*` → zero rows
→ the assistant falsely reports "no linked records."
- Fix: in `filter_exact`, treat `"*"`/`"all"`/empty as "no filter" (return frame
  unfiltered). Deterministic guard protecting every entity tool. Child-to-sibling
  chaining ("pass the resolved inverter id") is a softer guidance fix on top.

### X1 — Gujarat health summary (worse than doc frames it)
Two distinct problems:
- (b) Wrong totals — the real correctness bug. `app/tools/alerts.py:59` and
  `app/tools/maintenance.py:53` expose `total_alerts` / `total_tickets`
  (fleet-wide, `len(source)`) as siblings of `matched` (plant-filtered). The
  misleading field name is the trap; the model read the fleet field as the plant
  total. Fix: stop emitting `total_*` next to `matched` when a filter is applied
  (or rename to `total_alerts_all_plants`). Tool-design fix, not a synthesis
  caution.
- (a) Intent only `A`. Classifying "full health summary" as `A+B+C` is reasonable
  but more eval-shaped; lower priority than (b).

## Fixes we DO NOT want as behavior changes (matcher-only)

The assistant is already correct in these; the only failure is a brittle
exact-phrase oracle. Editing the assistant to emit a magic phrase overfits the
eval, makes the model more scripted, and regresses silently.

- `AL6` — correctly refuses MTTR for open alerts and explains `resolved_at` is
  missing; fails only on the literal `no inputs`.
- `X5` — correctly returns `out_of_scope` for a forecast; fails only on the
  literal `historical`.
- `X7` — correctly reports `matched=0` for plant 9999; fails only on the literal
  `no such plant`.

Recommendation: relax these replay checks to accept semantic equivalents rather
than mutating the assistant's wording. If exact strings must stay, standardize
them once in the refusal templates — but prefer the matcher change.

## Borderline — want the substance, not the mechanism

- `G6` (PR at night = undefined). Semantics are real: with no irradiance there is
  no valid PR, and `performance_ratio_metric` already filters
  `performance_ratio.notna()` (`derived_metrics.py:116`), so a genuine night
  window yields an empty result. The doc's proposed hardcoded `"night"` keyword
  guard is brittle/narrow. Prefer: when the chosen window has zero non-null PR
  readings, return an explicit `undefined`/empty verdict and let synthesis
  surface "undefined" — instead of pattern-matching the word "night."

## Cross-cutting caution

The doc's lead recommendation — "add deterministic aggregates instead of
synthesis arithmetic" — is correct and matches `derived_metrics.py`. Risk to
watch: do not add one bespoke reducer per failing oracle case (that overfits the
eval). Prefer a small set of general, composable aggregates so the same additions
answer questions the eval did not ask. The consolidated plan below does this — 14
failures collapse into ~7 real changes plus 3 matcher relaxations.

## Consolidated change set

1. **Maintenance aggregate** (new metric in `derived_metrics.py`): sum `cost_usd`,
   `mean_duration_hours`, `completed_tickets`. Fixes M3 + M4.
2. **Anomaly aggregates/filters** (`tools/anomalies.py`): sum
   `estimated_power_loss_kw`; `linked_to_maintenance` filter. Fixes AN4 + AN7.
3. **AC-power metric** (new metric in `derived_metrics.py`): mean + max over
   window, aggregate overall/plant/inverter. Fixes G3 + G5.
4. **Alerts downtime aggregate** (`tools/alerts.py`): `total_downtime_minutes`,
   `downtime_record_count`. Fixes AL4.
5. **Silent-inverter filter** (`tools/inverters.py`): `silent_by_generation`
   param + description; robust `silent_count`. Fixes I4.
6. **`filter_exact` wildcard guard** (`tools/common.py`): treat `*`/`all`/empty
   as no filter. Fixes X3 (protects all tools).
7. **Fleet-vs-matched field hygiene** (`tools/alerts.py`, `tools/maintenance.py`):
   don't expose `total_*` as a sibling of `matched` under a filter. Fixes X1(b).
8. **Classifier scope/metric enumeration** (`ai/intent_prompt.py`,
   `ai/intent_schema.py`): add `maintenance_cost`, `maintenance_duration`,
   `power_loss`, `ac_power` as in-scope metrics; route maintenance-duration away
   from MTTR; classify "full health summary" as `A+B+C`. Fixes M3/M4/AN4/X1(a)
   classification halves.
9. **Dispatch hardening**: unknown tool kwargs return a structured tool error,
   not a raw `TypeError`. Supports G3/G5 robustness.
10. **Matcher relaxation** (`app/case_replay.py` / oracle): accept semantic
    equivalents for `AL6`, `X5`, `X7`. No assistant behavior change.
11. **PR-undefined verdict** (`derived_metrics.py`): explicit `undefined`/empty
    result when a window has zero non-null PR readings. Fixes G6 without a
    keyword guard.
