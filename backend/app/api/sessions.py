from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.main import get_session_navigation_service
from app.models.api_models import CreateSessionRequest, ScanFolderListResponse, SessionResponse, UpdateModeRequest
from app.modules.session_navigation.service import SessionNavigationService

router = APIRouter(tags=["sessions"])


@router.get("/scan-folders", response_model=ScanFolderListResponse)
def list_scan_folders(service: SessionNavigationService = Depends(get_session_navigation_service)) -> ScanFolderListResponse:
    folders = service.list_scan_folders()
    return ScanFolderListResponse(folders=folders)


@router.post("/sessions", response_model=SessionResponse)
def create_session(
    payload: CreateSessionRequest,
    service: SessionNavigationService = Depends(get_session_navigation_service),
) -> SessionResponse:
    try:
        session = service.create_session(payload.folder_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionResponse(session=session)


@router.patch("/sessions/{session_id}/mode", response_model=SessionResponse)
def set_mode(
    session_id: str,
    payload: UpdateModeRequest,
    service: SessionNavigationService = Depends(get_session_navigation_service),
) -> SessionResponse:
    try:
        session = service.set_mode(session_id, payload.mode.value)
    except Exception as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc
    return SessionResponse(session=session)


@router.get("/sessions/{session_id}/state", response_model=SessionResponse)
def get_state(session_id: str, service: SessionNavigationService = Depends(get_session_navigation_service)) -> SessionResponse:
    try:
        session = service.require_session(session_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionResponse(session=session)
