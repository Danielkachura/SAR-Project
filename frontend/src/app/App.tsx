import { useState } from "react";
import { CalibrationPage } from "../pages/CalibrationPage";
import { OverviewPage } from "../pages/OverviewPage";
import { SessionStartPage } from "../pages/SessionStartPage";
import type { SessionState } from "../types/contracts";

export default function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [page, setPage] = useState<"overview" | "calibration">("overview");

  if (!session) {
    return <SessionStartPage onSessionReady={setSession} />;
  }

  if (page === "calibration") {
    return (
      <CalibrationPage
        session={session}
        onSessionUpdate={setSession}
        onBackToOverview={() => setPage("overview")}
      />
    );
  }

  return (
    <OverviewPage
      session={session}
      onSessionUpdate={setSession}
      onOpenCalibration={() => setPage("calibration")}
    />
  );
}
