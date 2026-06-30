import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.adapters.fake_live_adapter import FakeLiveAdapter
from app.adapters.provider_schemas import (
    LiveSessionContext,
    ProviderAudioEvent,
    ProviderErrorEvent,
    ProviderLiveEvent,
    ProviderLiveEventType,
    ProviderTranscriptEvent,
    TextToSpeechGateway,
    TranslationRequest,
)
from app.core.constants import (
    SCHEMA_VERSION,
    CardActionType,
    CardRiskLevel,
    GuardianDecisionType,
)
from app.core.conversation_debug import conversation_log, session_ref
from app.domain.credentials import TrustedRequestContext
from app.schemas.cards import CardAction, CardSet, CardType, ResponseCard
from app.schemas.runtime_events import (
    AudioSpeakerChangedEvent,
    CardConfirmEvent,
    TranscriptFinalEvent,
    parse_runtime_event,
)
from app.services.card_service import CardService
from app.services.pharmacy_product_options import PharmacyProductOptionTracker
from app.services.runtime_command_service import RuntimeCommandService
from app.services.translation_service import TranslationService
from app.services.turn_orchestrator import TurnOrchestrator

logger = logging.getLogger(__name__)

LIVE_UNAVAILABLE_ZH = (
    "\u6682\u65f6\u65e0\u6cd5\u8fde\u63a5\u5b9e\u65f6\u8bed\u97f3\u670d\u52a1\u3002"
)
TRANSLATION_UNAVAILABLE_ZH = (
    "\u6682\u65f6\u65e0\u6cd5\u751f\u6210\u4e2d\u6587\u7ffb\u8bd1\uff0c"
    "\u82f1\u6587\u539f\u6587\u4ecd\u4fdd\u7559\u3002"
)
TRANSLATION_UNAVAILABLE_EN = (
    "Translation is temporarily unavailable; the English transcript remains visible."
)


def _get_chinese_advice(en_text: str) -> str:
    lower = en_text.lower()
    if "no pharmacist medication instructions were recorded" in lower:
        return "没有记录到药师的用药说明。"
    if "routine" in lower:
        return "本次药局对话已结束。"
    return f"药师原话摘要：{en_text}"


