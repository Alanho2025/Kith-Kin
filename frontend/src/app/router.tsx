import { useMemo, useState } from "react";

import { ConversationPage } from "../pages/ConversationPage";
import { StartPage } from "../pages/StartPage";
import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { BackendConversationRuntime } from "../features/conversation/runtime/BackendConversationRuntime";
import { mockPharmacyFlow } from "../test/fixtures/mock-pharmacy-flow";


export function AppRouter() {
  const [started, setStarted] = useState(false);
  const [isMock, setIsMock] = useState(true);

  const runtime = useMemo(() => {
    if (isMock) {
      return new MockConversationRuntime(mockPharmacyFlow);
    } else {
      return new BackendConversationRuntime();
    }
  }, [isMock]);

  return started ? (
    <ConversationPage runtime={runtime} sessionId="ses-demo" />
  ) : (
    <StartPage
      onStart={() => setStarted(true)}
      isMock={isMock}
      onToggleMock={(val) => setIsMock(val)}
    />
  );
}

