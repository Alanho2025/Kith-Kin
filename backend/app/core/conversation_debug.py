"""Privacy-conscious conversation diagnostics for local runtime debugging."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager

LOGGER_NAME = "app.conversation"

_logger = logging.getLogger(LOGGER_NAME)
_observers: list[Callable[[str, object], None]] = []

_SENSITIVE_KEY_RE = re.compile(
    r"(ticket|token|cookie|authorization|secret|api[_-]?key|encoded|password)",
    re.IGNORECASE,
)
_TEXT_KEY_RE = re.compile(
    r"(^text$|_text$|text_|query|transcript|utterance|spoken|message|summary|advice|question)",
    re.IGNORECASE,
)
_DATE_LIKE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")


def configure_conversation_logging(level_name: str = "INFO") -> None:
    """Ensure conversation diagnostics are visible when the backend starts."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(levelname)s:%(name)s:%(message)s",
    )
    _logger.setLevel(level)


def session_ref(value: object) -> str:
    """Return a short stable reference that can correlate logs without full IDs."""
    text = str(value)
    return text[:8] if text else ""


def text_fingerprint(text: str, *, preview_chars: int = 96) -> dict[str, object]:
    """Summarise user/model text without logging the full sensitive payload."""
    normalized = " ".join(text.split())
    preview = _DATE_LIKE_RE.sub("[date]", normalized[:preview_chars])
    return {
        "chars": len(text),
        "sha256_12": hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
        "preview": preview,
    }


def conversation_log(label: str, **fields: object) -> None:
    """Emit one redacted structured backend conversation diagnostic line."""
    payload = _safe_value(fields)
    for observer in tuple(_observers):
        observer(label, payload)
    if not _logger.isEnabledFor(logging.INFO):
        return
    _logger.info(
        "[KK conversation backend] %s %s",
        label,
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    )


@contextmanager
def observe_conversation_logs(observer: Callable[[str, object], None]) -> Iterator[None]:
    """Register an in-process observer for deterministic tests."""
    _observers.append(observer)
    try:
        yield
    finally:
        _observers.remove(observer)


def _safe_value(value: object, *, key: str = "", depth: int = 0) -> object:
    if depth > 6:
        return "[depth-limit]"
    if _SENSITIVE_KEY_RE.search(key):
        return "[redacted]"
    if isinstance(value, str):
        if _TEXT_KEY_RE.search(key):
            return text_fingerprint(value)
        return value
    if isinstance(value, bytes | bytearray | memoryview):
        return {"byte_length": len(value)}
    if isinstance(value, Mapping):
        return {
            str(child_key): _safe_value(child_value, key=str(child_key), depth=depth + 1)
            for child_key, child_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_safe_value(item, key=key, depth=depth + 1) for item in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return enum_value
    return str(value)
