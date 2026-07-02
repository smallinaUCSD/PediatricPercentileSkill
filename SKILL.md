---
name: growth-percentile
description: Computes pediatric growth percentiles and z-scores (weight-for-age, length/height-for-age, weight-for-length/stature, BMI-for-age, head-circumference-for-age) against CDC and WHO growth standards, from a patient's measurements. Use when asked to calculate, interpret, or check a child's growth percentile, z-score, or position on a growth chart, or to assess/summarize growth for a pediatric patient given a FHIR bundle, a Synthea export, or a table of weight/height/head-circumference measurements. Do not use for adult BMI, for condition-specific growth charts (e.g. Down syndrome, Turner syndrome), or for growth-velocity/trend analysis across visits.
---

# Growth percentile calculation

This skill computes CDC/WHO growth percentiles from raw patient
measurements. **You never compute the percentile or z-score yourself** —
all arithmetic runs in `scripts/growth.py`, a frozen, tested, deterministic
engine. Your job is orchestration: get the data into the canonical shape,
call the engine, then interpret and present what it returns.

All commands below are run from this skill's own directory (`cd` into it
first if your shell is elsewhere). First time only: `uv sync`.

## 1. Identify the input and pick an adapter

| Input looks like | Adapter | Command |
|---|---|---|
| A FHIR R4 `Bundle` JSON file (one `Patient` + `Observation` resources) | `adapters/fhir_r4.py` | `uv run adapters/fhir_r4.py bundle.json > records.json` |
| Synthea's flat CSV export (`patients.csv` + `observations.csv`) | `adapters/synthea.py` | `uv run adapters/synthea.py patients.csv observations.csv [patient_id] > records.json` |
| A plain table/spreadsheet, or data you already have in hand | `adapters/flat.py` | `uv run adapters/flat.py measurements.csv > records.json` (or `.json`) |

If the user hands you raw values in conversation (e.g. "my son is 14 months
old, born 2024-11-02, weighs 9.8kg and is 76cm") rather than a file, skip
the adapter: write a small JSON file yourself matching the flat schema
below and feed it straight to `scripts/growth.py`. Don't guess a
patient's sex, birth date, or measurement date — ask if any are missing;
these are required fields and the engine cannot proceed without them.

If you're unsure which adapter applies, ask the user rather than guessing
the format — a FHIR bundle and a Synthea CSV pair look nothing alike, but
a generic "spreadsheet of measurements" could plausibly be reshaped into
the flat schema either way.

**Canonical record shape** (what every adapter outputs, and what
`flat.py`/hand-written JSON must already match): `patient_id`, `sex`
(`"male"`/`"female"`), `birth_date`, `observation_date` (ISO `YYYY-MM-DD`),
`metric` (`weight` | `height_standing` | `length_recumbent` |
`head_circumference` | `bmi`), `value`, `unit` (`kg`/`lb` for weight,
`cm`/`in` for length/height/head circumference, `kg/m2` for BMI). One
record per metric per visit — a single visit with weight, height, and
head circumference is three records. Full spec, including optional
`age_months`/`gestational_age_weeks` overrides: `references/CANONICAL_SCHEMA.md`.

If you're not sure whether a measurement is recumbent length or standing
height, don't guess — `metric` selection affects which reference table is
used. See `references/LOINC_MAP.md` ("Length vs. stature ambiguity") for
how the FHIR/Synthea adapters resolve this from LOINC code `8302-2`.

## 2. Run the engine

```bash
uv run scripts/growth.py records.json
```

This prints a JSON list of `GrowthResult` objects, one per indicator per
visit (plus a derived BMI-for-age result if weight and height/length were
both present but BMI wasn't supplied directly — flagged `bmi_derived`).
Each result has: `reference` (`WHO` or `CDC`, auto-selected by age —
0-<24 months uses WHO, 24 months-20 years uses CDC), `indicator`,
`z_score`, `percentile`, `flags`, and `provenance` (exact data file and
formula used, for audit).

## 3. Interpret and present results

- **Always report the reference standard used** (WHO vs CDC) alongside
  the percentile — don't just say "58th percentile," say "58th percentile
  (WHO standard)."
- **`flags` are not optional detail — surface them.** In particular:
  - `implausible_value`: the measurement is a likely data-entry error
    (e.g. a decimal point or unit mistake), per CDC's modified-z-score
    method. Say so plainly and suggest double-checking the raw value —
    don't just report a percentile near 0 or 100 as if it were normal.
  - `reference_unavailable`: no CDC or WHO table covers this
    age/metric/standard combination (e.g. standing height under 24
    months, or head circumference past 36 months — CDC simply doesn't
    publish that chart). Explain *why* rather than presenting a missing
    result as an error; see `references/METHODOLOGY.md` for the exact
    boundaries.
  - `corrected_age_recommended`: the child was preterm and under 24
    months; v1 deliberately does not correct for gestational age (see
    `references/METHODOLOGY.md` §6) — say the percentile is based on
    chronological, not corrected, age, and that a clinician may want to
    interpret it against corrected age instead.
  - `extended_bmi_used`: BMI is at/above the 95th percentile for age, so
    CDC's 2022 extended method was used instead of the ordinary chart
    (which compresses at extreme values). Percentile is still directly
    comparable to lower values.
  - `bmi_derived`: BMI wasn't in the source data; it was computed from a
    paired weight + height/length at the same visit. Mention this so the
    user knows it's not a directly-measured BMI observation.
- **Never recompute or sanity-check a percentile by doing the math
  yourself.** If a result looks surprising, re-check your input data (units,
  dates, sex) rather than adjusting the engine's output.
- For multiple visits, a clean per-visit table (age, indicator, value,
  percentile, reference, flags) is usually the most useful presentation.

## 4. Guardrails

- Do not edit anything under `tests/golden/` or `references/data/` — these
  are frozen, cited, CODEOWNER-protected reference data and test vectors
  (see `CONTRIBUTING.md`). If a calculation looks wrong, the bug is
  elsewhere; ask a human before touching either directory.
- Do not invent LMS parameters, percentiles, or z-scores yourself under
  any circumstances, including when the engine returns
  `reference_unavailable` or errors out. Report the gap; don't fill it in.
- This skill computes percentiles; it does not diagnose, and v1 does not
  correct for prematurity or apply condition-specific charts (see scope
  note in the frontmatter above and `references/METHODOLOGY.md` §6-7).
  Say so if asked for something out of scope rather than approximating it.

## Reference material (read on demand, not preloaded)

- `references/METHODOLOGY.md` — exact formulas, WHO/CDC selection rule,
  extended BMI, modified z-score/BIV cutoffs, interpolation, prematurity handling.
- `references/CANONICAL_SCHEMA.md` — full `MeasurementRecord`/`GrowthResult` field spec.
- `references/LOINC_MAP.md` — LOINC code mapping used by the FHIR/Synthea adapters.
- `references/DATA_SOURCES.md` — provenance and checksums for every CDC/WHO data file.
