import type { VisitSummaryView } from "../features/conversation/viewModels";


interface VisitSummaryPageProps {
  summary: VisitSummaryView;
  onSend: () => void;
  onSave: () => void;
  onCancel: () => void;
}

export function VisitSummaryPage({ summary, onSend, onSave, onCancel }: VisitSummaryPageProps) {
  return (
    <main className="min-h-screen bg-cool-canvas p-5 text-navy sm:p-8">
      <section className="mx-auto max-w-2xl bg-white p-6 sm:rounded-3xl sm:border sm:border-slate-200 sm:p-10">
        <h1 className="text-3xl font-bold">{summary.titleZh || "今天药局沟通重点"}</h1>
        <div className="mt-7 divide-y divide-slate-200">
          <SummarySection title="提到的药" items={summary.mentionedDrugs} />
          <SummarySection title="药剂师建议" items={[summary.pharmacistAdviceSummaryZh]} />
          <SummarySection title="需要家人跟进" items={summary.unresolvedQuestionsZh} />
          <SummarySection title="KK 已提醒的问题" items={summary.unresolvedQuestionsZh} />
        </div>
        <div className="mt-8 grid gap-3">
          <button type="button" onClick={onSend} className="min-h-12 rounded-xl bg-teal-700 px-5 py-3 text-xl font-bold text-white">发送给家人</button>
          <button type="button" onClick={onSave} className="min-h-12 rounded-xl border-2 border-slate-300 px-5 py-3 text-xl font-semibold">只保存，不发送</button>
          <button type="button" onClick={onCancel} className="min-h-12 rounded-xl border-2 border-slate-300 px-5 py-3 text-xl font-semibold text-red-700">取消</button>
        </div>
      </section>
    </main>
  );
}

function SummarySection({ title, items }: { title: string; items: readonly string[] }) {
  return (
    <section className="py-5">
      <h2 className="text-xl font-bold">{title}</h2>
      <ul className="mt-2 list-disc space-y-2 pl-6 text-lg leading-relaxed text-slate-700">
        {items.length ? items.map((item) => <li key={item}>{item}</li>) : <li>没有需要补充的内容</li>}
      </ul>
    </section>
  );
}
