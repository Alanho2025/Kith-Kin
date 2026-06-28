import { useState, useEffect } from "react";
import { BottomControls } from "../components/BottomControls";
import { GuardianWarningCard } from "../components/GuardianWarningCard";
import { ResponseCard } from "../components/ResponseCard";
import { StatusBar } from "../components/StatusBar";
import { TwoLayerSubtitle } from "../components/TwoLayerSubtitle";
import { useCardConfirmation } from "../features/conversation/hooks/useCardConfirmation";
import { useLiveConversation } from "../features/conversation/hooks/useLiveConversation";
import type { ConversationRuntime } from "../features/conversation/runtime/ConversationRuntime";
import type { ConversationTurnView, RuntimeCommandView } from "../features/conversation/viewModels";
import { VisitSummaryPage } from "./VisitSummaryPage";


export interface ConversationPageProps {
  runtime: ConversationRuntime;
  sessionId: string;
  isMock?: boolean;
  onRestart?: () => void;
}

type ActiveMicMode = "pharmacist" | "parent" | null;

const CARD_INTENT_LABELS = ["确认理解", "问清楚", "请慢一点"];

function ConversationLog({ turns }: { turns: readonly ConversationTurnView[] }) {
  if (turns.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-4 text-base text-slate-500">
        开始收听后，这里会显示本轮 session 的上下文。
      </p>
    );
  }

  // Deduplicate adjacent turns with identical sourceText or translatedText
  const deduplicatedTurns: ConversationTurnView[] = [];
  for (const turn of turns) {
    const prev = deduplicatedTurns[deduplicatedTurns.length - 1];
    if (
      prev &&
      ((prev.sourceText === turn.sourceText && turn.sourceText) ||
        (prev.translatedText === turn.translatedText && turn.translatedText))
    ) {
      continue;
    }
    deduplicatedTurns.push(turn);
  }

  return (
    <>
      {deduplicatedTurns.map((turn) => {
        const isPharmacist = turn.speaker === "pharmacist";
        return (
          <article
            key={turn.transcriptEventId}
            className={`max-w-[92%] rounded-lg border px-4 py-3 ${
              isPharmacist
                ? "mr-auto border-slate-200 bg-slate-50"
                : "ml-auto border-teal-200 bg-teal-50"
            }`}
          >
            <p className="text-sm font-bold text-slate-500">
              {isPharmacist ? "医护人员" : "老人 / KK"}
            </p>
            <p className="mt-1 text-lg font-bold leading-relaxed text-navy">
              {turn.translatedText || turn.sourceText}
            </p>
            {turn.translatedText ? (
              <p className="mt-2 text-sm leading-relaxed text-slate-500">
                {turn.sourceText}
              </p>
            ) : null}
          </article>
        );
      })}
    </>
  );
}

function isSystemThoughtText(text: string | null | undefined): boolean {
  if (!text) return false;
  return text.includes("**") || text.startsWith("Analyzing") || text.startsWith("Awaiting");
}

