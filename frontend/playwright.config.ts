import { defineConfig, devices } from "@playwright/test";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

type PlaywrightBackendMode = "deterministic" | "live_gemini";

function getBackendMode(): PlaywrightBackendMode {
  return process.env.PLAYWRIGHT_BACKEND_MODE === "deterministic"
    ? "deterministic"
    : "live_gemini";
}

function loadGoogleApiKey(required: boolean): string | undefined {
  if (process.env.GOOGLE_API_KEY) return process.env.GOOGLE_API_KEY;

  const envPath = path.resolve("../backend/.env");
  if (fs.existsSync(envPath)) {
    const contents = fs.readFileSync(envPath, "utf8");
    const line = contents
      .split(/\r?\n/)
      .find((entry) => entry.trim().startsWith("GOOGLE_API_KEY="));
    const value = line?.split("=").slice(1).join("=").trim();
    if (value) return value.replace(/^['"]|['"]$/g, "");
  }

  if (!required) return undefined;

  throw new Error(
    "GOOGLE_API_KEY is required for Playwright live backend tests. Set it in the environment or backend/.env.",
  );
}

const backendMode = getBackendMode();
const googleApiKey = loadGoogleApiKey(backendMode === "live_gemini");

export function createLiveDatabaseUrl(pid = process.pid): string {
  const tempRoot = process.env.RUNNER_TEMP || os.tmpdir();
  const databasePath = path.join(tempRoot, `kithkin_playwright_live_${pid}.db`);
  return `sqlite+aiosqlite:///${databasePath}`;
}

const liveDatabaseUrl = createLiveDatabaseUrl();
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER === "1";
const backendAppModule =
  backendMode === "live_gemini" ? "app.main:app" : "app.deterministic_main:app";
const backendCommand = [
  `.venv/bin/python ../scripts/seed_demo_data.py --database-url ${liveDatabaseUrl}`,
  `.venv/bin/python -u -m uvicorn ${backendAppModule} --host 127.0.0.1 --port 8000`,
].join(" && ");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  expect: {
    timeout: 10000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    headless: true,
    launchOptions: {
      args: [
        "--autoplay-policy=no-user-gesture-required",
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
      ],
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: backendCommand,
      cwd: "../backend",
      env: {
        ...process.env,
        GOOGLE_API_KEY: googleApiKey ?? "",
        GEMINI_API_KEY: googleApiKey ?? "",
        LIVE_TRANSPORT: backendMode === "live_gemini" ? "gemini_live" : "backend_proxy",
        DATABASE_URL: liveDatabaseUrl,
      },
      port: 8000,
      reuseExistingServer,
      timeout: 120000,
    },
    {
      command: "npm run dev",
      cwd: ".",
      port: 5173,
      reuseExistingServer,
      timeout: 120000,
    },
  ],
});
