from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_execution_service
from app.models.api_models import ExecutionStatusResponse
from app.models.canonical_models import LocalizationRunPayload
from app.modules.executions.service import ExecutionService

router = APIRouter(tags=["executions"])


@router.get("/executions/{execution_id}", response_model=ExecutionStatusResponse)
def get_execution_status(
    execution_id: str,
    execution_service: ExecutionService = Depends(get_execution_service),
) -> ExecutionStatusResponse:
    try:
        execution = execution_service.get(execution_id)
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc

    localization = None
    raw_localization = execution.result_metadata.get("localization")
    if isinstance(raw_localization, dict):
        localization = LocalizationRunPayload.model_validate(raw_localization)
    return ExecutionStatusResponse(execution=execution, localization=localization)
