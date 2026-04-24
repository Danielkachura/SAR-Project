from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_enrichment_service
from app.models.api_models import EnrichmentRunRequest, EnrichmentRunResponse
from app.modules.enrichment.service import EnrichmentService

router = APIRouter(tags=["enrichment"])


@router.post("/sessions/{session_id}/enrichment/run", response_model=EnrichmentRunResponse)
def post_enrichment_run(
    session_id: str,
    payload: EnrichmentRunRequest,
    service: EnrichmentService = Depends(get_enrichment_service),
) -> EnrichmentRunResponse:
    try:
        # Auto-detect matching PCAP by basename if caller omitted it
        pcap_file = payload.selected_pcap_file
        if pcap_file is None:
            session = service._session_service.require_session(session_id)
            pcap_file = service.resolve_matching_pcap(session.scan_folder_id, payload.selected_csv_file)

        result = service.run_enrichment(
            session_id=session_id,
            selected_csv_file=payload.selected_csv_file,
            selected_pcap_file=pcap_file,
            parameters=payload.parameters,
        )
        session_state = service._session_service.require_session(session_id)
    except Exception as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc

    return EnrichmentRunResponse(enrichment=result, session=session_state)
