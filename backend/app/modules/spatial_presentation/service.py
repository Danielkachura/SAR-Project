from __future__ import annotations

from typing import Any

from app.models.canonical_models import LocalizationUncertaintyRegion, OverviewSpatialPayload, SpatialPoint


class SpatialPresentationService:
    """Phase 2 basic spatial payload builder for Overview.

    This service only shapes CSV GPS points and lightweight hover metadata.
    It performs no localization or advanced map analytics.
    """

    _LATITUDE_COLUMNS = ("latitude", "lat", "gps_lat", "gps_latitude")
    _LONGITUDE_COLUMNS = ("longitude", "lon", "lng", "gps_lon", "gps_longitude")

    def build_overview_spatial_payload(self, rows: list[dict[str, str]]) -> OverviewSpatialPayload:
        points: list[SpatialPoint] = []
        for row in rows:
            lat = self._parse_float_from_candidates(row, self._LATITUDE_COLUMNS)
            lon = self._parse_float_from_candidates(row, self._LONGITUDE_COLUMNS)
            if lat is None or lon is None:
                continue

            hover_metadata: dict[str, Any] = {}
            for key in ("device_id", "mac", "device_address", "cluster_id", "rssi", "timestamp"):
                if row.get(key) not in (None, ""):
                    hover_metadata[key] = row[key]

            points.append(SpatialPoint(latitude=lat, longitude=lon, hover_metadata=hover_metadata))

        return OverviewSpatialPayload(points=points)

    def build_localization_overlay_points(
        self,
        *,
        cluster_id: str,
        peak_latitude: float,
        peak_longitude: float,
        uncertainty_regions: list[LocalizationUncertaintyRegion],
    ) -> dict[str, Any]:
        return {
            "cluster_id": cluster_id,
            "peak": {"latitude": peak_latitude, "longitude": peak_longitude},
            "uncertainty_regions": [region.model_dump() for region in uncertainty_regions],
        }

    @staticmethod
    def _parse_float_from_candidates(row: dict[str, str], keys: tuple[str, ...]) -> float | None:
        for key in keys:
            raw = row.get(key)
            if raw in (None, ""):
                continue
            try:
                return float(raw)
            except ValueError:
                continue
        return None
