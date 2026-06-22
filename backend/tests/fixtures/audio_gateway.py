class RecordingEventSink:
    def __init__(self, *, fail_audio: bool = False) -> None:
        self.items: list[tuple[str, object]] = []
        self.fail_audio = fail_audio

    async def send_event(self, event_type: str, payload: dict[str, object]) -> None:
        self.items.append((event_type, payload))

    async def send_audio(self, frame: bytes) -> None:
        if self.fail_audio:
            raise RuntimeError("tts failed")
        self.items.append(("audio.frame", frame))
