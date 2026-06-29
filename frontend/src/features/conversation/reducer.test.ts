import { describe, expect, it } from "vitest";

import { conversationReducer, initialConversationState } from "./reducer";
import { makeEvent } from "../../test/fixtures/runtime-events";

describe("conversationReducer", () => {
  function stateWithSelectedCard(card: {
    cardId?: string;
    zhText?: string;
    enText?: string;
    speakZh?: string;
    actionType?: string;
  }) {
    const withCards = conversationReducer(
      initialConversationState,
      makeEvent("cards.render", "evt-cards-1", {
        cardSet: {
          cardSetId: "cards-1",
          revision: 1,
          cards: [
            {
              cardId: card.cardId ?? "card-1",
              zhText: card.zhText ?? "请帮我确认布洛芬是否适合和我现在的药一起用？",
              enText:
                card.enText ??
                "Could you please check whether ibuprofen is suitable with my current medicines?",
              speakZh: card.speakZh,
              riskLevel: "medical",
              actionType: card.actionType ?? "show_to_pharmacist",
            },
          ],
        },
      }),
    );
    return conversationReducer(
      withCards,
      makeEvent("card.selected", "evt-selected-1", {
        cardSetId: "cards-1",
        cardId: card.cardId ?? "card-1",
        confirmationId: "confirmation-1",
      }),
    );
  }

  it.each([
    {
      name: "show_to_pharmacist with speakZh",
      actionType: "show_to_pharmacist",
      speakZh: "患者目前正在服用赖诺普利。请问这有冲突吗？",
    },
    {
      name: "speak without speakZh",
      actionType: "speak",
      speakZh: undefined,
    },
  ])("does not record confirmed card text as a KK conversation turn: $name", (card) => {
    const selected = stateWithSelectedCard({
      actionType: card.actionType,
      zhText: "确认我正在服用血压药赖诺普利并告诉药师",
      enText:
        "The patient is currently taking Lisinopril. Could you check if there is an interaction?",
      speakZh: card.speakZh,
    });

    const confirmed = conversationReducer(
      selected,
      makeEvent("card.confirmed", "evt-confirmed-1", {
        confirmationId: "confirmation-1",
        actionType: card.actionType,
        replayed: false,
      }),
    );

    expect(confirmed.turns).toEqual([]);
    expect(confirmed.confirmation).toBeNull();
    expect(confirmed.status).not.toBe("speaking");
    expect(confirmed.status).toBe("checking");
    expect(JSON.stringify(confirmed.turns)).not.toContain("The patient is currently taking");
    expect(JSON.stringify(confirmed.turns)).not.toContain("患者目前正在服用赖诺普利");
  });

  it("enters speaking only after audio.speaking starts", () => {
    const selected = stateWithSelectedCard({ actionType: "speak" });
    const confirmed = conversationReducer(
      selected,
      makeEvent("card.confirmed", "evt-confirmed-audio-1", {
        confirmationId: "confirmation-1",
        actionType: "speak",
        replayed: false,
      }),
    );
    const started = conversationReducer(
      confirmed,
      makeEvent("audio.speaking", "evt-audio-started-1", {
        phase: "started",
        cardId: "card-1",
      }),
    );
    const completed = conversationReducer(
      started,
      makeEvent("audio.speaking", "evt-audio-completed-1", {
        phase: "completed",
        cardId: "card-1",
      }),
    );

    expect(confirmed.status).toBe("checking");
    expect(started.status).toBe("speaking");
    expect(completed.status).toBe("listening");
  });

  it("keeps card select, confirm, cancel, and duplicate confirm out of conversation turns", () => {
    const withFirstSelection = stateWithSelectedCard({
      cardId: "card-1",
      zhText: "请确认第一句。",
      enText: "Could you please confirm the first statement?",
    });
    const reselected = conversationReducer(
      withFirstSelection,
      makeEvent("card.selected", "evt-selected-2", {
        cardSetId: "cards-1",
        cardId: "card-1",
        confirmationId: "confirmation-2",
      }),
    );

    expect(withFirstSelection.turns).toEqual([]);
    expect(reselected.turns).toEqual([]);
    expect(reselected.confirmation?.confirmationId).toBe("confirmation-2");

    const cancelled = conversationReducer(reselected, { type: "dismiss_confirmation" });
    expect(cancelled.turns).toEqual([]);
    expect(cancelled.confirmation).toBeNull();

    const confirmed = conversationReducer(
      reselected,
      makeEvent("card.confirmed", "evt-confirmed-2", {
        confirmationId: "confirmation-2",
        actionType: "speak",
        replayed: false,
      }),
    );
    const duplicateConfirmed = conversationReducer(
      confirmed,
      makeEvent("card.confirmed", "evt-confirmed-2", {
        confirmationId: "confirmation-2",
        actionType: "speak",
        replayed: true,
      }),
    );

    expect(confirmed.turns).toEqual([]);
    expect(duplicateConfirmed.turns).toEqual([]);
  });


  it("stores neutral pharmacist-stated product options", () => {
    const state = conversationReducer(
      initialConversationState,
      makeEvent("product.options.render", "evt-product-options-1", {
        options: [
          {
            name: "paracetamol",
            price: "6 dollars",
            pharmacistStatedUse: "usually used for pain or fever",
            pharmacistStatedDirections: "two tablets every six hours if suitable",
            pharmacistStatedCautions: null,
          },
          {
            name: "ibuprofen",
            price: "9 dollars",
            pharmacistStatedUse: null,
            pharmacistStatedCautions: "may not be suitable with certain medicines",
          },
        ],
      }),
    );

    expect(state.productOptions).toHaveLength(2);
    expect(state.productOptions[0].name).toBe("paracetamol");
    expect(state.productOptions[0].pharmacistStatedDirections).toContain("six hours");
    expect(state.productOptions[1].pharmacistStatedCautions).toContain("certain medicines");
  });

  it("keeps faithful translation history on turns and deduplicates repeated segments", () => {
    const firstTranscript = conversationReducer(
      initialConversationState,
      makeEvent("transcript.final", "evt-transcript-1", {
        utteranceId: "utt-1",
        speaker: "pharmacist",
        language: "en",
        text: "Good morning.",
        revision: 1,
      }),
    );
    const firstTranslation = conversationReducer(
      firstTranscript,
      makeEvent("translation.final", "evt-translation-1", {
        segmentId: "seg-1",
        sourceTranscriptEventId: "evt-transcript-1",
        translatedText: "早上好。",
      }),
    );
    const secondTranscript = conversationReducer(
      firstTranslation,
      makeEvent("transcript.final", "evt-transcript-2", {
        utteranceId: "utt-2",
        speaker: "pharmacist",
        language: "en",
        text: "Do you have any allergies?",
        revision: 1,
      }),
    );
    const secondTranslation = conversationReducer(
      secondTranscript,
      makeEvent("translation.final", "evt-translation-2", {
        segmentId: "seg-2",
        sourceTranscriptEventId: "evt-transcript-2",
        translatedText: "您有任何过敏吗？",
      }),
    );
    const duplicateSecond = conversationReducer(
      secondTranslation,
      makeEvent("translation.final", "evt-translation-2-duplicate", {
        segmentId: "seg-2",
        sourceTranscriptEventId: "evt-transcript-2",
        translatedText: "您有任何过敏吗？",
      }),
    );

    expect(secondTranslation.chineseSegments.map((segment) => segment.segmentId)).toEqual([
      "seg-1",
      "seg-2",
    ]);
    expect(duplicateSecond.chineseSegments.map((segment) => segment.segmentId)).toEqual([
      "seg-1",
      "seg-2",
    ]);
    expect(duplicateSecond.turns.map((turn) => turn.translatedText)).toEqual([
      "早上好。",
      "您有任何过敏吗？",
    ]);
  });

  it("normalizes invalid card risk fallback to normal", () => {
    const state = conversationReducer(
      initialConversationState,
      makeEvent("cards.render", "evt-cards-risk-fallback", {
        cardSet: {
          cardSetId: "cards-risk",
          revision: 1,
          cards: [
            {
              cardId: "card-risk",
              zhText: "请药师解释。",
              enText: "Could you please explain this?",
              actionType: "speak",
            },
          ],
        },
      }),
    );

    expect(state.activeCardSet?.cards[0]?.riskLevel).toBe("normal");
  });

  it("maps tool.status phases to terminal UI states", () => {
    const started = conversationReducer(
      initialConversationState,
      makeEvent("tool.status", "evt-tool-started", {
        operationId: "op-1",
        toolName: "memory_search",
        phase: "started",
      }),
    );
    const succeeded = conversationReducer(
      started,
      makeEvent("tool.status", "evt-tool-succeeded", {
        operationId: "op-1",
        toolName: "memory_search",
        phase: "succeeded",
      }),
    );
    const failed = conversationReducer(
      started,
      makeEvent("tool.status", "evt-tool-failed", {
        operationId: "op-1",
        toolName: "memory_search",
        phase: "failed",
      }),
    );
    const blocked = conversationReducer(
      started,
      makeEvent("tool.status", "evt-tool-blocked", {
        operationId: "op-1",
        toolName: "memory_search",
        phase: "blocked",
      }),
    );

    expect(started.status).toBe("checking");
    expect(succeeded.status).toBe("listening");
    expect(failed.status).toBe("error");
    expect(blocked.status).toBe("blocked");
  });

  it("sets cards.render and summary.render to needs_confirmation", () => {
    const withCards = conversationReducer(
      initialConversationState,
      makeEvent("cards.render", "evt-cards-status", {
        cardSet: {
          cardSetId: "cards-status",
          revision: 1,
          cards: [
            {
              cardId: "card-status",
              zhText: "请药师写下来。",
              enText: "Could you please write that down?",
              riskLevel: "normal",
              actionType: "speak",
            },
          ],
        },
      }),
    );
    const withSummary = conversationReducer(
      withCards,
      makeEvent("summary.render", "evt-summary-status", {
        summary: {
          titleZh: "今天药局沟通重点",
          mentionedDrugs: ["Panadol"],
          pharmacistAdviceSummaryZh: "药师说明可以现金或刷卡。",
          unresolvedQuestionsZh: [],
          followUpNeeded: false,
        },
      }),
    );

    expect(withCards.status).toBe("needs_confirmation");
    expect(withSummary.status).toBe("needs_confirmation");
  });
});
