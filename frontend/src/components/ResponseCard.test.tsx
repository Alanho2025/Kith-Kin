import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConversationPage } from "../pages/ConversationPage";
import { mockPharmacyFlow } from "../test/fixtures/mock-pharmacy-flow";
import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";


describe("ResponseCard", () => {
  it("selection only opens confirmation", async () => {
    const runtime = new MockConversationRuntime(mockPharmacyFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-test" />);

    fireEvent.click(await screen.findByRole("button", { name: /请帮我确认这个药/ }));

    await waitFor(() => {
      expect(runtime.commands).toEqual([
        {
          eventType: "card.select",
          payload: { cardSetId: "set-1", cardId: "card-1", revision: 1 },
        },
      ]);
    });
    expect(
      await screen.findByRole("dialog", { name: "你要让我用英文说这句吗？" }),
    ).toBeInTheDocument();
    expect(runtime.commands.some((command) => command.eventType === "card.confirm")).toBe(false);
  });

  it("cancel closes confirmation and sends only card cancel", async () => {
    const runtime = new MockConversationRuntime(mockPharmacyFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-cancel" />);

    fireEvent.click(await screen.findByRole("button", { name: /请帮我确认这个药/ }));
    const dialog = await screen.findByRole("dialog", { name: "你要让我用英文说这句吗？" });
    fireEvent.click(screen.getByRole("button", { name: "重选" }));

    await waitFor(() => expect(dialog).not.toBeInTheDocument());
    expect(runtime.commands.at(-1)).toEqual({
      eventType: "card.cancel",
      payload: { confirmationId: "confirmation-card-1" },
    });
  });
});
