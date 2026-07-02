# Demo: end-to-end growth percentiles from a raw Synthea FHIR bundle

This walks through the full pipeline — raw FHIR bundle in, audited growth
percentiles out — on a single real patient, exactly as an agent following
`SKILL.md` would run it.

## About this patient

The original project plan named this demo after a specific "Warren"
Synthea patient from an earlier meeting's notes, which weren't available
during implementation. Rather than fabricate a patient matching that
description, this demo uses a real Synthea-generated patient we already
verified end-to-end while building the adapters (`tests/fixtures/synthea_fhir_bundle.json`
— see `tests/fixtures/README.md` for exact provenance). The filename is
kept for continuity with the project plan. She's a good demo patient on
her own merits: her record runs from birth to just under three years old,
so it exercises the WHO→CDC handoff, the length-vs-stature switch, and
derived-BMI mid-record — all in one file.

## The input

A 128KB FHIR R4 `Bundle`: one `Patient` resource (female, born
2016-07-24) plus 81 `Observation` resources spanning 11 visits — most of
them unrelated vitals and labs, which is realistic and exercises the
adapter's LOINC filtering rather than a pre-curated list:

```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    { "resource": { "resourceType": "Patient", "birthDate": "2016-07-24", "gender": "female", "...": "..." } },
    { "resource": { "resourceType": "Observation", "code": {"coding": [{"code": "8302-2", "display": "Body Height"}]}, "effectiveDateTime": "2016-07-24T03:26:48-04:00", "valueQuantity": {"value": 54.325, "unit": "cm"} } },
    "... 80 more Observation resources (weight, BMI, labs, vitals) ..."
  ]
}
```

## Step 1 — ingest

```bash
uv run adapters/fhir_r4.py tests/fixtures/synthea_fhir_bundle.json > records.json
```

The adapter walks all 82 entries, keeps only the `Observation`s carrying a
recognized LOINC code (`references/LOINC_MAP.md`), and resolves each
`8302-2` ("Body Height" — Synthea never uses the recumbent-length-specific
code `8306-3`) to `length_recumbent` or `height_standing` by the patient's
age at that visit. Result: 24 canonical records — 11 weight, 9 recumbent
length (visits under 24 months), 2 standing height (visits at 24+
months), 2 BMI (only present in the source data for the last two visits).

```json
[
  {"patient_id": "2389dd31-...", "sex": "female", "birth_date": "2016-07-24",
   "observation_date": "2016-07-24", "metric": "length_recumbent", "value": 54.325, "unit": "cm"},
  {"patient_id": "2389dd31-...", "sex": "female", "birth_date": "2016-07-24",
   "observation_date": "2016-07-24", "metric": "weight", "value": 3.563, "unit": "kg"},
  "... 22 more records ..."
]
```

## Step 2 — compute

```bash
uv run scripts/growth.py records.json > results.json
```

The engine groups records into visits, computes every applicable
indicator, pairs weight with length/height for weight-for-length or
weight-for-stature, and derives BMI-for-age from weight+length/height for
the nine early visits where BMI wasn't directly recorded. No network
calls, no model arithmetic — every number below is `scripts/growth.py`
reading `references/data/*.csv` and applying the cited LMS formulas.

## Step 3 — present

This is the kind of summary `SKILL.md` asks an agent to produce — age,
indicator, value, percentile, reference standard, and flags, in
chronological order:

