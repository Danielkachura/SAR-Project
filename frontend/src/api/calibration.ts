import { apiPost } from "./client";
import type {
  CalibrationCandidatesPayload,
  CalibrationFallbackPreset,
  CalibrationGtMode,
  CalibrationRunPayload,
  CalibrationSessionState,
} from "../types/contracts";

export interface RunCalibrationParams {
  selected_csv_file: string;
  selected_mac: string;
  gt_mode?: CalibrationGtMode;
  gt_first_k?: number;
  enable_ransac?: boolean;
  ransac_residual_threshold_db?: number;
  ransac_iterations?: number;
  distance_floor_m?: number;
  manual_gt_latitude?: number | null;
  manual_gt_longitude?: number | null;
}

export async function fetchCalibrationCandidates(
  sessionId: string,
  selectedCsvFile: string,
): Promise<CalibrationCandidatesPayload> {
  const payload = await apiPost<{ candidates: CalibrationCandidatesPayload }>(
    `/sessions/${sessionId}/calibration/candidates`,
    { selected_csv_file: selectedCsvFile },
  );
  return payload.candidates;
}

export async function runCalibration(
  sessionId: string,
  params: RunCalibrationParams,
): Promise<CalibrationRunPayload> {
  const payload = await apiPost<{ calibration: CalibrationRunPayload }>(
    `/sessions/${sessionId}/calibration/run`,
    {
      gt_mode: params.gt_mode ?? "mean_first_k",
      gt_first_k: params.gt_first_k ?? 5,
      enable_ransac: params.enable_ransac ?? true,
      ransac_residual_threshold_db: params.ransac_residual_threshold_db ?? 4,
      ransac_iterations: params.ransac_iterations ?? 100,
      distance_floor_m: params.distance_floor_m ?? 1,
      manual_gt_latitude: params.manual_gt_latitude ?? null,
      manual_gt_longitude: params.manual_gt_longitude ?? null,
      selected_csv_file: params.selected_csv_file,
      selected_mac: params.selected_mac,
    },
  );
  return payload.calibration;
}

export async function approveCalibration(
  sessionId: string,
  calibration: CalibrationRunPayload,
): Promise<CalibrationSessionState> {
  const payload = await apiPost<{ active_calibration: CalibrationSessionState }>(
    `/sessions/${sessionId}/calibration/approve`,
    { calibration },
  );
  return payload.active_calibration;
}

export async function selectFallbackPreset(
  sessionId: string,
  selectedCsvFile: string,
  selectedMac: string,
  presetName: string,
): Promise<{ fallback: { preset: CalibrationFallbackPreset }; active_calibration: CalibrationSessionState }> {
  return apiPost(`/sessions/${sessionId}/calibration/fallback`, {
    selected_csv_file: selectedCsvFile,
    selected_mac: selectedMac,
    preset_name: presetName,
  });
}
