"""Tests for MOD-007 EnrichmentService."""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.models.canonical_models import EnrichmentMatchMethod, EnrichmentParameters, ProtocolMode
from app.modules.enrichment.service import EnrichmentService


# ---------------------------------------------------------------------------
# Minimal pcap binary builders
# ---------------------------------------------------------------------------

def _pcap_global_header(link_type: int) -> bytes:
    """Write a little-endian pcap global header."""
    return struct.pack(
        "<IHHiIII",
        0xA1B2C3D4,  # magic (microseconds)
        2, 4,          # version 2.4
        0,             # timezone
        0,             # accuracy
        65535,         # snaplen
        link_type,
    )


def _pcap_packet(ts_sec: int, ts_usec: int, data: bytes) -> bytes:
    return struct.pack("<IIII", ts_sec, ts_usec, len(data), len(data)) + data


def _build_wifi_pcap(packets: list[tuple[int, int, bytes]]) -> bytes:
    """Build a pcap with link type 105 (802.11)."""
    hdr = _pcap_global_header(105)
    return hdr + b"".join(_pcap_packet(s, u, d) for s, u, d in packets)


def _build_ble_pcap(packets: list[tuple[int, int, bytes]]) -> bytes:
    """Build a pcap with link type 251 (BLE LE LL)."""
    hdr = _pcap_global_header(251)
    return hdr + b"".join(_pcap_packet(s, u, d) for s, u, d in packets)


def _wifi_management_frame(src_mac: bytes, dst_mac: bytes, bssid: bytes) -> bytes:
    """Minimal 802.11 probe-request frame (subtype 4, no IEs)."""
    fc = (0 << 0) | (0 << 2) | (4 << 4)  # version=0, type=management, subtype=probe_request
    return struct.pack("<HH", fc, 0) + dst_mac + src_mac + bssid + struct.pack("<H", 0)


def _ble_adv_ind_frame(addr_bytes: bytes, local_name: str = "") -> bytes:
    """Minimal BLE ADV_IND PDU."""
    adv_data = b""
    if local_name:
        name_enc = local_name.encode("utf-8")
        adv_data = bytes([len(name_enc) + 1, 0x09]) + name_enc
    payload_len = 6 + len(adv_data)
    pdu_hdr = struct.pack("<H", (0x00 & 0xF) | (payload_len << 8))
    return pdu_hdr + addr_bytes + adv_data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def enrichment_services(services):
    dataset, sessions = services
    enrichment = EnrichmentService(session_service=sessions, dataset_service=dataset)
    return dataset, sessions, enrichment


# ---------------------------------------------------------------------------
# PCAP parsing tests
# ---------------------------------------------------------------------------

def test_parse_wifi_pcap_extracts_macs(enrichment_services, data_root: Path) -> None:
    folder = data_root / "wifi_scan"
    folder.mkdir()

    src = bytes.fromhex("aabbccddeeff")
    dst = bytes.fromhex("112233445566")
    bssid = bytes.fromhex("ffeeddccbbaa")
    frame = _wifi_management_frame(src, dst, bssid)
    pcap = _build_wifi_pcap([(1000, 0, frame)])
    (folder / "scan.pcap").write_bytes(pcap)

    from app.modules.enrichment.service import _parse_pcap_file
    link_type, frames = _parse_pcap_file(folder / "scan.pcap")
    assert link_type == 105
    assert len(frames) == 1
    assert frames[0].src_mac == "aa:bb:cc:dd:ee:ff"
    assert frames[0].dst_mac == "11:22:33:44:55:66"
    assert frames[0].bssid == "ff:ee:dd:cc:bb:aa"
    assert frames[0].frame_type == "management"
    assert frames[0].timestamp_ms == pytest.approx(1000 * 1000.0)


def test_parse_ble_pcap_extracts_address_and_name(enrichment_services, data_root: Path) -> None:
    folder = data_root / "ble_scan"
    folder.mkdir()

    addr = bytes.fromhex("aabbccddeeff")
    frame = _ble_adv_ind_frame(addr, local_name="MyDevice")
    pcap = _build_ble_pcap([(2000, 0, frame)])
    (folder / "scan.pcap").write_bytes(pcap)

    from app.modules.enrichment.service import _parse_pcap_file
    _, frames = _parse_pcap_file(folder / "scan.pcap")
    assert len(frames) == 1
    assert frames[0].ble_advertiser_addr == "aa:bb:cc:dd:ee:ff"
    assert frames[0].ble_local_name == "MyDevice"
    assert frames[0].ble_event_type == "ADV_IND"


def test_invalid_pcap_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pcap"
    bad.write_bytes(b"\x00" * 24)

    from app.modules.enrichment.service import _parse_pcap_file
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError, match="valid pcap"):
        _parse_pcap_file(bad)


# ---------------------------------------------------------------------------
# Enrichment service — full flow tests
# ---------------------------------------------------------------------------

def _make_wifi_folder(folder: Path) -> tuple[str, str]:
    """Create a folder with one CSV and one PCAP, return (csv_name, pcap_name)."""
    folder.mkdir(parents=True, exist_ok=True)

    # CSV: one row at t=1000s with MAC matching the PCAP frame
    csv_path = folder / "scan.csv"
    csv_path.write_text(
        "timestamp,mac,rssi\n"
        "1000,aa:bb:cc:dd:ee:ff,-55\n",
        encoding="utf-8",
    )

    # PCAP: one Wi-Fi management frame at t=1000s+10ms
    src = bytes.fromhex("aabbccddeeff")
    dst = bytes.fromhex("112233445566")
    bssid = bytes.fromhex("ffeeddccbbaa")
    frame = _wifi_management_frame(src, dst, bssid)
    pcap_bytes = _build_wifi_pcap([(1000, 10_000, frame)])  # 10_000 µs = 10ms offset
    (folder / "scan.pcap").write_bytes(pcap_bytes)

    return "scan.csv", "scan.pcap"


