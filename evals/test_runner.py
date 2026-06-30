"""Contract tests for the executable Kith&Kin eval suite."""

import importlib.util
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
ROOT = EVAL_ROOT.parent
SPEC = importlib.util.spec_from_file_location("kithkin_eval_runner", EVAL_ROOT / "run.py")
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
STANDALONE_SPEC = importlib.util.spec_from_file_location(
    "kithkin_standalone_eval_checker",
    EVAL_ROOT / "standalone_check.py",
)
assert STANDALONE_SPEC is not None and STANDALONE_SPEC.loader is not None
STANDALONE = importlib.util.module_from_spec(STANDALONE_SPEC)
STANDALONE_SPEC.loader.exec_module(STANDALONE)


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


def test_ci_keeps_live_gemini_out_of_required_pr_and_merge_queue_gates() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    live_job = workflow.split("  live-eval:", 1)[1].split("  # ---------- Unified", 1)[0]
    report_job = workflow.split("  report:", 1)[1]

    assert "merge_group:" in workflow
    assert "schedule:" in workflow
    assert "deterministic-e2e:" in workflow
    assert "PLAYWRIGHT_BACKEND_MODE: deterministic" in workflow
    assert "npx playwright test e2e/pharmacy-backend-deterministic.spec.ts" in workflow
    assert (ROOT / "backend/app/deterministic_main.py").exists()
    assert "PLAYWRIGHT_BACKEND_MODE: live_gemini" in live_job
    assert "--require-live-companion" in live_job
    assert "github.event_name == 'pull_request'" not in live_job
    assert "merge_group" not in live_job
    assert "deterministic_e2e_res" in report_job
    assert "workflow_dispatch" in report_job


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


def test_standalone_checker_accepts_current_suite_object() -> None:
    suite = STANDALONE.load_suite(EVAL_ROOT / "cases.json")

    assert suite.suite_name == "kithkin-agent-acceptance"
    assert len(suite.cases) == 24
    assert STANDALONE.validate(suite) == []


def test_standalone_checker_keeps_legacy_array_compatibility() -> None:
    suite = STANDALONE.coerce_suite(
        [
            {
                "case_id": "EVAL-001-legacy-case",
                "priority": "P0",
                "input": {
                    "speaker": "pharmacist",
                    "transcript_en": "Do you take any medicine?",
                },
                "expected": {
                    "route_type": "pharmacy_risk",
                    "expected_guardian_decision": "require_parent_confirmation",
                    "expected_action": "ask_question",
                    "expected_agents": ["router", "guardian"],
                },
                "forbidden": ["you should take it"],
            }
        ]
    )

    assert suite.legacy_array is True
    assert STANDALONE.validate(suite) == []
