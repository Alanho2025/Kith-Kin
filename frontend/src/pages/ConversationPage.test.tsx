import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { mockFallbackFlow } from "../test/fixtures/mock-fallback-flow";
import { ConversationPage } from "./ConversationPage";


describe("ConversationPage", () => {
  it("renders elder-first voice controls and conversation log", async () => {
    const runtime = new MockConversationRuntime(mockFallbackFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-controls" />);

    expect(await screen.findByRole("button", { name: "听药剂师说话" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "按住说中文" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "对话记录" })).toBeInTheDocument();
    expect(screen.getByText("听懂药剂师，再安全回应")).toBeInTheDocument();
  });

  it("fallback keeps english", async () => {
    const runtime = new MockConversationRuntime(mockFallbackFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-fallback" />);

    expect(await screen.findAllByText("Please write down the medicine name.")).toHaveLength(3);
    expect(screen.getByText("中文翻译暂时不可用。KK 会继续显示英文原文，并尽快恢复中文。")).toBeInTheDocument();
    expect(screen.getByLabelText("忠实中文翻译")).toHaveTextContent("上一句忠实翻译。");
    expect(screen.getByLabelText("忠实中文翻译")).not.toHaveTextContent("请写下药名");
  });
});
