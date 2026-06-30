import { conversationDebug } from "../debugLog";

type WindowWithWebkitAudioContext = Window & {
  webkitAudioContext?: typeof AudioContext;
};

function getAudioContextConstructor(): typeof AudioContext | undefined {
  if (typeof window === "undefined") return undefined;
  return window.AudioContext ?? (window as WindowWithWebkitAudioContext).webkitAudioContext;
}

function createAudioContext(): AudioContext {
  const AudioContextConstructor = getAudioContextConstructor();
  if (!AudioContextConstructor) throw new Error("AUDIO_CONTEXT_UNAVAILABLE");
  return new AudioContextConstructor();
}

const isBrowser = getAudioContextConstructor() !== undefined;

export class AudioPlayer {
  private audioContext: AudioContext | null = null;
  private nextPlayTime = 0;
  private playedChunkCount = 0;

  start(): void {
    conversationDebug("audio_player.start.request", {
      isBrowser,
      alreadyStarted: this.audioContext !== null,
    });
    if (!isBrowser) {
      conversationDebug("audio_player.start.skipped_not_browser");
      return;
    }
    if (this.audioContext) {
      conversationDebug("audio_player.start.already_started");
      return;
    }
    this.audioContext = createAudioContext();
    this.nextPlayTime = 0;
    this.playedChunkCount = 0;
    conversationDebug("audio_player.start.ready", {
      sampleRate: this.audioContext.sampleRate,
      state: this.audioContext.state,
    });
  }

  play(pcmBuffer: ArrayBuffer): void {
    if (!isBrowser || !this.audioContext) {
      conversationDebug("audio_player.play.skipped", {
        isBrowser,
        hasAudioContext: this.audioContext !== null,
        byteLength: pcmBuffer.byteLength,
      });
      return;
    }

    // Provider audio arrives as signed 16-bit PCM; Web Audio playback requires
    // normalized float samples.
    const int16Array = new Int16Array(pcmBuffer);
    const float32Array = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
      float32Array[i] = int16Array[i] / 0x7fff;
    }

    const audioBuffer = this.audioContext.createBuffer(1, float32Array.length, 24000);
    audioBuffer.getChannelData(0).set(float32Array);

    const source = this.audioContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.audioContext.destination);

    // Schedule chunks back-to-back to preserve provider TTS cadence without
    // overlapping frames or inserting silence between socket messages.
    const currentTime = this.audioContext.currentTime;
    if (this.nextPlayTime < currentTime) {
      this.nextPlayTime = currentTime;
    }

    source.start(this.nextPlayTime);
    this.nextPlayTime += audioBuffer.duration;
    this.playedChunkCount += 1;
    conversationDebug("audio_player.play.scheduled", {
      chunkCount: this.playedChunkCount,
      byteLength: pcmBuffer.byteLength,
      sampleCount: float32Array.length,
      durationSeconds: audioBuffer.duration,
      startTime: this.nextPlayTime - audioBuffer.duration,
      nextPlayTime: this.nextPlayTime,
      contextTime: currentTime,
    });
  }

  stop(): void {
    conversationDebug("audio_player.stop", {
      hadAudioContext: this.audioContext !== null,
      playedChunkCount: this.playedChunkCount,
    });
    if (this.audioContext) {
      void this.audioContext.close();
      this.audioContext = null;
    }
    this.nextPlayTime = 0;
    this.playedChunkCount = 0;
  }
}
