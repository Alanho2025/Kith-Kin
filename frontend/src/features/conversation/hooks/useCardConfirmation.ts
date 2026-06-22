import { useCallback } from "react";

import type {
  CardSetView,
  ConfirmationView,
  ResponseCardView,
  RuntimeCommandView,
} from "../viewModels";


export function useCardConfirmation(
  activeCardSet: CardSetView | null,
  confirmation: ConfirmationView | null,
  sendCommand: (command: RuntimeCommandView) => Promise<void>,
  dismissConfirmation: () => void,
) {
  const selectCard = useCallback(
    async (card: ResponseCardView) => {
      if (!activeCardSet) return;
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
    await sendCommand({
      eventType: "card.confirm",
      payload: { confirmationId: confirmation.confirmationId },
    });
  }, [confirmation, sendCommand]);

  const cancel = useCallback(async () => {
    if (!confirmation) return;
    dismissConfirmation();
    await sendCommand({
      eventType: "card.cancel",
      payload: { confirmationId: confirmation.confirmationId },
    });
  }, [confirmation, dismissConfirmation, sendCommand]);

  return { selectCard, confirm, cancel };
}
