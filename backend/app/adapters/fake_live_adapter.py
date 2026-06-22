class FakeLiveAdapter:
    async def echo_audio(self, frame: bytes) -> bytes:
        return frame
