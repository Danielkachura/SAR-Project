from __future__ import annotations

from pydantic import BaseModel

from app.models.canonical_models import FolderInventory, ProtocolMode, ScanFolder, SessionState, StageJumpSuggestion


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
