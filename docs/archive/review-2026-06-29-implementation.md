# Implementation Review — 2026-06-29

## Scope

Comprehensive review of the current implementation against:

- `docs/requirements/pipeline.md`
- `docs/design/architecture.md`
- `docs/implementation-notes.md`

Review focus:

- misimplementation
- bugs / incorrect logic
- redundant code
- coverage gaps
- documentation alignment

## Summary

The implementation is broadly aligned with the intended architecture:

- explicit intent classification exists
- tools are independently callable and return structured dicts
- dataset-relative date anchoring exists
- tool gating modes exist
- *most* dataset settings / reload flows are atomic for config persistence
- tests are present and currently pass

### Re-validation (2026-06-29, second pass)

All four original findings were re-checked against current source and are
**confirmed true**. This pass also adds five new findings and tightens several
recommendations. Verdicts per original finding:

| # | Original finding | Verdict | Note |
|---|------------------|---------|------|
| 1 | Dataset schema not validated before activation | ✅ confirmed | `PandasDataSource._load` only checks file existence + parseability + one reading timestamp; no per-table required-column check. |
| 2 | Smalltalk depends on provider resolution | ✅ confirmed | `pipeline.answer` calls `resolve_provider(...)` (eager model build) *before* `parse()`; also affects the empty-prompt fast-path, not just smalltalk. |
| 3 | Gated falls back to bind-all on empty `types` | ✅ confirmed | Also fires whenever intent parsing *fails*, since `make_empty_intent()` returns `types=[]`. |
| 4 | Dead `_clean` helper / `clean` import | ✅ confirmed | `clean` is imported only to back the unused `_clean`. |

Issues now treated as immediate correctness defects:

1. dataset activation does not fully validate the dataset schema before switching runtime (Finding 1)
2. smalltalk/empty-prompt fast-paths do not short-circuit before provider/model resolution (Finding 2)
3. **config import persists to disk before validating the dataset, so a bad import corrupts persisted config and can prevent the server from booting (Finding 5 — new, contract break)**

Plus a logic gap in gated mode (Finding 3), a graceful-degradation gap on the
tool-loop iteration limit (Finding 6 — new), and several redundancy/housekeeping
items (Findings 4, 7, 8, 9).

## Findings

### 1. Dataset validation is weaker than the documented contract

- Priority: `must_fix_now`
- Risk: `high`
- Value: `high`
- Effort: `med`

#### Documentation expectation

`docs/requirements/pipeline.md` says:

- dataset save/upload/import must validate the full resolved 7-file dataset before runtime switches
- on failure, the active dataset remains in use and persisted config remains unchanged

`docs/implementation-notes.md` says:

- rebuild the pipeline only after validating the full resolved dataset

#### Implementation reality

Dataset validation currently happens by constructing a new `Pipeline`:

- [app/server.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/server.py:178)

That in turn constructs `PandasDataSource`, which only checks:

- each CSV path exists
- pandas can read the file
- at least one reading timestamp exists for `dataset_today`

Relevant loader path:

- [app/data/pandas_source.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/data/pandas_source.py:47)

The loader does not validate required columns per table. It explicitly ignores missing date columns:

- [app/data/pandas_source.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/data/pandas_source.py:53)

Several tools assume required columns exist and crash later if the schema is incomplete. Example:

- [app/tools/common.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/tools/common.py:42)
- [app/tools/plants.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/tools/plants.py:63)

#### Verified repro

I replaced `plants.csv` with a parseable file containing only:

```csv
plant_id
P1
P2
P3
```

Observed behavior:

- `Pipeline(...)` constructed successfully
- dataset would therefore be accepted by save/upload/import validation
- plant-scoped tool usage later failed or degraded

Concrete results:

- `plants` tool returned partial records with only `plant_id`
- `alerts` with a plant-name filter failed with `{'ok': False, 'error': "KeyError: 'name'"}` because `filter_plant()` expects the plants table to contain `name`

#### Why this matters

This is a direct contract break. The system can report successful dataset activation while accepting a malformed dataset that will fail at runtime in normal user flows.

#### Validation verdict

**Confirmed true.** `validate_pipeline()` ([app/server.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/server.py:178)) constructs a `Pipeline`, which builds `PandasDataSource`. `PandasDataSource._load()` only enforces: file exists ([pandas_source.py:50](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/data/pandas_source.py:50)), `pd.read_csv` succeeds, and `_compute_dataset_today()` finds at least one reading timestamp ([pandas_source.py:59](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/data/pandas_source.py:59)). No per-table required-column check exists. Date-column parsing is explicitly guarded by `if column in frame.columns` ([pandas_source.py:54](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/data/pandas_source.py:54)), so missing columns pass silently.

