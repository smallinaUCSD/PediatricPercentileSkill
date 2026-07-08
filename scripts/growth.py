"""Deterministic CDC/WHO growth-percentile calculation engine.

No network access, no randomness, no model arithmetic. Given canonical
MeasurementRecords (see references/CANONICAL_SCHEMA.md) this computes
GrowthResults using Cole's LMS method, auto-selecting WHO (0-<24 months)
vs CDC (24 months-20 years) per references/METHODOLOGY.md. All formulas
implemented here are cited and, where possible, verified against the
source data file itself (see METHODOLOGY.md §4 for the extended-BMI
verification).

Usage as a library:
    from growth import MeasurementRecord, compute_batch
    results = compute_batch([MeasurementRecord(...), ...])

Usage as a CLI:
    uv run scripts/growth.py records.json
    (reads a JSON list of MeasurementRecord objects, prints a JSON list
    of GrowthResult objects)
"""

from __future__ import annotations

import bisect
import csv
import dataclasses
import functools
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from scipy.stats import norm

DATA_DIR = Path(__file__).resolve().parent.parent / "references" / "data"

AGE_DAYS_PER_MONTH = 30.4375  # WHO convention (365.25 / 12)
LB_TO_KG = 0.45359237
IN_TO_CM = 2.54

# WHO 0-<24mo / CDC 24mo-20yr, per references/METHODOLOGY.md section 2.
WHO_CDC_HANDOFF_MONTHS = 24

SEX_CODE = {"male": 1, "female": 2}

METRIC_TO_AGE_INDICATOR = {
    "weight": "weight_for_age",
    "height_standing": "height_for_age",
    "length_recumbent": "length_for_age",
    "head_circumference": "head_circumference_for_age",
    "bmi": "bmi_for_age",
}

TABLE_VERSION = {
    "WHO": "WHO Child Growth Standards, 2006 (files retrieved 2026-07-01; see references/DATA_SOURCES.md)",
    "CDC": "CDC 2000 Growth Charts / 2022 Extended BMI-for-Age (files retrieved 2026-07-01; see references/DATA_SOURCES.md)",
}

# BIV (biologically implausible value) modified-z cutoffs, per CDC's
# growth-chart SAS program and references/METHODOLOGY.md §4a. Indicators
# not listed here (weight_for_length, weight_for_stature) have no
# CDC-published cutoff and are not flagged in v1.
BIV_CUTOFFS = {
    "weight_for_age": (-5.0, 8.0),
    "height_for_age": (-5.0, 4.0),
    "length_for_age": (-5.0, 4.0),
    "bmi_for_age": (-4.0, 8.0),
    "head_circumference_for_age": (-5.0, 5.0),  # v1 generic threshold, not an official CDC cutoff
}


@dataclass(frozen=True)
class TableSpec:
    filename: str
    axis_col: str
    sex_col: str
    axis_semantic: str  # "age" | "length" | "height"
    file_axis_unit: str  # "months" | "days" | "cm"
    range_min: float  # in semantic units (months for age; cm for length/height)
    range_max: float
    has_extended: bool = False  # sigma/P95 columns present (CDC extended BMI)


