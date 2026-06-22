interface StartPageProps {
  onStart: () => void;
}

export function StartPage({ onStart }: StartPageProps) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-cool-canvas p-6 text-navy">
      <section className="w-full max-w-xl rounded-3xl border border-slate-200 bg-white p-8 shadow-sm sm:p-12">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Kith&amp;Kin</h1>
        <p className="mt-6 text-2xl font-semibold leading-relaxed">陪您听懂药剂师，也让每次表达都由您确认。</p>
        <p className="mt-4 text-lg leading-relaxed text-slate-600">开始后，KK 会聆听英文并显示大字中文翻译。涉及个人信息时会先提醒您。</p>
        <button type="button" onClick={onStart} className="mt-8 min-h-14 w-full rounded-2xl bg-teal-700 px-6 py-4 text-2xl font-bold text-white focus-visible:ring-4 focus-visible:ring-teal-300">
          开始药房对话
        </button>
        <p className="mt-5 text-base leading-relaxed text-slate-500">KK 不会自动说出或发送您的个人信息。</p>
      </section>
    </main>
  );
}
