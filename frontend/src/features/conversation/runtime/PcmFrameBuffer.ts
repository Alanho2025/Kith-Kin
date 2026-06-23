const SAMPLES_PER_FRAME = 1600;

export class PcmFrameBuffer {
  private pending = new Int16Array(0);

  constructor(private readonly emit: (frame: ArrayBuffer) => void) {}

  push(samples: Int16Array): void {
    const combined = new Int16Array(this.pending.length + samples.length);
    combined.set(this.pending);
    combined.set(samples, this.pending.length);

    let offset = 0;
    while (combined.length - offset >= SAMPLES_PER_FRAME) {
      const frame = new ArrayBuffer(SAMPLES_PER_FRAME * Int16Array.BYTES_PER_ELEMENT);
      new Int16Array(frame).set(combined.subarray(offset, offset + SAMPLES_PER_FRAME));
      this.emit(frame);
      offset += SAMPLES_PER_FRAME;
    }
    this.pending = combined.slice(offset);
  }
}
