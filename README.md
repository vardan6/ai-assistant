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
```

Provider config lives in `config/common.example.json`; copy to
`config/common.local.json` (gitignored) for local overrides. Tool-calling needs a
tool-capable model — the default `llama3` is weak at tools; `qwen3.5` / `gpt-oss` work.

## CLI

The CLI talks to the FastAPI server. Start the server first:

```bash
./run-web-server.sh
```

### Interactive mode

Open an interactive chat session:

```bash
.venv/bin/python -m app.cli
./run-cli.sh
```

Inside the prompt:

- type a question and press Enter
- type `/bind_all <question>` to force bind-all tool mode for one request
- type `/gated <question>` to force gated tool mode for one request
- type `exit` or `quit` to leave

### One-shot mode

Send a single prompt and print the answer as one terminal command:

```bash
./run-cli.sh --prompt "Which plants are offline today?"
./run-cli.sh "List inverter issues for today."
```

In one-shot mode:

- the assistant answer is printed to `stdout`
- session information and usage diagnostics are printed to `stderr`
- a new chat session is created automatically unless `--session-id` is provided

### Examples

Create a new session and ask one question:

```bash
./run-cli.sh --prompt "Which plants are offline today?"
```

Continue an existing session:

```bash
./run-cli.sh --session-id <session-id> "Continue from the previous answer."
```

Use bind-all mode for one request:

```bash
./run-cli.sh --gating-mode bind_all --prompt "Summarize current alerts and anomalies."
```

Set a title for a newly created session:

```bash
./run-cli.sh --title "Morning checks" --prompt "Give me today's plant status."
```

Target a different server URL:

```bash
./run-cli.sh --server http://127.0.0.1:9010 --prompt "Which plants are offline?"
```

Suppress diagnostics in one-shot mode:

```bash
./run-cli.sh --no-stats --prompt "Which plants are offline today?"
```

### Options

`./run-cli.sh` forwards arguments to `python -m app.cli`.

- `PROMPT` — positional prompt text for one-shot mode
- `--prompt TEXT` — prompt text for one-shot mode
- `--session-id ID` — reuse an existing chat session instead of creating a new one
- `--title TEXT` — title for a newly created session; default is `CLI chat`
- `--gating-mode {gated,bind_all}` — default tool binding mode for the request; default is `gated`
- `--server URL` — override the configured server base URL
- `--no-stats` — suppress trace and usage footer output in one-shot mode

Do not pass both a positional prompt and `--prompt` in the same command.

## Test

```bash
python -m pytest -q        # 15 offline tests (no LLM/network needed)
```
