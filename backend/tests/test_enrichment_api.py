"""API-level tests for the enrichment endpoint."""
from __future__ import annotations

import struct
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.enrichment import router
from app.core.dependencies import get_enrichment_service
from app.core.config import AppConfig
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.enrichment.service import EnrichmentService
from app.modules.session_navigation.service import SessionNavigationService
from app.storage.data_paths import DataPathResolver
from app.storage.session_store import InMemorySessionStore


def _pcap_global_header(link_type: int = 105) -> bytes:
    return struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, link_type)


def _pcap_packet(ts_sec: int, ts_usec: int, data: bytes) -> bytes:
    return struct.pack("<IIII", ts_sec, ts_usec, len(data), len(data)) + data


def _wifi_mgmt_frame(src: bytes, dst: bytes, bssid: bytes) -> bytes:
    fc = (0 << 0) | (0 << 2) | (4 << 4)
    return struct.pack("<HH", fc, 0) + dst + src + bssid + struct.pack("<H", 0)


@pytest.fixture()
def client_and_services(data_root: Path):
    config = AppConfig(repo_root=data_root.parent, runtime_root=data_root.parent, data_dir=data_root)
    resolver = DataPathResolver(config=config)
    dataset = DatasetDiscoveryService(path_resolver=resolver)
    sessions = SessionNavigationService(dataset_service=dataset, session_store=InMemorySessionStore())
    enrichment = EnrichmentService(session_service=sessions, dataset_service=dataset)

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_enrichment_service] = lambda: enrichment
    return TestClient(app), sessions, enrichment


def _make_folder(data_root: Path, name: str) -> tuple[str, Path]:
    folder = data_root / name
    folder.mkdir()

    csv_path = folder / "scan.csv"
    csv_path.write_text("timestamp,mac,rssi\n1000,aa:bb:cc:dd:ee:ff,-55\n", encoding="utf-8")

    src = bytes.fromhex("aabbccddeeff")
    dst = bytes.fromhex("112233445566")
    bssid = bytes.fromhex("ffeeddccbbaa")
    pkt = _wifi_mgmt_frame(src, dst, bssid)
    pcap = _pcap_global_header(105) + _pcap_packet(1000, 10_000, pkt)
    (folder / "scan.pcap").write_bytes(pcap)
    return name, folder


def test_enrichment_run_returns_200(client_and_services, data_root: Path) -> None:
    client, sessions, _ = client_and_services
    folder_id, _ = _make_folder(data_root, "enr_wifi")
    session = sessions.create_session(folder_id)

    resp = client.post(f"/api/sessions/{session.session_id}/enrichment/run", json={
        "selected_csv_file": "scan.csv",
        "selected_pcap_file": "scan.pcap",
        "parameters": {},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["enrichment"]["output_enriched_file"] == "scan_ENRICHED.csv"
    assert body["enrichment"]["diagnostics"]["total_rows"] == 1
    assert body["enrichment"]["diagnostics"]["matched_rows"] == 1
    assert "session" in body


def test_enrichment_run_auto_detects_pcap(client_and_services, data_root: Path) -> None:
    client, sessions, _ = client_and_services
    folder_id, _ = _make_folder(data_root, "enr_wifi3")
    session = sessions.create_session(folder_id)

    resp = client.post(f"/api/sessions/{session.session_id}/enrichment/run", json={
        "selected_csv_file": "scan.csv",
        # selected_pcap_file omitted — should auto-detect scan.pcap
    })
    assert resp.status_code == 200
    assert resp.json()["enrichment"]["selected_pcap_file"] == "scan.pcap"


def test_enrichment_missing_csv_returns_400(client_and_services, data_root: Path) -> None:
    client, sessions, _ = client_and_services
    folder_id, _ = _make_folder(data_root, "enr_wifi2")
    session = sessions.create_session(folder_id)

    resp = client.post(f"/api/sessions/{session.session_id}/enrichment/run", json={
        "selected_csv_file": "ghost.csv",
        "selected_pcap_file": "scan.pcap",
    })
    assert resp.status_code == 400


def test_enrichment_unknown_session_returns_404(client_and_services, data_root: Path) -> None:
    client, _, __ = client_and_services
    resp = client.post("/api/sessions/no-such-session/enrichment/run", json={
        "selected_csv_file": "scan.csv",
        "selected_pcap_file": "scan.pcap",
    })
    assert resp.status_code == 404
