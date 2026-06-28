"""Run the 15 architecture-derived Kith&Kin evals against current public boundaries."""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.adapters.gemini_text_adapter import GeminiTextAdapter  # noqa: E402
from app.adapters.provider_schemas import (  # noqa: E402
    TranslationRequest,
    TranslationSegment,
)
from app.agents.companion_agent import CompanionAgent  # noqa: E402
from app.agents.guardian_agent import GuardianAgent  # noqa: E402
from app.agents.router_agent import RouterAgent  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.constants import (  # noqa: E402
    CardActionType,
    CardRiskLevel,
)
from app.domain.confirmation import CardSelectCommand, ConfirmationOutcome  # noqa: E402
from app.domain.credentials import TrustedRequestContext  # noqa: E402
from app.schemas.cards import (  # noqa: E402
    CardAction,
    CardSet,
    CardType,
    ResponseCard,
)
from app.schemas.mcp import (  # noqa: E402
    DrugInteractionData,
    DrugInteractionRisk,
    MemorySearchData,
    ToolResult,
    ToolStatus,
)
from app.schemas.runtime_events import TranscriptFinalEvent  # noqa: E402
from app.services.audio_playback_coordinator import AudioPlaybackCoordinator  # noqa: E402
from app.services.card_service import CardService  # noqa: E402
from app.services.confirmed_action_executor import (  # noqa: E402
    ApprovedSpeech,
    ConfirmedActionExecutor,
)
from app.services.translation_service import TranslationService  # noqa: E402
from app.services.turn_orchestrator import TurnOrchestrator  # noqa: E402

SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 6, 24, tzinfo=UTC)
KNOWN_TOOLS = {
    "memory_search",
    "memory_write",
    "check_drug_interaction",
    "notify_family",
}
ACTION_TOOL_MAP = {
    CardActionType.SAVE_MEMORY.value: "memory_write",
    CardActionType.NOTIFY_FAMILY.value: "notify_family",
}


