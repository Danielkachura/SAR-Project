from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.reid import router
from app.core.config import AppConfig
from app.core.dependencies import get_reid_service, get_session_navigation_service
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.reid.service import ReIdService
from app.modules.session_navigation.service import SessionNavigationService
from app.storage.data_paths import DataPathResolver
from app.storage.session_store import InMemorySessionStore


@pytest.fixture()
def client_and_services(data_root: Path):
    config = AppConfig(repo_root=data_root.parent, runtime_root=data_root.parent, data_dir=data_root)
    resolver = DataPathResolver(config=config)
    dataset = DatasetDiscoveryService(path_resolver=resolver)
    sessions = SessionNavigationService(dataset_service=dataset, session_store=InMemorySessionStore())
    reid = ReIdService(session_service=sessions, dataset_service=dataset)

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_reid_service] = lambda: reid
    app.dependency_overrides[get_session_navigation_service] = lambda: sessions
    return TestClient(app), sessions


def test_reid_api_run_success(client_and_services, data_root: Path) -> None:
    client, sessions = client_and_services
    folder = data_root / "api_reid"
    folder.mkdir()
    pd.DataFrame([
        {
            "timestamp_utc": "2025-12-15T09:58:14.000Z",
            "src_mac": "aa:bb:cc:dd:ee:01",
            "enr_seq_num": 10,
            "enr_ie_fingerprint": "1:aa",
            "enr_ie_vendor_ouis": "001122",
            "enr_bssid": "aa:bb:cc:dd:ee:ff",
        }
    ]).to_csv(folder / "scan_ENRICHED.csv", index=False)

    session = sessions.create_session("api_reid")
    sessions.activate_artifact(session.session_id, "api_reid:scan_ENRICHED.csv")

    resp = client.post(f"/api/sessions/{session.session_id}/reid/run", json={"parameters": {}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reid"]["output_reid_file"] == "scan_REID.csv"


def test_reid_api_without_active_enriched_returns_400(client_and_services, data_root: Path) -> None:
    client, sessions = client_and_services
    folder = data_root / "api_reid_missing"
    folder.mkdir()
    session = sessions.create_session("api_reid_missing")

    resp = client.post(f"/api/sessions/{session.session_id}/reid/run", json={"parameters": {}})
    assert resp.status_code == 400
