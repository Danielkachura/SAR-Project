from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_reid_service, get_session_navigation_service
from app.models.api_models import ReIdRunRequest, ReIdRunResponse
from app.modules.reid.service import ReIdService
from app.modules.session_navigation.service import SessionNavigationService

router = APIRouter(tags=["reid"])


@router.post("/sessions/{session_id}/reid/run", response_model=ReIdRunResponse)
def post_reid_run(
    session_id: str,
    payload: ReIdRunRequest,
    service: ReIdService = Depends(get_reid_service),
    sessions: SessionNavigationService = Depends(get_session_navigation_service),
) -> ReIdRunResponse:
    try:
        result = service.run_reid(
            session_id=session_id,
            selected_enriched_artifact_id=payload.selected_enriched_artifact_id,
            parameters=payload.parameters,
        )
        session_state = sessions.require_session(session_id)
    except Exception as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc

    return ReIdRunResponse(reid=result, session=session_state)
