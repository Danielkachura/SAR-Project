from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from scapy.all import Dot11, Dot11ProbeReq, RadioTap, wrpcap  # type: ignore

from app.api.enrichment import router
from app.core.dependencies import get_enrichment_service
from app.modules.enrichment.service import EnrichmentService


def test_enrichment_api_run(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    (folder / "scan.csv").write_text(
        "timestamp_ms,mac,bssid,channel\n1000000,AA:BB:CC:11:22:33,AA:BB:CC:11:22:33,1\n",
        encoding="utf-8",
    )

    packet = RadioTap() / Dot11(type=0, subtype=4, addr1="ff:ff:ff:ff:ff:ff", addr2="AA:BB:CC:11:22:33", addr3="AA:BB:CC:11:22:33") / Dot11ProbeReq()
    packet.time = 1000.0
    wrpcap(str(folder / "scan.pcap"), [packet])

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_wifi")

    app = FastAPI()
    app.include_router(router, prefix="/api")

    def _get_enrichment_service() -> EnrichmentService:
        return enrichment

    app.dependency_overrides[get_enrichment_service] = _get_enrichment_service
    client = TestClient(app)

    response = client.post(
        f"/api/sessions/{session.session_id}/enrichment/run",
        json={"selected_csv_file": "scan.csv"},
    )

    assert response.status_code == 200
    payload = response.json()["enrichment"]
    assert payload["output_file_name"] == "scan_ENRICHED.csv"
    assert payload["quality_stats"]["matched_row_ratio"] == 1.0
