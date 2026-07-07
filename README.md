# Solar Operations AI Assistant

Conversational assistant over a solar-plant operations dataset (7 CSVs). The graded
deliverable is the **orchestration pipeline**: explicit intent classification →
tool selection → in-code aggregation → refusal-guarded synthesis.

> Design lives in `docs/design/`, requirements in `docs/requirements/`, and
> decisions in `docs/adr/`.

## Current implementation

- `DataSource` interface + `PandasDataSource` loading the 7 CSVs once; dataset-relative
  time anchored to the dataset's latest timestamp (~2026-06-22), not wall-clock.
- A uniform `ToolRegistry` with the per-surface dataset tools plus derived/tooling support
  used by the replay harness and synthesis pipeline.
- Explicit, logged turn routing and intent classification, with graph-state scaffolding for
  the committed LangGraph redesign now in place, while the real `StateGraph` runtime is still
  pending.
- FastAPI server, Web UI, server-backed CLI, persisted sessions/settings, dataset config
  import/export, and behavioural replay gates.

## Dataset profiling

Before trusting the pipeline on a dataset, profile it. `scripts/profile_dataset.py`
reads the seven CSVs (read-only — it never edits the data) and emits a markdown
report to `docs/dataset-analysis.md`:

```bash
python scripts/profile_dataset.py            # print report to stdout
python scripts/profile_dataset.py --write    # also write docs/dataset-analysis.md
```

Re-run it whenever the data changes (e.g. an evaluator swaps in a fresher CSV set).
It is the single source of truth for two things the tools depend on:

- **The `reference_now` anchor** — the max *observation* timestamp (excludes
  future-dated/commissioning columns). This is the dataset's "now"; relative time
  windows ("today", "last week") resolve against it, never the wall clock.
- **Tool advisories** — an auto-derived "be careful" list the query/aggregation
  tools must honour: null-vs-zero columns (e.g. `performance_ratio` is empty at
  night — filter, don't zero-fill), lifecycle nulls (`resolved_at` only on resolved
  alerts), silent-downtime inverters, enum typos, PK/FK/reconciliation, and outliers.

Beyond validation (date coverage, completeness, value domains, range checks,
foreign-key integrity), the report carries a **tool-design analysis** block that
maps question vocabulary onto the data — the bridge from "is the data valid" to
"is it answerable":

- **Data dictionary** — every column in every file with a plain-language
  description, type, unit, and PK/FK role.
- **Entity resolver index** — canonical `plant_id ↔ name ↔ region ↔ location`
  (note: `region` is a compass label, not the state) plus inverter counts.
- **Vocabulary coverage map** — each demo filter word (`offline`, `hotspot`,
  `in progress`…) resolved to its exact stored string, or flagged `✗ none`.
- **Current-state snapshot** — per-plant Type-A ground truth at `reference_now`.
- **Cross-table status reconciliation** — where one status field disagrees with
  another (offline inverters with no open alert), so tools combine signals.
- **Measure semantics** — the correct reducer per metric (`daily_yield` = daily
  max, `total_yield` = diff, `performance_ratio` = mean ex-null).
- **Derivable vs non-derivable** — what to compute vs where to refuse (the
  revenue-loss question has no basis in the data).

If a tool returns surprising results, re-run the profiler first: an empty result
is often stale/invalid data or a vocabulary mismatch, not a tool bug.

