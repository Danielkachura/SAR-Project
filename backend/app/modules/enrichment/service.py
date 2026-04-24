"""MOD-007 Enrichment Module — pure-Python PCAP reader and CSV enrichment."""
from __future__ import annotations

import csv
import struct
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from app.core.errors import NotFoundError, ValidationError
from app.models.canonical_models import (
    ArtifactKind,
    EnrichmentMatchMethod,
    EnrichmentParameters,
    EnrichmentDiagnostics,
    EnrichmentRunPayload,
    ProtocolMode,
)
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.session_navigation.service import SessionNavigationService


# ---------------------------------------------------------------------------
# PCAP binary parser (no external dependencies)
# ---------------------------------------------------------------------------

@dataclass
class _PcapFrame:
    timestamp_ms: float
    link_type: int
    frame_length: int
    # Wi-Fi fields
    src_mac: str | None = None
    dst_mac: str | None = None
    bssid: str | None = None
    seq_num: int | None = None
    ie_ids: list[int] = field(default_factory=list)
    ie_fingerprint: str | None = None
    ie_vendor_ouis: list[str] = field(default_factory=list)
    channel: int | None = None
    frame_type: str | None = None
    # BLE fields
    ble_advertiser_addr: str | None = None
    ble_addr_type: str | None = None
    ble_event_type: str | None = None
    ble_manufacturer_data: str | None = None
    ble_service_uuids: list[str] = field(default_factory=list)
    ble_local_name: str | None = None
    ble_tx_power: int | None = None
    ble_flags: int | None = None
    ble_vendor_company_id: str | None = None


_BLE_ADV_TYPE_NAMES = {
    0x00: "ADV_IND",
    0x01: "ADV_DIRECT_IND",
    0x02: "ADV_NONCONN_IND",
    0x03: "SCAN_REQ",
    0x04: "SCAN_RSP",
    0x05: "CONNECT_IND",
    0x06: "ADV_SCAN_IND",
}

_LINK_80211 = 105
_LINK_RADIOTAP = 127
_LINK_BLE_LL = 251
_LINK_BTLE = 272

_MGMT_FIXED_PARAM_LENS: dict[int, int] = {
    0: 4, 1: 6, 2: 10, 3: 6, 4: 0,
    5: 12, 8: 12, 11: 6, 12: 2, 13: 2,
}


def _fmt_mac(raw: bytes) -> str:
    return ":".join(f"{b:02x}" for b in raw)


def _parse_80211(frame: _PcapFrame, data: bytes) -> None:
    if len(data) < 24:
        return
    fc = struct.unpack_from("<H", data, 0)[0]
    frame_type = (fc >> 2) & 0x3
    frame_subtype = (fc >> 4) & 0xF
    type_names = {0: "management", 1: "control", 2: "data", 3: "extension"}
    frame.frame_type = type_names.get(frame_type, "unknown")
    if frame_type == 1:  # control — addresses not in standard positions
        return
    frame.dst_mac = _fmt_mac(data[4:10])
    frame.src_mac = _fmt_mac(data[10:16])
    frame.bssid = _fmt_mac(data[16:22])
    seq_ctrl = struct.unpack_from("<H", data, 22)[0]
    frame.seq_num = (seq_ctrl >> 4) & 0xFFF
    if frame_type == 0:  # management — parse IEs
        fixed_len = _MGMT_FIXED_PARAM_LENS.get(frame_subtype, 0)
        _parse_ies(frame, data, 24 + fixed_len)


def _parse_ies(frame: _PcapFrame, data: bytes, offset: int) -> None:
    ie_ids: list[int] = []
    vendor_ouis: list[str] = []
    while offset + 2 <= len(data):
        tag_id = data[offset]
        tag_len = data[offset + 1]
        offset += 2
        if offset + tag_len > len(data):
            break
        tag_data = data[offset:offset + tag_len]
        offset += tag_len
        ie_ids.append(tag_id)
        if tag_id == 3 and tag_len >= 1:  # DS Parameter Set → channel
            frame.channel = tag_data[0]
        if tag_id == 221 and tag_len >= 3:  # Vendor Specific → OUI
            vendor_ouis.append(":".join(f"{b:02x}" for b in tag_data[:3]))
    frame.ie_ids = ie_ids
    frame.ie_fingerprint = ",".join(str(x) for x in sorted(ie_ids)) if ie_ids else None
    frame.ie_vendor_ouis = vendor_ouis


