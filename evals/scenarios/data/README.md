# Eval scenario fixtures

Unlike `tests/fixtures/` (genuine Synthea tool output), these are hand-constructed
to exercise a specific behavior:

- `implausible_weight.csv` — one synthetic 18-month-old with a weight of
  95.0 kg (a plausible decimal-point data-entry error for ~9.5 kg), used
  by `s4_implausible_value.json` to check that the agent surfaces the
  engine's `implausible_value` BIV flag rather than reporting a
  ~100th-percentile result at face value. Not real patient data.
