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


export interface ConversationPageProps {
  runtime: ConversationRuntime;
  sessionId: string;
}

export function ConversationPage({ runtime, sessionId }: ConversationPageProps) {
  const { state, sendCommand, dismissConfirmation } = useLiveConversation(runtime, sessionId);
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

  return (
    <main className="min-h-screen bg-cool-canvas text-navy">
      <StatusBar status={state.status} />
      <div className="mx-auto grid max-w-screen-2xl lg:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="hidden border-r border-slate-200 bg-white px-6 py-8 lg:block" aria-label="最近的对话">
          <h2 className="text-xl font-bold">最近的对话</h2>
          <div className="mt-5 space-y-4">
            {state.chineseSegments.map((segment) => (
              <p key={segment.segmentId} className="border-b border-slate-200 pb-4 text-lg font-semibold leading-relaxed">
                {segment.translatedText}
              </p>
            ))}
          </div>
        </aside>
        <div className="flex min-h-[calc(100vh-5rem)] flex-col bg-white">
          <div className="flex-1 space-y-6 px-5 py-7 sm:px-8 lg:px-12 lg:py-10">
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
