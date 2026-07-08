"""Flat CSV/JSON -> canonical MeasurementRecord list (the escape hatch).

For sources with no FHIR or Synthea export -- a spreadsheet or a hand-built
JSON list. By default, columns/keys must already use the canonical field
names from references/CANONICAL_SCHEMA.md. If your source uses different
column names (e.g. "DOB" instead of "birth_date", "Weight (kg)" instead
of "value"), pass a column map instead of renaming your file: a flat JSON
object from canonical field name -> your column name, for only the
columns that differ. Anything not in the map is still looked up by its
canonical name, so a partial map (just the columns that need it) is fine.
Extra columns in your source that aren't part of the canonical schema are
simply ignored, not an error.

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

    # your source uses different column names:
    records = parse_csv("measurements.csv", column_map={"birth_date": "DOB", "value": "Weight (kg)"})

Usage as a CLI:
    uv run adapters/flat.py measurements.csv > records.json
    uv run adapters/flat.py measurements.json > records.json
    uv run adapters/flat.py measurements.csv --map colmap.json > records.json
    # colmap.json: {"birth_date": "DOB", "value": "Weight (kg)"}
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import AdapterError, build_record, normalize_sex  # noqa: E402

REQUIRED_FIELDS = ("patient_id", "sex", "birth_date", "observation_date", "metric", "value", "unit")
OPTIONAL_NUMERIC_FIELDS = ("age_months", "gestational_age_weeks")


def _get(row: dict, column_map: dict[str, str], canonical_name: str):
    source_key = column_map.get(canonical_name, canonical_name)
    return row.get(source_key)


def _is_missing(value) -> bool:
    return value is None or value == ""


def _row_to_record(row: dict, *, row_num: int, column_map: dict[str, str] | None = None) -> dict:
    column_map = column_map or {}
    missing = [f for f in REQUIRED_FIELDS if _is_missing(_get(row, column_map, f))]
    if missing:
        source_names = [column_map.get(f, f) for f in missing]
        raise AdapterError(
            f"row {row_num}: missing required field(s): {', '.join(missing)} "
            f"(looked for column(s): {', '.join(source_names)})"
        )

    raw_value = _get(row, column_map, "value")
    try:
        value = float(raw_value)
    except ValueError as e:
        raise AdapterError(f"row {row_num}: value {raw_value!r} is not numeric") from e

    kwargs = dict(
        patient_id=str(_get(row, column_map, "patient_id")),
        sex=normalize_sex(_get(row, column_map, "sex")),
        birth_date=str(_get(row, column_map, "birth_date")),
        observation_date=str(_get(row, column_map, "observation_date")),
        metric=str(_get(row, column_map, "metric")),
        value=value,
        unit=str(_get(row, column_map, "unit")),
    )
    for field_name in OPTIONAL_NUMERIC_FIELDS:
        raw = _get(row, column_map, field_name)
        if raw is None or raw == "":
            continue
        try:
            kwargs[field_name] = float(raw)
        except ValueError as e:
            raise AdapterError(f"row {row_num}: {field_name} {raw!r} is not numeric") from e

    return build_record(**kwargs)


def _validate_column_map(column_map: dict[str, str] | None) -> None:
    if column_map is None:
        return
    if not isinstance(column_map, dict) or not all(isinstance(v, str) for v in column_map.values()):
        raise AdapterError(
            f"column_map must be a JSON object of canonical field name -> your column name, got {column_map!r}"
        )


def parse_csv(path: str, *, column_map: dict[str, str] | None = None) -> list[dict]:
    _validate_column_map(column_map)
    with open(path, newline="") as f:
        return [
            _row_to_record(row, row_num=i, column_map=column_map)
            for i, row in enumerate(csv.DictReader(f), start=2)
        ]


def parse_json(path: str, *, column_map: dict[str, str] | None = None) -> list[dict]:
    _validate_column_map(column_map)
    with open(path) as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise AdapterError("expected a JSON list of measurement objects")
    return [_row_to_record(row, row_num=i, column_map=column_map) for i, row in enumerate(raw, start=1)]


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="measurements.csv or measurements.json")
    parser.add_argument(
        "--map",
        dest="map_path",
        help="path to a JSON file mapping canonical field name -> your column name, for columns that differ",
    )
    args = parser.parse_args(argv[1:])

    column_map = None
    if args.map_path:
        with open(args.map_path) as f:
            column_map = json.load(f)

    reader = parse_json if args.source.endswith(".json") else parse_csv
    records = reader(args.source, column_map=column_map)
    json.dump(records, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
