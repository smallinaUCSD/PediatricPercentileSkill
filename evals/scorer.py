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

A "json_block" scenario can additionally set `check_prose_consistency:
true`. This does NOT re-check that the JSON block itself is correct
(score_json_block already does that against a ground truth) -- it checks
that the agent's own PROSE description of the result agrees with the
agent's own appended JSON, so a model that reports "58th percentile" in
its summary while the JSON it pasted actually says 73.2 gets caught. An
agent could otherwise pass json_block scoring by pasting a correct JSON
block while describing a different, wrong number to the human reader.
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


_PERCENTILE_MENTION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:st|nd|rd|th)\s+percentile", re.IGNORECASE)


def extract_prose_percentile_mentions(text: str) -> list[float]:
    """Extracts percentile numbers mentioned in prose, outside fenced code
    blocks (so JSON content itself isn't double-counted as a 'mention')."""
    prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return [float(m) for m in _PERCENTILE_MENTION_RE.findall(prose)]


def score_prose_matches_json(text: str, tolerance: float = 1.5) -> ScoreResult:
    """Checks that every percentile number mentioned in the agent's prose is
    within `tolerance` of some percentile actually present in the JSON
    block it appended -- catches a prose/JSON inconsistency even when the
    JSON block itself would pass score_json_block.

    Known scope limits (deliberate, not bugs): only matches "Xth
    percentile" prose phrasing, not markdown-table cells (e.g. a "58.2th"
    column entry with no adjacent word "percentile") -- a scenario whose
    response is table-only will report "no percentile mentions found",
    which is a pass-by-absence, not a verification. The check also
    doesn't verify a mentioned number matches the *same indicator* it's
    prose-adjacent to -- it only checks the number appears somewhere in
    the full result set, so a correct-but-coincidental match to an
    unrelated indicator's value isn't distinguished from the intended
    one. This is a real limitation to keep in mind, not something to
    silently rely on as if it were exhaustive."""
    actual_results = extract_json_block(text)
    if actual_results is None:
        return ScoreResult(passed=False, details=["No parseable JSON array block found in response"])

    json_percentiles = [r["percentile"] for r in actual_results if r.get("percentile") is not None]
    prose_percentiles = extract_prose_percentile_mentions(text)

    details = []
    all_ok = True
    for p in prose_percentiles:
        if any(abs(p - jp) <= tolerance for jp in json_percentiles):
            details.append(f"ok: prose mentions {p}th percentile, matches a JSON entry within {tolerance}")
        else:
            all_ok = False
            nearby = sorted(json_percentiles, key=lambda jp: abs(jp - p))[:3]
            details.append(
                f"PROSE/JSON MISMATCH: prose states {p}th percentile, but no JSON entry is within "
                f"{tolerance} of that (closest JSON percentiles: {[round(x, 1) for x in nearby]})"
            )
    if not prose_percentiles:
        details.append("no percentile mentions found in prose (nothing to cross-check)")
    return ScoreResult(passed=all_ok, details=details)


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
        result = score_json_block(actual_results, scoring["expected_entries"])
        if scoring.get("check_prose_consistency"):
            prose_result = score_prose_matches_json(response_text, scoring.get("prose_tolerance", 1.5))
            result = ScoreResult(
                passed=result.passed and prose_result.passed,
                details=result.details + ["-- prose/JSON consistency --"] + prose_result.details,
            )
        return result
    if scoring["type"] == "text_checks":
        return score_text_checks(
            response_text,
            scoring.get("required_substrings", []),
            scoring.get("forbidden_substrings", []),
            scoring.get("required_any_groups"),
        )
    raise ValueError(f"unknown scoring type: {scoring['type']!r}")
