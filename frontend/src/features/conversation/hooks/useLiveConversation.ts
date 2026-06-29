import { useCallback, useEffect, useReducer } from "react";

import { conversationReducer, initialConversationState } from "../reducer";
import type { ConversationRuntime } from "../runtime/ConversationRuntime";
import type { MicrophoneModeView, RuntimeCommandView } from "../viewModels";


export function useLiveConversation(runtime: ConversationRuntime, sessionId: string) {
  const [state, dispatch] = useReducer(conversationReducer, initialConversationState);

  useEffect(() => {
    const unsubscribe = runtime.subscribe(dispatch);
    void runtime.connect(sessionId);
    return () => {
      unsubscribe();
      void runtime.disconnect();
    };
  }, [runtime, sessionId]);

  const sendCommand = useCallback(
    (command: RuntimeCommandView) => runtime.sendCommand(command),
    [runtime],
  );

  const setMicrophoneEnabled = useCallback(
    (enabled: boolean) => runtime.setMicrophoneEnabled(enabled),
    [runtime],
  );

  const setMicrophoneMode = useCallback(
    (mode: MicrophoneModeView) => runtime.setMicrophoneMode(mode),
    [runtime],
  );

  const dismissConfirmation = useCallback(() => {
    dispatch({ type: "dismiss_confirmation" });
  }, []);

  return { state, sendCommand, setMicrophoneEnabled, setMicrophoneMode, dismissConfirmation };
}