def _parse_ble_ad_structures(frame: _PcapFrame, data: bytes) -> None:
    service_uuids: list[str] = []
    offset = 0
    while offset < len(data):
        length = data[offset]
        offset += 1
        if length == 0:
            break
        if offset + length > len(data):
            break
        ad_type = data[offset]
        ad_data = data[offset + 1:offset + length]
        offset += length
        if ad_type == 0x01 and ad_data:
            frame.ble_flags = ad_data[0]
        elif ad_type in (0x08, 0x09):
            frame.ble_local_name = ad_data.decode("utf-8", errors="replace")
        elif ad_type == 0x0A and ad_data:
            frame.ble_tx_power = struct.unpack_from("b", ad_data, 0)[0]
        elif ad_type in (0x02, 0x03):
            for i in range(0, len(ad_data) - 1, 2):
                service_uuids.append(f"{struct.unpack_from('<H', ad_data, i)[0]:04x}")
        elif ad_type in (0x04, 0x05):
            for i in range(0, len(ad_data) - 3, 4):
                service_uuids.append(f"{struct.unpack_from('<I', ad_data, i)[0]:08x}")
        elif ad_type in (0x06, 0x07):
            for i in range(0, len(ad_data) - 15, 16):
                h = ad_data[i:i + 16][::-1].hex()
                service_uuids.append(f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}")
        elif ad_type == 0xFF and len(ad_data) >= 2:
            company_id = struct.unpack_from("<H", ad_data, 0)[0]
            frame.ble_vendor_company_id = f"{company_id:04x}"
            frame.ble_manufacturer_data = ad_data.hex()
    frame.ble_service_uuids = service_uuids


def _parse_ble_ll(frame: _PcapFrame, data: bytes) -> None:
    if len(data) < 2:
        return
    pdu_hdr = struct.unpack_from("<H", data, 0)[0]
    pdu_type = pdu_hdr & 0xF
    tx_add = (pdu_hdr >> 6) & 0x1
    pdu_len = (pdu_hdr >> 8) & 0x3F
    frame.ble_event_type = _BLE_ADV_TYPE_NAMES.get(pdu_type, f"type_{pdu_type}")
    frame.ble_addr_type = "random" if tx_add else "public"
    if pdu_type in (0x00, 0x02, 0x04, 0x06) and len(data) >= 8:
        frame.ble_advertiser_addr = _fmt_mac(data[2:8])
        adv_data = data[8:2 + pdu_len]
        _parse_ble_ad_structures(frame, adv_data)
    elif pdu_type == 0x01 and len(data) >= 8:
        frame.ble_advertiser_addr = _fmt_mac(data[2:8])


def _parse_pcap_file(pcap_path: Path) -> tuple[int, list[_PcapFrame]]:
    """Read .pcap file, return (link_type, frames). Raises ValidationError on bad file."""
    data = pcap_path.read_bytes()
    if len(data) < 24:
        raise ValidationError(f"PCAP file too small: {pcap_path.name}")

    magic = struct.unpack_from("<I", data, 0)[0]
    if magic in (0xA1B2C3D4, 0xA1B23C4D):
        endian, is_ns = "<", magic == 0xA1B23C4D
    elif magic in (0xD4C3B2A1, 0x4D3CB2A1):
        endian, is_ns = ">", magic == 0x4D3CB2A1
    else:
        raise ValidationError(f"Not a valid pcap file (magic={hex(magic)}): {pcap_path.name}")

    _, _, _, _, _, _, link_type = struct.unpack_from(f"{endian}IHHiIII", data, 0)
    frames: list[_PcapFrame] = []
    pos = 24
    while pos + 16 <= len(data):
        ts_sec, ts_frac, incl_len, orig_len = struct.unpack_from(f"{endian}IIII", data, pos)
        pos += 16
        if pos + incl_len > len(data):
            break
        pkt = data[pos:pos + incl_len]
        pos += incl_len
        ts_ms = ts_sec * 1000.0 + (ts_frac / 1_000_000.0 if is_ns else ts_frac / 1000.0)
        frame = _PcapFrame(timestamp_ms=ts_ms, link_type=link_type, frame_length=orig_len)
        if link_type == _LINK_RADIOTAP and len(pkt) >= 4:
            rt_len = struct.unpack_from("<H", pkt, 2)[0]
            if rt_len <= len(pkt):
                _parse_80211(frame, pkt[rt_len:])
        elif link_type == _LINK_80211:
            _parse_80211(frame, pkt)
        elif link_type == _LINK_BLE_LL:
            _parse_ble_ll(frame, pkt)
        elif link_type == _LINK_BTLE and len(pkt) >= 14:
            _parse_ble_ll(frame, pkt[14:])
        frames.append(frame)
    return link_type, frames


