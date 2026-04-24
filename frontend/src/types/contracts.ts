export type ProtocolMode = "wifi" | "ble" | "unknown";

export type StageSuggestion = "overview" | "calibration" | "reid_enrichment" | "localization";

export type CalibrationGtMode = "manual_map_click" | "first_sample" | "mean_first_k";

export type CalibrationPresetName = "urban" | "open_field" | "mixed_outdoor";

export interface ScanFolder {
  folder_id: string;
  folder_name: string;
  path: string;
}

export interface CalibrationParameters {
  rssi_at_1m: number;
  path_loss_n: number;
  sigma: number;
}

export interface CalibrationSelection {
  selected_csv_file: string;
  selected_mac: string;
}

export interface CalibrationDiagnostics {
  sample_count: number;
  inlier_count: number;
  inlier_ratio: number;
  distance_min_m: number;
  distance_max_m: number;
  distance_span_m: number;
  r2: number;
}

export interface CalibrationWarning {
  code: string;
  message: string;
}

export interface CalibrationSessionState {
  parameter_source: "derived" | "fallback";
  approved: boolean;
  parameters: CalibrationParameters;
  selection: CalibrationSelection;
  gt_mode: CalibrationGtMode;
  gt_first_k: number;
  enable_ransac: boolean;
  ransac_residual_threshold_db: number;
  ransac_iterations: number;
  distance_floor_m: number;
  diagnostics: CalibrationDiagnostics | null;
  warnings: CalibrationWarning[];
  fallback_name: CalibrationPresetName | null;
}

export interface SessionState {
  session_id: string;
  scan_folder_id: string;
  scan_folder_name: string;
  mode: ProtocolMode;
  mode_source: "detected" | "manual";
  current_stage: StageSuggestion;
  active_raw_csv_artifact_id: string | null;
  active_enriched_artifact_id: string | null;
  active_reid_artifact_id: string | null;
  selected_overview_csv_file: string | null;
  active_calibration: CalibrationSessionState | null;
  warnings: string[];
}

export interface ChartDatum {
  key: string;
  count: number;
}

export interface OverviewContext {
  session_id: string;
  mode: ProtocolMode;
  selected_csv_file: string | null;
  available_csv_files: string[];
  warnings: string[];
}

export interface OverviewSummaryStats {
  total_rows: number;
  unique_devices: number;
  average_rssi: number | null;
  vendor_company_counts: Record<string, number>;
}

export interface OverviewCharts {
  frame_or_event_type_distribution: ChartDatum[];
  top_vendors: ChartDatum[];
  rssi_histogram: ChartDatum[];
}

export interface OverviewPreview {
  columns: string[];
  rows: Record<string, string>[];
  total_rows: number;
  truncated: boolean;
}

export interface SpatialPoint {
  latitude: number;
  longitude: number;
  hover_metadata: Record<string, string>;
}

export interface OverviewSpatialPayload {
  points: SpatialPoint[];
}

export interface DeviceSummary {
  device_id: string;
  packet_count: number;
  average_rssi: number | null;
  vendor_or_company: string | null;
}

export interface OverviewDeviceAnalysis {
  devices: DeviceSummary[];
}

export interface OverviewPayload {
  context: OverviewContext;
  summary_stats: OverviewSummaryStats | null;
  charts: OverviewCharts | null;
  preview: OverviewPreview | null;
  spatial: OverviewSpatialPayload | null;
  device_analysis: OverviewDeviceAnalysis | null;
}

export interface CalibrationCandidateRecord {
  mac: string;
  sample_count: number;
}

export interface CalibrationCandidatesPayload {
  selected_csv_file: string;
  candidates: CalibrationCandidateRecord[];
}

export interface CalibrationScatterPoint {
  log10_distance: number;
  rssi: number;
  is_inlier: boolean;
}

export interface CalibrationFitLinePoint {
  log10_distance: number;
  predicted_rssi: number;
}

export interface CalibrationRunConfig {
  gt_mode: CalibrationGtMode;
  gt_first_k: number;
  enable_ransac: boolean;
  ransac_residual_threshold_db: number;
  ransac_iterations: number;
  distance_floor_m: number;
  manual_gt_latitude: number | null;
  manual_gt_longitude: number | null;
}

export interface CalibrationRunPayload {
  selected_csv_file: string;
  selected_mac: string;
  gt_point_latitude: number;
  gt_point_longitude: number;
  config: CalibrationRunConfig;
  scatter_points: CalibrationScatterPoint[];
  fit_line: CalibrationFitLinePoint[];
  parameters: CalibrationParameters;
  diagnostics: CalibrationDiagnostics;
  warnings: CalibrationWarning[];
}

export interface CalibrationFallbackPreset {
  name: CalibrationPresetName;
  label: string;
  parameters: CalibrationParameters;
}

// ---------------------------------------------------------------------------
// MOD-007 Enrichment
// ---------------------------------------------------------------------------

export type EnrichmentMatchMethod =
  | "time_identity_best_match"
  | "time_only_match"
  | "no_match";

export interface EnrichmentParameters {
  match_threshold?: number;
  match_time_window_ms?: number;
  time_score_weight?: number;
  identity_score_weight?: number;
  wifi_context_weight?: number;
  ble_context_weight?: number;
}

export interface EnrichmentDiagnostics {
  total_rows: number;
  matched_rows: number;
  unmatched_rows: number;
  match_rate: number;
}

export interface EnrichmentRunPayload {
  selected_csv_file: string;
  selected_pcap_file: string;
  output_enriched_file: string;
  protocol: ProtocolMode;
  parameters: EnrichmentParameters;
  diagnostics: EnrichmentDiagnostics;
}

export interface ArtifactRecord {
  artifact_id: string;
  file_name: string;
  kind: string;
  base_name: string;
  path: string;
  is_official: boolean;
}

export interface FolderInventory {
  folder_id: string;
  raw_csv_files: ArtifactRecord[];
  pcap_files: ArtifactRecord[];
  enriched_artifacts: ArtifactRecord[];
  reid_artifacts: ArtifactRecord[];
}
