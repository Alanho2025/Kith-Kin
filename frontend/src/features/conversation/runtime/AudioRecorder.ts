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

const isBrowser =
  getAudioContextConstructor() !== undefined &&
  typeof navigator !== "undefined" &&
  typeof navigator.mediaDevices !== "undefined";

export class AudioRecorder {
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private sourceNode: MediaStreamAudioSourceNode | null = null;
  private processorNode: ScriptProcessorNode | null = null;
  private socketSend: ((data: ArrayBuffer) => void) | null = null;
  private isPaused = false;

  async start(sendFn: (data: ArrayBuffer) => void): Promise<void> {
    if (!isBrowser) return;
    if (this.audioContext) return;

    this.socketSend = sendFn;
    this.isPaused = false;

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Create context with sampleRate 16000 directly if browser supports it,
      // otherwise use default and downsample in ScriptProcessor
      this.audioContext = createAudioContext();
      this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);

      // Using ScriptProcessorNode (known tech debt, simple for demo integration)
      this.processorNode = this.audioContext.createScriptProcessor(2048, 1, 1);

      const inputRate = this.audioContext.sampleRate;
      const targetRate = 16000;

      this.processorNode.onaudioprocess = (e) => {
        if (this.isPaused || !this.socketSend) return;
        const inputData = e.inputBuffer.getChannelData(0);
        const pcmData = this.downsampleAndConvert(inputData, inputRate, targetRate);
        const frame = new ArrayBuffer(pcmData.byteLength);
        new Int16Array(frame).set(pcmData);
        this.socketSend(frame);
      };

      this.sourceNode.connect(this.processorNode);
      this.processorNode.connect(this.audioContext.destination);
    } catch (err) {
      console.error("AudioRecorder failed to start microphone capture:", err);
      this.stop();
      throw err;
    }
  }

  pause(): void {
    this.isPaused = true;
  }

  resume(): void {
    this.isPaused = false;
  }

  stop(): void {
    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode = null;
    }
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.audioContext) {
      void this.audioContext.close();
      this.audioContext = null;
    }
    this.socketSend = null;
    this.isPaused = false;
  }

  private downsampleAndConvert(
    buffer: Float32Array,
    inputRate: number,
    outputRate: number
  ): Int16Array {
    if (inputRate === outputRate) {
      const out = new Int16Array(buffer.length);
      for (let i = 0; i < buffer.length; i++) {
        out[i] = Math.min(1, Math.max(-1, buffer[i])) * 0x7fff;
      }
      return out;
    }
    const ratio = inputRate / outputRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Int16Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let accum = 0;
      let count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }
      if (count > 0) {
        result[offsetResult] = Math.min(1, Math.max(-1, accum / count)) * 0x7fff;
      }
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  }
}
