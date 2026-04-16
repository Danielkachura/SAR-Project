from __future__ import annotations

from pathlib import Path

from app.models.canonical_models import ArtifactKind


def test_inventory_classifies_artifacts(services, data_root: Path) -> None:
    folder = data_root / "run_ble"
    folder.mkdir()
    (folder / "capture.csv").write_text("a,b")
    (folder / "capture.pcap").write_text("pcap")
    (folder / "capture_ENRICHED.csv").write_text("enriched")
    (folder / "capture_REID.csv").write_text("reid")

    dataset, _ = services
    inventory = dataset.resolve_inventory("run_ble")

    assert len(inventory.raw_csv_files) == 1
    assert len(inventory.pcap_files) == 1
    assert len(inventory.enriched_artifacts) == 1
    assert len(inventory.reid_artifacts) == 1
    assert inventory.enriched_artifacts[0].kind == ArtifactKind.ENRICHED_CSV
    assert inventory.reid_artifacts[0].kind == ArtifactKind.REID_CSV
