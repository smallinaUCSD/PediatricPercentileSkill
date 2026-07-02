"""Synthea CSV export -> canonical MeasurementRecord list.

Reads Synthea's patients.csv + observations.csv (CSVExporter output) and
maps rows carrying a recognized LOINC code (references/LOINC_MAP.md) into
canonical records. Synthea's *FHIR* export (one Bundle per patient) is
handled by adapters/fhir_r4.py instead -- both formats represent the same
underlying data, this module only covers the flat-file variant.

If patient_id is omitted, every patient in patients.csv that has at least
one recognized observation is included -- useful for a multi-patient
Synthea population export.

Usage as a library:
    from synthea import parse_csv
    records = parse_csv("patients.csv", "observations.csv")

Usage as a CLI:
    uv run adapters/synthea.py patients.csv observations.csv [patient_id] > records.json
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import AdapterError, build_record, normalize_sex, parse_date_only, resolve_metric  # noqa: E402


def parse_csv(patients_path: str, observations_path: str, *, patient_id: str | None = None) -> list[dict]:
    with open(patients_path, newline="") as f:
        patients = {row["Id"]: row for row in csv.DictReader(f)}

    if patient_id is not None:
        if patient_id not in patients:
            raise AdapterError(f"patient_id {patient_id!r} not found in {patients_path}")
        wanted_ids = {patient_id}
    else:
        wanted_ids = set(patients)

    observations_by_patient: dict[str, list[dict]] = defaultdict(list)
    with open(observations_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("PATIENT") in wanted_ids:
                observations_by_patient[row["PATIENT"]].append(row)

    records: list[dict] = []
    for pid, obs_rows in observations_by_patient.items():
        patient_row = patients[pid]
        sex = normalize_sex(patient_row.get("GENDER"))
        birth_date_str = patient_row.get("BIRTHDATE")
        if not birth_date_str:
            raise AdapterError(f"patient {pid} has no BIRTHDATE")
        birth_date = date.fromisoformat(birth_date_str)

        for row in sorted(obs_rows, key=lambda r: r.get("DATE", "")):
            if row.get("TYPE") not in (None, "numeric"):
                continue
            observation_date_str = parse_date_only(row["DATE"])
            observation_date = date.fromisoformat(observation_date_str)
            metric = resolve_metric(row.get("CODE", ""), birth_date, observation_date)
            if metric is None:
                continue
            try:
                value = float(row["VALUE"])
            except (KeyError, ValueError):
                continue

            records.append(
                build_record(
                    patient_id=pid,
                    sex=sex,
                    birth_date=birth_date_str,
                    observation_date=observation_date_str,
                    metric=metric,
                    value=value,
                    unit=row.get("UNITS", ""),
                )
            )
    return records


def _main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        print("usage: synthea.py <patients.csv> <observations.csv> [patient_id]", file=sys.stderr)
        return 2
    patient_id = argv[3] if len(argv) == 4 else None
    records = parse_csv(argv[1], argv[2], patient_id=patient_id)
    json.dump(records, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
