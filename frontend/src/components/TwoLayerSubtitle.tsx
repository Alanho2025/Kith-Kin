import type {
  TranslationSegmentView,
} from "../features/conversation/viewModels";


interface TwoLayerSubtitleProps {
  partialEnglish: string;
  chineseSegments: readonly TranslationSegmentView[];
}

export function TwoLayerSubtitle({
  partialEnglish,
  chineseSegments,
}: TwoLayerSubtitleProps) {
  const latestChineseSegment = chineseSegments.at(-1);

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
        {latestChineseSegment ? (
          <p key={latestChineseSegment.segmentId}>{latestChineseSegment.translatedText}</p>
        ) : (
          <p className="text-slate-400">中文翻译会显示在这里</p>
        )}
      </div>
    </section>
  );
}
