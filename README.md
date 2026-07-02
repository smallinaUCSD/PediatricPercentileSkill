# growth-percentile-skill

An open-source **Agent Skill** that computes pediatric growth percentiles
and z-scores from patient measurements, against the CDC and WHO growth
standards — using frozen, tested, deterministic code, not model arithmetic.

> Point any skill-compatible agent at this repo, hand it a patient's
> measurements (FHIR bundle, Synthea export, or a plain table), and it
> returns auditable growth percentiles with full provenance back to the
> source data row.

## Status

v0.1.0. The calculation engine (`scripts/growth.py`), the three ingestion
adapters (`adapters/fhir_r4.py`, `adapters/synthea.py`, `adapters/flat.py`),
`SKILL.md`, a Claude Code plugin manifest, an end-to-end demo
(`demo/warren_synthea.md`), and an agent-behavioral eval suite (`evals/`,
`EVALUATION.md`) are implemented and tested (68 unit/integration tests,
all passing) — including against real Synthea-generated FHIR and CSV
fixtures, not synthetic-looking hand-written ones. See `references/` for
the locked design and `CHANGELOG.md` for what shipped in each phase.

## Installation

**As a Claude Code plugin** (recommended — gives you `/plugin update`):

```
/plugin marketplace add smallinaUCSD/PediatricPercentileSkill
/plugin install growth-percentile@growth-percentile-skill
```

**As a raw skill**, for any skill-compatible agent: drop this repo's
folder into the agent's skills directory (e.g. `~/.claude/skills/`) —
`SKILL.md` is discovered automatically. See `SKILL.md` for the workflow
an agent follows, and `demo/warren_synthea.md` for a full worked example.

Either way, the underlying engine needs [`uv`](https://docs.astral.sh/uv/)
on the machine that runs it (see Development setup below) — the plugin/skill
install step does not bundle a Python environment.

## Why

Existing open-source growth tools (R `anthro`, `zscorer`, `pygrowup`, WHO
igrowup) are libraries: a developer imports them and writes code. This is
instead a `SKILL.md`-based capability an LLM agent discovers and uses
directly, with the arithmetic delegated to a small, frozen, unit-tested
Python engine that never enters the model's context.

## Design

- **Deterministic engine, not model math.** All LMS-transform arithmetic
  runs in `scripts/growth.py`, tested against frozen golden vectors.
- **Ingestion decoupled from calculation.** A single canonical
  `MeasurementRecord` schema (`references/CANONICAL_SCHEMA.md`) is the
  only contract the engine understands; adapters (FHIR R4, Synthea, flat
  CSV/JSON) map real-world sources into it.
- **Correctness proven, not asserted.** Golden test vectors from
  independent authoritative sources, protected from modification by
  CODEOWNERS + a fixture checksum gate, plus an agent-behavioral eval.

See `references/METHODOLOGY.md` for the exact formulas and clinical
decision rules (WHO vs CDC selection, extended BMI-for-age, prematurity
handling).

## Development setup

Requires [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync          # creates .venv and installs dependencies
uv run pytest    # run the test suite
```

## Trying it out

Directly, with a hand-written record:

```bash
echo '[{"patient_id":"demo","sex":"male","birth_date":"2020-01-01","observation_date":"2020-10-15","metric":"weight","value":9.7,"unit":"kg"}]' > /tmp/records.json
uv run scripts/growth.py /tmp/records.json
```

Through an adapter, with a real Synthea-generated patient (see
`tests/fixtures/README.md` for provenance):

```bash
uv run adapters/fhir_r4.py tests/fixtures/synthea_fhir_bundle.json > /tmp/records.json
uv run scripts/growth.py /tmp/records.json

uv run adapters/synthea.py tests/fixtures/synthea_patients.csv tests/fixtures/synthea_observations.csv > /tmp/records.json
uv run scripts/growth.py /tmp/records.json
```

## Evaluation

`EVALUATION.md` documents an agent-behavioral eval suite — five scenarios
run against real Claude subagents (not just the engine's own unit tests)
checking whether an agent *using this skill* picks the right adapter,
reports the right numbers, and correctly surfaces edge cases (missing
data, implausible values, out-of-scope requests) rather than guessing or
computing outside the audited engine. Re-run with:

```bash
uv run evals/run_eval.py --all
```

## Contributing

See `CONTRIBUTING.md` — in particular, `tests/golden/` and `references/data/`
are frozen and CODEOWNER-protected; read that file before touching either.

## Disclaimer

This tool computes growth percentiles; it does not diagnose, and it is
not a substitute for clinical judgment. It has not been evaluated or
cleared by any regulatory body (e.g. FDA) as a medical device. v1
deliberately does not correct for prematurity, apply condition-specific
growth charts, or compute growth velocity — see `references/METHODOLOGY.md`
for the full list of what's in and out of scope. Percentile results should
be reviewed by a qualified clinician, especially for `implausible_value`
or `reference_unavailable` flagged results.

## Citation

See `CITATION.cff`.

## License

MIT — see `LICENSE`.
