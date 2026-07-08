import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import fhir_r4  # noqa: E402
import flat  # noqa: E402
import growth  # noqa: E402
import synthea  # noqa: E402
from _common import AdapterError  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


# --------------------------------------------------------------------------
# fhir_r4 adapter -- against a real Synthea FHIR R4 bundle (see fixtures/README.md)
# --------------------------------------------------------------------------


def test_fhir_r4_parses_real_synthea_bundle():
    with open(FIXTURES / "synthea_fhir_bundle.json") as f:
        bundle = json.load(f)
    records = fhir_r4.parse_bundle(bundle)

    assert len(records) == 24
    counts = Counter(r["metric"] for r in records)
    assert counts == {"weight": 11, "length_recumbent": 9, "height_standing": 2, "bmi": 2}

    first = records[0]
    assert first["patient_id"] == "2389dd31-c3e8-4590-897f-5a9d2f359e2d"
    assert first["sex"] == "female"
    assert first["birth_date"] == "2016-07-24"
    assert first["observation_date"] == "2016-07-24"
    assert first["metric"] == "length_recumbent"  # newborn: 8302-2 resolved by age, not stature
    assert first["unit"] == "cm"


def test_fhir_r4_ambiguous_height_code_resolved_by_age():
    """The fixture never emits 8306-3 -- Synthea only ever uses the generic
    8302-2 code. This confirms the >=24mo observations in that same bundle
    are still correctly resolved to height_standing, not length_recumbent."""
    with open(FIXTURES / "synthea_fhir_bundle.json") as f:
        bundle = json.load(f)
    records = fhir_r4.parse_bundle(bundle)
    late_heights = [r for r in records if r["metric"] == "height_standing"]
    assert len(late_heights) == 2
    for r in late_heights:
        age_days = (
            growth.date.fromisoformat(r["observation_date"]) - growth.date.fromisoformat(r["birth_date"])
        ).days
        assert age_days / growth.AGE_DAYS_PER_MONTH >= 24


def test_fhir_r4_output_feeds_engine_end_to_end():
    with open(FIXTURES / "synthea_fhir_bundle.json") as f:
        bundle = json.load(f)
    records = [growth.MeasurementRecord(**r) for r in fhir_r4.parse_bundle(bundle)]
    results = growth.compute_batch(records)
    assert len(results) > 0
    assert all(r.indicator for r in results)
    # crosses no reference-unavailable gaps for this patient's own data
    assert not any("reference_unavailable" in r.flags for r in results)


def test_fhir_r4_rejects_bundle_without_patient():
    with pytest.raises(AdapterError):
        fhir_r4.parse_bundle({"resourceType": "Bundle", "entry": []})


def test_fhir_r4_rejects_unsupported_gender():
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p1", "birthDate": "2020-01-01", "gender": "unknown"}}
        ],
    }
    with pytest.raises(AdapterError):
        fhir_r4.parse_bundle(bundle)


def test_fhir_r4_skips_observations_without_valuequantity():
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p1", "birthDate": "2020-01-01", "gender": "male"}},
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {"coding": [{"code": "29463-7"}]},
                    "effectiveDateTime": "2020-06-01",
                    "component": [{"code": {"coding": [{"code": "8480-6"}]}, "valueQuantity": {"value": 110, "unit": "mmHg"}}],
                }
            },
        ],
    }
    assert fhir_r4.parse_bundle(bundle) == []


# --------------------------------------------------------------------------
# synthea CSV adapter -- against a real Synthea CSV export (see fixtures/README.md)
# --------------------------------------------------------------------------


def test_synthea_csv_parses_real_export():
    records = synthea.parse_csv(
        str(FIXTURES / "synthea_patients.csv"), str(FIXTURES / "synthea_observations.csv")
    )
    assert len(records) == 38
    counts = Counter(r["metric"] for r in records)
    assert counts == {
        "weight": 12, "head_circumference": 12, "length_recumbent": 10, "height_standing": 2, "bmi": 2,
    }
    assert all(r["patient_id"] == "b45d91ac-99ab-090a-df65-e60585ff87b3" for r in records)
    assert records[0]["sex"] == "female"
    assert records[0]["birth_date"] == "2023-04-09"


def test_synthea_csv_output_feeds_engine_end_to_end_across_who_cdc_boundary():
    records = [
        growth.MeasurementRecord(**r)
        for r in synthea.parse_csv(str(FIXTURES / "synthea_patients.csv"), str(FIXTURES / "synthea_observations.csv"))
    ]
    results = growth.compute_batch(records)
    references_used = {r.reference for r in results}
    assert references_used == {"WHO", "CDC"}  # this patient's own record spans the 24mo handoff


def test_synthea_csv_unknown_patient_id_raises():
    with pytest.raises(AdapterError):
        synthea.parse_csv(
            str(FIXTURES / "synthea_patients.csv"), str(FIXTURES / "synthea_observations.csv"), patient_id="nonexistent"
        )


def test_synthea_csv_explicit_patient_id_filters():
    real_id = "b45d91ac-99ab-090a-df65-e60585ff87b3"
    records = synthea.parse_csv(
        str(FIXTURES / "synthea_patients.csv"), str(FIXTURES / "synthea_observations.csv"), patient_id=real_id
    )
    assert len(records) == 38
    assert all(r["patient_id"] == real_id for r in records)


