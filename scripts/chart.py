"""Self-contained interactive HTML growth chart generator.

Consumes the GrowthResult JSON that scripts/growth.py produces (not raw
MeasurementRecords) and renders one HTML file per patient: standard
percentile curves (3rd/5th/10th/25th/50th/75th/90th/95th/97th) for each
age-based indicator present in that patient's results, with the
patient's own visits plotted and connected on top. Pure SVG plus a small
hand-written inline <script> for hover tooltips -- no charting library,
no CDN, no new Python dependency. Opens in any browser, fully offline,
same as the engine itself.

Curves reuse the engine's own reference-table selection (growth.py's
_select_table / _load_table) rather than re-deriving anything, and which
(indicator, reference standard) pairs get a curve is derived from what
actually appears in the patient's own results -- not hardcoded, since the
engine's own default selection can pick either standard for the same
indicator depending on age (e.g. a recumbent-length measurement at 24-36
months is a real, unremarkable case that resolves to CDC by default, not
just via explicit override).

Known limitations (also noted in README.md):
- weight-for-length and weight-for-stature are not charted -- they need
  a length/height x-axis rather than age, and GrowthResult doesn't carry
  that axis value (only the weight being percentiled). Charting these
  is tracked as future work, not silently dropped.
- Percentile curves always use the ordinary LMS transform, including
  for BMI-for-age -- matching how CDC's own printed growth charts draw
  the standard 3rd-97th lines. The CDC 2022 extended method only changes
  how an individual point above the 95th percentile is scored, not how
  the reference curves themselves are drawn.
- A result flagged reference_unavailable (percentile/z_score are None)
  is still plotted by its raw value, but its tooltip says so instead of
  showing a percentile.
- This is an orientation aid, not a clinical-grade chart image -- it has
  no independent test suite verifying rendered pixel positions, unlike
  the engine's numeric output (tests/golden/).

Usage:
    uv run scripts/chart.py results.json --out-dir charts/
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import growth  # noqa: E402

PERCENTILE_LINES = [3, 5, 10, 25, 50, 75, 90, 95, 97]
_Z_BY_PERCENTILE = {p: growth.norm.ppf(p / 100) for p in PERCENTILE_LINES}

# panel_key -> (title, y-axis unit, [indicator names that feed this panel])
PANELS = {
    "weight_for_age": ("Weight-for-age", "kg", ["weight_for_age"]),
    "length_height_for_age": ("Length/height-for-age", "cm", ["length_for_age", "height_for_age"]),
    "bmi_for_age": ("BMI-for-age", "kg/m2", ["bmi_for_age"]),
    "head_circumference_for_age": ("Head circumference-for-age", "cm", ["head_circumference_for_age"]),
}

# Indicators charting doesn't support yet -- see module docstring.
UNCHARTED_INDICATORS = {"weight_for_length", "weight_for_stature"}

# Representative ages guaranteed to fall inside a WHO or CDC table's valid
# range respectively, for reusing growth._select_table's real table-selection
# logic (which requires an axis value) rather than reimplementing it.
_WHO_PROBE_AGE_MONTHS = 0.0
_CDC_PROBE_AGE_MONTHS = growth.WHO_CDC_HANDOFF_MONTHS

SVG_WIDTH, SVG_HEIGHT = 980, 520
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 64, 40, 28, 48
PLOT_W = SVG_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
PLOT_H = SVG_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM


def _curve_points(standard: str, indicator: str, sex: str, age_max_months: float) -> list[tuple[float, float]] | None:
    """Returns [(age_months, L, M, S)] rows sampled at the reference table's own
    tabulated ages -- no smoothing/interpolation introduced beyond what the
    table already represents. Clamped to the WHO/CDC default-selection
    boundary (see references/METHODOLOGY.md section 2) rather than each
    table's full physical extent, so a WHO curve doesn't visually overlap a
    CDC curve drawn for the same panel."""
    probe_age = _WHO_PROBE_AGE_MONTHS if standard == "WHO" else _CDC_PROBE_AGE_MONTHS
    spec = growth._select_table(standard, indicator, probe_age)
    if spec is None or spec.axis_semantic != "age":
        return None
    table = growth._load_table(spec)
    sex_code = growth.SEX_CODE[sex]
    rows = table[sex_code]

    to_months = (lambda a: a / growth.AGE_DAYS_PER_MONTH) if spec.file_axis_unit == "days" else (lambda a: a)
    out = []
    for row in rows:
        age_months = to_months(row[0])
        if standard == "WHO" and age_months > growth.WHO_CDC_HANDOFF_MONTHS:
            break
        if standard == "CDC" and age_months < growth.WHO_CDC_HANDOFF_MONTHS:
            continue
        if age_months > age_max_months:
            break
        L, M, S = row[1], row[2], row[3]
        out.append((age_months, L, M, S))
    return out


def _build_panel_svg(title: str, unit: str, curves: list[tuple[str, list]], patient_points: list[dict]) -> str:
    safe_title = html.escape(title)
    all_ages = [p["age_months"] for p in patient_points]
    for _label, rows in curves:
        for row in rows:
            all_ages.append(row[0])
    all_values = [p["value"] for p in patient_points]
    for _label, rows in curves:
        for row in rows:
            L, M, S = row[1], row[2], row[3]
            for pct in (PERCENTILE_LINES[0], PERCENTILE_LINES[-1]):
                all_values.append(growth.lms_value_at_z(_Z_BY_PERCENTILE[pct], L, M, S))

    if not all_ages or not all_values:
        return f'<div class="panel"><h3>{safe_title}</h3><p class="empty">No data for this indicator.</p></div>'

    age_min, age_max = 0.0, max(all_ages) * 1.0 or 1.0
    val_min, val_max = min(all_values), max(all_values)
    val_pad = (val_max - val_min) * 0.08 or 1.0
    val_min, val_max = val_min - val_pad, val_max + val_pad

    def x(age):
        frac = 0 if age_max == age_min else (age - age_min) / (age_max - age_min)
        return MARGIN_LEFT + frac * PLOT_W

    def y(val):
        frac = 0 if val_max == val_min else (val - val_min) / (val_max - val_min)
        return MARGIN_TOP + (1 - frac) * PLOT_H

    svg_parts = [
        f'<svg viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" class="chart" data-title="{safe_title}">',
        f'<rect x="{MARGIN_LEFT}" y="{MARGIN_TOP}" width="{PLOT_W}" height="{PLOT_H}" fill="none" stroke="#ccc"/>',
    ]

    # percentile curves, one polyline per percentile per (indicator, standard) pair
    # present. A panel can have more than one curve segment (e.g. a WHO segment
    # ending at 24 months plus a CDC segment continuing further) -- only the
    # segment that reaches furthest right gets end-of-line percentile labels,
    # otherwise every segment's endpoint would get its own label and a WHO
    # segment ending mid-chart would print a confusing second set of numbers
    # that don't belong to the chart's right edge.
    rightmost_idx = None
    if curves:
        rightmost_idx = max(
            range(len(curves)),
            key=lambda i: max((row[0] for row in curves[i][1]), default=-1),
        )
    for i, (_label, rows) in enumerate(curves):
        if not rows:
            continue
        for pct in PERCENTILE_LINES:
            z = _Z_BY_PERCENTILE[pct]
            pts = [(row[0], growth.lms_value_at_z(z, row[1], row[2], row[3])) for row in rows]
            path = " ".join(f"{x(a):.1f},{y(v):.1f}" for a, v in pts)
            stroke = "#2b6cb0" if pct == 50 else "#a0aec0"
            width = 1.6 if pct == 50 else 0.8
            dash = "" if pct == 50 else ' stroke-dasharray="2,2"'
            svg_parts.append(f'<polyline points="{path}" fill="none" stroke="{stroke}" stroke-width="{width}"{dash}/>')
            if pts and i == rightmost_idx:
                lx, ly = pts[-1]
                svg_parts.append(
                    f'<text x="{x(lx) + 3:.1f}" y="{y(ly) + 3:.1f}" class="pct-label">{pct}</text>'
                )

    # patient trajectory
    ordered = sorted(patient_points, key=lambda p: p["age_months"])
    if ordered:
        path = " ".join(f"{x(p['age_months']):.1f},{y(p['value']):.1f}" for p in ordered)
        svg_parts.append(f'<polyline points="{path}" fill="none" stroke="#c53030" stroke-width="2.2"/>')
        for p in ordered:
            cx, cy = x(p["age_months"]), y(p["value"])
            if p["percentile"] is None:
                pct_text = "reference unavailable"
            else:
                pct_text = f"{p['percentile']:.1f}th pct ({p['reference']})"
            tooltip = (
                f"age {p['age_months']:.1f}mo | {p['value']:.2f} {unit} | {pct_text}"
                + (f" | flags: {', '.join(p['flags'])}" if p["flags"] else "")
            )
            svg_parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" fill="#c53030" '
                f'class="patient-point" data-tooltip="{html.escape(tooltip)}"/>'
            )

    svg_parts.append(f'<text x="{MARGIN_LEFT}" y="{SVG_HEIGHT - 8}" class="axis-label">age (months)</text>')
    svg_parts.append(
        f'<text x="8" y="{MARGIN_TOP + 10}" class="axis-label" '
        f'transform="rotate(-90, 14, {MARGIN_TOP + 10})">{html.escape(unit)}</text>'
    )
    svg_parts.append("</svg>")

    return f'<div class="panel"><h3>{safe_title}</h3>{"".join(svg_parts)}</div>'


def render_patient_html(patient_id: str, results: list[dict]) -> str:
    safe_patient_id = html.escape(patient_id)
    by_indicator: dict[str, list[dict]] = {}
    for r in results:
        by_indicator.setdefault(r["indicator"], []).append(r)

    uncharted_present = sorted(set(by_indicator) & UNCHARTED_INDICATORS)

    panels_html = []
    for title, unit, indicator_names in PANELS.values():
        points = []
        for ind in indicator_names:
            points.extend(by_indicator.get(ind, []))
        if not points:
            continue
        sex = points[0]["sex"]
        max_age = max(p["age_months"] for p in points)

        # Which (indicator, standard) pairs to draw a curve for is derived
        # from what actually occurs in this patient's own results, not
        # assumed -- the engine's default (non-override) selection can
        # produce either standard for the same indicator depending on age
        # (e.g. CDC length_for_age for a recumbent-length measurement at
        # 24-36 months is a real default case, not override-only).
        observed_pairs = sorted({(p["indicator"], p["reference"]) for p in points if p["reference"]})
        curves = []
        for ind, standard in observed_pairs:
            rows = _curve_points(standard, ind, sex, max_age * 1.15)
            if rows:
                curves.append((f"{ind}:{standard}", rows))
        panels_html.append(_build_panel_svg(title, unit, curves, points))

    limitations_note = ""
    if uncharted_present:
        escaped = ", ".join(html.escape(i) for i in uncharted_present)
        limitations_note = (
            f'<p class="limitation">Not charted (no age x-axis available for these yet): '
            f"{escaped}. See scripts/chart.py docstring.</p>"
        )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Growth chart -- {safe_patient_id}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; color: #1a202c; }}
h1 {{ font-size: 1.3rem; }}
h3 {{ font-size: 1rem; margin-bottom: 4px; }}
.panel {{ display: inline-block; margin: 16px; vertical-align: top; }}
.chart {{ width: 700px; height: auto; }}
.pct-label {{ font-size: 11px; fill: #718096; }}
.axis-label {{ font-size: 13px; fill: #4a5568; }}
.empty {{ color: #a0aec0; font-style: italic; }}
.limitation {{ color: #975a16; font-size: 0.85rem; }}
.disclaimer {{ color: #718096; font-size: 0.8rem; max-width: 720px; }}
#tooltip {{
  position: fixed; display: none; background: #1a202c; color: white;
  padding: 6px 10px; border-radius: 4px; font-size: 12px; pointer-events: none;
  z-index: 10;
}}
</style>
</head>
<body>
<h1>Growth chart -- patient {safe_patient_id}</h1>
<p class="disclaimer">Orientation aid only, not a clinical-grade chart image or a
diagnostic tool. Blue dashed lines are standard percentile curves (3rd-97th,
median in solid blue); red is this patient's own trajectory. Hover a red
point for exact values.</p>
{"".join(panels_html) or '<p class="empty">No age-based indicators found in this file.</p>'}
{limitations_note}
<div id="tooltip"></div>
<script>
const tooltip = document.getElementById('tooltip');
document.querySelectorAll('.patient-point').forEach(function(el) {{
  el.addEventListener('mousemove', function(e) {{
    tooltip.style.display = 'block';
    tooltip.style.left = (e.clientX + 12) + 'px';
    tooltip.style.top = (e.clientY + 12) + 'px';
    tooltip.textContent = el.getAttribute('data-tooltip');
  }});
  el.addEventListener('mouseleave', function() {{ tooltip.style.display = 'none'; }});
}});
</script>
</body>
</html>
"""


def generate_charts(results: list[dict], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    by_patient: dict[str, list[dict]] = {}
    for r in results:
        by_patient.setdefault(r["patient_id"], []).append(r)

    written = []
    for patient_id, patient_results in by_patient.items():
        html_text = render_patient_html(patient_id, patient_results)
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in patient_id)
        out_path = out_dir / f"chart_{safe_id}.html"
        out_path.write_text(html_text)
        written.append(out_path)
    return written


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_json", help="GrowthResult JSON produced by scripts/growth.py")
    parser.add_argument("--out-dir", default="charts", help="directory to write chart_<patient_id>.html files into")
    args = parser.parse_args(argv[1:])

    with open(args.results_json) as f:
        results = json.load(f)

    written = generate_charts(results, Path(args.out_dir))
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
