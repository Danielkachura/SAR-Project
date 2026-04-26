from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.config import AppConfig
from app.models.canonical_models import (
    CalibrationGtMode,
    CalibrationParameters,
    CalibrationSelection,
    CalibrationSessionState,
    LocalizationParameters,
    LocalizationPreFilters,
    LocalizationRunPayload,
)
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.localization.service import LocalizationService
from app.modules.session_navigation.service import SessionNavigationService
from app.modules.spatial_presentation.service import SpatialPresentationService
from app.storage.data_paths import DataPathResolver
from app.storage.session_store import InMemorySessionStore


def test_localization_service_supports_reid_rssi_dbm_fixture() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    data_root = repo_root / "Refrences" / "legacy" / "ground_station" / "data"
    folder_id = "scan - field test 1 - 19.1"
    reid_file = "scan_2026-01-19_11-20-58Z-test-circle2_reid.csv"
    reid_path = data_root / folder_id / reid_file

    df = pd.read_csv(reid_path)
    for required in ("rssi_dbm", "gps_lat", "gps_lon", "cluster_id"):
        assert required in df.columns

    config = AppConfig(repo_root=repo_root, runtime_root=repo_root, data_dir=data_root)
    resolver = DataPathResolver(config=config)
    dataset = DatasetDiscoveryService(path_resolver=resolver)
    sessions = SessionNavigationService(dataset_service=dataset, session_store=InMemorySessionStore())
    spatial = SpatialPresentationService()
    localization = LocalizationService(session_service=sessions, dataset_service=dataset, spatial_service=spatial)

    session = sessions.create_session(folder_id)
    sessions.activate_artifact(session.session_id, f"{folder_id}:{reid_file}")

    sessions.set_active_calibration(
        session.session_id,
        CalibrationSessionState(
            parameter_source="derived",
            approved=True,
            parameters=CalibrationParameters(rssi_at_1m=-42.0105, path_loss_n=2.2934, sigma=2.1636),
            selection=CalibrationSelection(
                selected_csv_file="scan_2026-01-19_11-14-13Z-calic_search1.csv",
                selected_mac="2c:59:8a:58:95:c1",
            ),
            gt_mode=CalibrationGtMode.FIRST_SAMPLE,
        ),
    )

    result = localization.run_localization(
        session_id=session.session_id,
        selected_reid_artifact_id=f"{folder_id}:{reid_file}",
        parameters=LocalizationParameters(
            grid_resolution_m=5,
            confidence_cutoff=0.2,
            enable_ransac=False,
            uncertainty_target_mass_q=0.68,
            min_samples_per_cluster=3,
        ),
        pre_filters=LocalizationPreFilters(),
    )

    assert isinstance(result, LocalizationRunPayload)
    succeeded = [item for item in result.cluster_results if item.status == "succeeded"]
    failed = [item for item in result.cluster_results if item.status == "failed"]

    assert len(succeeded) >= 1
    assert len(failed) >= 1

    for item in succeeded:
        assert item.primary_peak_latitude is not None
        assert item.primary_peak_longitude is not None
        assert 1 <= len(item.uncertainty_regions) <= 3
