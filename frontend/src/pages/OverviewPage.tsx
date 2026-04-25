import { useEffect, useState } from "react";

import { fetchOverview } from "../api/overview";
import { ChartsSection } from "../components/overview/ChartsSection";
import { DeviceInspection } from "../components/overview/DeviceInspection";
import { PreviewTable } from "../components/overview/PreviewTable";
import { SpatialInspection } from "../components/overview/SpatialInspection";
import { SummaryStats } from "../components/overview/SummaryStats";
import type { OverviewPayload, SessionState } from "../types/contracts";

interface Props {
  session: SessionState;
  onSessionUpdate: (session: SessionState) => void;
  onOpenCalibration: () => void;
  onOpenEnrichment: () => void;
}

export function OverviewPage({ session, onSessionUpdate, onOpenCalibration, onOpenEnrichment }: Props) {
  const [selectedCsv, setSelectedCsv] = useState<string>(session.selected_overview_csv_file ?? "");
  const [overview, setOverview] = useState<OverviewPayload | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetchOverview(session.session_id, selectedCsv || null)
      .then((payload) => {
        setOverview(payload);
        setError("");
        if (session.selected_overview_csv_file !== payload.context.selected_csv_file) {
          onSessionUpdate({ ...session, selected_overview_csv_file: payload.context.selected_csv_file });
        }
      })
      .catch((err) => setError(String(err)));
  }, [selectedCsv, session, onSessionUpdate]);

  const availableCsvFiles = overview?.context.available_csv_files ?? [];

  return (
    <section>
      <h1>Overview</h1>
      <p>Active folder: {session.scan_folder_name}</p>
      <p>Mode: {session.mode}</p>
      <button onClick={onOpenCalibration}>Open Calibration</button>
      <button onClick={onOpenEnrichment} style={{ marginLeft: 8 }}>Open Enrichment</button>

      <label>
        Select CSV
        <select value={selectedCsv} onChange={(event) => setSelectedCsv(event.target.value)}>
          <option value="">Choose CSV</option>
          {availableCsvFiles.map((fileName) => (
            <option key={fileName} value={fileName}>
              {fileName}
            </option>
          ))}
        </select>
      </label>

      {overview?.context.warnings.map((warning, index) => (
        <p key={`warning-${index}`} role="status">
          {warning}
        </p>
      ))}

      {!overview?.summary_stats && <p>No file-level outputs until a CSV is selected.</p>}

      {overview?.summary_stats && <SummaryStats stats={overview.summary_stats} />}
      {overview?.charts && <ChartsSection charts={overview.charts} />}
      {overview?.preview && <PreviewTable preview={overview.preview} />}
      {overview?.spatial && <SpatialInspection spatial={overview.spatial} />}
      {overview?.device_analysis && <DeviceInspection analysis={overview.device_analysis} />}

      {error && <p role="alert">{error}</p>}
    </section>
  );
}
