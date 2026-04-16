from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_dataset_discovery_service, get_session_navigation_service
from app.models.api_models import ActivateArtifactRequest, InventoryResponse, SessionResponse
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.session_navigation.service import SessionNavigationService

router = APIRouter(tags=["inventory"])


@router.get("/sessions/{session_id}/inventory", response_model=InventoryResponse)
def get_inventory(
    session_id: str,
    sessions: SessionNavigationService = Depends(get_session_navigation_service),
    dataset: DatasetDiscoveryService = Depends(get_dataset_discovery_service),
) -> InventoryResponse:
    try:
        session = sessions.require_session(session_id)
        inventory = dataset.resolve_inventory(session.scan_folder_id)
        stage_jump = dataset.suggest_stage_jump(session=session, inventory=inventory)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InventoryResponse(inventory=inventory, stage_jump=stage_jump)


@router.post("/sessions/{session_id}/artifacts/activate", response_model=SessionResponse)
def activate_artifact(
    session_id: str,
    payload: ActivateArtifactRequest,
    sessions: SessionNavigationService = Depends(get_session_navigation_service),
) -> SessionResponse:
    try:
        session = sessions.activate_artifact(session_id=session_id, artifact_id=payload.artifact_id)
    except Exception as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc
    return SessionResponse(session=session)
