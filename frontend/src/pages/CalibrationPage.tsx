import { useEffect, useMemo, useState } from "react";

import {
  approveCalibration,
  fetchCalibrationCandidates,
  runCalibration,
  selectFallbackPreset,
} from "../api/calibration";
import { fetchOverview } from "../api/overview";
import { CalibrationControls } from "../components/calibration/CalibrationControls";
import { CalibrationDiagnostics } from "../components/calibration/CalibrationDiagnostics";
import { CalibrationScatter } from "../components/calibration/CalibrationScatter";
import { FallbackPresets } from "../components/calibration/FallbackPresets";
import type {
  CalibrationCandidateRecord,
  CalibrationFallbackPreset,
  CalibrationGtMode,
  CalibrationRunPayload,
  SessionState,
} from "../types/contracts";

interface Props {
  session: SessionState;
  onSessionUpdate: (session: SessionState) => void;
  onBackToOverview: () => void;
}

const fallbackPresets: CalibrationFallbackPreset[] = [
  {
    name: "urban",
    label: "Urban",
    parameters: { rssi_at_1m: -41.0, path_loss_n: 2.7, sigma: 5.0 },
  },
  {
    name: "open_field",
    label: "Open Field",
    parameters: { rssi_at_1m: -38.0, path_loss_n: 2.0, sigma: 3.0 },
  },
  {
    name: "mixed_outdoor",
    label: "Mixed Outdoor",
    parameters: { rssi_at_1m: -40.0, path_loss_n: 2.3, sigma: 4.0 },
  },
];

export function CalibrationPage({ session, onSessionUpdate, onBackToOverview }: Props) {
  const [availableCsvFiles, setAvailableCsvFiles] = useState<string[]>([]);
  const [selectedCsv, setSelectedCsv] = useState<string>(session.selected_overview_csv_file ?? "");
  const [candidateMacs, setCandidateMacs] = useState<CalibrationCandidateRecord[]>([]);
  const [selectedMac, setSelectedMac] = useState<string>("");
  const [gtMode, setGtMode] = useState<CalibrationGtMode>("mean_first_k");
  const [gtFirstK, setGtFirstK] = useState<number>(5);
  const [enableRansac, setEnableRansac] = useState<boolean>(true);
  const [ransacThreshold, setRansacThreshold] = useState<number>(4);
  const [ransacIterations, setRansacIterations] = useState<number>(100);
  const [distanceFloorM, setDistanceFloorM] = useState<number>(1);
  const [manualLat, setManualLat] = useState<string>("");
  const [manualLon, setManualLon] = useState<string>("");
  const [result, setResult] = useState<CalibrationRunPayload | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetchOverview(session.session_id, null)
      .then((overview) => {
        setAvailableCsvFiles(overview.context.available_csv_files);
      })
      .catch((err) => setError(String(err)));
  }, [session.session_id]);

  useEffect(() => {
    if (!selectedCsv) {
      setCandidateMacs([]);
      setSelectedMac("");
      return;
    }

    fetchCalibrationCandidates(session.session_id, selectedCsv)
      .then((payload) => {
        setCandidateMacs(payload.candidates);
        setSelectedMac((current) => {
          if (current && payload.candidates.some((item) => item.mac === current)) {
            return current;
          }
          return payload.candidates[0]?.mac ?? "";
        });
      })
      .catch((err) => {
        setCandidateMacs([]);
        setSelectedMac("");
        setError(String(err));
      });
  }, [selectedCsv, session.session_id]);

  const canRun = useMemo(() => {
    if (!selectedCsv || !selectedMac) return false;
    if (gtMode !== "manual_map_click") return true;
    return manualLat.trim() !== "" && manualLon.trim() !== "";
  }, [selectedCsv, selectedMac, gtMode, manualLat, manualLon]);

  const handleRun = async () => {
    if (!canRun) return;

    setIsLoading(true);
    setError("");
    setStatus("");
    try {
      const payload = await runCalibration(session.session_id, {
        selected_csv_file: selectedCsv,
        selected_mac: selectedMac,
        gt_mode: gtMode,
        gt_first_k: gtFirstK,
        enable_ransac: enableRansac,
        ransac_residual_threshold_db: ransacThreshold,
        ransac_iterations: ransacIterations,
        distance_floor_m: distanceFloorM,
        manual_gt_latitude: gtMode === "manual_map_click" ? Number(manualLat) : null,
        manual_gt_longitude: gtMode === "manual_map_click" ? Number(manualLon) : null,
      });
      setResult(payload);
      setStatus("Calibration run completed.");
    } catch (err) {
      setError(String(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!result) return;

    setIsLoading(true);
    setError("");
    try {
      const activeCalibration = await approveCalibration(session.session_id, result);
      onSessionUpdate({ ...session, active_calibration: activeCalibration });
      setStatus("Derived calibration approved and saved in session.");
    } catch (err) {
      setError(String(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleFallback = async (presetName: string) => {
    if (!selectedCsv || !selectedMac) return;

    setIsLoading(true);
    setError("");
    try {
      const payload = await selectFallbackPreset(session.session_id, selectedCsv, selectedMac, presetName);
      onSessionUpdate({ ...session, active_calibration: payload.active_calibration });
      setStatus(`Fallback preset selected: ${payload.fallback.preset.label}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section>
      <h1>Calibration</h1>
      <p>Session folder: {session.scan_folder_name}</p>
      <button onClick={onBackToOverview}>Back to Overview</button>

      <CalibrationControls
        selectedCsv={selectedCsv}
        onSelectedCsvChange={setSelectedCsv}
        availableCsvFiles={availableCsvFiles}
        selectedMac={selectedMac}
        onSelectedMacChange={setSelectedMac}
        candidateMacs={candidateMacs}
        gtMode={gtMode}
        onGtModeChange={setGtMode}
        gtFirstK={gtFirstK}
        onGtFirstKChange={setGtFirstK}
        enableRansac={enableRansac}
        onEnableRansacChange={setEnableRansac}
        ransacThreshold={ransacThreshold}
        onRansacThresholdChange={setRansacThreshold}
        ransacIterations={ransacIterations}
        onRansacIterationsChange={setRansacIterations}
        distanceFloorM={distanceFloorM}
        onDistanceFloorMChange={setDistanceFloorM}
        manualLat={manualLat}
        onManualLatChange={setManualLat}
        manualLon={manualLon}
        onManualLonChange={setManualLon}
        onRun={handleRun}
      />

      {result && (
        <>
          <CalibrationScatter result={result} />
          <CalibrationDiagnostics result={result} />
          <button onClick={handleApprove} disabled={isLoading}>
            Approve derived calibration
          </button>
        </>
      )}

      <FallbackPresets presets={fallbackPresets} onSelectPreset={handleFallback} disabled={!selectedCsv || !selectedMac || isLoading} />

      {session.active_calibration && (
        <section>
          <h2>Active Session Calibration</h2>
          <pre>{JSON.stringify(session.active_calibration, null, 2)}</pre>
        </section>
      )}

      {status && <p role="status">{status}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
