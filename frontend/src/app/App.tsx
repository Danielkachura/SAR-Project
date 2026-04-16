import { useState } from "react";
import { CalibrationPage } from "../pages/CalibrationPage";
import { EnrichmentPage } from "../pages/EnrichmentPage";
import { OverviewPage } from "../pages/OverviewPage";
import { SessionStartPage } from "../pages/SessionStartPage";
import type { SessionState } from "../types/contracts";

export default function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [page, setPage] = useState<"overview" | "calibration" | "enrichment">("overview");

  if (!session) {
    return <SessionStartPage onSessionReady={setSession} />;
  }

  if (page === "enrichment") {
    return (
      <EnrichmentPage
        session={session}
        onSessionUpdate={setSession}
        onBackToCalibration={() => setPage("calibration")}
      />
    );
  }

  if (page === "calibration") {
    return (
      <CalibrationPage
        session={session}
        onSessionUpdate={setSession}
        onBackToOverview={() => setPage("overview")}
        onOpenEnrichment={() => setPage("enrichment")}
      />
    );
  }

  return (
    <OverviewPage
      session={session}
      onSessionUpdate={setSession}
      onOpenCalibration={() => setPage("calibration")}
      onBackToSessionStart={() => {
        setSession(null);
        setPage("overview");
      }}
    />
  );
}
