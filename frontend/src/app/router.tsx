import { useMemo, useState, useEffect } from "react";

import { ConversationPage } from "../pages/ConversationPage";
import { StartPage } from "../pages/StartPage";
import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { BackendConversationRuntime } from "../features/conversation/runtime/BackendConversationRuntime";
import { mockPharmacyFlow } from "../test/fixtures/mock-pharmacy-flow";


export function AppRouter() {
  const [started, setStarted] = useState(false);
  const [isMock, setIsMock] = useState(true);
  const [realSessionId, setRealSessionId] = useState<string>("");

  // Create a new backend session on mount when not in mock mode
  useEffect(() => {
    if (!isMock && !realSessionId) {
      const base = (import.meta as any).env?.VITE_API_BASE_URL ?? "/api";
      fetch(`${base}/sessions`, { method: "POST" })
        .then((r) => r.json())
        .then((data) => setRealSessionId(data.session_id))
        .catch(() => {
          // fallback — user will see the error in the console
          setRealSessionId("fallback-session");
        });
    }
  }, [isMock, realSessionId]);

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
      onStart={() => setStarted(true)}
      isMock={isMock}
      onToggleMock={(val) => setIsMock(val)}
    />
  );
}

