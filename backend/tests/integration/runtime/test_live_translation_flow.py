import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from app.adapters.fake_live_adapter import FakeLiveAdapter
from app.adapters.gemini_live_adapter import GeminiSdkLiveSession
from app.adapters.provider_schemas import (
    GeminiLiveGateway,
    LiveSessionContext,
    LiveSessionPort,
    ProviderAudioEvent,
    ProviderLiveEvent,
    ProviderLiveEventType,
    ProviderTranscriptEvent,
    TranslationRequest,
    TranslationSegment,
)
from app.agents.companion_agent import CompanionAgent
from app.agents.guardian_agent import GuardianAgent
from app.agents.router_agent import RouterAgent
from app.services.card_service import CardService
from app.services.live_runtime_service import LiveRuntimeService
from app.services.task_supervisor import TaskSupervisor
from app.services.translation_service import TranslationService
from app.services.turn_orchestrator import TurnOrchestrator

NOW = datetime(2026, 6, 22, tzinfo=UTC)
SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")


class CapturingTranslationGateway:
    def __init__(self, *, delay_seconds: float = 0) -> None:
        self.requests: list[TranslationRequest] = []
        self.delay_seconds = delay_seconds

    async def translate_final(self, request: TranslationRequest) -> TranslationSegment:
        self.requests.append(request)
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return TranslationSegment(
            source_transcript_event_id=request.source_event_id,
            segment_id=f"seg_{request.utterance_id}",
            source_language=request.source_language,
            target_language="zh_cn",
            translated_text="\u4f60\u5bf9\u6297\u751f\u7d20\u8fc7\u654f\u5417\uff1f",
            latency_ms=10,
        )


def runtime(
    gateway: CapturingTranslationGateway,
    *,
    timeout_ms: int = 1000,
    with_turn_orchestrator: bool = False,
) -> LiveRuntimeService:
    cards = CardService(lambda: NOW)
    turn_orchestrator = (
        TurnOrchestrator(
            RouterAgent(),
            GuardianAgent(),
            CompanionAgent(lambda: NOW),
            cards,
        )
        if with_turn_orchestrator
        else None
    )
    return LiveRuntimeService(
        cards,
        FakeLiveAdapter(),
        lambda: NOW,
        TranslationService(gateway, timeout_ms=timeout_ms),
        turn_orchestrator=turn_orchestrator,
        user_id=USER_ID if turn_orchestrator is not None else None,
    )


def provider_transcript(
    *,
    final: bool,
    utterance_id: str = "utt_1",
    language: Literal["en", "zh", "unknown"] = "en",
) -> ProviderTranscriptEvent:
    return ProviderTranscriptEvent(
        event_type=(
            ProviderLiveEventType.TRANSCRIPT_FINAL
            if final
            else ProviderLiveEventType.TRANSCRIPT_PARTIAL
        ),
        provider_event_id="provider_evt_1",
        utterance_id=utterance_id,
        speaker="pharmacist",
        language=language,
        text="Do you have any allergies to antibiotics?",
        revision=2 if final else 1,
    )


async def test_partial_never_calls_translation() -> None:
    gateway = CapturingTranslationGateway()

    events = await runtime(gateway).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=False),
    )

    assert gateway.requests == []
    assert events[-1]["event_type"] == "transcript.partial"


async def test_final_appends_one_faithful_segment() -> None:
    gateway = CapturingTranslationGateway()

    events = await runtime(gateway).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=True),
    )

    assert [event["event_type"] for event in events] == [
        "transcript.final",
        "translation.pending",
        "translation.final",
    ]
    assert events[-1]["payload"]["append_only"] is True
    assert events[-1]["payload"]["mode"] == "faithful"


async def test_successful_translation_runs_router_guardian_trace() -> None:
    gateway = CapturingTranslationGateway()

    events = await runtime(gateway, with_turn_orchestrator=True).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=True),
    )

    event_types = [event["event_type"] for event in events]
    assert event_types[:3] == [
        "transcript.final",
        "translation.pending",
        "translation.final",
    ]
    assert event_types.index("route.decision") > event_types.index("translation.final")
    assert event_types[-1] == "cards.render"
    route = next(event for event in events if event["event_type"] == "route.decision")
    assert route["payload"]["route_type"] == "pharmacy_risk"
    assert route["payload"]["reason_code"] == "pharmacy_term"


async def test_partial_with_orchestrator_never_runs_router_guardian() -> None:
    gateway = CapturingTranslationGateway()

    events = await runtime(gateway, with_turn_orchestrator=True).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=False),
    )

    assert gateway.requests == []
    assert [event["event_type"] for event in events] == ["transcript.partial"]


async def test_chinese_final_skips_english_translation_sidecar() -> None:
    gateway = CapturingTranslationGateway()

    events = await runtime(gateway).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=True, language="zh"),
    )

    assert gateway.requests == []
    assert [event["event_type"] for event in events] == ["transcript.final"]


async def test_duplicate_final_is_idempotent() -> None:
    gateway = CapturingTranslationGateway()
    service = runtime(gateway)

    first = await service.handle_provider_event(SESSION_ID, provider_transcript(final=True))
    second = await service.handle_provider_event(SESSION_ID, provider_transcript(final=True))

    assert sum(1 for event in first if event["event_type"] == "translation.final") == 1
    assert all(event["event_type"] != "translation.final" for event in second)
    assert len(gateway.requests) == 1