Note the failure is **uneven across tools** because the shared helpers degrade differently:

- `counts()` and `records()` ([app/tools/common.py:19](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/tools/common.py:19), [:28](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/tools/common.py:28)) **silently tolerate** missing columns (return `{}` / skip the field) — so a malformed table produces *quietly wrong* answers rather than an error.
- direct column access like `_filter_by_plant` reading `frame["name"]` ([app/tools/plants.py:63](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/tools/plants.py:63)) and `plants_status` reading `frame["status"]` ([app/tools/plants.py:48](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/tools/plants.py:48)) **hard-crash** with `KeyError`.

So the contract break has two faces: hard crashes *and* silent data corruption. The silent path is arguably worse because it never surfaces.

#### Recommended fix

Add explicit dataset schema validation before activation:

- define a required-columns manifest per canonical table (single source of truth, e.g. in `app/data/source.py` next to `TABLE_NAMES`)
- validate all 7 tables during dataset save/reload/upload/import **and** at config import (Finding 5) and process startup
- reject activation if any required column is missing; surface the offending table + column in the error
- prefer validating in `PandasDataSource._load()` (or a dedicated `validate_schema()` it calls) so *every* construction path is covered, rather than only the server endpoints
- add tests for malformed-but-parseable CSVs, not only missing files (cover both the hard-crash and silent-degradation tables)

## 2. Smalltalk fast-path still depends on provider resolution

- Priority: `must_fix_now`
- Risk: `high`
- Value: `high`
- Effort: `low`

#### Documentation expectation

Requirements say greetings/smalltalk must short-circuit before LLM/tools:

- [docs/requirements/pipeline.md](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/docs/requirements/pipeline.md:51)

The architecture doc also describes the flow as:

- smalltalk fast-path before the main intent/model/tool path
- [docs/design/architecture.md](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/docs/design/architecture.md:40)

#### Implementation reality

`Pipeline.answer()` resolves the intent provider before calling the intent parser:

- [app/pipeline.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/pipeline.py:115)

Only after provider resolution does the code inspect `fast_path == "smalltalk"`:

- [app/pipeline.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/pipeline.py:138)

This means a greeting can fail before the fast-path is reached.

#### Verified repro

I configured a single env-var-backed provider with a missing env var and called:

```text
hello
```

Observed result:

```text
ValueError: Environment variable MISSING_KEY is not set.
```

Expected result:

- return the smalltalk reply without requiring provider resolution or model access

#### Validation verdict

**Confirmed true.** In `Pipeline.answer()`, `resolve_provider(..., purpose="intent")` runs at [pipeline.py:116](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/pipeline.py:116), *before* `self._intent_service.parse(...)` at [pipeline.py:121](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/pipeline.py:121). `resolve_provider` eagerly builds (and caches) the chat model via `_cached_chat_model` → `build_chat_model` → `_api_key_for_provider`, which raises `ValueError("Environment variable ... is not set.")` for an `env_var` provider with a missing key ([provider_registry.py:198](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/ai/provider_registry.py:198)). The smalltalk check happens locally inside `IntentService.parse` via `is_smalltalk()` ([intent_service.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/ai/intent_service.py:38)) with **no model call**, so the fast-path never needs a provider at all — yet it is gated behind one.

**Scope is broader than the doc stated.** The same eager resolution also blocks the **empty-prompt fast-path** (`IntentService.parse` returns `fast_path="empty"` for blank input without touching the model). Both pure-local fast-paths are defeated. The fix must cover both.

Also note the `/api/chat` endpoint only catches `ValueError` and maps it to HTTP 400 ([server.py:491](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/server.py:491)) — so today a greeting with misconfigured providers returns a 400 error to the user instead of the friendly smalltalk reply.

#### Why this matters

This is a user-visible correctness bug. A greeting should be the safest path in the system, but right now it can fail because of unrelated LLM configuration state.

#### Recommended fix

Run the pure-local fast-path classification before any provider resolution. Concretely:

- at the top of `answer()`, compute `is_smalltalk(question)` (and the empty-prompt check) and return the canned reply *before* calling `resolve_provider`
- alternatively, restructure so `IntentService.parse` is given a lazily-resolved model (a thunk/callable) and only triggers resolution when it actually needs the LLM — this keeps the fast-path logic in one place and also fixes the empty-prompt case
- prefer the second option if you want a single source of truth for "what is a fast-path"; the first is lower-effort and adequate
- add a `Pipeline.answer()`-level test with a deliberately broken provider asserting that `"hi"` still returns the smalltalk reply

