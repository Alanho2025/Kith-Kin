"""In-memory confirmation repository used by the local runtime."""

from threading import Lock
from uuid import UUID

from app.domain.confirmation import StoredConfirmation


class InMemoryConfirmationRepository:
    """Store confirmation rows with process-local locking."""

    def __init__(self) -> None:
        self._records: dict[str, StoredConfirmation] = {}
        self._lock = Lock()

    def add(self, record: StoredConfirmation) -> None:
        with self._lock:
            self._records[record.confirmation_id] = record

    def get(self, confirmation_id: str) -> StoredConfirmation | None:
        with self._lock:
            return self._records.get(confirmation_id)

    def update(self, record: StoredConfirmation) -> None:
        with self._lock:
            self._records[record.confirmation_id] = record

    def find_pending_by_session(self, session_id: UUID) -> list[StoredConfirmation]:
        with self._lock:
            return [
                record
                for record in self._records.values()
                if record.session_id == session_id and record.state == "pending"
            ]
