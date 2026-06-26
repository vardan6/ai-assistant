# Solar Operations AI Assistant

Conversational assistant over a solar-plant operations dataset (7 CSVs). The graded
deliverable is the **orchestration pipeline**: explicit intent classification →
tool selection → in-code aggregation → refusal-guarded synthesis.

> Design lives in `docs/design/`, requirements in `docs/requirements/`, and
> decisions in `docs/adr/`.

## Phase 0 — what works now

- `DataSource` interface + `PandasDataSource` loading the 7 CSVs once; `dataset_today`
  anchored to the dataset's latest timestamp (~2026-06-22), not wall-clock.
- One `plants` tool under a uniform `ToolRegistry` (returns structured dicts).
- Explicit, logged intent classification (smalltalk fast-path + LLM→JSON A/B/C schema).
- A bare iterative tool-calling loop, wired end to end in a CLI.

## Run

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Configure a provider (one of):
export OPENAI_API_KEY=sk-...            # uses the pre-seeded OpenAI provider, or
# run Ollama locally (pre-seeded at http://localhost:11434)

./run-web-server.sh
.venv/bin/python -m app.cli
```

Provider config lives in `config/common.example.json`; copy to
`config/common.local.json` (gitignored) for local overrides. Tool-calling needs a
tool-capable model — the default `llama3` is weak at tools; `qwen3.5` / `gpt-oss` work.

## Test

```bash
python -m pytest -q        # 15 offline tests (no LLM/network needed)
```
