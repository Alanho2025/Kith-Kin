import type {
  CardSetView,
  ConfirmationView,
  ConversationRuntimeEvent,
  ConversationState,
  GuardianWarningView,
  SafeRuntimeMessageView,
  TranslationSegmentView,
  VisitSummaryView,
} from "./viewModels";


export const initialConversationState: ConversationState = {
  status: "idle",
  partialEnglish: "",
  turns: [],
  chineseSegments: [],
  activeCardSet: null,
  confirmation: null,
  guardianWarning: null,
  visibleError: null,
  summary: null,
  seenEventIds: new Set<string>(),
};

export type ConversationAction =
  | ConversationRuntimeEvent
  | { type: "dismiss_confirmation" };

function recordEvent(
  state: ConversationState,
  event: ConversationRuntimeEvent,
  changes: Partial<ConversationState>,
): ConversationState {
  const seenEventIds = new Set(state.seenEventIds);
  seenEventIds.add(event.eventId);
  return { ...state, ...changes, seenEventIds };
}

export function conversationReducer(
  state: ConversationState,
  event: ConversationAction,
): ConversationState {
  if ("type" in event) {
    return { ...state, status: "listening", confirmation: null };
  }
  if (state.seenEventIds.has(event.eventId)) {
    return state;
  }

  switch (event.eventType) {
    case "session.ready":
      return recordEvent(state, event, { status: "idle", visibleError: null });
    case "audio.listening": {
      const payload = event.payload as { active: boolean };
      return recordEvent(state, event, { status: payload.active ? "listening" : "idle" });
    }
    case "transcript.partial":
    case "transcript.final": {
      const payload = event.payload as {
        utteranceId?: string;
        speaker?: "parent" | "pharmacist" | "unknown";
        text: string;
      };
      const turns = event.eventType === "transcript.final"
        ? [
            ...state.turns,
            {
              utteranceId: payload.utteranceId ?? event.eventId,
              transcriptEventId: event.eventId,
              speaker: payload.speaker ?? "unknown",
              sourceText: payload.text,
              translatedText: null,
            },
          ]
        : state.turns;
      return recordEvent(state, event, {
        status: event.eventType === "transcript.partial" ? "transcribing" : "translating",
        partialEnglish: payload.text,
        turns,
      });
    }
    case "translation.pending":
      return recordEvent(state, event, { status: "translating" });
    case "translation.final": {
      const payload = event.payload as TranslationSegmentView;
      const exists = state.chineseSegments.some(
        (segment) => segment.segmentId === payload.segmentId,
      );
      const turns = state.turns.map((turn) =>
        turn.transcriptEventId === payload.sourceTranscriptEventId
          ? { ...turn, translatedText: payload.translatedText }
          : turn,
      );
      return recordEvent(state, event, {
        status: "listening",
        turns,
        chineseSegments: exists ? state.chineseSegments : [...state.chineseSegments, payload],
      });
    }
    case "route.decision":
    case "tool.status":
      return recordEvent(state, event, { status: "checking" });
    case "cards.render": {
      const payload = event.payload as { cardSet: any };
      const cardSet = payload.cardSet ? {
        ...payload.cardSet,
        cards: (payload.cardSet.cards || []).map((card: any) => ({
          ...card,
          actionType: card.actionType || card.action?.type || "no_action",
        })),
      } : null;
      return recordEvent(state, event, { activeCardSet: cardSet });
    }
    case "card.selected": {
      const payload = event.payload as {
        cardSetId: string;
        cardId: string;
        confirmationId: string;
      };
      let card = state.activeCardSet?.cards.find(
        (candidate) => candidate.cardId === payload.cardId,
      );
      if (card) {
        card = {
          ...card,
          actionType: card.actionType || (card as any).action?.type || "no_action",
        };
      }
      const confirmation: ConfirmationView | null = card
        ? {
            confirmationId: payload.confirmationId,
            cardSetId: payload.cardSetId,
            card,
          }
        : null;
      return recordEvent(state, event, { status: "needs_confirmation", confirmation });
    }
    case "card.confirmed":
    case "audio.speaking":
      return recordEvent(state, event, { status: "speaking", confirmation: null });
    case "guardian.warning":
      return recordEvent(state, event, {
        status: "blocked",
        guardianWarning: event.payload as GuardianWarningView,
      });
    case "fallback.show":
    case "error.show":
      return recordEvent(state, event, {
        status: "error",
        visibleError: event.payload as SafeRuntimeMessageView,
      });
    case "summary.render": {
      const payload = event.payload as { summary: VisitSummaryView };
      return recordEvent(state, event, { summary: payload.summary });
    }
    case "session.ended":
      return recordEvent(state, event, { status: "ended" });
    default:
      return recordEvent(state, event, {});
  }
}
