import type { RuntimeCommandView } from "../features/conversation/viewModels";
import { conversationDebug } from "../features/conversation/debugLog";


interface BottomControlsProps {
  onCommand: (command: RuntimeCommandView) => void;
}

const CONTROL_CLASS =
  "min-h-12 rounded-xl px-3 py-3 text-lg font-bold transition focus:outline-none focus-visible:ring-4 sm:text-xl";

export function BottomControls({ onCommand }: BottomControlsProps) {
  const endSession = () => {
    conversationDebug("bottom_controls.end.click");
    // End session is the only bottom control with a browser confirmation because
    // it moves the conversation into final summary/review.
    if (window.confirm("确定结束本次药房对话？")) {
      conversationDebug("bottom_controls.end.confirmed");
      onCommand({ eventType: "session.end", payload: { reason: "user_completed" } });
    } else {
      conversationDebug("bottom_controls.end.cancelled");
    }
  };

  return (
    <nav className="grid grid-cols-2 gap-3 border-t border-slate-200 bg-white p-4" aria-label="对话控制">
      <button type="button" className={`${CONTROL_CLASS} bg-amber-300 text-navy focus-visible:ring-amber-200`} onClick={() => {
        conversationDebug("bottom_controls.please_wait.click");
        onCommand({ eventType: "control.please_wait", payload: {} });
      }}>
        请稍等
      </button>
      <button type="button" className={`${CONTROL_CLASS} bg-red-600 text-white focus-visible:ring-red-300`} onClick={endSession}>
        结束
      </button>
    </nav>
  );
}
