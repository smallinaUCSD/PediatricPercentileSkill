"""Shared helpers for ingestion adapters.

Deliberately independent of scripts/growth.py (see CONTRIBUTING.md):
adapters produce plain dicts matching the canonical MeasurementRecord
shape (references/CANONICAL_SCHEMA.md), not engine objects.
"""

from __future__ import annotations

from datetime import date

# WHO convention, 365.25 / 12 -- see references/METHODOLOGY.md section 5.
# Duplicated (not imported) from scripts/growth.py deliberately: adapters
# don't depend on the engine module. Keep in sync if that constant moves.
AGE_DAYS_PER_MONTH = 30.4375

# See references/LOINC_MAP.md. 8302-2 is intentionally absent here --
# it's ambiguous (length vs. stature) and resolved by resolve_metric().
LOINC_TO_METRIC = {
    "29463-7": "weight",
    "8306-3": "length_recumbent",
    "9843-4": "head_circumference",
    "39156-5": "bmi",
}
AMBIGUOUS_HEIGHT_LOINC = "8302-2"

SEX_ALIASES = {
    "male": "male", "m": "male", "man": "male",
    "female": "female", "f": "female", "woman": "female",
}


class AdapterError(ValueError):
    """Raised when source data can't be mapped into the canonical schema."""


def normalize_sex(raw: str | None) -> str:
    if raw is None:
        raise AdapterError("missing sex/gender")
    key = raw.strip().lower()
    if key not in SEX_ALIASES:
        raise AdapterError(
            f"unsupported sex/gender {raw!r} -- v1 only supports male/female "
            "(no CDC/WHO reference table exists for other values)"
        )
    return SEX_ALIASES[key]


def age_months_between(birth_date: date, observation_date: date) -> float:
    return (observation_date - birth_date).days / AGE_DAYS_PER_MONTH


def resolve_metric(loinc_code: str, birth_date: date, observation_date: date) -> str | None:
    """Maps a LOINC code to a canonical metric name, or None if unrecognized.

    See references/LOINC_MAP.md "Length vs. stature ambiguity": 8302-2
    ("Body height") is used generically at every age by Synthea and many
    real EHR exports, so it's resolved by the patient's age at the
    observation rather than trusted at face value.
    """
    if loinc_code == AMBIGUOUS_HEIGHT_LOINC:
        age_months = age_months_between(birth_date, observation_date)
        return "length_recumbent" if age_months < 24 else "height_standing"
    return LOINC_TO_METRIC.get(loinc_code)


def parse_date_only(value: str) -> str:
    """Extracts the YYYY-MM-DD date portion from an ISO date or datetime string."""
    return value[:10]


def build_record(
    *,
    patient_id: str,
    sex: str,
    birth_date: str,
    observation_date: str,
    metric: str,
    value: float,
    unit: str,
    age_months: float | None = None,
    gestational_age_weeks: float | None = None,
) -> dict:
    """Constructs a canonical MeasurementRecord dict (references/CANONICAL_SCHEMA.md)."""
    record = {
        "patient_id": patient_id,
        "sex": sex,
        "birth_date": birth_date,
        "observation_date": observation_date,
        "metric": metric,
        "value": value,
        "unit": unit,
    }
    if age_months is not None:
        record["age_months"] = age_months
    if gestational_age_weeks is not None:
        record["gestational_age_weeks"] = gestational_age_weeks
    return record