async def test_translation_timeout_keeps_english() -> None:
    gateway = CapturingTranslationGateway(delay_seconds=0.05)

    events = await runtime(gateway, timeout_ms=1).handle_provider_event(
        SESSION_ID,
        provider_transcript(final=True),
    )

    assert events[0]["event_type"] == "transcript.final"
    assert events[-1]["event_type"] == "fallback.show"
    assert events[-1]["payload"]["code"] == "TRANSLATION_TIMEOUT"


async def test_disconnect_cancels_all_owned_tasks() -> None:
    supervisor = TaskSupervisor()
    supervisor.create(asyncio.sleep(60))

    await supervisor.cancel_all()

    assert supervisor.pending_count == 0


class CoordinatedLiveSession(LiveSessionPort):
    def __init__(self) -> None:
        self.audio_frames: list[bytes] = []
        self.closed = False
        self.audio_received = asyncio.Event()
        self.audio_delivered = asyncio.Event()

    async def send_audio(self, frame: bytes) -> None:
        self.audio_frames.append(frame)
        self.audio_received.set()

    async def close(self) -> None:
        self.closed = True

    async def _events(self) -> AsyncIterator[ProviderLiveEvent]:
        await self.audio_received.wait()
        yield ProviderAudioEvent(
            event_type=ProviderLiveEventType.AUDIO,
            provider_event_id="provider_audio_1",
            audio=b"\x10\x20",
        )
        await asyncio.Event().wait()

    def events(self) -> AsyncIterator[ProviderLiveEvent]:
        return self._events()


class CapturingLiveGateway(GeminiLiveGateway):
    def __init__(self, session: CoordinatedLiveSession) -> None:
        self.session = session
        self.contexts: list[LiveSessionContext] = []

    async def open_session(self, context: LiveSessionContext) -> LiveSessionPort:
        self.contexts.append(context)
        return self.session


class CoordinatedWebSocket:
    def __init__(self, live_session: CoordinatedLiveSession) -> None:
        self.live_session = live_session
        self.receives = 0
        self.sent_json: list[dict[str, object]] = []
        self.sent_bytes: list[bytes] = []

    async def send_json(self, event: dict[str, object]) -> None:
        self.sent_json.append(event)

    async def send_bytes(self, frame: bytes) -> None:
        self.sent_bytes.append(frame)
        self.live_session.audio_delivered.set()

    async def receive(self) -> dict[str, object]:
        self.receives += 1
        if self.receives == 1:
            return {"type": "websocket.receive", "bytes": b"\x01\x02"}
        await self.live_session.audio_delivered.wait()
        return {"type": "websocket.disconnect"}

    async def close(self, *, code: int, reason: str) -> None:
        return None


async def test_real_runtime_opens_one_session_and_bridges_audio() -> None:
    live_session = CoordinatedLiveSession()
    gateway = CapturingLiveGateway(live_session)
    websocket = CoordinatedWebSocket(live_session)
    cards = CardService(lambda: NOW)
    service = LiveRuntimeService(
        cards,
        FakeLiveAdapter(),
        lambda: NOW,
        live_gateway=gateway,
        user_id=USER_ID,
    )

    await service.serve(websocket, SESSION_ID, last_seen_sequence=None)  # type: ignore[arg-type]

    assert len(gateway.contexts) == 1
    assert gateway.contexts[0].session_id == SESSION_ID
    assert gateway.contexts[0].user_id == USER_ID
    assert live_session.audio_frames == [b"\x01\x02"]
    assert websocket.sent_bytes == [b"\x10\x20"]
    assert live_session.closed is True


class ProviderMessageSession:
    def __init__(self, messages: tuple[object, ...]) -> None:
        self.messages = messages

    async def send_realtime_input(self, **kwargs: object) -> None:
        return None

    async def receive(self) -> AsyncIterator[object]:
        for message in self.messages:
            yield message


class NoopConnection:
    async def __aenter__(self) -> ProviderMessageSession:
        raise AssertionError("already entered")

    async def __aexit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None


class NoopAsyncClient:
    async def aclose(self) -> None:
        return None


class NoopClient:
    def __init__(self) -> None:
        self.aio = NoopAsyncClient()


async def test_provider_partials_then_turn_complete_trigger_translation_route_and_cards() -> None:
    from google.genai import types

    messages = (
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(
                    text="Do you have any allergy",
                    finished=False,
                )
            )
        ),
        types.LiveServerMessage(
            server_content=types.LiveServerContent(
                input_transcription=types.Transcription(
                    text="Do you have any allergy to antibiotics?",
                    finished=False,
                )
            )
        ),
        types.LiveServerMessage(
            server_content=types.LiveServerContent(turn_complete=True)
        ),
    )
    provider_session = GeminiSdkLiveSession(
        ProviderMessageSession(messages),  # type: ignore[arg-type]
        NoopConnection(),  # type: ignore[arg-type]
        NoopClient(),  # type: ignore[arg-type]
    )
    gateway = CapturingTranslationGateway()
    service = runtime(gateway, with_turn_orchestrator=True)
    emitted: list[dict[str, object]] = []

    async for provider_event in provider_session.events():
        emitted.extend(await service.handle_provider_event(SESSION_ID, provider_event))
        if any(event["event_type"] == "cards.render" for event in emitted):
            break
    await provider_session.close()

    event_types = [event["event_type"] for event in emitted]
    assert "transcript.final" in event_types
    assert "translation.final" in event_types
    assert "route.decision" in event_types
    assert "cards.render" in event_types
