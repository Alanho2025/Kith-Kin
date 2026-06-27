import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { mockFallbackFlow } from "../test/fixtures/mock-fallback-flow";
import { ConversationPage } from "./ConversationPage";


describe("ConversationPage", () => {
  it("fallback keeps english", async () => {
    const runtime = new MockConversationRuntime(mockFallbackFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-fallback" />);

    expect(await screen.findAllByText("Please write down the medicine name.")).toHaveLength(2);
    expect(screen.getByText("中文翻译暂时不可用。KK 会继续显示英文原文，并尽快恢复中文。")).toBeInTheDocument();
    expect(screen.getByLabelText("忠实中文翻译")).toHaveTextContent("上一句忠实翻译。");
    expect(screen.getByLabelText("忠实中文翻译")).not.toHaveTextContent("请写下药名");
  });
});
