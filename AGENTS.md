# AGENTS.md

Instructions for any coding agent working *on* this repository (not to be
confused with [`SKILL.md`](SKILL.md), which is what an agent reads to
*use* this project as a skill).

## What this is

A deterministic engine (`scripts/growth.py`) that computes CDC/WHO
pediatric growth percentiles, plus ingestion adapters (`adapters/`) and
an Agent Skill wrapper (`SKILL.md`). The one rule that shapes everything
else: **the model never does the arithmetic.** If you're tempted to
compute or approximate a percentile, z-score, or LMS parameter yourself
instead of running the engine, don't — see
[references/METHODOLOGY.md](references/METHODOLOGY.md) for why, and
[EVALUATION.md](EVALUATION.md) for a real case where an agent violated
this and got caught.

## Commands

```bash
uv sync                       # install deps
uv run pytest                 # full test suite (must pass before any PR)
uv run evals/run_eval.py --all   # agent-behavioral eval suite
claude plugin validate .      # validate .claude-plugin/ manifests
```

No lint/format tooling is configured yet — don't invent one unilaterally.

## Hard constraints (not enforced by CI beyond the checksum gate)

- **Never edit files under [`tests/golden/`](tests/golden/)** to make a
  failing test pass. A failing golden test means the engine changed
  incorrectly, not that the fixture is wrong. See
  [CONTRIBUTING.md](CONTRIBUTING.md) for the full policy and the
  checksum-regeneration step if a change is legitimately warranted.
- **`scripts/growth.py` and `adapters/` stay deterministic and offline.**
  No network calls, no `datetime.now()`/system-locale dependence, no
  randomness.
- **Adapters output plain dicts, not engine objects.** They must not
  import `scripts/growth.py`'s calculation internals — see "Adding an
  adapter" in [CONTRIBUTING.md](CONTRIBUTING.md) for why.
- **Changes to `references/data/*.csv`** require updating the matching
  row in [references/DATA_SOURCES.md](references/DATA_SOURCES.md) (new
  checksum, retrieval date) in the same commit.
- **A version bump touches four files at once** — see
  [RELEASING.md](RELEASING.md).

## Domain vocabulary (so you don't have to reverse-engineer it from code)

- **LMS method**: Cole's transform, the same math CDC/WHO use to publish
  growth charts. `L`, `M`, `S` are per-sex-per-age parameters looked up
  from `references/data/*.csv`.
- **Indicator**: e.g. `weight_for_age`, `bmi_for_age`,
  `weight_for_length` — one canonical output type per measurement type.
- **The WHO/CDC handoff**: WHO 2006 standards for ages 0–<24 months, CDC
  2000/2022 for 24 months–20 years, selected automatically by age. This
  boundary is the single most-tested edge case in the repo — see
  `tests/golden/vectors.json` for why.
- **Flags**: `implausible_value`, `reference_unavailable`,
  `corrected_age_recommended`, `extended_bmi_used`, `bmi_derived` — see
  [references/CANONICAL_SCHEMA.md](references/CANONICAL_SCHEMA.md) for
  what each means. These are load-bearing, not cosmetic — don't drop
  them when refactoring output formatting.

## Where to look before assuming something is missing

- Full schema: [references/CANONICAL_SCHEMA.md](references/CANONICAL_SCHEMA.md)
- Formulas and clinical decision rules: [references/METHODOLOGY.md](references/METHODOLOGY.md)
- What's deliberately out of scope in v1 (don't "fix" these without discussion): [references/METHODOLOGY.md](references/METHODOLOGY.md) §6-7
- PR process and ground rules: [CONTRIBUTING.md](CONTRIBUTING.md)
