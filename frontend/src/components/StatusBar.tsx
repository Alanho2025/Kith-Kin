import type { ConversationStatus } from "../features/conversation/viewModels";


const STATUS_LABELS: Record<ConversationStatus, string> = {
  idle: "准备好了",
  listening: "KK 正在聆听",
  transcribing: "正在识别语音",
  translating: "正在翻译",
  checking: "KK 正在帮您确认",
  needs_confirmation: "请您确认",
  speaking: "KK 正在说话",
  blocked: "KK 已为您拦截",
  error: "出现问题，请稍等",
  reconnecting: "网络不稳定，正在重连",
  ended: "对话已结束",
};

export function StatusBar({ status }: { status: ConversationStatus }) {
  return (
    <header className="flex min-h-20 items-center justify-between gap-4 bg-navy px-5 py-4 text-white sm:px-8">
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Kith&amp;Kin</h1>
      <div
        className="flex items-center gap-3 text-lg font-semibold text-teal-100 sm:text-xl"
        role="status"
        aria-live="polite"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-teal-600" aria-hidden="true">
          <span className="h-3 w-3 rounded-full bg-white" />
        </span>
        {STATUS_LABELS[status]}
      </div>
    </header>
  );
}
