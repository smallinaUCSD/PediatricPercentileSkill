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


# --------------------------------------------------------------------------
# Regression tests for code-review findings (see CHANGELOG.md)
# --------------------------------------------------------------------------


def test_cdc_length_for_age_default_case_gets_a_curve():
    """Regression test: a recumbent-length measurement at 24-36 months
    resolves to CDC by DEFAULT (not just via explicit override) since
    cdc_lenageinf.csv covers 0-36 months -- chart.py must not assume
    length_for_age is WHO-only. Previously this patient's point would be
    plotted with no percentile curve behind it."""
    r_who = growth.compute_for_age(
        growth.MeasurementRecord("p", "male", "2020-01-01", "2020-01-01", "length_recumbent", 80.0, "cm", age_months=10.0)
    )
    r_cdc = growth.compute_for_age(
        growth.MeasurementRecord("p", "male", "2020-01-01", "2020-01-01", "length_recumbent", 88.0, "cm", age_months=30.0)
    )
    assert r_cdc.reference == "CDC"  # confirms this is the real default behavior, not a test setup error

    results = [dataclasses.asdict(r_who), dataclasses.asdict(r_cdc)]
    curves_seen = set()
    points = [r for r in results if r["indicator"] in ("length_for_age", "height_for_age")]
    sex = points[0]["sex"]
    max_age = max(p["age_months"] for p in points)
    for ind, standard in sorted({(p["indicator"], p["reference"]) for p in points}):
        if chart._curve_points(standard, ind, sex, max_age * 1.15):
            curves_seen.add((ind, standard))
    assert ("length_for_age", "WHO") in curves_seen
    assert ("length_for_age", "CDC") in curves_seen


def test_render_patient_html_handles_reference_unavailable_without_crashing():
    """Regression test: percentile/z_score are None whenever a result is
    flagged reference_unavailable; the tooltip formatter must not crash."""
    r = growth.compute_for_age(
        growth.MeasurementRecord("p", "male", "2020-01-01", "2020-01-01", "head_circumference", 50.0, "cm", age_months=48)
    )
    assert r.percentile is None and "reference_unavailable" in r.flags  # confirms the precondition
    html_out = chart.render_patient_html("p", [dataclasses.asdict(r)])
    assert "reference unavailable" in html_out


def test_render_patient_html_escapes_patient_id():
    """Regression test: patient_id was interpolated unescaped into HTML,
    so a patient_id containing markup could inject into the chart file."""
    malicious_id = 'p"</title><script>alert(1)</script>'
    html_out = chart.render_patient_html(malicious_id, [])
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_curve_points_uses_growth_select_table_not_a_reimplementation():
    """Regression test: _curve_points used to pick a table via its own
    max(range_min) without checking age coverage, which happened to work
    only by coincidence. It should now delegate to growth._select_table."""
    rows = chart._curve_points("CDC", "weight_for_age", "male", age_max_months=100)
    spec = growth._select_table("CDC", "weight_for_age", chart._CDC_PROBE_AGE_MONTHS)
    assert rows is not None
    assert spec.filename == "cdc_wtage.csv"
