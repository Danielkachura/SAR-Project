from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
import threading

from app.modules.live_mission.models import LiveMissionState, LivePacket, LivePacketIn, MissionStatus

BUFFER_CAPACITY = 1000


class LiveMissionService:
    def __init__(self, capacity: int = BUFFER_CAPACITY) -> None:
        self._capacity = capacity
        self._lock = threading.Lock()
        self._buffer: deque[LivePacket] = deque(maxlen=self._capacity)
        self._status: MissionStatus = "idle"
        self._started_at: datetime | None = None
        self._stopped_at: datetime | None = None
        self._received_count = 0
        self._dropped_count = 0
        self._seq_counter = 0

    def start(self) -> LiveMissionState:
        with self._lock:
            if self._status == "running":
                raise ValueError("Mission is already running.")
            self._status = "running"
            now = datetime.now(UTC)
            self._started_at = now
            self._stopped_at = None
            self._buffer.clear()
            self._received_count = 0
            self._dropped_count = 0
            self._seq_counter = 0
            return self._state_locked()

    def stop(self) -> LiveMissionState:
        with self._lock:
            if self._status != "running":
                raise ValueError("Mission is not running.")
            self._status = "stopped"
            self._stopped_at = datetime.now(UTC)
            return self._state_locked()

    def clear(self) -> LiveMissionState:
        with self._lock:
            self._buffer.clear()
            self._received_count = 0
            self._dropped_count = 0
            self._seq_counter = 0
            return self._state_locked()

    def ingest(self, packets: list[LivePacketIn]) -> tuple[int, int]:
        with self._lock:
            if self._status != "running":
                return 0, len(packets)

            accepted = 0
            for packet in packets:
                now = datetime.now(UTC)
                self._seq_counter += 1
                before_len = len(self._buffer)
                live_packet = LivePacket(
                    seq=self._seq_counter,
                    received_at=now,
                    protocol=packet.protocol,
                    device_id=packet.device_id,
                    rssi=packet.rssi,
                    frame_type=packet.frame_type,
                    timestamp=packet.timestamp or now,
                    extra=packet.extra,
                )
                self._buffer.append(live_packet)
                after_len = len(self._buffer)
                if before_len == self._capacity and after_len == self._capacity:
                    self._dropped_count += 1
                self._received_count += 1
                accepted += 1

            return accepted, len(packets) - accepted

    def get_state(self) -> LiveMissionState:
        with self._lock:
            return self._state_locked()

    def get_packets(self, since_seq: int, limit: int) -> list[LivePacket]:
        with self._lock:
            items = [packet for packet in self._buffer if packet.seq > since_seq]
            return items[:limit]

    def _state_locked(self) -> LiveMissionState:
        last_seq = self._buffer[-1].seq if self._buffer else 0
        return LiveMissionState(
            status=self._status,
            started_at=self._started_at,
            stopped_at=self._stopped_at,
            received_count=self._received_count,
            dropped_count=self._dropped_count,
            buffer_size=len(self._buffer),
            buffer_capacity=self._capacity,
            last_seq=last_seq,
        )
