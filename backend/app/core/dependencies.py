from __future__ import annotations

from app.modules.calibration.service import CalibrationService
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.enrichment.service import EnrichmentService
from app.modules.executions.service import ExecutionService
from app.modules.localization.service import LocalizationService
from app.modules.live_mission.service import LiveMissionService
from app.modules.overview.service import OverviewService
from app.modules.reid.service import ReIdService
from app.modules.session_navigation.service import SessionNavigationService

_dataset_service: DatasetDiscoveryService | None = None
_session_service: SessionNavigationService | None = None
_overview_service: OverviewService | None = None
_calibration_service: CalibrationService | None = None
_enrichment_service: EnrichmentService | None = None
_reid_service: ReIdService | None = None
_localization_service: LocalizationService | None = None
_execution_service: ExecutionService | None = None
_live_mission_service: LiveMissionService | None = None


def configure_services(
    dataset_service: DatasetDiscoveryService,
    session_service: SessionNavigationService,
    overview_service: OverviewService,
    calibration_service: CalibrationService,
    enrichment_service: EnrichmentService,
    reid_service: ReIdService,
    localization_service: LocalizationService,
    execution_service: ExecutionService,
    live_mission_service: LiveMissionService,
) -> None:
    global _dataset_service, _session_service, _overview_service, _calibration_service, _enrichment_service, _reid_service, _localization_service, _execution_service, _live_mission_service
    _dataset_service = dataset_service
    _session_service = session_service
    _overview_service = overview_service
    _calibration_service = calibration_service
    _enrichment_service = enrichment_service
    _reid_service = reid_service
    _localization_service = localization_service
    _execution_service = execution_service
    _live_mission_service = live_mission_service


def get_dataset_discovery_service() -> DatasetDiscoveryService:
    assert _dataset_service is not None
    return _dataset_service


def get_session_navigation_service() -> SessionNavigationService:
    assert _session_service is not None
    return _session_service


def get_overview_service() -> OverviewService:
    assert _overview_service is not None
    return _overview_service


def get_calibration_service() -> CalibrationService:
    assert _calibration_service is not None
    return _calibration_service


def get_enrichment_service() -> EnrichmentService:
    assert _enrichment_service is not None
    return _enrichment_service


def get_reid_service() -> ReIdService:
    assert _reid_service is not None
    return _reid_service


def get_localization_service() -> LocalizationService:
    assert _localization_service is not None
    return _localization_service


def get_execution_service() -> ExecutionService:
    assert _execution_service is not None
    return _execution_service


def get_live_mission_service() -> LiveMissionService:
    assert _live_mission_service is not None
    return _live_mission_service
