import { useEffect, useMemo, useState } from "react";

import { runEnrichment } from "../api/enrichment";
import { runReId } from "../api/reid";
import { apiGet, apiPost } from "../api/client";
import type {
  ArtifactRecord,
  EnrichmentDiagnostics,
  EnrichmentParameters,
  FolderInventory,
  ReIdParameters,
  ReIdRunPayload,
  SessionState,
} from "../types/contracts";

interface Props {
  session: SessionState;
  onSessionUpdate: (session: SessionState) => void;
  onBackToOverview: () => void;
  onOpenLocalization: () => void;
}

function qualityBadge(rate: number): string {
  if (rate >= 0.8) return "good";
  if (rate >= 0.4) return "fair";
  return "poor";
}

export function ReIdEnrichmentPage({ session, onSessionUpdate, onBackToOverview, onOpenLocalization }: Props) {
  const [inventory, setInventory] = useState<FolderInventory | null>(null);
  const [selectedCsv, setSelectedCsv] = useState<string>("");
  const [selectedPcap, setSelectedPcap] = useState<string>("");

  const [matchThreshold, setMatchThreshold] = useState<number>(0.3);
  const [matchTimeWindowMs, setMatchTimeWindowMs] = useState<number>(500);
  const [timeScoreWeight, setTimeScoreWeight] = useState<number>(0.6);
  const [identityScoreWeight, setIdentityScoreWeight] = useState<number>(0.3);
  const [wifiContextWeight, setWifiContextWeight] = useState<number>(0.1);
  const [bleContextWeight, setBleContextWeight] = useState<number>(0.1);

  const [reidMinMerge, setReidMinMerge] = useState<number>(0.75);
  const [wifiStrongMerge, setWifiStrongMerge] = useState<number>(0.85);
  const [wifiWeakMerge, setWifiWeakMerge] = useState<number>(0.75);
  const [bleStrongMerge, setBleStrongMerge] = useState<number>(0.85);
  const [bleWeakMerge, setBleWeakMerge] = useState<number>(0.78);
  const [maxGapMs, setMaxGapMs] = useState<number>(5000);
  const [wifiSeqGap, setWifiSeqGap] = useState<number>(32);
  const [minEvidence, setMinEvidence] = useState<number>(2);

  const [enrichmentResult, setEnrichmentResult] = useState<EnrichmentDiagnostics | null>(null);
  const [enrichedArtifactName, setEnrichedArtifactName] = useState<string | null>(null);
  const [reidResult, setReidResult] = useState<ReIdRunPayload | null>(null);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [isRunningReid, setIsRunningReid] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshSessionAndInventory() {
    const [inventoryResp, sessionResp] = await Promise.all([
      apiGet<{ inventory: FolderInventory; stage_jump: unknown }>(`/sessions/${session.session_id}/inventory`),
      apiGet<{ session: SessionState }>(`/sessions/${session.session_id}/state`),
    ]);
    setInventory(inventoryResp.inventory);
    onSessionUpdate(sessionResp.session);
  }

  useEffect(() => {
    refreshSessionAndInventory().catch((err) => setError(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.session_id]);

  const activeEnriched = useMemo(() => {
    const artifacts = inventory?.enriched_artifacts ?? [];
    return artifacts.find((a) => a.artifact_id === session.active_enriched_artifact_id) ?? null;
  }, [inventory, session.active_enriched_artifact_id]);

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
      const result = await runEnrichment(session.session_id, selectedCsv, selectedPcap, params);
      setEnrichmentResult(result.enrichment.diagnostics);
      setEnrichedArtifactName(result.enrichment.output_enriched_file);
      onSessionUpdate(result.session);
      await refreshSessionAndInventory();
    } catch (err) {
      setError(String(err));
    } finally {
      setIsRunning(false);
    }
  }

  async function handleRunReId() {
    if (!activeEnriched) {
      setError("No active enriched artifact found. Ensure Enrichment ran successfully or select one below.");
      return;
    }
    setIsRunningReid(true);
    setError(null);
    setReidResult(null);
    try {
      const params: ReIdParameters = {
        protocol_global_min_merge_threshold: reidMinMerge,
        wifi_strong_merge_threshold: wifiStrongMerge,
        wifi_weak_context_merge_threshold: wifiWeakMerge,
        ble_strong_merge_threshold: bleStrongMerge,
        ble_weak_context_merge_threshold: bleWeakMerge,
        max_time_gap_candidate_ms: maxGapMs,
        wifi_sequence_gap_threshold: wifiSeqGap,
        minimum_evidence_for_non_singleton: minEvidence,
        singleton_fallback_enabled: true,
      };
      const result = await runReId(session.session_id, activeEnriched.artifact_id, params);
      setReidResult(result.reid);
      onSessionUpdate(result.session);
      await refreshSessionAndInventory();
    } catch (err) {
      setError(String(err));
    } finally {
      setIsRunningReid(false);
    }
  }

  async function handleActivateArtifact(artifactId: string) {
    try {
      const resp = await apiPost<{ session: SessionState }>(`/sessions/${session.session_id}/artifacts/activate`, {
        artifact_id: artifactId,
      });
      onSessionUpdate(resp.session);
    } catch (err) {
      setError(String(err));
    }
  }

  const csvFiles = inventory?.raw_csv_files ?? [];
  const pcapFiles = inventory?.pcap_files ?? [];
  const enrichedArtifacts = inventory?.enriched_artifacts ?? [];
  const reidArtifacts = inventory?.reid_artifacts ?? [];

  return (
    <div style={{ padding: "1rem", fontFamily: "monospace" }}>
      <div style={{ marginBottom: "0.5rem" }}>
        <button onClick={onBackToOverview}>← Back to Overview</button>
      </div>

      <h2>Re-ID &amp; Enrichment</h2>
      <p style={{ color: "#888" }}>
        Session: <strong>{session.scan_folder_name}</strong> &mdash; Protocol: <strong>{session.mode.toUpperCase()}</strong>
      </p>

      <section style={{ marginBottom: "1rem" }}>
        <h3>1. Select Scan CSV</h3>
        <select value={selectedCsv} onChange={(e) => setSelectedCsv(e.target.value)} style={{ width: "100%", padding: "0.3rem" }}>
          <option value="">-- choose CSV --</option>
          {csvFiles.map((f: ArtifactRecord) => (
            <option key={f.artifact_id} value={f.file_name}>{f.file_name}</option>
          ))}
        </select>
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h3>2. Select Matching PCAP</h3>
        <select value={selectedPcap} onChange={(e) => setSelectedPcap(e.target.value)} style={{ width: "100%", padding: "0.3rem" }}>
          <option value="">-- choose PCAP --</option>
          {pcapFiles.map((f: ArtifactRecord) => (
            <option key={f.artifact_id} value={f.file_name}>{f.file_name}</option>
          ))}
        </select>
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h3>3. Enrichment Parameters</h3>
        <table style={{ borderCollapse: "collapse", width: "100%" }}><tbody>
          <tr><td style={{ paddingRight: "1rem" }}>Match threshold (ENR-01)</td><td><input type="number" min={0} max={1} step={0.05} value={matchThreshold} onChange={(e) => setMatchThreshold(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>Time window ms (ENR-02)</td><td><input type="number" min={1} max={10000} step={50} value={matchTimeWindowMs} onChange={(e) => setMatchTimeWindowMs(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>Time score weight (ENR-03)</td><td><input type="number" min={0} max={1} step={0.05} value={timeScoreWeight} onChange={(e) => setTimeScoreWeight(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>Identity score weight (ENR-04)</td><td><input type="number" min={0} max={1} step={0.05} value={identityScoreWeight} onChange={(e) => setIdentityScoreWeight(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>Wi-Fi context weight (ENR-05)</td><td><input type="number" min={0} max={1} step={0.05} value={wifiContextWeight} onChange={(e) => setWifiContextWeight(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>BLE context weight (ENR-06)</td><td><input type="number" min={0} max={1} step={0.05} value={bleContextWeight} onChange={(e) => setBleContextWeight(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
        </tbody></table>
      </section>

      <section style={{ marginBottom: "1rem" }}>
        <h3>4. Run Enrichment</h3>
        <button onClick={handleRunEnrichment} disabled={isRunning || !selectedCsv || !selectedPcap} style={{ padding: "0.5rem 1.5rem" }}>
          {isRunning ? "Running…" : "Run Enrichment"}
        </button>
        {error && <p style={{ color: "red", marginTop: "0.5rem" }}>{error}</p>}
      </section>

      {enrichmentResult && (
        <section style={{ marginBottom: "1rem", border: "1px solid #ccc", padding: "0.75rem" }}>
          <h3>5. Enrichment Quality</h3>
          <p>Output: <strong>{enrichedArtifactName}</strong></p>
          <p>Match rate: {(enrichmentResult.match_rate * 100).toFixed(1)}% ({qualityBadge(enrichmentResult.match_rate)})</p>
        </section>
      )}

      <section style={{ marginBottom: "1rem", border: "1px solid #aaa", padding: "0.75rem" }}>
        <h3>6. Re-ID Parameters</h3>
        <p>
          Active ENRICHED input: 
          <strong> {activeEnriched?.file_name ?? "None"} </strong>
          {(!activeEnriched && session.active_enriched_artifact_id) && (
            <span style={{ color: "orange" }}> (ID mismatch or missing from inventory)</span>
          )}
        </p>

        {enrichedArtifacts.length > 0 && !activeEnriched && (
          <div style={{ marginBottom: "1rem", border: "1px dashed orange", padding: "0.5rem" }}>
            <p style={{ margin: 0, fontSize: "0.9rem" }}>Select an existing enriched artifact to use as input:</p>
            <select 
              value={session.active_enriched_artifact_id ?? ""} 
              onChange={(e) => handleActivateArtifact(e.target.value)}
              style={{ width: "100%", marginTop: "0.3rem" }}
            >
              <option value="">-- select enriched file --</option>
              {enrichedArtifacts.map(a => (
                <option key={a.artifact_id} value={a.artifact_id}>{a.file_name}</option>
              ))}
            </select>
          </div>
        )}

        <table style={{ borderCollapse: "collapse", width: "100%" }}><tbody>
          <tr><td>Global min merge threshold</td><td><input type="number" min={0} max={1} step={0.01} value={reidMinMerge} onChange={(e) => setReidMinMerge(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>Wi-Fi strong merge threshold</td><td><input type="number" min={0} max={1} step={0.01} value={wifiStrongMerge} onChange={(e) => setWifiStrongMerge(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>Wi-Fi weak/context threshold</td><td><input type="number" min={0} max={1} step={0.01} value={wifiWeakMerge} onChange={(e) => setWifiWeakMerge(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>BLE strong merge threshold</td><td><input type="number" min={0} max={1} step={0.01} value={bleStrongMerge} onChange={(e) => setBleStrongMerge(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>BLE weak/context threshold</td><td><input type="number" min={0} max={1} step={0.01} value={bleWeakMerge} onChange={(e) => setBleWeakMerge(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>Max time gap candidate (ms)</td><td><input type="number" min={1} step={100} value={maxGapMs} onChange={(e) => setMaxGapMs(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>Wi-Fi sequence gap threshold</td><td><input type="number" min={1} step={1} value={wifiSeqGap} onChange={(e) => setWifiSeqGap(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
          <tr><td>Min evidence for non-singleton</td><td><input type="number" min={1} step={1} value={minEvidence} onChange={(e) => setMinEvidence(Number(e.target.value))} style={{ width: "100px" }} /></td></tr>
        </tbody></table>

        <button
          onClick={handleRunReId}
          disabled={isRunningReid || !activeEnriched}
          style={{ padding: "0.5rem 1.5rem", marginTop: "0.75rem" }}
        >
          {isRunningReid ? "Running…" : "Run Re-ID"}
        </button>
      </section>

      {reidResult && (
        <section style={{ marginBottom: "1rem", border: "1px solid #0a0", padding: "0.75rem" }}>
          <h3>7. Re-ID Summary</h3>
          <p>Output REID artifact: <strong>{reidResult.output_reid_file}</strong></p>
          <p>Rows: {reidResult.row_count} | Clusters: {reidResult.cluster_count} | Singleton ratio: {(reidResult.quality_stats.singleton_ratio * 100).toFixed(1)}%</p>
          <p>High confidence ratio: {(reidResult.quality_stats.high_confidence_ratio * 100).toFixed(1)}%</p>
          <p>Active REID for Localization: <strong>{session.active_reid_artifact_id ? "Yes" : "No"}</strong></p>
          <button onClick={onOpenLocalization} disabled={!session.active_reid_artifact_id}>
            Open Localization
          </button>
        </section>
      )}

      {enrichedArtifacts.length > 0 && (
        <section style={{ marginBottom: "1rem" }}>
          <h3>Existing ENRICHED Artifacts</h3>
          <ul>
            {enrichedArtifacts.map((a: ArtifactRecord) => (
              <li key={a.artifact_id}>
                {a.file_name}
                {session.active_enriched_artifact_id === a.artifact_id && <span style={{ color: "green", marginLeft: "0.5rem" }}>[active]</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {reidArtifacts.length > 0 && (
        <section style={{ marginBottom: "1rem" }}>
          <h3>Existing REID Artifacts</h3>
          <ul>
            {reidArtifacts.map((a: ArtifactRecord) => (
              <li key={a.artifact_id}>
                {a.file_name}
                {session.active_reid_artifact_id === a.artifact_id && <span style={{ color: "green", marginLeft: "0.5rem" }}>[active for localization]</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
