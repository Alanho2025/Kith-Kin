import type { RuntimeCommandView } from "../features/conversation/viewModels";


interface BottomControlsProps {
  onCommand: (command: RuntimeCommandView) => void;
}

const CONTROL_CLASS =
  "min-h-12 rounded-xl px-3 py-3 text-lg font-bold transition focus:outline-none focus-visible:ring-4 sm:text-xl";

export function BottomControls({ onCommand }: BottomControlsProps) {
  const endSession = () => {
    if (window.confirm("确定结束本次药房对话？")) {
      onCommand({ eventType: "session.end", payload: { reason: "user_completed" } });
    }
  };

  return (
    <nav className="grid grid-cols-2 gap-3 border-t border-slate-200 bg-white p-4 sm:grid-cols-4" aria-label="对话控制">
      <button type="button" className={`${CONTROL_CLASS} bg-teal-700 text-white focus-visible:ring-teal-300`} onClick={() => onCommand({ eventType: "control.self_speak", payload: {} })}>
        我自己说
      </button>
      <button type="button" className={`${CONTROL_CLASS} bg-amber-300 text-navy focus-visible:ring-amber-200`} onClick={() => onCommand({ eventType: "control.please_wait", payload: {} })}>
        请稍等
      </button>
      <button type="button" className={`${CONTROL_CLASS} bg-slate-100 text-navy focus-visible:ring-slate-300`} onClick={() => onCommand({ eventType: "control.repeat", payload: { target: "last_translation" } })}>
        重复
      </button>
      <button type="button" className={`${CONTROL_CLASS} bg-red-600 text-white focus-visible:ring-red-300`} onClick={endSession}>
        结束
      </button>
    </nav>
  );
}
