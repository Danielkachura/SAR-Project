from __future__ import annotations

from pathlib import Path


def test_list_scan_folders_returns_subdirectories_only(services, data_root: Path) -> None:
    (data_root / "wifi_run_1").mkdir()
    (data_root / "ble_run_2").mkdir()
    (data_root / "README.txt").write_text("not a folder")

    dataset, _ = services
    folders = dataset.list_scan_folders()

    assert [folder.folder_id for folder in folders] == ["ble_run_2", "wifi_run_1"]
