import { z } from "zod";

import type { ConversationRuntime } from "./ConversationRuntime";
import type {
  ConversationRuntimeEvent,
  MicrophoneModeView,
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

const SOCKET_OPEN = 1;

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
  private activeSpeaker: Exclude<MicrophoneModeView, null> = "pharmacist";
  private connecting = false;
  private readonly pendingCommandFrames: string[] = [];

  constructor(options: BackendConversationRuntimeOptions = {}) {
    this.fetchFn = options.fetchFn ?? window.fetch.bind(window);
    this.socketFactory = options.socketFactory ?? ((url) => new WebSocket(url));
    this.baseUrl = (options.baseUrl ?? globalThis.location.origin).replace(/\/$/, "");
  }

  async connect(sessionId: string): Promise<void> {
    const generation = ++this.connectionGeneration;
    this.sessionId = sessionId;
    this.connecting = true;
    let response: Response;
    try {
      response = await this.fetchFn(
        `${this.baseUrl}/api/sessions/${sessionId}/ticket`,
        { method: "POST", credentials: "include" },
      );
    } catch (error) {
      if (generation === this.connectionGeneration) {
        this.connecting = false;
        this.pendingCommandFrames.length = 0;
      }
      throw error;
    }
    if (!response.ok) {
      if (generation === this.connectionGeneration) {
        this.connecting = false;
        this.pendingCommandFrames.length = 0;
        this.emit({
          schemaVersion: "0.1",
          eventId: `runtime-ticket-${crypto.randomUUID()}`,
          eventType: "error.show",
          sessionId,
          sequence: this.sequence++,
          timestamp: new Date().toISOString(),
          correlationId: null,
          payload: {
            code: "RUNTIME_TICKET_REQUEST_FAILED",
            messageZh: "无法连接真实后端，请检查本地服务与授权来源。",
            messageEn: "Unable to connect to the real backend.",
            retryable: true,
            recoveryAction: "reconnect",
            relatedEventId: null,
          },
        });
      }
      return;
    }
    if (generation !== this.connectionGeneration) return;
    const websocketBase = this.baseUrl.replace(/^http/, "ws");
    const socket = this.socketFactory(`${websocketBase}/api/sessions/${sessionId}/live`);
    socket.binaryType = "arraybuffer";
    this.socket = socket;
    socket.onmessage = (message) => this.handleMessage(message);

    this.audioPlayer = new AudioPlayer();
    this.audioPlayer.start();

    this.audioRecorder = new AudioRecorder();

    try {
      await new Promise<void>((resolve, reject) => {
        socket.onopen = () => {
          socket.onclose = null;
          resolve();
        };
        socket.onerror = () => reject(new Error("RUNTIME_DISCONNECTED"));
        socket.onclose = () => reject(new Error("RUNTIME_DISCONNECTED"));
      });
    } catch (error) {
      if (generation === this.connectionGeneration) {
        this.connecting = false;
        this.pendingCommandFrames.length = 0;
      }
      throw error;
    }

    if (generation !== this.connectionGeneration) {
      socket.close();
      return;
    }
    this.connecting = false;
    this.flushPendingCommandFrames();
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
    this.activeSpeaker = "pharmacist";
    this.connecting = false;
    this.pendingCommandFrames.length = 0;
    return Promise.resolve();
  }

  setMicrophoneMode(mode: MicrophoneModeView): void {
    if (mode !== null) {
      this.activeSpeaker = mode;
      this.sendSpeakerChanged(mode);
    }
    this.userMicEnabled = mode !== null;
    if (this.micMode !== "system_speaking" && this.micMode !== "error") {
      this.micMode = mode === "parent" ? "user_speaking" : mode === "pharmacist" ? "listening_to_pharmacist" : "paused";
    }
    this.updateRecorderGate();
  }

  setMicrophoneEnabled(enabled: boolean): void {
    this.setMicrophoneMode(enabled ? "pharmacist" : null);
  }

  sendCommand(command: RuntimeCommandView): Promise<void> {
    if (!this.sessionId) return Promise.reject(new Error("RUNTIME_DISCONNECTED"));
    if (command.eventType === "transcript.final") {
      this.pauseMicrophoneForTypedFallback();
    }
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
    const frame = JSON.stringify(envelope);
    if (this.socket?.readyState === SOCKET_OPEN) {
      this.socket.send(frame);
      return Promise.resolve();
    }
    if (this.connecting) {
      this.pendingCommandFrames.push(frame);
      return Promise.resolve();
    }
    return Promise.reject(new Error("RUNTIME_DISCONNECTED"));
  }

  private flushPendingCommandFrames(): void {
    if (!this.socket || this.socket.readyState !== SOCKET_OPEN) return;
    const frames = this.pendingCommandFrames.splice(0);
    for (const frame of frames) this.socket.send(frame);
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
        this.micMode = this.userMicEnabled
          ? this.activeSpeaker === "parent"
            ? "user_speaking"
            : "listening_to_pharmacist"
          : "paused";
        this.updateRecorderGate();
      }
    }

    this.emit(event);
  }

  private updateRecorderGate(): void {
    const socket = this.socket;
    if (!this.audioRecorder || !socket) return;
    const wantsAudio =
      this.userMicEnabled &&
      !this.backendMuted &&
      socket.readyState === SOCKET_OPEN &&
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
    const websocketReady = this.socket?.readyState === SOCKET_OPEN;
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

  private pauseMicrophoneForTypedFallback(): void {
    this.userMicEnabled = false;
    this.micMode = "paused";
    this.audioRecorder?.pause();
  }

  private emit(event: ConversationRuntimeEvent): void {
    for (const listener of this.listeners) listener(event);
  }

  private sendSpeakerChanged(speaker: Exclude<MicrophoneModeView, null>): void {
    void this.sendCommand({ eventType: "audio.speaker_changed", payload: { speaker } }).catch(
      () => {},
    );
  }
}
