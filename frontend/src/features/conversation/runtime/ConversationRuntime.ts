import type {
  ConversationRuntimeEvent,
  RuntimeCommandView,
} from "../viewModels";


export interface ConversationRuntime {
  connect(sessionId: string): Promise<void>;
  disconnect(): Promise<void>;
  sendCommand(command: RuntimeCommandView): Promise<void>;
  subscribe(listener: (event: ConversationRuntimeEvent) => void): () => void;
}
