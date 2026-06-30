import type { ConversationRuntime } from "./ConversationRuntime";
import type {
  CardSetView,
  ConversationRuntimeEvent,
  MicrophoneModeView,
  RuntimeCommandView,
} from "../viewModels";
import { conversationDebug, summarizeCommand, summarizeRuntimeEvent } from "../debugLog";


function isCardSetPayload(value: unknown): value is { cardSet: CardSetView } {
  if (typeof value !== "object" || value === null || !("cardSet" in value)) {
    return false;
  }
  const cardSet = value.cardSet;
  return typeof cardSet === "object" && cardSet !== null && "cards" in cardSet;
}

export class MockConversationRuntime implements ConversationRuntime {
  readonly commands: RuntimeCommandView[] = [];
  microphoneEnabled = false;
  microphoneMode: MicrophoneModeView = null;
  private readonly listeners = new Set<(event: ConversationRuntimeEvent) => void>();
  private readonly cardSet: CardSetView | null;
  private sessionId = "mock-session";
  private sequence = 100;

  constructor(
    private readonly flow: readonly ConversationRuntimeEvent[],
    private readonly delayMs: number = 0,
  ) {
    const cardEvent = flow.find((event) => event.eventType === "cards.render");
    this.cardSet = cardEvent && isCardSetPayload(cardEvent.payload)
      ? cardEvent.payload.cardSet
      : null;
  }

  async connect(sessionId: string): Promise<void> {
    this.sessionId = sessionId;
    conversationDebug("mock_runtime.connect", {
      sessionId,
      flowEvents: this.flow.map((event) => event.eventType),
      delayMs: this.delayMs,
    });
    if (this.delayMs > 0) {
      await new Promise<void>((resolve) => setTimeout(resolve, 300));
    }
    
    for (const event of this.flow) {
      if (this.listeners.size === 0) return;
      
      this.emit({ ...event, sessionId });
      
      if (this.delayMs > 0) {
        await new Promise<void>((resolve) => setTimeout(resolve, this.delayMs));
      }
    }
  }

  disconnect(): Promise<void> {
    conversationDebug("mock_runtime.disconnect", { sessionId: this.sessionId });
    this.listeners.clear();
    return Promise.resolve();
  }

  setMicrophoneEnabled(enabled: boolean): void {
    this.setMicrophoneMode(enabled ? "pharmacist" : null);
  }

  setMicrophoneMode(mode: MicrophoneModeView): void {
    conversationDebug("mock_runtime.microphone.mode", { mode });
    this.microphoneMode = mode;
    this.microphoneEnabled = mode !== null;
  }

  async sendCommand(command: RuntimeCommandView): Promise<void> {
    conversationDebug("mock_runtime.command", summarizeCommand(command));
    this.commands.push(command);
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    if (command.eventType === "card.select" && this.cardSet) {
      this.emit({
        schemaVersion: "0.1",
        eventId: `evt-selected-${command.payload.cardId}`,
        eventType: "card.selected",
        sessionId: this.sessionId,
        sequence: this.sequence++,
        timestamp: new Date(0).toISOString(),
        correlationId: null,
        payload: {
          ...command.payload,
          confirmationId: `confirmation-${command.payload.cardId}`,
        },
      });
    }
  }

  subscribe(listener: (event: ConversationRuntimeEvent) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(event: ConversationRuntimeEvent): void {
    conversationDebug("mock_runtime.event.emit", summarizeRuntimeEvent(event));
    for (const listener of this.listeners) {
      listener(event);
    }
  }
}
