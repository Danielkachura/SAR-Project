from __future__ import annotations

from pathlib import Path

from app.core.errors import NotFoundError
from app.models.canonical_models import (
    ArtifactKind,
    ArtifactRecord,
    FolderInventory,
    ProtocolMode,
    ScanFolder,
    SessionState,
    StageJumpSuggestion,
    StageSuggestion,
)
from app.storage.data_paths import DataPathResolver


class DatasetDiscoveryService:
    def __init__(self, path_resolver: DataPathResolver) -> None:
        self._paths = path_resolver

    def list_scan_folders(self) -> list[ScanFolder]:
        data_dir = self._paths.ensure_data_dir()
        folders = [
            ScanFolder(folder_id=entry.name, folder_name=entry.name, path=str(entry))
            for entry in sorted(data_dir.iterdir())
            if entry.is_dir()
        ]
        return folders

    def detect_mode_from_folder_name(self, folder_name: str) -> ProtocolMode:
        name = folder_name.lower()
        if "wifi" in name or "wi-fi" in name:
            return ProtocolMode.WIFI
        if "ble" in name:
            return ProtocolMode.BLE
        # TODO(spec): define exhaustive mode detection rules when naming convention is finalized.
        return ProtocolMode.UNKNOWN

    def resolve_inventory(self, folder_id: str) -> FolderInventory:
        folder_path = self._paths.folder_path(folder_id)
        if not folder_path.exists() or not folder_path.is_dir():
            raise NotFoundError(f"Scan folder not found: {folder_id}")

        raw_csv_files: list[ArtifactRecord] = []
        pcap_files: list[ArtifactRecord] = []
        enriched_artifacts: list[ArtifactRecord] = []
        reid_artifacts: list[ArtifactRecord] = []

        for file_path in sorted(folder_path.iterdir()):
            if not file_path.is_file():
                continue

            file_name = file_path.name
            lower_name = file_name.lower()
            artifact_id = f"{folder_id}:{file_name}"

            if lower_name.endswith("_enriched.csv"):
                enriched_artifacts.append(
                    ArtifactRecord(
                        artifact_id=artifact_id,
                        file_name=file_name,
                        kind=ArtifactKind.ENRICHED_CSV,
                        base_name=file_name[:-13],
                        path=str(file_path),
                        is_official=True,
                    )
                )
            elif lower_name.endswith("_reid.csv"):
                reid_artifacts.append(
                    ArtifactRecord(
                        artifact_id=artifact_id,
                        file_name=file_name,
                        kind=ArtifactKind.REID_CSV,
                        base_name=file_name[:-9],
                        path=str(file_path),
                        is_official=True,
                    )
                )
            elif lower_name.endswith(".csv"):
                raw_csv_files.append(
                    ArtifactRecord(
                        artifact_id=artifact_id,
                        file_name=file_name,
                        kind=ArtifactKind.RAW_CSV,
                        base_name=file_name[:-4],
                        path=str(file_path),
                    )
                )
            elif lower_name.endswith(".pcap") or lower_name.endswith(".pcapng"):
                stem = Path(file_name).stem
                pcap_files.append(
                    ArtifactRecord(
                        artifact_id=artifact_id,
                        file_name=file_name,
                        kind=ArtifactKind.PCAP,
                        base_name=stem,
                        path=str(file_path),
                    )
                )

        return FolderInventory(
            folder_id=folder_id,
            raw_csv_files=raw_csv_files,
            pcap_files=pcap_files,
            enriched_artifacts=enriched_artifacts,
            reid_artifacts=reid_artifacts,
        )


    def resolve_csv_path(self, folder_id: str, file_name: str) -> Path:
        return self._paths.folder_path(folder_id) / file_name

    def suggest_stage_jump(self, session: SessionState, inventory: FolderInventory) -> StageJumpSuggestion:
        if session.active_reid_artifact_id:
            return StageJumpSuggestion(
                suggested_stage=StageSuggestion.LOCALIZATION,
                reason="Active REID artifact selected; continue at Localization.",
            )
        if session.active_enriched_artifact_id:
            return StageJumpSuggestion(
                suggested_stage=StageSuggestion.REID_ENRICHMENT,
                reason="Active ENRICHED artifact selected; continue at Re-ID & Enrichment.",
            )
        if inventory.reid_artifacts:
            return StageJumpSuggestion(
                suggested_stage=StageSuggestion.LOCALIZATION,
                reason="REID artifact exists and can be activated.",
            )
        if inventory.enriched_artifacts:
            return StageJumpSuggestion(
                suggested_stage=StageSuggestion.REID_ENRICHMENT,
                reason="ENRICHED artifact exists and can be activated.",
            )
        return StageJumpSuggestion(
            suggested_stage=StageSuggestion.OVERVIEW,
            reason="No official artifacts active; start from Overview.",
        )
