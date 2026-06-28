import type {
  ConversationTurnView,
  TranslationSegmentView,
} from "../features/conversation/viewModels";


interface TwoLayerSubtitleProps {
  partialEnglish: string;
  turns?: readonly ConversationTurnView[];
  chineseSegments: readonly TranslationSegmentView[];
}

export function TwoLayerSubtitle({
  partialEnglish,
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
    </section>
  );
}
