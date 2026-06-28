import type { ResponseCardView } from "../features/conversation/viewModels";


interface ResponseCardProps {
  card: ResponseCardView;
  onSelect: (card: ResponseCardView) => void;
  intentLabel?: string;
  recommended?: boolean;
}

export function ResponseCard({
  card,
  onSelect,
  intentLabel = "安全回应",
  recommended = false,
}: ResponseCardProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(card)}
      className="group w-full rounded-2xl border-2 border-slate-200 bg-white px-5 py-5 text-left transition hover:border-teal-600 hover:bg-teal-50 focus:outline-none focus-visible:ring-4 focus-visible:ring-teal-300"
      aria-label={`${card.zhText}，点击后确认`}
    >
      <span className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-center">
        <span>
          <span className="mb-3 flex flex-wrap gap-2">
            <span className="rounded-full bg-teal-100 px-3 py-1 text-base font-bold text-teal-800">
              {intentLabel}
            </span>
            {recommended ? (
              <span className="rounded-full bg-amber-100 px-3 py-1 text-base font-bold text-amber-800">
                推荐
              </span>
            ) : null}
          </span>
          <span className="block text-2xl font-bold leading-snug text-navy">{card.zhText}</span>
          <span className="mt-2 block text-base leading-relaxed text-slate-500">{card.enText}</span>
        </span>
        <span className="border-t border-slate-200 pt-3 text-lg font-semibold text-navy sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0">
          点击后确认
        </span>
      </span>
    </button>
  );
}
