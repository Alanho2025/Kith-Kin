import { describe, expect, it, vi } from "vitest";

describe("Playwright live backend config", () => {
  it("uses the CI runner temp directory for the live SQLite database", async () => {
    vi.resetModules();
    vi.stubEnv(["GOOGLE", "API", "KEY"].join("_"), "test-key");
    vi.stubEnv("RUNNER_TEMP", "/tmp/github-runner-temp");

    const { createLiveDatabaseUrl } = await import("../playwright.config");

    expect(createLiveDatabaseUrl(12345)).toBe(
      "sqlite+aiosqlite:////tmp/github-runner-temp/kithkin_playwright_live_12345.db",
    );
    expect(createLiveDatabaseUrl(12345)).not.toContain("/private/tmp");
  });
});
