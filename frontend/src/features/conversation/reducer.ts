import type {
  CardActionTypeView,
  CardRiskLevelView,
  CardSetView,
  ConfirmationView,
  ConversationRuntimeEvent,
  ConversationState,
  GuardianWarningView,
  ProductOptionView,
  ResponseCardView,
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
  productOptions: [],
  confirmation: null,
  guardianWarning: null,
  visibleError: null,
  summary: null,
  seenEventIds: new Set<string>(),
  activeUtteranceId: null,
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

interface RawCard {
  card_id?: string;
  cardId?: string;
  zh_text?: string;
  zhText?: string;
  en_text?: string;
  enText?: string;
  speak_zh?: string;
  speakZh?: string;
  risk_level?: string;
  riskLevel?: string;
  action_type?: string;
  actionType?: string;
  action?: { type?: string };
}


interface RawCardSet {
  card_set_id?: string;
  cardSetId?: string;
  revision?: number;
  cards?: RawCard[];
}

interface RawProductOption {
  name?: string;
  price?: string | null;
  pharmacist_stated_use?: string | null;
  pharmacistStatedUse?: string | null;
  pharmacist_stated_directions?: string | null;
  pharmacistStatedDirections?: string | null;
  pharmacist_stated_cautions?: string | null;
  pharmacistStatedCautions?: string | null;
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
      const isPharmacist = payload.speaker === "pharmacist";
      return recordEvent(state, event, {
        status: event.eventType === "transcript.partial" ? "transcribing" : "translating",
        partialEnglish: payload.text,
        turns,
        confirmation: isPharmacist ? null : state.confirmation,
      });
    }
    case "translation.pending":
      return recordEvent(state, event, { status: "translating" });
    case "translation.final": {
      const payload = event.payload as TranslationSegmentView;
      const isNew = state.activeUtteranceId !== payload.sourceTranscriptEventId;
      const exists = state.chineseSegments.some(
        (segment) => segment.segmentId === payload.segmentId,
      );
      const turns = state.turns.map((turn) =>
        turn.transcriptEventId === payload.sourceTranscriptEventId
          ? { ...turn, translatedText: payload.translatedText }
          : turn,
      );
      const nextSegments = isNew
        ? [payload]
        : exists
        ? state.chineseSegments
        : [...state.chineseSegments, payload];

      return recordEvent(state, event, {
        status: "listening",
        turns,
        chineseSegments: nextSegments,
        activeUtteranceId: payload.sourceTranscriptEventId ?? null,
      });
    }
    case "route.decision":
    case "tool.status":
      return recordEvent(state, event, { status: "checking" });
    case "cards.render": {
      const payload = event.payload as { cardSet: RawCardSet | null };
      const rawCardSet = payload.cardSet;
      const cardSet: CardSetView | null = rawCardSet ? {
        cardSetId: rawCardSet.cardSetId || rawCardSet.card_set_id || "",
        revision: rawCardSet.revision || 1,
        cards: (rawCardSet.cards || []).map((card): ResponseCardView => {
          const rawActionType = card.actionType || card.action_type || card.action?.type || "no_action";
          const actionType: CardActionTypeView =
            rawActionType === "speak" ||
            rawActionType === "show_to_pharmacist" ||
            rawActionType === "save_memory" ||
            rawActionType === "notify_family" ||
            rawActionType === "no_action"
              ? rawActionType
              : "no_action";

          return {
            cardId: card.cardId || card.card_id || "",
            zhText: card.zhText || card.zh_text || "",
            enText: card.enText || card.en_text || "",
            speakZh: card.speakZh || card.speak_zh || undefined,
            riskLevel: (card.riskLevel || card.risk_level || "low") as CardRiskLevelView,
            actionType,
          };

        }),
      } : null;
      return recordEvent(state, event, { activeCardSet: cardSet });
    }
    case "product.options.render": {
      const payload = event.payload as { options?: RawProductOption[] };
      const productOptions: ProductOptionView[] = (payload.options || []).map((option) => ({
        name: option.name || "",
        price: option.price ?? null,
        pharmacistStatedUse:
          option.pharmacistStatedUse ?? option.pharmacist_stated_use ?? null,
        pharmacistStatedDirections:
          option.pharmacistStatedDirections ?? option.pharmacist_stated_directions ?? null,
        pharmacistStatedCautions:
          option.pharmacistStatedCautions ?? option.pharmacist_stated_cautions ?? null,
      }));
      return recordEvent(state, event, { productOptions });
    }
    case "card.selected": {
      const payload = event.payload as {
        cardSetId: string;
        cardId: string;
        confirmationId: string;
      };
      const card = state.activeCardSet?.cards.find(
        (candidate) => candidate.cardId === payload.cardId,
      );
      const confirmation: ConfirmationView | null = card
        ? {
            confirmationId: payload.confirmationId,
            cardSetId: payload.cardSetId,
            card,
          }
        : null;
      return recordEvent(state, event, { status: "needs_confirmation", confirmation });
    }
    case "card.confirmed": {
      const confirmedCard = state.confirmation?.card;
      const turns = confirmedCard
        ? [
            ...state.turns,
            {
              utteranceId: `card-${event.eventId}`,
              transcriptEventId: event.eventId,
              speaker: "kk" as const,
              sourceText: confirmedCard.enText,
              translatedText: confirmedCard.speakZh || confirmedCard.zhText,
            },
          ]

        : state.turns;
      return recordEvent(state, event, { status: "speaking", confirmation: null, turns });
    }
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
