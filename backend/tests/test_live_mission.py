from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.live_mission import router
from app.modules.live_mission.service import LiveMissionService


def build_client(capacity: int = 1000) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    service = LiveMissionService(capacity=capacity)

    from app.core.dependencies import get_live_mission_service

    app.dependency_overrides[get_live_mission_service] = lambda: service
    return TestClient(app)


def test_start_ingest_and_fetch_packets() -> None:
    client = build_client()
    start = client.post("/api/live-mission/start")
    assert start.status_code == 200

    ingest = client.post(
        "/api/live-mission/packets",
        json={"protocol": "wifi", "device_id": "aa:bb:cc:dd:ee:ff", "rssi": -45, "frame_type": "beacon"},
    )
    assert ingest.status_code == 200
    assert ingest.json()["accepted"] == 1

    packets = client.get("/api/live-mission/packets?since_seq=0&limit=200")
    assert packets.status_code == 200
    body = packets.json()
    assert len(body["packets"]) == 1
    assert body["packets"][0]["seq"] == 1
    assert body["packets"][0]["protocol"] == "wifi"


def test_ingest_while_idle_rejects_all() -> None:
    client = build_client()
    response = client.post(
        "/api/live-mission/packets",
        json=[{"protocol": "ble"}, {"protocol": "wifi"}],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] == 0
    assert payload["rejected"] == 2


def test_clear_empties_buffer_and_preserves_status() -> None:
    client = build_client()
    client.post("/api/live-mission/start")
    client.post("/api/live-mission/packets", json={"protocol": "wifi"})

    cleared = client.post("/api/live-mission/clear")
    assert cleared.status_code == 200
    state = cleared.json()
    assert state["status"] == "running"
    assert state["buffer_size"] == 0
    assert state["received_count"] == 0
    assert state["dropped_count"] == 0


def test_overflow_updates_dropped_count() -> None:
    client = build_client(capacity=10)
    client.post("/api/live-mission/start")
    payload = [{"protocol": "unknown", "device_id": str(i)} for i in range(15)]
    client.post("/api/live-mission/packets", json=payload)

    state = client.get("/api/live-mission/state").json()
    assert state["buffer_size"] == 10
    assert state["dropped_count"] == 5


def test_since_seq_filters_seen_packets() -> None:
    client = build_client()
    client.post("/api/live-mission/start")
    client.post(
        "/api/live-mission/packets",
        json=[{"protocol": "wifi"}, {"protocol": "wifi"}, {"protocol": "ble"}],
    )

    response = client.get("/api/live-mission/packets?since_seq=2&limit=200")
    assert response.status_code == 200
    packets = response.json()["packets"]
    assert len(packets) == 1
    assert packets[0]["seq"] == 3


def test_double_start_returns_409() -> None:
    client = build_client()
    first = client.post("/api/live-mission/start")
    second = client.post("/api/live-mission/start")
    assert first.status_code == 200
    assert second.status_code == 409
