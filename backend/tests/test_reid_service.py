from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.core.errors import ValidationError
from app.models.canonical_models import ReIdParameters, StageSuggestion
from app.modules.reid.service import ReIdService


def _write_enriched(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture()
def reid_services(services):
    dataset, sessions = services
    service = ReIdService(session_service=sessions, dataset_service=dataset)
    return dataset, sessions, service


def test_reid_requires_active_enriched_artifact(reid_services, data_root: Path) -> None:
    folder = data_root / "mission_reid_missing"
    folder.mkdir()
    _, sessions, reid = reid_services
    session = sessions.create_session("mission_reid_missing")

    with pytest.raises(ValidationError, match="active ENRICHED"):
        reid.run_reid(session.session_id, parameters=ReIdParameters())


def test_reid_writes_official_artifact_and_activates(reid_services, data_root: Path) -> None:
    folder = data_root / "mission_reid"
    folder.mkdir()
    _write_enriched(
        folder / "scan_ENRICHED.csv",
        [
            {
                "timestamp_utc": "2025-12-15T09:58:14.000Z",
                "src_mac": "aa:bb:cc:dd:ee:01",
                "enr_seq_num": 10,
                "enr_ie_fingerprint": "1:aa",
                "enr_ie_vendor_ouis": "001122",
                "enr_bssid": "aa:bb:cc:dd:ee:ff",
            },
            {
                "timestamp_utc": "2025-12-15T09:58:14.100Z",
                "src_mac": "aa:bb:cc:dd:ee:02",
                "enr_seq_num": 11,
                "enr_ie_fingerprint": "1:aa",
                "enr_ie_vendor_ouis": "001122",
                "enr_bssid": "aa:bb:cc:dd:ee:ff",
            },
        ],
    )

    _, sessions, reid = reid_services
    session = sessions.create_session("mission_reid")
    session = sessions.activate_artifact(session.session_id, "mission_reid:scan_ENRICHED.csv")

    result = reid.run_reid(session.session_id, parameters=ReIdParameters())
    assert result.output_reid_file == "scan_REID.csv"

    out = pd.read_csv(folder / "scan_REID.csv")
    assert "cluster_id" in out.columns
    assert "cluster_type" in out.columns
    assert len(out) == 2

    updated = sessions.require_session(session.session_id)
    assert updated.active_reid_artifact_id == "mission_reid:scan_REID.csv"
    assert updated.current_stage == StageSuggestion.LOCALIZATION


def test_reid_is_deterministic_for_same_input(reid_services, data_root: Path) -> None:
    folder = data_root / "mission_reid_det"
    folder.mkdir()
    _write_enriched(
        folder / "scan_ENRICHED.csv",
        [
            {
                "timestamp_utc": "2025-12-15T09:58:14.000Z",
                "src_mac": "aa:bb:cc:dd:ee:01",
                "enr_seq_num": 10,
                "enr_ie_fingerprint": "1:aa",
                "enr_ie_vendor_ouis": "001122",
                "enr_bssid": "aa:bb:cc:dd:ee:ff",
            },
            {
                "timestamp_utc": "2025-12-15T09:58:15.000Z",
                "src_mac": "cc:dd:ee:ff:00:11",
                "enr_seq_num": 999,
                "enr_ie_fingerprint": "2:bb",
                "enr_ie_vendor_ouis": "334455",
                "enr_bssid": "cc:dd:ee:ff:00:22",
            },
        ],
    )

    _, sessions, reid = reid_services
    session = sessions.create_session("mission_reid_det")
    sessions.activate_artifact(session.session_id, "mission_reid_det:scan_ENRICHED.csv")

    reid.run_reid(session.session_id, parameters=ReIdParameters())
    first = pd.read_csv(folder / "scan_REID.csv")
    reid.run_reid(session.session_id, parameters=ReIdParameters())
    second = pd.read_csv(folder / "scan_REID.csv")

    assert first["cluster_id"].tolist() == second["cluster_id"].tolist()
