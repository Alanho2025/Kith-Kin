import json
from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.adapters.fake_live_adapter import FakeLiveAdapter
from app.core.constants import SCHEMA_VERSION
from app.schemas.runtime_events import CardConfirmEvent, parse_runtime_event
from app.services.card_service import CardService


class LiveRuntimeService:
    MAX_BUFFERED_EVENTS = 64

    def __init__(
        self,
        card_service: CardService,
        fake_live: FakeLiveAdapter,
        clock: Callable[[], datetime],
    ) -> None:
        self._cards = card_service
        self._fake_live = fake_live
        self._clock = clock
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
        if not isinstance(event, CardConfirmEvent):
            return
        result = self._cards.confirm(event.payload.confirmation_id)
        buffer = self._buffers[session_id]
        confirmed = self._event(
            session_id,
            self._sequence(buffer[-1]) + 1,
            "card.confirmed",
            {
                "confirmation_id": result.confirmation_id,
                "action_type": "speak",
                "replayed": result.replayed,
            },
            correlation_id=event.event_id,
        )
        buffer.append(confirmed)
        if len(buffer) > self.MAX_BUFFERED_EVENTS:
            del buffer[: -self.MAX_BUFFERED_EVENTS]
        await websocket.send_json(confirmed)

    @staticmethod
    def _sequence(event: dict[str, object]) -> int:
        sequence = event["sequence"]
        if not isinstance(sequence, int):
            raise RuntimeError("RUNTIME_SEQUENCE_INVALID")
        return sequence

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
