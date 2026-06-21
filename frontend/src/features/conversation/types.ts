export type TranscriptSpeaker = "parent" | "pharmacist" | "unknown";
export type TranscriptLanguage = "en" | "zh" | "unknown";

export interface TranscriptPayloadView {
  utteranceId: string;
  speaker: TranscriptSpeaker;
  language: TranscriptLanguage;
  text: string;
  revision: number;
}

export interface TranscriptFinalViewEvent {
  schemaVersion: string;
  eventId: string;
  eventType: "transcript.final";
  sessionId: string;
  sequence: number;
  timestamp: string;
  correlationId: string | null;
  payload: TranscriptPayloadView;
}

export interface UnknownRuntimeViewEvent {
  schemaVersion: string;
  eventId: string;
  eventType: string;
  sessionId: string;
  sequence: number;
  timestamp: string;
  correlationId: string | null;
  payload: null;
}

export type RuntimeViewEvent = TranscriptFinalViewEvent | UnknownRuntimeViewEvent;
