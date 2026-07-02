"""FHIR R4 Bundle -> canonical MeasurementRecord list.

Walks a Bundle (as produced by Synthea or a real FHIR server export):
the single Patient resource gives birth_date/sex, and Observation
resources carrying a recognized LOINC code (references/LOINC_MAP.md)
become MeasurementRecords. Observations without a recognized code or
without a valueQuantity (e.g. component-based vitals like blood
pressure) are silently skipped -- a real patient bundle is mostly
unrelated resources, and skipping them is expected, not an error.

v1 assumes one Patient per bundle, matching Synthea's "one transaction
Bundle per patient" export convention. A bundle with zero or multiple
Patient resources raises AdapterError.

Usage as a library:
    from fhir_r4 import parse_bundle
    records = parse_bundle(bundle_dict)

Usage as a CLI:
    uv run adapters/fhir_r4.py bundle.json > records.json
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import AdapterError, build_record, normalize_sex, parse_date_only, resolve_metric  # noqa: E402


def _find_patient(bundle: dict) -> dict:
    patients = [
        e["resource"]
        for e in bundle.get("entry", [])
        if e.get("resource", {}).get("resourceType") == "Patient"
    ]
    if len(patients) == 0:
        raise AdapterError("bundle contains no Patient resource")
    if len(patients) > 1:
        raise AdapterError(
            f"bundle contains {len(patients)} Patient resources; v1 supports one patient per bundle"
        )
    return patients[0]


def _observation_value_and_unit(resource: dict) -> tuple[float, str] | None:
    vq = resource.get("valueQuantity")
    if not vq or "value" not in vq:
        return None
    unit = vq.get("code") or vq.get("unit")
    if unit is None:
        return None
    return float(vq["value"]), unit


def parse_bundle(bundle: dict) -> list[dict]:
    patient = _find_patient(bundle)
    patient_id = patient.get("id", "unknown")
    sex = normalize_sex(patient.get("gender"))
    birth_date_str = patient.get("birthDate")
    if not birth_date_str:
        raise AdapterError(f"Patient {patient_id} has no birthDate")
    birth_date = date.fromisoformat(birth_date_str)

    records: list[dict] = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") != "Observation":
            continue
        codings = resource.get("code", {}).get("coding", [])
        effective = resource.get("effectiveDateTime")
        if not effective:
            continue
        observation_date_str = parse_date_only(effective)
        observation_date = date.fromisoformat(observation_date_str)

        value_unit = _observation_value_and_unit(resource)
        if value_unit is None:
            continue
        value, unit = value_unit

        metric = None
        for coding in codings:
            metric = resolve_metric(coding.get("code", ""), birth_date, observation_date)
            if metric is not None:
                break
        if metric is None:
            continue

        records.append(
            build_record(
                patient_id=patient_id,
                sex=sex,
                birth_date=birth_date_str,
                observation_date=observation_date_str,
                metric=metric,
                value=value,
                unit=unit,
            )
        )
    return records


def _main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: fhir_r4.py <bundle.json>", file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        bundle = json.load(f)
    records = parse_bundle(bundle)
    json.dump(records, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
