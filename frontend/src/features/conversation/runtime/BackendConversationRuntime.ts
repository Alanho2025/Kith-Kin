import { z } from "zod";

import type { ConversationRuntime } from "./ConversationRuntime";
import type {
  ConversationRuntimeEvent,
  RuntimeCommandView,
} from "../viewModels";


const envelopeSchema = z
  .object({
    schema_version: z.string().regex(/^0\.[0-9]+$/),
    event_id: z.string().min(1).max(80),
    event_type: z.string().min(1).max(80),
    session_id: z.string().min(1).max(80),
    sequence: z.number().int().positive(),
    timestamp: z.iso.datetime(),
    correlation_id: z.string().max(80).nullable(),
    payload: z.record(z.string(), z.unknown()),
  })
  .strict();

export interface RuntimeSocket {
  binaryType: BinaryType;
  onopen: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  onclose: ((event: CloseEvent) => void) | null;
  send(data: string | ArrayBufferLike | Blob | ArrayBufferView): void;
  close(): void;
}

interface BackendConversationRuntimeOptions {
  fetchFn?: typeof fetch;
  socketFactory?: (url: string) => RuntimeSocket;
  baseUrl?: string;
}

function camelCaseKey(key: string): string {
  return key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

function camelize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(camelize);
  if (typeof value !== "object" || value === null) return value;
  return Object.fromEntries(
    Object.entries(value).map(([key, entry]) => [camelCaseKey(key), camelize(entry)]),
  );
}

function snakeCaseKey(key: string): string {
  return key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
}

function snakeCase(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(snakeCase);
  if (typeof value !== "object" || value === null) return value;
  return Object.fromEntries(
    Object.entries(value).map(([key, entry]) => [snakeCaseKey(key), snakeCase(entry)]),
  );
}

export class BackendConversationRuntime implements ConversationRuntime {
  private readonly fetchFn: typeof fetch;
  private readonly socketFactory: (url: string) => RuntimeSocket;
  private readonly baseUrl: string;
  private readonly listeners = new Set<(event: ConversationRuntimeEvent) => void>();
  private socket: RuntimeSocket | null = null;
  private sessionId = "";
  private sequence = 1;

  constructor(options: BackendConversationRuntimeOptions = {}) {
    this.fetchFn = options.fetchFn ?? fetch;
    this.socketFactory = options.socketFactory ?? ((url) => new WebSocket(url));
    this.baseUrl = (options.baseUrl ?? globalThis.location.origin).replace(/\/$/, "");
  }

  async connect(sessionId: string): Promise<void> {
    this.sessionId = sessionId;
    const response = await this.fetchFn(
      `${this.baseUrl}/api/sessions/${sessionId}/ticket`,
      { method: "POST", credentials: "include" },
    );
    if (!response.ok) throw new Error("RUNTIME_TICKET_REQUEST_FAILED");
    const websocketBase = this.baseUrl.replace(/^http/, "ws");
    const socket = this.socketFactory(`${websocketBase}/api/sessions/${sessionId}/live`);
    socket.binaryType = "arraybuffer";
    this.socket = socket;
    socket.onmessage = (message) => this.handleMessage(message);
    await new Promise<void>((resolve, reject) => {
      socket.onopen = () => resolve();
      socket.onerror = () => reject(new Error("RUNTIME_DISCONNECTED"));
    });
  }

  disconnect(): Promise<void> {
    this.socket?.close();
    this.socket = null;
    return Promise.resolve();
  }

  sendCommand(command: RuntimeCommandView): Promise<void> {
    if (!this.socket) return Promise.reject(new Error("RUNTIME_DISCONNECTED"));
    const envelope = {
      schema_version: "0.1",
      event_id: `client-${crypto.randomUUID()}`,
      event_type: command.eventType,
      session_id: this.sessionId,
      sequence: this.sequence++,
      timestamp: new Date().toISOString(),
      correlation_id: null,
      payload: snakeCase(command.payload),
    };
    this.socket.send(JSON.stringify(envelope));
    return Promise.resolve();
  }

  subscribe(listener: (event: ConversationRuntimeEvent) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private handleMessage(message: MessageEvent): void {
    if (typeof message.data !== "string") return;
    const envelope = envelopeSchema.parse(JSON.parse(message.data));
    const event: ConversationRuntimeEvent = {
      schemaVersion: envelope.schema_version,
      eventId: envelope.event_id,
      eventType: envelope.event_type,
      sessionId: envelope.session_id,
      sequence: envelope.sequence,
      timestamp: envelope.timestamp,
      correlationId: envelope.correlation_id,
      payload: camelize(envelope.payload),
    };
    for (const listener of this.listeners) listener(event);
  }
}
