import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "adapters"))

import chart  # noqa: E402
import dataclasses  # noqa: E402
import fhir_r4  # noqa: E402
import growth  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _run_fhir_demo_patient():
    bundle = json.loads((FIXTURES / "synthea_fhir_bundle.json").read_text())
    records = [growth.MeasurementRecord(**r) for r in fhir_r4.parse_bundle(bundle)]
    return growth.compute_batch(records)


def test_curve_points_clamps_who_to_24_months():
    rows = chart._curve_points("WHO", "weight_for_age", "female", age_max_months=100)
    assert rows is not None
    assert all(age <= growth.WHO_CDC_HANDOFF_MONTHS for age, *_ in rows)


def test_curve_points_clamps_cdc_to_24_months_and_up():
    rows = chart._curve_points("CDC", "weight_for_age", "female", age_max_months=100)
    assert rows is not None
    assert all(age >= growth.WHO_CDC_HANDOFF_MONTHS for age, *_ in rows)


def test_curve_points_respects_age_max_months_cap():
    rows = chart._curve_points("WHO", "weight_for_age", "male", age_max_months=10)
    assert rows is not None
    assert all(age <= 10 for age, *_ in rows)


def test_curve_points_none_for_length_axis_indicator():
    # weight_for_length is a length-axis indicator, not age-axis -- chart.py
    # doesn't support it yet (see UNCHARTED_INDICATORS / module docstring).
    assert chart._curve_points("WHO", "weight_for_length", "female", 40) is None


def test_curve_points_none_for_unregistered_combination():
    assert chart._curve_points("WHO", "height_for_age", "male", 40) is None


def test_curve_points_cdc_length_for_age_no_longer_crashes():
    """Regression test for the repeated-header-row bug in cdc_lenageinf.csv
    (see scripts/growth.py _load_table and tests/golden/vectors.json
    cdc_length_for_age_explicit_override_12_5mo)."""
    rows = chart._curve_points("CDC", "length_for_age", "male", age_max_months=100)
    assert rows is not None
    assert len(rows) > 0


def test_render_patient_html_includes_expected_panels():
    results = [dataclasses.asdict(r) for r in _run_fhir_demo_patient()]
    html = chart.render_patient_html("test-patient", results)
    assert "Weight-for-age" in html
    assert "Length/height-for-age" in html
    assert "BMI-for-age" in html
    # this fixture patient has no head-circumference observations (see
    # tests/fixtures/README.md) so that panel should not appear
    assert "Head circumference-for-age" not in html


def test_render_patient_html_notes_uncharted_indicators():
    results = [
        {
            "patient_id": "p1", "reference": "WHO", "indicator": "weight_for_length", "age_months": 5.0,
            "sex": "male", "value": 6.5, "lms": {"L": 1, "M": 6, "S": 0.1}, "z_score": 0.1,
            "percentile": 55.0, "flags": [], "provenance": {},
        }
    ]
    html = chart.render_patient_html("p1", results)
    assert "weight_for_length" in html
    assert "Not charted" in html


def test_render_patient_html_handles_empty_results():
    html = chart.render_patient_html("p1", [])
    assert "No age-based indicators found" in html


def test_generate_charts_writes_one_file_per_patient(tmp_path):
    results = [dataclasses.asdict(r) for r in _run_fhir_demo_patient()]
    written = chart.generate_charts(results, tmp_path)
    assert len(written) == 1
    assert written[0].exists()
    assert written[0].read_text().startswith("<!DOCTYPE html>")


def test_generate_charts_sanitizes_patient_id_for_filename(tmp_path):
    results = [
        {
            "patient_id": "weird/id:with*chars", "reference": "WHO", "indicator": "weight_for_age",
            "age_months": 5.0, "sex": "male", "value": 6.5, "lms": {"L": 1, "M": 6, "S": 0.1},
            "z_score": 0.1, "percentile": 55.0, "flags": [], "provenance": {},
        }
    ]
    written = chart.generate_charts(results, tmp_path)
    assert len(written) == 1
    assert "/" not in written[0].name
    assert ":" not in written[0].name


def test_cli_end_to_end(tmp_path):
    results = [dataclasses.asdict(r) for r in _run_fhir_demo_patient()]
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(results))
    out_dir = tmp_path / "charts"
    exit_code = chart._main(["chart.py", str(results_path), "--out-dir", str(out_dir)])
    assert exit_code == 0
    assert len(list(out_dir.glob("chart_*.html"))) == 1
