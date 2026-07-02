"""Flat CSV/JSON -> canonical MeasurementRecord list (the escape hatch).

For sources with no FHIR or Synthea export -- a spreadsheet or a hand-built
JSON list. No code mapping or heuristics: columns/keys must already use
the canonical field names from references/CANONICAL_SCHEMA.md.

Required columns/keys: patient_id, sex, birth_date, observation_date,
metric, value, unit.
Optional: age_months, gestational_age_weeks.

CSV values are all strings; numeric fields (value, age_months,
gestational_age_weeks) are cast to float, and blank optional fields are
dropped rather than passed through as empty strings. JSON input is
expected to already have correctly-typed values (no casting is applied
beyond validating required keys are present).

Usage as a library:
    from flat import parse_csv, parse_json
    records = parse_csv("measurements.csv")
    records = parse_json("measurements.json")

Usage as a CLI:
    uv run adapters/flat.py measurements.csv > records.json
    uv run adapters/flat.py measurements.json > records.json
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import AdapterError, build_record, normalize_sex  # noqa: E402

REQUIRED_FIELDS = ("patient_id", "sex", "birth_date", "observation_date", "metric", "value", "unit")
OPTIONAL_NUMERIC_FIELDS = ("age_months", "gestational_age_weeks")


def _row_to_record(row: dict, *, row_num: int) -> dict:
    missing = [f for f in REQUIRED_FIELDS if not row.get(f)]
    if missing:
        raise AdapterError(f"row {row_num}: missing required field(s): {', '.join(missing)}")

    try:
        value = float(row["value"])
    except ValueError as e:
        raise AdapterError(f"row {row_num}: value {row['value']!r} is not numeric") from e

    kwargs = dict(
        patient_id=str(row["patient_id"]),
        sex=normalize_sex(row["sex"]),
        birth_date=str(row["birth_date"]),
        observation_date=str(row["observation_date"]),
        metric=str(row["metric"]),
        value=value,
        unit=str(row["unit"]),
    )
    for field_name in OPTIONAL_NUMERIC_FIELDS:
        raw = row.get(field_name)
        if raw is None or raw == "":
            continue
        try:
            kwargs[field_name] = float(raw)
        except ValueError as e:
            raise AdapterError(f"row {row_num}: {field_name} {raw!r} is not numeric") from e

    return build_record(**kwargs)


def parse_csv(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return [_row_to_record(row, row_num=i) for i, row in enumerate(csv.DictReader(f), start=2)]


def parse_json(path: str) -> list[dict]:
    with open(path) as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise AdapterError("expected a JSON list of measurement objects")
    return [_row_to_record(row, row_num=i) for i, row in enumerate(raw, start=1)]


def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: flat.py <measurements.csv|measurements.json>", file=sys.stderr)
        return 2
    path = argv[1]
    parser = parse_json if path.endswith(".json") else parse_csv
    records = parser(path)
    json.dump(records, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