# --------------------------------------------------------------------------
# flat adapter
# --------------------------------------------------------------------------


def test_flat_csv_parses():
    records = flat.parse_csv(str(FIXTURES / "flat_measurements.csv"))
    assert len(records) == 4
    assert records[0] == {
        "patient_id": "flat-1", "sex": "male", "birth_date": "2024-01-15",
        "observation_date": "2024-01-15", "metric": "weight", "value": 3.4, "unit": "kg",
    }


def test_flat_json_parses():
    records = flat.parse_json(str(FIXTURES / "flat_measurements.json"))
    assert len(records) == 2
    assert records[0]["value"] == 3.4


def test_flat_csv_and_json_agree_on_shared_rows():
    csv_records = flat.parse_csv(str(FIXTURES / "flat_measurements.csv"))[:2]
    json_records = flat.parse_json(str(FIXTURES / "flat_measurements.json"))
    assert csv_records == json_records


def test_flat_missing_required_field_raises():
    with pytest.raises(AdapterError):
        flat._row_to_record({"patient_id": "p1", "sex": "male"}, row_num=2)


def test_flat_non_numeric_value_raises():
    row = {
        "patient_id": "p1", "sex": "male", "birth_date": "2020-01-01",
        "observation_date": "2020-06-01", "metric": "weight", "value": "not-a-number", "unit": "kg",
    }
    with pytest.raises(AdapterError):
        flat._row_to_record(row, row_num=2)


def test_flat_accepts_optional_age_months():
    row = {
        "patient_id": "p1", "sex": "female", "birth_date": "2020-01-01",
        "observation_date": "2020-06-01", "metric": "weight", "value": "8.0", "unit": "kg",
        "age_months": "5.5",
    }
    record = flat._row_to_record(row, row_num=2)
    assert record["age_months"] == 5.5


def test_flat_csv_with_column_map_parses_arbitrary_column_names():
    column_map = {
        "patient_id": "id", "sex": "gender", "birth_date": "DOB",
        "observation_date": "Visit Date", "metric": "measurement_type",
        "value": "Weight (kg)", "unit": "units",
    }
    records = flat.parse_csv(str(FIXTURES / "flat_measurements_custom_columns.csv"), column_map=column_map)
    assert len(records) == 2
    assert records[0] == {
        "patient_id": "flat-2", "sex": "female", "birth_date": "2023-06-01",
        "observation_date": "2023-06-01", "metric": "weight", "value": 3.2, "unit": "kg",
    }


def test_flat_column_map_only_needs_to_cover_the_differing_columns():
    # patient_id/metric/unit already match canonical names in this fixture;
    # only the renamed columns need an entry.
    row = {
        "patient_id": "p1", "sex_col": "male", "birth_date": "2020-01-01",
        "observation_date": "2020-06-01", "metric": "weight", "value": "8.0", "unit": "kg",
    }
    record = flat._row_to_record(row, row_num=2, column_map={"sex": "sex_col"})
    assert record["sex"] == "male"


def test_flat_column_map_error_message_names_the_looked_up_source_column():
    with pytest.raises(AdapterError, match="DOB"):
        flat._row_to_record(
            {"patient_id": "p1", "sex": "male"}, row_num=2, column_map={"birth_date": "DOB"}
        )


def test_flat_cli_with_map_flag(tmp_path):
    proc = subprocess.run(
        [
            sys.executable, str(Path(flat.__file__)),
            str(FIXTURES / "flat_measurements_custom_columns.csv"),
            "--map", str(FIXTURES / "flat_column_map.json"),
        ],
        capture_output=True, text=True, check=True,
    )
    records = json.loads(proc.stdout)
    assert len(records) == 2
    assert records[0]["patient_id"] == "flat-2"


# --------------------------------------------------------------------------
# Regression tests for code-review findings (see CHANGELOG.md)
# --------------------------------------------------------------------------


def test_flat_rejects_non_dict_column_map():
    """Regression test: a non-dict --map file used to crash with an
    unhandled AttributeError instead of the module's normal AdapterError."""
    with pytest.raises(AdapterError, match="column_map must be"):
        flat.parse_csv(str(FIXTURES / "flat_measurements.csv"), column_map=[1, 2, 3])


def test_flat_accepts_falsy_zero_as_a_present_value():
    """Regression test: `not _get(...)` treated a legitimate 0 as missing."""
    row = {
        "patient_id": "p1", "sex": "male", "birth_date": "2020-01-01",
        "observation_date": "2020-01-01", "metric": "weight", "value": 0, "unit": "kg",
    }
    record = flat._row_to_record(row, row_num=2)
    assert record["value"] == 0.0


# --------------------------------------------------------------------------
# Shared sex normalization
# --------------------------------------------------------------------------


@pytest.mark.parametrize("raw,expected", [("male", "male"), ("M", "male"), ("m", "male"), ("female", "female"), ("F", "female")])
def test_normalize_sex_aliases(raw, expected):
    from _common import normalize_sex

    assert normalize_sex(raw) == expected


def test_normalize_sex_rejects_other():
    from _common import normalize_sex

    with pytest.raises(AdapterError):
        normalize_sex("other")
