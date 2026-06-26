"""Contract tests for the executable Kith&Kin eval suite."""

import importlib.util
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("kithkin_eval_runner", EVAL_ROOT / "run.py")
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_suite_contains_exactly_fifteen_unique_cases() -> None:
    suite = RUNNER._load_suite(EVAL_ROOT / "cases.json")

    assert len(suite["cases"]) == 15
    assert len({case["id"] for case in suite["cases"]}) == 15


def test_every_case_maps_all_required_eval_dimensions() -> None:
    suite = RUNNER._load_suite(EVAL_ROOT / "cases.json")

    for case in suite["cases"]:
        assert case["expected_route"]
        assert case["expected_guardian"]
        assert isinstance(case["expected_tool_trajectory"], list)
        assert case["forbidden_behavior"]
        assert case["pass_criteria"]
