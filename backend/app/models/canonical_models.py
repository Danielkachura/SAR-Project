from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProtocolMode(str, Enum):
    WIFI = "wifi"
    BLE = "ble"
    UNKNOWN = "unknown"


class ArtifactKind(str, Enum):
    RAW_CSV = "raw_csv"
    PCAP = "pcap"
    ENRICHED_CSV = "enriched_csv"
    REID_CSV = "reid_csv"


class StageSuggestion(str, Enum):
    OVERVIEW = "overview"
    CALIBRATION = "calibration"
    REID_ENRICHMENT = "reid_enrichment"
    LOCALIZATION = "localization"


class CalibrationGtMode(str, Enum):
    MANUAL_MAP_CLICK = "manual_map_click"
    FIRST_SAMPLE = "first_sample"
    MEAN_FIRST_K = "mean_first_k"


class CalibrationPresetName(str, Enum):
    URBAN = "urban"
    OPEN_FIELD = "open_field"
    MIXED_OUTDOOR = "mixed_outdoor"


class CalibrationWarningCode(str, Enum):
    LOW_SAMPLE_COUNT = "low_sample_count"
    LOW_INLIER_RATIO = "low_inlier_ratio"
    LOW_R2 = "low_r2"
    LOW_DISTANCE_SPAN = "low_distance_span"


class ScanFolder(BaseModel):
    folder_id: str
    folder_name: str
    path: str


class ArtifactRecord(BaseModel):
    artifact_id: str
    file_name: str
    kind: ArtifactKind
    base_name: str
    path: str
    is_official: bool = False


class FolderInventory(BaseModel):
    folder_id: str
    raw_csv_files: list[ArtifactRecord] = Field(default_factory=list)
    pcap_files: list[ArtifactRecord] = Field(default_factory=list)
    enriched_artifacts: list[ArtifactRecord] = Field(default_factory=list)
    reid_artifacts: list[ArtifactRecord] = Field(default_factory=list)


class CalibrationParameters(BaseModel):
    rssi_at_1m: float
    path_loss_n: float
    sigma: float


class CalibrationSelection(BaseModel):
    selected_csv_file: str
    selected_mac: str


class CalibrationDiagnostics(BaseModel):
    sample_count: int
    inlier_count: int
    inlier_ratio: float
    distance_min_m: float
    distance_max_m: float
    distance_span_m: float
    r2: float


class CalibrationWarning(BaseModel):
    code: CalibrationWarningCode
    message: str


class CalibrationSessionState(BaseModel):
    parameter_source: Literal["derived", "fallback"]
    approved: bool
    parameters: CalibrationParameters
    selection: CalibrationSelection
    gt_mode: CalibrationGtMode
    gt_first_k: int = 5
    enable_ransac: bool = True
    ransac_residual_threshold_db: float = 4
    ransac_iterations: int = 100
    distance_floor_m: float = 1
    diagnostics: CalibrationDiagnostics | None = None
    warnings: list[CalibrationWarning] = Field(default_factory=list)
    fallback_name: CalibrationPresetName | None = None


class SessionState(BaseModel):
    session_id: str
    scan_folder_id: str
    scan_folder_name: str
    mode: ProtocolMode
    mode_source: Literal["detected", "manual"] = "detected"
    current_stage: StageSuggestion = StageSuggestion.OVERVIEW
    active_raw_csv_artifact_id: str | None = None
    active_enriched_artifact_id: str | None = None
    active_reid_artifact_id: str | None = None
    selected_overview_csv_file: str | None = None
    active_calibration: CalibrationSessionState | None = None
    warnings: list[str] = Field(default_factory=list)


class StageJumpSuggestion(BaseModel):
    suggested_stage: StageSuggestion
    reason: str


class OverviewContext(BaseModel):
    session_id: str
    mode: ProtocolMode
    selected_csv_file: str | None = None
    available_csv_files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OverviewSummaryStats(BaseModel):
    total_rows: int
    unique_devices: int
    average_rssi: float | None = None
    vendor_company_counts: dict[str, int] = Field(default_factory=dict)


class ChartDatum(BaseModel):
    key: str
    count: int


class OverviewCharts(BaseModel):
    frame_or_event_type_distribution: list[ChartDatum] = Field(default_factory=list)
    top_vendors: list[ChartDatum] = Field(default_factory=list)
    rssi_histogram: list[ChartDatum] = Field(default_factory=list)


class OverviewPreview(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    total_rows: int
    truncated: bool = False


class SpatialPoint(BaseModel):
    latitude: float
    longitude: float
    hover_metadata: dict[str, Any] = Field(default_factory=dict)


class OverviewSpatialPayload(BaseModel):
    points: list[SpatialPoint] = Field(default_factory=list)


class DeviceSummary(BaseModel):
    device_id: str
    packet_count: int
    average_rssi: float | None = None
    vendor_or_company: str | None = None


class OverviewDeviceAnalysis(BaseModel):
    devices: list[DeviceSummary] = Field(default_factory=list)


class OverviewPayload(BaseModel):
    context: OverviewContext
    summary_stats: OverviewSummaryStats | None = None
    charts: OverviewCharts | None = None
    preview: OverviewPreview | None = None
    spatial: OverviewSpatialPayload | None = None
    device_analysis: OverviewDeviceAnalysis | None = None


class CalibrationCandidateRecord(BaseModel):
    mac: str
    sample_count: int


class CalibrationCandidatesPayload(BaseModel):
    selected_csv_file: str
    candidates: list[CalibrationCandidateRecord] = Field(default_factory=list)


class CalibrationScatterPoint(BaseModel):
    log10_distance: float
    rssi: float
    is_inlier: bool


class CalibrationFitLinePoint(BaseModel):
    log10_distance: float
    predicted_rssi: float


class CalibrationRunConfig(BaseModel):
    gt_mode: CalibrationGtMode = CalibrationGtMode.MEAN_FIRST_K
    gt_first_k: int = Field(default=5, ge=1, le=20)
    enable_ransac: bool = True
    ransac_residual_threshold_db: float = Field(default=4, ge=1, le=15)
    ransac_iterations: int = Field(default=100, ge=10, le=1000)
    distance_floor_m: float = Field(default=1, ge=0.5, le=5)
    manual_gt_latitude: float | None = None
    manual_gt_longitude: float | None = None


class CalibrationRunPayload(BaseModel):
    selected_csv_file: str
    selected_mac: str
    gt_point_latitude: float
    gt_point_longitude: float
    config: CalibrationRunConfig
    scatter_points: list[CalibrationScatterPoint] = Field(default_factory=list)
    fit_line: list[CalibrationFitLinePoint] = Field(default_factory=list)
    parameters: CalibrationParameters
    diagnostics: CalibrationDiagnostics
    warnings: list[CalibrationWarning] = Field(default_factory=list)


class CalibrationFallbackPreset(BaseModel):
    name: CalibrationPresetName
    label: str
    parameters: CalibrationParameters


class CalibrationFallbackSelection(BaseModel):
    selected_csv_file: str
    selected_mac: str
    preset: CalibrationFallbackPreset
