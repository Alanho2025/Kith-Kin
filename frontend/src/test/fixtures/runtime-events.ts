export function makeEvent(
  eventType: string,
  eventId: string,
  payload: object,
) {
  return {
    schemaVersion: "0.1",
    eventId,
    eventType,
    sessionId: "ses-test",
    sequence: 1,
    timestamp: "2026-06-22T00:00:00Z",
    correlationId: null,
    payload,
  };
}
