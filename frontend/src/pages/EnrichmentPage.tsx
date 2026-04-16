import { useEffect, useState } from "react";

import { runEnrichment } from "../api/enrichment";
import { fetchOverview } from "../api/overview";
import type { EnrichmentRunPayload, SessionState } from "../types/contracts";

interface Props {
  session: SessionState;
  onSessionUpdate: (session: SessionState) => void;
  onBackToCalibration: () => void;
}

export function EnrichmentPage({ session, onSessionUpdate, onBackToCalibration }: Props) {
  const [availableCsvFiles, setAvailableCsvFiles] = useState<string[]>([]);
  const [selectedCsv, setSelectedCsv] = useState<string>(session.selected_overview_csv_file ?? "");
  const [result, setResult] = useState<EnrichmentRunPayload | null>(null);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [isRunning, setIsRunning] = useState<boolean>(false);

  useEffect(() => {
    fetchOverview(session.session_id, null)
      .then((overview) => setAvailableCsvFiles(overview.context.available_csv_files))
      .catch((err) => setError(String(err)));
  }, [session.session_id]);

  const handleRun = async () => {
    if (!selectedCsv) return;
    setIsRunning(true);
    setError("");
    setStatus("");
    try {
      const payload = await runEnrichment(session.session_id, { selected_csv_file: selectedCsv });
      setResult(payload);
      setStatus("Enrichment completed and official artifact activated.");
      onSessionUpdate({
        ...session,
        active_enriched_artifact_id: payload.active_enriched_artifact_id,
      });
    } catch (err) {
      setError(String(err));
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <section>
      <h1>Enrichment</h1>
      <p>Session folder: {session.scan_folder_name}</p>
      <button onClick={onBackToCalibration}>Back to Calibration</button>

      <label>
        Enrichment CSV
        <select value={selectedCsv} onChange={(event) => setSelectedCsv(event.target.value)}>
          <option value="">Choose CSV</option>
          {availableCsvFiles.map((fileName) => (
            <option key={fileName} value={fileName}>
              {fileName}
            </option>
          ))}
        </select>
      </label>

      <button onClick={handleRun} disabled={!selectedCsv || isRunning}>
        {isRunning ? "Running..." : "Run Enrichment"}
      </button>

      {result && (
        <section>
          <h2>Enrichment Result</h2>
          <p>Output file: {result.output_file_name}</p>
          <p>Rows: {result.total_rows}</p>
          <p>Matched rows: {result.matched_rows}</p>
          <p>Matched ratio: {result.quality_stats.matched_row_ratio}</p>
          <p>Unmatched ratio: {result.quality_stats.unmatched_row_ratio}</p>
        </section>
      )}

      {status && <p role="status">{status}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