export function ConversationPage({
  runtime,
  sessionId,
  onRestart,
}: ConversationPageProps) {
  const { state, sendCommand, setMicrophoneEnabled, dismissConfirmation } = useLiveConversation(runtime, sessionId);
  const [inputText, setInputText] = useState("");
  const [activeMicMode, setActiveMicMode] = useState<ActiveMicMode>(null);
  const [devMode, setDevMode] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const { selectCard, confirm, cancel } = useCardConfirmation(
    state.activeCardSet,
    state.confirmation,
    sendCommand,
    dismissConfirmation,
  );

  const [isActionLocked, setIsActionLocked] = useState(false);

  const handleConfirm = async () => {
    setIsActionLocked(true);
    try {
      await confirm();
    } finally {
      setIsActionLocked(false);
    }
  };

  const handleCancel = async () => {
    setIsActionLocked(true);
    try {
      await cancel();
    } finally {
      setIsActionLocked(false);
    }
  };

  const handleSelfSpeak = () => {
    setIsActionLocked(true);
    try {
      selfSpeak();
    } finally {
      setIsActionLocked(false);
    }
  };

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        setMicrophoneEnabled(activeMicMode !== null);
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [activeMicMode, setMicrophoneEnabled]);

  const dispatchControl = (command: RuntimeCommandView) => {
    void sendCommand(command);
  };
  const selfSpeak = () => {
    dismissConfirmation();
    void sendCommand({ eventType: "control.self_speak", payload: {} });
  };
  const setMicrophoneMode = (mode: ActiveMicMode) => {
    setActiveMicMode(mode);
    setMicrophoneEnabled(mode !== null);
  };
  const togglePharmacistMic = () => {
    setMicrophoneMode(activeMicMode === "pharmacist" ? null : "pharmacist");
  };
  const startParentMic = () => setMicrophoneMode("parent");
  const stopParentMic = () => setMicrophoneMode(null);
  const triggerRepeat = () => {
    void sendCommand({
      eventType: "control.repeat",
      payload: { target: "last_translation" },
    });
  };

  const handleSendText = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    void sendCommand({
      eventType: "transcript.final",
      payload: {
        utteranceId: `utt-${Date.now()}`,
        speaker: "pharmacist",
        language: "en",
        text: inputText.trim(),
        revision: 1,
      },
    });
    setInputText("");
  };

  if (state.summary) {
    return (
      <VisitSummaryPage
        summary={state.summary}
        onSend={onRestart || (() => {})}
        onSave={onRestart || (() => {})}
        onCancel={onRestart || (() => {})}
      />
    );
  }

  const isReceivingSpeech = state.status === "transcribing" || state.status === "translating";
  const hasConfirmation = Boolean(state.confirmation);
  const filteredTurns = state.turns.filter((turn) => {
    if (devMode) return true;
    return !isSystemThoughtText(turn.sourceText) && !isSystemThoughtText(turn.translatedText);
  });

  const filteredChineseSegments = state.chineseSegments.filter((seg) => {
    if (devMode) return true;
    return !isSystemThoughtText(seg.translatedText);
  });

  const filteredPartialEnglish =
    !devMode && isSystemThoughtText(state.partialEnglish)
      ? ""
      : state.partialEnglish;

  const showResponseCards = Boolean(
    state.activeCardSet &&
    !state.guardianWarning &&
    filteredChineseSegments.length > 0 &&
    !isReceivingSpeech &&
    !hasConfirmation,
  );

  // Derive active stage label and titles
  const mainStateLabel = hasConfirmation
    ? "确认代说"
    : showResponseCards
    ? "请选择回应"
    : activeMicMode === "parent"
    ? "正在听您说中文"
    : activeMicMode === "pharmacist"
    ? "正在听药剂师说话"
    : "正在听药剂师说话";

  const mainInstruction = hasConfirmation
    ? "你要让我用英文说这句吗？"
    : showResponseCards
    ? "点选一句安全回应。点选后还需要再次确认，KK 不会自动说出。"
    : "先听懂药剂师的话。翻译完成后，再选择一句安全回应。";

  return (
    <main className="min-h-screen bg-cool-canvas text-navy">
      <StatusBar status={state.status} onToggleDevMode={() => setDevMode((prev) => !prev)} />
      <div className="mx-auto grid max-w-screen-2xl gap-4 px-4 py-4 lg:grid-cols-[minmax(0,1fr)_28rem] lg:px-6">
        <section className="flex min-h-[calc(100vh-7rem)] flex-col rounded-lg border border-slate-200 bg-white" aria-label="实时药局对话">
          <div className="flex-1 space-y-6 px-5 py-6 sm:px-8 lg:px-10">
            <div className="rounded-lg border border-teal-200 bg-teal-50 p-4">
              <p className="text-sm font-bold uppercase text-teal-700">
                {mainStateLabel}
              </p>
              <h2 className="mt-1 text-3xl font-bold leading-tight text-navy">
                听懂药剂师，再安全回应
              </h2>
              <p className="mt-2 text-lg leading-relaxed text-slate-600">
                {mainInstruction}
              </p>
              <div className="mt-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <button
                  type="button"
                  onClick={togglePharmacistMic}
                  className={`min-h-16 rounded-2xl px-5 py-4 text-xl font-bold text-white shadow-sm focus:outline-none focus-visible:ring-4 ${
                    activeMicMode === "pharmacist"
                      ? "bg-red-600 focus-visible:ring-red-200"
                      : "bg-teal-700 focus-visible:ring-teal-300"
                  }`}
                  aria-pressed={activeMicMode === "pharmacist"}
                >
                  {activeMicMode === "pharmacist" ? "停止收听" : "听药剂师说话"}
                </button>
                <button
                  type="button"
                  onPointerDown={startParentMic}
                  onPointerUp={stopParentMic}
                  onPointerLeave={stopParentMic}
                  onKeyDown={(event) => {
                    if (event.key === " " || event.key === "Enter") startParentMic();
                  }}
                  onKeyUp={(event) => {
                    if (event.key === " " || event.key === "Enter") stopParentMic();
                  }}
                  className={`min-h-16 rounded-2xl border-2 px-5 py-4 text-xl font-bold focus:outline-none focus-visible:ring-4 ${
                    activeMicMode === "parent"
                      ? "border-red-500 bg-red-50 text-red-700 focus-visible:ring-red-200"
                      : "border-teal-700 bg-white text-teal-800 focus-visible:ring-teal-300"
                  }`}
                  aria-pressed={activeMicMode === "parent"}
                >
                  按住说中文
                </button>
                <button
                  type="button"
                  onClick={triggerRepeat}
                  className="min-h-16 rounded-2xl border-2 border-teal-700 bg-white text-teal-800 px-5 py-4 text-xl font-bold focus:outline-none focus-visible:ring-4 focus-visible:ring-teal-300"
                >
                  请药剂师再说一次
                </button>
              </div>
            </div>

            <TwoLayerSubtitle
              partialEnglish={filteredPartialEnglish}
              chineseSegments={filteredChineseSegments}
            />

            {/* State C: Inline Confirmation Panel */}
            {hasConfirmation && state.confirmation ? (
              <section
                role="dialog"
                aria-modal="true"
                aria-labelledby="confirmation-title"
                className="space-y-4 border border-teal-200 bg-teal-50/30 rounded-2xl p-6"
              >
                <div>
                  <p className="text-sm font-bold uppercase text-teal-700">
                    确认代说
                  </p>
                  <h2 id="confirmation-title" className="text-2xl font-bold text-navy">
                    你要让我用英文说这句吗？
                  </h2>
                  <p className="text-base text-slate-500">
                    确认后 KK 才会替您说给药剂师听。
                  </p>
                </div>
                <blockquote className="rounded-xl border border-teal-200 bg-white p-5 text-xl font-bold leading-relaxed text-navy">
                  {state.confirmation.card.zhText}
                  <span className="mt-3 block text-base font-semibold leading-relaxed text-slate-500">
                    {state.confirmation.card.enText}
                  </span>
                </blockquote>
                <div className="grid gap-3 sm:grid-cols-3">
                  <button
                    type="button"
                    onClick={() => { void handleConfirm(); }}
                    disabled={isActionLocked}
                    className="min-h-12 rounded-xl bg-teal-700 px-5 py-3 text-lg font-bold text-white transition hover:bg-teal-800 focus-visible:ring-4 focus-visible:ring-teal-300 disabled:opacity-50"
                  >
                    替我说
                  </button>
                  <button
                    type="button"
                    onClick={() => { void handleCancel(); }}
                    disabled={isActionLocked}
                    className="min-h-12 rounded-xl border-2 border-slate-300 bg-white px-5 py-3 text-lg font-semibold text-red-700 transition hover:bg-slate-50 focus-visible:ring-4 focus-visible:ring-red-200 disabled:opacity-50"
                  >
                    重选
                  </button>
                  <button
                    type="button"
                    onClick={handleSelfSpeak}
                    disabled={isActionLocked}
                    className="min-h-12 rounded-xl border-2 border-slate-300 bg-white px-5 py-3 text-lg font-semibold text-navy transition hover:bg-slate-50 focus-visible:ring-4 focus-visible:ring-slate-300 disabled:opacity-50"
                  >
                    取消
                  </button>
                </div>
              </section>
            ) : null}

            {/* State B: Card selection list */}
            {showResponseCards && state.activeCardSet ? (
              <section className="space-y-3" aria-label="选择安全回应">
                <div>
                  <p className="text-sm font-bold uppercase text-teal-700">
                    请选择回应
                  </p>
                  <h2 className="text-2xl font-bold text-navy">
                    一次只选一句，下一步再确认代说。
                  </h2>
                </div>
                {state.activeCardSet.cards.slice(0, 3).map((card, index) => (
                  <ResponseCard
                    key={card.cardId}
                    card={card}
                    intentLabel={CARD_INTENT_LABELS[index] ?? "安全回应"}
                    recommended={index === 0}
                    onSelect={(selected) => void selectCard(selected)}
                  />
                ))}
              </section>
            ) : null}

            {showResponseCards ? (
              <section className="rounded-lg border border-teal-200 bg-teal-50 px-5 py-4 text-lg font-semibold leading-relaxed text-navy" aria-label="安全检查状态">
                安全检查已完成。这句话只是确认理解，不替您做医疗判断。
              </section>
            ) : null}

            {/* Developer Mode Trace details */}
            {devMode ? (
              <details className="rounded-lg border border-slate-200 bg-slate-50 px-5 py-4" open>
                <summary className="cursor-pointer text-base font-bold text-slate-700">
                  安全检查详情
                </summary>
                <dl className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
                  <div>
                    <dt className="font-semibold text-slate-900">Router</dt>
                    <dd>{state.activeCardSet ? "pharmacy_conversation" : "waiting"}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-slate-900">Guardian</dt>
                    <dd>{state.guardianWarning ? "blocked" : "sanitized"}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-slate-900">Tools</dt>
                    <dd>{state.activeCardSet ? "visible after safe routing" : "none"}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-slate-900">Confirmation</dt>
                    <dd>{state.confirmation ? "required" : "none"}</dd>
                  </div>
                </dl>
              </details>
            ) : null}

            {/* Mobile conversation log drawer trigger */}
            <button
              type="button"
              onClick={() => setIsDrawerOpen(true)}
              className="lg:hidden w-full min-h-12 rounded-xl border-2 border-slate-300 bg-slate-50 hover:bg-slate-100 px-4 py-2 text-lg font-bold text-navy"
            >
              查看对话记录
            </button>

            {state.guardianWarning ? (
              <GuardianWarningCard warning={state.guardianWarning} />
            ) : null}

            {state.visibleError ? (
              <section role="status" className="rounded-lg border-2 border-amber-400 bg-amber-50 p-5 text-lg font-semibold leading-relaxed">
                {state.visibleError.messageZh}
              </section>
            ) : null}
          </div>
          <BottomControls onCommand={dispatchControl} />
        </section>

        <aside className="hidden min-h-[calc(100vh-7rem)] flex-col rounded-lg border border-slate-200 bg-white lg:flex" aria-label="对话记录">
          <div className="border-b border-slate-200 px-5 py-5">
            <h2 className="text-2xl font-bold">对话记录</h2>
            <p className="mt-1 text-base text-slate-500">
              中文为主，英文为辅，方便回看本轮上下文。
            </p>
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
            <ConversationLog turns={filteredTurns} />
          </div>
          <form onSubmit={handleSendText} className="border-t border-slate-200 p-4">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="语音无效时输入医护人员英文"
              className="min-h-12 w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
            <button
              type="submit"
              className="mt-3 min-h-12 w-full rounded-lg bg-teal-700 px-6 py-2 text-lg font-bold text-white transition hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-300"
            >
              发送
            </button>
          </form>
        </aside>
      </div>

      {/* Mobile Drawer Overlay - Rendered but visually hidden when closed to keep text in DOM for tests */}
      <div
        className={
          isDrawerOpen
            ? "fixed inset-0 z-40 bg-navy/55 flex justify-end lg:hidden"
            : "hidden"
        }
        role="complementary"
        aria-label="对话记录"
      >
        <div className="w-full max-w-md bg-white h-full flex flex-col p-5 shadow-2xl">
          <div className="flex items-center justify-between border-b pb-3">
            <h2 className="text-xl font-bold text-navy">对话记录</h2>
            <button
              type="button"
              onClick={() => setIsDrawerOpen(false)}
              className="text-slate-500 hover:text-navy font-bold text-xl px-2"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-y-auto space-y-4 py-4">
            <ConversationLog turns={filteredTurns} />
          </div>
        </div>
      </div>
    </main>
  );
}
