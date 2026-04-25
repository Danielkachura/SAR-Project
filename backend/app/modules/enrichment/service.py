"""MOD-007 Enrichment — CSV+PCAP correlator."""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from app.core.errors import NotFoundError, ValidationError
from app.models.canonical_models import (
    EnrichmentDiagnostics,
    EnrichmentMatchMethod,
    EnrichmentParameters,
    EnrichmentRunPayload,
    ProtocolMode,
)
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.session_navigation.service import SessionNavigationService

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

_WIFI_PCAP_COLUMNS = [
    "timestamp_utc",
    "src_mac",
    "dst_mac",
    "bssid",
    "seq_ctl",
    "frame_len",
    "ie_ids",
    "ie_fingerprint",
    "ie_vendor_ouis",
    "ssid",
]

_BLE_PCAP_COLUMNS = [
    "timestamp_utc",
    "ble_advertiser_addr",
    "ble_addr_type",
    "ble_event_type",
    "ble_manufacturer_data",
    "ble_service_uuids",
    "ble_local_name",
    "ble_tx_power",
    "ble_flags",
    "ble_vendor_company_id",
]

_REQUIRED_ENRICH_COLUMNS = [
    "enr_src_vendor",
    "enr_dst_mac",
    "enr_bssid",
    "enr_seq_num",
    "enr_frame_length",
    "enr_ie_ids",
    "enr_ie_fingerprint",
    "enr_ie_vendor_ouis",
    "enr_channel",
    "enr_frame_type",
    "enr_ble_advertiser_addr",
    "enr_ble_addr_type",
    "enr_ble_event_type",
    "enr_ble_manufacturer_data",
    "enr_ble_service_uuids",
    "enr_ble_local_name",
    "enr_ble_tx_power",
    "enr_ble_flags",
    "enr_ble_vendor_company_id",
    "match_found",
    "match_delta_ms",
    "match_score",
    "match_method",
]

_IE_KEEP_IDS = {1, 50, 45, 61, 127, 191, 192, 221}

_BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"
_BROADCAST_ALIASES = {
    "broadcast": _BROADCAST_MAC,
    "ff-ff-ff-ff-ff-ff": _BROADCAST_MAC,
    "ff.ff.ff.ff.ff.ff": _BROADCAST_MAC,
    "": "",
    "nan": "",
}


def _build_ie_features(pkt) -> tuple[str, str, str, bytes]:
    from scapy.all import Dot11Elt

    ids: list[str] = []
    fingerprint_parts: list[str] = []
    vendor_ouis: list[str] = []
    ssid_bytes = b""
    elt = pkt.getlayer(Dot11Elt)
    while elt is not None:
        eid = int(getattr(elt, "ID", -1))
        info = bytes(getattr(elt, "info", b""))
        if eid == 0:
            ssid_bytes = info
        if eid in _IE_KEEP_IDS:
            ids.append(str(eid))
            fingerprint_parts.append(f"{eid}:{info.hex()}")
            if eid == 221 and len(info) >= 3:
                vendor_ouis.append(info[:3].hex())
        elt = elt.payload.getlayer(Dot11Elt)
    return ",".join(ids), ";".join(fingerprint_parts), ",".join(vendor_ouis), ssid_bytes


def _extract_ble_features(pkt) -> dict[str, str]:
    fields = {
        "ble_advertiser_addr": "",
        "ble_addr_type": "",
        "ble_event_type": "",
        "ble_manufacturer_data": "",
        "ble_service_uuids": "",
        "ble_local_name": "",
        "ble_tx_power": "",
        "ble_flags": "",
        "ble_vendor_company_id": "",
    }

    # Best effort extraction from scapy BLE packet structure (varies by link-layer capture format)
    summary = str(pkt.summary())
    if "BTLE" not in summary and "BLE" not in summary:
        return fields

    advertiser_addr = getattr(pkt, "AdvA", None) or getattr(pkt, "InitA", None)
    if advertiser_addr:
        fields["ble_advertiser_addr"] = str(advertiser_addr).lower()

    pdu_type = getattr(pkt, "PDU_type", None) or getattr(pkt, "PDUType", None)
    if pdu_type is not None:
        fields["ble_event_type"] = str(pdu_type)

    tx_power = getattr(pkt, "tx_power", None)
    if tx_power is not None:
        fields["ble_tx_power"] = str(tx_power)

    return fields


