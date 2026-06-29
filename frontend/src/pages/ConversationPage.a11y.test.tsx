import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { mockPharmacyFlow } from "../test/fixtures/mock-pharmacy-flow";
import { ConversationPage } from "./ConversationPage";


describe("ConversationPage accessibility", () => {
  it("critical controls are named", async () => {
    render(
      <ConversationPage
        runtime={new MockConversationRuntime(mockPharmacyFlow)}
        sessionId="ses-a11y"
      />,
    );

    for (const name of ["听药剂师说话", "按住说中文", "请药剂师再说一次", "请稍等", "结束"] as const) {
      const control = await screen.findByRole("button", { name });
      expect(control).toBeInTheDocument();
    }
  });
});
