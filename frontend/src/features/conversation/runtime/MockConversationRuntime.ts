import type { ConversationRuntime } from "./ConversationRuntime";
import type {
  CardSetView,
  ConversationRuntimeEvent,
  RuntimeCommandView,
} from "../viewModels";


function isCardSetPayload(value: unknown): value is { cardSet: CardSetView } {
  if (typeof value !== "object" || value === null || !("cardSet" in value)) {
    return false;
  }
  const cardSet = value.cardSet;
  return typeof cardSet === "object" && cardSet !== null && "cards" in cardSet;
}

export class MockConversationRuntime implements ConversationRuntime {
  readonly commands: RuntimeCommandView[] = [];
  private readonly listeners = new Set<(event: ConversationRuntimeEvent) => void>();
  private readonly cardSet: CardSetView | null;
  private sessionId = "mock-session";
  private sequence = 100;

  constructor(private readonly flow: readonly ConversationRuntimeEvent[]) {
    const cardEvent = flow.find((event) => event.eventType === "cards.render");
    this.cardSet = cardEvent && isCardSetPayload(cardEvent.payload)
      ? cardEvent.payload.cardSet
      : null;
  }

  async connect(sessionId: string): Promise<void> {
    this.sessionId = sessionId;
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    for (const event of this.flow) {
      this.emit({ ...event, sessionId });
    }
  }

  disconnect(): Promise<void> {
    this.listeners.clear();
    return Promise.resolve();
  }

  async sendCommand(command: RuntimeCommandView): Promise<void> {
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
    for (const listener of this.listeners) {
      listener(event);
    }
  }
}