# (standard, indicator) -> candidate tables, ordered by nothing in particular;
# _select_table() picks the most specific covering table (highest range_min).
REGISTRY: dict[tuple[str, str], list[TableSpec]] = {
    ("WHO", "weight_for_age"): [
        TableSpec("who_weight_for_age.csv", "age_days", "Sex", "age", "days", 0, 1856 / AGE_DAYS_PER_MONTH),
    ],
    ("WHO", "length_for_age"): [
        TableSpec("who_length_for_age.csv", "age_days", "Sex", "age", "days", 0, 1856 / AGE_DAYS_PER_MONTH),
    ],
    ("WHO", "head_circumference_for_age"): [
        TableSpec("who_head_circumference_for_age.csv", "age_days", "Sex", "age", "days", 0, 1856 / AGE_DAYS_PER_MONTH),
    ],
    ("WHO", "bmi_for_age"): [
        TableSpec("who_bmi_for_age.csv", "age_days", "Sex", "age", "days", 0, 1856 / AGE_DAYS_PER_MONTH),
    ],
    ("WHO", "weight_for_length"): [
        TableSpec("who_weight_for_length.csv", "length_cm", "Sex", "length", "cm", 45, 110),
    ],
    ("CDC", "weight_for_age"): [
        TableSpec("cdc_wtageinf.csv", "Agemos", "Sex", "age", "months", 0, 36),
        TableSpec("cdc_wtage.csv", "Agemos", "Sex", "age", "months", 24, 240),
    ],
    ("CDC", "length_for_age"): [
        TableSpec("cdc_lenageinf.csv", "Agemos", "Sex", "age", "months", 0, 36),
    ],
    ("CDC", "height_for_age"): [
        TableSpec("cdc_statage.csv", "Agemos", "Sex", "age", "months", 24, 240),
    ],
    ("CDC", "head_circumference_for_age"): [
        TableSpec("cdc_hcageinf.csv", "Agemos", "Sex", "age", "months", 0, 36),
    ],
    ("CDC", "bmi_for_age"): [
        TableSpec("cdc_bmi_extended.csv", "agemos", "sex", "age", "months", 24, 240, has_extended=True),
    ],
    ("CDC", "weight_for_length"): [
        TableSpec("cdc_wtleninf.csv", "Length", "Sex", "length", "cm", 45, 103.5),
    ],
    ("CDC", "weight_for_stature"): [
        TableSpec("cdc_wtstat.csv", "Height", "Sex", "height", "cm", 77, 121),
    ],
}


@dataclass
class MeasurementRecord:
    patient_id: str
    sex: str  # "male" | "female"
    birth_date: str  # ISO 8601 date
    observation_date: str  # ISO 8601 date
    metric: str  # weight | height_standing | length_recumbent | head_circumference | bmi
    value: float
    unit: str  # kg | lb | cm | in | kg/m2
    age_months: float | None = None
    gestational_age_weeks: float | None = None


@dataclass
class GrowthResult:
    patient_id: str
    reference: str  # "WHO" | "CDC"
    indicator: str
    age_months: float
    sex: str
    value: float
    lms: dict | None
    z_score: float | None
    percentile: float | None
    flags: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=dict)


class GrowthEngineError(ValueError):
    """Raised for invalid caller input (bad sex, unparseable dates, unsupported units)."""


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def _load_table(spec: TableSpec) -> dict[int, list[tuple]]:
    path = DATA_DIR / spec.filename
    by_sex: dict[int, list[tuple]] = {1: [], 2: []}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldmap = {name.lower(): name for name in reader.fieldnames or []}
        axis_key = fieldmap[spec.axis_col.lower()]
        sex_key = fieldmap[spec.sex_col.lower()]
        l_key, m_key, s_key = fieldmap["l"], fieldmap["m"], fieldmap["s"]
        sigma_key = fieldmap.get("sigma")
        p95_key = fieldmap.get("p95")
        for row in reader:
            if row[sex_key] == reader.fieldnames[0]:
                # Some CDC source files (e.g. cdc_lenageinf.csv, cdc_bmiagerev.csv)
                # repeat the header row at the male/female transition -- this is
                # how CDC publishes them, not a corruption of our copy, so we skip
                # it here rather than edit the checksummed data file.
                continue
            sex_code = int(row[sex_key])
            axis_val = float(row[axis_key])
            L, M, S = float(row[l_key]), float(row[m_key]), float(row[s_key])
            if spec.has_extended:
                sigma, p95 = float(row[sigma_key]), float(row[p95_key])
                by_sex[sex_code].append((axis_val, L, M, S, sigma, p95))
            else:
                by_sex[sex_code].append((axis_val, L, M, S))
    for rows in by_sex.values():
        rows.sort(key=lambda r: r[0])
    return by_sex


