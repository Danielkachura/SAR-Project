from __future__ import annotations

import csv
import math
import random
from collections import Counter
from pathlib import Path

from app.core.errors import NotFoundError, ValidationError
from app.models.canonical_models import (
    CalibrationCandidateRecord,
    CalibrationCandidatesPayload,
    CalibrationDiagnostics,
    CalibrationFallbackPreset,
    CalibrationFallbackSelection,
    CalibrationFitLinePoint,
    CalibrationGtMode,
    CalibrationParameters,
    CalibrationPresetName,
    CalibrationRunConfig,
    CalibrationRunPayload,
    CalibrationScatterPoint,
    CalibrationSessionState,
    CalibrationWarning,
    CalibrationWarningCode,
    StageSuggestion,
)
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.session_navigation.service import SessionNavigationService


class CalibrationService:
    _MAC_COLUMNS = (
        "mac",
        "device_id",
        "device_address",
        "addr",
        "source_mac",
        "src_mac",
        "bssid",
    )
    _RSSI_COLUMNS = ("rssi", "rssi_dbm", "signal_dbm")
    _LAT_COLUMNS = ("latitude", "lat", "gps_lat", "gps_latitude")
    _LON_COLUMNS = ("longitude", "lon", "lng", "gps_lon", "gps_longitude")

    # TODO(spec): replace warning thresholds with finalized CAL-07/CAL-08 values.
    _FIT_WARNING_MIN_SAMPLES = 8
    _FIT_WARNING_MIN_INLIER_RATIO = 0.5
    _FIT_WARNING_MIN_R2 = 0.1
    _FIT_WARNING_MIN_DISTANCE_SPAN_M = 3.0

    def __init__(
        self,
        session_service: SessionNavigationService,
        dataset_service: DatasetDiscoveryService,
    ) -> None:
        self._session_service = session_service
        self._dataset_service = dataset_service

    def list_mac_candidates(self, session_id: str, selected_csv_file: str) -> CalibrationCandidatesPayload:
        rows = self._load_selected_csv(session_id=session_id, selected_csv_file=selected_csv_file)

        mac_counts: Counter[str] = Counter()
        for row in rows:
            mac = self._mac_value(row)
            if mac:
                mac_counts[mac] += 1

        candidates = [
            CalibrationCandidateRecord(mac=mac, sample_count=count)
            for mac, count in mac_counts.most_common()
        ]

        return CalibrationCandidatesPayload(selected_csv_file=selected_csv_file, candidates=candidates)

    def run_calibration(
        self,
        session_id: str,
        selected_csv_file: str,
        selected_mac: str,
        config: CalibrationRunConfig,
    ) -> CalibrationRunPayload:
        mac_rows = self._load_selected_mac_rows(
            session_id=session_id,
            selected_csv_file=selected_csv_file,
            selected_mac=selected_mac,
        )

        gt_lat, gt_lon = self._resolve_ground_truth(mac_rows=mac_rows, config=config)
        prepared_points = self._build_calibration_points(mac_rows=mac_rows, gt_lat=gt_lat, gt_lon=gt_lon, config=config)

        if len(prepared_points) < 2:
            raise ValidationError("At least 2 usable calibration samples are required for regression fitting.")

        inlier_indices = set(range(len(prepared_points)))
        if config.enable_ransac:
            inlier_indices = self._run_ransac(points=prepared_points, config=config)
            if len(inlier_indices) < 2:
                raise ValidationError("RANSAC left too few inliers for final regression.")

        inlier_points = [prepared_points[idx] for idx in sorted(inlier_indices)]
        intercept, slope = self._linear_regression(inlier_points)

        residuals = [point[1] - (intercept + slope * point[0]) for point in inlier_points]
        sigma = self._stddev(residuals)

        all_y = [point[1] for point in inlier_points]
        y_mean = sum(all_y) / len(all_y)
        ss_tot = sum((value - y_mean) ** 2 for value in all_y)
        ss_res = sum(value ** 2 for value in residuals)
        r2 = 0.0 if ss_tot <= 0 else max(-1.0, min(1.0, 1 - (ss_res / ss_tot)))

        distance_values = [point[2] for point in prepared_points]
        distance_min = min(distance_values)
        distance_max = max(distance_values)
        distance_span = max(0.0, distance_max - distance_min)

        diagnostics = CalibrationDiagnostics(
            sample_count=len(prepared_points),
            inlier_count=len(inlier_points),
            inlier_ratio=round(len(inlier_points) / len(prepared_points), 4),
            distance_min_m=round(distance_min, 4),
            distance_max_m=round(distance_max, 4),
            distance_span_m=round(distance_span, 4),
            r2=round(r2, 4),
        )

        warnings = self._build_fit_warnings(diagnostics=diagnostics)

        param_source = CalibrationParameters(
            rssi_at_1m=round(intercept, 4),
            path_loss_n=round((-slope / 10.0), 4),
            sigma=round(max(sigma, 0.001), 4),
        )

        scatter_points = [
            CalibrationScatterPoint(
                log10_distance=round(point[0], 6),
                rssi=round(point[1], 4),
                is_inlier=index in inlier_indices,
            )
            for index, point in enumerate(prepared_points)
        ]

        x_min = min(point[0] for point in prepared_points)
        x_max = max(point[0] for point in prepared_points)
        if math.isclose(x_min, x_max):
            fit_line = [
                CalibrationFitLinePoint(log10_distance=round(x_min, 6), predicted_rssi=round(intercept + slope * x_min, 4))
            ]
        else:
            fit_line = [
                CalibrationFitLinePoint(log10_distance=round(x_min, 6), predicted_rssi=round(intercept + slope * x_min, 4)),
                CalibrationFitLinePoint(log10_distance=round(x_max, 6), predicted_rssi=round(intercept + slope * x_max, 4)),
            ]

        return CalibrationRunPayload(
            selected_csv_file=selected_csv_file,
            selected_mac=selected_mac,
            gt_point_latitude=round(gt_lat, 7),
            gt_point_longitude=round(gt_lon, 7),
            config=config,
            scatter_points=scatter_points,
            fit_line=fit_line,
            parameters=param_source,
            diagnostics=diagnostics,
            warnings=warnings,
        )

    def approve_derived_calibration(self, session_id: str, result: CalibrationRunPayload) -> CalibrationSessionState:
        session_state = CalibrationSessionState(
            parameter_source="derived",
            approved=True,
            parameters=result.parameters,
            selection={"selected_csv_file": result.selected_csv_file, "selected_mac": result.selected_mac},
            gt_mode=result.config.gt_mode,
            gt_first_k=result.config.gt_first_k,
            enable_ransac=result.config.enable_ransac,
            ransac_residual_threshold_db=result.config.ransac_residual_threshold_db,
            ransac_iterations=result.config.ransac_iterations,
            distance_floor_m=result.config.distance_floor_m,
            diagnostics=result.diagnostics,
            warnings=result.warnings,
            fallback_name=None,
        )
        return self._session_service.set_active_calibration(session_id=session_id, calibration=session_state)


    def get_active_calibration(self, session_id: str) -> CalibrationSessionState | None:
        return self._session_service.require_session(session_id).active_calibration

    def list_fallback_presets(self) -> list[CalibrationFallbackPreset]:
        return [
            CalibrationFallbackPreset(
                name=CalibrationPresetName.URBAN,
                label="Urban",
                parameters=CalibrationParameters(rssi_at_1m=-41.0, path_loss_n=2.7, sigma=5.0),
            ),
            CalibrationFallbackPreset(
                name=CalibrationPresetName.OPEN_FIELD,
                label="Open Field",
                parameters=CalibrationParameters(rssi_at_1m=-38.0, path_loss_n=2.0, sigma=3.0),
            ),
            CalibrationFallbackPreset(
                name=CalibrationPresetName.MIXED_OUTDOOR,
                label="Mixed Outdoor",
                parameters=CalibrationParameters(rssi_at_1m=-40.0, path_loss_n=2.3, sigma=4.0),
            ),
        ]

    def select_fallback_preset(
        self,
        session_id: str,
        selected_csv_file: str,
        selected_mac: str,
        preset_name: str,
    ) -> CalibrationFallbackSelection:
        preset = next((item for item in self.list_fallback_presets() if item.name.value == preset_name), None)
        if preset is None:
            raise ValidationError(f"Unknown fallback preset: {preset_name}")

        fallback_selection = CalibrationFallbackSelection(
            selected_csv_file=selected_csv_file,
            selected_mac=selected_mac,
            preset=preset,
        )

        state = CalibrationSessionState(
            parameter_source="fallback",
            approved=True,
            parameters=preset.parameters,
            selection={"selected_csv_file": selected_csv_file, "selected_mac": selected_mac},
            gt_mode=CalibrationGtMode.MEAN_FIRST_K,
            fallback_name=preset.name,
        )
        self._session_service.set_active_calibration(session_id=session_id, calibration=state)
        self._session_service.set_current_stage(session_id=session_id, stage=StageSuggestion.CALIBRATION)
        return fallback_selection

    def _load_selected_csv(self, session_id: str, selected_csv_file: str) -> list[dict[str, str]]:
        session = self._session_service.require_session(session_id)
        inventory = self._dataset_service.resolve_inventory(session.scan_folder_id)
        available_csv_files = {item.file_name for item in inventory.raw_csv_files}
        if selected_csv_file not in available_csv_files:
            raise ValidationError(f"Selected CSV is not available in active folder: {selected_csv_file}")

        csv_path = self._dataset_service.resolve_csv_path(session.scan_folder_id, selected_csv_file)
        if not csv_path.exists() or not csv_path.is_file():
            raise NotFoundError(f"Selected CSV does not exist: {selected_csv_file}")

        return self._read_csv_rows(csv_path)

    def _load_selected_mac_rows(
        self,
        session_id: str,
        selected_csv_file: str,
        selected_mac: str,
    ) -> list[dict[str, str]]:
        rows = self._load_selected_csv(session_id=session_id, selected_csv_file=selected_csv_file)
        mac_rows = [row for row in rows if (self._mac_value(row) or "") == selected_mac]
        if not mac_rows:
            raise ValidationError(f"Selected MAC has no rows in selected CSV: {selected_mac}")
        return mac_rows

    def _resolve_ground_truth(self, mac_rows: list[dict[str, str]], config: CalibrationRunConfig) -> tuple[float, float]:
        if config.gt_mode == CalibrationGtMode.MANUAL_MAP_CLICK:
            if config.manual_gt_latitude is None or config.manual_gt_longitude is None:
                raise ValidationError("manual_map_click requires manual_gt_latitude and manual_gt_longitude.")
            return config.manual_gt_latitude, config.manual_gt_longitude

        usable = [row for row in mac_rows if self._lat_lon(row) is not None]
        if not usable:
            raise ValidationError("No usable GPS rows for selected MAC.")

        if config.gt_mode == CalibrationGtMode.FIRST_SAMPLE:
            lat_lon = self._lat_lon(usable[0])
            assert lat_lon is not None
            return lat_lon

        k = min(config.gt_first_k, len(usable))
        selected = usable[:k]
        lats = []
        lons = []
        for row in selected:
            lat_lon = self._lat_lon(row)
            assert lat_lon is not None
            lats.append(lat_lon[0])
            lons.append(lat_lon[1])
        return (sum(lats) / len(lats), sum(lons) / len(lons))

    def _build_calibration_points(
        self,
        mac_rows: list[dict[str, str]],
        gt_lat: float,
        gt_lon: float,
        config: CalibrationRunConfig,
    ) -> list[tuple[float, float, float]]:
        points: list[tuple[float, float, float]] = []
        for row in mac_rows:
            lat_lon = self._lat_lon(row)
            rssi = self._rssi_value(row)
            if lat_lon is None or rssi is None:
                continue

            distance = self._haversine_m(lat1=gt_lat, lon1=gt_lon, lat2=lat_lon[0], lon2=lat_lon[1])
            floored = max(distance, config.distance_floor_m)
            points.append((math.log10(floored), rssi, floored))

        if not points:
            raise ValidationError("No usable rows with GPS and RSSI for selected MAC.")
        return points

    def _run_ransac(self, points: list[tuple[float, float, float]], config: CalibrationRunConfig) -> set[int]:
        rng = random.Random(0)
        if len(points) < 2:
            return set()

        best_inliers: set[int] = set()
        threshold = config.ransac_residual_threshold_db

        for _ in range(config.ransac_iterations):
            idx_a, idx_b = rng.sample(range(len(points)), k=2)
            p1 = points[idx_a]
            p2 = points[idx_b]
            if math.isclose(p1[0], p2[0]):
                continue

            intercept, slope = self._linear_regression([(p1[0], p1[1], p1[2]), (p2[0], p2[1], p2[2])])
            current: set[int] = set()
            for index, point in enumerate(points):
                predicted = intercept + slope * point[0]
                residual = abs(point[1] - predicted)
                if residual <= threshold:
                    current.add(index)

            if len(current) > len(best_inliers):
                best_inliers = current

        if not best_inliers:
            return set(range(len(points)))
        return best_inliers

    @staticmethod
    def _linear_regression(points: list[tuple[float, float, float]]) -> tuple[float, float]:
        xs = [item[0] for item in points]
        ys = [item[1] for item in points]
        x_mean = sum(xs) / len(xs)
        y_mean = sum(ys) / len(ys)
        denominator = sum((value - x_mean) ** 2 for value in xs)
        if math.isclose(denominator, 0.0):
            raise ValidationError("Calibration regression failed: all distances are identical.")
        slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=False)) / denominator
        intercept = y_mean - slope * x_mean
        return intercept, slope

    @staticmethod
    def _stddev(values: list[float]) -> float:
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        return math.sqrt(max(variance, 0.0))

    def _build_fit_warnings(self, diagnostics: CalibrationDiagnostics) -> list[CalibrationWarning]:
        warnings: list[CalibrationWarning] = []

        if diagnostics.sample_count < self._FIT_WARNING_MIN_SAMPLES:
            warnings.append(
                CalibrationWarning(
                    code=CalibrationWarningCode.LOW_SAMPLE_COUNT,
                    message=(
                        f"Sample count is low ({diagnostics.sample_count}); fit may be unstable. "
                        "Approval is still allowed."
                    ),
                )
            )

        if diagnostics.inlier_ratio < self._FIT_WARNING_MIN_INLIER_RATIO:
            warnings.append(
                CalibrationWarning(
                    code=CalibrationWarningCode.LOW_INLIER_RATIO,
                    message=(
                        f"Inlier ratio is low ({diagnostics.inlier_ratio}); fit may be noisy. "
                        "Approval is still allowed."
                    ),
                )
            )

        if diagnostics.r2 < self._FIT_WARNING_MIN_R2:
            warnings.append(
                CalibrationWarning(
                    code=CalibrationWarningCode.LOW_R2,
                    message=(
                        f"R² is low ({diagnostics.r2}); fit quality may be weak. "
                        "Approval is still allowed."
                    ),
                )
            )

        if diagnostics.distance_span_m < self._FIT_WARNING_MIN_DISTANCE_SPAN_M:
            warnings.append(
                CalibrationWarning(
                    code=CalibrationWarningCode.LOW_DISTANCE_SPAN,
                    message=(
                        f"Distance span is narrow ({diagnostics.distance_span_m} m); fit may be poorly constrained. "
                        "Approval is still allowed."
                    ),
                )
            )

        return warnings

    def _read_csv_rows(self, csv_path: Path) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        with csv_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return []
            for row in reader:
                if row is None:
                    continue
                normalized = {str(k).strip(): ("" if v is None else str(v).strip()) for k, v in row.items()}
                rows.append(normalized)
        return rows

    @classmethod
    def _first_present(cls, row: dict[str, str], columns: tuple[str, ...]) -> str | None:
        for key in columns:
            value = row.get(key)
            if value not in (None, ""):
                return value
        return None

    @classmethod
    def _mac_value(cls, row: dict[str, str]) -> str | None:
        return cls._first_present(row, cls._MAC_COLUMNS)

    @classmethod
    def _rssi_value(cls, row: dict[str, str]) -> float | None:
        raw = cls._first_present(row, cls._RSSI_COLUMNS)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    @classmethod
    def _lat_lon(cls, row: dict[str, str]) -> tuple[float, float] | None:
        lat_raw = cls._first_present(row, cls._LAT_COLUMNS)
        lon_raw = cls._first_present(row, cls._LON_COLUMNS)
        if lat_raw is None or lon_raw is None:
            return None
        try:
            return float(lat_raw), float(lon_raw)
        except ValueError:
            return None

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        earth_radius = 6_371_000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)

        a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return earth_radius * c
