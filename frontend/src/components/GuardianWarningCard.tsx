import type { GuardianWarningView } from "../features/conversation/viewModels";


export function GuardianWarningCard({ warning }: { warning: GuardianWarningView }) {
  return (
    <section role="alert" className="rounded-2xl border-2 border-amber-400 bg-amber-50 p-5 text-navy">
      <p className="text-base font-bold text-amber-700">隐私提醒</p>
      <h2 className="mt-1 text-2xl font-bold">{warning.zhTitle}</h2>
      <p className="mt-2 text-lg leading-relaxed">{warning.zhMessage}</p>
    </section>
  );
}
