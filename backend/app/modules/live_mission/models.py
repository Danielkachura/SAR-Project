from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MissionStatus = Literal["idle", "running", "stopped"]
PacketProtocol = Literal["wifi", "ble", "unknown"]


class LivePacketIn(BaseModel):
    protocol: PacketProtocol = "unknown"
    device_id: str | None = None
    rssi: float | None = None
    frame_type: str | None = None
    timestamp: datetime | None = None
    extra: dict = Field(default_factory=dict)


class LivePacket(LivePacketIn):
    seq: int
    received_at: datetime


class LiveMissionState(BaseModel):
    status: MissionStatus
    started_at: datetime | None
    stopped_at: datetime | None
    received_count: int
    dropped_count: int
    buffer_size: int
    buffer_capacity: int
    last_seq: int


class LivePacketsResponse(BaseModel):
    state: LiveMissionState
    packets: list[LivePacket]


class IngestResponse(BaseModel):
    accepted: int
    rejected: int
    state: LiveMissionState
