from __future__ import annotations

from app.modules.calibration.service import CalibrationService
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.overview.service import OverviewService
from app.modules.session_navigation.service import SessionNavigationService

_dataset_service: DatasetDiscoveryService | None = None
_session_service: SessionNavigationService | None = None
_overview_service: OverviewService | None = None
_calibration_service: CalibrationService | None = None


def configure_services(
    dataset_service: DatasetDiscoveryService,
    session_service: SessionNavigationService,
    overview_service: OverviewService,
    calibration_service: CalibrationService,
) -> None:
    global _dataset_service, _session_service, _overview_service, _calibration_service
    _dataset_service = dataset_service
    _session_service = session_service
    _overview_service = overview_service
    _calibration_service = calibration_service


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
