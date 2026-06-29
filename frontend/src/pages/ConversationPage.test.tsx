import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { mockFallbackFlow } from "../test/fixtures/mock-fallback-flow";
import { ConversationPage } from "./ConversationPage";
import type { RuntimeCommandView } from "../features/conversation/viewModels";


describe("ConversationPage", () => {
  function runtimeEvent(eventType: string, eventId: string, sequence: number, payload: object) {
    return {
      schemaVersion: "0.1",
      eventId,
      eventType,
      sessionId: "ses-page",
      sequence,
      timestamp: "2026-06-22T00:00:00Z",
      correlationId: null,
      payload,
    };
  }

  function translationEvent(eventId: string, sequence: number, translatedText: string) {
    return runtimeEvent("translation.final", eventId, sequence, {
      sourceTranscriptEventId: "evt-source-page",
      segmentId: `seg-${eventId}`,
      sourceLanguage: "en",
      targetLanguage: "zh_cn",
      translatedText,
      mode: "faithful",
      appendOnly: true,
      latencyMs: 10,
    });
  }

  it("renders elder-first voice controls and conversation log", async () => {
    const runtime = new MockConversationRuntime(mockFallbackFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-controls" />);

    expect(await screen.findByRole("button", { name: "听药剂师说话" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "按住说中文" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "我自己说" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重复" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("complementary", { name: "对话记录" })[0]).toBeInTheDocument();
    expect(screen.getByText("听懂药剂师，再安全回应")).toBeInTheDocument();
  });

  it("please wait pauses the recorder until a top voice control resumes it", async () => {
    const runtime = new MockConversationRuntime([]);
    render(<ConversationPage runtime={runtime} sessionId="ses-wait" />);

    fireEvent.click(await screen.findByRole("button", { name: "听药剂师说话" }));
    expect(runtime.microphoneMode).toBe("pharmacist");

    fireEvent.click(screen.getByRole("button", { name: "请稍等" }));
    expect(runtime.microphoneMode).toBeNull();
    expect(runtime.commands).toContainEqual({
      eventType: "control.please_wait",
      payload: {},
    });

    fireEvent.click(screen.getByRole("button", { name: "听药剂师说话" }));
    expect(runtime.microphoneMode).toBe("pharmacist");
  });

  it("records parent Chinese speech as elder speech, not medical staff", async () => {
    const runtime = new MockConversationRuntime([
      {
        schemaVersion: "0.1",
        eventId: "evt-parent-zh",
        eventType: "transcript.final",
        sessionId: "ses-parent",
        sequence: 1,
        timestamp: "2026-06-22T00:00:00Z",
        correlationId: null,
        payload: {
          utteranceId: "utt-parent-zh",
          speaker: "parent",
          language: "zh",
          text: "我想知道关于感冒药。",
          revision: 1,
        },
      },
    ]);

    render(<ConversationPage runtime={runtime} sessionId="ses-parent" />);

    expect(await screen.findAllByText("老人原话")).not.toHaveLength(0);
    expect(screen.getAllByText("我想知道关于感冒药。")).not.toHaveLength(0);
    expect(screen.queryByText("医护人员")).not.toBeInTheDocument();
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

  it("renders neutral pharmacist-stated product options", async () => {
    const productFlow = [
      {
        schemaVersion: "0.1",
        eventId: "evt-products-1",
        eventType: "product.options.render",
        sessionId: "ses-products",
        sequence: 1,
        timestamp: "2026-06-22T00:00:00Z",
        correlationId: null,
        payload: {
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
        },
      },
    ];

    const runtime = new MockConversationRuntime(productFlow);
    render(<ConversationPage runtime={runtime} sessionId="ses-products" />);

    expect(await screen.findByText("药师说的产品选项")).toBeInTheDocument();
    expect(screen.getByText("paracetamol")).toBeInTheDocument();
    expect(screen.getByText("6 dollars")).toBeInTheDocument();
    expect(screen.getByText("usually used for pain or fever")).toBeInTheDocument();
    expect(screen.getByText("two tablets every six hours if suitable")).toBeInTheDocument();
    expect(screen.queryByText(/best option/i)).not.toBeInTheDocument();
  });

  it("does not show confirmed response-card text as a KK speech turn in the conversation log", async () => {
    const cardText =
      "Could you please confirm if Nurofen has an interaction with my blood pressure medicine, Lisinopril?";
    const cardFlow = [
      runtimeEvent("transcript.final", "evt-card-log-source", 1, {
        utteranceId: "utt-card-log-source",
        speaker: "pharmacist",
        language: "en",
        text: "I can show you three options.",
        revision: 1,
      }),
      translationEvent("evt-card-log-translation", 2, "我可以给你看三个选项。"),
      runtimeEvent("cards.render", "evt-card-log-render", 3, {
        cardSet: {
          cardSetId: "set-card-log",
          revision: 1,
          cards: [
            {
              cardId: "card-log-1",
              zhText: "我想确认布洛芬是否和我的降压药赖诺普利有冲突？",
              enText: cardText,
              riskLevel: "medical",
              actionType: "show_to_pharmacist",
            },
          ],
        },
      }),
      runtimeEvent("card.selected", "evt-card-log-selected", 4, {
        cardSetId: "set-card-log",
        cardId: "card-log-1",
        confirmationId: "confirmation-card-log",
      }),
      runtimeEvent("card.confirmed", "evt-card-log-confirmed", 5, {
        confirmationId: "confirmation-card-log",
        actionType: "show_to_pharmacist",
        replayed: false,
      }),
    ];

    render(<ConversationPage runtime={new MockConversationRuntime(cardFlow)} sessionId="ses-card-log" />);

    await screen.findByText("我可以给你看三个选项。");
    expect(screen.queryAllByText("KK 代说")).toHaveLength(0);
    expect(screen.queryAllByText(cardText)).toHaveLength(0);
  });

  it("keeps the latest faithful translation visible after route decisions, card renders, and listening resumes", async () => {
    const translatedText =
      "我可以给你看三个选项：Panadol 八美元用于疼痛和发烧，Nurofen 十二美元用于疼痛和炎症。";
    const flow = [
      runtimeEvent("transcript.final", "evt-retain-source", 1, {
        utteranceId: "utt-retain-source",
        speaker: "pharmacist",
        language: "en",
        text:
          "I can show you three options. Panadol costs eight dollars and is for pain and fever. Nurofen costs twelve dollars.",
        revision: 1,
      }),
      translationEvent("evt-retain-translation", 2, translatedText),
      runtimeEvent("route.decision", "evt-retain-route", 3, {
        sourceTranscriptEventId: "evt-retain-source",
        routeType: "pharmacy_risk",
        confidence: 0.9,
        reasonCode: "pharmacy_term",
      }),
      runtimeEvent("cards.render", "evt-retain-cards", 4, {
        cardSet: {
          cardSetId: "set-retain",
          revision: 1,
          cards: [
            {
              cardId: "card-retain-1",
              zhText: "请药师写下药品名称和剂量。",
              enText: "Could you please write down the product names and doses?",
              riskLevel: "normal",
              actionType: "speak",
            },
          ],
        },
      }),
      runtimeEvent("audio.listening", "evt-retain-listening", 5, { active: true }),
    ];

    render(<ConversationPage runtime={new MockConversationRuntime(flow)} sessionId="ses-retain" />);

    const subtitle = await screen.findByLabelText("忠实中文翻译");
    expect(within(subtitle).getByText(translatedText)).toBeInTheDocument();
    expect(subtitle).not.toHaveTextContent("中文翻译会显示在这里");
  });

  it("shows only the latest faithful translation in the large-print main area", async () => {
    const firstTranslation = "早上好。你今天怎么样？";
    const secondTranslation = "您有任何药物过敏吗？";
    const flow = [
      runtimeEvent("transcript.final", "evt-latest-source-1", 1, {
        utteranceId: "utt-latest-1",
        speaker: "pharmacist",
        language: "en",
        text: "Good morning. How are you today?",
        revision: 1,
      }),
      runtimeEvent("translation.final", "evt-latest-translation-1", 2, {
        sourceTranscriptEventId: "evt-latest-source-1",
        segmentId: "seg-latest-1",
        sourceLanguage: "en",
        targetLanguage: "zh_cn",
        translatedText: firstTranslation,
        mode: "faithful",
        appendOnly: true,
        latencyMs: 10,
      }),
      runtimeEvent("transcript.final", "evt-latest-source-2", 3, {
        utteranceId: "utt-latest-2",
        speaker: "pharmacist",
        language: "en",
        text: "Do you have any drug allergies?",
        revision: 1,
      }),
      runtimeEvent("translation.final", "evt-latest-translation-2", 4, {
        sourceTranscriptEventId: "evt-latest-source-2",
        segmentId: "seg-latest-2",
        sourceLanguage: "en",
        targetLanguage: "zh_cn",
        translatedText: secondTranslation,
        mode: "faithful",
        appendOnly: true,
        latencyMs: 10,
      }),
    ];

    render(<ConversationPage runtime={new MockConversationRuntime(flow)} sessionId="ses-latest-only" />);

    const subtitle = await screen.findByLabelText("忠实中文翻译");
    expect(within(subtitle).queryByText(firstTranslation)).not.toBeInTheDocument();
    expect(within(subtitle).getByText(secondTranslation)).toBeInTheDocument();
    expect(screen.getAllByText(firstTranslation).length).toBeGreaterThan(0);
  });

  it("keeps product options in the main workspace with the translation after product.options.render", async () => {
    const translatedText =
      "药师说 Panadol 八美元用于疼痛和发烧；Nurofen 十二美元用于疼痛和炎症，但服用降压药时要先询问。";
    const flow = [
      runtimeEvent("transcript.final", "evt-products-natural-source", 1, {
        utteranceId: "utt-products-natural",
        speaker: "pharmacist",
        language: "en",
        text:
          "I can show you three options. Panadol costs eight dollars and is for pain and fever. Nurofen costs twelve dollars and is for pain and inflammation, but please check with me if you take blood pressure medicine.",
        revision: 1,
      }),
      translationEvent("evt-products-natural-translation", 2, translatedText),
      runtimeEvent("product.options.render", "evt-products-natural-table", 3, {
        options: [
          {
            name: "Panadol",
            price: "8 dollars",
            pharmacistStatedUse: "pain and fever",
            pharmacistStatedDirections: null,
            pharmacistStatedCautions: null,
          },
          {
            name: "Nurofen",
            price: "12 dollars",
            pharmacistStatedUse: "pain and inflammation",
            pharmacistStatedDirections: null,
            pharmacistStatedCautions: "check with me if you take blood pressure medicine",
          },
        ],
      }),
    ];

    render(<ConversationPage runtime={new MockConversationRuntime(flow)} sessionId="ses-products-main" />);

    const subtitle = await screen.findByLabelText("忠实中文翻译");
    expect(within(subtitle).getByText(translatedText)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "药师说的产品选项" })).toBeInTheDocument();
    expect(screen.getByText("Panadol")).toBeInTheDocument();
    expect(screen.getByText("8 dollars")).toBeInTheDocument();
    expect(screen.getByText("check with me if you take blood pressure medicine")).toBeInTheDocument();
  });

  it("returns to a stable listening state after passive translation without cards", async () => {
    const translatedText = "早上好。你今天怎么样？";
    const flow = [
      runtimeEvent("transcript.final", "evt-passive-source", 1, {
        utteranceId: "utt-passive-source",
        speaker: "pharmacist",
        language: "en",
        text: "Good morning. How are you today?",
        revision: 1,
      }),
      translationEvent("evt-passive-translation", 2, translatedText),
      runtimeEvent("route.decision", "evt-passive-route", 3, {
        sourceTranscriptEventId: "evt-passive-source",
        routeType: "passive_translation",
        confidence: 0.96,
        reasonCode: "routine_translation",
      }),
    ];

    render(<ConversationPage runtime={new MockConversationRuntime(flow)} sessionId="ses-passive" />);

    const subtitle = await screen.findByLabelText("忠实中文翻译");
    expect(within(subtitle).getByText(translatedText)).toBeInTheDocument();
    expect(screen.getByText("Voice Ready")).toBeInTheDocument();
    expect(screen.queryByText("KK 正在帮您确认")).not.toBeInTheDocument();
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
