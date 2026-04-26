from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.executions import router as executions_router
from app.api.localization import router as localization_router
from app.core.config import AppConfig
from app.core.dependencies import get_execution_service, get_localization_service
from app.models.canonical_models import CalibrationGtMode, CalibrationParameters, CalibrationSelection, CalibrationSessionState
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.executions.service import ExecutionService
from app.modules.localization.service import LocalizationService
from app.modules.session_navigation.service import SessionNavigationService
from app.modules.spatial_presentation.service import SpatialPresentationService
from app.storage.data_paths import DataPathResolver
from app.storage.session_store import InMemorySessionStore


@pytest.fixture()
def client_and_services(data_root: Path):
    config = AppConfig(repo_root=data_root.parent, runtime_root=data_root.parent, data_dir=data_root)
    resolver = DataPathResolver(config=config)
    dataset = DatasetDiscoveryService(path_resolver=resolver)
    sessions = SessionNavigationService(dataset_service=dataset, session_store=InMemorySessionStore())
    spatial = SpatialPresentationService()
    localization = LocalizationService(session_service=sessions, dataset_service=dataset, spatial_service=spatial)
    executions = ExecutionService()

    app = FastAPI()
    app.include_router(localization_router, prefix="/api")
    app.include_router(executions_router, prefix="/api")
    app.dependency_overrides[get_localization_service] = lambda: localization
    app.dependency_overrides[get_execution_service] = lambda: executions
    return TestClient(app), sessions


def test_localization_execution_success(client_and_services, data_root: Path) -> None:
    client, sessions = client_and_services
    folder = data_root / "api_localization"
    folder.mkdir()
    pd.DataFrame([
        {"cluster_id": "c1", "lat": 32.1, "lon": 34.8, "rssi": -55, "src_mac": "aa:bb:cc:dd:ee:01"},
        {"cluster_id": "c1", "lat": 32.1001, "lon": 34.8001, "rssi": -56, "src_mac": "aa:bb:cc:dd:ee:01"},
        {"cluster_id": "c1", "lat": 32.0999, "lon": 34.8002, "rssi": -57, "src_mac": "aa:bb:cc:dd:ee:01"},
    ]).to_csv(folder / "scan_REID.csv", index=False)

    session = sessions.create_session("api_localization")
    sessions.activate_artifact(session.session_id, "api_localization:scan_REID.csv")
    sessions.set_active_calibration(
        session.session_id,
        CalibrationSessionState(
            parameter_source="fallback",
            approved=True,
            parameters=CalibrationParameters(rssi_at_1m=-40, path_loss_n=2.2, sigma=4.0),
            selection=CalibrationSelection(selected_csv_file="scan.csv", selected_mac="aa:bb:cc:dd:ee:01"),
            gt_mode=CalibrationGtMode.FIRST_SAMPLE,
            fallback_name="urban",
        ),
    )

    run_resp = client.post(
        f"/api/sessions/{session.session_id}/localization/run",
        json={"parameters": {}, "pre_filters": {}},
    )
    assert run_resp.status_code == 200, run_resp.text
    execution_id = run_resp.json()["execution"]["execution_id"]

    for _ in range(20):
        status_resp = client.get(f"/api/executions/{execution_id}")
        assert status_resp.status_code == 200
        body = status_resp.json()
        if body["execution"]["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)

    assert body["execution"]["status"] == "succeeded"
    assert body["localization"]["input_reid_file"] == "scan_REID.csv"


def test_localization_requires_reid(client_and_services, data_root: Path) -> None:
    client, sessions = client_and_services
    folder = data_root / "api_localization_missing"
    folder.mkdir()
    session = sessions.create_session("api_localization_missing")

    run_resp = client.post(
        f"/api/sessions/{session.session_id}/localization/run",
        json={"parameters": {}, "pre_filters": {}},
    )
    assert run_resp.status_code == 200
    execution_id = run_resp.json()["execution"]["execution_id"]

    for _ in range(20):
        status_resp = client.get(f"/api/executions/{execution_id}")
        body = status_resp.json()
        if body["execution"]["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)

    assert body["execution"]["status"] == "failed"
    assert "traceback" in body["execution"]["result_metadata"]
    assert "Localization requires an active REID artifact." in body["execution"]["result_metadata"]["traceback"]
