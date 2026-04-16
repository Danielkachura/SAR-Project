export type ProtocolMode = "wifi" | "ble" | "unknown";

export type StageSuggestion = "overview" | "reid_enrichment" | "localization";

export interface ScanFolder {
  folder_id: string;
  folder_name: string;
  path: string;
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
