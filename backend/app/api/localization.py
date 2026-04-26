from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_execution_service, get_localization_service
from app.models.api_models import LocalizationRunRequest, LocalizationRunResponse
from app.modules.executions.service import ExecutionService
from app.modules.localization.service import LocalizationService

router = APIRouter(tags=["localization"])


@router.post("/sessions/{session_id}/localization/run", response_model=LocalizationRunResponse)
def post_localization_run(
    session_id: str,
    payload: LocalizationRunRequest,
    localization_service: LocalizationService = Depends(get_localization_service),
    execution_service: ExecutionService = Depends(get_execution_service),
) -> LocalizationRunResponse:
    try:
        execution = execution_service.start_execution(
            stage="localization",
            session_id=session_id,
            runner=lambda: _run_localization(localization_service, session_id, payload),
        )
        return LocalizationRunResponse(execution=execution)
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc


def _run_localization(
    localization_service: LocalizationService,
    session_id: str,
    payload: LocalizationRunRequest,
) -> tuple[dict[str, str | int | dict], list[str]]:
    result = localization_service.run_localization(
        session_id=session_id,
        selected_reid_artifact_id=payload.selected_reid_artifact_id,
        parameters=payload.parameters,
        pre_filters=payload.pre_filters,
    )
    metadata = {
        "input_reid_file": result.input_reid_file,
        "cluster_count": len(result.cluster_results),
        "succeeded_clusters": sum(1 for item in result.cluster_results if item.status == "succeeded"),
        "localization": result.model_dump(),
    }
    return metadata, result.warnings
