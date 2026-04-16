from __future__ import annotations

import csv
from collections import Counter, defaultdict
from app.core.errors import NotFoundError, ValidationError
from app.models.canonical_models import (
    DeviceSummary,
    OverviewCharts,
    OverviewContext,
    OverviewDeviceAnalysis,
    OverviewPayload,
    OverviewPreview,
    OverviewSummaryStats,
)
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.session_navigation.service import SessionNavigationService
from app.modules.spatial_presentation.service import SpatialPresentationService


class OverviewService:
    _DEVICE_COLUMNS = (
        "device_id",
        "mac",
        "device_address",
        "addr",
        "source_mac",
        "src_mac",
        "bssid",
    )
    _RSSI_COLUMNS = ("rssi", "rssi_dbm", "signal_dbm")
    _VENDOR_COLUMNS = ("vendor", "company", "manufacturer")
    _TYPE_COLUMNS = ("frame_type", "event_type", "type")

    def __init__(
        self,
        session_service: SessionNavigationService,
        dataset_service: DatasetDiscoveryService,
        spatial_service: SpatialPresentationService,
    ) -> None:
        self._session_service = session_service
        self._dataset_service = dataset_service
        self._spatial_service = spatial_service

    def build_overview(
        self,
        session_id: str,
        selected_csv_file: str | None,
        preview_limit: int,
    ) -> OverviewPayload:
        session = self._session_service.require_session(session_id)
        inventory = self._dataset_service.resolve_inventory(session.scan_folder_id)
        available_csv_files = [item.file_name for item in inventory.raw_csv_files]

        effective_csv = selected_csv_file or session.selected_overview_csv_file

        if effective_csv is None:
            return OverviewPayload(
                context=OverviewContext(
                    session_id=session_id,
                    mode=session.mode,
                    selected_csv_file=None,
                    available_csv_files=available_csv_files,
                    warnings=["Select a CSV file to generate Overview outputs."],
                )
            )

        if effective_csv not in available_csv_files:
            raise ValidationError(f"Selected CSV is not available in active folder: {effective_csv}")

        csv_path = self._dataset_service.resolve_csv_path(session.scan_folder_id, effective_csv)
        if not csv_path.exists() or not csv_path.is_file():
            raise NotFoundError(f"Selected CSV does not exist: {effective_csv}")

        rows, columns, parse_warnings = self._read_csv_rows(csv_path)
        self._session_service.set_selected_overview_csv(session_id, effective_csv)

        return OverviewPayload(
            context=OverviewContext(
                session_id=session_id,
                mode=session.mode,
                selected_csv_file=effective_csv,
                available_csv_files=available_csv_files,
                warnings=parse_warnings,
            ),
            summary_stats=self._build_summary(rows),
            charts=self._build_charts(rows),
            preview=self._build_preview(rows, columns, preview_limit),
            spatial=self._spatial_service.build_overview_spatial_payload(rows),
            device_analysis=self._build_device_analysis(rows),
        )

    def _read_csv_rows(self, csv_path: Path) -> tuple[list[dict[str, str]], list[str], list[str]]:
        rows: list[dict[str, str]] = []
        parse_warnings: list[str] = []

        with csv_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return [], [], ["CSV has no header row; returning empty overview payload."]
            columns = [name.strip() for name in reader.fieldnames]

            for row in reader:
                if row is None:
                    continue
                normalized = {str(k).strip(): ("" if v is None else str(v).strip()) for k, v in row.items()}
                rows.append(normalized)

        if rows and self._first_present(rows[0], self._DEVICE_COLUMNS) is None:
            parse_warnings.append("No recognized device identifier column found; device summary may be limited.")

        # TODO(spec): integrate MOD-003 protocol/schema normalization once available.
        return rows, columns, parse_warnings

    def _build_summary(self, rows: list[dict[str, str]]) -> OverviewSummaryStats:
        devices = {device for device in (self._device_id(row) for row in rows) if device is not None}
        rssis = [value for value in (self._rssi(row) for row in rows) if value is not None]

        vendor_counter: Counter[str] = Counter()
        for row in rows:
            vendor = self._first_present(row, self._VENDOR_COLUMNS)
            if vendor:
                vendor_counter[vendor] += 1

        avg_rssi = round(sum(rssis) / len(rssis), 2) if rssis else None

        return OverviewSummaryStats(
            total_rows=len(rows),
            unique_devices=len(devices),
            average_rssi=avg_rssi,
            vendor_company_counts=dict(vendor_counter),
        )

    def _build_charts(self, rows: list[dict[str, str]]) -> OverviewCharts:
        type_counter: Counter[str] = Counter()
        vendor_counter: Counter[str] = Counter()
        rssi_bins: Counter[str] = Counter()

        for row in rows:
            type_value = self._first_present(row, self._TYPE_COLUMNS)
            if type_value:
                type_counter[type_value] += 1

            vendor = self._first_present(row, self._VENDOR_COLUMNS)
            if vendor:
                vendor_counter[vendor] += 1

            rssi = self._rssi(row)
            if rssi is not None:
                bin_start = int(rssi // 10) * 10
                bin_key = f"{bin_start}..{bin_start + 9}"
                rssi_bins[bin_key] += 1

        return OverviewCharts(
            frame_or_event_type_distribution=[{"key": key, "count": count} for key, count in type_counter.most_common()],
            top_vendors=[{"key": key, "count": count} for key, count in vendor_counter.most_common(10)],
            rssi_histogram=[{"key": key, "count": count} for key, count in sorted(rssi_bins.items())],
        )

    def _build_preview(self, rows: list[dict[str, str]], columns: list[str], preview_limit: int) -> OverviewPreview:
        capped = rows[:preview_limit]
        return OverviewPreview(columns=columns, rows=capped, total_rows=len(rows), truncated=len(rows) > preview_limit)

    def _build_device_analysis(self, rows: list[dict[str, str]]) -> OverviewDeviceAnalysis:
        grouped_rssi: dict[str, list[float]] = defaultdict(list)
        grouped_count: Counter[str] = Counter()
        grouped_vendor: dict[str, str] = {}

        for row in rows:
            device_id = self._device_id(row)
            if not device_id:
                continue

            grouped_count[device_id] += 1
            rssi = self._rssi(row)
            if rssi is not None:
                grouped_rssi[device_id].append(rssi)

            if device_id not in grouped_vendor:
                vendor = self._first_present(row, self._VENDOR_COLUMNS)
                if vendor:
                    grouped_vendor[device_id] = vendor

        summaries: list[DeviceSummary] = []
        for device_id, count in grouped_count.most_common():
            values = grouped_rssi.get(device_id, [])
            average = round(sum(values) / len(values), 2) if values else None
            summaries.append(
                DeviceSummary(
                    device_id=device_id,
                    packet_count=count,
                    average_rssi=average,
                    vendor_or_company=grouped_vendor.get(device_id),
                )
            )

        return OverviewDeviceAnalysis(devices=summaries)

    @classmethod
    def _device_id(cls, row: dict[str, str]) -> str | None:
        return cls._first_present(row, cls._DEVICE_COLUMNS)

    @classmethod
    def _rssi(cls, row: dict[str, str]) -> float | None:
        raw = cls._first_present(row, cls._RSSI_COLUMNS)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _first_present(row: dict[str, str], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return value
        return None
