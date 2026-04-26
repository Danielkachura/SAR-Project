import { useState } from "react";
import { CalibrationPage } from "../pages/CalibrationPage";
import { OverviewPage } from "../pages/OverviewPage";
import { LocalizationPage } from "../pages/LocalizationPage";
import { ReIdEnrichmentPage } from "../pages/ReIdEnrichmentPage";
import { SessionStartPage } from "../pages/SessionStartPage";
import type { SessionState } from "../types/contracts";

export default function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [page, setPage] = useState<"overview" | "calibration" | "enrichment" | "localization">("overview");

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

  if (page === "enrichment") {
    return (
      <ReIdEnrichmentPage
        session={session}
        onSessionUpdate={setSession}
        onBackToOverview={() => setPage("overview")}
        onOpenLocalization={() => setPage("localization")}
      />
    );
  }

  if (page === "localization") {
    return (
      <LocalizationPage
        session={session}
        onBackToEnrichment={() => setPage("enrichment")}
      />
    );
  }

  return (
    <div>
      <div style={{ padding: "1rem 1rem 0 1rem" }}>
        <button onClick={() => { setSession(null); setPage("overview"); }}>
          Change Folder
        </button>
      </div>
      <OverviewPage
        session={session}
        onSessionUpdate={setSession}
        onOpenCalibration={() => setPage("calibration")}
        onOpenEnrichment={() => setPage("enrichment")}
      />
    </div>
  );
}
