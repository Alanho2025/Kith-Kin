import { makeEvent } from "./runtime-events";


export const mockFallbackFlow = [
  makeEvent("translation.final", "evt-existing-translation", {
    sourceTranscriptEventId: "evt-old-final",
    segmentId: "segment-old",
    sourceLanguage: "en",
    targetLanguage: "zh_cn",
    translatedText: "上一句忠实翻译。",
    mode: "faithful",
    appendOnly: true,
    latencyMs: 180,
  }),
  makeEvent("transcript.final", "evt-failed-source", {
    utteranceId: "utt-fallback",
    speaker: "pharmacist",
    language: "en",
    text: "Please write down the medicine name.",
    revision: 1,
  }),
  makeEvent("fallback.show", "evt-fallback", {
    code: "TRANSLATION_UNAVAILABLE",
    messageZh: "中文翻译暂时不可用。KK 会继续显示英文原文，并尽快恢复中文。",
    messageEn: "Chinese translation is temporarily unavailable.",
    retryable: true,
    recoveryAction: "reconnect",
    relatedEventId: "evt-failed-source",
  }),
];
