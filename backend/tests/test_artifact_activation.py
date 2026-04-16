from __future__ import annotations

from pathlib import Path

from app.models.canonical_models import StageSuggestion


def test_activate_reid_artifact_jumps_to_localization(services, data_root: Path) -> None:
    folder = data_root / "mission_wifi"
    folder.mkdir()
    (folder / "sample_REID.csv").write_text("c1")

    _, sessions = services
    session = sessions.create_session("mission_wifi")

    activated = sessions.activate_artifact(session.session_id, "mission_wifi:sample_REID.csv")

    assert activated.active_reid_artifact_id == "mission_wifi:sample_REID.csv"
    assert activated.current_stage == StageSuggestion.LOCALIZATION
