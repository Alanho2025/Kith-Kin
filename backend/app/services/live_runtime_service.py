import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any
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
    TranslationRequest,
)
from app.core.constants import SCHEMA_VERSION, GuardianDecisionType
from app.domain.credentials import TrustedRequestContext
from app.schemas.runtime_events import (
    CardConfirmEvent,
    TranscriptFinalEvent,
    parse_runtime_event,
)
from app.services.card_service import CardService
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
    if "nurofen" in lower or "ibuprofen" in lower:
        return (
            "药剂师建议不要服用 Nurofen (布洛芬)，因为这与降血压药 Perindopril (培哚普利) "
            "存在药物相互作用，有肾脏风险。建议使用 Panadol 代替。"
        )
    if "voltaren" in lower or "diclofenac" in lower:
        return (
            "药剂师警告说 Voltaren (双氯芬酸) 与 Warfarin (华法林) 同服会使出血风险翻倍。"
            "强烈建议使用 Panadol 代替。"
        )
    if "codral" in lower or "pseudoephedrine" in lower:
        return "药剂师警告说 Codral (伪麻黄碱) 会升高血压。建议使用生理盐水鼻喷雾剂。"
    if "grapefruit" in lower:
        return "药剂师建议限制或避免食用葡萄柚，因为它会影响 Lipitor (阿托伐他汀) 的代谢。"
    if "coenzyme q10" in lower or "coq10" in lower:
        return "药剂师建议服用辅酶 Q10 补充剂以缓解肌肉酸痛。"
    if "routine" in lower:
        return "常规就诊已完成。"
    return en_text


def _get_chinese_question(en_q: str) -> str:
    lower = en_q.lower()
    if "coenzyme q10" in lower or "coq10" in lower:
        return "我应该开始服用辅酶 Q10 来缓解肌肉酸痛吗？"
    if "interacts" in lower or "interaction" in lower:
        return "确认药物是否存在相互作用。"
    return en_q



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
        self._settings = settings
        self._completion_service = completion_service
        self._buffers: dict[UUID, list[dict[str, object]]] = {}
        self._speech_sessions: set[UUID] = set()
        self._paused_sessions: set[UUID] = set()
        self._last_spoken_text: dict[UUID, str] = {}


    def discard_session(self, session_id: UUID) -> None:
        self._buffers.pop(session_id, None)
        self._speech_sessions.discard(session_id)
        self._paused_sessions.discard(session_id)
        self._last_spoken_text.pop(session_id, None)

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
        events = (
            buffer
            if last_seen_sequence is None
            else [event for event in buffer if self._sequence(event) > last_seen_sequence]
        )
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
            from app.schemas.runtime_events import (
                PleaseWaitEvent,
                RepeatEvent,
                SelfSpeakEvent,
                SessionEndEvent,
            )

            if isinstance(event, PleaseWaitEvent):
                self._paused_sessions.add(session_id)
            elif isinstance(event, SelfSpeakEvent):
                self._paused_sessions.discard(session_id)
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
        try:
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
                    break
                frame = message.get("bytes")
                if isinstance(frame, bytes):
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
                    continue
                if not model_speaking:
                    model_speaking = True
                    muted_evt = self._append_event(
                        session_id,
                        "audio.muted",
                        {"muted": True, "reason": "tts_playback"},
                    )
                    await websocket.send_json(muted_evt)

                    speaking_evt = self._append_event(
                        session_id,
                        "audio.speaking",
                        {"phase": "started"},
                    )
                    await websocket.send_json(speaking_evt)
                await websocket.send_bytes(event.audio)
            elif isinstance(event, ProviderTranscriptEvent):
                if session_id in self._paused_sessions:
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
                    if model_speaking or session_id in self._speech_sessions:
                        model_speaking = False
                        self._speech_sessions.discard(session_id)
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
                else:
                    outcomes = await self.handle_provider_event(session_id, event)
                    for out in outcomes:
                        await websocket.send_json(out)
                    is_final = event.event_type == ProviderLiveEventType.TRANSCRIPT_FINAL
                    if is_final and model_speaking:
                        model_speaking = False
                        self._speech_sessions.discard(session_id)
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
                outcomes = await self.handle_provider_event(session_id, event)
                for out in outcomes:
                    await websocket.send_json(out)

    async def _handle_live_command(
        self, websocket: WebSocket, session_id: UUID, text: str, port: Any
    ) -> None:
        try:
            event = parse_runtime_event(json.loads(text))
        except (ValueError, json.JSONDecodeError):
            return

        if isinstance(event, TranscriptFinalEvent):
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
            from app.schemas.runtime_events import (
                PleaseWaitEvent,
                RepeatEvent,
                SelfSpeakEvent,
                SessionEndEvent,
            )

            if isinstance(event, PleaseWaitEvent):
                self._paused_sessions.add(session_id)
            elif isinstance(event, SelfSpeakEvent):
                self._paused_sessions.discard(session_id)
            elif isinstance(event, RepeatEvent):
                self._paused_sessions.discard(session_id)
                last_text = self._last_spoken_text.get(session_id)
                if last_text:
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
                    await port.send_text(last_text)

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
                    logger.warning("Failed to generate visit summary: %s", e)
            return


        if isinstance(event, CardConfirmEvent):
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
            except Exception as e:
                logger.warning("Card confirmation failed: %s", e)
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
                    "confirmation_id": confirmation_outcome.confirmation_id,
                    "action_type": confirmation_outcome.action_type.value,
                    "replayed": confirmation_outcome.replayed,
                },
                correlation_id=event.event_id,
            )
            await websocket.send_json(confirmed)

            should_voice_action = confirmation_outcome.action_type.value in (
                "speak",
                "notify_family",
                "save_memory",
            )
            if confirmation_outcome.phase == "succeeded" or should_voice_action:
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
                self._last_spoken_text[session_id] = card.en_text
                await port.send_text(card.en_text)


def _string_field(event: dict[str, Any], field: str) -> str:
    value = event[field]
    if not isinstance(value, str):
        raise RuntimeError("RUNTIME_EVENT_FIELD_INVALID")
    return value
