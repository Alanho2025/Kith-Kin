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
    if (
      event.payload === null ||
      typeof event.payload !== "object" ||
      !("utteranceId" in event.payload)
    ) {
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

  it.each([
    {
      eventType: "translation.final",
      payload: {
        source_transcript_event_id: "evt-transcript-1",
        segment_id: "seg-1",
        translated_text: "您有任何过敏吗？",
      },
    },
    {
      eventType: "cards.render",
      payload: {
        card_set: {
          card_set_id: "cards-1",
          revision: 1,
          cards: [],
        },
      },
    },
    {
      eventType: "guardian.warning",
      payload: {
        guardian_decision_id: "guardian-1",
        decision: "block",
      },
    },
    {
      eventType: "product.options.render",
      payload: {
        options: [{ name: "Panadol", price: "8 dollars" }],
      },
    },
    {
      eventType: "summary.render",
      payload: {
        summary_id: "summary-1",
        summary: { title_zh: "今天药局沟通重点" },
      },
    },
  ])("preserves payload for known runtime event $eventType", ({ eventType, payload }) => {
    const event = mapRuntimeEvent({
      schema_version: "0.1",
      event_id: `evt-${eventType}`,
      event_type: eventType,
      session_id: "session-1",
      sequence: 2,
      timestamp: "2026-06-22T00:00:01Z",
      correlation_id: null,
      payload,
    });

    expect(event.payload).toEqual(payload);
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
