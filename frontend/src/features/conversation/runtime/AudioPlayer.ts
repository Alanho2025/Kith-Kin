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

  start(): void {
    if (!isBrowser) return;
    if (this.audioContext) return;
    this.audioContext = createAudioContext();
    this.nextPlayTime = 0;
  }

  play(pcmBuffer: ArrayBuffer): void {
    if (!isBrowser || !this.audioContext) return;

    // Convert Int16Array back to Float32Array for AudioBuffer
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

    // Schedule playback back-to-back without overlapping or silence gaps
    const currentTime = this.audioContext.currentTime;
    if (this.nextPlayTime < currentTime) {
      this.nextPlayTime = currentTime;
    }

    source.start(this.nextPlayTime);
    this.nextPlayTime += audioBuffer.duration;
  }

  stop(): void {
    if (this.audioContext) {
      void this.audioContext.close();
      this.audioContext = null;
    }
    this.nextPlayTime = 0;
  }
}
