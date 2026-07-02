# Test fixtures

Real synthetic-patient output from MITRE's Synthea project, not hand-written.
Fully synthetic (no real patient data); retrieved 2026-07-02.

- `synthea_fhir_bundle.json` -- one patient (female, born 2016-07-24) from
  Synthea's public "1K Sample Synthetic Patient Records, FHIR R4" set
  (https://synthetichealth.github.io/synthea-sample-data/downloads/synthea_sample_data_fhir_r4_sep2019.zip).
  Trimmed to the `Patient` resource and all `Observation` resources (81 of
  them -- most are unrelated vitals/labs, intentionally left in so the
  adapter is tested against realistic noise, not a pre-filtered list).
- `synthea_patients.csv` / `synthea_observations.csv` -- one patient
  (female, born 2023-04-09) from Synthea's public CSV sample export
  (https://synthetichealth.github.io/synthea-sample-data/downloads/latest/synthea_sample_data_csv_latest.zip),
  same column headers Synthea's `CSVExporter` produces. Observations file
  keeps all 159 rows for this patient (vitals, labs, etc.), not just the
  growth-relevant ones.

**Real-world finding baked into the adapters from these fixtures:** Synthea
(both the 2019 FHIR export and the current CSV export) reports body length/
height under LOINC `8302-2` ("Body Height") at every age, including at
birth -- it never emits the recumbent-length-specific code `8306-3`. Real
EHR exports are frequently just as ambiguous. See `references/LOINC_MAP.md`
and `adapters/fhir_r4.py` for how the adapters resolve this (age-based
fallback: `8302-2` under 24 months is treated as recumbent length).
