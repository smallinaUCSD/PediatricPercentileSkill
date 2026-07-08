# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed
- `scripts/chart.py` printed a confusing second set of percentile
  labels mid-chart whenever a panel had more than one curve segment
  (e.g. weight-for-age for a patient whose record crosses 24 months
  has a WHO segment ending at 24mo and a CDC segment continuing
  further) -- every segment's endpoint got its own label instead of
  only the chart's true right edge. Now only the rightmost segment is
  labeled. Found by user inspection of the rendered chart, not caught
  by the earlier visual verification pass.
- Charts were too small to read comfortably; increased the SVG
  dimensions, margins, font sizes, and display width. Regenerated
  `assets/growth-chart-example.png` and `demo/warren_chart_example.png`
  to reflect both fixes.

### Added
- `evals/scorer.py`'s `json_block` scoring gained an optional
  `check_prose_consistency` flag: cross-checks any "Xth percentile"
  claim in an agent's prose against its own appended JSON block, so a
  correct JSON paired with a different stated number to the human reader
  is caught. Enabled on `s1`/`s2`. First run caught a fidelity bug in
  `evals/responses/s1_fhir_happy_path.txt` itself (an earlier manual
  excerpt to 8 of the real 44 entries broke consistency with the
  prose, which was written against the full set) -- fixed by restoring
  the complete response; see `EVALUATION.md`.

