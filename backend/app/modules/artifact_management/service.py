from __future__ import annotations

from app.models.canonical_models import ArtifactKind


class ArtifactManagementService:
    """Artifact helpers for classification and official artifact naming lifecycle."""

    @staticmethod
    def is_official_artifact(file_name: str) -> bool:
        lower = file_name.lower()
        return lower.endswith("_enriched.csv") or lower.endswith("_reid.csv")

    @staticmethod
    def classify_file_kind(file_name: str) -> ArtifactKind | None:
        lower = file_name.lower()
        if lower.endswith("_enriched.csv"):
            return ArtifactKind.ENRICHED_CSV
        if lower.endswith("_reid.csv"):
            return ArtifactKind.REID_CSV
        if lower.endswith(".csv"):
            return ArtifactKind.RAW_CSV
        if lower.endswith(".pcap") or lower.endswith(".pcapng"):
            return ArtifactKind.PCAP
        return None

    @staticmethod
    def build_official_enriched_filename(raw_csv_file: str) -> str:
        lower = raw_csv_file.lower()
        if not lower.endswith(".csv"):
            raise ValueError(f"Raw CSV file must end with .csv: {raw_csv_file}")
        return f"{raw_csv_file[:-4]}_ENRICHED.csv"
