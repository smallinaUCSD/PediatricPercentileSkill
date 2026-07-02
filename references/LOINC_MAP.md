# LOINC → canonical metric mapping

Used by `adapters/fhir_r4.py` (and any adapter reading LOINC-coded data,
e.g. Synthea) to map `Observation.code` to a canonical `MeasurementRecord.metric`.

| LOINC code | Display | Canonical `metric` | Notes |
|---|---|---|---|
| `29463-7` | Body weight | `weight` | |
| `8302-2` | Body height | `height_standing` **or** `length_recumbent` | See "Length vs. stature ambiguity" below — the code alone doesn't tell you which. |
| `8306-3` | Body height (lying) | `length_recumbent` | Unambiguous recumbent-length code, always trusted over the age heuristic when present. |
| `9843-4` | Head circumference | `head_circumference` | |
| `39156-5` | Body mass index (BMI) | `bmi` | If absent but weight + height/length are both present for the same visit, the engine derives BMI itself rather than requiring the source to supply it. |

### Length vs. stature ambiguity

LOINC `8302-2` ("Body height") is generic and is what most real-world
EHR exports (and Synthea, both its FHIR and CSV output, as of the
fixtures in `tests/fixtures/`) use for *every* age, including newborns
measured lying down — the recumbent-length-specific code `8306-3` exists
but is rarely populated in practice. Silently treating every `8302-2`
reading as standing height would misclassify infant measurements and
trip the engine's `reference_unavailable` guard (WHO has no
standing-height table under 24 months — see `METHODOLOGY.md` §3).

The `fhir_r4` and `synthea` adapters resolve this with an explicit,
documented heuristic: an `8302-2` observation is mapped to
`length_recumbent` if the patient's age at that observation is under 24
months, and to `height_standing` otherwise. `8306-3`, when present, is
always trusted as `length_recumbent` regardless of age. This is a
deliberate approximation of real clinical practice (children under 2 are
measured lying down), not a guess — but it is a heuristic, not a
guarantee, and is called out here so it isn't mistaken for an official
LOINC distinction.

`Observation.valueQuantity.value` maps to `MeasurementRecord.value`;
`valueQuantity.unit` (UCUM) maps to `MeasurementRecord.unit` — the adapter
does not convert units, it passes the UCUM code through and the engine
handles conversion (see `references/CANONICAL_SCHEMA.md`).

`Observation.effectiveDateTime` maps to `observation_date`.
`Patient.birthDate` maps to `birth_date`; `Patient.gender` maps to `sex`
(`male`/`female` only in v1 — other FHIR `AdministrativeGender` values have
no corresponding CDC/WHO reference table and are rejected with a clear
error rather than guessed).
