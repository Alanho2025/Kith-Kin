"""Contract tests for the executable Kith&Kin eval suite."""

import importlib.util
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
ROOT = EVAL_ROOT.parent
SPEC = importlib.util.spec_from_file_location("kithkin_eval_runner", EVAL_ROOT / "run.py")
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_suite_contains_round1_gap_lockdown_cases() -> None:
    suite = RUNNER._load_suite(EVAL_ROOT / "cases.json")

    assert len(suite["cases"]) == 24
    assert sum(1 for case in suite["cases"] if case["priority"] == "P0") == 23
    assert "24" in suite["description"]
    assert "Seventeen" not in suite["description"]
    assert len({case["id"] for case in suite["cases"]}) == len(suite["cases"])
    ids = {case["id"] for case in suite["cases"]}
    assert {"E18", "E19", "E20", "E21", "E22", "E23", "E24"}.issubset(ids)


def test_ci_labels_match_current_eval_suite_size() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "17 cases" not in workflow
    assert "24 cases" in workflow


def test_every_case_maps_all_required_eval_dimensions() -> None:
    suite = RUNNER._load_suite(EVAL_ROOT / "cases.json")

    for case in suite["cases"]:
        assert case["expected_route"]
        assert case["expected_guardian"]
        assert isinstance(case["expected_tool_trajectory"], list)
        assert case["forbidden_behavior"]
        assert case["pass_criteria"]


def test_round1_gap_cases_assert_payload_or_trace_facts() -> None:
    suite = RUNNER._load_suite(EVAL_ROOT / "cases.json")
    cases = {case["id"]: case for case in suite["cases"]}

    assert cases["E16"]["required_product_options"]
    assert cases["E18"]["forbidden_user_facing_text"]
    assert cases["E19"]["required_card_grounding"]
    assert cases["E20"]["forbidden_payload_text"]
    assert cases["E21"]["required_product_options"]
    assert cases["E22"]["required_summary_fields"]
    assert cases["E23"]["required_audio_delivery_contract"] is True
    assert cases["E24"]["required_speaker_attribution"]
