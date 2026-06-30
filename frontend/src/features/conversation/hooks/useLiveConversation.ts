import { useCallback, useEffect, useReducer } from "react";

import { conversationReducer, initialConversationState } from "../reducer";
import type { ConversationRuntime } from "../runtime/ConversationRuntime";
import type { MicrophoneModeView, RuntimeCommandView } from "../viewModels";
import {
  conversationDebug,
  summarizeCommand,
  summarizeRuntimeEvent,
  summarizeState,
} from "../debugLog";


export function useLiveConversation(runtime: ConversationRuntime, sessionId: string) {
  const [state, dispatch] = useReducer(conversationReducer, initialConversationState);

  useEffect(() => {
    conversationDebug("hook.connect_effect.start", { sessionId });
    const unsubscribe = runtime.subscribe((event) => {
      conversationDebug("hook.runtime_event.received", summarizeRuntimeEvent(event));
      dispatch(event);
    });
    void runtime.connect(sessionId);
    return () => {
      conversationDebug("hook.connect_effect.cleanup", { sessionId });
      unsubscribe();
      void runtime.disconnect();
    };
  }, [runtime, sessionId]);

  useEffect(() => {
    conversationDebug("hook.state.after_reduce", summarizeState(state));
  }, [state]);

  const sendCommand = useCallback(
    (command: RuntimeCommandView) => {
      conversationDebug("hook.command.send", summarizeCommand(command));
      return runtime.sendCommand(command);
    },
    [runtime],
  );

  const setMicrophoneEnabled = useCallback(
    (enabled: boolean) => {
      conversationDebug("hook.microphone.enabled", { enabled });
      runtime.setMicrophoneEnabled(enabled);
    },
    [runtime],
  );

  const setMicrophoneMode = useCallback(
    (mode: MicrophoneModeView) => {
      conversationDebug("hook.microphone.mode", { mode });
      runtime.setMicrophoneMode(mode);
    },
    [runtime],
  );

  const dismissConfirmation = useCallback(() => {
    conversationDebug("hook.confirmation.dismiss");
    dispatch({ type: "dismiss_confirmation" });
  }, []);

  return { state, sendCommand, setMicrophoneEnabled, setMicrophoneMode, dismissConfirmation };
}