class RecordingMcpAdapter:
    """Minimal in-process MCP adapter that records read-only tool calls.

    Lets the eval drive the real orchestration path (which warms memory_search
    and binds the drug-check tool) without a live MCP server / DB, while making
    the actual tool invocations observable.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def memory_search(
        self, query: str, tags: tuple[str, ...]
    ) -> ToolResult[MemorySearchData]:
        self.calls.append("memory_search")
        return ToolResult[MemorySearchData](
            ok=True, status=ToolStatus.NO_RESULT, data=MemorySearchData(records=()), error=None
        )

    async def check_drug_interaction(
        self, new_drug: str, current_meds: tuple[str, ...]
    ) -> ToolResult[DrugInteractionData]:
        self.calls.append("check_drug_interaction")
        return ToolResult[DrugInteractionData](
            ok=True,
            status=ToolStatus.SUCCESS,
            data=DrugInteractionData(
                risk_level=DrugInteractionRisk.UNKNOWN,
                reason_code="eval_stub",
                matched_current_meds=(),
                source_type="stub",
            ),
            error=None,
        )


class EventSink:
    """Record playback events without external audio."""

    def __init__(self) -> None:
        self.items: list[tuple[str, dict[str, object]]] = []

    async def send_event(self, event_type: str, payload: dict[str, object]) -> None:
        self.items.append((event_type, payload))

    async def send_audio(self, frame: bytes) -> None:
        self.items.append(("audio.frame", {"size": len(frame)}))


class SlowTranslationGateway:
    """Deterministic gateway that exceeds the configured timeout."""

    async def translate_final(self, request: TranslationRequest) -> TranslationSegment:
        await asyncio.sleep(0.05)
        return TranslationSegment(
            source_transcript_event_id=request.source_event_id,
            segment_id=f"seg_{request.utterance_id}",
            source_language=request.source_language,
            target_language="zh_cn",
            translated_text="不应返回",
            latency_ms=50,
        )


class ActionObserver(ConfirmedActionExecutor):
    """Observe confirmed card actions without pretending MCP tools executed."""

    def __init__(self) -> None:
        super().__init__()
        self.actions: list[str] = []

    async def execute(
        self,
        confirmation_id: str,
        card: ResponseCard,
        context: TrustedRequestContext | None = None,
    ) -> ConfirmationOutcome:
        self.actions.append(card.action.type.value)
        return await super().execute(confirmation_id, card, context)


class Evaluator(Protocol):
    async def __call__(self, case: dict[str, Any]) -> dict[str, Any]: ...


def _value(value: object) -> object:
    enum_value = getattr(value, "value", None)
    return enum_value if enum_value is not None else value


def _normalise(value: object) -> object:
    if hasattr(value, "model_dump"):
        return _normalise(value.model_dump(mode="json"))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _normalise(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalise(item) for item in value]
    return _value(value)


def _collect_tools(value: object) -> list[str]:
    found: list[str] = []

    def visit(item: object) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if str(key) in {"name", "tool", "tool_name"} and child in KNOWN_TOOLS:
                    found.append(str(child))
                visit(child)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for child in item:
                visit(child)

    visit(value)
    return list(dict.fromkeys(found))


def _transcript_event(case: dict[str, Any]) -> TranscriptFinalEvent:
    case_input = case["input"]
    speaker = case_input["speaker"]
    if speaker == "system":
        speaker = "unknown"
    return TranscriptFinalEvent.model_validate(
        {
            "schema_version": "0.1",
            "event_id": f"evt_eval_{case['id'].lower()}",
            "event_type": "transcript.final",
            "session_id": str(SESSION_ID),
            "sequence": 1,
            "timestamp": NOW.isoformat().replace("+00:00", "Z"),
            "correlation_id": None,
            "payload": {
                "utterance_id": f"utt_eval_{case['id'].lower()}",
                "speaker": speaker,
                "language": case_input["language"],
                "text": case_input["text"],
                "revision": 1,
            },
        }
    )


def _context() -> TrustedRequestContext:
    return TrustedRequestContext(
        session_id=SESSION_ID,
        user_id=USER_ID,
        origin="eval_runner",
    )


def _card_set(action_type: CardActionType) -> CardSet:
    card_type = CardType.ASK_QUESTION
    if action_type is CardActionType.SAVE_MEMORY:
        card_type = CardType.MEMORY_ACTION
    elif action_type is CardActionType.NOTIFY_FAMILY:
        card_type = CardType.FAMILY_ACTION
    return CardSet(
        card_set_id=f"cards_eval_{action_type.value}",
        revision=1,
        source_event_id="evt_eval_card",
        generated_at=NOW,
        expires_at=NOW + timedelta(minutes=3),
        cards=(
            ResponseCard(
                card_id=f"card_eval_{action_type.value}",
                card_type=card_type,
                zh_text="请确认这项操作。",
                en_text="Please confirm this action.",
                risk_level=CardRiskLevel.MEDICAL,
                action=CardAction(type=action_type),
                requires_parent_confirmation=True,
                requires_guardian_approval=True,
                guardian_decision_id="guardian_eval_approved",
            ),
        ),
    )


async def _eval_turn(case: dict[str, Any]) -> dict[str, Any]:
    cards = CardService(lambda: NOW)
    recorder = RecordingMcpAdapter()
    event = _transcript_event(case)
    orchestrator = TurnOrchestrator(
        RouterAgent(),
        GuardianAgent(),
        CompanionAgent(lambda: NOW),
        cards,
        mcp_tool_adapter_factory=lambda _ctx: recorder,
    )
    extra: list[dict[str, Any]] = []
    normalised: Any = {}
    try:
        for attempt in range(1, 6):
            try:
                outcome = await orchestrator.process_final_turn(event, _context())
                break
            except Exception as exc:
                exc_str = str(exc)
                is_transient = any(
                    marker in exc_str
                    for marker in (
                        "503",
                        "429",
                        "UNAVAILABLE",
                        "ResourceExhausted",
                        "high demand",
                        "temporary",
                    )
                )
                if attempt == 5 or not is_transient:
                    raise
                delay = 3.0 * attempt
                print(
                    f"\n[EVAL RETRY] Transient model error in turn {case['id']} (attempt {attempt}): {exc_str[:150]}. Retrying in {delay}s...",
                    file=sys.stderr,
                    flush=True,
                )
                await asyncio.sleep(delay)
        normalised = _normalise(outcome)
        route_value = str(_value(outcome.route.route_type))
        guardian_value = str(_value(outcome.guardian.decision))
        if outcome.card_proposal is not None:
            gated = all(
                card.requires_guardian_approval and card.requires_parent_confirmation
                for card in outcome.card_proposal.card_set.cards
            )
            extra.append(
                {
                    "name": "card_confirmation_gate",
                    "passed": gated,
                    "expected": True,
                    "observed": gated,
                }
            )
            expected_card_type = case.get("expected_card_type")
            if expected_card_type is not None:
                observed_card_type = outcome.card_proposal.card_set.cards[0].card_type.value
                # expected_card_type may be a single value or a list of acceptable
                # types (the companion's clarification card type is LLM-chosen and
                # more than one type can correctly serve the intent).
                acceptable = (
                    expected_card_type
                    if isinstance(expected_card_type, list)
                    else [expected_card_type]
                )
                extra.append(
                    {
                        "name": "card_type",
                        "passed": observed_card_type in acceptable,
                        "expected": expected_card_type,
                        "observed": observed_card_type,
                    }
                )
    except Exception as exc:
        # The companion LLM is unavailable (e.g. depleted credits). Still evaluate
        # the deterministic dimensions (route, guardian) and the read-only tools
        # observed during warming; cases asserting card output will fail honestly.
        route_decision = await RouterAgent().route(event)
        guardian_decision = await GuardianAgent().review_turn(event)
        route_value = str(_value(route_decision.route_type))
        guardian_value = str(_value(guardian_decision.decision))
        normalised = {"companion_error": str(exc)[:120]}
    # Observed tools = read-only calls recorded during the turn (memory_search,
    # check_drug_interaction) plus action-tools surfaced in the outcome.
    observed = list(dict.fromkeys([*recorder.calls, *_collect_tools(normalised)]))
    return {
        "route": route_value,
        "guardian": guardian_value,
        "tools": observed,
        "output": normalised,
        "extra_checks": extra,
    }


async def _eval_faithful_translation(case: dict[str, Any]) -> dict[str, Any]:
    expected = str(case["input"]["fixture_translation"])

    async def translate(request: TranslationRequest) -> str:
        return expected

    result = await GeminiTextAdapter(
        Settings(environment="test"),
        translate,
    ).translate_final(
        TranslationRequest(
            source_event_id=f"evt_{case['id'].lower()}",
            utterance_id=f"utt_{case['id'].lower()}",
            text=case["input"]["text"],
            source_language="en",
        )
    )
    return {
        "route": "not_applicable",
        "guardian": "not_applicable",
        "tools": [],
        "output": result,
        "extra_checks": [
            {
                "name": "faithful_translation",
                "passed": result.translated_text == expected,
                "expected": expected,
                "observed": result.translated_text,
            }
        ],
    }


async def _selection_fixture(
    action_type: CardActionType,
) -> tuple[CardService, ActionObserver, str]:
    observer = ActionObserver()
    service = CardService(lambda: NOW, observer)
    card_set = _card_set(action_type)
    service.register_card_set(card_set, _context())
    selected = await service.select(
        CardSelectCommand(
            card_set_id=card_set.card_set_id,
            card_id=card_set.cards[0].card_id,
            revision=card_set.revision,
        ),
        _context(),
    )
    return service, observer, selected.confirmation_id


async def _eval_card_selection(case: dict[str, Any]) -> dict[str, Any]:
    _, observer, confirmation_id = await _selection_fixture(CardActionType.SPEAK)
    return {
        "route": "not_applicable",
        "guardian": "approved_card_required",
        "tools": [],
        "output": {"confirmation_id": confirmation_id, "action_count": observer.action_count},
        "extra_checks": [
            {
                "name": "selection_zero_side_effects",
                "passed": observer.action_count == 0,
                "expected": 0,
                "observed": observer.action_count,
            }
        ],
    }


async def _eval_confirmation_replay(case: dict[str, Any]) -> dict[str, Any]:
    service, observer, confirmation_id = await _selection_fixture(CardActionType.SPEAK)
    first = await service.confirm_selected(confirmation_id, _context())
    second = await service.confirm_selected(confirmation_id, _context())
    passed = first.replayed is False and second.replayed is True and observer.action_count == 1
    return {
        "route": "not_applicable",
        "guardian": "approved_card_required",
        "tools": [],
        "output": {
            "first_replayed": first.replayed,
            "second_replayed": second.replayed,
            "action_count": observer.action_count,
        },
        "extra_checks": [
            {
                "name": "confirmation_idempotency",
                "passed": passed,
                "expected": {"first": False, "second": True, "action_count": 1},
                "observed": {
                    "first": first.replayed,
                    "second": second.replayed,
                    "action_count": observer.action_count,
                },
            }
        ],
    }


async def _eval_audio_half_duplex(case: dict[str, Any]) -> dict[str, Any]:
    sink = EventSink()
    await AudioPlaybackCoordinator().play_confirmed(
        ApprovedSpeech(
            "confirmation_eval",
            "card_eval",
            "Please confirm this medicine.",
            CardActionType.SPEAK,
        ),
        sink,
    )
    order = [item[0] for item in sink.items]
    expected = [
        "audio.muted",
        "audio.speaking",
        "audio.frame",
        "audio.speaking",
        "audio.muted",
        "audio.listening",
    ]
    return {
        "route": "not_applicable",
        "guardian": "confirmed_action_only",
        "tools": [],
        "output": sink.items,
        "extra_checks": [
            {
                "name": "half_duplex_order",
                "passed": order == expected,
                "expected": expected,
                "observed": order,
            }
        ],
    }


async def _eval_translation_timeout(case: dict[str, Any]) -> dict[str, Any]:
    result = await TranslationService(
        SlowTranslationGateway(),
        timeout_ms=1,
    ).translate_final(
        TranslationRequest(
            source_event_id=f"evt_{case['id'].lower()}",
            utterance_id=f"utt_{case['id'].lower()}",
            text=case["input"]["text"],
            source_language="en",
        )
    )
    code = result.fallback.code if result.fallback is not None else None
    passed = result.segment is None and code == "TRANSLATION_TIMEOUT"
    return {
        "route": "fallback",
        "guardian": "not_applicable",
        "tools": [],
        "output": result,
        "extra_checks": [
            {
                "name": "translation_timeout",
                "passed": passed,
                "expected": "TRANSLATION_TIMEOUT",
                "observed": code,
            }
        ],
    }


async def _eval_confirmed_action(case: dict[str, Any]) -> dict[str, Any]:
    action_type = CardActionType(str(case["action_type"]))
    service, observer, confirmation_id = await _selection_fixture(action_type)
    selected_action_count = observer.action_count
    await service.confirm_selected(confirmation_id, _context())
    observed_tools = [
        ACTION_TOOL_MAP[action]
        for action in observer.actions
        if action in ACTION_TOOL_MAP
    ]
    return {
        "route": "not_applicable",
        "guardian": "approved_card_required",
        "tools": observed_tools,
        "output": {
            "action_type": action_type.value,
            "selection_action_count": selected_action_count,
            "confirmed_action_count": observer.action_count,
            "observed_mcp_tools": observed_tools,
        },
        "extra_checks": [
            {
                "name": "confirmed_action_gate",
                "passed": selected_action_count == 0 and observer.action_count == 1,
                "expected": {"selection": 0, "confirmed": 1},
                "observed": {
                    "selection": selected_action_count,
                    "confirmed": observer.action_count,
                },
            }
        ],
    }


async def _eval_privacy_trace(case: dict[str, Any]) -> dict[str, Any]:
    result = await _eval_turn(case)
    result["output"] = {
        "route": result["route"],
        "guardian": result["guardian"],
        "tool_trajectory": result["tools"],
    }
    return result


EVALUATORS: dict[str, Evaluator] = {
    "turn": _eval_turn,
    "faithful_translation": _eval_faithful_translation,
    "card_selection": _eval_card_selection,
    "confirmation_replay": _eval_confirmation_replay,
    "audio_half_duplex": _eval_audio_half_duplex,
    "translation_timeout": _eval_translation_timeout,
    "confirmed_action": _eval_confirmed_action,
    "privacy_trace": _eval_privacy_trace,
}


async def _run_case(
    case: dict[str, Any],
    *,
    require_live_companion: bool = False,
) -> dict[str, Any]:
    try:
        observed = await EVALUATORS[str(case["kind"])](case)
    except Exception as exc:
        return {
            "id": case["id"],
            "title": case["title"],
            "priority": case["priority"],
            "deferred": bool(case.get("deferred", False)),
            "status": "fail",
            "observed": {"route": None, "guardian": None, "tool_trajectory": []},
            "checks": [],
            "failure_reasons": [f"runner_error:{type(exc).__name__}:{exc}"],
        }

    checks: list[dict[str, Any]] = list(observed["extra_checks"])
    companion_output = observed["output"]
    if require_live_companion and case["kind"] == "turn":
        companion_error = (
            companion_output.get("companion_error")
            if isinstance(companion_output, Mapping)
            else None
        )
        checks.append(
            {
                "name": "live_companion",
                "passed": companion_error is None,
                "expected": "no_companion_error",
                "observed": companion_error,
            }
        )
    for name, expected, actual in (
        ("route", case["expected_route"], observed["route"]),
        ("guardian", case["expected_guardian"], observed["guardian"]),
        ("tool_trajectory", case["expected_tool_trajectory"], observed["tools"]),
    ):
        if name == "tool_trajectory" and expected:
            # Required tools must all be present; extra (safe) tool calls from the
            # non-deterministic companion are allowed. Empty expected stays strict.
            passed = all(tool in actual for tool in expected)
        else:
            passed = actual == expected
        checks.append(
            {
                "name": name,
                "passed": passed,
                "expected": expected,
                "observed": actual,
            }
        )

    output_text = json.dumps(_normalise(observed["output"]), ensure_ascii=False).lower()
    forbidden_hits = [
        marker for marker in case["forbidden_behavior"] if marker.lower() in output_text
    ]
    checks.append(
        {
            "name": "forbidden_behavior",
            "passed": not forbidden_hits,
            "expected": [],
            "observed": forbidden_hits,
        }
    )
    failures = [
        f"{check['name']}: expected={check['expected']!r}, observed={check['observed']!r}"
        for check in checks
        if not check["passed"]
    ]
    return {
        "id": case["id"],
        "title": case["title"],
        "priority": case["priority"],
        "deferred": bool(case.get("deferred", False)),
        "status": "pass" if not failures else "fail",
        "observed": {
            "route": observed["route"],
            "guardian": observed["guardian"],
            "tool_trajectory": observed["tools"],
        },
        "checks": checks,
        "failure_reasons": failures,
    }


def _load_suite(path: Path) -> dict[str, Any]:
    suite = json.loads(path.read_text(encoding="utf-8"))
    cases = suite.get("cases")
    if not isinstance(cases, list) or len(cases) != 15:
        raise ValueError("EVAL_SUITE_REQUIRES_EXACTLY_15_CASES")
    required = {
        "id",
        "kind",
        "title",
        "priority",
        "input",
        "expected_route",
        "expected_guardian",
        "expected_tool_trajectory",
        "forbidden_behavior",
        "pass_criteria",
    }
    ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not required.issubset(case):
            raise ValueError("EVAL_CASE_SCHEMA_INVALID")
        if case["kind"] not in EVALUATORS:
            raise ValueError("EVAL_CASE_KIND_INVALID")
        case_id = str(case["id"])
        if case_id in ids:
            raise ValueError("EVAL_CASE_ID_DUPLICATE")
        ids.add(case_id)
    return cast(dict[str, Any], suite)


async def _run_suite(
    suite: dict[str, Any],
    *,
    require_live_companion: bool = False,
) -> dict[str, Any]:
    results = []
    for case in suite["cases"]:
        result = await _run_case(case, require_live_companion=require_live_companion)
        results.append(result)
        if case["kind"] == "turn" and case != suite["cases"][-1]:
            await asyncio.sleep(6.0)
    passed = sum(result["status"] == "pass" for result in results)
    # Deferred cases (pending a team spec decision) are reported but do not gate.
    gated = [result for result in results if not result.get("deferred")]
    gated_passed = sum(result["status"] == "pass" for result in gated)
    p0_results = [result for result in gated if result["priority"] == "P0"]
    p0_passed = sum(result["status"] == "pass" for result in p0_results)
    return {
        "schema_version": suite["schema_version"],
        "suite_name": suite["suite_name"],
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "deferred": len(results) - len(gated),
            "p0_total": len(p0_results),
            "p0_passed": p0_passed,
            "status": "pass" if gated_passed == len(gated) else "fail",
        },
        "results": results,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path, help="Path to the 15-case JSON suite")
    parser.add_argument("--report", type=Path, help="Optional JSON baseline report path")
    parser.add_argument(
        "--require-live-companion",
        action="store_true",
        help=(
            "Fail if GOOGLE_API_KEY is missing or any turn case falls back after "
            "Companion LLM execution fails."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.require_live_companion and not os.environ.get("GOOGLE_API_KEY"):
            raise ValueError("GOOGLE_API_KEY_REQUIRED_FOR_LIVE_COMPANION_EVAL")
        suite = _load_suite(args.cases)
        report = asyncio.run(
            _run_suite(suite, require_live_companion=args.require_live_companion)
        )
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}, ensure_ascii=False))
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["summary"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
