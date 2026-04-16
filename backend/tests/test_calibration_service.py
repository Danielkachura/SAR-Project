from __future__ import annotations

from pathlib import Path

from app.models.canonical_models import CalibrationGtMode, CalibrationRunConfig


def _write_calibration_csv(path: Path) -> None:
    path.write_text(
        "timestamp,mac,rssi,latitude,longitude\n"
        "1,AA:AA:AA:AA:AA:AA,-40,37.00000,-122.00000\n"
        "2,AA:AA:AA:AA:AA:AA,-43,37.00003,-122.00000\n"
        "3,AA:AA:AA:AA:AA:AA,-47,37.00006,-122.00000\n"
        "4,AA:AA:AA:AA:AA:AA,-51,37.00009,-122.00000\n"
        "5,BB:BB:BB:BB:BB:BB,-60,37.00100,-122.00100\n",
        encoding="utf-8",
    )


def test_candidate_mac_listing(calibration_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    _write_calibration_csv(folder / "calib.csv")

    _, sessions, calibration = calibration_services
    session = sessions.create_session("mission_wifi")

    candidates = calibration.list_mac_candidates(session_id=session.session_id, selected_csv_file="calib.csv")

    assert candidates.selected_csv_file == "calib.csv"
    assert [item.mac for item in candidates.candidates] == ["AA:AA:AA:AA:AA:AA", "BB:BB:BB:BB:BB:BB"]
    assert [item.sample_count for item in candidates.candidates] == [4, 1]


def test_gt_modes_work_and_scatter_payload_generated(calibration_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    _write_calibration_csv(folder / "calib.csv")

    _, sessions, calibration = calibration_services
    session = sessions.create_session("mission_wifi")

    for mode in (CalibrationGtMode.FIRST_SAMPLE, CalibrationGtMode.MEAN_FIRST_K, CalibrationGtMode.MANUAL_MAP_CLICK):
        payload = calibration.run_calibration(
            session_id=session.session_id,
            selected_csv_file="calib.csv",
            selected_mac="AA:AA:AA:AA:AA:AA",
            config=CalibrationRunConfig(
                gt_mode=mode,
                gt_first_k=2,
                enable_ransac=True,
                ransac_residual_threshold_db=4,
                ransac_iterations=100,
                distance_floor_m=1,
                manual_gt_latitude=37.0 if mode == CalibrationGtMode.MANUAL_MAP_CLICK else None,
                manual_gt_longitude=-122.0 if mode == CalibrationGtMode.MANUAL_MAP_CLICK else None,
            ),
        )

        assert payload.selected_csv_file == "calib.csv"
        assert payload.selected_mac == "AA:AA:AA:AA:AA:AA"
        assert len(payload.scatter_points) >= 2
        assert all(point.log10_distance >= 0 for point in payload.scatter_points)
        assert payload.parameters.path_loss_n > 0
        assert payload.parameters.sigma >= 0
        assert payload.diagnostics.sample_count == len(payload.scatter_points)


def test_ransac_on_off_behavior_covered(calibration_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    (folder / "calib.csv").write_text(
        "timestamp,mac,rssi,latitude,longitude\n"
        "1,AA,-40,37.00000,-122.00000\n"
        "2,AA,-44,37.00003,-122.00000\n"
        "3,AA,-48,37.00006,-122.00000\n"
        "4,AA,-52,37.00009,-122.00000\n"
        "5,AA,-20,37.00012,-122.00000\n",
        encoding="utf-8",
    )

    _, sessions, calibration = calibration_services
    session = sessions.create_session("mission_wifi")

    without_ransac = calibration.run_calibration(
        session_id=session.session_id,
        selected_csv_file="calib.csv",
        selected_mac="AA",
        config=CalibrationRunConfig(enable_ransac=False),
    )
    with_ransac = calibration.run_calibration(
        session_id=session.session_id,
        selected_csv_file="calib.csv",
        selected_mac="AA",
        config=CalibrationRunConfig(enable_ransac=True, ransac_iterations=200, ransac_residual_threshold_db=3),
    )

    assert without_ransac.diagnostics.sample_count == with_ransac.diagnostics.sample_count
    assert with_ransac.diagnostics.inlier_count <= without_ransac.diagnostics.inlier_count


def test_weak_fit_warns_but_approval_and_fallback_and_session_save_work(calibration_services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    (folder / "calib.csv").write_text(
        "timestamp,mac,rssi,latitude,longitude\n"
        "1,AA,-70,37.00000,-122.00000\n"
        "2,AA,-45,37.00001,-122.00001\n"
        "3,AA,-80,37.00002,-122.00002\n"
        "4,AA,-50,37.00003,-122.00003\n",
        encoding="utf-8",
    )

    _, sessions, calibration = calibration_services
    session = sessions.create_session("mission_wifi")

    result = calibration.run_calibration(
        session_id=session.session_id,
        selected_csv_file="calib.csv",
        selected_mac="AA",
        config=CalibrationRunConfig(enable_ransac=False, gt_mode=CalibrationGtMode.FIRST_SAMPLE),
    )

    assert result.warnings

    saved = calibration.approve_derived_calibration(session_id=session.session_id, result=result)
    assert saved.parameter_source == "derived"
    assert saved.approved is True

    fallback = calibration.select_fallback_preset(
        session_id=session.session_id,
        selected_csv_file="calib.csv",
        selected_mac="AA",
        preset_name="urban",
    )
    assert fallback.preset.name == "urban"

    updated_session = sessions.require_session(session.session_id)
    assert updated_session.active_calibration is not None
    assert updated_session.active_calibration.parameter_source == "fallback"
    assert updated_session.active_calibration.selection.selected_csv_file == "calib.csv"