| Visit date | Age | Indicator | Value | Percentile | Reference | Flags |
|---|---|---|---|---|---|---|
| 2016-07-24 | 0.0mo | Length-for-age | 54.3 cm | 99.7th | WHO | |
| 2016-07-24 | 0.0mo | Weight-for-age | 3.6 kg | 75.8th | WHO | |
| 2016-07-24 | 0.0mo | Weight-for-length | 3.6 kg | 1.0th | WHO | |
| 2016-07-24 | 0.0mo | BMI-for-age | 12.1 | 14.1th | WHO | derived |
| 2016-08-28 | 1.2mo | Length-for-age | 57.9 cm | 96.7th | WHO | |
| 2016-08-28 | 1.2mo | Weight-for-age | 4.3 kg | 45.3th | WHO | |
| 2016-08-28 | 1.2mo | Weight-for-length | 4.3 kg | 0.7th | WHO | |
| 2016-08-28 | 1.2mo | BMI-for-age | 12.8 | 6.5th | WHO | derived |
| 2016-10-30 | 3.2mo | Length-for-age | 63.0 cm | 89.9th | WHO | |
| 2016-10-30 | 3.2mo | Weight-for-age | 5.5 kg | 27.2th | WHO | |
| 2016-10-30 | 3.2mo | Weight-for-length | 5.5 kg | 2.2th | WHO | |
| 2016-10-30 | 3.2mo | BMI-for-age | 14.0 | 3.8th | WHO | derived |
| ... | | *(visits at 5.3, 8.3, 11.3, 14.3, 17.3, 23.2 months follow the same pattern — full data in `results.json`)* | | | | |
| 2018-12-30 | 29.2mo | Height-for-age | 93.5 cm | 86.6th | **CDC** | |
| 2018-12-30 | 29.2mo | Weight-for-age | 12.3 kg | 34.0th | CDC | |
| 2018-12-30 | 29.2mo | Weight-for-**stature** | 12.3 kg | 5.4th | CDC | |
| 2018-12-30 | 29.2mo | BMI-for-age | 14.1 | 3.4th | CDC | |
| 2019-06-30 | 35.2mo | Height-for-age | 97.8 cm | 86.3th | CDC | |
| 2019-06-30 | 35.2mo | Weight-for-age | 13.1 kg | 34.0th | CDC | |
| 2019-06-30 | 35.2mo | Weight-for-**stature** | 13.1 kg | 4.0th | CDC | |
| 2019-06-30 | 35.2mo | BMI-for-age | 13.7 | 2.1th | CDC | |

A prose summary an agent might give the user, applying `SKILL.md`'s
guidance on presenting flags rather than burying them:

> This patient's length/height and weight have tracked in the
> 80th-90th and 30th-75th percentiles respectively from birth through
> age 3, using the WHO standard through 23 months and switching to the
> CDC standard at 24 months as recommended by the CDC/AAP for U.S.
> children. Her weight-for-length/stature percentile has run low
> throughout (below the 10th percentile at several visits) and her BMI
> percentile has trended downward across the two most recent visits (3rd,
> then 2nd percentile) — worth a clinician's attention, though this skill
> reports point-in-time percentiles only and doesn't compute a formal
> growth-velocity trend (see `references/METHODOLOGY.md` §7). BMI for the
> nine earliest visits was derived from paired weight and length/height
> readings rather than measured directly (`bmi_derived` flag) since the
> source data didn't include a BMI observation until the 2018-12-30 visit.

## What this demonstrates

- **Deterministic engine, real data.** Every percentile above traces back
  through `provenance` in `results.json` to an exact row in
  `references/data/who_*.csv` / `cdc_*.csv` and a cited formula
  (`references/METHODOLOGY.md`) — nothing here was estimated by a model.
- **Automatic WHO→CDC handoff**, mid-record, at exactly 24 months —
  the same patient, same file, switching reference standards without any
  special-casing by the caller.
- **Automatic length-vs-stature resolution** from an ambiguous LOINC
  code (`references/LOINC_MAP.md`), also driven by age, also mid-record.
- **Derived BMI** when the source data doesn't supply it directly, clearly
  flagged rather than silently presented as a measured value.
- **A noisy, realistic input** — 81 Observations of which only 24 are
  growth-relevant — handled correctly by LOINC filtering, not a
  pre-cleaned list.

## Reproduce it yourself

```bash
cd growth-percentile-skill  # this repo
uv sync
uv run adapters/fhir_r4.py tests/fixtures/synthea_fhir_bundle.json > /tmp/records.json
uv run scripts/growth.py /tmp/records.json > /tmp/results.json
cat /tmp/results.json
```
