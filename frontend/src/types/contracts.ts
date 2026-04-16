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
  warnings: string[];
}