## 3. Gated mode falls back to binding every tool when classification is empty

- Priority: `should_fix_before_phase_complete`
- Risk: `med`
- Value: `high`
- Effort: `low`

#### Documentation expectation

The requirements and design emphasize explicit intent classification and intent-driven tool selection:

- [docs/requirements/pipeline.md](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/docs/requirements/pipeline.md:25)
- [docs/requirements/pipeline.md](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/docs/requirements/pipeline.md:28)
- [docs/design/architecture.md](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/docs/design/architecture.md:68)

#### Implementation reality

In `select_tool_names()`, if `types` is missing or empty, `gated` mode returns the full tool list:

- [app/pipeline.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/pipeline.py:221)

I verified:

```python
select_tool_names({"types": []}, gating_mode="gated", ...)
```

returns all tools.

#### Validation verdict

**Confirmed true.** [pipeline.py:221-223](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/pipeline.py:221): when `types` is not a non-empty list, the function returns `[name for name in available_tools if name in available]` — i.e. every tool.

**Aggravating factor not in the original note:** this path is not just hit when the model legitimately returns no types. `IntentService.parse` returns `make_empty_intent()` (with `types=[]`) on *parse failure* after repair attempts are exhausted ([intent_service.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/ai/intent_service.py:108)). So **a flaky/garbled intent response silently downgrades `gated` to `bind_all`** — the opposite of failing safe, and it does so invisibly (the trace shows empty `types`, not "fell back to all tools").

#### Why this matters

This effectively degrades `gated` into `bind_all` whenever classification fails or comes back empty. That weakens the explicit “classify first, then select tools” contract and makes the gating behavior less inspectable than intended. Requirement 2 explicitly states the orchestrator "must not load all seven tables on every question" — the empty-types fallback violates exactly that for the failure case.

#### Recommended fix

Pick an explicit fallback policy and test it. Reasonable choices:

- bind only the always-on resolvers (`plants`, `inverters`) plus a minimal safe subset
- fail closed and ask the model to clarify
- treat empty classification as an error path instead of silently binding everything

Whichever is chosen, **emit a distinct trace event** (e.g. `gating_fallback`) so the downgrade is inspectable rather than hidden behind an empty `types` list. Test both "model returned empty types" and "intent parse failed" inputs.

## 4. Minor redundant code in the plants tool

- Priority: `backlog`
- Risk: `low`
- Value: `low`
- Effort: `low`

There is a dead helper:

- `_clean()` in [app/tools/plants.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/tools/plants.py:67)

Because it is unused, the `clean` import in the same file is also unnecessary:

- [app/tools/plants.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/tools/plants.py:10)

This is harmless, but it is redundant code. **Confirmed:** `_clean` is never called and `clean` is imported solely to back it (`counts`/`records` are the only other imports from `.common`, both used).

## 5. Config import persists before validating the dataset — non-atomic, can brick startup

- Priority: `must_fix_now`
- Risk: `high`
- Value: `high`
- Effort: `low`

#### Documentation expectation

`docs/requirements/pipeline.md` ([:64-66](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/docs/requirements/pipeline.md:64)):

- "Saving or upload/import activation must validate the full resolved 7-file dataset before the runtime switches over. On failure, the current active dataset remains in use and the persisted config remains unchanged."
- Config import "includes dataset settings as paths/config only".

The dataset endpoints (`PUT /api/settings/dataset`, reload, reset, upload, import-zip) follow this carefully: they build a candidate config, call `validate_pipeline()`, and only call `save_config()` **after** validation succeeds ([server.py:279-281](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/server.py:279)).

#### Implementation reality

`PUT /api/settings/config` does **not** follow that order:

- [server.py:414-424](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/server.py:414)

```python
cfg = import_config_payload(cfg, payload=request.config)  # <-- save_config() runs here, persists to disk
secrets = SecretStore(cfg.llm_secrets_db_path)
sessions = SessionStore(cfg.ai_sessions_db_path)
evict_model_cache()
live_pipeline = Pipeline(cfg, secret_resolver=secrets.get)  # <-- dataset only validated HERE, unguarded
```

`import_config_payload` calls `save_config(...)` internally ([provider_config.py:255](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/provider_config.py:255)), so the new config is written to disk **before** any dataset validation. If the imported `data.csv_dir` / `csv_files` point to a missing or malformed dataset, the `Pipeline(cfg)` call raises an unhandled exception (only `ValueError` is caught, and `FileNotFoundError` is not), producing an HTTP 500 — **but the bad config is already persisted**.

#### Why this matters

