from __future__ import annotations

import csv
from pathlib import Path

import pytest
from scapy.all import Dot11, Dot11Elt, Dot11ProbeReq, RadioTap, wrpcap  # type: ignore

from app.models.canonical_models import EnrichmentRunConfig, MatchMethod


def _write_wifi_pcap(path: Path) -> None:
    packet = (
        RadioTap()
        / Dot11(type=0, subtype=4, addr1="ff:ff:ff:ff:ff:ff", addr2="AA:BB:CC:11:22:33", addr3="AA:BB:CC:11:22:33", SC=0x1230)
        / Dot11ProbeReq()
        / Dot11Elt(ID=0, info=b"test-ssid")
        / Dot11Elt(ID=221, info=b"\xAA\xBB\xCC\x01")
    )
    packet.time = 1000.0
    wrpcap(str(path), [packet])


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_enrichment_requires_matching_pcap(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    (folder / "scan.csv").write_text("timestamp_ms,mac\n1000000,AA:BB:CC:11:22:33\n", encoding="utf-8")

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_wifi")

    with pytest.raises(Exception, match="Matching PCAP"):
        enrichment.run_enrichment(
            session_id=session.session_id,
            selected_csv_file="scan.csv",
            config=EnrichmentRunConfig(),
        )


def test_enrichment_generates_official_artifact_and_preserves_rows(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    (folder / "scan.csv").write_text(
        "timestamp_ms,mac,bssid,channel,existing_field\n"
        "1000000,AA:BB:CC:11:22:33,AA:BB:CC:11:22:33,1,keep-me\n"
        "3000000,11:22:33:44:55:66,11:22:33:44:55:66,6,keep-too\n",
        encoding="utf-8",
    )
    _write_wifi_pcap(folder / "scan.pcap")
    (folder / "scan_ENRICHED.csv").write_text("old,data\n", encoding="utf-8")

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_wifi")

    result = enrichment.run_enrichment(
        session_id=session.session_id,
        selected_csv_file="scan.csv",
        config=EnrichmentRunConfig(),
    )

    assert result.output_file_name == "scan_ENRICHED.csv"
    assert result.total_rows == 2
    assert result.matched_rows == 1
    assert result.quality_stats.matched_row_ratio == 0.5
    assert result.active_enriched_artifact_id == "mission_wifi:scan_ENRICHED.csv"

    output_path = folder / "scan_ENRICHED.csv"
    rows = _read_rows(output_path)
    assert len(rows) == 2

    # original columns preserved
    assert rows[0]["existing_field"] == "keep-me"
    assert rows[1]["existing_field"] == "keep-too"

    # diagnostics columns always exist
    for row in rows:
        assert "match_found" in row
        assert "match_delta_ms" in row
        assert "match_score" in row
        assert "match_method" in row

    # one matched row and one preserved no-match row
    assert rows[0]["match_found"] == "true"
    assert rows[0]["match_method"] in {
        MatchMethod.TIME_IDENTITY_BEST_MATCH.value,
        MatchMethod.TIME_ONLY_MATCH.value,
    }
    assert rows[1]["match_found"] == "false"
    assert rows[1]["match_method"] == MatchMethod.NO_MATCH.value

    # BLE schema columns must exist even for Wi-Fi runs
    assert "pcap_ble_adv_address" in rows[0]
    assert "pcap_ble_manufacturer_digest" in rows[0]
    assert "pcap_ble_service_uuid_digest" in rows[0]

    # overwrite behavior (old file replaced with enriched schema)
    header = output_path.read_text(encoding="utf-8").splitlines()[0]
    assert "old" not in header
