"""Tests for MOD-007 EnrichmentService (scapy + pandas merge_asof)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.core.errors import ValidationError
from app.models.canonical_models import EnrichmentParameters
from app.modules.enrichment.service import EnrichmentService


def _write_wifi_pcap(path: Path, frames: list[tuple[float, str, str, str, str]]) -> None:
    """frames: list of (epoch_ts, src_mac, dst_mac, bssid, ssid)."""
    from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap, wrpcap

    pkts = []
    for ts, src, dst, bssid, ssid in frames:
        pkt = (
            RadioTap()
            / Dot11(type=0, subtype=8, addr1=dst, addr2=src, addr3=bssid)
            / Dot11Beacon(cap="ESS")
            / Dot11Elt(ID=0, info=ssid.encode("utf-8"))
            / Dot11Elt(ID=1, info=b"\x82\x84\x8b\x96")
        )
        pkt.time = ts
        pkts.append(pkt)
    wrpcap(str(path), pkts)


@pytest.fixture()
def enrichment_services(services):
    dataset, sessions = services
    enrichment = EnrichmentService(session_service=sessions, dataset_service=dataset)
    return dataset, sessions, enrichment


def _make_folder(folder: Path, csv_text: str, pcap_frames: list[tuple[float, str, str, str, str]]) -> tuple[str, str]:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "scan.csv").write_text(csv_text, encoding="utf-8")
    _write_wifi_pcap(folder / "scan.pcap", pcap_frames)
    return "scan.csv", "scan.pcap"


def test_enrichment_writes_artifact_and_matches_by_mac(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    csv_text = (
        "timestamp_utc,frame_type,src_mac,bssid,ssid,rssi_dbm,gps_lat,gps_lon\n"
        "2025-12-15T09:58:14Z,beacon,aa:bb:cc:dd:ee:ff,aa:bb:cc:dd:ee:ff,Liat,-87,31.289,34.812\n"
    )
    csv_name, pcap_name = _make_folder(
        folder,
        csv_text,
        [(pd.Timestamp("2025-12-15T09:58:14.010Z").timestamp(),
          "aa:bb:cc:dd:ee:ff", "ff:ff:ff:ff:ff:ff", "aa:bb:cc:dd:ee:ff", "Liat")],
    )

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_wifi")
    result = enrichment.run_enrichment(
        session_id=session.session_id,
        selected_csv_file=csv_name,
        selected_pcap_file=pcap_name,
        parameters=EnrichmentParameters(),
    )

    assert result.output_enriched_file == "scan_ENRICHED.csv"
    assert result.diagnostics.total_rows == 1
    assert result.diagnostics.matched_rows == 1
    assert result.diagnostics.unmatched_rows == 0

    out = pd.read_csv(folder / "scan_ENRICHED.csv")
    # Columns from PCAP have been merged in
    assert "frame_len" in out.columns
    assert "ie_ids" in out.columns
    assert "ie_fingerprint" in out.columns
    assert bool(out.loc[0, "match_found"]) is True


def test_enrichment_no_match_when_mac_differs(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_nomatch"
    csv_text = (
        "timestamp_utc,src_mac,rssi_dbm\n"
        "2025-12-15T09:58:14Z,aa:bb:cc:dd:ee:ff,-50\n"
    )
    csv_name, pcap_name = _make_folder(
        folder,
        csv_text,
        [(pd.Timestamp("2025-12-15T09:58:14.000Z").timestamp(),
          "11:22:33:44:55:66", "ff:ff:ff:ff:ff:ff", "11:22:33:44:55:66", "Other")],
    )

    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_nomatch")
    result = enrichment.run_enrichment(
        session_id=session.session_id,
        selected_csv_file=csv_name,
        selected_pcap_file=pcap_name,
        parameters=EnrichmentParameters(),
    )
    assert result.diagnostics.matched_rows == 0
    assert result.diagnostics.match_rate == 0.0


def test_enrichment_overwrite_is_silent(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_overwrite"
    csv_text = (
        "timestamp_utc,src_mac\n"
        "2025-12-15T09:58:14Z,aa:bb:cc:dd:ee:ff\n"
    )
    csv_name, pcap_name = _make_folder(
        folder,
        csv_text,
        [(pd.Timestamp("2025-12-15T09:58:14Z").timestamp(),
          "aa:bb:cc:dd:ee:ff", "ff:ff:ff:ff:ff:ff", "aa:bb:cc:dd:ee:ff", "X")],
    )
    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_overwrite")
    enrichment.run_enrichment(
        session_id=session.session_id, selected_csv_file=csv_name,
        selected_pcap_file=pcap_name, parameters=EnrichmentParameters(),
    )
    result2 = enrichment.run_enrichment(
        session_id=session.session_id, selected_csv_file=csv_name,
        selected_pcap_file=pcap_name, parameters=EnrichmentParameters(),
    )
    assert result2.output_enriched_file == "scan_ENRICHED.csv"


def test_enrichment_missing_timestamp_column_raises(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_no_ts"
    csv_text = "src_mac,rssi\naa:bb:cc:dd:ee:ff,-60\n"
    csv_name, pcap_name = _make_folder(
        folder,
        csv_text,
        [(pd.Timestamp("2025-12-15T09:58:14Z").timestamp(),
          "aa:bb:cc:dd:ee:ff", "ff:ff:ff:ff:ff:ff", "aa:bb:cc:dd:ee:ff", "X")],
    )
    _, sessions, enrichment = enrichment_services
    session = sessions.create_session("mission_no_ts")
    with pytest.raises(ValidationError, match="timestamp_utc"):
        enrichment.run_enrichment(
            session_id=session.session_id, selected_csv_file=csv_name,
            selected_pcap_file=pcap_name, parameters=EnrichmentParameters(),
        )


def test_resolve_matching_pcap_by_basename(enrichment_services, data_root: Path) -> None:
    folder = data_root / "mission_resolve"
    csv_text = "timestamp_utc,src_mac\n2025-12-15T09:58:14Z,aa:bb:cc:dd:ee:ff\n"
    _make_folder(folder, csv_text, [
        (pd.Timestamp("2025-12-15T09:58:14Z").timestamp(),
         "aa:bb:cc:dd:ee:ff", "ff:ff:ff:ff:ff:ff", "aa:bb:cc:dd:ee:ff", "X")
    ])
    _, _, enrichment = enrichment_services
    assert enrichment.resolve_matching_pcap("mission_resolve", "scan.csv") == "scan.pcap"

    with pytest.raises(ValidationError, match="No matching PCAP"):
        enrichment.resolve_matching_pcap("mission_resolve", "ghost.csv")
