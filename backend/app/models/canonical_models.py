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
    REID_ENRICHMENT = "reid_enrichment"
    LOCALIZATION = "localization"


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
