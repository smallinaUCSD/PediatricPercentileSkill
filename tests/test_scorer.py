import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evals"))

import scorer  # noqa: E402


def test_extract_json_block_finds_fenced_json():
    text = "Here's the data:\n```json\n[{\"a\": 1}]\n```\nDone."
    assert scorer.extract_json_block(text) == [{"a": 1}]


def test_extract_json_block_uses_last_valid_block():
    text = "not json:\n```\nnope\n```\nreal one:\n```json\n[{\"a\": 2}]\n```"
    assert scorer.extract_json_block(text) == [{"a": 2}]


def test_extract_json_block_returns_none_when_absent():
    assert scorer.extract_json_block("just prose, no code blocks") is None


def test_score_json_block_passes_on_matching_entry():
    actual = [{"indicator": "weight_for_age", "age_months": 9.5, "reference": "CDC", "percentile": 58.2, "flags": []}]
    expected = [{"indicator": "weight_for_age", "age_months_approx": 9.5, "reference": "CDC", "percentile": 58.2, "percentile_tolerance": 0.5}]
    result = scorer.score_json_block(actual, expected)
    assert result.passed


def test_score_json_block_fails_on_wrong_reference():
    actual = [{"indicator": "weight_for_age", "age_months": 9.5, "reference": "WHO", "percentile": 58.2, "flags": []}]
    expected = [{"indicator": "weight_for_age", "age_months_approx": 9.5, "reference": "CDC", "percentile": 58.2}]
    result = scorer.score_json_block(actual, expected)
    assert not result.passed
    assert any("WRONG REFERENCE" in d for d in result.details)


def test_score_json_block_fails_on_missing_entry():
    result = scorer.score_json_block([], [{"indicator": "weight_for_age", "age_months_approx": 9.5, "reference": "CDC"}])
    assert not result.passed
    assert any("MISSING" in d for d in result.details)


def test_score_json_block_fails_on_percentile_out_of_tolerance():
    actual = [{"indicator": "bmi_for_age", "age_months": 24.0, "reference": "CDC", "percentile": 50.0, "flags": []}]
    expected = [{"indicator": "bmi_for_age", "age_months_approx": 24.0, "reference": "CDC", "percentile": 97.0, "percentile_tolerance": 1.0}]
    result = scorer.score_json_block(actual, expected)
    assert not result.passed


def test_score_json_block_fails_on_missing_required_flag():
    actual = [{"indicator": "bmi_for_age", "age_months": 24.0, "reference": "CDC", "percentile": 97.7, "flags": []}]
    expected = [{"indicator": "bmi_for_age", "age_months_approx": 24.0, "reference": "CDC", "flags_subset": ["extended_bmi_used"]}]
    result = scorer.score_json_block(actual, expected)
    assert not result.passed
    assert any("MISSING FLAGS" in d for d in result.details)


def test_score_text_checks_passes_when_required_present_and_forbidden_absent():
    text = "The reference standard used was WHO. This looks like a data-entry error."
    result = scorer.score_text_checks(text, required_substrings=["WHO", "data-entry error"], forbidden_substrings=["CDC"])
    assert result.passed


def test_score_text_checks_fails_when_required_missing():
    result = scorer.score_text_checks("nothing relevant here", required_substrings=["WHO"], forbidden_substrings=[])
    assert not result.passed


def test_score_text_checks_fails_when_forbidden_present():
    result = scorer.score_text_checks("I'll assume the sex is male.", required_substrings=[], forbidden_substrings=["I'll assume"])
    assert not result.passed


def test_score_text_checks_required_any_group_passes_on_one_match():
    result = scorer.score_text_checks(
        "Please double-check that value.", required_substrings=[], forbidden_substrings=[],
        required_any_groups=[["double-check", "double check", "data-entry error"]],
    )
    assert result.passed


def test_score_text_checks_required_any_group_fails_when_none_match():
    result = scorer.score_text_checks(
        "Looks fine to me.", required_substrings=[], forbidden_substrings=[],
        required_any_groups=[["double-check", "double check", "data-entry error"]],
    )
    assert not result.passed


def test_score_scenario_dispatches_json_block():
    scenario = {
        "scoring": {
            "type": "json_block",
            "expected_entries": [{"indicator": "weight_for_age", "age_months_approx": 1.0, "reference": "WHO"}],
        }
    }
    text = '```json\n[{"indicator": "weight_for_age", "age_months": 1.0, "reference": "WHO", "percentile": 50.0, "flags": []}]\n```'
    assert scorer.score_scenario(scenario, text).passed


def test_score_scenario_dispatches_text_checks():
    scenario = {"scoring": {"type": "text_checks", "required_substrings": ["hello"], "forbidden_substrings": []}}
    assert scorer.score_scenario(scenario, "hello world").passed
