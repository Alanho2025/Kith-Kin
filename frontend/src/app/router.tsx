import { useMemo, useState } from "react";

import { ConversationPage } from "../pages/ConversationPage";
import { StartPage } from "../pages/StartPage";
import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { BackendConversationRuntime } from "../features/conversation/runtime/BackendConversationRuntime";
import { mockPharmacyFlow } from "../test/fixtures/mock-pharmacy-flow";


export function AppRouter() {
  const [started, setStarted] = useState(false);
  const [isMock, setIsMock] = useState(true);
  const [realSessionId, setRealSessionId] = useState<string>("");
  const [sessionLoading, setSessionLoading] = useState(false);

  async function handleStart() {
    if (isMock) {
      setStarted(true);
      return;
    }
    setSessionLoading(true);
    try {
      const base = (import.meta as any).env?.VITE_API_BASE_URL ?? "/api";
      const res = await fetch(`${base}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ encounter_type: "pharmacy" }),
      });
      const data = await res.json();
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
    <ConversationPage runtime={runtime} sessionId={isMock ? "mock-session" : realSessionId} isMock={isMock} />
  ) : (
    <StartPage
      onStart={handleStart}
      isMock={isMock}
      onToggleMock={(val) => setIsMock(val)}
    />
  );
}

