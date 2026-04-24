from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.canonical_models import (
    CalibrationCandidatesPayload,
    CalibrationFallbackSelection,
    CalibrationGtMode,
    CalibrationRunPayload,
    CalibrationSessionState,
    EnrichmentParameters,
    EnrichmentRunPayload,
    FolderInventory,
    OverviewPayload,
    ProtocolMode,
    ScanFolder,
    SessionState,
    StageJumpSuggestion,
)


class ScanFolderListResponse(BaseModel):
    folders: list[ScanFolder]


class CreateSessionRequest(BaseModel):
    folder_id: str


class UpdateModeRequest(BaseModel):
    mode: ProtocolMode


class ActivateArtifactRequest(BaseModel):
    artifact_id: str


class SessionResponse(BaseModel):
    session: SessionState


class InventoryResponse(BaseModel):
    inventory: FolderInventory
    stage_jump: StageJumpSuggestion


class OverviewRequest(BaseModel):
    selected_csv_file: str | None = None
    preview_limit: int = Field(default=50, ge=1, le=500)


class OverviewResponse(BaseModel):
    overview: OverviewPayload


class CalibrationCandidatesRequest(BaseModel):
    selected_csv_file: str


class CalibrationCandidatesResponse(BaseModel):
    candidates: CalibrationCandidatesPayload


class CalibrationRunRequest(BaseModel):
    selected_csv_file: str
    selected_mac: str
    gt_mode: CalibrationGtMode = CalibrationGtMode.MEAN_FIRST_K
    gt_first_k: int = Field(default=5, ge=1, le=20)
    enable_ransac: bool = True
    ransac_residual_threshold_db: float = Field(default=4, ge=1, le=15)
    ransac_iterations: int = Field(default=100, ge=10, le=1000)
    distance_floor_m: float = Field(default=1, ge=0.5, le=5)
    manual_gt_latitude: float | None = None
    manual_gt_longitude: float | None = None


class CalibrationRunResponse(BaseModel):
    calibration: CalibrationRunPayload


class CalibrationApproveRequest(BaseModel):
    calibration: CalibrationRunPayload


class CalibrationFallbackRequest(BaseModel):
    selected_csv_file: str
    selected_mac: str
    preset_name: str


class CalibrationSaveResponse(BaseModel):
    active_calibration: CalibrationSessionState


class CalibrationFallbackResponse(BaseModel):
    fallback: CalibrationFallbackSelection
    active_calibration: CalibrationSessionState


class EnrichmentRunRequest(BaseModel):
    selected_csv_file: str
    selected_pcap_file: str | None = None  # auto-detected by basename if omitted
    parameters: EnrichmentParameters = Field(default_factory=EnrichmentParameters)


class EnrichmentRunResponse(BaseModel):
    enrichment: EnrichmentRunPayload
    session: SessionState
