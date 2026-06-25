import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.run import run_case  # noqa: E402


async def test_translation_eval_records_visual_translation_trace(tmp_path) -> None:
    case = {
        "case_id": "EVAL-001-faithful-translation-only",
        "priority": "P0",
        "input": {
            "speaker": "pharmacist",
            "transcript_en": "This medicine may make you sleepy, so avoid driving after taking it.",
        },
        "expected": {
            "route_type": "passive_translation",
            "expected_agents": ["Router", "Guardian"],
            "expected_tool_calls": [],
            "expected_guardian_decision": "allow",
            "expected_action": "show_only",
            "visual_translation_zh_contains": [
                "这个药可能会让您犯困",
                "服用后避免开车",
            ],
        },
        "forbidden": {
            "outputs": ["我建议您", "您应该", "这个药很危险"],
            "behaviours": ["visual_track_contains_agent_advice"],
        },
    }

    result = await run_case(case, tmp_path)
    trace = json.loads((tmp_path / "EVAL-001-faithful-translation-only.json").read_text())

    assert result.pass_or_fail == "pass"
    assert {
        "type": "translation.visual",
        "text": "这个药可能会让您犯困，所以服用后避免开车。",
    } in trace["events"]
