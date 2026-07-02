# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Repo scaffold: uv-managed Python project, directory layout, MIT license.
- `references/CANONICAL_SCHEMA.md` — canonical `MeasurementRecord` /
  `GrowthResult` contract.
- `references/METHODOLOGY.md` — LMS formulas, WHO/CDC reference selection,
  extended BMI-for-age, prematurity flag-only decision.
- `references/DATA_SOURCES.md` — data file provenance tracking (files not
  yet downloaded).
- `references/LOINC_MAP.md` — LOINC code to canonical metric mapping.
- `references/data/` — real CDC 2000/2022-extended-BMI and WHO Child
  Growth Standards LMS reference tables, with checksummed provenance.
- `scripts/growth.py` — deterministic engine: LMS transform, WHO/CDC
  auto-selection, L/M/S interpolation, extended BMI-for-age, CDC modified
  z-score plausibility flagging, prematurity flag, unit conversion,
  weight-for-length/stature pairing, derived-BMI, JSON CLI.
- `tests/golden/` — frozen, cited golden vectors (engine-level and pure
  formula) plus a checksum manifest; `tests/test_engine.py` (31 tests).
- `.github/CODEOWNERS` and `.github/workflows/ci.yml` — golden-fixture
  checksum gate + test suite in CI.
- `adapters/fhir_r4.py`, `adapters/synthea.py` (Synthea CSV export),
  `adapters/flat.py` (CSV/JSON escape hatch), and shared helpers in
  `adapters/_common.py` — including the age-based heuristic for
  resolving LOINC `8302-2` ("Body height") to `length_recumbent` vs.
  `height_standing`, needed because real-world exports (Synthea
  included) don't reliably use the recumbent-length-specific code.
- `tests/fixtures/` — real Synthea-generated FHIR R4 and CSV patient data
  (not hand-written) used to test the adapters; `tests/test_adapters.py`
  (22 tests).
- `SKILL.md` — the agent-facing workflow: input detection, adapter
  selection, calling the engine, and how to interpret/present each flag.
