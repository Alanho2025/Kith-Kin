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
    expect(confirmed.status).toBe("speaking");
    expect(JSON.stringify(confirmed.turns)).not.toContain("The patient is currently taking");
    expect(JSON.stringify(confirmed.turns)).not.toContain("患者目前正在服用赖诺普利");
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
});
