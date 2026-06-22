import { useMemo, useState } from "react";

import { ConversationPage } from "../pages/ConversationPage";
import { StartPage } from "../pages/StartPage";
import { MockConversationRuntime } from "../features/conversation/runtime/MockConversationRuntime";
import { mockPharmacyFlow } from "../test/fixtures/mock-pharmacy-flow";


export function AppRouter() {
  const [started, setStarted] = useState(false);
  const runtime = useMemo(() => new MockConversationRuntime(mockPharmacyFlow), []);

  return started ? (
    <ConversationPage runtime={runtime} sessionId="ses-demo" />
  ) : (
    <StartPage onStart={() => setStarted(true)} />
  );
}
