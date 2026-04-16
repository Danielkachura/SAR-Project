from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_enrichment_service
from app.models.api_models import EnrichmentRunRequest, EnrichmentRunResponse
from app.models.canonical_models import EnrichmentRunConfig
from app.modules.enrichment.service import EnrichmentService

router = APIRouter(tags=["enrichment"])


@router.post("/sessions/{session_id}/enrichment/run", response_model=EnrichmentRunResponse)
def post_enrichment_run(
    session_id: str,
    payload: EnrichmentRunRequest,
    service: EnrichmentService = Depends(get_enrichment_service),
) -> EnrichmentRunResponse:
    try:
        result = service.run_enrichment(
            session_id=session_id,
            selected_csv_file=payload.selected_csv_file,
            config=EnrichmentRunConfig(
                match_threshold=payload.match_threshold,
                match_time_window_ms=payload.match_time_window_ms,
                time_score_weight=payload.time_score_weight,
                identity_score_weight=payload.identity_score_weight,
                wifi_context_weight=payload.wifi_context_weight,
                ble_context_weight=payload.ble_context_weight,
            ),
        )
    except Exception as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc

    return EnrichmentRunResponse(enrichment=result)
