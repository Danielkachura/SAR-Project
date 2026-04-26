import { useState } from "react";
import { CalibrationPage } from "../pages/CalibrationPage";
import { LiveMissionPage } from "../pages/LiveMissionPage";
import { OverviewPage } from "../pages/OverviewPage";
import { LocalizationPage } from "../pages/LocalizationPage";
import { ReIdEnrichmentPage } from "../pages/ReIdEnrichmentPage";
import { SessionStartPage } from "../pages/SessionStartPage";
import type { SessionState } from "../types/contracts";

export default function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [page, setPage] = useState<"overview" | "calibration" | "enrichment" | "localization" | "live">("overview");

  if (page === "live") {
    return <LiveMissionPage onBack={() => setPage("overview")} />;
  }

  if (!session) {
    return (
      <div>
        <div style={{ padding: "1rem 1rem 0 1rem" }}>
          <button onClick={() => setPage("live")}>Live Mission</button>
        </div>
        <SessionStartPage onSessionReady={setSession} />
      </div>
    );
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
      <div style={{ padding: "1rem 1rem 0 1rem", display: "flex", gap: "0.5rem" }}>
        <button onClick={() => { setSession(null); setPage("overview"); }}>
          Change Folder
        </button>
        <button onClick={() => setPage("live")}>Live Mission</button>
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
