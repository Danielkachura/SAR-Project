from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_live_mission_service
from app.modules.live_mission.models import IngestResponse, LiveMissionState, LivePacketIn, LivePacketsResponse
from app.modules.live_mission.service import LiveMissionService

router = APIRouter(prefix="/live-mission", tags=["live-mission"])


@router.post("/start", response_model=LiveMissionState)
def start_live_mission(service: LiveMissionService = Depends(get_live_mission_service)) -> LiveMissionState:
    try:
        return service.start()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/stop", response_model=LiveMissionState)
def stop_live_mission(service: LiveMissionService = Depends(get_live_mission_service)) -> LiveMissionState:
    try:
        return service.stop()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/clear", response_model=LiveMissionState)
def clear_live_mission(service: LiveMissionService = Depends(get_live_mission_service)) -> LiveMissionState:
    return service.clear()


@router.post("/packets", response_model=IngestResponse)
def ingest_live_packets(
    payload: LivePacketIn | list[LivePacketIn],
    service: LiveMissionService = Depends(get_live_mission_service),
) -> IngestResponse:
    packets = payload if isinstance(payload, list) else [payload]
    accepted, rejected = service.ingest(packets)
    return IngestResponse(accepted=accepted, rejected=rejected, state=service.get_state())


@router.get("/state", response_model=LiveMissionState)
def get_live_mission_state(service: LiveMissionService = Depends(get_live_mission_service)) -> LiveMissionState:
    return service.get_state()


@router.get("/packets", response_model=LivePacketsResponse)
def get_live_packets(
    since_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    service: LiveMissionService = Depends(get_live_mission_service),
) -> LivePacketsResponse:
    state = service.get_state()
    packets = service.get_packets(since_seq=since_seq, limit=limit)
    return LivePacketsResponse(state=state, packets=packets)
