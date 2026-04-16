from __future__ import annotations

from pathlib import Path

from app.models.canonical_models import StageSuggestion


def test_stage_jump_suggests_enrichment_when_enriched_exists(services, data_root: Path) -> None:
    folder = data_root / "mission_ble"
    folder.mkdir()
    (folder / "sample_ENRICHED.csv").write_text("x")

    dataset, sessions = services
    session = sessions.create_session("mission_ble")
    inventory = dataset.resolve_inventory("mission_ble")

    suggestion = dataset.suggest_stage_jump(session=session, inventory=inventory)

    assert suggestion.suggested_stage == StageSuggestion.REID_ENRICHMENT
