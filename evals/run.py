"""Run deterministic architecture evals against the local agent boundaries."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.agents.companion_agent import CompanionAgent  # noqa: E402
from app.agents.guardian_agent import GuardianAgent  # noqa: E402
from app.agents.router_agent import RouterAgent  # noqa: E402
from app.core.constants import GuardianDecisionType  # noqa: E402
from app.domain.credentials import TrustedRequestContext  # noqa: E402
from app.schemas.runtime_events import TranscriptFinalEvent  # noqa: E402
from app.services.card_service import CardService  # noqa: E402
from app.services.turn_orchestrator import TurnOrchestrator  # noqa: E402

NOW = datetime(2026, 6, 22, tzinfo=UTC)
SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    pass_or_fail: str
    route_match: bool
    expected_tools_match: bool
    guardian_match: bool
    forbidden_output_found: bool
    trace_file_path: str


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", type=Path)
    parser.add_argument("--case", dest="case_filter", default="")
    parser.add_argument("--trace-dir", type=Path, default=ROOT / "evals" / "traces")
    args = parser.parse_args()

    selected = {item.strip() for item in args.case_filter.split(",") if item.strip()}
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if selected:
        cases = [case for case in cases if case["case_id"] in selected]

    results = asyncio.run(run_cases(cases, args.trace_dir))
    print(
        "case_id pass_or_fail route_match expected_tools_match "
        "guardian_match forbidden_output_found trace_file_path"
    )
    for result in results:
        print(
            result.case_id,
            result.pass_or_fail,
            str(result.route_match).lower(),
            str(result.expected_tools_match).lower(),
            str(result.guardian_match).lower(),
            str(result.forbidden_output_found).lower(),
            result.trace_file_path,
        )

    if any(result.pass_or_fail == "fail" for result in results):
        raise SystemExit(1)


async def run_cases(cases: list[dict[str, object]], trace_dir: Path) -> list[EvalResult]:
    trace_dir.mkdir(parents=True, exist_ok=True)
    return [await run_case(case, trace_dir) for case in cases]


async def run_case(case: dict[str, object], trace_dir: Path) -> EvalResult:
    event = _event_for(case)
    context = TrustedRequestContext(session_id=SESSION_ID, user_id=USER_ID, origin="eval")
    outcome = await TurnOrchestrator(
        RouterAgent(),
        GuardianAgent(),
        CompanionAgent(lambda: NOW),
        CardService(lambda: NOW),
    ).process_final_turn(event, context)

    expected = _dict_value(case, "expected")
    agents = ["Router", "Guardian"]
    if outcome.route.route_type.value == "fallback":
        agents = ["Guardian"]
    if outcome.card_proposal is not None:
        agents.append("Companion")
    tool_calls = _planned_tool_calls(event.payload.text, agents)
    output_text = _output_text(outcome)
    guardian_decision = _guardian_eval_label(outcome.guardian.decision)

    forbidden = _dict_value(case, "forbidden")
    forbidden_outputs = _list_value(forbidden, "outputs")
    forbidden_output_found = any(item.lower() in output_text.lower() for item in forbidden_outputs)
    forbidden_tools = set(_list_value(expected, "forbidden_tool_calls"))

    route_match = outcome.route.route_type.value == expected.get("route_type")
    agent_match = agents == _list_value(expected, "expected_agents")
    expected_tools_match = (
        sorted(tool_calls) == sorted(_list_value(expected, "expected_tool_calls"))
        and not set(tool_calls).intersection(forbidden_tools)
    )
    guardian_match = guardian_decision == expected.get("expected_guardian_decision")
    passed = route_match and agent_match and expected_tools_match and guardian_match
    passed = passed and not forbidden_output_found

    trace_path = trace_dir / f"{case['case_id']}.json"
    events = [
        {"type": "transcript.final", "text": event.payload.text},
        {"type": "route.decision", "route_type": outcome.route.route_type.value},
        {"type": "agent.path", "agents": agents},
        {"type": "tool.calls", "tool_calls": tool_calls},
        *[
            {
                "type": "tool.call",
                "tool_name": tool,
                "access": "write" if tool in {"memory_write", "notify_family"} else "read",
            }
            for tool in tool_calls
        ],
        {
            "type": "guardian.decision",
            "decision": guardian_decision,
            "reason_code": outcome.guardian.reason_code.value,
        },
        {"type": "output.preview", "text": output_text},
    ]

    trace_path.write_text(
        json.dumps(
            {
                "case_id": case["case_id"],
                "events": events,
                "checks": {
                    "route_match": route_match,
                    "agent_match": agent_match,
                    "expected_tools_match": expected_tools_match,
                    "guardian_match": guardian_match,
                    "forbidden_output_found": forbidden_output_found,
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return EvalResult(
        case_id=str(case["case_id"]),
        pass_or_fail="pass" if passed else "fail",
        route_match=route_match,
        expected_tools_match=expected_tools_match,
        guardian_match=guardian_match,
        forbidden_output_found=forbidden_output_found,
        trace_file_path=str(trace_path),
    )


def _event_for(case: dict[str, object]) -> TranscriptFinalEvent:
    payload = _dict_value(case, "input")
    return TranscriptFinalEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": f"evt-{case['case_id']}",
            "event_type": "transcript.final",
            "session_id": str(SESSION_ID),
            "sequence": 1,
            "timestamp": NOW.isoformat(),
            "correlation_id": None,
            "payload": {
                "utterance_id": f"utt-{case['case_id']}",
                "speaker": payload.get("speaker", "pharmacist"),
                "language": "en",
                "text": payload["transcript_en"],
                "revision": 1,
            },
        }
    )


def _planned_tool_calls(text: str, agents: list[str]) -> list[str]:
    if "Companion" not in agents:
        return []
    lowered = text.lower()
    if "save the summary" in lowered or "save this" in lowered:
        return ["memory_write"]
    if (
        "send this to my daughter" in lowered
        or "send this to my son" in lowered
        or "send this to my family" in lowered
        or "notify family" in lowered
    ):
        return ["notify_family"]
    calls = ["memory_search"]
    if "ibuprofen" in lowered or "lisinopril" in lowered:
        calls.append("check_drug_interaction")
    return calls


def _guardian_eval_label(decision: GuardianDecisionType) -> str:
    if decision is GuardianDecisionType.BLOCK:
        return "block"
    if decision is GuardianDecisionType.REQUIRE_PARENT_CONFIRMATION:
        return "require_parent_confirmation"
    return "allow"


def _output_text(outcome: object) -> str:
    card_proposal = getattr(outcome, "card_proposal")
    if card_proposal is None:
        return ""
    return " ".join(f"{card.zh_text} {card.en_text}" for card in card_proposal.card_set.cards)


def _dict_value(value: dict[str, object], key: str) -> dict[str, object]:
    nested = value[key]
    if not isinstance(nested, dict):
        raise TypeError(f"{key} must be an object")
    return nested


def _list_value(value: dict[str, object], key: str) -> list[str]:
    nested = value.get(key, [])
    if not isinstance(nested, list) or not all(isinstance(item, str) for item in nested):
        raise TypeError(f"{key} must be a string list")
    return nested


if __name__ == "__main__":
    main()
