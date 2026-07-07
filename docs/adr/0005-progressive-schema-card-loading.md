# ADR 0005 — Progressive schema-card loading

**Status:** accepted · 2026-07-03
**Revisits:** ADR 0003 (static schema card injected whole into the system prompt).

## Context

ADR 0003 decided to flatten the fixed FK graph into a static "schema card" and
inject it in full at every turn. The rationale was: the topology is fixed and
shallow (2 hops), the card is small relative to the answer quality it protects,
and front-loading it eliminates discovery loops — a deliberate R2-for-R1 trade
the requirements permit.

R2 now asks directly:

> **Prefer progressive disclosure of schema/tool detail over sending everything
> up front, whenever it does not cost answer quality.**

AQ-4 proposes making the card lazy/progressive: a compact summary first, with
full sections injected only for the tools selected by intent classification.
Before implementation, the standing ADR 0003 decision needs to be revisited.

The card today consists of four sections pulled from `docs/dataset-analysis.md`
by `app/schema_card.py`:
1. Join cardinality (~10 rows)
2. Entity resolver index (3-plant lookup table)
3. Vocabulary coverage map (~17 rows)
4. Measure semantics — aggregation rules (6 rows)

It is assembled once at `Pipeline.__init__` and injected verbatim into every
turn's system prompt via `_build_synthesis_prompt`. No section is omitted
regardless of what tools intent-gating selects for that turn.

**AQ-2 coordination seam:** Thread B (AQ-2) plans to wrap *system prompt +
schema card + tool defs* as one cached prefix using Anthropic `cache_control`.
If the card becomes per-turn dynamic (content changes with selected tools), that
prefix can no longer be a stable cached block — cache hit-rate drops to near
zero and AQ-2's savings evaporate. The two tasks must be sequenced or designed
together.

## Options considered

### (a) Keep ADR 0003 as-is — full card, every turn

Inject all four sections unchanged. Cache boundary is stable (AQ-2 works
cleanly). No implementation cost; no risk to R1 or R3.

### (b) Summary-first, drill-down on demand

Inject a short header (FK tree + entity resolver, ~5 lines) by default. Inject
the vocabulary map and measure semantics sections only when intent classification
selects tools that need them (e.g. vocabulary map for anomaly/alert tools,
measure semantics for generation/derived-metric tools). The model requests
additional detail via a `get_schema_detail(section)` tool call if needed.

### (c) Per-tool card sections keyed to selected tools

Decompose the card into per-tool fragments. At intent classification time,
assemble only the fragments for the gated tool subset. No drill-down tool needed;
the card is just smaller. Cache boundary moves to post-intent (per-turn dynamic).

## Decision

Adopt **option (a)** and keep ADR 0003's static schema-card approach.

The system will continue to inject the full schema card on every turn. We are
not implementing progressive schema-card loading as part of AQ-4.

| | (a) Full card, static | (b) Summary + drill-down | (c) Per-tool fragments |
|---|---|---|---|
| **R1 — answer quality** | Baseline (no risk) | Risk: drill-down adds a loop; model may miss a section it didn't know to request | Mild risk: fragment selection logic could omit a needed section |
| **R2 — token cost** | No saving; pays for unused sections every turn | Saves vocabulary + measure sections on Type-A turns (~30–40% of card) | Saves proportionally to how many tool subsets are small; saving is bounded by card size |
| **R3 — iteration count** | Baseline | Worse: adds ≥1 loop per turn that needs a drill-down | Neutral: fragments arrive at turn start, no extra loop |
| **AQ-2 cache compat.** | Fully compatible; prefix is stable | Incompatible unless drill-down is never triggered (defeats the purpose) | Incompatible; prefix content changes per intent |
| **Implementation cost** | Zero | New tool + card sectioning + loop budget impact | Card sectioning + intent-to-fragment mapping |

## Consequences

**(a)** No change. The AQ-2 prompt-caching benefit is fully realised — a single
cached block covers every turn. Token savings from caching the card across
iterations within a turn are preserved. R1 and R3 are unaffected.

**(b)** Drill-down loops consume iterations (R3 impact), and any turn that
triggers one pays extra tokens for the tool call plus re-injected content.
The net R2 benefit may be negative once iteration overhead is counted. The cached
prefix must shrink to the stable header only; AQ-2 saves less per cache hit.
Viable only if empirical data shows most turns skip the drill-down reliably.

**(c)** Per-turn card assembly is cheap (string concatenation). The measurable
R2 saving is bounded: the full card is short (~50 lines); the largest section
(vocabulary map) saves ~20 lines on turns that don't touch alert/anomaly tools.
AQ-2's cached prefix becomes per-intent-class rather than per-process, which
means cache invalidation on every new turn's tool-set — a significant loss of
caching value. If AQ-2 lands first with a static prefix, option (c) would
require AQ-2 to be reworked.

## Rationale

The full-card size is modest, while the downside of dynamic card loading is
concrete:

- It weakens AQ-2's stable cached prefix and would reduce prompt-cache value.
- It adds either answer-quality risk ((c) fragment omission) or extra loop cost
  ((b) drill-down).
- It adds implementation complexity without a proportionate R2 win at the
  current card size.

Given the existing integrated implementation, option (a) is the only choice
that preserves the current R1/R3 behavior and avoids reworking AQ-2.

## Follow-up

AQ-4 is closed by decision rather than implementation. If schema-card size
changes materially in the future, revisit this ADR with measured token data
before re-opening progressive loading.