def _extract_pcap_features(pcap_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (wifi_df, ble_df)."""
    try:
        from scapy.all import Dot11, PcapReader
    except Exception as exc:  # pragma: no cover
        raise ValidationError(
            "scapy is required for enrichment. Install with: pip install scapy"
        ) from exc

    wifi_rows: list[dict] = []
    ble_rows: list[dict] = []
    ssid_observations: dict[str, list[str]] = defaultdict(list)

    try:
        with PcapReader(str(pcap_path)) as reader:
            for pkt in reader:
                ts = getattr(pkt, "time", None)
                if ts is None:
                    continue
                ts_utc = pd.to_datetime(float(ts), unit="s", utc=True, errors="coerce")

                if pkt.haslayer(Dot11):
                    dot11 = pkt[Dot11]
                    ie_ids, ie_fp, ie_vendors, ssid_bytes = _build_ie_features(pkt)
                    src_mac = (dot11.addr2 or "").lower()
                    ssid_str = ssid_bytes.decode("utf-8", errors="replace") if ssid_bytes else ""
                    if src_mac and ssid_str:
                        ssid_observations[src_mac].append(ssid_str)

                    wifi_rows.append(
                        {
                            "timestamp_utc": ts_utc,
                            "src_mac": src_mac,
                            "dst_mac": (dot11.addr1 or "").lower(),
                            "bssid": (dot11.addr3 or "").lower(),
                            "seq_ctl": getattr(dot11, "SC", None),
                            "frame_len": len(pkt),
                            "ie_ids": ie_ids,
                            "ie_fingerprint": ie_fp,
                            "ie_vendor_ouis": ie_vendors,
                            "ssid": ssid_str,
                        }
                    )
                    continue

                ble_base = _extract_ble_features(pkt)
                if any(ble_base.values()):
                    ble_rows.append({"timestamp_utc": ts_utc, **ble_base})

    except Exception as exc:
        raise ValidationError(f"Failed to parse PCAP: {pcap_path.name} — {exc}") from exc

    wifi_df = pd.DataFrame(wifi_rows) if wifi_rows else pd.DataFrame(columns=_WIFI_PCAP_COLUMNS)
    ble_df = pd.DataFrame(ble_rows) if ble_rows else pd.DataFrame(columns=_BLE_PCAP_COLUMNS)

    if not wifi_df.empty:
        consensus = {
            mac: Counter(values).most_common(1)[0][0]
            for mac, values in ssid_observations.items()
            if values
        }
        if consensus:
            wifi_df["ssid"] = wifi_df["src_mac"].map(consensus).fillna(wifi_df["ssid"])

    return wifi_df, ble_df


def _normalize_mac_series(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.lower()
    return s.replace(_BROADCAST_ALIASES)


def _parse_row_timestamp_ms(row: pd.Series) -> float | None:
    for col in ("timestamp_utc", "timestamp", "time", "ts"):
        if col in row and pd.notna(row[col]):
            ts = pd.to_datetime(row[col], errors="coerce", utc=True)
            if pd.notna(ts):
                return float(ts.value / 1_000_000)
    return None


def _row_identity(row: pd.Series, protocol: ProtocolMode) -> str:
    if protocol == ProtocolMode.BLE:
        for key in ("device_address", "adv_address", "mac", "src_mac"):
            value = str(row.get(key, "")).strip().lower()
            if value and value != "nan":
                return value
        return ""

    for key in ("src_mac", "mac", "source_mac", "addr"):
        value = str(row.get(key, "")).strip().lower()
        if value and value != "nan":
            return value
    return ""


def _compute_match(
    row: pd.Series,
    protocol: ProtocolMode,
    wifi_df: pd.DataFrame,
    ble_df: pd.DataFrame,
    parameters: EnrichmentParameters,
) -> dict[str, object]:
    row_ts = _parse_row_timestamp_ms(row)
    if row_ts is None:
        return {
            "match_found": False,
            "match_delta_ms": None,
            "match_score": 0.0,
            "match_method": EnrichmentMatchMethod.NO_MATCH.value,
        }

    row_id = _row_identity(row, protocol)
    context_weight = (
        float(parameters.wifi_context_weight)
        if protocol == ProtocolMode.WIFI
        else float(parameters.ble_context_weight)
    )

    candidates: list[dict[str, object]] = []
    if protocol == ProtocolMode.BLE:
        for _, frame in ble_df.iterrows():
            frame_ts = pd.to_datetime(frame.get("timestamp_utc"), utc=True, errors="coerce")
            if pd.isna(frame_ts):
                continue
            delta_ms = abs(row_ts - float(frame_ts.value / 1_000_000))
            if delta_ms > parameters.match_time_window_ms:
                continue
            frame_id = str(frame.get("ble_advertiser_addr", "")).strip().lower()
            identity_score = 1.0 if row_id and row_id == frame_id else 0.0
            context_score = 1.0 if str(frame.get("ble_event_type", "")).strip() else 0.0
            time_score = max(0.0, 1.0 - (delta_ms / parameters.match_time_window_ms))
            if identity_score == 0.0 and context_score == 0.0:
                time_score = 0.0
            score = (
                parameters.time_score_weight * time_score
                + parameters.identity_score_weight * identity_score
                + context_weight * context_score
            )
            candidates.append(
                {
                    "score": float(score),
                    "delta_ms": float(delta_ms),
                    "identity_match": bool(identity_score > 0.0),
                    "frame": frame,
                }
            )
    else:
        for _, frame in wifi_df.iterrows():
            frame_ts = pd.to_datetime(frame.get("timestamp_utc"), utc=True, errors="coerce")
            if pd.isna(frame_ts):
                continue
            delta_ms = abs(row_ts - float(frame_ts.value / 1_000_000))
            if delta_ms > parameters.match_time_window_ms:
                continue
            frame_id = str(frame.get("src_mac", "")).strip().lower()
            identity_score = 1.0 if row_id and row_id == frame_id else 0.0
            row_bssid = str(row.get("bssid", "")).strip().lower()
            frame_bssid = str(frame.get("bssid", "")).strip().lower()
            context_score = 1.0 if row_bssid and frame_bssid and row_bssid == frame_bssid else 0.0
            time_score = max(0.0, 1.0 - (delta_ms / parameters.match_time_window_ms))
            if identity_score == 0.0 and context_score == 0.0:
                time_score = 0.0
            score = (
                parameters.time_score_weight * time_score
                + parameters.identity_score_weight * identity_score
                + context_weight * context_score
            )
            candidates.append(
                {
                    "score": float(score),
                    "delta_ms": float(delta_ms),
                    "identity_match": bool(identity_score > 0.0),
                    "frame": frame,
                }
            )

    if not candidates:
        return {
            "match_found": False,
            "match_delta_ms": None,
            "match_score": 0.0,
            "match_method": EnrichmentMatchMethod.NO_MATCH.value,
        }

    best = max(candidates, key=lambda item: (item["score"], -item["delta_ms"]))
    if best["score"] < parameters.match_threshold:
        return {
            "match_found": False,
            "match_delta_ms": float(best["delta_ms"]),
            "match_score": float(best["score"]),
            "match_method": EnrichmentMatchMethod.NO_MATCH.value,
        }

    method = (
        EnrichmentMatchMethod.TIME_IDENTITY_BEST_MATCH.value
        if best["identity_match"]
        else EnrichmentMatchMethod.TIME_ONLY_MATCH.value
    )
    # TODO: Add an explicit context-assisted method label when identity is absent but context evidence contributes.
    return {
        "match_found": True,
        "match_delta_ms": float(best["delta_ms"]),
        "match_score": float(best["score"]),
        "match_method": method,
        "frame": best["frame"],
    }


def _enrich_dataframe(
    csv_df: pd.DataFrame,
    wifi_df: pd.DataFrame,
    ble_df: pd.DataFrame,
    protocol: ProtocolMode,
    parameters: EnrichmentParameters,
) -> tuple[pd.DataFrame, int, int]:
    out = csv_df.copy()
    out.columns = [c.strip().lower() for c in out.columns]
    if not any(col in out.columns for col in ("timestamp_utc", "timestamp", "time", "ts")):
        raise ValidationError("CSV is missing 'timestamp_utc' column.")

    if "src_mac" in out.columns:
        out["src_mac"] = _normalize_mac_series(out["src_mac"])
    if "dst_mac" in out.columns:
        out["dst_mac"] = _normalize_mac_series(out["dst_mac"])
    if "bssid" in out.columns:
        out["bssid"] = _normalize_mac_series(out["bssid"])

    matched = 0
    # TODO: O(n×m) matching — candidate for indexed lookup (time-bucket + identity key) for large scans.
    for idx, row in out.iterrows():
        match = _compute_match(row, protocol=protocol, wifi_df=wifi_df, ble_df=ble_df, parameters=parameters)

        for key in ("match_found", "match_delta_ms", "match_score", "match_method"):
            out.at[idx, key] = match.get(key)

        frame = match.get("frame")
        if frame is not None:
            matched += 1
            if protocol == ProtocolMode.BLE:
                out.at[idx, "enr_ble_advertiser_addr"] = frame.get("ble_advertiser_addr")
                out.at[idx, "enr_ble_addr_type"] = frame.get("ble_addr_type")
                out.at[idx, "enr_ble_event_type"] = frame.get("ble_event_type")
                out.at[idx, "enr_ble_manufacturer_data"] = frame.get("ble_manufacturer_data")
                out.at[idx, "enr_ble_service_uuids"] = frame.get("ble_service_uuids")
                out.at[idx, "enr_ble_local_name"] = frame.get("ble_local_name")
                out.at[idx, "enr_ble_tx_power"] = frame.get("ble_tx_power")
                out.at[idx, "enr_ble_flags"] = frame.get("ble_flags")
                out.at[idx, "enr_ble_vendor_company_id"] = frame.get("ble_vendor_company_id")
            else:
                out.at[idx, "enr_dst_mac"] = frame.get("dst_mac")
                out.at[idx, "enr_bssid"] = frame.get("bssid")
                out.at[idx, "enr_seq_num"] = frame.get("seq_ctl")
                out.at[idx, "enr_frame_length"] = frame.get("frame_len")
                out.at[idx, "enr_ie_ids"] = frame.get("ie_ids")
                out.at[idx, "enr_ie_fingerprint"] = frame.get("ie_fingerprint")
                out.at[idx, "enr_ie_vendor_ouis"] = frame.get("ie_vendor_ouis")

    total = len(out)
    for col in _REQUIRED_ENRICH_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    out["match_found"] = out["match_found"].fillna(False).astype(bool)
    return out, matched, total


class EnrichmentService:
    def __init__(
        self,
        session_service: SessionNavigationService,
        dataset_service: DatasetDiscoveryService,
    ) -> None:
        self._session_service = session_service
        self._dataset_service = dataset_service

    def run_enrichment(
        self,
        session_id: str,
        selected_csv_file: str,
        selected_pcap_file: str,
        parameters: EnrichmentParameters,
    ) -> EnrichmentRunPayload:
        session = self._session_service.require_session(session_id)
        if Path(selected_csv_file).stem.lower() != Path(selected_pcap_file).stem.lower():
            raise ValidationError(
                "Selected PCAP must have the same basename as selected CSV."
            )
        csv_path = self._resolve_csv(session.scan_folder_id, selected_csv_file)
        pcap_path = self._resolve_pcap(session.scan_folder_id, selected_pcap_file)
        protocol = session.mode

        try:
            csv_df = pd.read_csv(csv_path)
        except Exception as exc:
            raise ValidationError(f"Failed to read CSV: {selected_csv_file} — {exc}") from exc
        if csv_df.empty:
            raise ValidationError(f"CSV file is empty: {selected_csv_file}")

        wifi_df, ble_df = _extract_pcap_features(pcap_path)
        # TODO: For BLE sessions, surface a diagnostic warning when BLE extraction yields zero rows (best-effort parser limit).
        enriched_df, matched, total = _enrich_dataframe(
            csv_df,
            wifi_df,
            ble_df,
            protocol=protocol,
            parameters=parameters,
        )

        stem = Path(selected_csv_file).stem
        output_name = f"{stem}_ENRICHED.csv"
        output_path = self._dataset_service.resolve_csv_path(session.scan_folder_id, output_name)
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        try:
            enriched_df.to_csv(tmp_path, index=False)
            tmp_path.replace(output_path)
        except PermissionError as exc:
            tmp_path.unlink(missing_ok=True)
            raise ValidationError(
                f"Cannot write enriched artifact '{output_name}'. "
                f"The file is locked by another program (likely open in Excel). "
                f"Close it and try again."
            ) from exc

        artifact_id = f"{session.scan_folder_id}:{output_name}"
        self._session_service.activate_artifact(session_id=session_id, artifact_id=artifact_id)

        match_rate = round(matched / total, 4) if total else 0.0
        return EnrichmentRunPayload(
            selected_csv_file=selected_csv_file,
            selected_pcap_file=selected_pcap_file,
            output_enriched_file=output_name,
            protocol=protocol,
            parameters=parameters,
            diagnostics=EnrichmentDiagnostics(
                total_rows=total,
                matched_rows=matched,
                unmatched_rows=total - matched,
                match_rate=match_rate,
            ),
        )

    def resolve_matching_pcap(self, folder_id: str, csv_file_name: str) -> str:
        stem = Path(csv_file_name).stem.lower()
        inventory = self._dataset_service.resolve_inventory(folder_id)
        match = next(
            (item.file_name for item in inventory.pcap_files if item.base_name.lower() == stem),
            None,
        )
        if match is None:
            raise ValidationError(
                f"No matching PCAP found for '{csv_file_name}'. "
                "Expected a file with the same base name in the same folder."
            )
        return match

    def _resolve_csv(self, folder_id: str, file_name: str) -> Path:
        inventory = self._dataset_service.resolve_inventory(folder_id)
        available = {item.file_name for item in inventory.raw_csv_files}
        if file_name not in available:
            raise ValidationError(f"Selected CSV is not available in active folder: {file_name}")
        path = self._dataset_service.resolve_csv_path(folder_id, file_name)
        if not path.exists():
            raise NotFoundError(f"CSV file does not exist: {file_name}")
        return path

    def _resolve_pcap(self, folder_id: str, file_name: str) -> Path:
        inventory = self._dataset_service.resolve_inventory(folder_id)
        available = {item.file_name for item in inventory.pcap_files}
        if file_name not in available:
            raise ValidationError(f"Selected PCAP is not available in active folder: {file_name}")
        path = self._dataset_service.resolve_csv_path(folder_id, file_name)
        if not path.exists():
            raise NotFoundError(f"PCAP file does not exist: {file_name}")
        return path
