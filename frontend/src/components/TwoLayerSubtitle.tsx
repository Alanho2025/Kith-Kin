import type {
  ConversationTurnView,
  TranslationSegmentView,
} from "../features/conversation/viewModels";


interface TwoLayerSubtitleProps {
  partialEnglish: string;
  turns: readonly ConversationTurnView[];
  chineseSegments: readonly TranslationSegmentView[];
}

export function TwoLayerSubtitle({
  partialEnglish,
  turns,
  chineseSegments,
}: TwoLayerSubtitleProps) {
  return (
    <section className="space-y-5" aria-label="对话翻译">
      <p className="min-h-6 text-base font-medium leading-relaxed text-slate-500" aria-label="英文原文">
        {partialEnglish || "等待药剂师说话…"}
      </p>
      <div
        className="space-y-4 text-3xl font-bold leading-snug tracking-tight text-navy sm:text-4xl lg:text-5xl"
        aria-label="忠实中文翻译"
        aria-live="polite"
      >
        {chineseSegments.length === 0 ? (
          <p className="text-slate-400">中文翻译会显示在这里</p>
        ) : (
          chineseSegments.map((segment) => (
            <p key={segment.segmentId}>{segment.translatedText}</p>
          ))
        )}
      </div>
      {turns.length > 0 ? (
        <div className="space-y-3 border-t border-slate-200 pt-5" aria-label="完整对话">
          {turns.map((turn) => (
            <article key={turn.transcriptEventId} className="space-y-1">
              <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                {turn.speaker === "pharmacist" ? "Pharmacist" : "Parent"}
              </p>
              <p className="text-lg font-semibold leading-relaxed text-slate-800">
                {turn.sourceText}
              </p>
              {turn.translatedText ? (
                <p className="text-xl font-bold leading-relaxed text-navy">
                  {turn.translatedText}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
