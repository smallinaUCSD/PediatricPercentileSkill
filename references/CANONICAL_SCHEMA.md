# Canonical schema

This is the one contract every ingestion adapter targets and the only shape
the calculation engine ever reads. Adapters translate messy real-world
sources (FHIR bundles, Synthea exports, flat files) into this schema; the
engine never parses source formats directly.

## `MeasurementRecord` (input to the engine)

| Field | Type | Required | Notes |
|---|---|---|---|
| `patient_id` | string | yes | Opaque identifier, passed through for provenance/output grouping only. Not used in any calculation. |
| `sex` | `"male"` \| `"female"` | yes | CDC/WHO LMS tables are sex-specific. No other values are supported in v1. |
| `birth_date` | ISO 8601 date (`YYYY-MM-DD`) | yes | Used with `observation_date` to derive `age_months` if not supplied directly. |
| `observation_date` | ISO 8601 date (`YYYY-MM-DD`) | yes | Date the measurement was taken. |
| `age_months` | float | no | Fractional months. Derived from `birth_date`/`observation_date` if omitted. If supplied, takes precedence over the derived value (lets callers pass corrected age deliberately). |
| `metric` | `"weight"` \| `"height_standing"` \| `"length_recumbent"` \| `"head_circumference"` \| `"bmi"` | yes | Determines which indicator(s) the engine computes. `weight` also drives weight-for-length/stature when a paired length/height record exists for the same `patient_id` + `observation_date`. |
| `value` | float | yes | Magnitude in `unit`. |
| `unit` | UCUM string: `"kg"`, `"cm"`, `"kg/m2"` | yes | Engine converts internally as needed; it does not guess units. |
| `gestational_age_weeks` | float | no | If present and `< 37`, and `age_months` (uncorrected) is `< 24`, the engine emits a `corrected_age_recommended` flag instead of guessing a correction (see [[METHODOLOGY]] §Prematurity). |

Records are one metric per record. A single clinic visit with weight,
height, and head circumference is three `MeasurementRecord`s sharing the
same `patient_id` and `observation_date`.

## `GrowthResult` (output from the engine)

| Field | Type | Notes |
|---|---|---|
| `patient_id` | string | Passed through from input. |
| `reference` | `"CDC"` \| `"WHO"` | Which standard was auto-selected (or explicitly requested). |
| `indicator` | string | e.g. `"weight_for_age"`, `"bmi_for_age"`, `"weight_for_length"`. |
| `age_months` | float | Age actually used for the lookup (uncorrected unless caller supplied corrected `age_months`). |
| `sex` | `"male"` \| `"female"` | Echoed input. |
| `value` | float | Echoed input measurement, in the unit used for calculation. |
| `lms` | `{L, M, S}` | The (possibly interpolated) LMS triplet used. |
| `z_score` | float | Cole's LMS z-score. Extended BMI uses the CDC 2022 method above the 95th percentile instead. |
| `percentile` | float | 0-100. |
| `flags` | string[] | e.g. `["corrected_age_recommended"]`, `["implausible_value"]`, `["extended_bmi_used"]`. Empty list if none apply. |
| `provenance` | `{data_file, table_version, formula}` | Exact source row and formula variant used, for audit. |

## Design notes

- The schema is intentionally flat and metric-per-record rather than a
  wide per-visit object — it keeps adapters simple (map one source row to
  one record) and lets the engine treat every indicator uniformly.
- `age_months` as an optional override (rather than always deriving it)
  is what allows the flag-only prematurity approach: a caller who *has*
  done corrected-age math themselves can pass it in, while the engine's
  own default path never performs that correction silently.
- Unit conversion is the engine's job, not the adapter's, so adapters stay
  dumb mappers and all conversion logic lives in one tested place.
