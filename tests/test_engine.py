import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import growth  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _load_golden(name):
    with open(GOLDEN_DIR / name) as f:
        return json.load(f)


def _assert_close(actual, expected, tolerance, label):
    if expected is None:
        assert actual is None, f"{label}: expected None, got {actual}"
        return
    assert actual is not None, f"{label}: expected {expected}, got None"
    assert math.isclose(actual, expected, abs_tol=tolerance), (
        f"{label}: expected {expected}, got {actual} (tolerance {tolerance})"
    )


# --------------------------------------------------------------------------
# Frozen golden vectors (tests/golden/) -- see CONTRIBUTING.md
# --------------------------------------------------------------------------

FORMULA_VECTORS = _load_golden("formula_examples.json")["vectors"]
ENGINE_VECTORS = _load_golden("vectors.json")["vectors"]
PAIRED_VECTORS = _load_golden("vectors.json")["paired_vectors"]


@pytest.mark.parametrize("vector", FORMULA_VECTORS, ids=[v["id"] for v in FORMULA_VECTORS])
def test_formula_golden_vectors(vector):
    fn = getattr(growth, vector["function"])
    args = vector["args"]
    actual = fn(args["x"], args["L"], args["M"], args["S"])
    _assert_close(actual, vector["expect"], vector["tolerance"], vector["id"])


@pytest.mark.parametrize("vector", ENGINE_VECTORS, ids=[v["id"] for v in ENGINE_VECTORS])
def test_engine_golden_vectors(vector):
    record = growth.MeasurementRecord(**vector["record"])
    result = growth.compute_for_age(record, reference_override=vector.get("reference_override"))
    expect = vector["expect"]
    assert result.reference == expect["reference"], vector["id"]
    assert result.indicator == expect["indicator"], vector["id"]
    _assert_close(result.z_score, expect["z_score"], expect["z_tolerance"], f"{vector['id']} z_score")
    _assert_close(result.percentile, expect["percentile"], expect["percentile_tolerance"], f"{vector['id']} percentile")
    assert set(result.flags) == set(expect["flags"]), f"{vector['id']} flags: {result.flags}"


@pytest.mark.parametrize("vector", PAIRED_VECTORS, ids=[v["id"] for v in PAIRED_VECTORS])
def test_paired_golden_vectors(vector):
    weight_record = growth.MeasurementRecord(**vector["weight_record"])
    other_record = growth.MeasurementRecord(**vector["length_or_height_record"])
    result = growth.compute_weight_for_length_or_stature(weight_record, other_record)
    expect = vector["expect"]
    assert result.reference == expect["reference"], vector["id"]
    assert result.indicator == expect["indicator"], vector["id"]
    _assert_close(result.z_score, expect["z_score"], expect["z_tolerance"], f"{vector['id']} z_score")
    _assert_close(result.percentile, expect["percentile"], expect["percentile_tolerance"], f"{vector['id']} percentile")
    assert set(result.flags) == set(expect["flags"]), f"{vector['id']} flags: {result.flags}"


def test_golden_fixture_files_are_syntactically_frozen():
    """Sanity check that both golden files still carry the DO NOT MODIFY banner."""
    for name in ("formula_examples.json", "vectors.json"):
        data = _load_golden(name)
        assert data["_banner"].startswith("DO NOT MODIFY")


# --------------------------------------------------------------------------
# Engine mechanics (not sourced clinical values -- ordinary regression tests)
# --------------------------------------------------------------------------


def test_interpolation_is_linear_between_bracketing_rows():
    rows = [(0.0, -1.0, 10.0, 0.1), (2.0, -1.0, 12.0, 0.1)]
    L, M, S = growth._interpolate(rows, 1.0)
    assert M == pytest.approx(11.0)
    L, M, S = growth._interpolate(rows, 0.5)
    assert M == pytest.approx(10.5)


