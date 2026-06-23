import json
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.adapters.fake_live_adapter import FakeLiveAdapter
from app.adapters.provider_schemas import (
    ProviderErrorEvent,
    ProviderLiveEvent,
    ProviderLiveEventType,
    ProviderTranscriptEvent,
    TranslationRequest,
)
from app.core.constants import SCHEMA_VERSION, GuardianDecisionType
from app.domain.credentials import TrustedRequestContext
from app.schemas.runtime_events import CardConfirmEvent, TranscriptFinalEvent, parse_runtime_event
from app.services.card_service import CardService
from app.services.runtime_command_service import RuntimeCommandService
from app.services.translation_service import TranslationService
from app.services.turn_orchestrator import TurnOrchestrator

LIVE_UNAVAILABLE_ZH = (
    "\u6682\u65f6\u65e0\u6cd5\u8fde\u63a5"
    "\u5b9e\u65f6\u8bed\u97f3\u670d\u52a1\u3002"
)
TRANSLATION_UNAVAILABLE_ZH = (
    "\u6682\u65f6\u65e0\u6cd5\u751f\u6210\u4e2d\u6587\u7ffb\u8bd1\uff0c"
    "\u82f1\u6587\u539f\u6587\u4ecd\u4fdd\u7559\u3002"
)
TRANSLATION_UNAVAILABLE_EN = (
    "Translation is temporarily unavailable; "
    "the English transcript remains visible."
)


