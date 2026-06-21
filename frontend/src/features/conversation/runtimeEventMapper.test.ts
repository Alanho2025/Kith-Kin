import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { mapRuntimeEvent } from "./mappers/runtimeEventMapper";


describe("mapRuntimeEvent", () => {
  it("maps the canonical shared transcript fixture", () => {
    const fixture = JSON.parse(
      readFileSync(
        resolve(process.cwd(), "../specs/fixtures/runtime/transcript-final.json"),
        "utf8",
      ),
    ) as unknown;

    const event = mapRuntimeEvent(fixture);

    expect(event.eventId).toBe("evt_fixture_001");
    expect(event.payload).not.toBeNull();
    if (event.payload === null) {
      throw new Error("Expected a transcript payload");
    }
    expect(event.payload.utteranceId).toBe("utt_fixture_001");
  });

  it("maps a snake_case transcript event to a camelCase view event", () => {
    const event = mapRuntimeEvent({
      schema_version: "0.1",
      event_id: "evt-1",
      event_type: "transcript.final",
      session_id: "session-1",
      sequence: 1,
      timestamp: "2026-06-22T00:00:00Z",
      correlation_id: null,
      payload: {
        utterance_id: "utterance-1",
        speaker: "pharmacist",
        language: "en",
        text: "Do you have allergies?",
        revision: 1,
      },
    });

    expect(event).toEqual({
      schemaVersion: "0.1",
      eventId: "evt-1",
      eventType: "transcript.final",
      sessionId: "session-1",
      sequence: 1,
      timestamp: "2026-06-22T00:00:00Z",
      correlationId: null,
      payload: {
        utteranceId: "utterance-1",
        speaker: "pharmacist",
        language: "en",
        text: "Do you have allergies?",
        revision: 1,
      },
    });
  });

  it("rejects a malformed known event", () => {
    expect(() =>
      mapRuntimeEvent({
        schema_version: "0.1",
        event_id: "evt-1",
        event_type: "transcript.final",
        session_id: "session-1",
        sequence: 1,
        timestamp: "2026-06-22T00:00:00Z",
        correlation_id: null,
        payload: { text: "missing required fields" },
      }),
    ).toThrow();
  });

  it("preserves sequence metadata and drops payload for an unknown minor event", () => {
    const event = mapRuntimeEvent({
      schema_version: "0.2",
      event_id: "evt-future",
      event_type: "future.event",
      session_id: "session-1",
      sequence: 2,
      timestamp: "2026-06-22T00:00:01Z",
      correlation_id: null,
      payload: { provider_debug: "must not reach components" },
    });

    expect(event).toEqual({
      schemaVersion: "0.2",
      eventId: "evt-future",
      eventType: "future.event",
      sessionId: "session-1",
      sequence: 2,
      timestamp: "2026-06-22T00:00:01Z",
      correlationId: null,
      payload: null,
    });
  });
});
