# Design — architecture

> How the pipeline is built. Decisions with non-obvious rationale or rejected
> alternatives live in `docs/adr/`.

## Source of reuse

Reference project: `remote-rover/gcs_server` (LangChain tool-calling agent; **not** the React
root `frontend/`). There is **no LangGraph `StateGraph`** — orchestration is a hand-rolled
tool-calling loop (`ai/agent_loop.py`). See ADR 0001. We **selectively reimplement**: copy small
proven modules, write a fresh tool layer, drop all rover/mission/MAVLink code.

### Modules to carry over (small, clean, portable)

| Reference module | Use here |
|---|---|
| `ai/intent_service.py` | LLM→JSON intent classifier + regex fast-path + JSON-repair retry |
| `ai/smalltalk_patterns.py` | Greeting/smalltalk fast-path (skip LLM+tools); extend patterns |
| `ai/agent_loop.py` | Iterative tool-calling loop, result caching, traces, failure detection |
| `ai/provider_registry.py` | Multi-provider chat-model builder + caching + secret resolver |
| `ai/secret_store.py` | SQLite secret store keyed by `secret_ref` (raw keys never in config) |
| `provider_normalizers.py`, `routers/llm.py` | Provider CRUD/normalization, secret redaction |
| `config.py` pattern | JSON config deep-merge (`common.local.json` over `common.example.json`) |
| `ai/agent_traces.py`, `ai/usage_telemetry.py`, `ai/tool_result_cache.py` | Streaming traces + token/timing telemetry + tool-result cache |
| `ai/session_store.py` | SQLite session store for sidebar + CLI session resume (trimmed) |
| `tools/gcs_ai_cli.py` | Thin HTTP-client CLI (token/timing footer); adapt |
| Web theme tokens (colors/spacing/styling) | Adopt for the fresh Web UI |

### Dropped

`tool_registry.py` (126K, rover-specific), all mission/MAVLink/road-graph/replay services, RAG
service, chat mode, execution-mode/permission tiers, the heavy `webapp/ai.js`.

## Topology — server-centric

FastAPI server on **:9006** is the brain. **CLI and Web UI are thin HTTP clients** of the same
API (shared token/timing footer format). One pipeline, two front-ends.

```
question → [smalltalk fast-path?] → IntentClassifier (A/B/C + entities + out_of_scope)
        → tool gating (gated subset | bind_all)  → agent loop (iterative tool calls)
        → tools (pandas aggregation, structured dicts) → synthesis (refusal-guarded)
        → answer + telemetry (intent, tool steps streamed, tokens/time footer)
```

## Data access

Pandas in-memory: load 7 CSVs into DataFrames once at startup behind a thin **`DataSource`
interface** so the backing store is swappable later (SQLite/DuckDB) without touching tools. All
aggregation happens in code; tools return structured dicts. No raw rows reach the model.

## Tools

One tool per CSV (7) + a small number of derived metric tools (e.g. daily_yield,
performance_ratio, mttr) under a uniform registration pattern. Tools accept name **or** id so the
loop can resolve `plant_id`/`inverter_id` then filter (the 2-step chain). Type B intent gating may
bind the raw reading summaries and the derived metric tools together so the loop can choose the
smallest sufficient tool for the question.

## Intent classification

Reuse `intent_service` shape. Skeleton schema (fields finalized with tools):
`{ types: [A|B|C], entities: {plant, inverter, ...}, time_range, metric, out_of_scope, confidence }`.
Explicit, logged, inspectable. May route to a cheaper/local model via `model_routing`.

## Tool gating — config toggle (marquee design point)

Tools bound per-request in the loop, so the mode is a **per-request parameter** (no reload):
- **`gated`** (default): intent → *generous* subset = the type's tables **plus always-on
  `plants`/`inverters` resolvers**. Rubric-compliant, inspectable, ~zero accuracy loss on this
  dataset.
- **`bind_all`**: bind every tool, max accuracy (reference's actual behavior). Template-friendly.

**Live toggle on the chat page** (applies to next message) + default in Settings. The
accuracy-vs-cost comparison is documented for the debrief — see ADR 0002.

## LLM providers

All reference provider **types** are configurable options: `openai`, `anthropic`,
`google_gemini`, `mistral`, `groq`, `ollama`, `openai_compatible` (cohere = stub, skipped).
Routing: `ollama`→`ChatOllama`, `anthropic`→`ChatAnthropic`, rest→`ChatOpenAI`+`base_url`.
Per-provider fields: `id, display_name, provider_type, model_id, auth_mode(env_var|stored_secret|none),
secret_ref, base_url, enabled`. **Pre-seed OpenAI + Ollama** (copied from reference local config,
refs only); Anthropic selectable without a key. Config = JSON file; secrets = SQLite SecretStore.

`model_routing` lets the **intent classifier use a cheap/local model** while synthesis uses a
stronger one — a token-cost lever.

## Token / context optimization

Compounding, accuracy-neutral: Anthropic prompt caching (tool defs + system prompt in cached
prefix) · smalltalk fast-path · gated tools · cheap intent model via routing · concise structured
tool results (never raw CSV). Accept a small latency cost (occasionally one extra loop iteration)
to keep early-iteration context small.

## Telemetry & UI

- Backend: `stream_tool_events` + `agent_traces` + `usage_telemetry` → live agent-step trace
  (which tool, gradually) and per-message footer (tokens in/out/total, time elapsed, tok/s, model,
  timestamp). Verbose-trace toggle in Settings.
- Web UI: sessions **sidebar** + chat area + message cards, adopting reference theme tokens.
  Settings: **LLM Providers tab now**; Appearance/theme tab later.
- CLI: thin client mirroring the same footer.

## Graceful degradation

Intent `out_of_scope` flag + synthesis prompt guarded to explicitly refuse when tool results are
empty/insufficient or required data does not exist (e.g. Q6 revenue-from-downtime). Never fabricate.
</content>