def test_interpolation_exact_row_hit_returns_row_unmodified():
    rows = [(0.0, -1.0, 10.0, 0.1), (2.0, -1.0, 12.0, 0.1)]
    assert growth._interpolate(rows, 2.0) == (-1.0, 12.0, 0.1)


def test_unit_conversion_lb_matches_equivalent_kg():
    kg_record = growth.MeasurementRecord(
        "p", "male", "2020-01-01", "2020-01-01", "weight", 9.7, "kg", age_months=9.5
    )
    lb_record = growth.MeasurementRecord(
        "p", "male", "2020-01-01", "2020-01-01", "weight", 9.7 / growth.LB_TO_KG, "lb", age_months=9.5
    )
    kg_result = growth.compute_for_age(kg_record, reference_override="CDC")
    lb_result = growth.compute_for_age(lb_record, reference_override="CDC")
    assert kg_result.z_score == pytest.approx(lb_result.z_score, abs=1e-9)


def test_unsupported_unit_raises():
    record = growth.MeasurementRecord(
        "p", "male", "2020-01-01", "2020-01-01", "weight", 9.7, "stone", age_months=9.5
    )
    with pytest.raises(growth.GrowthEngineError):
        growth.compute_for_age(record)


def test_unsupported_sex_raises():
    record = growth.MeasurementRecord(
        "p", "other", "2020-01-01", "2020-01-01", "weight", 9.7, "kg", age_months=9.5
    )
    with pytest.raises(growth.GrowthEngineError):
        growth.compute_for_age(record)


def test_age_computed_from_dates_when_age_months_absent():
    record = growth.MeasurementRecord(
        "p", "male", "2020-01-01", "2022-01-01", "weight", 12.0, "kg"
    )
    result = growth.compute_for_age(record)
    assert result.age_months == pytest.approx(731 / growth.AGE_DAYS_PER_MONTH)


def test_compute_batch_derives_bmi_when_not_supplied():
    records = [
        growth.MeasurementRecord("p", "male", "2020-01-01", "2025-01-01", "weight", 18.0, "kg"),
        growth.MeasurementRecord("p", "male", "2020-01-01", "2025-01-01", "height_standing", 110.0, "cm"),
    ]
    results = growth.compute_batch(records)
    indicators = {r.indicator for r in results}
    assert "weight_for_age" in indicators
    assert "height_for_age" in indicators
    assert "weight_for_stature" in indicators
    bmi_results = [r for r in results if r.indicator == "bmi_for_age"]
    assert len(bmi_results) == 1
    assert "bmi_derived" in bmi_results[0].flags
    expected_bmi = 18.0 / (1.10**2)
    assert bmi_results[0].value == pytest.approx(expected_bmi)


def test_compute_batch_does_not_derive_bmi_when_already_supplied():
    records = [
        growth.MeasurementRecord("p", "male", "2020-01-01", "2025-01-01", "weight", 18.0, "kg"),
        growth.MeasurementRecord("p", "male", "2020-01-01", "2025-01-01", "height_standing", 110.0, "cm"),
        growth.MeasurementRecord("p", "male", "2020-01-01", "2025-01-01", "bmi", 15.0, "kg/m2"),
    ]
    results = growth.compute_batch(records)
    bmi_results = [r for r in results if r.indicator == "bmi_for_age"]
    assert len(bmi_results) == 1
    assert "bmi_derived" not in bmi_results[0].flags
    assert bmi_results[0].value == pytest.approx(15.0)


def test_cli_round_trip(tmp_path):
    input_path = tmp_path / "records.json"
    input_path.write_text(json.dumps([
        {
            "patient_id": "cli-1",
            "sex": "male",
            "birth_date": "2020-01-01",
            "observation_date": "2020-01-01",
            "metric": "weight",
            "value": 9.7,
            "unit": "kg",
            "age_months": 9.5,
        }
    ]))
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "growth.py"), str(input_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    output = json.loads(proc.stdout)
    assert len(output) == 1
    assert output[0]["indicator"] == "weight_for_age"
    assert output[0]["reference"] == "WHO"
