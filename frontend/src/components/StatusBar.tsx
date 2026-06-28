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

export interface StatusBarProps {
  status: ConversationStatus;
  onToggleDevMode?: () => void;
}

export function StatusBar({ status, onToggleDevMode }: StatusBarProps) {
  const getStatusPillConfig = (currentStatus: ConversationStatus) => {
    switch (currentStatus) {
      case "listening":
      case "idle":
        return {
          text: "Voice Ready",
          className: "bg-green-50 text-green-700 border-green-200",
        };
      case "speaking":
        return {
          text: "KK Speaking",
          className: "bg-sky-50 text-sky-700 border-sky-200",
        };
      case "blocked":
        return {
          text: "Security Alert",
          className: "bg-red-50 text-red-700 border-red-200 animate-pulse",
        };
      case "reconnecting":
        return {
          text: "Reconnecting",
          className: "bg-amber-50 text-amber-700 border-amber-200 animate-pulse",
        };
      case "error":
        return {
          text: "System Error",
          className: "bg-red-50 text-red-700 border-red-200",
        };
      default:
        return {
          text: STATUS_LABELS[currentStatus] || "Active",
          className: "bg-slate-50 text-slate-700 border-slate-200",
        };
    }
  };

  const pill = getStatusPillConfig(status);

  return (
    <header className="flex min-h-16 items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-3 shadow-sm sm:px-8">
      <button
        type="button"
        onClick={onToggleDevMode}
        data-testid="dev-mode-toggle"
        className="flex items-center gap-3 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 rounded-lg p-1"
        aria-label="Kith&Kin 药房陪伴助手"
      >
        <div className="h-8 w-8 rounded-full border border-sky-400 bg-sky-50 flex items-center justify-center text-sky-600 font-bold text-sm" aria-hidden="true">
          KK
        </div>
        <span className="text-lg sm:text-xl font-bold text-navy">Kith&amp;Kin 药房陪伴助手</span>
      </button>

      <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
        <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs sm:text-sm font-semibold text-slate-600">
          Current: Pharmacy visit
        </span>
        <span className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs sm:text-sm font-semibold text-slate-600">
          English ↔ 中文
        </span>
        <span className={`rounded-full border px-3 py-1.5 text-xs sm:text-sm font-bold transition-colors ${pill.className}`}>
          {pill.text}
        </span>
        <button
          type="button"
          className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs sm:text-sm font-semibold text-slate-600 hover:bg-slate-50 transition active:scale-95"
        >
          Settings
        </button>
      </div>
    </header>
  );
}
