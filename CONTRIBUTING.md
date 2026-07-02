# Contributing

## Setup

```bash
uv sync
uv run pytest
```

## Ground rules

- **`tests/golden/` is frozen.** These are reference vectors sourced from
  independent authoritative publications (CDC worked examples, published
  clinical analysis plans) or cross-checked against an established
  reference implementation. Do not edit expected values in this directory
  to make a failing test pass — a failing golden test means the engine
  changed, not that the fixture is wrong. Changes to this directory
  require a CODEOWNER review (`.github/CODEOWNERS`) and a rationale
  (source citation) in the PR description. Every vector already carries a
  `citation` field explaining where its expected numbers come from — a
  new or changed vector needs one too. If you legitimately change
  `vectors.json` or `formula_examples.json`, regenerate the checksum
  manifest in the same commit: `uv run python3
  tests/golden/generate_checksums.py`. CI runs `sha256sum -c
  tests/golden/CHECKSUMS.sha256` and fails the build if the fixtures and
  manifest disagree, so an edit that skips this step is caught even if
  the PR author forgets to flag it for review.
- **Agents modifying this repo:** never edit files under `tests/golden/`.
  If your change causes a golden test to fail, that is a signal to fix the
  engine or ask a human to review the fixture, not to update the expected
  value yourself.
- **The engine stays deterministic and offline.** No network calls, no
  reliance on system time/locale, no randomness, in `scripts/growth.py` or
  `adapters/`.
- Changes to `references/data/*.csv` must update the corresponding row in
  `references/DATA_SOURCES.md` in the same commit (new checksum, retrieval
  date) and go through CODEOWNER review, since they can silently change
  every downstream percentile.

## Adding an adapter

New ingestion sources should map into the canonical `MeasurementRecord`
shape (`references/CANONICAL_SCHEMA.md`) and live under `adapters/`. They
output plain JSON-serializable dicts matching that schema (not a Python
object imported from the engine) and must not import or depend on
`scripts/growth.py`'s calculation internals — this keeps ingestion and
calculation chainable purely through JSON, the same way an agent invokes
them (adapter CLI output piped into `growth.py`'s CLI input), and keeps
the engine's test surface (`tests/golden/`) independent of adapter code.

## Adding an eval scenario

See `EVALUATION.md` and `evals/scenarios/` for the schema. Expected
values in a scenario's `scoring` block should be computed by actually
running `scripts/growth.py` on the scenario's input (not hand-derived),
same standard as `tests/golden/`, even though `evals/` isn't
CODEOWNER-protected the same way. Capture a real agent's response into
`evals/responses/<id>.txt` before claiming a scenario passes — a scenario
with no captured response is untested, not passing.

## Releasing

Version is declared in four places and should move together:
`pyproject.toml`, `CITATION.cff`, `.claude-plugin/plugin.json`, and the
matching entry in `.claude-plugin/marketplace.json`. Update
`CHANGELOG.md` in the same commit. `claude plugin validate .` should pass
before tagging.
