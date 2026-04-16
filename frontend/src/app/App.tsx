import { useState } from "react";
import { OverviewPage } from "../pages/OverviewPage";
import { SessionStartPage } from "../pages/SessionStartPage";
import type { SessionState } from "../types/contracts";

export default function App() {
  const [session, setSession] = useState<SessionState | null>(null);

  if (!session) {
    return <SessionStartPage onSessionReady={setSession} />;
  }

  return <OverviewPage session={session} />;
}