## Run

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

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
python -m pytest -q
python -m compileall app scripts
rg -n "</content>|</invoke>" README.md docs
```

`pytest` is the offline/unit-style suite. The staged behavioural replay program
is separate and runs through the live server/chat API.

`requirements.txt` carries runtime dependencies; `requirements-dev.txt` adds the local test
dependency. The `rg` command is the lightweight docs-hygiene check for stray copy artifacts in
durable documentation.

### Recommended Gate Run With Saved Artifacts

For a full local gate pass with reviewable artifacts, activate the local venv
and redirect both `stdout` and `stderr` into files:

```bash
source .venv/bin/activate
mkdir -p tests/output/verification tests/output/replay
python -m pytest -q > tests/output/verification/pytest-gint1.txt 2>&1
python -m compileall app scripts > tests/output/verification/compileall-gint1.txt 2>&1
rg -n "</content>|</invoke>" README.md docs > tests/output/verification/docs-hygiene-gint1.txt 2>&1
tests/scripts/run-case-replay.sh --gate gate1 > tests/output/replay/gate1-replay.txt 2>&1
tests/scripts/run-case-replay.sh --gate gate2 > tests/output/replay/gate2-replay.txt 2>&1
tests/scripts/run-case-replay.sh --transcript MT-D3-DISPUTE > tests/output/replay/mt-d3-dispute.txt 2>&1
```

This sequence maps to the current gate plan:

- `G-INT1` — `pytest`, `compileall`, and docs hygiene.
- `G-INT2` — replay `gate1`, replay `gate2`, and the multi-turn dispute transcript.

If you want to watch the replay live and still keep a file artifact, use:

```bash
mkdir -p tests/output/replay
tests/scripts/run-case-replay.sh --gate gate1 2>&1 | tee tests/output/replay/gate1-replay.txt
```

## Case Replay Gates

The replay harness has two behavioural gates:

- `gate1` — the initial-task 15-question set from `docs/solar_interview_task.md`
  (`D1–D6`, `A1–A3`, `B1–B3`, `C1–C3`)
- `gate2` — the remaining 36 canonical behavioural cases from `docs/test-plan.md`
  plus 4 multi-turn transcript fixtures

Use the shell wrapper:

```bash
tests/scripts/run-case-replay.sh --gate gate1
tests/scripts/run-case-replay.sh --gate gate2
```

The wrapper covers server startup for you:

- if the FastAPI server is already running on `127.0.0.1:9006`, it reuses it
- otherwise it starts `app.server`, waits for readiness, then launches replay

So the normal operator path is just:

```bash
tests/scripts/run-case-replay.sh --gate gate1
tests/scripts/run-case-replay.sh --gate gate2
```

You do not need to start `./run-web-server.sh` first unless you specifically
want the server running separately.

### What The Command Runs

`tests/scripts/run-case-replay.sh` forwards to:

```bash
.venv/bin/python -m app.case_replay --server http://127.0.0.1:9006 ...
```

The replay CLI supports:

- `--gate gate1`
- `--gate gate2`
- `--gate gate2verify` for the focused `G2-FIX-11` fresh-port verification subset
- `--case CASE_ID` to run one or more specific single-turn cases
- `--transcript TRANSCRIPT_ID` to run multi-turn transcript fixtures
- `--gating-mode gated|bind_all`
- `--server URL`
- `--request-timeout SECONDS`

Examples:

```bash
tests/scripts/run-case-replay.sh --gate gate1
tests/scripts/run-case-replay.sh --gate gate2 --gating-mode bind_all
tests/scripts/run-case-replay.sh --gate gate2verify --request-timeout 45
tests/scripts/run-case-replay.sh --case D3 --case X4
tests/scripts/run-case-replay.sh --transcript MT-D3-DISPUTE
```

The wrapper also honors:

- `AI_ASSISTANT_STARTUP_TIMEOUT_SECS` to allow longer clean-port startup waits
- `AI_ASSISTANT_READINESS_TIMEOUT_SECS` to control each readiness probe timeout

If wrapper startup fails, it now prints the tail of the captured `uvicorn` log to
help distinguish slow startup from an actual server error.

### Output

Replay output is printed to the terminal as plain text. For each case, the
harness prints:

- case id and `PASS` / `FAIL`
- the question text
- detected intent types
- tool calls used
- individual check results such as intent, tools, text, numbers, trace, and
  stop reason

Typical shape:

```text
D3: PASS
  question: Which inverters have open hotspot anomalies caused by soiling?
  intent: ['C']
  tools: ['anomalies']
  - intent_types: ok (...)
  - tool_calls: ok (...)
  - answer_text: ok (...)
  - answer_numbers: ok (...)
```

At the end of the run, the harness also prints a compact summary table:

```text
Summary
| Status | Kind | Case | Intent | Tools      | Failed Checks  |
|--------|------|------|--------|------------|----------------|
| ✓ PASS | case | D3   | C      | anomalies  | -              |
| ✗ FAIL | case | X4   | B      | perform... | answer_numbers |

Totals: 1 passed, 1 failed, 2 total
```

The process exits non-zero if any selected case fails, so it is suitable for
shell scripting and CI.

### Saving Results

If you want a file artifact, redirect or tee the output:

```bash
mkdir -p tests/output/replay
tests/scripts/run-case-replay.sh --gate gate1 | tee tests/output/replay/gate1-replay.txt
tests/scripts/run-case-replay.sh --gate gate2 | tee tests/output/replay/gate2-replay.txt
```

Or keep stderr and stdout together:

```bash
mkdir -p tests/output/replay
tests/scripts/run-case-replay.sh --gate gate1 > tests/output/replay/gate1-replay.txt 2>&1
tests/scripts/run-case-replay.sh --gate gate2 > tests/output/replay/gate2-replay.txt 2>&1
```

This is useful when you want a human or an AI agent to review the exact replay
report after the run.

### Validation Workflow

Recommended order:

1. Run Gate 1 and confirm all 15 initial-task questions pass.
2. If Gate 1 passes, run Gate 2 for the remaining 36 canonical behavioural
   cases plus the multi-turn transcript fixtures.
3. If needed, run specific transcripts for multi-turn validation.
4. Review any `FAIL` lines and their failed checks.

Example:

```bash
mkdir -p tests/output/replay
tests/scripts/run-case-replay.sh --gate gate1 > tests/output/replay/gate1-replay.txt 2>&1
tests/scripts/run-case-replay.sh --gate gate2 > tests/output/replay/gate2-replay.txt 2>&1
tests/scripts/run-case-replay.sh --transcript MT-D3-DISPUTE > tests/output/replay/mt-d3-dispute.txt 2>&1
```

After that:

- if everything passes, the staged behavioural replay is green
- if anything fails, inspect the failed case block in the saved output file
- use the final summary table to spot failing case ids quickly
- hand those files to a reviewer, or ask an AI agent to summarize failures and
  suggest fixes
