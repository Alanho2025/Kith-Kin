export type ConversationStatus =
  | "idle"
  | "listening"
  | "transcribing"
  | "translating"
  | "checking"
  | "needs_confirmation"
  | "speaking"
  | "blocked"
  | "error"
  | "reconnecting"
  | "ended";

export interface TranslationSegmentView {
  segmentId: string;
  sourceTranscriptEventId?: string;
  translatedText: string;
}

export interface ConversationTurnView {
  utteranceId: string;
  transcriptEventId: string;
  speaker: "parent" | "pharmacist" | "unknown";
  sourceText: string;
  translatedText: string | null;
}

export type CardRiskLevelView = "normal" | "caution" | "privacy" | "medical" | "urgent";
export type CardActionTypeView =
  | "speak"
  | "show_to_pharmacist"
  | "save_memory"
  | "notify_family"
  | "no_action";

export interface ResponseCardView {
  cardId: string;
  zhText: string;
  enText: string;
  riskLevel: CardRiskLevelView;
  actionType: CardActionTypeView;
}

export interface CardSetView {
  cardSetId: string;
  revision: number;
  cards: readonly ResponseCardView[];
}

export interface ConfirmationView {
  confirmationId: string;
  cardSetId: string;
  card: ResponseCardView;
}

export interface GuardianWarningView {
  warningId: string;
  type: "privacy" | "payment" | "identity" | "medical" | "family" | "unknown";
  zhTitle: string;
  zhMessage: string;
}

export interface SafeRuntimeMessageView {
  code: string;
  messageZh: string;
  messageEn: string;
  retryable: boolean;
  recoveryAction: string;
  relatedEventId: string | null;
}

export interface VisitSummaryView {
  titleZh: string;
  mentionedDrugs: readonly string[];
  pharmacistAdviceSummaryZh: string;
  unresolvedQuestionsZh: readonly string[];
  followUpNeeded: boolean;
}

export interface ConversationState {
  status: ConversationStatus;
  partialEnglish: string;
  turns: readonly ConversationTurnView[];
  chineseSegments: readonly TranslationSegmentView[];
  activeCardSet: CardSetView | null;
  confirmation: ConfirmationView | null;
  guardianWarning: GuardianWarningView | null;
  visibleError: SafeRuntimeMessageView | null;
  summary: VisitSummaryView | null;
  seenEventIds: ReadonlySet<string>;
  activeUtteranceId: string | null;
}

export interface ConversationRuntimeEvent {
  schemaVersion: string;
  eventId: string;
  eventType: string;
  sessionId: string;
  sequence: number;
  timestamp: string;
  correlationId: string | null;
  payload: unknown;
}

export type RuntimeCommandView =
  | {
      eventType: "card.select";
      payload: { cardSetId: string; cardId: string; revision: number };
    }
  | { eventType: "card.confirm"; payload: { confirmationId: string } }
  | { eventType: "card.cancel"; payload: { confirmationId: string } }
  | { eventType: "control.self_speak"; payload: Record<string, never> }
  | { eventType: "control.please_wait"; payload: Record<string, never> }
  | { eventType: "control.repeat"; payload: { target: "last_translation" } }
  | {
      eventType: "session.end";
      payload: { reason: "user_completed" | "user_cancelled" };
    }
  | {
      eventType: "transcript.final";
      payload: {
        utteranceId: string;
        speaker: "parent" | "pharmacist" | "unknown";
        language: "en" | "zh" | "unknown";
        text: string;
        revision: number;
      };
    };
