# LOINC → canonical metric mapping

Used by `adapters/fhir_r4.py` (and any adapter reading LOINC-coded data,
e.g. Synthea) to map `Observation.code` to a canonical `MeasurementRecord.metric`.

| LOINC code | Display | Canonical `metric` | Notes |
|---|---|---|---|
| `29463-7` | Body weight | `weight` | |
| `8302-2` | Body height | `height_standing` | Standing height. |
| `8306-3` | Body height (lying) | `length_recumbent` | Recumbent length, infants/toddlers. |
| `9843-4` | Head circumference | `head_circumference` | |
| `39156-5` | Body mass index (BMI) | `bmi` | If absent but weight + height/length are both present for the same visit, the engine derives BMI itself rather than requiring the source to supply it. |

`Observation.valueQuantity.value` maps to `MeasurementRecord.value`;
`valueQuantity.unit` (UCUM) maps to `MeasurementRecord.unit` — the adapter
does not convert units, it passes the UCUM code through and the engine
handles conversion (see `references/CANONICAL_SCHEMA.md`).

`Observation.effectiveDateTime` maps to `observation_date`.
`Patient.birthDate` maps to `birth_date`; `Patient.gender` maps to `sex`
(`male`/`female` only in v1 — other FHIR `AdministrativeGender` values have
no corresponding CDC/WHO reference table and are rejected with a clear
error rather than guessed).
