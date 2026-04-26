from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from app.core.errors import ValidationError
from app.models.canonical_models import (
    CalibrationParameters,
    LocalizationClusterResult,
    LocalizationParameters,
    LocalizationPreFilters,
    LocalizationRunPayload,
    LocalizationUncertaintyRegion,
)
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.session_navigation.service import SessionNavigationService
from app.modules.spatial_presentation.service import SpatialPresentationService


class LocalizationService:
    def __init__(
        self,
        session_service: SessionNavigationService,
        dataset_service: DatasetDiscoveryService,
        spatial_service: SpatialPresentationService,
    ) -> None:
        self._session_service = session_service
        self._dataset_service = dataset_service
        self._spatial_service = spatial_service

    def run_localization(
        self,
        session_id: str,
        selected_reid_artifact_id: str | None,
        parameters: LocalizationParameters,
        pre_filters: LocalizationPreFilters,
    ) -> LocalizationRunPayload:
        session = self._session_service.require_session(session_id)
        artifact_id = selected_reid_artifact_id or session.active_reid_artifact_id
        if artifact_id is None:
            raise ValidationError("Localization requires an active REID artifact.")

        calibration_params = self._resolve_calibration(session_id)
        inventory = self._dataset_service.resolve_inventory(session.scan_folder_id)
        artifact = next((a for a in inventory.reid_artifacts if a.artifact_id == artifact_id), None)
        if artifact is None:
            raise ValidationError("Selected artifact is not a compatible REID artifact.")

        input_path = Path(artifact.path)
        if not input_path.exists():
            raise ValidationError(f"Active REID artifact not found on disk: {artifact.file_name}")

        df = pd.read_csv(input_path)
        if df.empty:
            raise ValidationError("REID artifact is empty; cannot run localization.")

        if "cluster_id" not in df.columns:
            raise ValidationError("Localization input must include cluster_id.")

        working = self._apply_prefilters(df, pre_filters)
        if working.empty:
            raise ValidationError("Pre-localization filters removed all usable rows.")

        cluster_results: list[LocalizationClusterResult] = []
        warnings: list[str] = []

        for cluster_id, group in working.groupby("cluster_id"):
            result = self._localize_cluster(
                cluster_id=str(cluster_id),
                cluster_rows=group,
                parameters=parameters,
                calibration=calibration_params,
            )
            cluster_results.append(result)
            warnings.extend(result.warnings)

        if not any(item.status == "succeeded" for item in cluster_results):
            raise ValidationError("Localization failed for all clusters.")

        return LocalizationRunPayload(
            input_reid_file=artifact.file_name,
            protocol=session.mode,
            parameters=self._effective_parameters(parameters, calibration_params),
            pre_filters=pre_filters,
            cluster_results=cluster_results,
            warnings=warnings,
        )

    def _apply_prefilters(self, df: pd.DataFrame, pre_filters: LocalizationPreFilters) -> pd.DataFrame:
        filtered = df.copy()
        if pre_filters.cluster_ids:
            filtered = filtered[filtered["cluster_id"].astype(str).isin(pre_filters.cluster_ids)]

        if pre_filters.mac_addresses:
            mac_col = self._first_existing_column(filtered, ["src_mac", "mac", "device_id", "device_address"])
            if mac_col is None:
                return filtered.iloc[0:0]
            mac_target = {item.lower() for item in pre_filters.mac_addresses}
            filtered = filtered[filtered[mac_col].astype(str).str.lower().isin(mac_target)]

        return filtered

    def _localize_cluster(
        self,
        cluster_id: str,
        cluster_rows: pd.DataFrame,
        parameters: LocalizationParameters,
        calibration: CalibrationParameters,
    ) -> LocalizationClusterResult:
        lat_col = self._first_existing_column(cluster_rows, ["latitude", "lat", "gps_lat", "gps_latitude"])
        lon_col = self._first_existing_column(cluster_rows, ["longitude", "lon", "lng", "gps_lon", "gps_longitude"])
        rssi_col = self._first_existing_column(cluster_rows, ["rssi", "signal_dbm", "signal_strength"])

        warnings: list[str] = []
        if not lat_col or not lon_col or not rssi_col:
            return LocalizationClusterResult(
                cluster_id=cluster_id,
                sample_count=int(len(cluster_rows)),
                status="failed",
                warnings=["Cluster missing required GPS/RSSI fields."],
            )

        usable = cluster_rows[[lat_col, lon_col, rssi_col]].dropna()
        if len(usable) < parameters.min_samples_per_cluster:
            return LocalizationClusterResult(
                cluster_id=cluster_id,
                sample_count=int(len(usable)),
                status="failed",
                warnings=["Cluster has fewer than minimum required samples."],
            )

        path_loss = parameters.path_loss_n if parameters.path_loss_n is not None else calibration.path_loss_n
        rssi_at_1m = parameters.rssi_at_1m if parameters.rssi_at_1m is not None else calibration.rssi_at_1m
        sigma = parameters.sigma if parameters.sigma is not None else calibration.sigma

        estimates: list[tuple[float, float, float]] = []
        for _, row in usable.iterrows():
            measured = float(row[rssi_col])
            distance = 10 ** ((rssi_at_1m - measured) / (10 * max(path_loss, 0.1)))
            lat = float(row[lat_col])
            lon = float(row[lon_col])
            score = math.exp(-((measured - rssi_at_1m) ** 2) / (2 * max(sigma, 0.1) ** 2))
            estimates.append((lat + distance / 111_111.0, lon + distance / 111_111.0, score))

        total_score = sum(item[2] for item in estimates)
        peak_lat = sum(item[0] * item[2] for item in estimates) / total_score
        peak_lon = sum(item[1] * item[2] for item in estimates) / total_score

        uncertainty_regions = [
            LocalizationUncertaintyRegion(
                latitude=peak_lat,
                longitude=peak_lon,
                radius_m=max(2.0, parameters.grid_resolution_m * 1.5),
                confidence_mass_q=parameters.uncertainty_target_mass_q,
            )
        ]

        if len(estimates) >= 8:
            uncertainty_regions.append(
                LocalizationUncertaintyRegion(
                    latitude=peak_lat + 0.00003,
                    longitude=peak_lon - 0.00003,
                    radius_m=max(3.0, parameters.grid_resolution_m * 2.0),
                    confidence_mass_q=parameters.uncertainty_target_mass_q,
                )
            )

        self._spatial_service.build_localization_overlay_points(
            cluster_id=cluster_id,
            peak_latitude=peak_lat,
            peak_longitude=peak_lon,
            uncertainty_regions=uncertainty_regions,
        )

        return LocalizationClusterResult(
            cluster_id=cluster_id,
            sample_count=int(len(usable)),
            status="succeeded",
            primary_peak_latitude=peak_lat,
            primary_peak_longitude=peak_lon,
            peak_score=total_score / len(estimates),
            uncertainty_regions=uncertainty_regions[:3],
            warnings=warnings,
        )

    def _resolve_calibration(self, session_id: str) -> CalibrationParameters:
        session = self._session_service.require_session(session_id)
        if session.active_calibration is None:
            raise ValidationError("Localization requires approved calibration or fallback parameters.")
        return session.active_calibration.parameters

    @staticmethod
    def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        return None

    @staticmethod
    def _effective_parameters(parameters: LocalizationParameters, calibration: CalibrationParameters) -> LocalizationParameters:
        return parameters.model_copy(
            update={
                "path_loss_n": parameters.path_loss_n if parameters.path_loss_n is not None else calibration.path_loss_n,
                "rssi_at_1m": parameters.rssi_at_1m if parameters.rssi_at_1m is not None else calibration.rssi_at_1m,
                "sigma": parameters.sigma if parameters.sigma is not None else calibration.sigma,
            }
        )
