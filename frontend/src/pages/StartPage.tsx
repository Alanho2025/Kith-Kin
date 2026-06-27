interface StartPageProps {
  onStart: () => void;
  isMock: boolean;
  onToggleMock: (isMock: boolean) => void;
}

export function StartPage({ onStart, isMock, onToggleMock }: StartPageProps) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-cool-canvas p-6 text-navy">
      <section className="w-full max-w-xl rounded-3xl border border-slate-200 bg-white p-8 shadow-sm sm:p-12">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Kith&amp;Kin</h1>
        <p className="mt-6 text-2xl font-semibold leading-relaxed">陪您听懂药剂师，也让每次表达都由您确认。</p>
        <p className="mt-4 text-lg leading-relaxed text-slate-600">开始后，KK 会聆听英文并显示大字中文翻译。涉及个人信息时会先提醒您。</p>
        
        {/* Segmented Toggle Control */}
        <div className="mt-8 rounded-xl bg-slate-100 p-1 flex">
          <button
            type="button"
            onClick={() => onToggleMock(true)}
            className={`flex-1 py-2 text-center rounded-lg font-bold text-lg transition-all ${
              isMock
                ? "bg-white text-teal-800 shadow-sm"
                : "text-slate-600 hover:text-navy"
            }`}
          >
            演示模式 (Mock)
          </button>
          <button
            type="button"
            onClick={() => onToggleMock(false)}
            className={`flex-1 py-2 text-center rounded-lg font-bold text-lg transition-all ${
              !isMock
                ? "bg-white text-teal-800 shadow-sm"
                : "text-slate-600 hover:text-navy"
            }`}
          >
            真实后端 (Backend)
          </button>
        </div>

        <p className="mt-3 text-sm text-slate-500 leading-relaxed">
          {isMock
            ? "💡 演示模式：使用内置的模拟对话流，不需要配置任何 API Key 或运行后端 Python。"
            : "⚡ 真实后端模式：连接到 Python 服务端，并调用真实的 Gemini API (需要配置 API Key)。"}
        </p>

        <button type="button" onClick={onStart} className="mt-6 min-h-14 w-full rounded-2xl bg-teal-700 px-6 py-4 text-2xl font-bold text-white focus-visible:ring-4 focus-visible:ring-teal-300">
          开始药房对话
        </button>
        <p className="mt-5 text-base leading-relaxed text-slate-500">KK 不会自动说出或发送您的个人信息。</p>
      </section>
    </main>
  );
}

