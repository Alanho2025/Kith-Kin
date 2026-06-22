from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class ConfirmationResult:
    confirmation_id: str
    replayed: bool


class CardService:
    def __init__(self) -> None:
        self._confirmed: set[str] = set()
        self._lock = Lock()

    def confirm(self, confirmation_id: str) -> ConfirmationResult:
        with self._lock:
            replayed = confirmation_id in self._confirmed
            self._confirmed.add(confirmation_id)
        return ConfirmationResult(confirmation_id=confirmation_id, replayed=replayed)
