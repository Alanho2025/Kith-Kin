import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { mockFallbackFlow } from "../test/fixtures/mock-fallback-flow";
import { ConversationPage } from "./ConversationPage";
import type { RuntimeCommandView } from "../features/conversation/viewModels";


describe("ConversationPage", () => {
  it("renders elder-first voice controls and conversation log", async () => {
    const runtime = new MockConversationRuntime(mockFallbackFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-controls" />);

    expect(await screen.findByRole("button", { name: "听药剂师说话" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "按住说中文" })).toBeInTheDocument();
    expect(screen.getAllByRole("complementary", { name: "对话记录" })[0]).toBeInTheDocument();
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

  it("renders State A (Listening) correctly without cards", () => {
    const listeningFlow = [
      {
        schemaVersion: "0.1",
        eventId: "evt-listening-1",
        eventType: "audio.listening",
        sessionId: "ses-listening",
        sequence: 1,
        timestamp: "2026-06-22T00:00:00Z",
        correlationId: null,
        payload: { active: true },
      },
      {
        schemaVersion: "0.1",
        eventId: "evt-trans-old",
        eventType: "translation.final",
        sessionId: "ses-listening",
        sequence: 2,
        timestamp: "2026-06-22T00:00:00Z",
        correlationId: null,
        payload: {
          sourceTranscriptEventId: "evt-transcribing-1",
          segmentId: "seg-old-1",
          sourceLanguage: "en",
          targetLanguage: "zh_cn",
          translatedText: "请帮我确认这个药会不会冲突。",
          mode: "faithful",
          appendOnly: true,
          latencyMs: 10,
        },
      },
      // Even if cards are rendered by a previous event, transcribing status should hide them
      {
        schemaVersion: "0.1",
        eventId: "evt-cards-old",
        eventType: "cards.render",
        sessionId: "ses-listening",
        sequence: 3,
        timestamp: "2026-06-22T00:00:00Z",
        correlationId: null,
        payload: {
          cardSet: {
            cardSetId: "set-old",
            revision: 1,
            cards: [
              {
                cardId: "card-old-1",
                zhText: "请帮我确认这个药会不会冲突。",
                enText: "Could you check whether this conflicts?",
                riskLevel: "medical",
                actionType: "speak",
              },
            ],
          },
        },
      },
      {
        schemaVersion: "0.1",
        eventId: "evt-transcribing-1",
        eventType: "transcript.partial",
        sessionId: "ses-listening",
        sequence: 4,
        timestamp: "2026-06-22T00:00:00Z",
        correlationId: null,
        payload: { text: "Is Lisinopril your blood pressure medication?", speaker: "pharmacist" },
      },
    ];

    const runtime = new MockConversationRuntime(listeningFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-listening" />);

    // In State A, cards should not be displayed
    expect(screen.queryByText("请选择回应")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /确认这个药会不会冲突/ })).not.toBeInTheDocument();
    expect(screen.getByText("正在听药剂师说话")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "请药剂师再说一次" })).toBeInTheDocument();
  });

  it("renders State C (Inline Confirmation) directly replacing cards list", async () => {
    const cardFlow = [
      {
        schemaVersion: "0.1",
        eventId: "evt-trans-confirm",
        eventType: "translation.final",
        sessionId: "ses-confirm",
        sequence: 1,
        timestamp: "2026-06-22T00:00:00Z",
        correlationId: null,
        payload: {
          sourceTranscriptEventId: "evt-source-confirm",
          segmentId: "seg-confirm",
          sourceLanguage: "en",
          targetLanguage: "zh_cn",
          translatedText: "请帮我確認衝突。",
          mode: "faithful",
          appendOnly: true,
          latencyMs: 10,
        },
      },
      {
        schemaVersion: "0.1",
        eventId: "evt-cards-render",
        eventType: "cards.render",
        sessionId: "ses-confirm",
        sequence: 2,
        timestamp: "2026-06-22T00:00:00Z",
        correlationId: null,
        payload: {
          cardSet: {
            cardSetId: "set-confirm",
            revision: 1,
            cards: [
              {
                cardId: "card-conf-1",
                zhText: "请帮我確認衝突。",
                enText: "Could you check conflict?",
                riskLevel: "medical",
                actionType: "speak",
              },
            ],
          },
        },
      },
    ];

    const runtime = new MockConversationRuntime(cardFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-confirm" />);

    // Click to select the card to enter State C (Confirmation)
    const cardElement = await screen.findByRole("button", { name: /请帮我確認/ });
    const { act } = await import("@testing-library/react");
    await act(async () => {
      fireEvent.click(cardElement);
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    // The inline confirmation should be rendered, replacing the card list
    expect(await screen.findByRole("heading", { name: /你要让我用英文说这句/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "替我说" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重选" })).toBeInTheDocument();
    // Cards list is now hidden
    expect(screen.queryByText("请选择回应")).not.toBeInTheDocument();
  });

  it("toggles trace visibility via hidden dev switch", () => {
    const runtime = new MockConversationRuntime([]);
    render(<ConversationPage runtime={runtime} sessionId="ses-dev" />);

    // Technical trace details should not be rendered by default
    expect(screen.queryByText("安全检查详情")).not.toBeInTheDocument();

    // Click hidden toggle in StatusBar
    const toggleButton = screen.getByTestId("dev-mode-toggle");
    fireEvent.click(toggleButton);

    // Now it should render
    expect(screen.getByText("安全检查详情")).toBeInTheDocument();
  });

  it("filters out system reasoning from subtitles and logs in user mode", async () => {
    const reasoningFlow = [
      {
        schemaVersion: "0.1",
        eventId: "evt-reasoning-1",
        eventType: "transcript.final",
        sessionId: "ses-reasoning",
        sequence: 1,
        timestamp: new Date().toISOString(),
        correlationId: null,
        payload: {
          utteranceId: "utt-r1",
          speaker: "pharmacist",
          language: "en",
          text: "**Awaiting further instructions**",
          revision: 1,
        },
      },
      {
        schemaVersion: "0.1",
        eventId: "evt-reasoning-trans",
        eventType: "translation.final",
        sessionId: "ses-reasoning",
        sequence: 2,
        timestamp: new Date().toISOString(),
        correlationId: null,
        payload: {
          sourceTranscriptEventId: "evt-reasoning-1",
          segmentId: "seg-r1",
          sourceLanguage: "en",
          targetLanguage: "zh_cn",
          translatedText: "**等待进一步指示**",
          mode: "faithful",
          append_only: true,
          latencyMs: 100,
        },
      },
    ];

    const runtime = new MockConversationRuntime(reasoningFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-reasoning" />);

    // In user mode (default), the subtitle should NOT show the reasoning text
    expect(screen.queryByText(/等待进一步指示/)).not.toBeInTheDocument();

    // Toggle devMode
    const toggleButton = screen.getByTestId("dev-mode-toggle");
    fireEvent.click(toggleButton);

    // In dev mode, the subtitle and log should show the reasoning text
    const elements = await screen.findAllByText(/等待进一步指示/);
    expect(elements.length).toBeGreaterThan(0);
  });

  it("locks action buttons when confirm is clicked", async () => {
    const cardFlow = [
      {
        schemaVersion: "0.1",
        eventId: "evt-final",
        eventType: "transcript.final",
        sessionId: "ses-lock",
        sequence: 1,
        timestamp: new Date().toISOString(),
        correlationId: null,
        payload: {
          utteranceId: "utt-1",
          speaker: "pharmacist",
          language: "en",
          text: "Are you taking any blood pressure medicine?",
          revision: 1,
        },
      },
      {
        schemaVersion: "0.1",
        eventId: "evt-translation",
        eventType: "translation.final",
        sessionId: "ses-lock",
        sequence: 2,
        timestamp: new Date().toISOString(),
        correlationId: null,
        payload: {
          sourceTranscriptEventId: "evt-final",
          segmentId: "segment-1",
          sourceLanguage: "en",
          targetLanguage: "zh_cn",
          translatedText: "请帮我確認衝突。",
          mode: "faithful",
          append_only: true,
          latencyMs: 100,
        },
      },
      {
        schemaVersion: "0.1",
        eventId: "evt-proposal",
        eventType: "cards.render",
        sessionId: "ses-lock",
        sequence: 3,
        timestamp: new Date().toISOString(),
        correlationId: null,
        payload: {
          cardSet: {
            cardSetId: "cardset-1",
            revision: 1,
            sourceEventId: "evt-final",
            generatedAt: new Date().toISOString(),
            expiresAt: new Date().toISOString(),
            cards: [
              {
                cardId: "card-1",
                cardType: "ask_question",
                zhText: "请帮我確認衝突。",
                enText: "Could you check conflict?",
                riskLevel: "medical",
                action: {
                  type: "speak",
                  payload: {
                    text: "Could you check conflict?",
                  },
                },
                requiresParentConfirmation: true,
                requiresGuardianApproval: true,
                guardianDecisionId: "gd-1",
              },
            ],
          },
        },
      },
    ];

    const runtime = new MockConversationRuntime(cardFlow);
    let resolveSendCommand: (value: unknown) => void = () => {};
    const sendCommandPromise = new Promise((resolve) => {
      resolveSendCommand = resolve;
    });
    const originalSendCommand = runtime.sendCommand.bind(runtime);
    vi.spyOn(runtime, "sendCommand").mockImplementation((cmd: RuntimeCommandView) => {
      if (cmd.eventType === "card.confirm") {
        return sendCommandPromise as Promise<void>;
      }
      return originalSendCommand(cmd);
    });

    render(<ConversationPage runtime={runtime} sessionId="ses-lock" />);

    const cardElement = await screen.findByRole("button", { name: /请帮我確認/ });
    const { act } = await import("@testing-library/react");
    await act(async () => {
      fireEvent.click(cardElement);
      await new Promise((resolve) => setTimeout(resolve, 10));
    });

    const confirmButton = screen.getByRole("button", { name: "替我说" });
    const retryButton = screen.getByRole("button", { name: "重选" });
    const cancelButton = screen.getByRole("button", { name: "取消" });

    // Click confirm button
    act(() => {
      fireEvent.click(confirmButton);
    });

    // Both buttons should be disabled during confirm speaking action
    expect(confirmButton).toBeDisabled();
    expect(retryButton).toBeDisabled();
    expect(cancelButton).toBeDisabled();

    // Clean up
    resolveSendCommand(undefined);
  });
});
