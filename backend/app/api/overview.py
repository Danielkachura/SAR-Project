from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_overview_service
from app.models.api_models import OverviewRequest, OverviewResponse
from app.modules.overview.service import OverviewService

router = APIRouter(tags=["overview"])


@router.post("/sessions/{session_id}/overview", response_model=OverviewResponse)
def post_overview(
    session_id: str,
    payload: OverviewRequest,
    overview_service: OverviewService = Depends(get_overview_service),
) -> OverviewResponse:
    try:
        overview = overview_service.build_overview(
            session_id=session_id,
            selected_csv_file=payload.selected_csv_file,
            preview_limit=payload.preview_limit,
        )
    except Exception as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc

    return OverviewResponse(overview=overview)
