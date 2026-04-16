from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.canonical_models import (
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
