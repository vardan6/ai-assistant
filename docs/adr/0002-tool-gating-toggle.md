# ADR 0002 — Tool gating as a config toggle (gated vs bind_all)

**Status:** accepted · 2026-06-27
**Debrief artifact:** this ADR + a README section presenting the accuracy-vs-cost comparison.

## Context

The task explicitly requires the orchestrator to **not load all seven tables on every question**
and to select tools based on classified intent (graded criterion). The user separately wants
**maximum accuracy** and a reusable template.

How the reference actually gates tools (definitive): in **agent mode it binds ALL eligible tools
at once** (after coarse rover-specific source/permission/execution filters) and lets the LLM
choose. It does **no per-intent subsetting**. Its only "don't attach tools" levers are the
smalltalk fast-path and the chat-vs-agent mode split. We are dropping chat mode → reference
behavior reduces to pure bind-all.

### Token cost of bind-all (asked: ~30 tools)

- ~80–150 tokens per modest tool schema (complex: 200–400) → ~30 tools ≈ **3,000–4,500 tokens of
  tool defs, re-sent every model call**; a 3-iteration loop ≈ ~10k tokens/turn on defs alone.
- **Anthropic prompt caching** puts tool defs + system prompt in the cached prefix → reads ~10%
  cost, not recomputed across iterations/turns → erases ~90% of the recurring cost. This is why
  bind-all is affordable in the reference.
- **This project has only ~7–12 tools** → ~1–1.5k tokens, fully cacheable → token cost is
  effectively negligible. So tokens are **not** the deciding factor here — the graded requirement
  is.

## Decision

Implement gating as a **per-request config toggle** (both paths share the same loop; only the
`bind_tools` list differs):

- **`gated` (default for submission):** intent → *generous* subset = the type's tables **plus
  always-on `plants`/`inverters` resolvers**. Rubric-compliant + inspectable. Generous resolver
  inclusion means no realistic question is stranded → ~zero accuracy delta on this dataset.
- **`bind_all`:** every tool bound; max accuracy; the template-friendly default for other
  projects.

UX: **live toggle on the chat page** (applies to the next message, no reload), with the default
set in Settings. Demo both live and present the comparison.

## Alternatives rejected

- **bind_all default:** fails a named grading criterion unless manually switched for the demo.
- **gated only:** compliant but drops the bind_all option the user wants for the template.
- **Source-controls toggle (reference style):** a settings feature, not per-question gating; does
  not satisfy the requirement on its own.

## Consequences

- Both compliance and the user's accuracy preference are served; the comparison becomes a strong
  debrief talking point.
- A static intent→subset map must be kept in sync with the tool set (mitigated by generous
  resolver inclusion). Detailed map defined in the tools session.
</content>