### Fixed (LLM-agnostic audit)
- `AGENTS.md`'s "Commands" section listed `claude plugin validate .`
  alongside universally-runnable commands (`uv sync`, `uv run pytest`)
  with no caveat, in a file whose entire stated purpose is being
  canonical for *any* agent. Moved it to its own note explaining it's
  Claude Code-specific. No other Claude-specific assumptions found in
  `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, or any adapter/engine code --
  Claude Code mentions elsewhere (README's install section, `RELEASING.md`'s
  plugin-verification steps, `CONTRIBUTING.md`'s release checklist) are
  already correctly scoped to the one thing that's genuinely Claude
  Code-specific: validating the `.claude-plugin/` manifests themselves.

### Fixed
An 8-angle code review (correctness, removed-behavior, cross-file,
reuse, simplification, efficiency, altitude, conventions -- run as
parallel independent passes, then verified) of the v0.2.0 diff found and
verified 7 real issues, all fixed here:

- **`scripts/chart.py` silently omitted a valid percentile curve.** The
  length/height-for-age panel assumed `length_for_age` only ever uses
  the WHO standard, but the engine's default (non-override) selection
  produces `CDC`/`length_for_age` for any recumbent-length measurement
  at 24-36 months (`cdc_lenageinf.csv` covers 0-36mo) -- an ordinary,
  unremarkable case, not an edge case. Fixed by deriving which
  (indicator, standard) pairs get a curve from what actually appears in
  the patient's own results, instead of a hardcoded assumption that can
  drift from the engine's real behavior.
- `scripts/chart.py` crashed with `TypeError` when a result was flagged
  `reference_unavailable` (`percentile`/`z_score` are `None` in that
  case) -- now renders the point with a "reference unavailable" tooltip
  instead of a formatted percentile.
- `scripts/chart.py` interpolated `patient_id` unescaped into HTML, so a
  patient ID containing markup (from an untrusted FHIR/CSV source) could
  inject content into the locally-opened chart file. Now HTML-escaped.
- `scripts/chart.py`'s table selection reimplemented (and subtly
  under-specified, missing an age-coverage check) `growth._select_table`
  in a second place; now calls it directly.
- `scripts/growth.py`'s repeated-header-row skip (added in v0.2.0)
  detected the sentinel row by comparing against the *first* CSV column,
  which only worked because the sex column happens to be first in every
  current file. Now compares against the sex column's own header
  regardless of position.
- `adapters/flat.py`'s `--map` flag crashed with an unhandled
  `AttributeError` if the JSON file wasn't an object; now raises the
  same `AdapterError` every other bad-input path in the module uses.
- `adapters/flat.py` treated a legitimate falsy value (e.g. `value: 0`)
  as a missing required field; now checks for `None`/empty-string
  explicitly.

Regression tests added for all seven in `tests/test_chart.py`,
`tests/test_adapters.py`, and `tests/test_engine.py`.

## [0.2.0] - 2026-07-08

### Added
- `AGENTS.md` — canonical instructions for any coding agent working on
  this repo (build/test commands, hard constraints, domain vocabulary);
  `CLAUDE.md` is now a one-line `@AGENTS.md` pointer so the two don't
  drift apart.
- `RELEASING.md` — the release checklist, expanded out of a one-line
  note that used to live in `CONTRIBUTING.md`.
- `.github/PULL_REQUEST_TEMPLATE.md` and `.github/ISSUE_TEMPLATE/`
  (bug report + feature request) — contributing was previously prose-only
  with no scaffolding.
- A "Pull requests" section in `CONTRIBUTING.md` spelling out the actual
  PR process (branch, test, CI, CODEOWNER review, small-PR guidance).
- `scripts/chart.py` — self-contained, interactive HTML growth chart
  generator. One file per patient, percentile curves (3rd-97th, reusing
  the engine's own reference tables so a curve and a patient's own
  percentile always come from the same source row) plus the patient's
  trajectory, for every age-based indicator present. Pure SVG + vanilla
  JS for hover tooltips — no charting library, no CDN, no new Python
  dependency, works fully offline. Does not yet cover weight-for-length
  or weight-for-stature (documented limitation, not silently dropped).
  `WHO_CDC_HANDOFF_MONTHS` constant added to `scripts/growth.py` so the
  chart's curve-clamping and the engine's reference selection can't
  drift out of sync. `tests/test_chart.py` (12 tests).
- `adapters/flat.py` accepts an optional column map (`--map colmap.json`
  on the CLI, or `column_map=` as a library) so a spreadsheet with
  differently-named columns (e.g. `DOB`, `Weight (kg)`) doesn't need to
  be renamed first — only the columns that differ need an entry in the
  map. 4 new tests in `tests/test_adapters.py`.

### Fixed
- `cdc_lenageinf.csv` and `cdc_bmiagerev.csv` contain a repeated header
  row at the male/female transition, which is how CDC actually publishes
  these two files (not a corruption of our copy) but crashed
  `scripts/growth.py`'s CSV parser whenever that exact combination was
  hit — which nothing had exercised until building the chart feature
  surfaced it. Fixed in `_load_table`; added
  `cdc_length_for_age_explicit_override_12_5mo` to
  `tests/golden/vectors.json` to close the coverage gap that let it hide.

### Changed
- README rewritten for a human-first, agent-agnostic flow: install
  (Claude Code plugin, or any agent that reads `SKILL.md` directly) →
  first result (a plain-English prompt, no terminal) → bring-your-own-data
  → how it works → limitations, with terminal/`uv run` commands moved out
  to `CONTRIBUTING.md`. All internal doc references are now clickable
  relative links instead of plain backticked paths.
- Clarified that `age_months` can be supplied directly or derived from
  `birth_date`/`observation_date` — this already worked, it just wasn't
  documented as a deliberate either/or choice.

### Removed
- A stray `records.json` left at the repo root from manual testing.

## [0.1.0] - 2026-07-02

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
- `demo/warren_synthea.md` — end-to-end walkthrough (raw FHIR bundle ->
  adapter -> engine -> presented summary) on a real Synthea patient whose
  record crosses the WHO->CDC boundary and the length/stature switch.
- `evals/` — agent-behavioral eval harness: `scorer.py` (deterministic,
  unit-tested in `tests/test_scorer.py`, 15 tests), `run_eval.py` CLI,
  five scenarios (`evals/scenarios/`) covering happy-path FHIR/Synthea
  ingestion and behavioral edge cases (missing required field,
  implausible-value flagging, out-of-scope request), and committed real
  captured responses (`evals/responses/`).
- `EVALUATION.md` — results of running the eval suite against real
  subagents: 4/5 passed on the first run; the failure (an agent
  hand-computing out-of-scope growth-velocity math despite a caveat)
  led to a `SKILL.md` guardrail fix, re-verified to pass. Both the
  original failing response and the fixed passing response are committed
  for auditability.
- `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` —
  installable as a Claude Code plugin (`/plugin marketplace add
  smallinaUCSD/PediatricPercentileSkill`, `/plugin install
  growth-percentile@growth-percentile-skill`), in addition to dropping
  the repo into a skills directory directly. Both manifests verified
  against a live install/uninstall cycle, not just schema-checked.
- README installation section, clinical-use disclaimer, and contributing/
  citation pointers for the public v0.1.0 release.
