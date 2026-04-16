from __future__ import annotations

from pathlib import Path

from app.models.canonical_models import ProtocolMode


def test_create_session_detects_mode_and_sets_warning_without_raw_csv(services, data_root: Path) -> None:
    (data_root / "mission_wifi_001").mkdir()

    _, sessions = services
    state = sessions.create_session("mission_wifi_001")

    assert state.mode == ProtocolMode.WIFI
    assert state.mode_source == "detected"
    assert state.warnings == ["No raw CSV files found in selected folder."]


def test_manual_mode_override_updates_source(services, data_root: Path) -> None:
    (data_root / "mission_unknown_001").mkdir()

    _, sessions = services
    state = sessions.create_session("mission_unknown_001")
    updated = sessions.set_mode(state.session_id, "ble")

    assert updated.mode == ProtocolMode.BLE
    assert updated.mode_source == "manual"


def test_create_session_detects_scan_prefix_as_wifi(services, data_root: Path) -> None:
    (data_root / "Scan_2026_01_19").mkdir()

    _, sessions = services
    state = sessions.create_session("Scan_2026_01_19")

    assert state.mode == ProtocolMode.WIFI
