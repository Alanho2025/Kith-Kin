import type {
  ConversationRuntimeEvent,
  MicrophoneModeView,
  RuntimeCommandView,
} from "../viewModels";


export interface ConversationRuntime {
  connect(sessionId: string): Promise<void>;
  disconnect(): Promise<void>;
  setMicrophoneMode(mode: MicrophoneModeView): void;
  setMicrophoneEnabled(enabled: boolean): void;
  sendCommand(command: RuntimeCommandView): Promise<void>;
  subscribe(listener: (event: ConversationRuntimeEvent) => void): () => void;
}