def _get_chinese_question(en_q: str) -> str:
    return f"待确认问题：{en_q}"


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
        tts_gateway: TextToSpeechGateway | None = None,
        settings: Any = None,
        completion_service: Any = None,
    ) -> None:
        self._cards = card_service
        self._fake_live = fake_live
        self._clock = clock
        self._translation_service = translation_service
        self._command_service = command_service
        self._turn_orchestrator = turn_orchestrator
        self._user_id = user_id
        self._live_gateway = live_gateway
        self._tts_gateway = tts_gateway
        self._settings = settings
        self._completion_service = completion_service
        self._buffers: dict[UUID, list[dict[str, object]]] = {}
        self._speech_sessions: set[UUID] = set()
        self._speech_audio_seen: set[UUID] = set()
        self._active_speech_actions: dict[UUID, tuple[str, CardActionType]] = {}
        self._paused_sessions: set[UUID] = set()
        self._last_spoken_text: dict[UUID, str] = {}
        self._speaker_sessions: dict[UUID, Literal["parent", "pharmacist"]] = {}
        self._product_options = PharmacyProductOptionTracker()
        self._client_audio_frame_counts: dict[UUID, int] = {}
        self._provider_audio_frame_counts: dict[UUID, int] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}

    def discard_session(self, session_id: UUID) -> None:
        self._buffers.pop(session_id, None)
        self._speech_sessions.discard(session_id)
        self._speech_audio_seen.discard(session_id)
        self._active_speech_actions.pop(session_id, None)
        self._paused_sessions.discard(session_id)
        self._last_spoken_text.pop(session_id, None)
        self._speaker_sessions.pop(session_id, None)
        self._product_options.discard_session(str(session_id))
        self._client_audio_frame_counts.pop(session_id, None)
        self._provider_audio_frame_counts.pop(session_id, None)

    def _log_client_audio_frame(
        self,
        session_id: UUID,
        byte_length: int,
        *,
        transport: str,
    ) -> None:
        count = self._client_audio_frame_counts.get(session_id, 0) + 1
        self._client_audio_frame_counts[session_id] = count
        if count == 1 or count % 100 == 0:
            conversation_log(
                "live.client_audio.frame",
                session=session_ref(session_id),
                transport=transport,
                frame_count=count,
                byte_length=byte_length,
            )

    def _log_provider_audio_frame(
        self,
        session_id: UUID,
        *,
        provider_event_id: str,
        byte_length: int,
    ) -> None:
        count = self._provider_audio_frame_counts.get(session_id, 0) + 1
        self._provider_audio_frame_counts[session_id] = count
        if count == 1 or count % 20 == 0:
            conversation_log(
                "live.provider_audio.chunk",
                session=session_ref(session_id),
                provider_event_id=provider_event_id,
                frame_count=count,
                byte_length=byte_length,
            )

    async def _speak_confirmed_text(
        self,
        websocket: WebSocket,
        session_id: UUID,
        *,
        text: str,
        card_id: str,
        confirmation_id: str,
        action_type: CardActionType,
        correlation_id: str | None,
    ) -> None:
        if self._tts_gateway is None:
            raise RuntimeError("TTS_GATEWAY_UNAVAILABLE")
        conversation_log(
            "live.card_tts.request",
            session=session_ref(session_id),
            confirmation_id=confirmation_id,
            card_id=card_id,
            action_type=action_type.value,
            spoken_text=text,
        )
        muted_evt = self._append_event(
            session_id,
            "audio.muted",
            {"muted": True, "reason": "tts_playback"},
        )
        await websocket.send_json(muted_evt)

        speaking_evt = self._append_event(
            session_id,
            "audio.speaking",
            {"phase": "started", "card_id": card_id},
        )
        await websocket.send_json(speaking_evt)

        started_evt = self._append_event(
            session_id,
            "card.action.status",
            {
                "confirmation_id": confirmation_id,
                "action_type": action_type.value,
                "phase": "started",
                "code": None,
            },
            correlation_id=correlation_id,
        )
        await websocket.send_json(started_evt)

        try:
            speech = await self._tts_gateway.synthesize(text)
            conversation_log(
                "live.card_tts.audio_ready",
                session=session_ref(session_id),
                confirmation_id=confirmation_id,
                card_id=card_id,
                byte_length=len(speech.audio),
                mime_type=speech.mime_type,
                sample_rate_hz=speech.sample_rate_hz,
            )
            await websocket.send_bytes(speech.audio)
            conversation_log(
                "live.card_tts.audio_sent",
                session=session_ref(session_id),
                confirmation_id=confirmation_id,
                card_id=card_id,
                byte_length=len(speech.audio),
            )
        except Exception as exc:
            conversation_log(
                "live.card_tts.failed",
                session=session_ref(session_id),
                confirmation_id=confirmation_id,
                card_id=card_id,
                error=type(exc).__name__,
            )
            failed_evt = self._append_event(
                session_id,
                "card.action.status",
                {
                    "confirmation_id": confirmation_id,
                    "action_type": action_type.value,
                    "phase": "failed",
                    "code": "AUDIO_DELIVERY_FAILED",
                },
                correlation_id=correlation_id,
            )
            await websocket.send_json(failed_evt)
            conversation_log(
                "live.card_action.status",
                session=session_ref(session_id),
                confirmation_id=confirmation_id,
                action_type=action_type.value,
                phase="failed",
                code="AUDIO_DELIVERY_FAILED",
            )
            await self._restore_listening_after_tts(websocket, session_id)
            return

        completed_evt = self._append_event(
            session_id,
            "audio.speaking",
            {"phase": "completed"},
        )
        await websocket.send_json(completed_evt)
        succeeded_evt = self._append_event(
            session_id,
            "card.action.status",
            {
                "confirmation_id": confirmation_id,
                "action_type": action_type.value,
                "phase": "succeeded",
                "code": None,
            },
            correlation_id=correlation_id,
        )
        await websocket.send_json(succeeded_evt)
        conversation_log(
            "live.card_action.status",
            session=session_ref(session_id),
            confirmation_id=confirmation_id,
            action_type=action_type.value,
            phase="succeeded",
            code=None,
        )
        await self._restore_listening_after_tts(websocket, session_id)

    async def _restore_listening_after_tts(
        self,
        websocket: WebSocket,
        session_id: UUID,
    ) -> None:
        muted_evt = self._append_event(
            session_id,
            "audio.muted",
            {"muted": False, "reason": "tts_playback"},
        )
        await websocket.send_json(muted_evt)

        listening_evt = self._append_event(
            session_id,
            "audio.listening",
            {"active": True},
        )
        await websocket.send_json(listening_evt)

    async def serve(
        self,
        websocket: WebSocket,
        session_id: UUID,
        *,
        last_seen_sequence: int | None,
    ) -> None:
        buffer = self._buffers.setdefault(session_id, self._initial_events(session_id))
        conversation_log(
            "live.serve.start",
            session=session_ref(session_id),
            transport=getattr(self._settings, "live_transport", "backend_proxy"),
            last_seen_sequence=last_seen_sequence,
            buffered_events=len(buffer),
        )
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
        events = (
            buffer
            if last_seen_sequence is None
            else [event for event in buffer if self._sequence(event) > last_seen_sequence]
        )
        for event in events:
            await websocket.send_json(event)

        if self._settings and getattr(self._settings, "live_transport", None) == "gemini_live":
            conversation_log("live.serve.real_live", session=session_ref(session_id))
            await self._serve_real_live(websocket, session_id)
            return

        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                frame = message.get("bytes")
                if isinstance(frame, bytes):
                    self._log_client_audio_frame(session_id, len(frame), transport="fake")
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
            return await self._handle_transcript_provider_event(
                session_id,
                provider_event,
                apply_speaker_override=True,
            )
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
        if isinstance(event, AudioSpeakerChangedEvent):
            self._speaker_sessions[session_id] = event.payload.speaker
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
                session_id,
                provider_event,
                apply_speaker_override=False,
                include_turn_outcome=False,
            )
            for provider_outcome in provider_outcomes:
                await websocket.send_json(provider_outcome)
            transcript = next(
                (
                    outcome
                    for outcome in provider_outcomes
                    if outcome.get("event_type") == "transcript.final"
                ),
                None,
            )
            if transcript is not None and not _is_identity_request(provider_event.text.lower()):
                asyncio.create_task(
                    self._send_turn_outcome(websocket, session_id, transcript)
                )
            return
        if self._command_service is not None:
            from app.schemas.runtime_events import (
                PleaseWaitEvent,
                RepeatEvent,
                SelfSpeakEvent,
                SessionEndEvent,
            )

            if isinstance(event, PleaseWaitEvent):
                self._paused_sessions.add(session_id)
            elif isinstance(event, SelfSpeakEvent):
                self._paused_sessions.add(session_id)
            elif isinstance(event, RepeatEvent):
                self._paused_sessions.discard(session_id)

            outcomes = await self._command_service.handle(event, session_id=session_id)
            for outcome in outcomes:
                emitted = self._append_event(
                    session_id,
                    outcome.event_type,
                    outcome.payload,
                    correlation_id=outcome.correlation_id,
                )
                await websocket.send_json(emitted)

            if isinstance(event, CardConfirmEvent):
                context = TrustedRequestContext(
                    session_id=session_id,
                    user_id=self._user_id or UUID("00000000-0000-4000-8000-000000000001"),
                    origin="runtime",
                )
                try:
                    card = self._cards.get_card_by_confirmation(
                        event.payload.confirmation_id,
                        context,
                    )
                    result = await self._cards.confirm_selected(event.payload.confirmation_id, context)
                    from app.core.constants import CardActionType

                    should_voice_action = result.action_type in (
                        CardActionType.SPEAK,
                        CardActionType.SHOW_TO_PHARMACIST,
                    ) or str(result.action_type) in ("speak", "show_to_pharmacist")

                    if result.phase == "succeeded" and should_voice_action:
                        if self._tts_gateway is not None:
                            await self._speak_confirmed_text(
                                websocket,
                                session_id,
                                text=card.en_text,
                                card_id=card.card_id,
                                confirmation_id=result.confirmation_id,
                                action_type=result.action_type,
                                correlation_id=event.event_id,
                            )
                except Exception as ex:
                    logger.exception("Failed handling deterministic CardConfirmEvent: %s", ex)

            # If SessionEndEvent in mock mode, generate and emit summary.render
            if isinstance(event, SessionEndEvent) and self._completion_service is not None:
                context = TrustedRequestContext(
                    session_id=session_id,
                    user_id=self._user_id or UUID("00000000-0000-4000-8000-000000000001"),
                    origin="runtime",
                )
                try:
                    summary_review = await self._completion_service.prepare_summary(
                        session_id, context
                    )
                    advice_zh = _get_chinese_advice(summary_review.pharmacist_advice_summary)
                    questions_zh = [
                        _get_chinese_question(q) for q in summary_review.unresolved_questions
                    ]

                    summary_payload: dict[str, object] = {
                        "summary_id": f"sum-{uuid4()}",
                        "summary": {
                            "title_zh": "今天药局沟通重点",
                            "mentioned_drugs": list(summary_review.mentioned_drugs),
                            "pharmacist_advice_summary_zh": advice_zh,
                            "unresolved_questions_zh": questions_zh,
                            "follow_up_needed": summary_review.follow_up_needed,
                            "pharmacist_stated_advice_zh": advice_zh,
                            "unresolved_follow_up_questions_zh": questions_zh,
                            "confirmed_family_follow_up": (
                                summary_review.confirmed_family_follow_up
                            ),
                        },
                        "card_set_id": f"cards-summary-{uuid4()}",
                    }
                    summary_event = self._append_event(
                        session_id,
                        "summary.render",
                        summary_payload,
                    )
                    await websocket.send_json(summary_event)
                except Exception as e:
                    logger.warning("Failed to generate mock summary: %s", e)
            return



    async def _handle_transcript_provider_event(
        self,
        session_id: UUID,
        provider_event: ProviderTranscriptEvent,
        *,
        apply_speaker_override: bool = True,
        include_turn_outcome: bool = True,
    ) -> tuple[dict[str, object], ...]:
        if provider_event.utterance_id != "turn_complete" and _is_provider_thought_text(
            provider_event.text
        ):
            conversation_log(
                "live.provider_transcript.filtered_thought",
                session=session_ref(session_id),
                provider_event_id=provider_event.provider_event_id,
                utterance_id=provider_event.utterance_id,
                text=provider_event.text,
            )
            return ()

        active_speaker = self._speaker_sessions.get(session_id)
        if (
            apply_speaker_override
            and active_speaker is not None
            and provider_event.utterance_id != "turn_complete"
        ):
            conversation_log(
                "live.provider_transcript.speaker_override",
                session=session_ref(session_id),
                provider_event_id=provider_event.provider_event_id,
                utterance_id=provider_event.utterance_id,
                original_speaker=provider_event.speaker,
                active_speaker=active_speaker,
            )
            provider_event = replace(provider_event, speaker=active_speaker)

        # Filter out self-echoes of Kith & Kin's TTS spoken English
        last_spoken = self._last_spoken_text.get(session_id)
        if last_spoken and provider_event.text:
            import re
            norm_incoming = re.sub(r'[^a-z0-9\s]', '', provider_event.text.lower()).strip()
            norm_spoken = re.sub(r'[^a-z0-9\s]', '', last_spoken.lower()).strip()
            is_match = (
                norm_incoming == norm_spoken
                or (len(norm_spoken) > 5 and norm_spoken in norm_incoming)
                or (len(norm_incoming) > 5 and norm_incoming in norm_spoken)
            )
            if is_match:
                logger.info(
                    "Filtered out self-echo for session %s: incoming=%r, last_spoken=%r",
                    session_id,
                    provider_event.text,
                    last_spoken,
                )
                conversation_log(
                    "live.provider_transcript.filtered_self_echo",
                    session=session_ref(session_id),
                    provider_event_id=provider_event.provider_event_id,
                    utterance_id=provider_event.utterance_id,
                    incoming_text=provider_event.text,
                    last_spoken_text=last_spoken,
                )
                return ()

        is_final = provider_event.event_type == ProviderLiveEventType.TRANSCRIPT_FINAL
        conversation_log(
            "live.provider_transcript.received",
            session=session_ref(session_id),
            provider_event_id=provider_event.provider_event_id,
            utterance_id=provider_event.utterance_id,
            event_type=provider_event.event_type.value,
            is_final=is_final,
            speaker=provider_event.speaker,
            language=provider_event.language,
            text=provider_event.text,
            apply_speaker_override=apply_speaker_override,
            include_turn_outcome=include_turn_outcome,
        )
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
        source_event_id = _string_field(transcript, "event_id")
        if provider_event.speaker == "pharmacist":
            product_snapshot = self._product_options.update(
                str(session_id),
                provider_event.text,
            )
            if product_snapshot is not None:
                options = product_snapshot.get("options", ())
                conversation_log(
                    "live.product_options.render",
                    session=session_ref(session_id),
                    source_event_id=source_event_id,
                    option_count=len(options) if isinstance(options, (list, tuple)) else None,
                )
                emitted.append(
                    self._append_event(
                        session_id,
                        "product.options.render",
                        product_snapshot,
                        correlation_id=source_event_id,
                    )
                )
            if not include_turn_outcome and _is_identity_request(provider_event.text.lower()):
                event = TranscriptFinalEvent.model_validate(transcript)
                self._append_identity_cards(session_id, event, emitted)
        if self._translation_service is None:
            if include_turn_outcome:
                return tuple(await self._append_turn_outcome(session_id, transcript, emitted))
            return tuple(emitted)
        if self._translation_service.has_seen(provider_event.utterance_id):
            conversation_log(
                "live.translation.skipped_duplicate",
                session=session_ref(session_id),
                utterance_id=provider_event.utterance_id,
            )
            if include_turn_outcome:
                return tuple(await self._append_turn_outcome(session_id, transcript, emitted))
            return tuple(emitted)
        segment_id = f"seg_{provider_event.utterance_id}"
        conversation_log(
            "live.translation.start",
            session=session_ref(session_id),
            source_event_id=source_event_id,
            utterance_id=provider_event.utterance_id,
            source_language=provider_event.language,
            text=provider_event.text,
        )
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
            conversation_log(
                "live.translation.duplicate_after_request",
                session=session_ref(session_id),
                utterance_id=provider_event.utterance_id,
            )
            return tuple(emitted[:-1])
        if result.segment is not None:
            conversation_log(
                "live.translation.final",
                session=session_ref(session_id),
                source_event_id=source_event_id,
                utterance_id=provider_event.utterance_id,
                translated_text=result.segment.translated_text,
                latency_ms=result.segment.latency_ms,
            )
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
            if include_turn_outcome:
                return tuple(await self._append_turn_outcome(session_id, transcript, emitted))
            return tuple(emitted)
        fallback = result.fallback
        assert fallback is not None
        conversation_log(
            "live.translation.fallback",
            session=session_ref(session_id),
            source_event_id=source_event_id,
            utterance_id=provider_event.utterance_id,
            code=fallback.code,
        )
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
        if include_turn_outcome:
            return tuple(await self._append_turn_outcome(session_id, transcript, emitted))
        return tuple(emitted)

    async def _send_turn_outcome(
        self,
        websocket: WebSocket,
        session_id: UUID,
        transcript: dict[str, object],
    ) -> None:
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            try:
                outcomes = await self._append_turn_outcome(session_id, transcript, [])
                for outcome in outcomes:
                    await websocket.send_json(outcome)
            except Exception:
                logger.warning("Background turn outcome failed", exc_info=True)

    def _append_identity_cards(
        self,
        session_id: UUID,
        event: TranscriptFinalEvent,
        emitted: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        card_set = self._identity_card_set(event)
        conversation_log(
            "live.identity_cards.render",
            session=session_ref(session_id),
            source_event_id=event.event_id,
            card_count=len(card_set.cards),
            reason="identity_request",
        )
        self._cards.register_card_set(
            card_set,
            TrustedRequestContext(
                session_id=session_id,
                user_id=self._user_id,
                origin="runtime",
            ),
        )
        emitted.append(
            self._append_event(
                session_id,
                "cards.render",
                {"card_set": card_set.model_dump(mode="json")},
                correlation_id=event.event_id,
            )
        )
        return emitted

    async def _append_turn_outcome(
        self,
        session_id: UUID,
        transcript: dict[str, object],
        emitted: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        if self._turn_orchestrator is None or self._user_id is None:
            conversation_log(
                "live.turn_outcome.skipped",
                session=session_ref(session_id),
                reason="missing_orchestrator_or_user",
            )
            return emitted
        event = TranscriptFinalEvent.model_validate(transcript)
        if event.payload.speaker != "pharmacist":
            conversation_log(
                "live.turn_outcome.skipped",
                session=session_ref(session_id),
                source_event_id=event.event_id,
                reason="non_pharmacist_speaker",
                speaker=event.payload.speaker,
            )
            return emitted
        if _is_identity_request(event.payload.text.lower()):
            conversation_log(
                "live.turn_outcome.identity_request",
                session=session_ref(session_id),
                source_event_id=event.event_id,
            )
            return self._append_identity_cards(session_id, event, emitted)
        try:
            conversation_log(
                "live.turn_outcome.orchestrator.start",
                session=session_ref(session_id),
                source_event_id=event.event_id,
                transcript_text=event.payload.text,
            )
            outcome = await self._turn_orchestrator.process_final_turn(
                event,
                TrustedRequestContext(
                    session_id=session_id, user_id=self._user_id, origin="runtime"
                ),
                conversation_context=self._recent_conversation_context(session_id),
            )
        except Exception:
            # Agent/card track is best-effort: never let it discard the
            # already-produced transcript + translation events. Still surface a
            # COMPANION_UNAVAILABLE fallback so the UI knows cards degraded.
            logger.warning("Turn orchestrator failed; preserving translation", exc_info=True)
            conversation_log(
                "live.turn_outcome.orchestrator.failed",
                session=session_ref(session_id),
                source_event_id=event.event_id,
            )
            emitted.append(
                self._append_event(
                    session_id,
                    "fallback.show",
                    {
                        "code": "COMPANION_UNAVAILABLE",
                        "message_zh": "暂时无法生成回应卡片，翻译仍在继续。",
                        "message_en": (
                            "Response cards are temporarily unavailable; translation continues."
                        ),
                        "retryable": True,
                        "recovery_action": "return_to_listening",
                        "related_event_id": None,
                    },
                )
            )
            return emitted
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
        conversation_log(
            "live.turn_outcome.route",
            session=session_ref(session_id),
            source_event_id=event.event_id,
            route_type=outcome.route.route_type.value,
            route_reason=outcome.route.reason_code.value,
            guardian_decision=outcome.guardian.decision.value,
            guardian_reason=outcome.guardian.reason_code.value,
        )
        if outcome.guardian.decision is GuardianDecisionType.BLOCK:
            conversation_log(
                "live.turn_outcome.guardian_block",
                session=session_ref(session_id),
                source_event_id=event.event_id,
                risk_level=outcome.guardian.risk_level.value,
                reason_code=outcome.guardian.reason_code.value,
            )
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
            card_set = self._safe_card_set_for_turn(
                session_id,
                event,
                outcome.card_proposal.card_set,
            )
            if card_set is None:
                emitted.append(
                    self._append_event(
                        session_id,
                        "fallback.show",
                        {
                            "code": "CARD_REVIEW_FAILED",
                            "message_zh": "这组回应卡片没有通过安全检查，翻译仍在继续。",
                            "message_en": (
                                "These response cards did not pass safety review; "
                                "translation continues."
                            ),
                            "retryable": True,
                            "recovery_action": "return_to_listening",
                            "related_event_id": event.event_id,
                        },
                        correlation_id=event.event_id,
                    )
                )
                return emitted
            self._cards.register_card_set(
                card_set,
                TrustedRequestContext(
                    session_id=session_id,
                    user_id=self._user_id,
                    origin="runtime",
                ),
            )
            conversation_log(
                "live.cards.render",
                session=session_ref(session_id),
                source_event_id=event.event_id,
                card_set_id=card_set.card_set_id,
                card_count=len(card_set.cards),
                action_types=tuple(card.action.type.value for card in card_set.cards),
            )
            emitted.append(
                self._append_event(
                    session_id,
                    "cards.render",
                    {"card_set": card_set.model_dump(mode="json")},
                    correlation_id=event.event_id,
                )
            )
        elif (
            outcome.card_proposal is not None
            and outcome.card_review is not None
            and outcome.card_review.decision is not GuardianDecisionType.ALLOW
        ):
            conversation_log(
                "live.cards.review_failed",
                session=session_ref(session_id),
                source_event_id=event.event_id,
                card_review=outcome.card_review.decision.value,
                reason_code=outcome.card_review.reason_code.value,
            )
            card_set = self._safe_replacement_card_set_for_blocked_review(
                session_id,
                event,
                outcome.card_proposal.card_set,
            )
            if card_set is not None:
                self._cards.register_card_set(
                    card_set,
                    TrustedRequestContext(
                        session_id=session_id,
                        user_id=self._user_id,
                        origin="runtime",
                    ),
                )
                conversation_log(
                    "live.cards.safe_replacement_render",
                    session=session_ref(session_id),
                    source_event_id=event.event_id,
                    card_set_id=card_set.card_set_id,
                    card_count=len(card_set.cards),
                )
                emitted.append(
                    self._append_event(
                        session_id,
                        "cards.render",
                        {"card_set": card_set.model_dump(mode="json")},
                        correlation_id=event.event_id,
                    )
                )
                return emitted
            emitted.append(
                self._append_event(
                    session_id,
                    "fallback.show",
                    {
                        "code": "CARD_REVIEW_FAILED",
                        "message_zh": "这组回应卡片没有通过安全检查，翻译仍在继续。",
                        "message_en": (
                            "These response cards did not pass safety review; "
                            "translation continues."
                        ),
                        "retryable": True,
                        "recovery_action": "return_to_listening",
                        "related_event_id": event.event_id,
                    },
                    correlation_id=event.event_id,
                )
            )
        return emitted

    def _safe_card_set_for_turn(
        self,
        session_id: UUID,
        event: TranscriptFinalEvent,
        card_set: CardSet,
    ) -> CardSet | None:
        latest = event.payload.text.lower()
        card_text = " ".join(
            f"{card.zh_text} {card.en_text} {card.speak_zh or ''}" for card in card_set.cards
        ).lower()
        if _is_identity_request(latest):
            return self._identity_card_set(event)
        if _bundles_medication_and_allergy(card_text):
            return self._split_health_disclosure_card_set(event, card_text)
        if any(_is_meta_card_text(f"{card.zh_text} {card.en_text}") for card in card_set.cards):
            return None
        return card_set

    def _safe_replacement_card_set_for_blocked_review(
        self,
        session_id: UUID,
        event: TranscriptFinalEvent,
        card_set: CardSet,
    ) -> CardSet | None:
        latest = event.payload.text.lower()
        card_text = " ".join(
            f"{card.zh_text} {card.en_text} {card.speak_zh or ''}" for card in card_set.cards
        ).lower()
        if _is_health_disclosure_request(latest) and (
            _bundles_medication_and_allergy(card_text)
            or "penicillin" in card_text
            or "lisinopril" in card_text
            or "allergy" in card_text
            or "blood pressure" in card_text
        ):
            return self._split_health_disclosure_card_set(event, card_text)
        conversation_log(
            "live.cards.safe_replacement_skipped",
            session=session_ref(session_id),
            source_event_id=event.event_id,
        )
        return None

    def _identity_card_set(self, event: TranscriptFinalEvent) -> CardSet:
        now = self._clock()
        return CardSet(
            card_set_id=f"cards-identity-{uuid4()}",
            revision=1,
            source_event_id=event.event_id,
            generated_at=now,
            expires_at=now + timedelta(minutes=15),
            cards=(
                ResponseCard(
                    card_id=f"card-identity-repeat-{uuid4()}",
                    card_type=CardType.ASK_QUESTION,
                    zh_text="请药师重复需要我确认的姓名和生日。",
                    en_text="Could you please repeat the name and birthday you need me to confirm?",
                    speak_zh="请您重复需要我确认的姓名和生日。",
                    risk_level=CardRiskLevel.NORMAL,
                    action=CardAction(type=CardActionType.SPEAK),
                    requires_parent_confirmation=True,
                    requires_guardian_approval=True,
                    guardian_decision_id="guardian_identity_grounding",
                ),
                ResponseCard(
                    card_id=f"card-identity-write-{uuid4()}",
                    card_type=CardType.ASK_TO_WRITE_DOWN,
                    zh_text="请药师把要核对的姓名和生日写下来。",
                    en_text=(
                        "Could you please write down the name and birthday "
                        "you need me to check?"
                    ),
                    speak_zh="请您写下需要我核对的姓名和生日。",
                    risk_level=CardRiskLevel.NORMAL,
                    action=CardAction(type=CardActionType.SPEAK),
                    requires_parent_confirmation=True,
                    requires_guardian_approval=True,
                    guardian_decision_id="guardian_identity_grounding",
                ),
            ),
        )

    def _split_health_disclosure_card_set(
        self,
        event: TranscriptFinalEvent,
        card_text: str,
    ) -> CardSet:
        now = self._clock()
        medication = (
            "Lisinopril"
            if "lisinopril" in card_text
            else "my recorded blood pressure medicine"
        )
        allergy = "Penicillin" if "penicillin" in card_text else "my recorded allergy"
        return CardSet(
            card_set_id=f"cards-health-split-{uuid4()}",
            revision=1,
            source_event_id=event.event_id,
            generated_at=now,
            expires_at=now + timedelta(minutes=15),
            cards=(
                ResponseCard(
                    card_id=f"card-medication-{uuid4()}",
                    card_type=CardType.CONFIRM_INFO,
                    zh_text=f"我有记录正在用{medication}，请药师核对是否相关。",
                    en_text=(
                        f"I have a record that I take {medication}. "
                        "Could you please check whether that matters for these options?"
                    ),
                    speak_zh=f"我有记录正在用{medication}。请您核对这是否和这些选择有关。",
                    risk_level=CardRiskLevel.MEDICAL,
                    action=CardAction(type=CardActionType.SPEAK),
                    requires_parent_confirmation=True,
                    requires_guardian_approval=True,
                    guardian_decision_id="guardian_split_health_disclosure",
                ),
                ResponseCard(
                    card_id=f"card-allergy-{uuid4()}",
                    card_type=CardType.CONFIRM_INFO,
                    zh_text=f"我有记录对{allergy}过敏，请药师核对是否相关。",
                    en_text=(
                        f"I have a recorded {allergy} allergy. "
                        "Could you please check whether that matters for these options?"
                    ),
                    speak_zh=f"我有记录对{allergy}过敏。请您核对这是否和这些选择有关。",
                    risk_level=CardRiskLevel.MEDICAL,
                    action=CardAction(type=CardActionType.SPEAK),
                    requires_parent_confirmation=True,
                    requires_guardian_approval=True,
                    guardian_decision_id="guardian_split_health_disclosure",
                ),
            ),
        )

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

    def _recent_conversation_context(self, session_id: UUID, limit: int = 6) -> str | None:
        lines: list[str] = []
        for event in self._buffers.get(session_id, []):
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            if event.get("event_type") == "transcript.final":
                text = payload.get("text")
                if isinstance(text, str) and text.strip():
                    lines.append(f"Pharmacist: {text.strip()}")
            elif event.get("event_type") == "translation.final":
                text = payload.get("translated_text")
                if isinstance(text, str) and text.strip():
                    lines.append(f"Chinese translation: {text.strip()}")
        recent = lines[-limit:]
        return "\n".join(recent) if recent else None

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
        system_instruction = (
            "You are Kith&Kin's real-time voice bridge. "
            "You are listening to the pharmacist speaking English. "
            "You must NEVER reply, respond, or generate audio on your own to "
            "the pharmacist's voice. "
            "Only listen and transcribe. "
            "You will receive English text messages from Kith&Kin to voice to the pharmacist. "
            "When you receive a text message, read it out loud in English exactly."
        )

        context = LiveSessionContext(
            session_id=session_id,
            user_id=self._user_id or UUID("00000000-0000-4000-8000-000000000001"),
            system_instruction=system_instruction,
            current_speaker=lambda: self._speaker_sessions.get(session_id, "pharmacist"),
        )

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
        except Exception:
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
            tasks = {
                asyncio.create_task(self._read_client_loop(websocket, session_id, port)),
                asyncio.create_task(self._read_provider_loop(websocket, session_id, port)),
            }
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                task.result()
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Live transport error in serving loops: %s", e)
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
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    conversation_log("live.client.disconnect", session=session_ref(session_id))
                    break
                frame = message.get("bytes")
                if isinstance(frame, bytes):
                    self._log_client_audio_frame(session_id, len(frame), transport="gemini_live")
                    await port.send_audio(frame)
                    continue
                text = message.get("text")
                if isinstance(text, str):
                    try:
                        await self._handle_live_command(websocket, session_id, text, port)
                    except Exception as exc:
                        logging.getLogger(__name__).warning(
                            "Live command processing failed without closing audio transport: %s",
                            exc,
                        )
                        fallback = self._append_event(
                            session_id,
                            "fallback.show",
                            {
                                "code": "COMPANION_UNAVAILABLE",
                                "message_zh": "KK 暂时无法生成回应，实时聆听仍在继续。",
                                "message_en": (
                                    "KK cannot generate a response right now; "
                                    "live listening is still active."
                                ),
                                "retryable": True,
                                "recovery_action": "retry",
                                "related_event_id": None,
                            },
                        )
                        await websocket.send_json(fallback)
        except WebSocketDisconnect:
            pass

    async def _read_provider_loop(self, websocket: WebSocket, session_id: UUID, port: Any) -> None:
        model_speaking = False
        async for event in port.events():
            if isinstance(event, ProviderAudioEvent):
                if session_id not in self._speech_sessions:
                    conversation_log(
                        "live.provider_audio.ignored",
                        session=session_ref(session_id),
                        provider_event_id=event.provider_event_id,
                        byte_length=len(event.audio),
                        reason="no_active_speech_session",
                    )
                    continue
                model_speaking = True
                self._speech_audio_seen.add(session_id)
                self._log_provider_audio_frame(
                    session_id,
                    provider_event_id=event.provider_event_id,
                    byte_length=len(event.audio),
                )
                await websocket.send_bytes(event.audio)
            elif isinstance(event, ProviderTranscriptEvent):
                conversation_log(
                    "live.provider_event.transcript",
                    session=session_ref(session_id),
                    provider_event_id=event.provider_event_id,
                    utterance_id=event.utterance_id,
                    event_type=event.event_type.value,
                    speaker=event.speaker,
                    language=event.language,
                    text=event.text,
                )
                if session_id in self._paused_sessions:
                    conversation_log(
                        "live.provider_event.skipped_paused",
                        session=session_ref(session_id),
                        provider_event_id=event.provider_event_id,
                        utterance_id=event.utterance_id,
                    )
                    continue
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
                            },
                        )
                        await websocket.send_json(trans_final_evt)
                        outcomes = await self.handle_provider_event(session_id, event)
                        for out in outcomes:
                            await websocket.send_json(out)
                elif event.utterance_id == "turn_complete":
                    if session_id in self._speech_sessions:
                        action = self._active_speech_actions.get(session_id)
                        saw_audio = session_id in self._speech_audio_seen
                        conversation_log(
                            "live.provider_turn_complete",
                            session=session_ref(session_id),
                            provider_event_id=event.provider_event_id,
                            saw_audio=saw_audio,
                            has_active_action=action is not None,
                            model_speaking=model_speaking,
                        )
                        model_speaking = False
                        self._speech_sessions.discard(session_id)
                        self._speech_audio_seen.discard(session_id)
                        self._active_speech_actions.pop(session_id, None)
                        if saw_audio:
                            speaking_evt = self._append_event(
                                session_id,
                                "audio.speaking",
                                {"phase": "completed"},
                            )
                            await websocket.send_json(speaking_evt)
                            if action is not None:
                                confirmation_id, action_type = action
                                status_evt = self._append_event(
                                    session_id,
                                    "card.action.status",
                                    {
                                        "confirmation_id": confirmation_id,
                                        "action_type": action_type.value,
                                        "phase": "succeeded",
                                        "code": None,
                                    },
                                )
                                await websocket.send_json(status_evt)
                                conversation_log(
                                    "live.card_action.status",
                                    session=session_ref(session_id),
                                    confirmation_id=confirmation_id,
                                    action_type=action_type.value,
                                    phase="succeeded",
                                    code=None,
                                )
                        elif action is not None:
                            confirmation_id, action_type = action
                            failed_evt = self._append_event(
                                session_id,
                                "card.action.status",
                                {
                                    "confirmation_id": confirmation_id,
                                    "action_type": action_type.value,
                                    "phase": "failed",
                                    "code": "AUDIO_DELIVERY_FAILED",
                                },
                            )
                            await websocket.send_json(failed_evt)
                            conversation_log(
                                "live.card_action.status",
                                session=session_ref(session_id),
                                confirmation_id=confirmation_id,
                                action_type=action_type.value,
                                phase="failed",
                                code="AUDIO_DELIVERY_FAILED",
                            )

                        muted_evt = self._append_event(
                            session_id,
                            "audio.muted",
                            {"muted": False, "reason": "tts_playback"},
                        )
                        await websocket.send_json(muted_evt)

                        listening_evt = self._append_event(
                            session_id,
                            "audio.listening",
                            {"active": True},
                        )
                        await websocket.send_json(listening_evt)
                else:
                    outcomes = await self.handle_provider_event(session_id, event)
                    for out in outcomes:
                        await websocket.send_json(out)
                    is_final = event.event_type == ProviderLiveEventType.TRANSCRIPT_FINAL
                    if is_final and model_speaking:
                        model_speaking = False
                        self._speech_sessions.discard(session_id)
                        self._speech_audio_seen.discard(session_id)
                        self._active_speech_actions.pop(session_id, None)
                        speaking_evt = self._append_event(
                            session_id,
                            "audio.speaking",
                            {"phase": "completed"},
                        )
                        await websocket.send_json(speaking_evt)

                        muted_evt = self._append_event(
                            session_id,
                            "audio.muted",
                            {"muted": False, "reason": "tts_playback"},
                        )
                        await websocket.send_json(muted_evt)

                        listening_evt = self._append_event(
                            session_id,
                            "audio.listening",
                            {"active": True},
                        )
                        await websocket.send_json(listening_evt)
            elif isinstance(event, ProviderErrorEvent):
                conversation_log(
                    "live.provider_event.error",
                    session=session_ref(session_id),
                    provider_event_id=event.provider_event_id,
                    code=event.code,
                    retryable=event.retryable,
                )
                outcomes = await self.handle_provider_event(session_id, event)
                for out in outcomes:
                    await websocket.send_json(out)

    async def _handle_live_command(
        self, websocket: WebSocket, session_id: UUID, text: str, port: Any
    ) -> None:
        try:
            event = parse_runtime_event(json.loads(text))
        except (ValueError, json.JSONDecodeError):
            conversation_log("live.client_command.invalid", session=session_ref(session_id))
            return
        conversation_log(
            "live.client_command.received",
            session=session_ref(session_id),
            event_id=event.event_id,
            event_type=event.event_type,
        )

        if isinstance(event, AudioSpeakerChangedEvent):
            self._speaker_sessions[session_id] = event.payload.speaker
            conversation_log(
                "live.speaker_changed",
                session=session_ref(session_id),
                event_id=event.event_id,
                speaker=event.payload.speaker,
            )
            return

        if isinstance(event, TranscriptFinalEvent):
            conversation_log(
                "live.typed_transcript.received",
                session=session_ref(session_id),
                event_id=event.event_id,
                utterance_id=event.payload.utterance_id,
                speaker=event.payload.speaker,
                language=event.payload.language,
                text=event.payload.text,
            )
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
                session_id,
                provider_event,
                apply_speaker_override=False,
                include_turn_outcome=False,
            )
            for provider_outcome in provider_outcomes:
                await websocket.send_json(provider_outcome)
            transcript = next(
                (
                    outcome
                    for outcome in provider_outcomes
                    if outcome.get("event_type") == "transcript.final"
                ),
                None,
            )
            if transcript is not None:
                conversation_log(
                    "live.typed_transcript.turn_outcome_task",
                    session=session_ref(session_id),
                    event_id=event.event_id,
                    transcript_event_id=transcript.get("event_id"),
                )
                asyncio.create_task(
                    self._send_turn_outcome(websocket, session_id, transcript)
                )
            return

        if self._command_service is not None and not isinstance(event, CardConfirmEvent):
            from app.schemas.runtime_events import (
                PleaseWaitEvent,
                RepeatEvent,
                SelfSpeakEvent,
                SessionEndEvent,
            )

            if isinstance(event, PleaseWaitEvent):
                self._paused_sessions.add(session_id)
                conversation_log(
                    "live.pause.enabled",
                    session=session_ref(session_id),
                    reason="please_wait",
                )
            elif isinstance(event, SelfSpeakEvent):
                self._paused_sessions.add(session_id)
                conversation_log(
                    "live.pause.enabled",
                    session=session_ref(session_id),
                    reason="self_speak",
                )
            elif isinstance(event, RepeatEvent):
                self._paused_sessions.discard(session_id)
                repeat_text = "Could you please say that again?"
                conversation_log("live.repeat.tts_request", session=session_ref(session_id))
                muted_evt = self._append_event(
                    session_id,
                    "audio.muted",
                    {"muted": True, "reason": "tts_playback"},
                )
                await websocket.send_json(muted_evt)

                speaking_evt = self._append_event(
                    session_id,
                    "audio.speaking",
                    {"phase": "started", "card_id": f"repeat-{uuid4()}"},
                )
                await websocket.send_json(speaking_evt)
                self._speech_sessions.add(session_id)
                self._speech_audio_seen.discard(session_id)
                self._last_spoken_text[session_id] = repeat_text
                await port.send_text(repeat_text)
                conversation_log("live.repeat.tts_sent", session=session_ref(session_id))

            outcomes = await self._command_service.handle(event, session_id=session_id)
            for command_outcome in outcomes:
                emitted = self._append_event(
                    session_id,
                    command_outcome.event_type,
                    command_outcome.payload,
                    correlation_id=command_outcome.correlation_id,
                )
                await websocket.send_json(emitted)

            # Generate and emit summary.render on SessionEndEvent
            if isinstance(event, SessionEndEvent) and self._completion_service is not None:
                conversation_log(
                    "live.session_end.summary.start",
                    session=session_ref(session_id),
                    event_id=event.event_id,
                    reason=event.payload.reason,
                )
                context = TrustedRequestContext(
                    session_id=session_id,
                    user_id=self._user_id or UUID("00000000-0000-4000-8000-000000000001"),
                    origin="runtime",
                )
                try:
                    summary_review = await self._completion_service.prepare_summary(
                        session_id, context
                    )
                    advice_zh = _get_chinese_advice(summary_review.pharmacist_advice_summary)
                    questions_zh = [
                        _get_chinese_question(q) for q in summary_review.unresolved_questions
                    ]

                    summary_payload: dict[str, object] = {
                        "summary_id": f"sum-{uuid4()}",
                        "summary": {
                            "title_zh": "今天药局沟通重点",
                            "mentioned_drugs": list(summary_review.mentioned_drugs),
                            "pharmacist_advice_summary_zh": advice_zh,
                            "unresolved_questions_zh": questions_zh,
                            "follow_up_needed": summary_review.follow_up_needed,
                            "pharmacist_stated_advice_zh": advice_zh,
                            "unresolved_follow_up_questions_zh": questions_zh,
                            "confirmed_family_follow_up": (
                                summary_review.confirmed_family_follow_up
                            ),
                        },
                        "card_set_id": f"cards-summary-{uuid4()}",
                    }
                    summary_event = self._append_event(
                        session_id,
                        "summary.render",
                        summary_payload,
                    )
                    await websocket.send_json(summary_event)
                    conversation_log(
                        "live.session_end.summary.rendered",
                        session=session_ref(session_id),
                        event_id=event.event_id,
                        mentioned_drug_count=len(summary_review.mentioned_drugs),
                        unresolved_count=len(summary_review.unresolved_questions),
                        follow_up_needed=summary_review.follow_up_needed,
                    )
                except Exception as e:
                    logger.warning("Failed to generate visit summary: %s", e)
                    conversation_log(
                        "live.session_end.summary.failed",
                        session=session_ref(session_id),
                        event_id=event.event_id,
                        error=type(e).__name__,
                    )
            return

        if isinstance(event, CardConfirmEvent):
            conversation_log(
                "live.card_confirm.received",
                session=session_ref(session_id),
                event_id=event.event_id,
                confirmation_id=event.payload.confirmation_id,
            )
            if self._user_id is None:
                raise RuntimeError("Missing user ID")
            context = TrustedRequestContext(
                session_id=session_id,
                user_id=self._user_id,
                origin="runtime",
            )
            try:
                card = self._cards.get_card_by_confirmation(
                    event.payload.confirmation_id,
                    context,
                )
                confirmation_outcome = await self._cards.confirm_selected(
                    event.payload.confirmation_id,
                    context,
                )
                conversation_log(
                    "live.card_confirm.resolved",
                    session=session_ref(session_id),
                    event_id=event.event_id,
                    confirmation_id=confirmation_outcome.confirmation_id,
                    card_id=card.card_id,
                    action_type=confirmation_outcome.action_type.value,
                    phase=confirmation_outcome.phase,
                    replayed=confirmation_outcome.replayed,
                    card_en_text=card.en_text,
                    card_zh_text=card.zh_text,
                    card_speak_zh=card.speak_zh,
                )
            except Exception as e:
                logger.warning("Card confirmation failed: %s", e)
                conversation_log(
                    "live.card_confirm.failed",
                    session=session_ref(session_id),
                    event_id=event.event_id,
                    confirmation_id=event.payload.confirmation_id,
                    error=type(e).__name__,
                )

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
                    "confirmation_id": confirmation_outcome.confirmation_id,
                    "action_type": confirmation_outcome.action_type.value,
                    "replayed": confirmation_outcome.replayed,
                },
                correlation_id=event.event_id,
            )
            await websocket.send_json(confirmed)
            conversation_log(
                "live.card_confirm.confirmed_event_sent",
                session=session_ref(session_id),
                event_id=event.event_id,
                confirmation_id=confirmation_outcome.confirmation_id,
                action_type=confirmation_outcome.action_type.value,
                replayed=confirmation_outcome.replayed,
            )

            should_voice_action = confirmation_outcome.action_type in (
                CardActionType.SPEAK,
                CardActionType.SHOW_TO_PHARMACIST,
            )
            if confirmation_outcome.phase == "succeeded" and should_voice_action:
                if self._tts_gateway is not None:
                    await self._speak_confirmed_text(
                        websocket,
                        session_id,
                        text=card.en_text,
                        card_id=card.card_id,
                        confirmation_id=confirmation_outcome.confirmation_id,
                        action_type=confirmation_outcome.action_type,
                        correlation_id=event.event_id,
                    )
                    return
                conversation_log(
                    "live.card_tts.request",
                    session=session_ref(session_id),
                    event_id=event.event_id,
                    confirmation_id=confirmation_outcome.confirmation_id,
                    card_id=card.card_id,
                    action_type=confirmation_outcome.action_type.value,
                    spoken_text=card.en_text,
                )
                muted_evt = self._append_event(
                    session_id,
                    "audio.muted",
                    {"muted": True, "reason": "tts_playback"},
                )
                await websocket.send_json(muted_evt)

                speaking_evt = self._append_event(
                    session_id,
                    "audio.speaking",
                    {"phase": "started", "card_id": card.card_id},
                )
                await websocket.send_json(speaking_evt)
                self._speech_sessions.add(session_id)
                self._speech_audio_seen.discard(session_id)
                self._active_speech_actions[session_id] = (
                    confirmation_outcome.confirmation_id,
                    confirmation_outcome.action_type,
                )
                self._last_spoken_text[session_id] = card.en_text
                started_evt = self._append_event(
                    session_id,
                    "card.action.status",
                    {
                        "confirmation_id": confirmation_outcome.confirmation_id,
                        "action_type": confirmation_outcome.action_type.value,
                        "phase": "started",
                        "code": None,
                    },
                    correlation_id=event.event_id,
                )
                await websocket.send_json(started_evt)
                await port.send_text(card.en_text)
                conversation_log(
                    "live.card_tts.sent_to_provider",
                    session=session_ref(session_id),
                    event_id=event.event_id,
                    confirmation_id=confirmation_outcome.confirmation_id,
                    card_id=card.card_id,
                )
            else:
                conversation_log(
                    "live.card_tts.skipped",
                    session=session_ref(session_id),
                    event_id=event.event_id,
                    confirmation_id=confirmation_outcome.confirmation_id,
                    action_type=confirmation_outcome.action_type.value,
                    phase=confirmation_outcome.phase,
                    should_voice_action=should_voice_action,
                )


