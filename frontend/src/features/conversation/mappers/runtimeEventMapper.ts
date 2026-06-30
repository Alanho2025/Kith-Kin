import { z } from "zod";

import type { RuntimeViewEvent } from "../types";

const runtimeEnvelopeSchema = z
  .object({
    schema_version: z.string().regex(/^0\.[0-9]+$/),
    event_id: z.string().min(1).max(80),
    event_type: z.string().min(1).max(80),
    session_id: z.string().min(1).max(80),
    sequence: z.number().int().positive(),
    timestamp: z.iso.datetime(),
    correlation_id: z.string().max(80).nullable(),
    payload: z.record(z.string(), z.unknown()),
  })
  .strict();

const transcriptFinalWireSchema = z
  .object({
    schema_version: z.string().regex(/^0\.[0-9]+$/),
    event_id: z.string().min(1).max(80),
    event_type: z.literal("transcript.final"),
    session_id: z.string().min(1).max(80),
    sequence: z.number().int().positive(),
    timestamp: z.iso.datetime(),
    correlation_id: z.string().max(80).nullable(),
    payload: z
      .object({
        utterance_id: z.string().min(1).max(80),
        speaker: z.enum(["parent", "pharmacist", "unknown"]),
        language: z.enum(["en", "zh", "unknown"]),
        text: z.string().min(1),
        revision: z.number().int().positive(),
      })
      .strict(),
  })
  .strict();

const KNOWN_RUNTIME_EVENTS = new Set([
  "session.ready",
  "audio.listening",
  "audio.muted",
  "audio.speaking",
  "transcript.partial",
  "transcript.final",
  "translation.pending",
  "translation.final",
  "route.decision",
  "tool.status",
  "guardian.warning",
  "cards.render",
  "product.options.render",
  "card.selected",
  "card.confirmed",
  "card.action.status",
  "summary.render",
  "memory.write.status",
  "notification.status",
  "fallback.show",
  "error.show",
  "session.ended",
]);

export function mapRuntimeEvent(input: unknown): RuntimeViewEvent {
  const envelope = runtimeEnvelopeSchema.parse(input);
  if (envelope.event_type !== "transcript.final") {
    return {
      schemaVersion: envelope.schema_version,
      eventId: envelope.event_id,
      eventType: envelope.event_type,
      sessionId: envelope.session_id,
      sequence: envelope.sequence,
      timestamp: envelope.timestamp,
      correlationId: envelope.correlation_id,
      payload: KNOWN_RUNTIME_EVENTS.has(envelope.event_type) ? envelope.payload : null,
    };
  }
  const event = transcriptFinalWireSchema.parse(input);

  return {
    schemaVersion: event.schema_version,
    eventId: event.event_id,
    eventType: event.event_type,
    sessionId: event.session_id,
    sequence: event.sequence,
    timestamp: event.timestamp,
    correlationId: event.correlation_id,
    payload: {
      utteranceId: event.payload.utterance_id,
      speaker: event.payload.speaker,
      language: event.payload.language,
      text: event.payload.text,
      revision: event.payload.revision,
    },
  };
}
