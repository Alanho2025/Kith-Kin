import { describe, expect, it } from "vitest";

import config from "../vite.config";

describe("Vite API proxy", () => {
  it("preserves the browser Origin for ticket and WebSocket scope validation", () => {
    expect(config.server?.proxy?.["/api"]).toMatchObject({
      changeOrigin: false,
      ws: true,
    });
  });
});
