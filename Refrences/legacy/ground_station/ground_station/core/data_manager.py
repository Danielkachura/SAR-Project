"""Centralized data loading and enrichment for the modular app."""

from __future__ import annotations

import os
import io
import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import streamlit as st

from .shared_utils import (
    detect_protocol,
    extract_heartbeats,
    filter_valid_data,
    load_csv_generic,
    prepare_map_data,
    resolve_vendor,
    is_randomized_mac,
)

try:
    from reid.vendor_lookup import get_vendor_series  # type: ignore
except Exception:  # pragma: no cover - fallback
    def get_vendor_series(mac_series: pd.Series) -> pd.Series:
        return pd.Series(["Unknown"] * len(mac_series), index=mac_series.index)

try:
    from reid.pipeline import enrich_csv_with_pcap  # type: ignore
except Exception:  # pragma: no cover
    enrich_csv_with_pcap = None

DATA_DIR = Path(__file__).parent.parent / "data"


@dataclass
class Dataset:
    data: pd.DataFrame
    protocol: str
    source_path: Path
    enriched_path: Optional[Path]
    heartbeats: pd.DataFrame
    map_df: pd.DataFrame
    error: Optional[str] = None


def list_scan_folders(base_dir: Optional[Path] = None, prefixes: Optional[Iterable[str]] = None) -> List[Path]:
    base = Path(base_dir) if base_dir else DATA_DIR
    if not base.exists():
        return []
    prefixes = [p.lower() for p in (prefixes or ["scan", "ble"])]
    folders: List[Path] = []
    for entry in base.iterdir():
        if entry.is_dir() and any(entry.name.lower().startswith(p) for p in prefixes):
            folders.append(entry)
    return sorted(folders)


def list_csv_files(folder: Path) -> Dict[str, Path]:
    if not folder.exists():
        return {}
    csvs = sorted(folder.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    options: Dict[str, Path] = {}
    for path in csvs:
        size = path.stat().st_size
        size_str = f"{size/1024:.1f} KB" if size < 1024 * 1024 else f"{size/(1024*1024):.2f} MB"
        label = f"{path.name} ({size_str})"
        options[label] = path
    return options


def get_enriched_path(csv_path: Path) -> Path:
    stem = csv_path.with_suffix("")
    return Path(f"{stem}_enriched.csv")


def _load_wifi_csv(csv_path: Path) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        data = pd.read_csv(csv_path)
        data.columns = [c.lower() for c in data.columns]

        required = {"src_mac", "rssi_dbm", "timestamp_utc"}
        missing = [c for c in required if c not in data.columns]
        if missing:
            return None, f"Missing critical columns: {', '.join(missing)}"

        # Ensure baseline columns exist
        for col, default in {"gps_lat": pd.NA, "gps_lon": pd.NA, "frame_type": "unknown", "channel": 0, "noise_dbm": 0}.items():
            if col not in data.columns:
                data[col] = default

        # Normalize types
        data["rssi_dbm"] = pd.to_numeric(data["rssi_dbm"], errors="coerce")
        data["gps_lat"] = pd.to_numeric(data["gps_lat"], errors="coerce")
        data["gps_lon"] = pd.to_numeric(data["gps_lon"], errors="coerce")
        data["timestamp_utc"] = pd.to_datetime(data["timestamp_utc"], format="ISO8601", errors="coerce")
        if "seq_ctl" in data.columns:
            data["seq_ctl"] = pd.to_numeric(data["seq_ctl"], errors="coerce")

        # Preserve heartbeats; keep rows with valid RSSI+MAC otherwise
        mask_hb = data["frame_type"] == "heartbeat"
        keep_mask = mask_hb | (~data[["rssi_dbm", "src_mac"]].isna().any(axis=1))
        data = data[keep_mask]

        # Vendor + LAA flags
        mac_series = data["src_mac"].astype(str)
        try:
            vendor_series = get_vendor_series(mac_series)
        except Exception:
            vendor_series = mac_series.apply(resolve_vendor)
        data["vendor"] = vendor_series.fillna("Unknown")
        data["is_randomized"] = mac_series.apply(is_randomized_mac)

        # Clean GPS zeros
        data.loc[(data["gps_lat"].isna()) | (data["gps_lat"] == 0), "gps_lat"] = pd.NA
        data.loc[(data["gps_lon"].isna()) | (data["gps_lon"] == 0), "gps_lon"] = pd.NA

        return data, None
    except Exception as exc:  # pragma: no cover
        return None, str(exc)


@st.cache_data(show_spinner=False)
def load_dataset(path_str: str, prefer_enriched: bool = False, file_sig: Optional[Tuple[float, int]] = None) -> Dataset:
    csv_path = Path(path_str)
    if not csv_path.exists():
        return Dataset(
            data=pd.DataFrame(),
            protocol="unknown",
            source_path=csv_path,
            enriched_path=None,
            heartbeats=pd.DataFrame(),
            map_df=pd.DataFrame(),
            error=f"File not found: {csv_path}",
        )

    enriched_path = get_enriched_path(csv_path)
    target_path = enriched_path if prefer_enriched and enriched_path.exists() else csv_path

    # file_sig is part of the cache key to invalidate when the file changes
    _ = file_sig

    df, protocol = load_csv_generic(target_path)
    error: Optional[str] = None

    if protocol == "unknown":
        df, error = _load_wifi_csv(csv_path)
        protocol = "wifi" if error is None else "unknown"

    if df is None:
        df = pd.DataFrame()

    heartbeats = extract_heartbeats(df, protocol)
    map_df = prepare_map_data(df, protocol)
    df = filter_valid_data(df, protocol)

    return Dataset(
        data=df,
        protocol=protocol,
        source_path=csv_path,
        enriched_path=enriched_path if enriched_path.exists() else None,
        heartbeats=heartbeats,
        map_df=map_df,
        error=error,
    )


def enrich_csv(csv_path: Path, output_path: Optional[Path] = None, tolerance_ms: int = 1000) -> Tuple[Optional[Path], Optional[str]]:
    if enrich_csv_with_pcap is None:
        return None, "Re-ID enrichment module not available"

    pcap_path = csv_path.with_suffix(".pcap")
    if not pcap_path.exists():
        return None, f"Missing PCAP: {pcap_path.name}"

    out_path = output_path or get_enriched_path(csv_path)

    log_stream = io.StringIO()
    try:
        with contextlib.redirect_stdout(log_stream), contextlib.redirect_stderr(log_stream):
            enrich_csv_with_pcap(str(csv_path), str(pcap_path), output_path=str(out_path), tolerance_ms=tolerance_ms)
        log_text = log_stream.getvalue().strip() or None
        return out_path, log_text
    except Exception as exc:  # pragma: no cover
        return None, str(exc)
