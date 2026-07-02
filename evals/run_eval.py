"""CLI for scoring a captured agent response against an eval scenario.

Usage:
    uv run evals/run_eval.py evals/scenarios/s1_fhir_happy_path.json evals/responses/s1_fhir_happy_path.txt
    uv run evals/run_eval.py --all   # scores every scenarios/*.json against responses/<id>.txt

The harness does not itself spawn an agent -- capturing a response is a
separate step (an agent, given the scenario's prompt and read access to
this repo, produces a final answer; that answer text is saved to
evals/responses/<scenario id>.txt). This script only scores an
already-captured response, deterministically and reproducibly. See
EVALUATION.md for how the committed responses/ were produced.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scorer import score_scenario  # noqa: E402

EVALS_DIR = Path(__file__).resolve().parent
SCENARIOS_DIR = EVALS_DIR / "scenarios"
RESPONSES_DIR = EVALS_DIR / "responses"


def run_one(scenario_path: Path, response_path: Path) -> bool:
    scenario = json.loads(scenario_path.read_text())
    response_text = response_path.read_text()
    result = score_scenario(scenario, response_text)
    status = "PASS" if result.passed else "FAIL"
    print(f"[{status}] {scenario['id']}: {scenario['description']}")
    for line in result.details:
        print(f"    {line}")
    return result.passed


def run_all() -> int:
    scenario_paths = sorted(SCENARIOS_DIR.glob("*.json"))
    if not scenario_paths:
        print("no scenarios found", file=sys.stderr)
        return 2
    all_passed = True
    for scenario_path in scenario_paths:
        scenario_id = json.loads(scenario_path.read_text())["id"]
        response_path = RESPONSES_DIR / f"{scenario_id}.txt"
        if not response_path.exists():
            print(f"[SKIP] {scenario_id}: no captured response at {response_path}")
            continue
        passed = run_one(scenario_path, response_path)
        all_passed = all_passed and passed
    return 0 if all_passed else 1


def main(argv: list[str]) -> int:
    if argv[1:] == ["--all"]:
        return run_all()
    if len(argv) == 3:
        return 0 if run_one(Path(argv[1]), Path(argv[2])) else 1
    print("usage: run_eval.py <scenario.json> <response.txt>  |  run_eval.py --all", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
