import { describe, expect, it } from "vitest";

import { PcmFrameBuffer } from "./PcmFrameBuffer";

describe("PcmFrameBuffer", () => {
  it("emits exact 100ms mono PCM16 frames at 16kHz", () => {
    const frames: ArrayBuffer[] = [];
    const buffer = new PcmFrameBuffer((frame) => frames.push(frame));

    buffer.push(new Int16Array(900));
    buffer.push(new Int16Array(2300));

    expect(frames).toHaveLength(2);
    expect(frames.map((frame) => frame.byteLength)).toEqual([3200, 3200]);
  });

  it("retains incomplete audio until enough samples arrive", () => {
    const frames: ArrayBuffer[] = [];
    const buffer = new PcmFrameBuffer((frame) => frames.push(frame));

    buffer.push(new Int16Array(1599));
    expect(frames).toHaveLength(0);

    buffer.push(new Int16Array(1));
    expect(frames).toHaveLength(1);
  });
});
