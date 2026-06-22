from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class MutableClock:
    current: datetime = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, *, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)
