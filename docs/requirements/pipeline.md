# Requirements — conversational AI assistant pipeline

> Finished behavior, constraints, acceptance criteria, and non-goals.

## Product picture

A conversational assistant that answers natural-language questions about a solar-plant
operations dataset (7 CSVs, 3 plants → 30 inverters → readings/alerts/maintenance/anomalies).
The graded deliverable is the **orchestration pipeline**, not the UI. This repo is also
intended to be a **reusable, presentable template** for future AI-agent projects, so design
choices must stay clean and unsurprising in a walkthrough.

## Question types the assistant must handle

- **Type A — current state:** snapshot/status questions (which plants offline, inverters in
  fault, open critical alerts, in-progress maintenance).
- **Type B — statistics & trends:** multi-row aggregation/comparison over generation & weather
  (avg daily yield, performance ratio ranking, mean-time-to-resolve).
- **Type C — anomaly lookup:** filter the anomaly log by type/cause/status/inverter; may join to
  inverters/plants for context.
- A question may be a **multi-type combination**.

## Pipeline requirements (graded)

1. **Explicit intent classification** — classify into A/B/C (or combination) *before* querying
   data. Must be explicit and inspectable (visible in output/logs), not silently inferred inside
   one prompt.
2. **Tool/function design** — each logical data source is an independently callable, testable tool
   returning **structured data, not prose**. The orchestrator **must not load all seven tables on
   every question** — it selects tools based on classified intent.
3. **Multi-step planning** — support at least one 2-step chain (e.g. resolve `plant_id` from
   `plants`, then filter `anomalies`).
4. **Aggregation in code** — counts/sums/averages/correlations computed in code (pandas), never by
   asking the LLM to read raw CSV text. **No raw CSV rows in the final LLM prompt.**
5. **Graceful degradation** — on ambiguous or unanswerable questions, say so clearly; never
   hallucinate a number. (Demo Q6 "revenue lost from downtime" is intentionally unanswerable.)

## Coverage principle — the spec is a floor, not a ceiling

The task's three intent types (A/B/C) and its suggested questions are the
**minimum** the assistant must satisfy, not the boundary of the design. A more
universal, reliable mechanism that subsumes a narrow spec ask is **preferred and
counts as satisfied** — we are not constrained to mirror the A/B/C shape if our
agent loop already covers those cases more generally and more dependably.

The obligation is asymmetric:

- Every concrete phrase/question/requirement in `solar_interview_task.md` **must
  be covered** — verified to produce a correct result, or to refuse correctly.
- *How* it is covered may be broader than the spec. If a wider implementation
  serves a narrow requirement, that requirement is **met by superset** — treated
  as done/better, not as a gap.
- If our behavior deviates from the literal spec wording, the deviation must be
  **justified as an improvement** (more universal, more reliable, broader
  coverage) — never as a shortfall.

This drives the status vocabulary the test plan uses to report each spec item:

| Status | Meaning |
|--------|---------|
| ✅ **Covered** | Works exactly as the spec asks; verified against the oracle. |
| ➕ **Met by superset** | A broader/more universal mechanism satisfies the narrow ask; verified. Counted as done/better. |
| 🟡 **Working** | Implemented but not yet verified end-to-end (e.g. awaiting a CLI run). |
| 🔧 **Needs work** | Known gap, defect, or unverified-and-suspect. |
| ⛔ **Refuse (by design)** | Spec item is intentionally unanswerable; correct behavior is a clean refusal. |

## Acceptance criteria

- Intent classification is logged/shown per question.
- Tools are unit-testable in isolation and return structured dicts.
- At least one demonstrated 2-step chain in the test questions.
- Aggregations verified against the dataset; no raw rows reach the model.
- At least one out-of-scope question yields an explicit refusal.

## Behavioral constraints

- **Date anchoring:** "today" / "last week" / "this month" anchor to the **dataset's max
  timestamp** (~2026-06-22), NOT wall-clock time. The CSVs are the full dataset.
- Agent operates in a single mode (**agent mode only**; no separate chat mode).
- Greetings/smalltalk short-circuit before the LLM/tools (fast-path).

## Dataset configuration behavior

- The app exposes dataset selection in Settings through the same shared JSON config used by
  Config I/O.
- Dataset configuration uses a base directory (`data.csv_dir`) plus optional per-table file
  overrides (`data.csv_files`) for the 7 canonical CSVs. A blank override means
  `<csv_dir>/<canonical_name>.csv`.
- The Settings UI must show backend/server paths, not browser-local paths, and must show the
  effective resolved path for each canonical table.
- Dataset changes apply only on explicit actions (`Save Paths`, `Reload Current Dataset`,
  `Reset to Defaults`, per-table upload, bulk zip import), never on field edit.
- Saving or upload/import activation must validate the full resolved 7-file dataset before the
  runtime switches over. On failure, the current active dataset remains in use and the persisted
  config remains unchanged.
- The app manages exactly one active dataset configuration at a time.
- Uploads are optional convenience flows layered onto the same config model:
  per-table CSV upload and bulk `.zip` import. Uploaded files become managed backend files whose
  stored paths are written back into dataset config.
- Config export/import includes dataset settings as paths/config only; it does not embed dataset
  file contents.

## Non-goals

- No RAG / retrieval / embeddings (confirmed out of scope for this task).
- No production UI polish required by the spec (but see template goals — we build a real Web UI
  + CLI anyway for demo and template value).
- No streaming requirement from the spec, auth, multi-user, real-time feeds, or model training.
</content>
</invoke>