This breaks the documented atomicity contract specifically for the config-import path. Worse: the module-level `app = create_app()` ([server.py:565](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/server.py:565)) constructs `live_pipeline` at import time, which loads the dataset. So a persisted-but-invalid dataset config means **the server fails to boot on the next restart** — a self-inflicted denial of service from a single bad import payload.

#### Recommended fix

Mirror the dataset-endpoint pattern: build the candidate `AppConfig` in memory, run `validate_pipeline()` (which must also do schema validation per Finding 1), and only `save_config()` after validation passes. Split `import_config_payload` into a `prepare_` (no save) + explicit save, the way `prepare_dataset_settings` / `save_config` are already separated. Catch the same broad exception set `validate_pipeline` already wraps. Add a test importing a config with a bad dataset path and assert (a) HTTP 400, (b) persisted config unchanged, (c) `live_pipeline` unchanged.

## 6. Tool loop has no graceful fallback on iteration limit; "refusal-guarded" is doc-only

- Priority: `should_fix_before_phase_complete`
- Risk: `med`
- Value: `med`
- Effort: `low`

#### Documentation expectation

The `Pipeline` module docstring describes the flow as ending in a "refusal-guarded answer" ([pipeline.py:1-8](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/pipeline.py:1)). Requirement 5 ("Graceful degradation") says the assistant must "say so clearly; never hallucinate a number."

#### Implementation reality

There is **no refusal guard** in `run_agent_loop` or `Pipeline.answer`. If the model exhausts `MAX_TOOL_ITERATIONS = 6` ([agent_loop.py:19](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/ai/agent_loop.py:19)) still emitting tool calls, the loop exits with `stop_reason = "iteration_limit"` and the final message it builds is from a turn that contained tool calls — so `_final_text()` typically returns an **empty string** ([agent_loop.py:62, 128](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/ai/agent_loop.py:128)). The user receives a blank answer with no explanation.

Graceful degradation for out-of-scope/unanswerable questions is handled earlier (the `out_of_scope` branch and prompt instructions), so this gap is narrow — but the empty-answer-on-iteration-limit case is real and silent.

#### Recommended fix

- when `stop_reason == "iteration_limit"` and the answer is empty, substitute an explicit "couldn't complete this within the step budget" message rather than returning `""`
- either implement an actual refusal guard at the pipeline level or remove the "refusal-guarded" phrasing from the docstring so docs match code (decision truth vs. implementation truth)
- add a test driving a stub model that always returns tool calls, asserting a non-empty, explanatory answer

## 7. `select_tool_names` has dead membership filtering in two branches

- Priority: `backlog`
- Risk: `low`
- Value: `low`
- Effort: `low`

In `select_tool_names`, `available = set(available_tools)`, and both the `bind_all` branch and the empty-`types` branch return `[name for name in available_tools if name in available]` ([pipeline.py:218-223](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/pipeline.py:218)). Every element of `available_tools` is by definition in `available`, so the `if name in available` guard is always true — these two branches are just `list(available_tools)` written in a way that reads as if it filters. In the final branch the `and name in available` clause is likewise always true (it iterates `available_tools`). This is harmless but misleading; simplify to `list(available_tools)` and drop the redundant `available` set (keep only the `selected` membership check in the gated branch).

## 8. `plants.py` references `pd` without importing it

- Priority: `backlog`
- Risk: `low`
- Value: `low`
- Effort: `low`

`_filter_by_plant(frame: pd.DataFrame, ...)` annotates with `pd.DataFrame` ([plants.py:60](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/tools/plants.py:60)), but `plants.py` never imports pandas. This does not crash at runtime only because `from __future__ import annotations` ([plants.py:6](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/tools/plants.py:6)) makes annotations lazy strings. It would raise `NameError` under `typing.get_type_hints()` and is flagged by static type checkers. Add `import pandas as pd` (paired with removing the unused `clean` import from Finding 4) or drop the annotation.

## 9. Uploaded/imported managed dataset files are never garbage-collected

- Priority: `backlog`
- Risk: `low`
- Value: `low`
- Effort: `med`

`upload_dataset_table` writes a uniquely-named file under `managed_datasets/overrides/` on every successful upload ([server.py:308](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/server.py:308)) and `import_dataset_zip` writes a fresh `imports/dataset-<uuid>/` tree each time ([server.py:367](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/app/server.py:367)). The previously-active managed files are never removed when a new one supersedes them. Since exactly one dataset config is active at a time (requirement, [pipeline.md:67](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/docs/requirements/pipeline.md:67)), superseded managed files are orphaned and accumulate unbounded. Not a correctness bug, but a housekeeping/disk-leak gap. Consider pruning managed files no longer referenced by the active config after a successful activation (carefully — only files under `MANAGED_DATASET_ROOT`, never user-supplied paths).

