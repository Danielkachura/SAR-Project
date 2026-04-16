from __future__ import annotations

import uuid

from app.core.errors import NotFoundError, ValidationError
from app.models.canonical_models import ArtifactKind, SessionState, StageSuggestion
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.storage.session_store import InMemorySessionStore


class SessionNavigationService:
    def __init__(
        self,
        dataset_service: DatasetDiscoveryService,
        session_store: InMemorySessionStore,
    ) -> None:
        self._dataset_service = dataset_service
        self._session_store = session_store

    def list_scan_folders(self):
        return self._dataset_service.list_scan_folders()

    def create_session(self, folder_id: str) -> SessionState:
        folders = self._dataset_service.list_scan_folders()
        target = next((folder for folder in folders if folder.folder_id == folder_id), None)
        if not target:
            raise NotFoundError(f"Scan folder not found: {folder_id}")

        mode = self._dataset_service.detect_mode_from_folder_name(folder_id)
        inventory = self._dataset_service.resolve_inventory(folder_id)
        warnings: list[str] = []
        if not inventory.raw_csv_files:
            warnings.append("No raw CSV files found in selected folder.")

        state = SessionState(
            session_id=str(uuid.uuid4()),
            scan_folder_id=folder_id,
            scan_folder_name=target.folder_name,
            mode=mode,
            mode_source="detected",
            current_stage=StageSuggestion.OVERVIEW,
            warnings=warnings,
        )
        self._session_store.upsert(state)
        return state

    def set_mode(self, session_id: str, mode: str) -> SessionState:
        state = self.require_session(session_id)
        if mode not in {"wifi", "ble", "unknown"}:
            raise ValidationError(f"Invalid mode: {mode}")

        updated = state.model_copy(update={"mode": mode, "mode_source": "manual"})
        self._session_store.upsert(updated)
        return updated


    def set_selected_overview_csv(self, session_id: str, csv_file: str | None) -> SessionState:
        state = self.require_session(session_id)
        updated = state.model_copy(update={"selected_overview_csv_file": csv_file})
        self._session_store.upsert(updated)
        return updated

    def require_session(self, session_id: str) -> SessionState:
        state = self._session_store.get(session_id)
        if state is None:
            raise NotFoundError(f"Session not found: {session_id}")
        return state

    def activate_artifact(self, session_id: str, artifact_id: str) -> SessionState:
        state = self.require_session(session_id)
        inventory = self._dataset_service.resolve_inventory(state.scan_folder_id)
        artifact = self._find_artifact(inventory, artifact_id)
        if artifact is None:
            raise NotFoundError(f"Artifact not found in session inventory: {artifact_id}")

        if artifact.kind == ArtifactKind.ENRICHED_CSV:
            updated = state.model_copy(
                update={
                    "active_enriched_artifact_id": artifact_id,
                    "active_reid_artifact_id": None,
                    "current_stage": StageSuggestion.REID_ENRICHMENT,
                }
            )
        elif artifact.kind == ArtifactKind.REID_CSV:
            updated = state.model_copy(
                update={
                    "active_reid_artifact_id": artifact_id,
                    "current_stage": StageSuggestion.LOCALIZATION,
                }
            )
        elif artifact.kind == ArtifactKind.RAW_CSV:
            updated = state.model_copy(update={"active_raw_csv_artifact_id": artifact_id, "current_stage": StageSuggestion.OVERVIEW})
        else:
            raise ValidationError("Only CSV artifacts can be activated in this phase.")

        self._session_store.upsert(updated)
        return updated

    @staticmethod
    def _find_artifact(inventory, artifact_id: str):
        all_artifacts = (
            inventory.raw_csv_files
            + inventory.pcap_files
            + inventory.enriched_artifacts
            + inventory.reid_artifacts
        )
        return next((item for item in all_artifacts if item.artifact_id == artifact_id), None)
