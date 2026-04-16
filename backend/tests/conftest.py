from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import AppConfig
from app.modules.artifact_management.service import ArtifactManagementService
from app.modules.calibration.service import CalibrationService
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.enrichment.service import EnrichmentService
from app.modules.overview.service import OverviewService
from app.modules.session_navigation.service import SessionNavigationService
from app.modules.spatial_presentation.service import SpatialPresentationService
from app.storage.data_paths import DataPathResolver
from app.storage.session_store import InMemorySessionStore


@pytest.fixture()
def data_root(tmp_path: Path) -> Path:
    data_dir = tmp_path / "DATA"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture()
def services(data_root: Path):
    config = AppConfig(repo_root=data_root.parent, runtime_root=data_root.parent, data_dir=data_root)
    resolver = DataPathResolver(config=config)
    dataset = DatasetDiscoveryService(path_resolver=resolver)
    sessions = SessionNavigationService(dataset_service=dataset, session_store=InMemorySessionStore())
    return dataset, sessions


@pytest.fixture()
def overview_services(services):
    dataset, sessions = services
    spatial = SpatialPresentationService()
    overview = OverviewService(session_service=sessions, dataset_service=dataset, spatial_service=spatial)
    return dataset, sessions, overview


@pytest.fixture()
def calibration_services(services):
    dataset, sessions = services
    calibration = CalibrationService(session_service=sessions, dataset_service=dataset)
    return dataset, sessions, calibration


@pytest.fixture()
def enrichment_services(services):
    dataset, sessions = services
    artifact = ArtifactManagementService()
    enrichment = EnrichmentService(session_service=sessions, dataset_service=dataset, artifact_service=artifact)
    return dataset, sessions, enrichment
