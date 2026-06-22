import { makeEvent } from "./runtime-events";


export const mockPharmacyFlow = [
  makeEvent("session.ready", "evt-ready", { nextSequence: 1 }),
  makeEvent("audio.listening", "evt-listening", { active: true }),
  makeEvent("transcript.partial", "evt-partial", {
    utteranceId: "utt-1",
    speaker: "pharmacist",
    language: "en",
    text: "Are you taking any blood pressure medicine?",
    revision: 1,
  }),
  makeEvent("translation.final", "evt-translation", {
    sourceTranscriptEventId: "evt-final",
    segmentId: "segment-1",
    sourceLanguage: "en",
    targetLanguage: "zh_cn",
    translatedText: "您有在服用降压药吗？",
    mode: "faithful",
    appendOnly: true,
    latencyMs: 220,
  }),
  makeEvent("cards.render", "evt-cards", {
    cardSet: {
      cardSetId: "set-1",
      revision: 1,
      cards: [
        {
          cardId: "card-1",
          zhText: "请帮我确认这个药会不会和我现在吃的降血压药冲突。",
          enText: "Could you check whether this conflicts with my blood pressure medicine?",
          riskLevel: "medical",
          actionType: "speak",
        },
        {
          cardId: "card-2",
          zhText: "请把药名写下来。",
          enText: "Please write down the medicine name.",
          riskLevel: "normal",
          actionType: "show_to_pharmacist",
        },
      ],
    },
  }),
];
