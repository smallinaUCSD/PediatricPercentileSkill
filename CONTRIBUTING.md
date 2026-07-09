# Contributing

## Setup

```bash
uv sync
uv run pytest
```

## Running it directly (without an agent)

Most people should just ask an agent (see the main [README](README.md)).
This is for development, debugging, or anyone who prefers a terminal.

A hand-written record:

```bash
echo '[{"patient_id":"demo","sex":"male","birth_date":"2020-01-01","observation_date":"2020-10-15","metric":"weight","value":9.7,"unit":"kg"}]' > /tmp/records.json
uv run scripts/growth.py /tmp/records.json
```

Through an adapter, with a Synthea-generated (synthetic, not real patient
data) test patient (see
[`tests/fixtures/README.md`](tests/fixtures/README.md) for provenance):

```bash
uv run adapters/fhir_r4.py tests/fixtures/synthea_fhir_bundle.json > /tmp/records.json
uv run scripts/growth.py /tmp/records.json

uv run adapters/synthea.py tests/fixtures/synthea_patients.csv tests/fixtures/synthea_observations.csv > /tmp/records.json
uv run scripts/growth.py /tmp/records.json
```

Re-running the agent-behavioral eval suite:

```bash
uv run evals/run_eval.py --all
```

## Opening a pull request

1. Fork the repo, branch off `main` (any branch name is fine — there's
   no enforced naming convention).
2. Make your change. `uv run pytest` should pass locally before you push.
3. Open the PR against `main`. The template will prompt you for what
   changed, why, and how you tested it — fill it in, don't delete it.
4. CI runs the full test suite plus the [`tests/golden/`](tests/golden/)
   checksum gate ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).
   A red check means something real, not a flake — this repo has no CI
   flakiness by design (offline, deterministic).
5. If your PR touches [`tests/golden/`](tests/golden/) or
   [`references/data/`](references/data/), a CODEOWNER review is required
   automatically ([`.github/CODEOWNERS`](.github/CODEOWNERS)) — see the
   ground rules below for what that review is looking for.
6. Small, focused PRs get reviewed faster. A PR that both adds a feature
   and reformats unrelated files is harder to review and more likely to
   get punted back.

## Ground rules

- **[`tests/golden/`](tests/golden/) is frozen.** These are reference
  vectors sourced from independent authoritative publications (CDC worked
  examples, published clinical analysis plans) or cross-checked against
  an established reference implementation. Do not edit expected values in
  this directory to make a failing test pass — a failing golden test
  means the engine changed, not that the fixture is wrong. Changes to
  this directory require a CODEOWNER review
  ([`.github/CODEOWNERS`](.github/CODEOWNERS)) and a rationale (source
  citation) in the PR description. Every vector already carries a
  `citation` field explaining where its expected numbers come from — a
  new or changed vector needs one too. If you legitimately change
  `vectors.json` or `formula_examples.json`, regenerate the checksum
  manifest in the same commit: `uv run python3
  tests/golden/generate_checksums.py`. CI runs `sha256sum -c
  tests/golden/CHECKSUMS.sha256` and fails the build if the fixtures and
  manifest disagree, so an edit that skips this step is caught even if
  the PR author forgets to flag it for review.
- **Agents modifying this repo:** never edit files under
  [`tests/golden/`](tests/golden/). If your change causes a golden test
  to fail, that is a signal to fix the engine or ask a human to review
  the fixture, not to update the expected value yourself.
- **The engine stays deterministic and offline.** No network calls, no
  reliance on system time/locale, no randomness, in
  [`scripts/growth.py`](scripts/growth.py) or [`adapters/`](adapters/).
- Changes to [`references/data/`](references/data/)`*.csv` must update
  the corresponding row in
  [`references/DATA_SOURCES.md`](references/DATA_SOURCES.md) in the same
  commit (new checksum, retrieval date) and go through CODEOWNER review,
  since they can silently change every downstream percentile.

## Adding an adapter

New ingestion sources should map into the canonical `MeasurementRecord`
shape ([`references/CANONICAL_SCHEMA.md`](references/CANONICAL_SCHEMA.md))
and live under [`adapters/`](adapters/). They output plain
JSON-serializable dicts matching that schema (not a Python object
imported from the engine) and must not import or depend on
[`scripts/growth.py`](scripts/growth.py)'s calculation internals — this
keeps ingestion and calculation chainable purely through JSON, the same
way an agent invokes them (adapter CLI output piped into `growth.py`'s
CLI input), and keeps the engine's test surface
([`tests/golden/`](tests/golden/)) independent of adapter code.

## Adding an eval scenario

See [`EVALUATION.md`](EVALUATION.md) and
[`evals/scenarios/`](evals/scenarios/) for the schema. Expected values in
a scenario's `scoring` block should be computed by actually running
`scripts/growth.py` on the scenario's input (not hand-derived), same
standard as [`tests/golden/`](tests/golden/), even though
[`evals/`](evals/) isn't CODEOWNER-protected the same way. Capture a real
agent's response into `evals/responses/<id>.txt` before claiming a
scenario passes — a scenario with no captured response is untested, not
passing.

## Releasing

See [RELEASING.md](RELEASING.md) for the full process. Short version:
version is declared in four places and should move together —
[`pyproject.toml`](pyproject.toml), [`CITATION.cff`](CITATION.cff),
[`.claude-plugin/plugin.json`](.claude-plugin/plugin.json), and the
matching entry in
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json).
Update [`CHANGELOG.md`](CHANGELOG.md) in the same commit. `claude plugin
validate .` should pass before tagging.
