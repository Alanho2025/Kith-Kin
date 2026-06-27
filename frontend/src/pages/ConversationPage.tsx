import { useState } from "react";
import { BottomControls } from "../components/BottomControls";
import { ConfirmationSheet } from "../components/ConfirmationSheet";
import { GuardianWarningCard } from "../components/GuardianWarningCard";
import { ResponseCard } from "../components/ResponseCard";
import { StatusBar } from "../components/StatusBar";
import { TwoLayerSubtitle } from "../components/TwoLayerSubtitle";
import { useCardConfirmation } from "../features/conversation/hooks/useCardConfirmation";
import { useLiveConversation } from "../features/conversation/hooks/useLiveConversation";
import type { ConversationRuntime } from "../features/conversation/runtime/ConversationRuntime";
import type { RuntimeCommandView } from "../features/conversation/viewModels";
import { VisitSummaryPage } from "./VisitSummaryPage";


export interface ConversationPageProps {
  runtime: ConversationRuntime;
  sessionId: string;
  isMock?: boolean;
  onRestart?: () => void;
}

export function ConversationPage({
  runtime,
  sessionId,
  onRestart,
}: ConversationPageProps) {
  const { state, sendCommand, dismissConfirmation } = useLiveConversation(runtime, sessionId);
  const [inputText, setInputText] = useState("");

  const { selectCard, confirm, cancel } = useCardConfirmation(
    state.activeCardSet,
    state.confirmation,
    sendCommand,
    dismissConfirmation,
  );

  const dispatchControl = (command: RuntimeCommandView) => {
    void sendCommand(command);
  };
  const selfSpeak = () => {
    dismissConfirmation();
    void sendCommand({ eventType: "control.self_speak", payload: {} });
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

  return (
    <main className="min-h-screen bg-cool-canvas text-navy">
      <StatusBar status={state.status} />
      <div className="mx-auto grid max-w-screen-2xl lg:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="hidden border-r border-slate-200 bg-white px-6 py-8 lg:block" aria-label="最近的对话">
          <h2 className="text-xl font-bold">最近的对话</h2>
          <div className="mt-5 space-y-4">
            {state.turns.map((turn) => (
              <div key={turn.transcriptEventId} className="border-b border-slate-200 pb-4">
                <p className="text-sm font-bold text-slate-400">
                  {turn.speaker === "pharmacist" ? "药剂师 (Pharmacist)" : "您 (Parent)"}
                </p>
                <p className="text-lg font-semibold leading-relaxed">
                  {turn.translatedText || turn.sourceText}
                </p>
              </div>
            ))}
          </div>
        </aside>
        <div className="flex min-h-[calc(100vh-5rem)] flex-col bg-white">
          <div className="flex-1 space-y-6 px-5 py-7 sm:px-8 lg:px-12 lg:py-10">
            <form onSubmit={handleSendText} className="mb-6 flex gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="⌨️ 語音無效時的替代文字輸入（例如：Do you have any drug allergies?）"
                className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2 text-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
              <button
                type="submit"
                className="rounded-xl bg-teal-700 px-6 py-2 text-lg font-bold text-white hover:bg-teal-800 transition focus:outline-none focus:ring-2 focus:ring-teal-300"
              >
                发送
              </button>
            </form>

            <TwoLayerSubtitle
              partialEnglish={state.partialEnglish}
              chineseSegments={state.chineseSegments}
            />

            {state.activeCardSet && !state.guardianWarning ? (
              <section className="rounded-2xl bg-teal-50 px-5 py-4 text-lg font-semibold leading-relaxed text-navy" aria-label="KK 提醒">
                KK 正在帮您检查过敏和用药记录。
              </section>
            ) : null}

            {state.guardianWarning ? (
              <GuardianWarningCard warning={state.guardianWarning} />
            ) : null}

            {state.visibleError ? (
              <section role="status" className="rounded-2xl border-2 border-amber-400 bg-amber-50 p-5 text-lg font-semibold leading-relaxed">
                {state.visibleError.messageZh}
              </section>
            ) : null}

            {state.activeCardSet ? (
              <section className="space-y-3" aria-label="回应选择">
                {state.activeCardSet.cards.map((card) => (
                  <ResponseCard key={card.cardId} card={card} onSelect={(selected) => void selectCard(selected)} />
                ))}
              </section>
            ) : null}
          </div>
          <BottomControls onCommand={dispatchControl} />
        </div>
      </div>

      {state.confirmation ? (
        <ConfirmationSheet
          confirmation={state.confirmation}
          onConfirm={() => void confirm()}
          onCancel={() => void cancel()}
          onSelfSpeak={selfSpeak}
        />
      ) : null}
    </main>
  );
}