def _interpolate(rows: list[tuple], axis_value: float) -> tuple:
    axes = [r[0] for r in rows]
    idx = bisect.bisect_left(axes, axis_value)
    if idx < len(axes) and axes[idx] == axis_value:
        return rows[idx][1:]
    if idx == 0:
        return rows[0][1:]
    if idx >= len(axes):
        return rows[-1][1:]
    lo, hi = rows[idx - 1], rows[idx]
    frac = (axis_value - lo[0]) / (hi[0] - lo[0])
    return tuple(lo[i] + frac * (hi[i] - lo[i]) for i in range(1, len(lo)))


def _select_table(standard: str, indicator: str, axis_value: float) -> TableSpec | None:
    candidates = REGISTRY.get((standard, indicator), [])
    covering = [t for t in candidates if t.range_min <= axis_value <= t.range_max]
    if not covering:
        return None
    return max(covering, key=lambda t: t.range_min)


# --------------------------------------------------------------------------
# LMS math (references/METHODOLOGY.md §1, §4, §4a)
# --------------------------------------------------------------------------


def lms_z(x: float, L: float, M: float, S: float) -> float:
    if abs(L) < 1e-9:
        return math.log(x / M) / S
    return ((x / M) ** L - 1) / (L * S)


def lms_value_at_z(z: float, L: float, M: float, S: float) -> float:
    if abs(L) < 1e-9:
        return M * math.exp(S * z)
    return M * (1 + L * S * z) ** (1 / L)


def percentile_from_z(z: float) -> float:
    return float(norm.cdf(z) * 100)


def extended_bmi_z_percentile(
    x: float, L: float, M: float, S: float, sigma: float, p95: float
) -> tuple[float, float, bool]:
    """Returns (z, percentile, used_extended). See METHODOLOGY.md §4."""
    if x < p95:
        z = lms_z(x, L, M, S)
        return z, percentile_from_z(z), False
    arg = (x - p95) / (sigma * math.sqrt(2))
    p = 0.95 + 0.05 * math.erf(arg)
    p = min(p, 1 - 1e-12)
    z = float(norm.ppf(p))
    return z, p * 100, True


def modified_z(x: float, L: float, M: float, S: float) -> float:
    """CDC modified z-score for plausibility flagging. See METHODOLOGY.md §4a."""
    if x == M:
        return 0.0
    if x > M:
        sd_distance = 0.5 * (lms_value_at_z(2.0, L, M, S) - M)
    else:
        sd_distance = 0.5 * (M - lms_value_at_z(-2.0, L, M, S))
    return (x - M) / sd_distance


# --------------------------------------------------------------------------
# Unit conversion, age, and record helpers
# --------------------------------------------------------------------------


def _to_kg(value: float, unit: str) -> float:
    if unit == "kg":
        return value
    if unit == "lb":
        return value * LB_TO_KG
    raise GrowthEngineError(f"unsupported weight unit: {unit!r}")


def _to_cm(value: float, unit: str) -> float:
    if unit == "cm":
        return value
    if unit == "in":
        return value * IN_TO_CM
    raise GrowthEngineError(f"unsupported length/height unit: {unit!r}")


def _normalize_metric_value(metric: str, value: float, unit: str) -> float:
    if metric == "weight":
        return _to_kg(value, unit)
    if metric in ("height_standing", "length_recumbent"):
        return _to_cm(value, unit)
    if metric == "head_circumference":
        return _to_cm(value, unit)
    if metric == "bmi":
        if unit != "kg/m2":
            raise GrowthEngineError(f"unsupported BMI unit: {unit!r}")
        return value
    raise GrowthEngineError(f"unknown metric: {metric!r}")


def compute_age_months(birth_date: date, observation_date: date) -> float:
    days = (observation_date - birth_date).days
    if days < 0:
        raise GrowthEngineError("observation_date precedes birth_date")
    return days / AGE_DAYS_PER_MONTH


