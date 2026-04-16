from __future__ import annotations

from enum import Enum
from typing import Literal

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
    warnings: list[str] = Field(default_factory=list)


class StageJumpSuggestion(BaseModel):
    suggested_stage: StageSuggestion
    reason: str
