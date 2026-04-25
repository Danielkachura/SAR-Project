"""API-level tests for the enrichment endpoint."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.enrichment import router
from app.core.config import AppConfig
from app.core.dependencies import get_enrichment_service
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.enrichment.service import EnrichmentService
from app.modules.session_navigation.service import SessionNavigationService
from app.storage.data_paths import DataPathResolver
from app.storage.session_store import InMemorySessionStore


def _write_wifi_pcap(path: Path, frames: list[tuple[float, str, str, str, str]]) -> None:
    from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap, wrpcap

    pkts = []
    for ts, src, dst, bssid, ssid in frames:
        pkt = (
            RadioTap()
            / Dot11(type=0, subtype=8, addr1=dst, addr2=src, addr3=bssid)
            / Dot11Beacon(cap="ESS")
            / Dot11Elt(ID=0, info=ssid.encode("utf-8"))
        )
        pkt.time = ts
        pkts.append(pkt)
    wrpcap(str(path), pkts)


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
    (folder / "scan.csv").write_text(
        "timestamp_utc,src_mac,rssi_dbm\n"
        "2025-12-15T09:58:14Z,aa:bb:cc:dd:ee:ff,-50\n",
        encoding="utf-8",
    )
    _write_wifi_pcap(
        folder / "scan.pcap",
        [(pd.Timestamp("2025-12-15T09:58:14.005Z").timestamp(),
          "aa:bb:cc:dd:ee:ff", "ff:ff:ff:ff:ff:ff", "aa:bb:cc:dd:ee:ff", "Liat")],
    )
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
    assert resp.status_code == 200, resp.text
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
    })
    assert resp.status_code == 200, resp.text
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
