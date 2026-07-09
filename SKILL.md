---
name: growth-percentile
description: Computes pediatric growth percentiles and z-scores (weight-for-age, length/height-for-age, weight-for-length/stature, BMI-for-age, head-circumference-for-age) against CDC and WHO growth standards, from a patient's measurements, and can render an interactive growth chart from the results. Use when asked to calculate, interpret, or check a child's growth percentile, z-score, or position on a growth chart, to plot/visualize a child's growth, or to assess/summarize growth for a pediatric patient given a FHIR bundle, a Synthea export, or a table of weight/height/head-circumference measurements. Do not use for adult BMI, for condition-specific growth charts (e.g. Down syndrome, Turner syndrome), or for growth-velocity/trend analysis across visits.
---

# Growth percentile calculation

This skill computes CDC/WHO growth percentiles from raw patient
measurements. **You never compute the percentile or z-score yourself** —
all arithmetic runs in `scripts/growth.py`, a frozen, tested, deterministic
engine. Your job is orchestration: get the data into the canonical shape,
call the engine, then interpret and present what it returns.

All commands below are run from this skill's own directory (`cd` into it
first if your shell is elsewhere). Everything here is pure Python standard
library (Python 3.11+) — no install step, no virtual environment, no
network access. Whatever `python3` is already on the machine running you
is enough; there is nothing to download or set up first.

## 1. Get the data into canonical shape

The end user should never have to reshape their own data, write code, or
run a command themselves. You do the conversion; they just hand you a file
or describe the patient.

**Known formats, use the adapter directly:**

| Input looks like | Adapter | Command |
|---|---|---|
| A FHIR R4 `Bundle` JSON file (one `Patient` + `Observation` resources) | `adapters/fhir_r4.py` | `python3 adapters/fhir_r4.py bundle.json > records.json` |
| Synthea's flat CSV export (`patients.csv` + `observations.csv`) | `adapters/synthea.py` | `python3 adapters/synthea.py patients.csv observations.csv [patient_id] > records.json` |
| A spreadsheet/CSV already using the canonical column names below | `adapters/flat.py` | `python3 adapters/flat.py measurements.csv > records.json` (or `.json`) |

**Everything else, interpret it yourself.** A spreadsheet with different
column names, mixed units, a pasted table, a PDF-extracted table, or raw
values typed into the conversation (e.g. "my son is 14 months old, born
2024-11-02, weighs 9.8kg and is 76cm") all end up the same way: you read
whatever you were given and construct canonical records matching the
schema below, converting weight/height/length to `kg`/`cm` and computing
age in months if only dates are given. If the mismatch is just column
names on an otherwise well-shaped spreadsheet, `adapters/flat.py --map
colmap.json` (see `CONTRIBUTING.md`) can do the rename for you; for
anything less regular, write the canonical JSON yourself and feed it
straight to `scripts/growth.py`.

**Sex/gender column:** the header might be `sex` or `gender`; values
might be `male`/`female`, `M`/`F`, or an explicit unknown marker
(`U`, `unknown`, blank). Map recognizable values to the canonical
`"male"`/`"female"` yourself, don't require an exact match. If sex is
genuinely missing or unresolvable for a record, ask the user rather than
guessing; a wrong guess silently selects the wrong sex-specific reference
table, and don't invent a value just because there's an "unknown" option.
Birth date and measurement date are the same: don't guess, ask if
missing, since the engine cannot proceed without them.

If you're unsure which adapter applies, ask the user rather than guessing
the format; a FHIR bundle and a Synthea CSV pair look nothing alike, but
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
python3 scripts/growth.py records.json
```

This prints a JSON list of `GrowthResult` objects, one per indicator per
visit (plus a derived BMI-for-age result if weight and height/length were
both present but BMI wasn't supplied directly — flagged `bmi_derived`).
Each result has: `reference` (`WHO` or `CDC`, auto-selected by age —
0-<24 months uses WHO, 24 months-20 years uses CDC), `indicator`,
`z_score`, `percentile`, `flags`, and `provenance` (exact data file and
formula used, for audit).

## 2a. Optional: visualize the results

If the user wants a chart, or a patient has several visits and a visual
would help, run:

```bash
python3 scripts/chart.py records_output.json --out-dir charts/
```

This produces one self-contained, interactive HTML file per patient
(open it in a browser — no server, no internet connection needed) with
percentile curves and the patient's own trajectory. It only covers the
age-based indicators (weight/length/height/BMI/head-circumference-for-age)
— not weight-for-length or weight-for-stature yet. Offer this as an
addition to the numeric summary, not a replacement for it.

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
  correct for prematurity, apply condition-specific charts, or compute
  growth velocity/trend across visits (see scope note in the frontmatter
  above and `references/METHODOLOGY.md` §6-7). If asked for any of these,
  say plainly that it's out of scope for this skill and stop there —
  **do not perform the calculation yourself as a "supplementary" or
  "manual" addition, even with caveats.** A caveated ad hoc calculation
  (e.g. hand-computing cm/month between visits, or eyeballing an
  acceleration/deceleration trend) is still an uncited, untested number
  presented alongside the engine's audited ones, and defeats the purpose
  of this skill. If it would genuinely help, you may report the raw
  per-visit values and percentiles and let the user or a clinician draw
  their own trend conclusions — that is different from computing and
  asserting a trend/velocity metric yourself.

## Reference material (read on demand, not preloaded)

- `references/METHODOLOGY.md` — exact formulas, WHO/CDC selection rule,
  extended BMI, modified z-score/BIV cutoffs, interpolation, prematurity handling.
- `references/CANONICAL_SCHEMA.md` — full `MeasurementRecord`/`GrowthResult` field spec.
- `references/LOINC_MAP.md` — LOINC code mapping used by the FHIR/Synthea adapters.
- `references/DATA_SOURCES.md` — provenance and checksums for every CDC/WHO data file.