def _parse_date(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise GrowthEngineError(f"invalid ISO 8601 date: {s!r}") from e


def _resolve_age_months(record: MeasurementRecord) -> float:
    if record.age_months is not None:
        return record.age_months
    return compute_age_months(_parse_date(record.birth_date), _parse_date(record.observation_date))


def _prematurity_flags(record: MeasurementRecord, age_months: float) -> list[str]:
    if (
        record.gestational_age_weeks is not None
        and record.gestational_age_weeks < 37
        and age_months < WHO_CDC_HANDOFF_MONTHS
    ):
        return ["corrected_age_recommended"]
    return []


def _plausibility_flags(indicator: str, value: float, L: float, M: float, S: float) -> list[str]:
    cutoffs = BIV_CUTOFFS.get(indicator)
    if cutoffs is None:
        return []
    low, high = cutoffs
    mz = modified_z(value, L, M, S)
    if mz < low or mz > high:
        return ["implausible_value"]
    return []


def _sex_code(sex: str) -> int:
    if sex not in SEX_CODE:
        raise GrowthEngineError(f"unsupported sex: {sex!r} (must be 'male' or 'female')")
    return SEX_CODE[sex]


def _axis_value_for_lookup(spec: TableSpec, age_months: float, cm_value: float | None) -> float:
    if spec.axis_semantic == "age":
        return age_months * AGE_DAYS_PER_MONTH if spec.file_axis_unit == "days" else age_months
    return cm_value  # length/height tables store cm natively


def _lookup(
    standard: str, indicator: str, sex: str, age_months: float, cm_value: float | None
) -> tuple[TableSpec | None, tuple | None]:
    range_probe = cm_value if cm_value is not None else age_months
    spec = _select_table(standard, indicator, range_probe)
    if spec is None:
        return None, None
    table = _load_table(spec)
    rows = table[_sex_code(sex)]
    axis_value = _axis_value_for_lookup(spec, age_months, cm_value)
    return spec, _interpolate(rows, axis_value)


def _unavailable_result(record: MeasurementRecord, indicator: str, standard: str, age_months: float, value: float) -> GrowthResult:
    return GrowthResult(
        patient_id=record.patient_id,
        reference=standard,
        indicator=indicator,
        age_months=age_months,
        sex=record.sex,
        value=value,
        lms=None,
        z_score=None,
        percentile=None,
        flags=["reference_unavailable"],
        provenance={
            "data_file": None,
            "table_version": TABLE_VERSION.get(standard),
            "formula": None,
            "note": f"no {standard} reference table covers this age/measurement for {indicator}",
        },
    )


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def compute_for_age(record: MeasurementRecord, *, reference_override: str | None = None) -> GrowthResult:
    """Computes the *-for-age indicator implied by record.metric."""
    indicator = METRIC_TO_AGE_INDICATOR.get(record.metric)
    if indicator is None:
        raise GrowthEngineError(f"metric {record.metric!r} has no *-for-age indicator")
    age_months = _resolve_age_months(record)
    value = _normalize_metric_value(record.metric, record.value, record.unit)
    standard = reference_override or ("WHO" if age_months < WHO_CDC_HANDOFF_MONTHS else "CDC")

    spec, row = _lookup(standard, indicator, record.sex, age_months, None)
    if spec is None:
        return _unavailable_result(record, indicator, standard, age_months, value)

    flags = list(_prematurity_flags(record, age_months))
    if spec.has_extended:
        L, M, S, sigma, p95 = row
        z, pct, used_extended = extended_bmi_z_percentile(value, L, M, S, sigma, p95)
        if used_extended:
            flags.append("extended_bmi_used")
    else:
        L, M, S = row
        z = lms_z(value, L, M, S)
        pct = percentile_from_z(z)
    flags.extend(_plausibility_flags(indicator, value, L, M, S))

    return GrowthResult(
        patient_id=record.patient_id,
        reference=standard,
        indicator=indicator,
        age_months=age_months,
        sex=record.sex,
        value=value,
        lms={"L": L, "M": M, "S": S},
        z_score=z,
        percentile=pct,
        flags=flags,
        provenance={
            "data_file": spec.filename,
            "table_version": TABLE_VERSION[standard],
            "formula": "LMS+extended-half-normal" if spec.has_extended else "LMS",
        },
    )


def compute_weight_for_length_or_stature(
    weight_record: MeasurementRecord,
    length_or_height_record: MeasurementRecord,
    *,
    reference_override: str | None = None,
) -> GrowthResult:
    if length_or_height_record.metric == "length_recumbent":
        indicator = "weight_for_length"
    elif length_or_height_record.metric == "height_standing":
        indicator = "weight_for_stature"
    else:
        raise GrowthEngineError(
            f"expected length_recumbent or height_standing, got {length_or_height_record.metric!r}"
        )

    age_months = _resolve_age_months(weight_record)
    weight_kg = _normalize_metric_value("weight", weight_record.value, weight_record.unit)
    length_cm = _normalize_metric_value(length_or_height_record.metric, length_or_height_record.value, length_or_height_record.unit)
    standard = reference_override or ("WHO" if age_months < WHO_CDC_HANDOFF_MONTHS else "CDC")

    spec, row = _lookup(standard, indicator, weight_record.sex, age_months, length_cm)
    if spec is None:
        return _unavailable_result(weight_record, indicator, standard, age_months, weight_kg)

    L, M, S = row
    z = lms_z(weight_kg, L, M, S)
    pct = percentile_from_z(z)
    flags = list(_prematurity_flags(weight_record, age_months))
    flags.extend(_plausibility_flags(indicator, weight_kg, L, M, S))

    return GrowthResult(
        patient_id=weight_record.patient_id,
        reference=standard,
        indicator=indicator,
        age_months=age_months,
        sex=weight_record.sex,
        value=weight_kg,
        lms={"L": L, "M": M, "S": S},
        z_score=z,
        percentile=pct,
        flags=flags,
        provenance={
            "data_file": spec.filename,
            "table_version": TABLE_VERSION[standard],
            "formula": "LMS",
        },
    )


def _derive_bmi_record(weight_record: MeasurementRecord, height_or_length_record: MeasurementRecord) -> MeasurementRecord:
    weight_kg = _normalize_metric_value("weight", weight_record.value, weight_record.unit)
    height_cm = _normalize_metric_value(height_or_length_record.metric, height_or_length_record.value, height_or_length_record.unit)
    height_m = height_cm / 100
    bmi_value = weight_kg / (height_m**2)
    return MeasurementRecord(
        patient_id=weight_record.patient_id,
        sex=weight_record.sex,
        birth_date=weight_record.birth_date,
        observation_date=weight_record.observation_date,
        metric="bmi",
        value=bmi_value,
        unit="kg/m2",
        age_months=weight_record.age_months,
        gestational_age_weeks=weight_record.gestational_age_weeks,
    )


def compute_batch(records: list[MeasurementRecord]) -> list[GrowthResult]:
    """Groups records by (patient_id, observation_date) and computes every
    applicable indicator: one *-for-age result per record, weight-for-length
    or weight-for-stature when a weight and a length/height are paired at
    the same visit, and a derived BMI-for-age when BMI wasn't supplied
    directly but weight and height/length were.
    """
    visits: dict[tuple[str, str], list[MeasurementRecord]] = {}
    for r in records:
        visits.setdefault((r.patient_id, r.observation_date), []).append(r)

    results: list[GrowthResult] = []
    for group in visits.values():
        by_metric = {r.metric: r for r in group}

        for r in group:
            if r.metric in METRIC_TO_AGE_INDICATOR:
                results.append(compute_for_age(r))

        weight_r = by_metric.get("weight")
        height_or_length = by_metric.get("length_recumbent") or by_metric.get("height_standing")
        if weight_r and height_or_length:
            results.append(compute_weight_for_length_or_stature(weight_r, height_or_length))
            if "bmi" not in by_metric:
                derived = _derive_bmi_record(weight_r, height_or_length)
                bmi_result = compute_for_age(derived)
                bmi_result.flags.append("bmi_derived")
                results.append(bmi_result)

    return results


def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: growth.py <records.json>", file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        raw = json.load(f)
    records = [MeasurementRecord(**r) for r in raw]
    results = compute_batch(records)
    json.dump([dataclasses.asdict(r) for r in results], sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