def test_enrichment_run_writes_enriched_artifact(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    csv_name, pcap_name = _make_wifi_folder(folder)

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_wifi")

    params = EnrichmentParameters()
    result = enrichment.run_enrichment(
        session_id=session.session_id,
        selected_csv_file=csv_name,
        selected_pcap_file=pcap_name,
        parameters=params,
    )

    assert result.output_enriched_file == "scan_ENRICHED.csv"
    assert result.diagnostics.total_rows == 1
    assert result.diagnostics.matched_rows == 1
    assert result.diagnostics.match_rate == 1.0

    enriched_path = folder / "scan_ENRICHED.csv"
    assert enriched_path.exists()

    import csv as _csv
    rows = list(_csv.DictReader(enriched_path.open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["match_found"] == "true"
    assert rows[0]["match_method"] == EnrichmentMatchMethod.TIME_IDENTITY_BEST_MATCH.value
    assert rows[0]["enr_bssid"] == "ff:ee:dd:cc:bb:aa"
    assert rows[0]["mac"] == "aa:bb:cc:dd:ee:ff"


def test_enrichment_overwrite_is_silent(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    csv_name, pcap_name = _make_wifi_folder(folder)

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_wifi")
    params = EnrichmentParameters()

    enrichment.run_enrichment(session_id=session.session_id, selected_csv_file=csv_name, selected_pcap_file=pcap_name, parameters=params)
    # Second run should overwrite without error
    result2 = enrichment.run_enrichment(session_id=session.session_id, selected_csv_file=csv_name, selected_pcap_file=pcap_name, parameters=params)
    assert result2.output_enriched_file == "scan_ENRICHED.csv"


def test_row_with_no_timestamp_gets_no_match(enrichment_services, data_root: Path) -> None:
    folder = data_root / "notimestamp_wifi"
    folder.mkdir()

    csv_path = folder / "scan.csv"
    csv_path.write_text("mac,rssi\naabbccddee00,-60\n", encoding="utf-8")

    src = bytes.fromhex("aabbccddee00")
    dst = b"\x00" * 6
    bssid = b"\x00" * 6
    frame = _wifi_management_frame(src, dst, bssid)
    pcap_bytes = _build_wifi_pcap([(1000, 0, frame)])
    (folder / "scan.pcap").write_bytes(pcap_bytes)

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("notimestamp_wifi")
    params = EnrichmentParameters()

    result = enrichment.run_enrichment(
        session_id=session.session_id,
        selected_csv_file="scan.csv",
        selected_pcap_file="scan.pcap",
        parameters=params,
    )
    assert result.diagnostics.matched_rows == 0
    assert result.diagnostics.match_rate == 0.0

    import csv as _csv
    rows = list(_csv.DictReader((folder / "scan_ENRICHED.csv").open(encoding="utf-8")))
    assert rows[0]["match_found"] == "false"
    assert rows[0]["match_method"] == EnrichmentMatchMethod.NO_MATCH.value


def test_enrichment_ble_match(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_ble"
    folder.mkdir()

    csv_path = folder / "scan.csv"
    csv_path.write_text(
        "timestamp,mac,rssi\n"
        "500,aa:bb:cc:dd:ee:ff,-70\n",
        encoding="utf-8",
    )

    addr = bytes.fromhex("aabbccddeeff")
    frame = _ble_adv_ind_frame(addr, local_name="TestDevice")
    pcap_bytes = _build_ble_pcap([(500, 50_000, frame)])  # 50ms offset
    (folder / "scan.pcap").write_bytes(pcap_bytes)

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_ble")
    params = EnrichmentParameters()

    result = enrichment.run_enrichment(
        session_id=session.session_id,
        selected_csv_file="scan.csv",
        selected_pcap_file="scan.pcap",
        parameters=params,
    )
    assert result.diagnostics.matched_rows == 1

    import csv as _csv
    rows = list(_csv.DictReader((folder / "scan_ENRICHED.csv").open(encoding="utf-8")))
    assert rows[0]["enr_ble_advertiser_addr"] == "aa:bb:cc:dd:ee:ff"
    assert rows[0]["enr_ble_local_name"] == "TestDevice"
    assert rows[0]["enr_ble_event_type"] == "ADV_IND"


def test_unknown_csv_raises_validation(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    src = bytes.fromhex("aabbccddeeff")
    pcap_bytes = _build_wifi_pcap([(1, 0, _wifi_management_frame(src, b"\x00" * 6, b"\x00" * 6))])
    (folder / "scan.pcap").write_bytes(pcap_bytes)

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_wifi")

    from app.core.errors import ValidationError
    with pytest.raises(ValidationError, match="not available"):
        enrichment.run_enrichment(session_id=session.session_id, selected_csv_file="missing.csv", selected_pcap_file="scan.pcap", parameters=EnrichmentParameters())


def test_enriched_schema_contains_all_ble_cols(enrichment_services, data_root: Path) -> None:
    """BLE enrichment fields must exist in schema even when no BLE frames matched."""
    folder = data_root / "mission_wifi2"
    csv_name, pcap_name = _make_wifi_folder(folder)

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_wifi2")

    enrichment.run_enrichment(session_id=session.session_id, selected_csv_file=csv_name, selected_pcap_file=pcap_name, parameters=EnrichmentParameters())

    import csv as _csv
    from app.modules.enrichment.service import _BLE_COLS
    rows = list(_csv.DictReader((folder / "scan_ENRICHED.csv").open(encoding="utf-8")))
    for col in _BLE_COLS:
        assert col in rows[0], f"Missing BLE column: {col}"
