import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { conversationReducer, initialConversationState } from "../features/conversation/reducer";
import { TwoLayerSubtitle } from "./TwoLayerSubtitle";
import { makeEvent } from "../test/fixtures/runtime-events";


describe("TwoLayerSubtitle", () => {
  it("replaces partial and appends finals", () => {
    const firstPartial = conversationReducer(
      initialConversationState,
      makeEvent("transcript.partial", "evt-partial-1", {
        utteranceId: "utt-1",
        speaker: "pharmacist",
        language: "en",
        text: "Are you taking",
        revision: 1,
      }),
    );
    const replacedPartial = conversationReducer(
      firstPartial,
      makeEvent("transcript.partial", "evt-partial-2", {
        utteranceId: "utt-1",
        speaker: "pharmacist",
        language: "en",
        text: "Are you taking any medicine?",
        revision: 2,
      }),
    );
    const firstFinal = conversationReducer(
      replacedPartial,
      makeEvent("translation.final", "evt-translation-1", {
        sourceTranscriptEventId: "evt-source-1",
        segmentId: "segment-1",
        sourceLanguage: "en",
        targetLanguage: "zh_cn",
        translatedText: "您有在服用任何药物吗？",
        mode: "faithful",
        appendOnly: true,
        latencyMs: 220,
      }),
    );
    const secondFinal = conversationReducer(
      firstFinal,
      makeEvent("translation.final", "evt-translation-2", {
        sourceTranscriptEventId: "evt-source-2",
        segmentId: "segment-2",
        sourceLanguage: "en",
        targetLanguage: "zh_cn",
        translatedText: "请告诉我药名。",
        mode: "faithful",
        appendOnly: true,
        latencyMs: 180,
      }),
    );

    render(
      <TwoLayerSubtitle
        partialEnglish={secondFinal.partialEnglish}
        turns={secondFinal.turns}
        chineseSegments={secondFinal.chineseSegments}
      />,
    );

    expect(screen.queryByText("Are you taking")).not.toBeInTheDocument();
    expect(screen.getByText("Are you taking any medicine?")).toBeInTheDocument();
    expect(screen.getByText("您有在服用任何药物吗？")).toBeInTheDocument();
    expect(screen.getByText("请告诉我药名。")).toBeInTheDocument();
  });
});
