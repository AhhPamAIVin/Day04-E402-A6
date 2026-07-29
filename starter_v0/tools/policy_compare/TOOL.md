---
name: policy_compare
track: team_authored
kind: deterministic_analysis
requires_env: []
inputs: [policy_sections, comparison_focus]
outputs:
  - shared_topics
  - section_summaries
  - combined_requirements
  - permissions
  - possible_tensions
  - focus_coverage
  - sources
side_effect: false
---

# policy_compare

Compares at least two policy sections already returned by `policy` or supplied
by the user. It does not search the knowledge base.

## Use when

- The user asks to compare two or more internal policies.
- Several policy search results need one evidence-based requirements view.
- Retrieved sections may overlap and need a manual-review flag.

## Do not use when

- Fewer than two policy sections are available.
- The policy search has not happened yet; call `policy` first.
- The user expects a legal conclusion.

## Input

`policy_sections` accepts native `policy` result fields:

- `doc_id`
- `policy_area`
- `title`
- `section`
- `facts`
- `source`
- `effective_date`

For user-supplied items, `content` or `text` may replace `facts`.

`comparison_focus` is an optional phrase describing the issue to compare.

## Guardrails

- Uses only supplied evidence.
- Preserves an `evidence_id` for every rule and source.
- Does not invent missing policy text.
- Labels possible conflicts as `manual_review_required`.
- Does not perform network calls or external writes.
