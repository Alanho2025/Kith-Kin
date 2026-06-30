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
  actions: [],
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

function actionTypeView(value: unknown): CardActionTypeView | null {
  return value === "speak" ||
    value === "show_to_pharmacist" ||
    value === "save_memory" ||
    value === "notify_family" ||
    value === "no_action"
    ? value
    : null;
}

function riskLevelView(value: unknown): CardRiskLevelView {
  return value === "normal" ||
    value === "caution" ||
    value === "privacy" ||
    value === "medical" ||
    value === "urgent"
    ? value
    : "normal";
}

function recordEvent(
  state: ConversationState,
  event: ConversationRuntimeEvent,
  changes: Partial<ConversationState>,
): ConversationState {
  // Runtime events may be replayed after reconnect; track event IDs so reducers
  // stay idempotent across resume and duplicate socket delivery.
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
    // Local dismiss updates the confirmation UI immediately while recording the
    // same action shape used by server card events.
    const action = state.confirmation
      ? {
          eventId: `local-dismiss-${state.confirmation.confirmationId}`,
          eventType: "card.cancel",
          timestamp: "",
          confirmationId: state.confirmation.confirmationId,
          cardSetId: state.confirmation.cardSetId,
          cardId: state.confirmation.card.cardId,
          actionType: state.confirmation.card.actionType,
          phase: "cancelled",
          replayed: null,
        }
      : null;
    return {
      ...state,
      status: "listening",
      confirmation: null,
      actions: action ? [...state.actions, action] : state.actions,
    };
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
      // Partials update the live subtitle; finals append immutable turns that
      // later translation.final events can enrich by transcript event ID.
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
        // New pharmacist speech invalidates an old confirmation because the
        // conversation context has moved on.
        confirmation: isPharmacist ? null : state.confirmation,
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
      const nextSegments = exists
        ? state.chineseSegments
        : [...state.chineseSegments, payload];

      // Translation segments are append-only; duplicate segment IDs preserve the
      // first rendered text and prevent replay from duplicating subtitles.
      return recordEvent(state, event, {
        status: "listening",
        turns,
        chineseSegments: nextSegments,
        activeUtteranceId: payload.sourceTranscriptEventId ?? null,
      });
    }
    case "route.decision": {
      const payload = event.payload as { routeType?: string; route_type?: string };
      return recordEvent(state, event, {
        status:
          (payload.routeType ?? payload.route_type) === "passive_translation"
            ? "listening"
            : "checking",
      });
    }
    case "tool.status": {
      const payload = event.payload as { phase?: string };
      const status =
        payload.phase === "started"
          ? "checking"
          : payload.phase === "succeeded"
          ? "listening"
          : payload.phase === "blocked"
          ? "blocked"
          : payload.phase === "failed"
          ? "error"
          : state.status;
      return recordEvent(state, event, { status });
    }
    case "cards.render": {
      const payload = event.payload as { cardSet: RawCardSet | null };
      const rawCardSet = payload.cardSet;
      // Accept both snake_case and camelCase because replayed backend events and
      // direct test fixtures can enter the reducer through different mappers.
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
            riskLevel: riskLevelView(card.riskLevel || card.risk_level),
            actionType,
          };

        }),
      } : null;
      return recordEvent(state, event, {
        activeCardSet: cardSet,
        status: cardSet && cardSet.cards.length > 0 ? "needs_confirmation" : state.status,
      });
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
      // The server-minted confirmation ID is the only executable authority; the
      // frontend keeps card text only for display.
      const action = {
        eventId: event.eventId,
        eventType: event.eventType,
        timestamp: event.timestamp,
        confirmationId: payload.confirmationId,
        cardSetId: payload.cardSetId,
        cardId: payload.cardId,
        actionType: card?.actionType ?? null,
        phase: "selected",
        replayed: null,
      };
      return recordEvent(state, event, {
        status: "needs_confirmation",
        confirmation,
        actions: [...state.actions, action],
      });
    }
    case "card.confirmed": {
      const payload = event.payload as {
        confirmationId?: string;
        confirmation_id?: string;
        actionType?: string;
        action_type?: string;
        replayed?: boolean;
      };
      const confirmationId = payload.confirmationId ?? payload.confirmation_id ?? null;
      const action = {
        eventId: event.eventId,
        eventType: event.eventType,
        timestamp: event.timestamp,
        confirmationId,
        cardSetId: state.confirmation?.cardSetId ?? null,
        cardId: state.confirmation?.card.cardId ?? null,
        actionType: actionTypeView(payload.actionType ?? payload.action_type),
        phase: "confirmed",
        replayed: payload.replayed ?? null,
      };
      return recordEvent(state, event, {
        status: "checking",
        // Once confirmed, card selection UI is cleared while action status
        // events report whether speech or side effects completed.
        confirmation: null,
        activeCardSet: null,
        actions: [...state.actions, action],
      });
    }
    case "card.action.status": {
      const payload = event.payload as {
        confirmationId?: string;
        confirmation_id?: string;
        actionType?: string;
        action_type?: string;
        phase?: string;
      };
      const action = {
        eventId: event.eventId,
        eventType: event.eventType,
        timestamp: event.timestamp,
        confirmationId: payload.confirmationId ?? payload.confirmation_id ?? null,
        cardSetId: null,
        cardId: null,
        actionType: actionTypeView(payload.actionType ?? payload.action_type),
        phase: payload.phase ?? null,
        replayed: null,
      };
      const status =
        payload.phase === "started"
          ? state.status === "speaking"
            ? "speaking"
            : "checking"
          : payload.phase === "succeeded"
          ? "listening"
          : payload.phase === "blocked"
          ? "blocked"
          : payload.phase === "failed"
          ? "error"
          : state.status;
      return recordEvent(state, event, {
        status,
        actions: [...state.actions, action],
      });
    }
    case "audio.speaking": {
      const payload = event.payload as { phase?: string };
      const status =
        payload.phase === "started"
          ? "speaking"
          : payload.phase === "completed" || payload.phase === "interrupted"
          ? "listening"
          : state.status;
      return recordEvent(state, event, {
        status,
        // Speech start also clears the confirmation panel; the approved card is
        // now owned by the action-status lifecycle.
        confirmation: null,
      });
    }
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
      // Summary render is a review state, not delivery. The summary page still
      // requires an explicit send/save/cancel choice.
      return recordEvent(state, event, {
        summary: payload.summary,
        status: "needs_confirmation",
      });
    }
    case "session.ended":
      return recordEvent(state, event, { status: "ended" });
    default:
      return recordEvent(state, event, {});
  }
}
