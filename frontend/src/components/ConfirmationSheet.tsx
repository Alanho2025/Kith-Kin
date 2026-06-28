import type { ConfirmationView } from "../features/conversation/viewModels";


interface ConfirmationSheetProps {
  confirmation: ConfirmationView;
  onConfirm: () => void;
  onCancel: () => void;
  onSelfSpeak: () => void;
}

export function ConfirmationSheet({
  confirmation,
  onConfirm,
  onCancel,
  onSelfSpeak,
}: ConfirmationSheetProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-navy/55 p-0 sm:items-center sm:p-6">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirmation-title"
        className="w-full max-w-2xl rounded-t-3xl bg-white p-6 shadow-2xl sm:rounded-3xl sm:p-8"
      >
        <div className="mx-auto mb-5 h-1.5 w-14 rounded-full bg-slate-300 sm:hidden" />
        <h2 id="confirmation-title" className="text-center text-2xl font-bold text-navy sm:text-3xl">
          你要让我用英文说这句吗？
        </h2>
        <p className="mt-3 text-center text-lg leading-relaxed text-slate-600">
          确认后 KK 才会替您说给药剂师听。
        </p>
        <blockquote className="my-6 rounded-2xl border border-teal-300 bg-teal-50 p-5 text-2xl font-bold leading-relaxed text-navy">
          {confirmation.card.zhText}
          <span className="mt-3 block text-base font-semibold leading-relaxed text-slate-600">
            {confirmation.card.enText}
          </span>
        </blockquote>
        <div className="grid gap-3">
          <button type="button" onClick={onConfirm} className="min-h-12 rounded-xl bg-teal-700 px-5 py-3 text-xl font-bold text-white focus-visible:ring-4 focus-visible:ring-teal-300">
            替我说
          </button>
          <button type="button" onClick={onCancel} className="min-h-12 rounded-xl border-2 border-slate-300 px-5 py-3 text-xl font-semibold text-red-700 focus-visible:ring-4 focus-visible:ring-red-200">
            重选
          </button>
          <button type="button" onClick={onSelfSpeak} className="min-h-12 rounded-xl border-2 border-slate-300 px-5 py-3 text-xl font-semibold text-navy focus-visible:ring-4 focus-visible:ring-slate-300">
            我自己说 / 取消
          </button>
        </div>
      </section>
    </div>
  );
}
