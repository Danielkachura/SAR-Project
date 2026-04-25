"""MOD-007 Enrichment — CSV+PCAP correlator (scapy + pandas merge_asof).

Ported from the legacy `reid.pipeline.enrich_csv_with_pcap` so the output
matches what the previous ground station produced.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from app.core.errors import NotFoundError, ValidationError
from app.models.canonical_models import (
    EnrichmentDiagnostics,
    EnrichmentParameters,
    EnrichmentRunPayload,
    ProtocolMode,
)
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.session_navigation.service import SessionNavigationService

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)


# ---------------------------------------------------------------------------
# PCAP feature extraction (scapy)
# ---------------------------------------------------------------------------

_IE_KEEP_IDS = {1, 50, 45, 61, 127, 191, 192, 221}

_PCAP_COLUMNS = [
    "timestamp_utc",
    "src_mac",
    "dst_mac",
    "bssid",
    "seq_ctl",
    "frame_len",
    "ie_ids",
    "ie_fingerprint",
    "ie_vendor_ouis",
    "ssid",
]


def _build_ie_features(pkt) -> tuple[str, str, str, bytes]:
    from scapy.all import Dot11Elt

    ids: list[str] = []
    fingerprint_parts: list[str] = []
    vendor_ouis: list[str] = []
    ssid_bytes = b""
    elt = pkt.getlayer(Dot11Elt)
    while elt is not None:
        eid = int(getattr(elt, "ID", -1))
        info = bytes(getattr(elt, "info", b""))
        if eid == 0:
            ssid_bytes = info
        if eid in _IE_KEEP_IDS:
            ids.append(str(eid))
            fingerprint_parts.append(f"{eid}:{info.hex()}")
            if eid == 221 and len(info) >= 3:
                vendor_ouis.append(info[:3].hex())
        elt = elt.payload.getlayer(Dot11Elt)
    return ",".join(ids), ";".join(fingerprint_parts), ",".join(vendor_ouis), ssid_bytes


def _extract_pcap_features(pcap_path: Path) -> pd.DataFrame:
    """Return a DataFrame of 802.11 features from the PCAP, one row per frame."""
    try:
        from scapy.all import Dot11, PcapReader
    except Exception as exc:
        raise ValidationError(
            "scapy is required for enrichment. Install with: pip install scapy"
        ) from exc

    rows: list[dict] = []
    ssid_observations: dict[str, list[str]] = defaultdict(list)

    try:
        with PcapReader(str(pcap_path)) as reader:
            for pkt in reader:
                if not pkt.haslayer(Dot11):
                    continue
                dot11 = pkt[Dot11]
                ts = getattr(pkt, "time", None)
                if ts is None:
                    continue

                ie_ids, ie_fp, ie_vendors, ssid_bytes = _build_ie_features(pkt)
                src_mac = (dot11.addr2 or "").lower()
                ssid_str = ssid_bytes.decode("utf-8", errors="replace") if ssid_bytes else ""
                if src_mac and ssid_str:
                    ssid_observations[src_mac].append(ssid_str)

                rows.append(
                    {
                        "timestamp_utc": pd.to_datetime(float(ts), unit="s", utc=True, errors="coerce"),
                        "src_mac": src_mac,
                        "dst_mac": (dot11.addr1 or "").lower(),
                        "bssid": (dot11.addr3 or "").lower(),
                        "seq_ctl": getattr(dot11, "SC", None),
                        "frame_len": len(pkt),
                        "ie_ids": ie_ids,
                        "ie_fingerprint": ie_fp,
                        "ie_vendor_ouis": ie_vendors,
                        "ssid": ssid_str,
                    }
                )
    except Exception as exc:
        raise ValidationError(f"Failed to parse PCAP: {pcap_path.name} — {exc}") from exc

    if not rows:
        return pd.DataFrame(columns=_PCAP_COLUMNS)

    df = pd.DataFrame(rows)

    # Per-MAC most-common SSID — overrides per-frame ssid for stability
    consensus = {
        mac: Counter(values).most_common(1)[0][0]
        for mac, values in ssid_observations.items()
        if values
    }
    if consensus:
        df["ssid"] = df["src_mac"].map(consensus).fillna(df["ssid"])

    return df


# ---------------------------------------------------------------------------
# CSV/PCAP normalization helpers
# ---------------------------------------------------------------------------

_BROADCAST_MAC = "ff:ff:ff:ff:ff:ff"
_BROADCAST_ALIASES = {
    "broadcast": _BROADCAST_MAC,
    "ff-ff-ff-ff-ff-ff": _BROADCAST_MAC,
    "ff.ff.ff.ff.ff.ff": _BROADCAST_MAC,
    "": "",
    "nan": "",
}


def _normalize_mac_series(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.lower()
    return s.replace(_BROADCAST_ALIASES)


# ---------------------------------------------------------------------------
# Core enrichment (mirrors legacy enrich_csv_with_pcap)
# ---------------------------------------------------------------------------

def _enrich_dataframe(
    csv_df: pd.DataFrame,
    pcap_df: pd.DataFrame,
    tolerance_ms: float,
) -> tuple[pd.DataFrame, int, int]:
    """Return (enriched_df, matched_rows, total_rows)."""
    df = csv_df.copy()
    df.columns = [c.strip().lower() for c in df.columns]

    if "timestamp_utc" not in df.columns:
        # Fall back: try other common column names
        for alt in ("timestamp", "time", "ts"):
            if alt in df.columns:
                df = df.rename(columns={alt: "timestamp_utc"})
                break
    if "timestamp_utc" not in df.columns:
        raise ValidationError("CSV is missing 'timestamp_utc' column.")
    if "src_mac" not in df.columns:
        for alt in ("mac", "source_mac", "addr"):
            if alt in df.columns:
                df = df.rename(columns={alt: "src_mac"})
                break
    if "src_mac" not in df.columns:
        raise ValidationError("CSV is missing 'src_mac' column.")

    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], errors="coerce", utc=True)
    df["src_mac"] = _normalize_mac_series(df["src_mac"])
    if "dst_mac" in df.columns:
        df["dst_mac"] = _normalize_mac_series(df["dst_mac"])
    if "bssid" in df.columns:
        df["bssid"] = _normalize_mac_series(df["bssid"])

    total = len(df)
    matched = 0

    if pcap_df.empty:
        df["_match_delta_ms"] = pd.NA
        df["match_found"] = False
        return df, 0, total

    valid_mask = df["timestamp_utc"].notna()
    df_valid = df[valid_mask].copy().sort_values("timestamp_utc").reset_index(drop=True)
    df_invalid = df[~valid_mask].copy()

    pcap_sorted = pcap_df.copy().sort_values("timestamp_utc").reset_index(drop=True)
    pcap_sorted["src_mac"] = _normalize_mac_series(pcap_sorted["src_mac"])

    if df_valid.empty:
        df["_match_delta_ms"] = pd.NA
        df["match_found"] = False
        return df, 0, total

    merged = pd.merge_asof(
        df_valid,
        pcap_sorted,
        on="timestamp_utc",
        by="src_mac",
        direction="nearest",
        tolerance=pd.Timedelta(milliseconds=tolerance_ms),
        suffixes=("", "_pcap"),
    )

    # match indicator: rows where any pcap-only column was filled
    pcap_only_cols = [c for c in pcap_sorted.columns if c not in df_valid.columns and c != "timestamp_utc"]
    if pcap_only_cols:
        match_mask = merged[pcap_only_cols].notna().any(axis=1)
    else:
        match_mask = pd.Series(False, index=merged.index)
    merged["match_found"] = match_mask
    matched = int(match_mask.sum())

    # _match_delta_ms — for merge_asof we don't have the pcap timestamp post-merge,
    # but rows that didn't match will have NaN in pcap-only cols. Set 0.0 when matched.
    merged["_match_delta_ms"] = match_mask.map({True: 0.0, False: None})

    if not df_invalid.empty:
        for col in merged.columns:
            if col not in df_invalid.columns:
                df_invalid[col] = pd.NA
        df_invalid["match_found"] = False
        out = pd.concat([merged, df_invalid], ignore_index=True)
    else:
        out = merged

    # SSID coalesce (CSV ssid wins, fill missing from pcap)
    if "ssid_pcap" in out.columns:
        if "ssid" in out.columns:
            out["ssid"] = out["ssid"].where(out["ssid"].astype(bool), out["ssid_pcap"])
        else:
            out["ssid"] = out["ssid_pcap"]
        out = out.drop(columns=["ssid_pcap"])

    return out, matched, total


# ---------------------------------------------------------------------------
# EnrichmentService
# ---------------------------------------------------------------------------

class EnrichmentService:
    def __init__(
        self,
        session_service: SessionNavigationService,
        dataset_service: DatasetDiscoveryService,
    ) -> None:
        self._session_service = session_service
        self._dataset_service = dataset_service

    def run_enrichment(
        self,
        session_id: str,
        selected_csv_file: str,
        selected_pcap_file: str,
        parameters: EnrichmentParameters,
    ) -> EnrichmentRunPayload:
        session = self._session_service.require_session(session_id)
        csv_path = self._resolve_csv(session.scan_folder_id, selected_csv_file)
        pcap_path = self._resolve_pcap(session.scan_folder_id, selected_pcap_file)
        protocol = session.mode

        try:
            csv_df = pd.read_csv(csv_path)
        except Exception as exc:
            raise ValidationError(f"Failed to read CSV: {selected_csv_file} — {exc}") from exc
        if csv_df.empty:
            raise ValidationError(f"CSV file is empty: {selected_csv_file}")

        pcap_df = _extract_pcap_features(pcap_path)
        tolerance_ms = float(parameters.match_time_window_ms) if parameters.match_time_window_ms else 1000.0
        enriched_df, matched, total = _enrich_dataframe(csv_df, pcap_df, tolerance_ms=tolerance_ms)

        stem = Path(selected_csv_file).stem
        output_name = f"{stem}_ENRICHED.csv"
        output_path = self._dataset_service._paths.folder_path(session.scan_folder_id) / output_name
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        try:
            enriched_df.to_csv(tmp_path, index=False)
            tmp_path.replace(output_path)
        except PermissionError as exc:
            tmp_path.unlink(missing_ok=True)
            raise ValidationError(
                f"Cannot write enriched artifact '{output_name}'. "
                f"The file is locked by another program (likely open in Excel). "
                f"Close it and try again."
            ) from exc

        artifact_id = f"{session.scan_folder_id}:{output_name}"
        try:
            self._session_service.activate_artifact(session_id=session_id, artifact_id=artifact_id)
        except NotFoundError:
            pass

        match_rate = round(matched / total, 4) if total else 0.0
        return EnrichmentRunPayload(
            selected_csv_file=selected_csv_file,
            selected_pcap_file=selected_pcap_file,
            output_enriched_file=output_name,
            protocol=protocol,
            parameters=parameters,
            diagnostics=EnrichmentDiagnostics(
                total_rows=total,
                matched_rows=matched,
                unmatched_rows=total - matched,
                match_rate=match_rate,
            ),
        )

    # ------------------------------------------------------------------
    # Resolution helpers
    # ------------------------------------------------------------------

    def resolve_matching_pcap(self, folder_id: str, csv_file_name: str) -> str:
        stem = Path(csv_file_name).stem.lower()
        inventory = self._dataset_service.resolve_inventory(folder_id)
        match = next(
            (item.file_name for item in inventory.pcap_files if item.base_name.lower() == stem),
            None,
        )
        if match is None:
            raise ValidationError(
                f"No matching PCAP found for '{csv_file_name}'. "
                "Expected a file with the same base name in the same folder."
            )
        return match

    def _resolve_csv(self, folder_id: str, file_name: str) -> Path:
        inventory = self._dataset_service.resolve_inventory(folder_id)
        available = {item.file_name for item in inventory.raw_csv_files}
        if file_name not in available:
            raise ValidationError(f"Selected CSV is not available in active folder: {file_name}")
        path = self._dataset_service._paths.folder_path(folder_id) / file_name
        if not path.exists():
            raise NotFoundError(f"CSV file does not exist: {file_name}")
        return path

    def _resolve_pcap(self, folder_id: str, file_name: str) -> Path:
        inventory = self._dataset_service.resolve_inventory(folder_id)
        available = {item.file_name for item in inventory.pcap_files}
        if file_name not in available:
            raise ValidationError(f"Selected PCAP is not available in active folder: {file_name}")
        path = self._dataset_service._paths.folder_path(folder_id) / file_name
        if not path.exists():
            raise NotFoundError(f"PCAP file does not exist: {file_name}")
        return path
