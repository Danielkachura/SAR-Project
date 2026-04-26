from __future__ import annotations

from fastapi import FastAPI

from app.api import api_router
from app.core.config import build_config
from app.core.dependencies import configure_services
from app.modules.calibration.service import CalibrationService
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.enrichment.service import EnrichmentService
from app.modules.executions.service import ExecutionService
from app.modules.localization.service import LocalizationService
from app.modules.overview.service import OverviewService
from app.modules.reid.service import ReIdService
from app.modules.session_navigation.service import SessionNavigationService
from app.modules.spatial_presentation.service import SpatialPresentationService
from app.storage.data_paths import DataPathResolver
from app.storage.session_store import InMemorySessionStore

config = build_config()
path_resolver = DataPathResolver(config=config)
session_store = InMemorySessionStore()
dataset_service = DatasetDiscoveryService(path_resolver=path_resolver)
session_navigation_service = SessionNavigationService(
    dataset_service=dataset_service,
    session_store=session_store,
)
spatial_presentation_service = SpatialPresentationService()
overview_service = OverviewService(
    session_service=session_navigation_service,
    dataset_service=dataset_service,
    spatial_service=spatial_presentation_service,
)
calibration_service = CalibrationService(
    session_service=session_navigation_service,
    dataset_service=dataset_service,
)
enrichment_service = EnrichmentService(
    session_service=session_navigation_service,
    dataset_service=dataset_service,
)
reid_service = ReIdService(
    session_service=session_navigation_service,
    dataset_service=dataset_service,
)
localization_service = LocalizationService(
    session_service=session_navigation_service,
    dataset_service=dataset_service,
    spatial_service=spatial_presentation_service,
)
execution_service = ExecutionService()

configure_services(
    dataset_service=dataset_service,
    session_service=session_navigation_service,
    overview_service=overview_service,
    calibration_service=calibration_service,
    enrichment_service=enrichment_service,
    reid_service=reid_service,
    localization_service=localization_service,
    execution_service=execution_service,
)

app = FastAPI(title="SAR Ground Station Refactor")
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
