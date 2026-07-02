"""Deterministic scorer for agent-behavioral eval scenarios.

This does NOT test scripts/growth.py's math (tests/golden/ already does
that, exhaustively). It tests whether an agent *using the skill* -- given
only SKILL.md, the adapters, and a scenario prompt -- behaves correctly:
picks the right adapter, gets the right numbers into its final answer,
surfaces flags instead of burying them, and asks rather than guesses when
required data is missing.

Two scoring modes, chosen per-scenario:

- "json_block": the scenario asks the agent to end its response with the
  raw JSON output of scripts/growth.py in a fenced code block. The scorer
  extracts it and checks specific expected entries (indicator, age,
  reference, percentile within tolerance, required flags) -- this is
  checking the agent transcribed/used the tool output correctly, not
  re-deriving numbers from prose.
- "text_checks": behavioral scenarios (missing data, out-of-scope
  requests, data-quality flags) where the expected behavior is best
  captured as required/forbidden substrings in the agent's final answer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class ScoreResult:
    passed: bool
    details: list[str] = field(default_factory=list)


def extract_json_block(text: str) -> list[dict] | None:
    """Extracts the last fenced ```json ... ``` (or bare ```...```) block that parses as a JSON list."""
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", text, flags=re.DOTALL)
    for block in reversed(blocks):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            return parsed
    return None


def _find_matching_entry(actual_results: list[dict], expected: dict) -> dict | None:
    tolerance_months = expected.get("tolerance_months", 0.5)
    candidates = [
        r
        for r in actual_results
        if r.get("indicator") == expected["indicator"]
        and r.get("age_months") is not None
        and abs(r["age_months"] - expected["age_months_approx"]) <= tolerance_months
    ]
    return candidates[0] if candidates else None


def score_json_block(actual_results: list[dict], expected_entries: list[dict]) -> ScoreResult:
    details = []
    suite_ok = True
    for expected in expected_entries:
        entry = _find_matching_entry(actual_results, expected)
        label = f"{expected['indicator']} @ ~{expected['age_months_approx']}mo"
        if entry is None:
            suite_ok = False
            details.append(f"MISSING: no result found for {label}")
            continue

        entry_ok = True
        if entry.get("reference") != expected["reference"]:
            entry_ok = False
            details.append(
                f"WRONG REFERENCE: {label} expected {expected['reference']}, got {entry.get('reference')}"
            )

        if "percentile" in expected:
            actual_pct = entry.get("percentile")
            tol = expected.get("percentile_tolerance", 1.0)
            if actual_pct is None or abs(actual_pct - expected["percentile"]) > tol:
                entry_ok = False
                details.append(
                    f"WRONG PERCENTILE: {label} expected {expected['percentile']} (+/-{tol}), got {actual_pct}"
                )

        required_flags = set(expected.get("flags_subset", []))
        actual_flags = set(entry.get("flags", []))
        if not required_flags.issubset(actual_flags):
            entry_ok = False
            details.append(
                f"MISSING FLAGS: {label} expected flags including {sorted(required_flags)}, got {sorted(actual_flags)}"
            )

        if entry_ok:
            details.append(f"ok: {label} -> reference={entry.get('reference')} percentile={entry.get('percentile')}")
        else:
            suite_ok = False

    return ScoreResult(passed=suite_ok, details=details)


def score_text_checks(
    text: str,
    required_substrings: list[str],
    forbidden_substrings: list[str],
    required_any_groups: list[list[str]] | None = None,
) -> ScoreResult:
    details = []
    all_ok = True
    lower = text.lower()
    for s in required_substrings:
        if s.lower() not in lower:
            all_ok = False
            details.append(f"MISSING required text: {s!r}")
        else:
            details.append(f"ok: found required text {s!r}")
    for group in required_any_groups or []:
        if any(s.lower() in lower for s in group):
            details.append(f"ok: found at least one of {group!r}")
        else:
            all_ok = False
            details.append(f"MISSING: none of {group!r} found")
    for s in forbidden_substrings:
        if s.lower() in lower:
            all_ok = False
            details.append(f"FOUND forbidden text: {s!r}")
        else:
            details.append(f"ok: absent forbidden text {s!r}")
    return ScoreResult(passed=all_ok, details=details)


def score_scenario(scenario: dict, response_text: str) -> ScoreResult:
    scoring = scenario["scoring"]
    if scoring["type"] == "json_block":
        actual_results = extract_json_block(response_text)
        if actual_results is None:
            return ScoreResult(passed=False, details=["No parseable JSON array block found in response"])
        return score_json_block(actual_results, scoring["expected_entries"])
    if scoring["type"] == "text_checks":
        return score_text_checks(
            response_text,
            scoring.get("required_substrings", []),
            scoring.get("forbidden_substrings", []),
            scoring.get("required_any_groups"),
        )
    raise ValueError(f"unknown scoring type: {scoring['type']!r}")