## What looks aligned

These parts appear consistent with the current docs:

- dataset-relative date anchoring is implemented in the synthesis prompt and metric window helpers
- tools return structured dicts rather than prose
- aggregation logic is performed in code
- at least one 2-step tool chain is represented in tests
- dataset save/reload/reset/upload/import flows keep persisted config unchanged on hard validation failure (**but config *import* does not — see Finding 5**)
- config export/import excludes dataset file contents and operates on paths/config only (the *contents* exclusion holds; the *validate-before-persist* guarantee does not for import — Finding 5)

## Test coverage gaps

Current test status:

- full suite passes: `42 passed`

But the suite does not currently catch the most important defects above.

### Missing tests

1. Dataset schema validation

- Existing tests cover missing files
- They do not cover malformed-but-readable CSVs with missing required columns

Relevant area:

- [tests/test_phase2_server_provider_telemetry.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/tests/test_phase2_server_provider_telemetry.py:250)

2. Pipeline-level smalltalk short-circuit

- `IntentService.parse()` is tested for local smalltalk fast-path behavior
- `Pipeline.answer()` is not tested to ensure provider resolution is skipped for smalltalk

Relevant area:

- [tests/test_intent.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/tests/test_intent.py:25)

3. Empty-classification gated fallback

- happy-path A/B/C gating is tested
- empty `types` behavior is not tested, nor the intent-parse-failure path that produces empty `types`

Relevant area:

- [tests/test_phase1_pipeline_core.py](/mnt/c/Users/vardana/Documents/Proj/aregi/ai-assistant/tests/test_phase1_pipeline_core.py:40)

4. Config-import atomicity (Finding 5)

- existing tests cover dataset-endpoint atomicity
- no test imports a config whose dataset is broken and asserts persisted config + live pipeline are unchanged and startup still works

5. Tool-loop iteration limit (Finding 6)

- no test drives the loop to `MAX_TOOL_ITERATIONS` and asserts a non-empty, explanatory answer instead of `""`

## Recommended next actions

1. Fix config-import to validate before persisting (Finding 5) — highest blast radius, can brick startup.
2. Fix dataset schema validation before any further dataset-upload polish (Finding 1); share the validator with the config-import fix.
3. Fix pipeline-level fast-path short-circuit so greetings/empty prompts do not depend on provider config (Finding 2).
4. Decide and codify the intended fallback behavior for empty/failed intent classification in `gated` mode, with an inspectable trace event (Finding 3).
5. Add an iteration-limit fallback message and reconcile the "refusal-guarded" docstring (Finding 6).
6. Add regression tests for all of the above.
7. Backlog cleanup: Findings 4, 7, 8, 9.

## Triage summary

| # | Finding | Risk | Value | Effort | Priority | Verdict | Reason |
|---|---------|------|-------|--------|----------|---------|--------|
| 1 | Dataset activation does not validate full schema before switching runtime | high | high | med | must_fix_now | ✅ confirmed | Documented contract break; malformed datasets activate, causing hard crashes *and* silent wrong answers |
| 2 | Fast-paths (smalltalk + empty prompt) depend on provider resolution | high | high | low | must_fix_now | ✅ confirmed | User-visible bug; greetings return HTTP 400 on missing LLM config |
| 3 | `gated` binds all tools when classification is empty/failed | med | high | low | should_fix_before_phase_complete | ✅ confirmed | Weakens intent-driven selection; also triggered invisibly by parse failure |
| 4 | Dead `_clean` helper + `clean` import in `plants.py` | low | low | low | backlog | ✅ confirmed | Redundant code only |
| 5 | Config import persists before dataset validation | high | high | low | must_fix_now | 🆕 new | Atomicity contract break; bad import corrupts persisted config and can prevent server boot |
| 6 | Tool loop returns empty answer at iteration limit; "refusal-guarded" is doc-only | med | med | low | should_fix_before_phase_complete | 🆕 new | Silent blank answer; docstring claims a guard that does not exist |
| 7 | Dead membership filtering in `select_tool_names` | low | low | low | backlog | 🆕 new | Misleading no-op filters; simplify to `list(available_tools)` |
| 8 | `plants.py` uses `pd` without importing it | low | low | low | backlog | 🆕 new | Saved only by lazy annotations; breaks `get_type_hints` / type checkers |
| 9 | Managed uploaded/imported dataset files never pruned | low | low | med | backlog | 🆕 new | Unbounded disk accumulation of orphaned managed files |
