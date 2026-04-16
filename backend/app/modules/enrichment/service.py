from __future__ import annotations

import csv
import hashlib
import math
from bisect import bisect_left, bisect_right
from pathlib import Path
from statistics import mean
from typing import Any

from scapy.all import Dot11, Dot11Elt, PcapReader  # type: ignore

from app.core.errors import NotFoundError, ValidationError
from app.models.canonical_models import (
    EnrichmentQualityStats,
    EnrichmentRunConfig,
    EnrichmentRunPayload,
    MatchMethod,
)
from app.modules.artifact_management.service import ArtifactManagementService
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.session_navigation.service import SessionNavigationService


class EnrichmentService:
    _TIMESTAMP_COLUMNS = ("timestamp_ms", "timestamp", "ts_ms", "time_ms", "time")
    _WIFI_ID_COLUMNS = ("mac", "source_mac", "src_mac", "device_id", "addr")
    _WIFI_BSSID_COLUMNS = ("bssid",)
    _WIFI_CHANNEL_COLUMNS = ("channel",)
    _BLE_ADDR_COLUMNS = ("device_address", "address", "addr", "mac", "device_id")
    _BLE_EVENT_COLUMNS = ("event_type", "type")

    _ENRICHMENT_COLUMNS = [
        "pcap_timestamp_ms",
        "pcap_src_mac",
        "pcap_dst_mac",
        "pcap_bssid",
        "pcap_channel",
        "pcap_frequency_mhz",
        "pcap_sequence_number",
        "pcap_fragment_number",
        "pcap_frame_length",
        "pcap_ie_ids",
        "pcap_ie_fingerprint",
        "pcap_ie_vendor_ouis",
        "pcap_src_vendor",
        "pcap_dst_vendor",
        "pcap_bssid_vendor",
        "pcap_ble_adv_address",
        "pcap_ble_event_type",
        "pcap_ble_manufacturer_digest",
        "pcap_ble_service_uuids",
        "pcap_ble_service_uuid_digest",
        "pcap_ble_local_name",
        "pcap_ble_local_name_digest",
        "pcap_ble_tx_power",
        "pcap_ble_flags",
        "pcap_ble_vendor",
        "match_found",
        "match_delta_ms",
        "match_score",
        "match_method",
    ]

    def __init__(
        self,
        session_service: SessionNavigationService,
        dataset_service: DatasetDiscoveryService,
        artifact_service: ArtifactManagementService,
    ) -> None:
        self._session_service = session_service
        self._dataset_service = dataset_service
        self._artifact_service = artifact_service

    def run_enrichment(self, session_id: str, selected_csv_file: str, config: EnrichmentRunConfig) -> EnrichmentRunPayload:
        session = self._session_service.require_session(session_id)
        inventory = self._dataset_service.resolve_inventory(session.scan_folder_id)

        raw_artifact = next((a for a in inventory.raw_csv_files if a.file_name == selected_csv_file), None)
        if raw_artifact is None:
            raise ValidationError(f"Selected CSV is not available in active folder: {selected_csv_file}")

        csv_base = raw_artifact.base_name
        pcap_artifact = next((a for a in inventory.pcap_files if a.base_name == csv_base), None)
        if pcap_artifact is None:
            raise ValidationError(f"Matching PCAP with identical basename is required for enrichment: {csv_base}")

        csv_path = Path(raw_artifact.path)
        pcap_path = Path(pcap_artifact.path)
        if not csv_path.exists() or not csv_path.is_file():
            raise NotFoundError(f"Selected CSV does not exist: {selected_csv_file}")
        if not pcap_path.exists() or not pcap_path.is_file():
            raise NotFoundError(f"Matching PCAP does not exist: {pcap_artifact.file_name}")

        source_rows, source_columns = self._read_csv(csv_path)
        mode = session.mode.value
        if mode not in {"wifi", "ble"}:
            raise ValidationError("Enrichment requires protocol mode wifi or ble.")

        frame_table = self._parse_pcap_to_features(pcap_path=pcap_path, mode=mode)
        normalized_frames = [self._normalize_frame(frame) for frame in frame_table]
        timestamps = [frame["timestamp_ms"] for frame in normalized_frames]

        enriched_rows: list[dict[str, str]] = []
        matched = 0
        deltas: list[float] = []
        scores: list[float] = []
        seq_covered = 0
        fingerprint_covered = 0
        vendor_covered = 0

        for row in source_rows:
            candidate_indices = self._candidate_indices_by_time(
                timestamps=timestamps,
                row_timestamp_ms=self._row_timestamp_ms(row),
                window_ms=config.match_time_window_ms,
            )
            match = self._best_match(
                row=row,
                mode=mode,
                frames=normalized_frames,
                candidate_indices=candidate_indices,
                config=config,
            )
            enriched_row = dict(row)
            for key in self._ENRICHMENT_COLUMNS:
                enriched_row.setdefault(key, "")

            if match is None:
                enriched_row["match_found"] = "false"
                enriched_row["match_delta_ms"] = ""
                enriched_row["match_score"] = ""
                enriched_row["match_method"] = MatchMethod.NO_MATCH.value
            else:
                matched += 1
                frame = match["frame"]
                delta_ms = float(match["delta_ms"])
                score = float(match["score"])
                deltas.append(delta_ms)
                scores.append(score)

                enriched_row.update(self._frame_to_enrichment_columns(frame))
                enriched_row["match_found"] = "true"
                enriched_row["match_delta_ms"] = f"{delta_ms:.3f}"
                enriched_row["match_score"] = f"{score:.4f}"
                enriched_row["match_method"] = str(match["method"])

                if enriched_row.get("pcap_sequence_number"):
                    seq_covered += 1
                if enriched_row.get("pcap_ie_fingerprint") or enriched_row.get("pcap_ble_manufacturer_digest"):
                    fingerprint_covered += 1
                if (
                    enriched_row.get("pcap_src_vendor")
                    or enriched_row.get("pcap_dst_vendor")
                    or enriched_row.get("pcap_bssid_vendor")
                    or enriched_row.get("pcap_ble_vendor")
                ):
                    vendor_covered += 1

            enriched_rows.append(enriched_row)

        output_file_name = self._artifact_service.build_official_enriched_filename(selected_csv_file)
        output_path = csv_path.parent / output_file_name
        output_columns = list(source_columns)
        for col in self._ENRICHMENT_COLUMNS:
            if col not in output_columns:
                output_columns.append(col)

        self._write_csv(output_path=output_path, columns=output_columns, rows=enriched_rows)

        artifact_id = f"{session.scan_folder_id}:{output_file_name}"
        updated_session = self._session_service.activate_artifact(session_id=session_id, artifact_id=artifact_id)

        total_rows = len(enriched_rows)
        stats = self._build_quality_stats(
            total_rows=total_rows,
            matched_rows=matched,
            seq_covered_rows=seq_covered,
            fingerprint_covered_rows=fingerprint_covered,
            vendor_covered_rows=vendor_covered,
            deltas=deltas,
            scores=scores,
        )

        return EnrichmentRunPayload(
            selected_csv_file=selected_csv_file,
            output_artifact_id=artifact_id,
            output_file_name=output_file_name,
            output_path=str(output_path),
            total_rows=total_rows,
            matched_rows=matched,
            quality_stats=stats,
            active_enriched_artifact_id=updated_session.active_enriched_artifact_id,
        )

    def _parse_pcap_to_features(self, pcap_path: Path, mode: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with PcapReader(str(pcap_path)) as reader:
            for packet in reader:
                timestamp_ms = float(packet.time) * 1000.0
                base: dict[str, Any] = {"timestamp_ms": timestamp_ms, "frame_length": int(len(packet))}
                if mode == "wifi":
                    base.update(self._extract_wifi(packet))
                else:
                    base.update(self._extract_ble(packet))
                rows.append(base)

        rows.sort(key=lambda item: float(item.get("timestamp_ms", 0.0)))
        return rows

    def _extract_wifi(self, packet: Any) -> dict[str, Any]:
        if not packet.haslayer(Dot11):
            return {}

        dot11 = packet[Dot11]
        src = self._normalize_mac(dot11.addr2)
        dst = self._normalize_mac(dot11.addr1)
        bssid = self._normalize_mac(dot11.addr3)

        ie_ids: list[str] = []
        ie_vendor_ouis: set[str] = set()

        current = packet.getlayer(Dot11Elt)
        while current is not None:
            ie_ids.append(str(getattr(current, "ID", "")))
            if getattr(current, "ID", None) == 221:
                info = bytes(getattr(current, "info", b""))
                if len(info) >= 3:
                    ie_vendor_ouis.add(info[:3].hex().upper())
            current = getattr(current, "payload", None)
            if current is not None and current.__class__.__name__ == "NoPayload":
                current = None
            elif current is not None and not isinstance(current, Dot11Elt):
                current = current.getlayer(Dot11Elt)

        channel = str(getattr(packet, "Channel", "") or "")
        frequency = str(getattr(packet, "ChannelFrequency", "") or "")

        seq_control = getattr(dot11, "SC", None)
        sequence_number = ""
        fragment_number = ""
        if isinstance(seq_control, int):
            sequence_number = str(seq_control >> 4)
            fragment_number = str(seq_control & 0xF)

        fingerprint_input = "|".join(ie_ids)
        ie_fingerprint = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:16] if ie_ids else ""

        return {
            "src_mac": src,
            "dst_mac": dst,
            "bssid": bssid,
            "channel": channel,
            "frequency_mhz": frequency,
            "sequence_number": sequence_number,
            "fragment_number": fragment_number,
            "ie_ids": ";".join(ie_ids),
            "ie_fingerprint": ie_fingerprint,
            "ie_vendor_ouis": ";".join(sorted(ie_vendor_ouis)),
            "src_vendor": self._oui_vendor(src),
            "dst_vendor": self._oui_vendor(dst),
            "bssid_vendor": self._oui_vendor(bssid),
            "identity_key": src or bssid,
            "context_key": f"{bssid}|{channel}",
        }

    def _extract_ble(self, packet: Any) -> dict[str, Any]:
        raw_hex = bytes(packet).hex()
        sha = hashlib.sha256(raw_hex.encode("utf-8")).hexdigest()

        adv_address = ""
        if hasattr(packet, "AdvA"):
            adv_address = self._normalize_mac(getattr(packet, "AdvA"))

        event_type = str(getattr(packet, "PDU_type", ""))
        flags = ""

        payload = bytes(packet)
        for i in range(0, max(0, len(payload) - 2)):
            if payload[i] == 0x02 and i + 2 < len(payload) and payload[i + 1] == 0x01:
                flags = f"0x{payload[i + 2]:02x}"

        return {
            "ble_adv_address": adv_address,
            "ble_event_type": event_type,
            "ble_manufacturer_digest": sha[:16],
            "ble_service_uuids": "",
            "ble_service_uuid_digest": "",
            "ble_local_name": "",
            "ble_local_name_digest": "",
            "ble_tx_power": "",
            "ble_flags": flags,
            "ble_vendor": self._oui_vendor(adv_address),
            "identity_key": adv_address,
            "context_key": event_type,
        }

    def _normalize_frame(self, frame: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(frame)
        for key in ("src_mac", "dst_mac", "bssid", "ble_adv_address", "identity_key"):
            value = normalized.get(key)
            if isinstance(value, str):
                normalized[key] = self._normalize_mac(value)
        return normalized

    def _candidate_indices_by_time(self, timestamps: list[float], row_timestamp_ms: float | None, window_ms: float) -> list[int]:
        if row_timestamp_ms is None or not timestamps:
            return []
        left = bisect_left(timestamps, row_timestamp_ms - window_ms)
        right = bisect_right(timestamps, row_timestamp_ms + window_ms)
        return list(range(left, right))

    def _best_match(
        self,
        row: dict[str, str],
        mode: str,
        frames: list[dict[str, Any]],
        candidate_indices: list[int],
        config: EnrichmentRunConfig,
    ) -> dict[str, Any] | None:
        if not candidate_indices:
            return None

        row_ts = self._row_timestamp_ms(row)
        if row_ts is None:
            return None

        best: dict[str, Any] | None = None
        for idx in candidate_indices:
            frame = frames[idx]
            frame_ts = float(frame.get("timestamp_ms", 0.0))
            delta = abs(row_ts - frame_ts)
            time_score = max(0.0, 1.0 - (delta / max(config.match_time_window_ms, 1.0)))

            identity_score, context_score, used_identity = self._compatibility(row=row, frame=frame, mode=mode)
            score = (
                config.time_score_weight * time_score
                + config.identity_score_weight * identity_score
                + (config.wifi_context_weight if mode == "wifi" else config.ble_context_weight) * context_score
            )

            method = MatchMethod.TIME_ONLY_MATCH.value
            if used_identity:
                method = MatchMethod.TIME_IDENTITY_BEST_MATCH.value

            candidate = {
                "frame": frame,
                "delta_ms": float(delta),
                "score": float(max(0.0, min(1.0, score))),
                "method": method,
            }

            if best is None or candidate["score"] > best["score"]:
                best = candidate

        if best is None:
            return None
        if float(best["score"]) < config.match_threshold:
            return None
        return best

    def _compatibility(self, row: dict[str, str], frame: dict[str, Any], mode: str) -> tuple[float, float, bool]:
        if mode == "wifi":
            row_id = self._normalize_mac(self._first_present(row, self._WIFI_ID_COLUMNS) or "")
            frame_id = str(frame.get("identity_key", ""))
            identity = 1.0 if row_id and frame_id and row_id == frame_id else 0.0

            row_bssid = self._normalize_mac(self._first_present(row, self._WIFI_BSSID_COLUMNS) or "")
            row_channel = str(self._first_present(row, self._WIFI_CHANNEL_COLUMNS) or "")
            frame_bssid = str(frame.get("bssid", ""))
            frame_channel = str(frame.get("channel", ""))
            context_parts = [
                1.0 if row_bssid and frame_bssid and row_bssid == frame_bssid else 0.0,
                1.0 if row_channel and frame_channel and row_channel == frame_channel else 0.0,
            ]
            context_score = sum(context_parts) / len(context_parts)
            return identity, context_score, bool(row_id and frame_id)

        row_addr = self._normalize_mac(self._first_present(row, self._BLE_ADDR_COLUMNS) or "")
        frame_addr = str(frame.get("identity_key", ""))
        identity = 1.0 if row_addr and frame_addr and row_addr == frame_addr else 0.0

        row_evt = str(self._first_present(row, self._BLE_EVENT_COLUMNS) or "")
        frame_evt = str(frame.get("ble_event_type", ""))
        context_score = 1.0 if row_evt and frame_evt and row_evt == frame_evt else 0.0
        return identity, context_score, bool(row_addr and frame_addr)

    def _frame_to_enrichment_columns(self, frame: dict[str, Any]) -> dict[str, str]:
        return {
            "pcap_timestamp_ms": self._to_str(frame.get("timestamp_ms")),
            "pcap_src_mac": self._to_str(frame.get("src_mac")),
            "pcap_dst_mac": self._to_str(frame.get("dst_mac")),
            "pcap_bssid": self._to_str(frame.get("bssid")),
            "pcap_channel": self._to_str(frame.get("channel")),
            "pcap_frequency_mhz": self._to_str(frame.get("frequency_mhz")),
            "pcap_sequence_number": self._to_str(frame.get("sequence_number")),
            "pcap_fragment_number": self._to_str(frame.get("fragment_number")),
            "pcap_frame_length": self._to_str(frame.get("frame_length")),
            "pcap_ie_ids": self._to_str(frame.get("ie_ids")),
            "pcap_ie_fingerprint": self._to_str(frame.get("ie_fingerprint")),
            "pcap_ie_vendor_ouis": self._to_str(frame.get("ie_vendor_ouis")),
            "pcap_src_vendor": self._to_str(frame.get("src_vendor")),
            "pcap_dst_vendor": self._to_str(frame.get("dst_vendor")),
            "pcap_bssid_vendor": self._to_str(frame.get("bssid_vendor")),
            "pcap_ble_adv_address": self._to_str(frame.get("ble_adv_address")),
            "pcap_ble_event_type": self._to_str(frame.get("ble_event_type")),
            "pcap_ble_manufacturer_digest": self._to_str(frame.get("ble_manufacturer_digest")),
            "pcap_ble_service_uuids": self._to_str(frame.get("ble_service_uuids")),
            "pcap_ble_service_uuid_digest": self._to_str(frame.get("ble_service_uuid_digest")),
            "pcap_ble_local_name": self._to_str(frame.get("ble_local_name")),
            "pcap_ble_local_name_digest": self._to_str(frame.get("ble_local_name_digest")),
            "pcap_ble_tx_power": self._to_str(frame.get("ble_tx_power")),
            "pcap_ble_flags": self._to_str(frame.get("ble_flags")),
            "pcap_ble_vendor": self._to_str(frame.get("ble_vendor")),
        }

    def _build_quality_stats(
        self,
        total_rows: int,
        matched_rows: int,
        seq_covered_rows: int,
        fingerprint_covered_rows: int,
        vendor_covered_rows: int,
        deltas: list[float],
        scores: list[float],
    ) -> EnrichmentQualityStats:
        denominator = max(total_rows, 1)
        return EnrichmentQualityStats(
            matched_row_ratio=round(matched_rows / denominator, 6),
            unmatched_row_ratio=round((total_rows - matched_rows) / denominator, 6),
            sequence_data_coverage_ratio=round(seq_covered_rows / denominator, 6),
            fingerprint_data_coverage_ratio=round(fingerprint_covered_rows / denominator, 6),
            vendor_data_coverage_ratio=round(vendor_covered_rows / denominator, 6),
            match_delta_distribution=self._distribution(deltas),
            match_score_distribution=self._distribution(scores),
        )

    @staticmethod
    def _distribution(values: list[float]) -> dict[str, float | int | None]:
        if not values:
            return {"count": 0, "min": None, "max": None, "avg": None}
        return {
            "count": len(values),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "avg": round(mean(values), 6),
        }

    @classmethod
    def _read_csv(cls, csv_path: Path) -> tuple[list[dict[str, str]], list[str]]:
        rows: list[dict[str, str]] = []
        with csv_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValidationError("Selected CSV has no header row.")
            columns = [str(item).strip() for item in reader.fieldnames]
            for row in reader:
                normalized = {str(k).strip(): ("" if v is None else str(v).strip()) for k, v in row.items()}
                rows.append(normalized)
        return rows, columns

    @staticmethod
    def _write_csv(output_path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col, "") for col in columns})

    @classmethod
    def _row_timestamp_ms(cls, row: dict[str, str]) -> float | None:
        value = cls._first_present(row, cls._TIMESTAMP_COLUMNS)
        if value is None:
            return None
        try:
            raw = float(value)
        except ValueError:
            return None
        if raw > 1e12:
            return raw
        if raw > 1e9:
            return raw * 1000.0
        return raw

    @staticmethod
    def _first_present(row: dict[str, str], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return value
        return None

    @staticmethod
    def _normalize_mac(value: str | None) -> str:
        if not value:
            return ""
        clean = value.strip().replace("-", ":").upper()
        parts = [part.zfill(2) for part in clean.split(":") if part]
        if len(parts) >= 6:
            return ":".join(parts[:6])
        return clean

    @staticmethod
    def _oui_vendor(mac: str) -> str:
        if not mac:
            return ""
        parts = mac.split(":")
        if len(parts) < 3:
            return ""
        return ":".join(parts[:3])

    @staticmethod
    def _to_str(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            if math.isnan(value):
                return ""
            return f"{value:.6f}"
        return str(value)
