import { describe, expect, it } from "vitest";

import { conversationReducer, initialConversationState } from "./reducer";
import { makeEvent } from "../../test/fixtures/runtime-events";

describe("conversationReducer", () => {
  it("records confirmed card speech as KK relay instead of parent speech", () => {
    const withCards = conversationReducer(
      initialConversationState,
      makeEvent("cards.render", "evt-cards-1", {
        cardSet: {
          cardSetId: "cards-1",
          revision: 1,
          cards: [
            {
              cardId: "card-1",
              zhText: "请帮我确认布洛芬是否适合和我现在的药一起用？",
              enText: "Could you please check whether ibuprofen is suitable with my current medicines?",
              riskLevel: "medical",
              actionType: "show_to_pharmacist",
            },
          ],
        },
      }),
    );
    const selected = conversationReducer(
      withCards,
      makeEvent("card.selected", "evt-selected-1", {
        cardSetId: "cards-1",
        cardId: "card-1",
        confirmationId: "confirmation-1",
      }),
    );

    const confirmed = conversationReducer(
      selected,
      makeEvent("card.confirmed", "evt-confirmed-1", {
        confirmationId: "confirmation-1",
        actionType: "show_to_pharmacist",
        replayed: false,
      }),
    );

    expect(confirmed.turns).toHaveLength(1);
    expect(confirmed.turns[0].speaker).toBe("kk");
    expect(confirmed.turns[0].sourceText).toContain("Could you please check");
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
