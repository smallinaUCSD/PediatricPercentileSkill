# growth-percentile-skill

An open-source **Agent Skill** that computes pediatric growth percentiles
and z-scores from patient measurements, against the CDC and WHO growth
standards — using frozen, tested, deterministic code, not model arithmetic.

> Point any skill-compatible agent at this repo, hand it a patient's
> measurements (FHIR bundle, Synthea export, or a plain table), and it
> returns auditable growth percentiles with full provenance back to the
> source data row.

## Status

Phase 1 complete: the calculation engine (`scripts/growth.py`) is
implemented and tested against real CDC/WHO data with a frozen golden
suite (31 tests, all passing). Adapters (FHIR R4, Synthea, flat) and
`SKILL.md` are not implemented yet — see `references/` for the locked
design and the project plan for the phased roadmap.

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

```bash
echo '[{"patient_id":"demo","sex":"male","birth_date":"2020-01-01","observation_date":"2020-10-15","metric":"weight","value":9.7,"unit":"kg"}]' > /tmp/records.json
uv run scripts/growth.py /tmp/records.json
```

## License

MIT — see `LICENSE`.
