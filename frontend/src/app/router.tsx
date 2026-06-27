import { useMemo, useState } from "react";

import { ConversationPage } from "../pages/ConversationPage";
import { StartPage } from "../pages/StartPage";
import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { BackendConversationRuntime } from "../features/conversation/runtime/BackendConversationRuntime";
import { mockPharmacyFlow } from "../test/fixtures/mock-pharmacy-flow";

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
    if (isMock) {
      setStarted(true);
      return;
    }
    try {
      const base = import.meta.env.VITE_API_BASE_URL ?? "/api";
      const res = await fetch(`${base}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ encounter_type: "pharmacy" }),
      });
      const body: unknown = await res.json();
      const data = parseSessionResponse(body);
      setRealSessionId(data.session_id);
      setStarted(true);
    } catch {
      setRealSessionId("fallback-session");
      setStarted(true);
    }
  }

  const runtime = useMemo(() => {
    if (isMock) {
      return new MockConversationRuntime(mockPharmacyFlow, 1500);
    } else {
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
      onToggleMock={(val) => setIsMock(val)}
    />
  );
}