# ---------------------------------------------------------------------------
# PCAP index for fast time + identity lookup
# ---------------------------------------------------------------------------

class _PcapIndex:
    _BUCKET_MS = 1000.0  # 1-second time buckets

    def __init__(self, frames: list[_PcapFrame]) -> None:
        self._by_time: dict[int, list[_PcapFrame]] = defaultdict(list)
        self._by_identity: dict[str, list[_PcapFrame]] = defaultdict(list)
        for f in frames:
            bucket = int(f.timestamp_ms // self._BUCKET_MS)
            self._by_time[bucket].append(f)
            identity = (f.src_mac or f.ble_advertiser_addr or "").lower()
            if identity:
                self._by_identity[identity].append(f)

    def get_candidates(self, row_ts_ms: float, window_ms: float) -> list[_PcapFrame]:
        low_bucket = int((row_ts_ms - window_ms) // self._BUCKET_MS)
        high_bucket = int((row_ts_ms + window_ms) // self._BUCKET_MS)
        result: list[_PcapFrame] = []
        for b in range(low_bucket, high_bucket + 1):
            result.extend(self._by_time.get(b, []))
        return result


# ---------------------------------------------------------------------------
# Column name helpers (shared with calibration patterns)
# ---------------------------------------------------------------------------

_MAC_COLUMNS = ("mac", "device_id", "device_address", "addr", "source_mac", "src_mac", "bssid")
_TS_COLUMNS = ("timestamp", "time", "ts", "packet_time", "capture_time", "detection_time", "epoch_ms", "epoch_s")


def _first_present(row: dict[str, str], columns: tuple[str, ...]) -> str | None:
    for k in columns:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return None


def _parse_ts_ms(row: dict[str, str]) -> float | None:
    raw = _first_present(row, _TS_COLUMNS)
    if raw is None:
        return None
    try:
        val = float(raw)
        # Heuristic: values < 1e10 are seconds, otherwise milliseconds
        return val * 1000.0 if val < 1e10 else val
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Enrichment result row builders
# ---------------------------------------------------------------------------

# Wi-Fi enrichment column names
_WIFI_COLS = [
    "enr_src_vendor", "enr_dst_mac", "enr_bssid", "enr_seq_num",
    "enr_frame_length", "enr_ie_ids", "enr_ie_fingerprint",
    "enr_ie_vendor_ouis", "enr_channel", "enr_frame_type",
]
# BLE enrichment column names (always present in schema per spec)
_BLE_COLS = [
    "enr_ble_advertiser_addr", "enr_ble_addr_type", "enr_ble_event_type",
    "enr_ble_manufacturer_data", "enr_ble_service_uuids", "enr_ble_local_name",
    "enr_ble_tx_power", "enr_ble_flags", "enr_ble_vendor_company_id",
]
# Match diagnostics (always present)
_DIAG_COLS = ["match_found", "match_delta_ms", "match_score", "match_method"]

_ALL_ENRICHMENT_COLS = _WIFI_COLS + _BLE_COLS + _DIAG_COLS


def _empty_enrichment_cols() -> dict[str, str]:
    return {col: "" for col in _ALL_ENRICHMENT_COLS}


def _build_enriched_fields(
    frame: _PcapFrame,
    delta_ms: float,
    score: float,
    method: str,
) -> dict[str, str]:
    return {
        # Wi-Fi
        "enr_src_vendor": "",
        "enr_dst_mac": frame.dst_mac or "",
        "enr_bssid": frame.bssid or "",
        "enr_seq_num": str(frame.seq_num) if frame.seq_num is not None else "",
        "enr_frame_length": str(frame.frame_length),
        "enr_ie_ids": str(frame.ie_ids) if frame.ie_ids else "",
        "enr_ie_fingerprint": frame.ie_fingerprint or "",
        "enr_ie_vendor_ouis": str(frame.ie_vendor_ouis) if frame.ie_vendor_ouis else "",
        "enr_channel": str(frame.channel) if frame.channel is not None else "",
        "enr_frame_type": frame.frame_type or "",
        # BLE
        "enr_ble_advertiser_addr": frame.ble_advertiser_addr or "",
        "enr_ble_addr_type": frame.ble_addr_type or "",
        "enr_ble_event_type": frame.ble_event_type or "",
        "enr_ble_manufacturer_data": frame.ble_manufacturer_data or "",
        "enr_ble_service_uuids": str(frame.ble_service_uuids) if frame.ble_service_uuids else "",
        "enr_ble_local_name": frame.ble_local_name or "",
        "enr_ble_tx_power": str(frame.ble_tx_power) if frame.ble_tx_power is not None else "",
        "enr_ble_flags": str(frame.ble_flags) if frame.ble_flags is not None else "",
        "enr_ble_vendor_company_id": frame.ble_vendor_company_id or "",
        # Diagnostics
        "match_found": "true",
        "match_delta_ms": f"{delta_ms:.3f}",
        "match_score": f"{score:.4f}",
        "match_method": method,
    }


# ---------------------------------------------------------------------------
# EnrichmentService
# ---------------------------------------------------------------------------

class EnrichmentService:
    def __init__(
        self,
        session_service: SessionNavigationService,
        dataset_service: DatasetDiscoveryService,
    ) -> None:
        self._session_service = session_service
        self._dataset_service = dataset_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_enrichment(
        self,
        session_id: str,
        selected_csv_file: str,
        selected_pcap_file: str,
        parameters: EnrichmentParameters,
    ) -> EnrichmentRunPayload:
        """Execute the 7-step enrichment algorithm and write the ENRICHED artifact."""
        session = self._session_service.require_session(session_id)

        # Step 0 — Validate inputs
        csv_path = self._resolve_csv(session.scan_folder_id, selected_csv_file)
        pcap_path = self._resolve_pcap(session.scan_folder_id, selected_pcap_file)
        protocol = session.mode

        # Step 1 — Parse PCAP into frame-feature table
        link_type, frames = _parse_pcap_file(pcap_path)
        if not frames:
            raise ValidationError(f"PCAP file contained no parseable packets: {selected_pcap_file}")

        # Step 2 — Normalize is done inside _parse_pcap_file (timestamps → ms, MACs → lowercase hex)

        # Step 3 — Build searchable index
        index = _PcapIndex(frames)

        # Steps 4-6 — Match CSV rows
        csv_rows = self._read_csv_rows(csv_path)
        if not csv_rows:
            raise ValidationError(f"CSV file is empty: {selected_csv_file}")

        enriched_rows, matched = self._match_rows(csv_rows, index, parameters, protocol)

        # Step 7 — Write official ENRICHED artifact
        stem = Path(selected_csv_file).stem
        output_name = f"{stem}_ENRICHED.csv"
        output_path = self._dataset_service._paths.folder_path(session.scan_folder_id) / output_name

        output_columns = list(csv_rows[0].keys()) + _ALL_ENRICHMENT_COLS
        with output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=output_columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(enriched_rows)

        # Activate the new artifact
        artifact_id = f"{session.scan_folder_id}:{output_name}"
        try:
            self._session_service.activate_artifact(session_id=session_id, artifact_id=artifact_id)
        except NotFoundError:
            # Inventory cache miss right after write — not fatal; caller can activate manually
            pass

        total = len(enriched_rows)
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_csv(self, folder_id: str, file_name: str) -> Path:
        inventory = self._dataset_service.resolve_inventory(folder_id)
        available = {item.file_name for item in inventory.raw_csv_files}
        if file_name not in available:
            raise ValidationError(f"Selected CSV is not available in active folder: {file_name}")
        path = self._dataset_service._paths.folder_path(folder_id) / file_name
        if not path.exists():
            raise NotFoundError(f"CSV file does not exist: {file_name}")
        return path

    def resolve_matching_pcap(self, folder_id: str, csv_file_name: str) -> str:
        """Return PCAP file_name whose base_name matches the CSV stem. Raises ValidationError if none."""
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

    def _resolve_pcap(self, folder_id: str, file_name: str) -> Path:
        inventory = self._dataset_service.resolve_inventory(folder_id)
        available = {item.file_name for item in inventory.pcap_files}
        if file_name not in available:
            raise ValidationError(f"Selected PCAP is not available in active folder: {file_name}")
        path = self._dataset_service._paths.folder_path(folder_id) / file_name
        if not path.exists():
            raise NotFoundError(f"PCAP file does not exist: {file_name}")
        return path

    def _match_rows(
        self,
        rows: list[dict[str, str]],
        index: _PcapIndex,
        params: EnrichmentParameters,
        protocol: ProtocolMode,
    ) -> tuple[list[dict[str, str]], int]:
        enriched: list[dict[str, str]] = []
        matched = 0
        no_match_fields = {
            **_empty_enrichment_cols(),
            "match_found": "false",
            "match_method": EnrichmentMatchMethod.NO_MATCH.value,
        }
        for row in rows:
            row_ts = _parse_ts_ms(row)
            if row_ts is None:
                enriched.append({**row, **no_match_fields})
                continue

            candidates = index.get_candidates(row_ts, params.match_time_window_ms)
            if not candidates:
                enriched.append({**row, **no_match_fields})
                continue

            best = self._score_candidates(row, row_ts, candidates, params, protocol)
            if best is None:
                enriched.append({**row, **no_match_fields})
            else:
                score, delta_ms, frame, method = best
                matched += 1
                enriched.append({**row, **_build_enriched_fields(frame, delta_ms, score, method)})

        return enriched, matched

    def _score_candidates(
        self,
        row: dict[str, str],
        row_ts_ms: float,
        candidates: list[_PcapFrame],
        params: EnrichmentParameters,
        protocol: ProtocolMode,
    ) -> tuple[float, float, _PcapFrame, str] | None:
        row_identity = (_first_present(row, _MAC_COLUMNS) or "").lower()
        best_score = -1.0
        best_frame: _PcapFrame | None = None
        best_delta = 0.0
        best_method = EnrichmentMatchMethod.NO_MATCH.value

        for frame in candidates:
            delta_ms = abs(frame.timestamp_ms - row_ts_ms)
            if delta_ms > params.match_time_window_ms:
                continue

            time_score = max(0.0, 1.0 - delta_ms / params.match_time_window_ms)

            # Identity match
            frame_identity = (frame.src_mac or frame.ble_advertiser_addr or "").lower()
            identity_match = bool(row_identity and frame_identity and row_identity == frame_identity)
            identity_score = 1.0 if identity_match else 0.0

            # Context score
            context_score = self._context_score(row, frame, protocol)

            if protocol == ProtocolMode.BLE:
                score = (
                    params.time_score_weight * time_score
                    + params.identity_score_weight * identity_score
                    + params.ble_context_weight * context_score
                )
            else:
                score = (
                    params.time_score_weight * time_score
                    + params.identity_score_weight * identity_score
                    + params.wifi_context_weight * context_score
                )

            if score > best_score:
                best_score = score
                best_frame = frame
                best_delta = delta_ms
                if identity_match:
                    best_method = EnrichmentMatchMethod.TIME_IDENTITY_BEST_MATCH.value
                else:
                    best_method = EnrichmentMatchMethod.TIME_ONLY_MATCH.value

        if best_frame is None or best_score < params.match_threshold:
            return None
        return best_score, best_delta, best_frame, best_method

    @staticmethod
    def _context_score(
        row: dict[str, str],
        frame: _PcapFrame,
        protocol: ProtocolMode,
    ) -> float:
        """Protocol-specific context compatibility signal in [0, 1]."""
        if protocol == ProtocolMode.WIFI:
            row_bssid = (_first_present(row, ("bssid",)) or "").lower()
            frame_bssid = (frame.bssid or "").lower()
            if row_bssid and frame_bssid and row_bssid == frame_bssid:
                return 1.0
            return 0.0
        if protocol == ProtocolMode.BLE:
            row_name = row.get("local_name", "").lower()
            frame_name = (frame.ble_local_name or "").lower()
            if row_name and frame_name and row_name == frame_name:
                return 1.0
            return 0.0
        return 0.0

    @staticmethod
    def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        with csv_path.open("r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                return []
            for row in reader:
                if row is None:
                    continue
                rows.append({str(k).strip(): ("" if v is None else str(v).strip()) for k, v in row.items()})
        return rows
