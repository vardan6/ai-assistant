# FuturePlus

Forward-looking improvements that are not part of the current Gate 2 fix.

## Replay Grounding For Empty Tool Results

Proposal 3 from the X7 Gate 2 triage should be revisited as an evaluation
quality improvement, not as an immediate agent-runtime change.

The current Gate 2 fix relaxes brittle text matching for X7 because the agent
already performs the correct lookup: `plants(plant="9999")` returns
`matched: 0` and an empty `plants` list, and the answer communicates that the
plant is absent.

A future replay enhancement could generalize this pattern across entity tools:

- Validate the structured tool evidence first, such as `matched == 0`.
- Accept several natural-language no-match phrasings in the final answer.
- Apply the same pattern to plants, inverters, alerts, anomalies, and
  maintenance lookups where an empty result is valid and should not be treated
  as an error.

This would make the evaluation harness better at judging grounded behavior, but
it should be designed as a reusable replay concept rather than as another
X7-specific rule.
