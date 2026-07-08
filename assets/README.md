# Assets

- `growth-chart-example.png` — a real, unedited screenshot of
  `scripts/chart.py`'s output for the Synthea CSV patient in
  `tests/fixtures/` (the one whose record crosses the WHO→CDC boundary).
  Not a mockup. Regenerate after a chart-rendering change with:

  ```bash
  uv run adapters/synthea.py tests/fixtures/synthea_patients.csv tests/fixtures/synthea_observations.csv > /tmp/records.json
  uv run scripts/growth.py /tmp/records.json > /tmp/results.json
  uv run scripts/chart.py /tmp/results.json --out-dir /tmp/charts
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
    --screenshot=/tmp/raw.png --window-size=1600,1400 \
    "file:///tmp/charts/chart_b45d91ac-99ab-090a-df65-e60585ff87b3.html"
  ```

  then crop to content (trim the white margin, e.g. with Pillow's
  `ImageChops.difference` against a white background) before committing
  as `assets/growth-chart-example.png`. The window size needs to be
  comfortably larger than the rendered content (`scripts/chart.py`'s
  `SVG_WIDTH`/`SVG_HEIGHT` and the `.chart` CSS width) or the screenshot
  clips panels instead of just cropping whitespace.

  `demo/warren_chart_example.png` is the same process against the FHIR
  patient (`tests/fixtures/synthea_fhir_bundle.json` via `adapters/fhir_r4.py`).
