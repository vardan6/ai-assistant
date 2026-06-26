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

## Non-goals

- No RAG / retrieval / embeddings (confirmed out of scope for this task).
- No production UI polish required by the spec (but see template goals — we build a real Web UI
  + CLI anyway for demo and template value).
- No streaming requirement from the spec, auth, multi-user, real-time feeds, or model training.
</content>
</invoke>
