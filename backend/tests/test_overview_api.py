from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.overview import router
from app.modules.overview.service import OverviewService


def test_overview_api_returns_expected_categories(overview_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    (folder / "scan.csv").write_text(
        "timestamp,mac,rssi,vendor,frame_type,latitude,longitude\n"
        "1,AA,-70,Acme,probe,-37.1,144.9\n",
        encoding="utf-8",
    )

    _, sessions, overview = overview_services
    session = sessions.create_session("mission_wifi")

    app = FastAPI()
    app.include_router(router, prefix="/api")

    def _get_overview_service() -> OverviewService:
        return overview

    app.dependency_overrides.clear()
    from app.core.dependencies import get_overview_service

    app.dependency_overrides[get_overview_service] = _get_overview_service
    client = TestClient(app)

    response = client.post(
        f"/api/sessions/{session.session_id}/overview",
        json={"selected_csv_file": "scan.csv", "preview_limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()["overview"]
    assert set(payload.keys()) == {
        "context",
        "summary_stats",
        "charts",
        "preview",
        "spatial",
        "device_analysis",
    }
