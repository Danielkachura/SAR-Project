from __future__ import annotations

from pathlib import Path


def _write_sample_csv(path: Path) -> None:
    path.write_text(
        "timestamp,mac,rssi,vendor,frame_type,latitude,longitude,cluster_id\n"
        "1,AA:AA:AA:AA:AA:01,-70,Acme,probe,-37.1000,144.9000,c1\n"
        "2,AA:AA:AA:AA:AA:02,-60,Acme,beacon,-37.1001,144.9001,c2\n"
        "3,AA:AA:AA:AA:AA:01,-80,Zen,probe,-37.1002,144.9002,c1\n",
        encoding="utf-8",
    )


def test_overview_no_csv_selected_returns_context_only(overview_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    _write_sample_csv(folder / "scan.csv")

    _, sessions, overview = overview_services
    session = sessions.create_session("mission_wifi")

    payload = overview.build_overview(session.session_id, selected_csv_file=None, preview_limit=50)

    assert payload.context.selected_csv_file is None
    assert payload.summary_stats is None
    assert payload.preview is None
    assert payload.charts is None
    assert payload.spatial is None
    assert payload.device_analysis is None


def test_overview_summary_and_preview_for_valid_csv(overview_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    _write_sample_csv(folder / "scan.csv")

    _, sessions, overview = overview_services
    session = sessions.create_session("mission_wifi")

    payload = overview.build_overview(session.session_id, selected_csv_file="scan.csv", preview_limit=2)

    assert payload.summary_stats is not None
    assert payload.summary_stats.total_rows == 3
    assert payload.summary_stats.unique_devices == 2
    assert payload.summary_stats.average_rssi == -70.0

    assert payload.preview is not None
    assert payload.preview.total_rows == 3
    assert len(payload.preview.rows) == 2
    assert payload.preview.truncated is True


def test_overview_handles_partial_rows_gracefully(overview_services, data_root: Path) -> None:
    folder = data_root / "mission_ble"
    folder.mkdir()
    (folder / "partial.csv").write_text(
        "timestamp,device_address,rssi,latitude,longitude\n"
        "1,,,-37.1,144.9\n"
        "2,AA:BB,-55,,\n",
        encoding="utf-8",
    )

    _, sessions, overview = overview_services
    session = sessions.create_session("mission_ble")

    payload = overview.build_overview(session.session_id, selected_csv_file="partial.csv", preview_limit=50)

    assert payload.summary_stats is not None
    assert payload.summary_stats.total_rows == 2
    assert payload.summary_stats.unique_devices == 1
    assert payload.spatial is not None
    assert len(payload.spatial.points) == 1


def test_overview_does_not_trigger_heavy_processing_state(overview_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    _write_sample_csv(folder / "scan.csv")

    _, sessions, overview = overview_services
    session = sessions.create_session("mission_wifi")

    overview.build_overview(session.session_id, selected_csv_file="scan.csv", preview_limit=50)
    updated = sessions.require_session(session.session_id)

    assert updated.active_enriched_artifact_id is None
    assert updated.active_reid_artifact_id is None
    assert updated.current_stage == session.current_stage
