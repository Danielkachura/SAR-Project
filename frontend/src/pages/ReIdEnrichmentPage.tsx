import { useEffect, useState } from "react";

import { runEnrichment } from "../api/enrichment";
import { apiGet } from "../api/client";
import type {
  ArtifactRecord,
  EnrichmentParameters,
  EnrichmentDiagnostics,
  FolderInventory,
  SessionState,
} from "../types/contracts";

interface Props {
  session: SessionState;
  onSessionUpdate: (session: SessionState) => void;
  onBackToOverview: () => void;
}

function qualityBadge(rate: number): string {
  if (rate >= 0.8) return "good";
  if (rate >= 0.4) return "fair";
  return "poor";
}

export function ReIdEnrichmentPage({ session, onSessionUpdate, onBackToOverview }: Props) {
  const [inventory, setInventory] = useState<FolderInventory | null>(null);
  const [selectedCsv, setSelectedCsv] = useState<string>("");
  const [selectedPcap, setSelectedPcap] = useState<string>("");

  // Enrichment parameters (ENR-01 .. ENR-06)
  const [matchThreshold, setMatchThreshold] = useState<number>(0.3);
  const [matchTimeWindowMs, setMatchTimeWindowMs] = useState<number>(500);
  const [timeScoreWeight, setTimeScoreWeight] = useState<number>(0.6);
  const [identityScoreWeight, setIdentityScoreWeight] = useState<number>(0.3);
  const [wifiContextWeight, setWifiContextWeight] = useState<number>(0.1);
  const [bleContextWeight, setBleContextWeight] = useState<number>(0.1);

  const [enrichmentResult, setEnrichmentResult] = useState<EnrichmentDiagnostics | null>(null);
  const [enrichedArtifactName, setEnrichedArtifactName] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ inventory: FolderInventory; stage_jump: unknown }>(
      `/sessions/${session.session_id}/inventory`,
    )
      .then((resp) => setInventory(resp.inventory))
      .catch((err) => setError(String(err)));
  }, [session.session_id]);

  async function handleRunEnrichment() {
    if (!selectedCsv || !selectedPcap) {
      setError("Select a scan CSV and a matching PCAP file before running enrichment.");
      return;
    }
    setIsRunning(true);
    setError(null);
    setEnrichmentResult(null);
    try {
      const params: EnrichmentParameters = {
        match_threshold: matchThreshold,
        match_time_window_ms: matchTimeWindowMs,
        time_score_weight: timeScoreWeight,
        identity_score_weight: identityScoreWeight,
        wifi_context_weight: wifiContextWeight,
        ble_context_weight: bleContextWeight,
      };
      const result = await runEnrichment(
        session.session_id,
        selectedCsv,
        selectedPcap,
        params,
      );
      setEnrichmentResult(result.diagnostics);
      setEnrichedArtifactName(result.output_enriched_file);
      // Refresh session state after artifact activation
      const refreshed = await apiGet<{ session: SessionState }>(
        `/sessions/${session.session_id}`,
      ).catch(() => null);
      if (refreshed) onSessionUpdate(refreshed.session);
    } catch (err) {
      setError(String(err));
    } finally {
      setIsRunning(false);
    }
  }

  const csvFiles = inventory?.raw_csv_files ?? [];
  const pcapFiles = inventory?.pcap_files ?? [];
  const enrichedArtifacts = inventory?.enriched_artifacts ?? [];

  return (
    <div style={{ padding: "1rem", fontFamily: "monospace" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        <button onClick={onBackToOverview}>← Back to Overview</button>
      </div>

      <h2>Re-ID &amp; Enrichment</h2>
      <p style={{ color: "#888" }}>
        Session: <strong>{session.scan_folder_name}</strong> &mdash; Protocol:{" "}
        <strong>{session.mode.toUpperCase()}</strong>
      </p>

      {/* ---- Section 1: Scan CSV selection ---- */}
      <section style={{ marginBottom: "1rem" }}>
        <h3>1. Select Scan CSV</h3>
        <select
          value={selectedCsv}
          onChange={(e) => setSelectedCsv(e.target.value)}
          style={{ width: "100%", padding: "0.3rem" }}
        >
          <option value="">-- choose CSV --</option>
          {csvFiles.map((f: ArtifactRecord) => (
            <option key={f.artifact_id} value={f.file_name}>
              {f.file_name}
            </option>
          ))}
        </select>
      </section>

      {/* ---- Section 2: PCAP selection ---- */}
      <section style={{ marginBottom: "1rem" }}>
        <h3>2. Select Matching PCAP</h3>
        <select
          value={selectedPcap}
          onChange={(e) => setSelectedPcap(e.target.value)}
          style={{ width: "100%", padding: "0.3rem" }}
        >
          <option value="">-- choose PCAP --</option>
          {pcapFiles.map((f: ArtifactRecord) => (
            <option key={f.artifact_id} value={f.file_name}>
              {f.file_name}
            </option>
          ))}
        </select>
      </section>

      {/* ---- Section 3: Enrichment parameters ---- */}
      <section style={{ marginBottom: "1rem" }}>
        <h3>3. Enrichment Parameters</h3>
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <tbody>
            <tr>
              <td style={{ paddingRight: "1rem" }}>Match threshold (ENR-01)</td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={matchThreshold}
                  onChange={(e) => setMatchThreshold(Number(e.target.value))}
                  style={{ width: "80px" }}
                />
              </td>
            </tr>
            <tr>
              <td>Time window ms (ENR-02)</td>
              <td>
                <input
                  type="number"
                  min={1}
                  max={10000}
                  step={50}
                  value={matchTimeWindowMs}
                  onChange={(e) => setMatchTimeWindowMs(Number(e.target.value))}
                  style={{ width: "80px" }}
                />
              </td>
            </tr>
            <tr>
              <td>Time score weight (ENR-03)</td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={timeScoreWeight}
                  onChange={(e) => setTimeScoreWeight(Number(e.target.value))}
                  style={{ width: "80px" }}
                />
              </td>
            </tr>
            <tr>
              <td>Identity score weight (ENR-04)</td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={identityScoreWeight}
                  onChange={(e) => setIdentityScoreWeight(Number(e.target.value))}
                  style={{ width: "80px" }}
                />
              </td>
            </tr>
            <tr>
              <td>Wi-Fi context weight (ENR-05)</td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={wifiContextWeight}
                  onChange={(e) => setWifiContextWeight(Number(e.target.value))}
                  style={{ width: "80px" }}
                />
              </td>
            </tr>
            <tr>
              <td>BLE context weight (ENR-06)</td>
              <td>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={bleContextWeight}
                  onChange={(e) => setBleContextWeight(Number(e.target.value))}
                  style={{ width: "80px" }}
                />
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      {/* ---- Section 4: Enrichment controls ---- */}
      <section style={{ marginBottom: "1rem" }}>
        <h3>4. Run Enrichment</h3>
        <button
          onClick={handleRunEnrichment}
          disabled={isRunning || !selectedCsv || !selectedPcap}
          style={{ padding: "0.5rem 1.5rem" }}
        >
          {isRunning ? "Running…" : "Run Enrichment"}
        </button>
        {error && (
          <p style={{ color: "red", marginTop: "0.5rem" }}>{error}</p>
        )}
      </section>

      {/* ---- Section 5: Enrichment quality panel ---- */}
      {enrichmentResult && (
        <section style={{ marginBottom: "1rem", border: "1px solid #ccc", padding: "0.75rem" }}>
          <h3>5. Enrichment Quality</h3>
          <p>
            Output: <strong>{enrichedArtifactName}</strong>
          </p>
          <table style={{ borderCollapse: "collapse" }}>
            <tbody>
              <tr>
                <td style={{ paddingRight: "1rem" }}>Total rows</td>
                <td>{enrichmentResult.total_rows}</td>
              </tr>
              <tr>
                <td>Matched rows</td>
                <td>{enrichmentResult.matched_rows}</td>
              </tr>
              <tr>
                <td>Match rate</td>
                <td>
                  {(enrichmentResult.match_rate * 100).toFixed(1)}%{" "}
                  <span style={{ color: qualityBadge(enrichmentResult.match_rate) === "good" ? "green" : qualityBadge(enrichmentResult.match_rate) === "fair" ? "orange" : "red" }}>
                    ({qualityBadge(enrichmentResult.match_rate)})
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      )}

      {/* ---- Existing ENRICHED artifacts ---- */}
      {enrichedArtifacts.length > 0 && (
        <section style={{ marginBottom: "1rem" }}>
          <h3>Existing ENRICHED Artifacts</h3>
          <ul>
            {enrichedArtifacts.map((a: ArtifactRecord) => (
              <li key={a.artifact_id}>
                {a.file_name}
                {session.active_enriched_artifact_id === a.artifact_id && (
                  <span style={{ color: "green", marginLeft: "0.5rem" }}>[active]</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ---- Re-ID placeholder (Phase 5) ---- */}
      <section style={{ opacity: 0.4, border: "1px dashed #aaa", padding: "0.75rem" }}>
        <h3>Re-ID (Phase 5 — not yet implemented)</h3>
        <p>Re-ID parameters and controls will appear here once an ENRICHED artifact is active.</p>
      </section>
    </div>
  );
}