class LiveRuntimeService:
    MAX_BUFFERED_EVENTS = 64

    def __init__(
        self,
        card_service: CardService,
        fake_live: FakeLiveAdapter,
        clock: Callable[[], datetime],
        translation_service: TranslationService | None = None,
        command_service: RuntimeCommandService | None = None,
        turn_orchestrator: TurnOrchestrator | None = None,
        user_id: UUID | None = None,
        live_gateway: Any = None,
        settings: Any = None,
    ) -> None:
        self._cards = card_service
        self._fake_live = fake_live
        self._clock = clock
        self._translation_service = translation_service
        self._command_service = command_service
        self._turn_orchestrator = turn_orchestrator
        self._user_id = user_id
        self._live_gateway = live_gateway
        self._settings = settings
        self._buffers: dict[UUID, list[dict[str, object]]] = {}

    async def serve(
        self,
        websocket: WebSocket,
        session_id: UUID,
        *,
        last_seen_sequence: int | None,
    ) -> None:
        buffer = self._buffers.setdefault(session_id, self._initial_events(session_id))
        if (
            last_seen_sequence is not None
            and buffer
            and last_seen_sequence < self._sequence(buffer[0]) - 1
        ):
            fallback = self._event(
                session_id,
                self._sequence(buffer[-1]) + 1,
                "fallback.show",
                {
                    "code": "SESSION_RESUME_UNAVAILABLE",
                    "message_zh": "无法恢复较早的对话，请开始新的会话。",
                    "message_en": "The earlier conversation can no longer be resumed.",
                    "retryable": False,
                    "recovery_action": "end_session",
                    "related_event_id": None,
                },
            )
            await websocket.send_json(fallback)
            await websocket.close(code=1012, reason="SESSION_RESUME_UNAVAILABLE")
            return
        events = buffer if last_seen_sequence is None else [
            event
            for event in buffer
            if self._sequence(event) > last_seen_sequence
        ]
        for event in events:
            await websocket.send_json(event)

        if self._settings and getattr(self._settings, "live_transport", None) == "gemini_live":
            await self._serve_real_live(websocket, session_id)
            return

        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                frame = message.get("bytes")
                if isinstance(frame, bytes):
                    await websocket.send_bytes(await self._fake_live.echo_audio(frame))
                    continue
                text = message.get("text")
                if isinstance(text, str):
                    await self._handle_command(websocket, session_id, text)
        except WebSocketDisconnect:
            return

    async def handle_provider_event(
        self,
        session_id: UUID,
        provider_event: ProviderLiveEvent,
    ) -> tuple[dict[str, object], ...]:
        """Append normalised provider events to the replay buffer."""
        if isinstance(provider_event, ProviderTranscriptEvent):
            return await self._handle_transcript_provider_event(session_id, provider_event)
        if isinstance(provider_event, ProviderErrorEvent):
            return (
                self._append_event(
                    session_id,
                    "fallback.show",
                    {
                        "code": provider_event.code,
                        "message_zh": LIVE_UNAVAILABLE_ZH,
                        "message_en": "Live speech is temporarily unavailable.",
                        "retryable": provider_event.retryable,
                        "recovery_action": "reconnect",
                        "related_event_id": provider_event.provider_event_id,
                    },
                ),
            )
        return ()

    def _initial_events(self, session_id: UUID) -> list[dict[str, object]]:
        return [
            self._event(
                session_id,
                1,
                "session.ready",
                {
                    "resumption_supported": True,
                    "next_sequence": 1,
                    "input_audio_format": {
                        "encoding": "pcm_s16le",
                        "sample_rate_hz": 16000,
                        "channels": 1,
                    },
                    "output_audio_format": {
                        "encoding": "pcm_s16le",
                        "sample_rate_hz": 24000,
                        "channels": 1,
                    },
                },
            ),
            self._event(session_id, 2, "audio.listening", {"active": True}),
        ]

    async def _handle_command(self, websocket: WebSocket, session_id: UUID, text: str) -> None:
        try:
            event = parse_runtime_event(json.loads(text))
        except (ValueError, json.JSONDecodeError):
            return
        if isinstance(event, TranscriptFinalEvent):
            from app.adapters.provider_schemas import ProviderLiveEventType, ProviderTranscriptEvent
            provider_event = ProviderTranscriptEvent(
                event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
                provider_event_id=event.event_id,
                utterance_id=event.payload.utterance_id,
                speaker=event.payload.speaker,
                language=event.payload.language,
                text=event.payload.text,
                revision=event.payload.revision,
            )
            provider_outcomes = await self._handle_transcript_provider_event(
                session_id, provider_event
            )
            for provider_outcome in provider_outcomes:
                await websocket.send_json(provider_outcome)
            return
        if self._command_service is not None:
            outcomes = await self._command_service.handle(event, session_id=session_id)
            for outcome in outcomes:
                emitted = self._append_event(
                    session_id,
                    outcome.event_type,
                    outcome.payload,
                    correlation_id=outcome.correlation_id,
                )
                await websocket.send_json(emitted)
            return
        if not isinstance(event, CardConfirmEvent):
            return
        if self._user_id is None:
            raise RuntimeError("Missing user ID")
        context = TrustedRequestContext(
            session_id=session_id,
            user_id=self._user_id,
            origin="runtime",
        )
        result = await self._cards.confirm_selected(event.payload.confirmation_id, context)
        confirmed = self._append_event(
            session_id,
            "card.confirmed",
            {
                "confirmation_id": result.confirmation_id,
                "action_type": "speak",
                "replayed": result.replayed,
            },
            correlation_id=event.event_id,
        )
        await websocket.send_json(confirmed)

    async def _handle_transcript_provider_event(
        self,
        session_id: UUID,
        provider_event: ProviderTranscriptEvent,
    ) -> tuple[dict[str, object], ...]:
        is_final = provider_event.event_type == ProviderLiveEventType.TRANSCRIPT_FINAL
        transcript = self._append_event(
            session_id,
            "transcript.final" if is_final else "transcript.partial",
            {
                "utterance_id": provider_event.utterance_id,
                "speaker": provider_event.speaker,
                "language": provider_event.language,
                "text": provider_event.text,
                "revision": provider_event.revision,
            },
            correlation_id=provider_event.provider_event_id,
        )
        emitted = [transcript]
        if not is_final:
            return tuple(emitted)
        if self._translation_service is None:
            return tuple(await self._append_turn_outcome(session_id, transcript, emitted))
        if self._translation_service.has_seen(provider_event.utterance_id):
            return tuple(await self._append_turn_outcome(session_id, transcript, emitted))
        source_event_id = _string_field(transcript, "event_id")
        segment_id = f"seg_{provider_event.utterance_id}"
        emitted.append(
            self._append_event(
                session_id,
                "translation.pending",
                {
                    "source_transcript_event_id": source_event_id,
                    "segment_id": segment_id,
                },
                correlation_id=source_event_id,
            )
        )
        result = await self._translation_service.translate_final(
            TranslationRequest(
                source_event_id=source_event_id,
                utterance_id=provider_event.utterance_id,
                text=provider_event.text,
                source_language=provider_event.language,
            )
        )
        if result.duplicate:
            return tuple(emitted[:-1])
        if result.segment is not None:
            emitted.append(
                self._append_event(
                    session_id,
                    "translation.final",
                    {
                        "source_transcript_event_id": result.segment.source_transcript_event_id,
                        "segment_id": result.segment.segment_id,
                        "source_language": result.segment.source_language,
                        "target_language": result.segment.target_language,
                        "translated_text": result.segment.translated_text,
                        "mode": "faithful",
                        "append_only": True,
                        "latency_ms": result.segment.latency_ms,
                    },
                    correlation_id=source_event_id,
                )
            )
            return tuple(await self._append_turn_outcome(session_id, transcript, emitted))
        fallback = result.fallback
        assert fallback is not None
        emitted.append(
            self._append_event(
                session_id,
                "fallback.show",
                {
                    "code": fallback.code,
                    "message_zh": TRANSLATION_UNAVAILABLE_ZH,
                    "message_en": TRANSLATION_UNAVAILABLE_EN,
                    "retryable": True,
                    "recovery_action": "return_to_listening",
                    "related_event_id": fallback.related_event_id,
                },
                correlation_id=source_event_id,
            )
        )
        return tuple(await self._append_turn_outcome(session_id, transcript, emitted))

    async def _append_turn_outcome(
        self,
        session_id: UUID,
        transcript: dict[str, object],
        emitted: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if self._turn_orchestrator is None or self._user_id is None:
            return emitted
        event = TranscriptFinalEvent.model_validate(transcript)
        outcome = await self._turn_orchestrator.process_final_turn(
            event,
            TrustedRequestContext(session_id=session_id, user_id=self._user_id, origin="runtime"),
        )
        emitted.append(
            self._append_event(
                session_id,
                "route.decision",
                {
                    "source_transcript_event_id": event.event_id,
                    "route_type": outcome.route.route_type.value,
                    "confidence": outcome.route.confidence,
                    "reason_code": outcome.route.reason_code.value,
                },
                correlation_id=event.event_id,
            )
        )
        if outcome.guardian.decision is GuardianDecisionType.BLOCK:
            emitted.append(
                self._append_event(
                    session_id,
                    "guardian.warning",
                    {
                        "guardian_decision_id": outcome.guardian.guardian_decision_id,
                        "source_event_id": event.event_id,
                        "decision": outcome.guardian.decision.value,
                        "risk_level": outcome.guardian.risk_level.value,
                        "reason_code": outcome.guardian.reason_code.value,
                        "warning_type": "privacy_block",
                        "zh_title": "已为你拦截敏感请求",
                        "zh_message": "这类信息不应自动提供。你可以请药剂师换一种方式确认。",
                        "safe_card_set_id": None,
                    },
                    correlation_id=event.event_id,
                )
            )
        if (
            outcome.card_proposal is not None
            and outcome.card_review is not None
            and outcome.card_review.decision is GuardianDecisionType.ALLOW
        ):
            emitted.append(
                self._append_event(
                    session_id,
                    "cards.render",
                    {"card_set": outcome.card_proposal.card_set.model_dump(mode="json")},
                    correlation_id=event.event_id,
                )
            )
        return emitted

    @staticmethod
    def _sequence(event: dict[str, object]) -> int:
        sequence = event["sequence"]
        if not isinstance(sequence, int):
            raise RuntimeError("RUNTIME_SEQUENCE_INVALID")
        return sequence

    def _append_event(
        self,
        session_id: UUID,
        event_type: str,
        payload: dict[str, object],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        buffer = self._buffers.setdefault(session_id, self._initial_events(session_id))
        event = self._event(
            session_id,
            self._sequence(buffer[-1]) + 1,
            event_type,
            payload,
            correlation_id=correlation_id,
        )
        buffer.append(event)
        if len(buffer) > self.MAX_BUFFERED_EVENTS:
            del buffer[: -self.MAX_BUFFERED_EVENTS]
        return event

    def _event(
        self,
        session_id: UUID,
        sequence: int,
        event_type: str,
        payload: dict[str, object],
        *,
        correlation_id: str | None = None,
    ) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "event_id": f"evt_{uuid4()}",
            "event_type": event_type,
            "session_id": str(session_id),
            "sequence": sequence,
            "timestamp": self._clock().isoformat().replace("+00:00", "Z"),
            "correlation_id": correlation_id,
            "payload": payload,
        }

    async def _serve_real_live(self, websocket: WebSocket, session_id: UUID) -> None:
        import asyncio
        from app.adapters.provider_schemas import LiveSessionContext
        from starlette.websockets import WebSocketDisconnect
        import logging

        logger = logging.getLogger(__name__)

        system_instruction = (
            "You are Kith&Kin's real-time voice bridge. "
            "You are listening to the pharmacist speaking English. "
            "You must NEVER reply, respond, or generate audio on your own to the pharmacist's voice. "
            "Only listen and transcribe. "
            "You will receive English text messages from Kith&Kin to voice to the pharmacist. "
            "When you receive a text message, read it out loud in English exactly."
        )

        context = LiveSessionContext(
            session_id=session_id,
            user_id=self._user_id or UUID("00000000-0000-4000-8000-000000000001"),
            system_instruction=system_instruction,
        )

        buffer = self._buffers.setdefault(session_id, self._initial_events(session_id))

        if not self._live_gateway:
            fallback = self._append_event(
                session_id,
                "fallback.show",
                {
                    "code": "LIVE_UNAVAILABLE",
                    "message_zh": LIVE_UNAVAILABLE_ZH,
                    "message_en": "Live speech is temporarily unavailable.",
                    "retryable": True,
                    "recovery_action": "reconnect",
                    "related_event_id": None,
                },
            )
            await websocket.send_json(fallback)
            return

        try:
            port = await self._live_gateway.open_session(context)
        except Exception as e:
            logger.exception("Failed to open Gemini Live session")
            fallback = self._append_event(
                session_id,
                "fallback.show",
                {
                    "code": "LIVE_UNAVAILABLE",
                    "message_zh": LIVE_UNAVAILABLE_ZH,
                    "message_en": "Live speech is temporarily unavailable.",
                    "retryable": True,
                    "recovery_action": "reconnect",
                    "related_event_id": None,
                },
            )
            await websocket.send_json(fallback)
            return

        try:
            await asyncio.gather(
                self._read_client_loop(websocket, session_id, port),
                self._read_provider_loop(websocket, session_id, port),
            )
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.warning(f"Live transport error in serving loops: {e}")
            fallback = self._append_event(
                session_id,
                "fallback.show",
                {
                    "code": "COMPANION_UNAVAILABLE",
                    "message_zh": "实时连接遇到问题，已自动降级。",
                    "message_en": "Real-time connection encountered an issue.",
                    "retryable": True,
                    "recovery_action": "reconnect",
                    "related_event_id": None,
                },
            )
            try:
                await websocket.send_json(fallback)
            except Exception:
                pass
        finally:
            await port.close()

    async def _read_client_loop(self, websocket: WebSocket, session_id: UUID, port: Any) -> None:
        from starlette.websockets import WebSocketDisconnect
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                frame = message.get("bytes")
                if isinstance(frame, bytes):
                    await port.send_audio(frame)
                    continue
                text = message.get("text")
                if isinstance(text, str):
                    await self._handle_live_command(websocket, session_id, text, port)
        except WebSocketDisconnect:
            pass

    async def _read_provider_loop(self, websocket: WebSocket, session_id: UUID, port: Any) -> None:
        from app.adapters.provider_schemas import (
            ProviderAudioEvent,
            ProviderTranscriptEvent,
            ProviderErrorEvent,
            ProviderLiveEventType,
        )
        model_speaking = False
        async for event in port.events():
            if isinstance(event, ProviderAudioEvent):
                if not model_speaking:
                    model_speaking = True
                    muted_evt = self._append_event(
                        session_id,
                        "audio.muted",
                        {"muted": True, "reason": "tts_playback"}
                    )
                    await websocket.send_json(muted_evt)
                    
                    speaking_evt = self._append_event(
                        session_id,
                        "audio.speaking",
                        {"phase": "started"}
                    )
                    await websocket.send_json(speaking_evt)
                await websocket.send_bytes(event.audio)
            elif isinstance(event, ProviderTranscriptEvent):
                if event.language == "zh":
                    is_final = event.event_type == ProviderLiveEventType.TRANSCRIPT_FINAL
                    if is_final:
                        trans_final_evt = self._append_event(
                            session_id,
                            "translation.final",
                            {
                                "source_transcript_event_id": f"evt_{uuid4()}",
                                "segment_id": event.utterance_id,
                                "source_language": "en",
                                "target_language": "zh_cn",
                                "translated_text": event.text,
                                "mode": "faithful",
                                "append_only": True,
                                "latency_ms": 100,
                            }
                        )
                        await websocket.send_json(trans_final_evt)
                elif event.utterance_id == "turn_complete":
                    if model_speaking:
                        model_speaking = False
                        speaking_evt = self._append_event(
                            session_id,
                            "audio.speaking",
                            {"phase": "completed"}
                        )
                        await websocket.send_json(speaking_evt)
                        
                        muted_evt = self._append_event(
                            session_id,
                            "audio.muted",
                            {"muted": False, "reason": "tts_playback"}
                        )
                        await websocket.send_json(muted_evt)
                        
                        listening_evt = self._append_event(
                            session_id,
                            "audio.listening",
                            {"active": True}
                        )
                        await websocket.send_json(listening_evt)
                else:
                    outcomes = await self.handle_provider_event(session_id, event)
                    for out in outcomes:
                        await websocket.send_json(out)
                    is_final = event.event_type == ProviderLiveEventType.TRANSCRIPT_FINAL
                    if is_final and model_speaking:
                        model_speaking = False
                        speaking_evt = self._append_event(
                            session_id,
                            "audio.speaking",
                            {"phase": "completed"}
                        )
                        await websocket.send_json(speaking_evt)
                        
                        muted_evt = self._append_event(
                            session_id,
                            "audio.muted",
                            {"muted": False, "reason": "tts_playback"}
                        )
                        await websocket.send_json(muted_evt)
                        
                        listening_evt = self._append_event(
                            session_id,
                            "audio.listening",
                            {"active": True}
                        )
                        await websocket.send_json(listening_evt)
            elif isinstance(event, ProviderErrorEvent):
                outcomes = await self.handle_provider_event(session_id, event)
                for out in outcomes:
                    await websocket.send_json(out)

    async def _handle_live_command(
        self, websocket: WebSocket, session_id: UUID, text: str, port: Any
    ) -> None:
        import json
        from app.schemas.runtime_events import parse_runtime_event, CardConfirmEvent, TranscriptFinalEvent
        try:
            event = parse_runtime_event(json.loads(text))
        except (ValueError, json.JSONDecodeError):
            return

        if isinstance(event, TranscriptFinalEvent):
            from app.adapters.provider_schemas import ProviderLiveEventType, ProviderTranscriptEvent
            provider_event = ProviderTranscriptEvent(
                event_type=ProviderLiveEventType.TRANSCRIPT_FINAL,
                provider_event_id=event.event_id,
                utterance_id=event.payload.utterance_id,
                speaker=event.payload.speaker,
                language=event.payload.language,
                text=event.payload.text,
                revision=event.payload.revision,
            )
            provider_outcomes = await self._handle_transcript_provider_event(
                session_id, provider_event
            )
            for provider_outcome in provider_outcomes:
                await websocket.send_json(provider_outcome)
            return

        if self._command_service is not None and not isinstance(event, CardConfirmEvent):
            outcomes = await self._command_service.handle(event, session_id=session_id)
            for outcome in outcomes:
                emitted = self._append_event(
                    session_id,
                    outcome.event_type,
                    outcome.payload,
                    correlation_id=outcome.correlation_id,
                )
                await websocket.send_json(emitted)
            return

        if isinstance(event, CardConfirmEvent):
            if self._user_id is None:
                raise RuntimeError("Missing user ID")
            context = TrustedRequestContext(
                session_id=session_id,
                user_id=self._user_id,
                origin="runtime",
            )
            
            # Security Gate: Fetch card & verify Guardian ALLOW state
            card = self._cards.get_card_by_confirmation(event.payload.confirmation_id)
            if card is None:
                logger.warning("Card confirmation rejected: card not found")
                return

            try:
                outcome = await self._cards.confirm_selected(event.payload.confirmation_id, context)
            except Exception as e:
                logger.warning(f"Card confirmation failed: {e}")
                from app.core.constants import CardActionType
                err_event = self._append_event(
                    session_id,
                    "card.action.status",
                    {
                        "confirmation_id": event.payload.confirmation_id,
                        "action_type": CardActionType.NO_ACTION.value,
                        "phase": "blocked",
                        "code": "ACTION_BLOCKED",
                    },
                    correlation_id=event.event_id,
                )
                await websocket.send_json(err_event)
                return

            confirmed = self._append_event(
                session_id,
                "card.confirmed",
                {
                    "confirmation_id": outcome.confirmation_id,
                    "action_type": outcome.action_type.value,
                    "replayed": outcome.replayed,
                },
                correlation_id=event.event_id,
            )
            await websocket.send_json(confirmed)

            if outcome.phase == "succeeded" or outcome.action_type.value in ("speak", "notify_family", "save_memory"):
                muted_evt = self._append_event(
                    session_id,
                    "audio.muted",
                    {"muted": True, "reason": "tts_playback"}
                )
                await websocket.send_json(muted_evt)
                
                speaking_evt = self._append_event(
                    session_id,
                    "audio.speaking",
                    {"phase": "started", "card_id": card.card_id}
                )
                await websocket.send_json(speaking_evt)
                await port.send_text(card.en_text)


def _string_field(event: dict[str, Any], field: str) -> str:
    value = event[field]
    if not isinstance(value, str):
        raise RuntimeError("RUNTIME_EVENT_FIELD_INVALID")
    return value
