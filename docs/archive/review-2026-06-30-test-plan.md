# Test Plan Review - 2026-06-30

## Scope

Review of `docs/test-plan.md` only. No edits were made to the test plan.

## Request

Review `docs/test-plan.md` and report findings only; do not edit it yet.

The file currently feels too mixed and too complicated, and some material may be
repeated in several places. The goal is to have a strong test plan for running
all cases in CLI mode. "All cases" means the cases defined in the initial task
document, plus the additional comprehensive cases defined later and documented
in the test plan.

The test plan should keep strong criteria for what we check, how we check it,
and how we mark results. The question is whether we can improve the structure
and clean up repetition without losing any data.

Review focus:

- whether the plan is a clear CLI-mode contract for all required cases
- whether task-document cases and added comprehensive cases are both preserved
- whether criteria are clear: what we check, how we check, how we mark
- whether repeated or mixed material can be cleaned up without losing data

Sources checked:

- `docs/test-plan.md`
- `docs/solar_interview_task.md`
- `docs/requirements/pipeline.md`
- `docs/golden-answers.md`
- `app/case_replay.py`
- `scripts/golden_answers.py`
- `tests/test_case_replay.py`
- `activeContext.md`
- `roadmap.md`

## Summary

The test plan has the right raw material: task-derived cases, expanded
surface-by-surface cases, trap coverage, oracle references, and structural probe
ideas. The problem is organization, not missing intent. The file currently mixes
four roles:

- task-document extraction
- runnable case catalog
- traceability matrix
- implementation/progress status

That mixing creates repeated sections and makes it hard to answer the most
important operational question: "Which CLI cases do we run, what must each prove,
and how do we mark the result?"

The plan can be restructured cleanly without losing data by making the full case
catalog the single canonical inventory, moving duplicated task/rubric material
into traceability tables, and separating stable test contract from current
execution status.

## Findings

### 1. "All cases" is not currently a precise executable set

- Priority: `must_fix_before_cleanup`
- Risk: `high`
- Value: `high`
- Effort: `med`

`docs/test-plan.md` says the full catalog replay is still pending:

- `docs/test-plan.md:14`
- `docs/test-plan.md:361`

The document's section 3 contains:

- 51 behavioral cases: `D/P/I/G/W/AL/M/AN/X`
- 5 structural probe cases: `R2-unit`, `R2-gating`, `R4-probe`, `R3-trace`, `R1-trace`

The current replay harness contains 15 behavioral replay specs:

- `D2`, `D3`, `D4`, `D5`, `D6`
- `P4`, `I5`, `G2`, `G4`, `W3`, `AL5`, `AN6`
- `X2`, `X4`, `X6`

So 36 section-3 behavioral cases are documented but not represented in
`app/case_replay.py` as replay specs:

`D1`, `P1`, `P2`, `P3`, `P5`, `I1`, `I2`, `I3`, `I4`, `G1`, `G3`,
`G5`, `G6`, `W1`, `W2`, `W4`, `AL1`, `AL2`, `AL3`, `AL4`, `AL6`,
`M1`, `M2`, `M3`, `M4`, `M5`, `AN1`, `AN2`, `AN3`, `AN4`, `AN5`,
`AN7`, `X1`, `X3`, `X5`, `X7`.

This is not necessarily a product bug, but it is a test-plan clarity problem.
The plan needs a visible distinction between:

- full planned catalog
- currently automated CLI replay set
- cases intentionally covered through aliases or probes
- cases not automated yet

### 2. Status meanings mix plan coverage, implemented probes, and CLI verification

- Priority: `must_fix_before_cleanup`
- Risk: `high`
- Value: `high`
- Effort: `low`

The status legend says `✅` and `➕` are verified states:

- `docs/test-plan.md:154`

But the document also says the live full-catalog CLI replay is still pending:

- `docs/test-plan.md:361`

Some rows therefore read as verified even though the live CLI run has not yet
confirmed the full catalog. This weakens the document as a pass/fail contract.

Recommended split:

- `Coverage`: `required`, `added`, `probe`, `alias`, `non-goal`
- `Automation`: `cli_replay`, `unit_probe`, `manual_review`, `not_automated`
- `Latest result`: `not_run`, `pass`, `fail`, `blocked`, `accepted_refusal`

That avoids one overloaded status symbol trying to describe three different
facts.

### 3. The document duplicates source-of-truth material in several places

- Priority: `should_fix_before_cleanup_complete`
- Risk: `med`
- Value: `high`
- Effort: `med`

Repeated material:

- demo cases appear in section 1.1 and section 3.1
- pipeline requirements appear in section 1.5 and section 2.2
- evaluation criteria appear in section 1.7 and section 2.3
- non-goals appear in section 1.8 and section 2.4

The durable source for requirements is already `docs/requirements/pipeline.md`.
The original assignment is already `docs/solar_interview_task.md`.
The test plan should not recopy those documents at length. It should map from
them into runnable test coverage.

### 4. Stale notes make the plan look less trustworthy than it is

- Priority: `should_fix_before_cleanup_complete`
- Risk: `med`
- Value: `med`
- Effort: `low`

Examples:

- `docs/test-plan.md:95` says "Section 2 (to follow)", but section 2 exists.
- `docs/test-plan.md:101` describes TODO marking, while `docs/test-plan.md:140`
  says those TODOs have been reconciled.
- `docs/test-plan.md:346` says "Still owed in later sections", but the list below
  includes several already-completed items and only one truly pending item.

These are cleanup issues, but they matter because this document is intended to
be the verification contract.

### 5. Initial task cases should be represented as aliases to canonical cases

- Priority: `should_fix_before_cleanup_complete`
- Risk: `med`
- Value: `high`
- Effort: `low`

The task examples `A1`-`C3` are useful because they prove direct assignment
coverage. But many are effectively aliases of richer section-3 cases:

- `A1` -> `P1`
- `A2` -> `I1`
- `A3` -> `AL1`
- `B1` -> `G1`
- `B2` -> `G4`
- `B3` -> `AL5`
- `C1` -> `AN1`
- `C2` -> `AN2`
- `C3` -> `AN6`

Keeping both as separate rows makes the plan feel larger and more repetitive.
The better structure is one canonical case row with an `Origin/spec alias`
column, then a traceability table showing every original task item is covered.

### 6. CLI execution criteria are present but scattered

- Priority: `must_fix_before_cleanup`
- Risk: `high`
- Value: `high`
- Effort: `med`

The document has strong criteria concepts:

- intent classification must be inspectable
- tools and bound tools must match intent
- code aggregation must be verified
- final answers must match oracle facts
- refusals and ambiguity must be marked explicitly
- traces must prove stage order and tool-chain behavior

But those rules are spread across sections 1.7, 2, 3.10, and 3.12. A CLI test
operator should not have to infer the execution contract.

The plan needs one central section:

- command to run
- server/provider prerequisites
- gating mode
- case selection rule
- captured fields
- pass/fail criteria
- allowed result states
- triage output format

### 7. Some expected outcomes are not exact enough for automated marking

- Priority: `should_fix_before_cleanup_complete`
- Risk: `med`
- Value: `med`
- Effort: `low`

Examples:

- `G6` says `refuse/empty`
- `AL6` says `refuse/empty`
- `AN7` says approximately 2

Those may be fine as exploratory notes, but a CLI-mode test plan needs exact
acceptable behavior:

- expected `stop_reason`
- required text or structured refusal reason
- expected empty result shape
- exact count if count is asserted
- whether clarification is expected instead of refusal

### 8. Oracle ownership should be clearer

- Priority: `should_fix_before_cleanup_complete`
- Risk: `med`
- Value: `high`
- Effort: `low`

`docs/golden-answers.md` is the correctness oracle. `docs/test-plan.md` repeats
many concrete values inline. That is useful for readability, but risky for drift.

Recommended rule:

- `docs/golden-answers.md` owns exact computed values.
- `docs/test-plan.md` owns question, intent, expected checks, trap, and oracle key.
- Inline values in `docs/test-plan.md` should be short summaries only, not the
  canonical source.

## Recommended Restructure

Preserve all data, but change ownership and order:

1. `Purpose and Sources`
   Short statement that the test plan maps task requirements into CLI-verifiable
   cases. Link to task, requirements, oracle, and dataset analysis.

2. `How CLI Replay Is Run`
   Server prerequisites, command, gating mode, case selection, output captured,
   and where results are stored.

3. `How Cases Are Marked`
   Define pass/fail/result states. Separate coverage, automation, and latest run
   result instead of one overloaded status symbol.

4. `Canonical Case Catalog`
   One row per canonical case. Suggested columns:
   `ID`, `Origin/spec alias`, `Question`, `Intent`, `Expected chain`,
   `Oracle/probe`, `Required checks`, `Trap`, `Automation`, `Latest result`.

5. `Structural Probe Catalog`
   Keep `R1-trace`, `R2-unit`, `R2-gating`, `R3-trace`, `R4-probe` separate from
   user-question cases.

6. `Traceability Matrix`
   Map every item from `docs/solar_interview_task.md` to canonical case IDs and
   probes. This replaces long duplicated task extraction.

7. `Trap Coverage Index`
   Keep this section. It is useful and belongs in the plan.

8. `Open Items`
   Only unresolved work. Today that should mainly be the live full-catalog CLI
   replay and any cases not yet automated.

## Proposed Immediate Cleanup Order

1. Remove stale notes and contradictory status language.
2. Decide whether section-3 "full catalog" means all 51 behavioral cases must be
   replayed through CLI, or whether the 15-case harness is a representative
   subset.
3. Convert `A1`-`C3` into aliases in the canonical catalog instead of repeated
   standalone cases.
4. Add a central CLI execution and marking section.
5. Move implementation progress notes out of the stable test contract.
6. Keep exact numeric answers owned by `docs/golden-answers.md`; reference oracle
   keys from the test plan.

## Open Question

The main decision before editing `docs/test-plan.md`:

Should the required CLI run include every section-3 behavioral case, or should it
run a smaller representative subset while unit/probe tests cover the rest?

The current document implies "full catalog", while the current harness implements
a smaller subset. The cleanup should make that decision explicit before wording
or table structure is changed.
