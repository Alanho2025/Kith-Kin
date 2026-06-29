import { useMemo, useState } from "react";

import { ConversationPage } from "../pages/ConversationPage";
import { StartPage } from "../pages/StartPage";
import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { BackendConversationRuntime } from "../features/conversation/runtime/BackendConversationRuntime";
import { mockPharmacyFlow } from "../test/fixtures/mock-pharmacy-flow";
import { conversationDebug } from "../features/conversation/debugLog";

interface SessionResponse {
  session_id: string;
}

function parseSessionResponse(value: unknown): SessionResponse {
  if (
    typeof value === "object" &&
    value !== null &&
    "session_id" in value &&
    typeof value.session_id === "string"
  ) {
    return { session_id: value.session_id };
  }
  throw new Error("SESSION_RESPONSE_INVALID");
}

export function AppRouter() {
  const [started, setStarted] = useState(false);
  const [isMock, setIsMock] = useState(true);
  const [realSessionId, setRealSessionId] = useState<string>("");

  async function handleStart() {
    conversationDebug("app.start", { mode: isMock ? "mock" : "backend" });
    if (isMock) {
      setStarted(true);
      return;
    }
    try {
      const base = import.meta.env.VITE_API_BASE_URL ?? "/api";
      conversationDebug("app.session.create.request", { base });
      const res = await fetch(`${base}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ encounter_type: "pharmacy" }),
      });
      const body: unknown = await res.json();
      const data = parseSessionResponse(body);
      conversationDebug("app.session.create.ok", {
        status: res.status,
        sessionId: data.session_id,
      });
      setRealSessionId(data.session_id);
      setStarted(true);
    } catch (error) {
      conversationDebug("app.session.create.failed", { error: String(error) });
      setRealSessionId("fallback-session");
      setStarted(true);
    }
  }

  const runtime = useMemo(() => {
    if (isMock) {
      conversationDebug("app.runtime.create", { mode: "mock" });
      return new MockConversationRuntime(mockPharmacyFlow, 1500);
    } else {
      conversationDebug("app.runtime.create", { mode: "backend" });
      return new BackendConversationRuntime();
    }
  }, [isMock]);

  return started ? (
    <ConversationPage
      runtime={runtime}
      sessionId={isMock ? "mock-session" : realSessionId}
      isMock={isMock}
      onRestart={() => setStarted(false)}
    />
  ) : (
    <StartPage
      onStart={() => {
        void handleStart();
      }}
      isMock={isMock}
      onToggleMock={(val) => {
        conversationDebug("app.mode.toggle", { isMock: val });
        setIsMock(val);
      }}
    />
  );
}
