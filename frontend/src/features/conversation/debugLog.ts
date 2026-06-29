import type {
  ConversationRuntimeEvent,
  ConversationState,
  RuntimeCommandView,
} from "./viewModels";

const REDACTED = "[redacted]";

function isDebugEnabled(): boolean {
  const viteDebug = import.meta.env.DEV && import.meta.env.MODE !== "test";
  if (typeof window === "undefined") return viteDebug;
  try {
    const flag = window.localStorage.getItem("kk_debug_conversation");
    if (flag === "0" || flag === "false") return false;
    if (flag === "1" || flag === "true") return true;
  } catch {
    // localStorage may be blocked; keep the dev default.
  }
  return viteDebug;
}

function isSensitiveKey(key: string): boolean {
  return /ticket|token|cookie|authorization|secret|api[_-]?key|encoded/i.test(key);
}

function sanitize(value: unknown, depth = 0): unknown {
  if (depth > 6) return "[depth-limit]";
  if (value instanceof ArrayBuffer) return { byteLength: value.byteLength };
  if (ArrayBuffer.isView(value)) return { byteLength: value.byteLength };
  if (typeof Blob !== "undefined" && value instanceof Blob) {
    return { blobSize: value.size, blobType: value.type };
  }
  if (Array.isArray(value)) return value.map((item) => sanitize(item, depth + 1));
  if (typeof value !== "object" || value === null) return value;

  return Object.fromEntries(
    Object.entries(value).map(([key, entry]) => [
      key,
      isSensitiveKey(key) ? REDACTED : sanitize(entry, depth + 1),
    ]),
  );
}

export function summarizeRuntimeEvent(event: ConversationRuntimeEvent) {
  return sanitize({
    eventType: event.eventType,
    eventId: event.eventId,
    sequence: event.sequence,
    correlationId: event.correlationId,
    payload: event.payload,
  });
}

export function summarizeCommand(command: RuntimeCommandView) {
  return sanitize({
    eventType: command.eventType,
    payload: command.payload,
  });
}

export function summarizeState(state: ConversationState) {
  return sanitize({
    status: state.status,
    partialEnglish: state.partialEnglish,
    turns: state.turns.map((turn) => ({
      speaker: turn.speaker,
      sourceText: turn.sourceText,
      translatedText: turn.translatedText,
    })),
    chineseSegments: state.chineseSegments.map((segment) => ({
      segmentId: segment.segmentId,
      translatedText: segment.translatedText,
    })),
    activeCardSet: state.activeCardSet,
    productOptions: state.productOptions,
    confirmation: state.confirmation,
    guardianWarning: state.guardianWarning,
    visibleError: state.visibleError,
    summary: state.summary,
  });
}

export function conversationDebug(label: string, details?: unknown): void {
  if (!isDebugEnabled()) return;
  const payload = details === undefined ? undefined : sanitize(details);
  console.log(`[KK conversation] ${label}`, payload ?? "");
}
