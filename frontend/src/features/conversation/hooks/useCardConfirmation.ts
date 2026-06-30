import { useCallback } from "react";

import type {
  CardSetView,
  ConfirmationView,
  ResponseCardView,
  RuntimeCommandView,
} from "../viewModels";
import { conversationDebug } from "../debugLog";


export function useCardConfirmation(
  activeCardSet: CardSetView | null,
  confirmation: ConfirmationView | null,
  sendCommand: (command: RuntimeCommandView) => Promise<void>,
  dismissConfirmation: () => void,
) {
  const selectCard = useCallback(
    async (card: ResponseCardView) => {
      if (!activeCardSet) return;
      conversationDebug("card.select", {
        cardSetId: activeCardSet.cardSetId,
        revision: activeCardSet.revision,
        card,
      });
      // Selecting a card only asks the backend to mint a confirmation ID; it
      // never speaks or executes the card action.
      await sendCommand({
        eventType: "card.select",
        payload: {
          cardSetId: activeCardSet.cardSetId,
          cardId: card.cardId,
          revision: activeCardSet.revision,
        },
      });
    },
    [activeCardSet, sendCommand],
  );

  const confirm = useCallback(async () => {
    if (!confirmation) return;
    conversationDebug("card.confirm", {
      confirmationId: confirmation.confirmationId,
      card: confirmation.card,
    });
    // Confirmation sends only the server-minted ID so executable text remains
    // server-owned.
    await sendCommand({
      eventType: "card.confirm",
      payload: { confirmationId: confirmation.confirmationId },
    });
  }, [confirmation, sendCommand]);

  const cancel = useCallback(async () => {
    if (!confirmation) return;
    conversationDebug("card.cancel", {
      confirmationId: confirmation.confirmationId,
      card: confirmation.card,
    });
    dismissConfirmation();
    // Cancel is local-first for responsiveness, then the backend revokes the
    // pending confirmation so stale actions cannot be confirmed later.
    await sendCommand({
      eventType: "card.cancel",
      payload: { confirmationId: confirmation.confirmationId },
    });
  }, [confirmation, dismissConfirmation, sendCommand]);

  return { selectCard, confirm, cancel };
}
