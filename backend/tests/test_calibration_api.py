from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.calibration import router
from app.core.dependencies import get_calibration_service
from app.modules.calibration.service import CalibrationService


def test_calibration_api_flow(calibration_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    (folder / "calib.csv").write_text(
        "timestamp,mac,rssi,latitude,longitude\n"
        "1,AA,-40,37.00000,-122.00000\n"
        "2,AA,-43,37.00003,-122.00000\n"
        "3,AA,-47,37.00006,-122.00000\n"
        "4,AA,-51,37.00009,-122.00000\n",
        encoding="utf-8",
    )

    _, sessions, calibration = calibration_services
    session = sessions.create_session("mission_wifi")

    app = FastAPI()
    app.include_router(router, prefix="/api")

    def _get_calibration_service() -> CalibrationService:
        return calibration

    app.dependency_overrides[get_calibration_service] = _get_calibration_service
    client = TestClient(app)

    candidates_response = client.post(
        f"/api/sessions/{session.session_id}/calibration/candidates",
        json={"selected_csv_file": "calib.csv"},
    )
    assert candidates_response.status_code == 200
    assert candidates_response.json()["candidates"]["candidates"][0]["mac"] == "AA"

    run_response = client.post(
        f"/api/sessions/{session.session_id}/calibration/run",
        json={
            "selected_csv_file": "calib.csv",
            "selected_mac": "AA",
            "gt_mode": "first_sample",
            "enable_ransac": True,
            "ransac_residual_threshold_db": 4,
            "ransac_iterations": 100,
            "distance_floor_m": 1,
        },
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()["calibration"]
    assert "scatter_points" in run_payload
    assert "parameters" in run_payload

    approve_response = client.post(
        f"/api/sessions/{session.session_id}/calibration/approve",
        json={"calibration": run_payload},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["active_calibration"]["parameter_source"] == "derived"

    fallback_response = client.post(
        f"/api/sessions/{session.session_id}/calibration/fallback",
        json={"selected_csv_file": "calib.csv", "selected_mac": "AA", "preset_name": "urban"},
    )
    assert fallback_response.status_code == 200
    assert fallback_response.json()["active_calibration"]["parameter_source"] == "fallback"
