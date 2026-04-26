import { useMemo, useState } from "react";

import { getExecutionStatus } from "../api/executions";
import { runLocalization } from "../api/localization";
import type { LocalizationRunPayload, SessionState } from "../types/contracts";

interface Props {
  session: SessionState;
  onBackToEnrichment: () => void;
}

export function LocalizationPage({ session, onBackToEnrichment }: Props) {
  const [clusterIdsText, setClusterIdsText] = useState("");
  const [macsText, setMacsText] = useState("");
  const [gridResolution, setGridResolution] = useState(5);
  const [confidenceCutoff, setConfidenceCutoff] = useState(0.2);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [showGrid, setShowGrid] = useState(true);
  const [showRadii, setShowRadii] = useState(true);
  const [showPeaks, setShowPeaks] = useState(true);
  const [basemapType, setBasemapType] = useState("satellite");
  const [zoomClusterId, setZoomClusterId] = useState("");

  const [executionId, setExecutionId] = useState<string | null>(null);
  const [result, setResult] = useState<LocalizationRunPayload | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [error, setError] = useState<string | null>(null);

  const activeReid = session.active_reid_artifact_id;

  const clusterFilterList = useMemo(
    () => clusterIdsText.split(",").map((item) => item.trim()).filter(Boolean),
    [clusterIdsText],
  );

  const macFilterList = useMemo(
    () => macsText.split(",").map((item) => item.trim()).filter(Boolean),
    [macsText],
  );

  async function handleRun() {
    if (!activeReid) {
      setError("No active REID artifact selected.");
      return;
    }
    setError(null);
    setResult(null);
    setStatus("queued");
    try {
      const runResp = await runLocalization(
        session.session_id,
        activeReid,
        {
          grid_resolution_m: gridResolution,
          confidence_cutoff: confidenceCutoff,
          enable_ransac: true,
          uncertainty_target_mass_q: 0.68,
          min_samples_per_cluster: 3,
        },
        {
          cluster_ids: clusterFilterList,
          mac_addresses: macFilterList,
        },
      );
      setExecutionId(runResp.execution.execution_id);
      await pollExecution(runResp.execution.execution_id);
    } catch (err) {
      setError(String(err));
      setStatus("failed");
    }
  }

  async function pollExecution(id: string) {
    for (let i = 0; i < 60; i += 1) {
      const resp = await getExecutionStatus(id);
      setStatus(resp.execution.status);
      if (resp.execution.status === "succeeded") {
        setResult(resp.localization);
        return;
      }
      if (resp.execution.status === "failed") {
        setError(resp.execution.error_message ?? "Localization execution failed.");
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    setError("Localization execution timed out.");
  }

  return (
    <div style={{ padding: "1rem", fontFamily: "monospace" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        <button onClick={onBackToEnrichment}>← Back to Re-ID & Enrichment</button>
      </div>
      <h2>Localization</h2>
      <p>Active REID artifact: <strong>{activeReid ?? "None"}</strong></p>

      <section style={{ border: "1px solid #ccc", padding: "0.75rem", marginBottom: "1rem" }}>
        <h3>Pre-Localization Filters</h3>
        <label>Cluster IDs (comma-separated)</label>
        <input value={clusterIdsText} onChange={(e) => setClusterIdsText(e.target.value)} style={{ width: "100%" }} />
        <label>MAC addresses (comma-separated)</label>
        <input value={macsText} onChange={(e) => setMacsText(e.target.value)} style={{ width: "100%" }} />
      </section>

      <section style={{ border: "1px solid #ccc", padding: "0.75rem", marginBottom: "1rem" }}>
        <h3>Localization Parameters</h3>
        <label>Grid resolution (m)</label>
        <input type="number" min={1} step={1} value={gridResolution} onChange={(e) => setGridResolution(Number(e.target.value))} />
        <label style={{ marginLeft: "1rem" }}>Confidence cutoff</label>
        <input type="number" min={0} max={1} step={0.05} value={confidenceCutoff} onChange={(e) => setConfidenceCutoff(Number(e.target.value))} />
      </section>

      <section style={{ border: "1px solid #ccc", padding: "0.75rem", marginBottom: "1rem" }}>
        <h3>View Controls (no rerun)</h3>
        <label><input type="checkbox" checked={showHeatmap} onChange={(e) => setShowHeatmap(e.target.checked)} /> heatmap</label>
        <label style={{ marginLeft: "1rem" }}><input type="checkbox" checked={showGrid} onChange={(e) => setShowGrid(e.target.checked)} /> grid</label>
        <label style={{ marginLeft: "1rem" }}><input type="checkbox" checked={showRadii} onChange={(e) => setShowRadii(e.target.checked)} /> radii</label>
        <label style={{ marginLeft: "1rem" }}><input type="checkbox" checked={showPeaks} onChange={(e) => setShowPeaks(e.target.checked)} /> peaks</label>
        <div style={{ marginTop: "0.5rem" }}>
          <label>Basemap</label>
          <select value={basemapType} onChange={(e) => setBasemapType(e.target.value)}>
            <option value="satellite">satellite</option>
            <option value="street">street</option>
          </select>
          <label style={{ marginLeft: "1rem" }}>Zoom to cluster</label>
          <input value={zoomClusterId} onChange={(e) => setZoomClusterId(e.target.value)} placeholder="cluster_id" />
        </div>
      </section>

      <button onClick={handleRun} disabled={!activeReid || status === "running" || status === "queued"}>Run Localization</button>
      <p>Status: <strong>{status}</strong>{executionId ? ` (execution ${executionId})` : ""}</p>
      {error && <p style={{ color: "red" }}>{error}</p>}

      {result && (
        <section style={{ border: "1px solid #0a0", padding: "0.75rem", marginTop: "1rem" }}>
          <h3>Cluster Results</h3>
          <p>Input file: {result.input_reid_file}</p>
          <ul>
            {result.cluster_results.map((item) => (
              <li key={item.cluster_id}>
                <strong>{item.cluster_id}</strong> — {item.status} — samples {item.sample_count}
                {item.primary_peak_latitude !== null && item.primary_peak_longitude !== null && (
                  <span> — peak ({item.primary_peak_latitude.toFixed(6)}, {item.primary_peak_longitude.toFixed(6)})</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
