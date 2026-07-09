# Trust and limitations

This page is for contributors and clinicians who want to know exactly what
this tool does and doesn't do, and how its output is verified. If you just
want to use the skill, see [README.md](README.md) instead.

## Scope (v1)

In scope: weight-for-age, length/height-for-age, weight-for-length/stature,
BMI-for-age, and head-circumference-for-age percentiles and z-scores, ages
0-20, with automatic WHO/CDC reference-standard selection.

Deliberately **not** in scope yet, and clearly flagged when relevant rather
than silently approximated or estimated by the agent:

- Prematurity/gestational-age correction (flagged via `corrected_age_recommended`, not computed)
- Condition-specific growth charts (Down syndrome, Turner syndrome, etc.)
- Growth velocity / trend analysis across visits
- Weight-for-length/stature charting (numeric output only for those two indicators; see [What it can do](README.md#what-it-can-do))

See [references/METHODOLOGY.md](references/METHODOLOGY.md) §6-7 for the
full technical detail on each of these.

## Clinical disclaimer

This tool computes percentiles; it does not diagnose, and it is not a
substitute for clinical judgment. It has not been evaluated or cleared by
any regulatory body (e.g. FDA) as a medical device. Percentile results
should be reviewed by a qualified clinician, especially anything flagged
`implausible_value` or `reference_unavailable`.

## How the output is verified

- **Golden test suite:** 85 tests, all checked against real CDC/WHO data
  files or CDC's own published worked examples, not invented numbers.
  Frozen and CODEOWNER-protected (`tests/golden/`); see
  [CONTRIBUTING.md](CONTRIBUTING.md).
- **Agent-behavioral eval:** [EVALUATION.md](EVALUATION.md) documents
  running real Claude subagents through test scenarios to check whether
  an agent *using this skill* behaves correctly, not just whether the
  engine's math is right. One scenario failed on the first real run (an
  agent hand-computed an out-of-scope number with a caveat attached); the
  fix and re-verification are documented there too.
- **Every result carries provenance.** Each percentile traces back to an
  exact data file and formula (see `references/DATA_SOURCES.md` and
  `references/METHODOLOGY.md`), so a clinician or auditor can check the
  engine's work rather than trusting a black box.
