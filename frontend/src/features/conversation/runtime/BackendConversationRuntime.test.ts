import { describe, expect, it, vi } from "vitest";

import type { ConversationRuntimeEvent } from "../viewModels";
import {
  BackendConversationRuntime,
  type RuntimeSocket,
} from "./BackendConversationRuntime";
import { AudioPlayer } from "./AudioPlayer";
import { AudioRecorder } from "./AudioRecorder";


class FakeSocket implements RuntimeSocket {
  binaryType: BinaryType = "blob";
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  readonly sent: string[] = [];

  send(data: string | ArrayBufferLike | Blob | ArrayBufferView): void {
    if (typeof data === "string") this.sent.push(data);
  }

  close(): void {
    this.onclose?.(new CloseEvent("close"));
  }

  emitOpen(): void {
    this.onopen?.(new Event("open"));
  }

  emitJson(value: object): void {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(value) }));
  }
}


describe("BackendConversationRuntime", () => {
  it("requests an app ticket and maps the backend websocket contract", async () => {
    const requests: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const fetchFn: typeof fetch = (input, init) => {
      requests.push({ input, init });
      return Promise.resolve(
        new Response(
          JSON.stringify({
            session_id: "ses-1",
            expires_at: "2026-06-22T00:01:00Z",
            max_uses: 1,
          }),
          { status: 201, headers: { "content-type": "application/json" } },
        ),
      );
    };
    const socket = new FakeSocket();
    const events: ConversationRuntimeEvent[] = [];
    const runtime = new BackendConversationRuntime({
      fetchFn,
      socketFactory: () => socket,
      baseUrl: "http://localhost:8000",
    });
    runtime.subscribe((event) => events.push(event));

    const connected = runtime.connect("ses-1");
    await Promise.resolve();
    socket.emitOpen();
    await connected;
    socket.emitJson({
      schema_version: "0.1",
      event_id: "evt-ready",
      event_type: "session.ready",
      session_id: "ses-1",
      sequence: 1,
      timestamp: "2026-06-22T00:00:00Z",
      correlation_id: null,
      payload: {
        resumption_supported: true,
        next_sequence: 1,
        input_audio_format: {
          encoding: "pcm_s16le",
          sample_rate_hz: 16000,
          channels: 1,
        },
        output_audio_format: {
          encoding: "pcm_s16le",
          sample_rate_hz: 24000,
          channels: 1,
        },
      },
    });

    expect(requests).toEqual([
      {
        input: "http://localhost:8000/api/sessions/ses-1/ticket",
        init: { method: "POST", credentials: "include" },
      },
    ]);
    expect(events[0]).toMatchObject({
      eventId: "evt-ready",
      eventType: "session.ready",
      payload: { resumptionSupported: true, nextSequence: 1 },
    });
    expect(JSON.stringify(events)).not.toContain("encoded_ticket");
  });

  it("plays binary messages and handles audio.muted events", async () => {
    const playSpy = vi.spyOn(AudioPlayer.prototype, "play").mockImplementation(() => {});
    const startPlayerSpy = vi.spyOn(AudioPlayer.prototype, "start").mockImplementation(() => {});
    const startRecorderSpy = vi.spyOn(AudioRecorder.prototype, "start").mockImplementation(() => Promise.resolve());
    const pauseSpy = vi.spyOn(AudioRecorder.prototype, "pause").mockImplementation(() => {});
    const resumeSpy = vi.spyOn(AudioRecorder.prototype, "resume").mockImplementation(() => {});

    const fetchFn: typeof fetch = () =>
      Promise.resolve(
        new Response(
          JSON.stringify({ session_id: "ses-1", expires_at: "2026-06-22T00:01:00Z", max_uses: 1 }),
          { status: 201, headers: { "content-type": "application/json" } },
        ),
      );
    const socket = new FakeSocket();
    const runtime = new BackendConversationRuntime({
      fetchFn,
      socketFactory: () => socket,
      baseUrl: "http://localhost:8000",
    });

    const connected = runtime.connect("ses-1");
    await Promise.resolve();
    socket.emitOpen();
    await connected;

    expect(startPlayerSpy).toHaveBeenCalled();
    expect(startRecorderSpy).toHaveBeenCalled();

    // Emit binary message
    const buffer = new ArrayBuffer(10);
    socket.onmessage?.(new MessageEvent("message", { data: buffer }));
    expect(playSpy).toHaveBeenCalledWith(buffer);

    // Emit audio.muted (true)
    socket.emitJson({
      schema_version: "0.1",
      event_id: "evt-muted",
      event_type: "audio.muted",
      session_id: "ses-1",
      sequence: 2,
      timestamp: "2026-06-22T00:00:01Z",
      correlation_id: null,
      payload: {
        muted: true,
        reason: "tts_playback",
      },
    });
    expect(pauseSpy).toHaveBeenCalled();

    // Emit audio.muted (false)
    socket.emitJson({
      schema_version: "0.1",
      event_id: "evt-unmuted",
      event_type: "audio.muted",
      session_id: "ses-1",
      sequence: 3,
      timestamp: "2026-06-22T00:00:02Z",
      correlation_id: null,
      payload: {
        muted: false,
        reason: "tts_playback",
      },
    });
    expect(resumeSpy).toHaveBeenCalled();

    playSpy.mockRestore();
    startPlayerSpy.mockRestore();
    startRecorderSpy.mockRestore();
    pauseSpy.mockRestore();
    resumeSpy.mockRestore();
  });
});
