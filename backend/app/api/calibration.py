from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_calibration_service
from app.models.api_models import (
    CalibrationApproveRequest,
    CalibrationCandidatesRequest,
    CalibrationCandidatesResponse,
    CalibrationFallbackRequest,
    CalibrationFallbackResponse,
    CalibrationRunRequest,
    CalibrationRunResponse,
    CalibrationSaveResponse,
)
from app.models.canonical_models import CalibrationRunConfig
from app.modules.calibration.service import CalibrationService

router = APIRouter(tags=["calibration"])


@router.post("/sessions/{session_id}/calibration/candidates", response_model=CalibrationCandidatesResponse)
def post_calibration_candidates(
    session_id: str,
    payload: CalibrationCandidatesRequest,
    service: CalibrationService = Depends(get_calibration_service),
) -> CalibrationCandidatesResponse:
    try:
        candidates = service.list_mac_candidates(session_id=session_id, selected_csv_file=payload.selected_csv_file)
    except Exception as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc

    return CalibrationCandidatesResponse(candidates=candidates)


@router.post("/sessions/{session_id}/calibration/run", response_model=CalibrationRunResponse)
def post_calibration_run(
    session_id: str,
    payload: CalibrationRunRequest,
    service: CalibrationService = Depends(get_calibration_service),
) -> CalibrationRunResponse:
    try:
        result = service.run_calibration(
            session_id=session_id,
            selected_csv_file=payload.selected_csv_file,
            selected_mac=payload.selected_mac,
            config=CalibrationRunConfig(
                gt_mode=payload.gt_mode,
                gt_first_k=payload.gt_first_k,
                enable_ransac=payload.enable_ransac,
                ransac_residual_threshold_db=payload.ransac_residual_threshold_db,
                ransac_iterations=payload.ransac_iterations,
                distance_floor_m=payload.distance_floor_m,
                manual_gt_latitude=payload.manual_gt_latitude,
                manual_gt_longitude=payload.manual_gt_longitude,
            ),
        )
    except Exception as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc

    return CalibrationRunResponse(calibration=result)


@router.post("/sessions/{session_id}/calibration/approve", response_model=CalibrationSaveResponse)
def post_calibration_approve(
    session_id: str,
    payload: CalibrationApproveRequest,
    service: CalibrationService = Depends(get_calibration_service),
) -> CalibrationSaveResponse:
    try:
        saved = service.approve_derived_calibration(session_id=session_id, result=payload.calibration)
    except Exception as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc

    return CalibrationSaveResponse(active_calibration=saved)


@router.post("/sessions/{session_id}/calibration/fallback", response_model=CalibrationFallbackResponse)
def post_calibration_fallback(
    session_id: str,
    payload: CalibrationFallbackRequest,
    service: CalibrationService = Depends(get_calibration_service),
) -> CalibrationFallbackResponse:
    try:
        fallback = service.select_fallback_preset(
            session_id=session_id,
            selected_csv_file=payload.selected_csv_file,
            selected_mac=payload.selected_mac,
            preset_name=payload.preset_name,
        )
        active_calibration = service.get_active_calibration(session_id=session_id)
        assert active_calibration is not None
    except Exception as exc:
        message = str(exc)
        code = 404 if "not found" in message.lower() else 400
        raise HTTPException(status_code=code, detail=message) from exc

    return CalibrationFallbackResponse(fallback=fallback, active_calibration=active_calibration)
