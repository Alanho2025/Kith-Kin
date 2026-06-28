import { z } from "zod";

import type { ConversationRuntime } from "./ConversationRuntime";
import type {
  ConversationRuntimeEvent,
  RuntimeCommandView,
} from "../viewModels";
import { AudioPlayer } from "./AudioPlayer";
import { AudioRecorder } from "./AudioRecorder";


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
  readyState: number;
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

type MicMode =
  | "idle"
  | "listening_to_pharmacist"
  | "user_speaking"
  | "system_speaking"
  | "paused"
  | "error";

interface AudioGate {
  userMicEnabled: boolean;
  backendMuted: boolean;
  websocketReady: boolean;
  recorderReady: boolean;
  canSendAudio: boolean;
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
  private audioRecorder: AudioRecorder | null = null;
  private audioPlayer: AudioPlayer | null = null;
  private connectionGeneration = 0;
  private userMicEnabled = false;
  private backendMuted = false;
  private recorderStarted = false;
  private micMode: MicMode = "idle";

  constructor(options: BackendConversationRuntimeOptions = {}) {
    this.fetchFn = options.fetchFn ?? window.fetch.bind(window);
    this.socketFactory = options.socketFactory ?? ((url) => new WebSocket(url));
    this.baseUrl = (options.baseUrl ?? globalThis.location.origin).replace(/\/$/, "");
  }

  async connect(sessionId: string): Promise<void> {
    const generation = ++this.connectionGeneration;
    this.sessionId = sessionId;
    const response = await this.fetchFn(
      `${this.baseUrl}/api/sessions/${sessionId}/ticket`,
      { method: "POST", credentials: "include" },
    );
    if (!response.ok) throw new Error("RUNTIME_TICKET_REQUEST_FAILED");
    if (generation !== this.connectionGeneration) return;
    const websocketBase = this.baseUrl.replace(/^http/, "ws");
    const socket = this.socketFactory(`${websocketBase}/api/sessions/${sessionId}/live`);
    socket.binaryType = "arraybuffer";
    this.socket = socket;
    socket.onmessage = (message) => this.handleMessage(message);

    this.audioPlayer = new AudioPlayer();
    this.audioPlayer.start();

    this.audioRecorder = new AudioRecorder();

    await new Promise<void>((resolve, reject) => {
      socket.onopen = () => {
        socket.onclose = null;
        resolve();
      };
      socket.onerror = () => reject(new Error("RUNTIME_DISCONNECTED"));
      socket.onclose = () => reject(new Error("RUNTIME_DISCONNECTED"));
    });

    if (generation !== this.connectionGeneration) {
      socket.close();
      return;
    }
    this.updateRecorderGate();
  }

  disconnect(): Promise<void> {
    this.connectionGeneration += 1;
    this.socket?.close();
    this.socket = null;
    this.audioRecorder?.stop();
    this.audioRecorder = null;
    this.audioPlayer?.stop();
    this.audioPlayer = null;
    this.backendMuted = false;
    this.recorderStarted = false;
    this.userMicEnabled = false;
    this.micMode = "idle";
    return Promise.resolve();
  }

  setMicrophoneEnabled(enabled: boolean): void {
    this.userMicEnabled = enabled;
    if (this.micMode !== "system_speaking" && this.micMode !== "error") {
      this.micMode = enabled ? "listening_to_pharmacist" : "paused";
    }
    this.updateRecorderGate();
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
    if (typeof message.data !== "string") {
      if (message.data instanceof ArrayBuffer) {
        this.audioPlayer?.play(message.data);
      } else if (message.data instanceof Blob) {
        void message.data.arrayBuffer().then((buf) => {
          this.audioPlayer?.play(buf);
        });
      }
      return;
    }
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

    if (event.eventType === "audio.muted") {
      const payloadObj = event.payload as Record<string, unknown> | null;
      const isMuted = payloadObj?.muted;
      if (isMuted) {
        this.backendMuted = true;
        this.micMode = "system_speaking";
        this.audioRecorder?.pause();
      } else {
        this.backendMuted = false;
        this.micMode = this.userMicEnabled ? "listening_to_pharmacist" : "paused";
        this.updateRecorderGate();
      }
    }

    for (const listener of this.listeners) listener(event);
  }

  private updateRecorderGate(): void {
    const socket = this.socket;
    if (!this.audioRecorder || !socket) return;
    const wantsAudio =
      this.userMicEnabled &&
      !this.backendMuted &&
      socket.readyState === WebSocket.OPEN &&
      this.micMode !== "system_speaking" &&
      this.micMode !== "error";

    if (!this.recorderStarted) {
      if (!wantsAudio) return;
      this.recorderStarted = true;
      void this.audioRecorder.start((pcm) => {
        if (this.getAudioGate().canSendAudio) {
          socket.send(pcm);
        }
      }).catch(() => {
        this.userMicEnabled = false;
        this.recorderStarted = false;
        this.micMode = "error";
      });
      return;
    }

    if (wantsAudio) {
      this.audioRecorder.resume();
    } else {
      this.audioRecorder.pause();
    }
  }

  private getAudioGate(): AudioGate {
    const websocketReady = this.socket?.readyState === WebSocket.OPEN;
    const recorderReady = this.recorderStarted;
    return {
      userMicEnabled: this.userMicEnabled,
      backendMuted: this.backendMuted,
      websocketReady,
      recorderReady,
      canSendAudio:
        this.userMicEnabled &&
        !this.backendMuted &&
        websocketReady &&
        recorderReady &&
        this.micMode !== "system_speaking" &&
        this.micMode !== "error",
    };
  }
}