def _string_field(event: dict[str, Any], field: str) -> str:
    value = event[field]
    if not isinstance(value, str):
        raise RuntimeError("RUNTIME_EVENT_FIELD_INVALID")
    return value


def _is_provider_thought_text(text: str) -> bool:
    normalized = " ".join(text.strip().split()).lower()
    if not normalized:
        return True
    return normalized.startswith(
        (
            "**analyzing",
            "**awaiting",
            "**interpreting",
            "analyzing the role-play",
            "awaiting further input",
            "interpreting the user's speech",
        )
    )


def _is_identity_request(text: str) -> bool:
    return ("name" in text and "birthday" in text) or (
        "name" in text and "date of birth" in text
    )


def _is_health_disclosure_request(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return any(
        marker in normalized
        for marker in (
            "allergy",
            "allergies",
            "allergic",
            "current medication",
            "current medications",
            "take any medicine",
            "take any medicines",
            "take blood pressure medicine",
            "blood pressure medicine",
        )
    )


def _bundles_medication_and_allergy(text: str) -> bool:
    medication_markers = ("lisinopril", "blood pressure medicine", "medication")
    allergy_markers = ("penicillin", "allergy", "allergic")
    return any(marker in text for marker in medication_markers) and any(
        marker in text for marker in allergy_markers
    )


def _is_meta_card_text(text: str) -> bool:
    normalized = " ".join(text.lower().split())
    return any(
        marker in normalized
        for marker in (
            "the patient is",
            "let kk",
            "ask pharmacist",
            "tell the pharmacist",
            "让 kk",
            "請 kk",
            "请 kk",
        )
    )
