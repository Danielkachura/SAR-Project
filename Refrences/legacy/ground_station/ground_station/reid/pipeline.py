import os
import json
import pandas as pd

from .features import load_scan_csv, extract_feature_vector, normalize_columns
from .models import ReidConfig
from .clustering import OnlineClusterer
from .pcap_features import extract_pcap_features # Kept if needed by other modules
from .vendor_lookup import get_vendor_series # Kept for backward compat

def generate_localization_export(df_reid, main_output_path):
    """
    Generate lightweight CSV optimized for localization engine.
    
    Args:
        df_reid: Enriched DataFrame containing 'cluster_id'
        main_output_path: Path for standard Re-ID output, used to determine localization export path.
    """
    if not main_output_path:
        return
    
    base_dir = os.path.dirname(main_output_path)
    loc_path = os.path.join(base_dir, "localization_input.csv")
    
    required_cols = ["timestamp_utc", "gps_lat", "gps_lon", "rssi_dbm", "cluster_id"]
    optional_cols = ["src_mac", "ssid"]
    
    # Filter for required columns
    available_req = [c for c in required_cols if c in df_reid.columns]
    
    if "gps_lat" not in available_req or "cluster_id" not in available_req:
        return

    export_cols = available_req + [c for c in optional_cols if c in df_reid.columns]
    
    loc_df = df_reid[export_cols].copy()
    loc_df = loc_df.dropna(subset=["gps_lat", "gps_lon", "cluster_id"])
    loc_df.to_csv(loc_path, index=False)


def resolve_mac_conflicts(df):
    """
    Conflict Resolution Pass:
    If a MAC address exists in more than one cluster_id, identify the dominant cluster
    (highest packet count) and set others to -1 (Noise).
    """
    if "cluster_id" not in df.columns or "src_mac" not in df.columns:
        return df

    # Work on a copy or inplace? Inplace is usually expected in pipeline but let's be safe.
    df = df.copy()

    # robust groupby
    # We want to find MACs that have > 1 unique cluster_id (ignoring -1? mostly -1 is result of this, but maybe input has -1?)
    # User says: "If a MAC address exists in more than one cluster_id"
    
    # 1. Get counts of (mac, cluster_id)
    # Filter out invalid macs if needed
    
    # We will iterate by MAC for clarity and robustness
    # Optimization: vectorized approach using groupby
    
    # Count occurrences of each cluster_id per mac
    counts = df.groupby(["src_mac", "cluster_id"]).size().reset_index(name="count")
    
    # Filter out noise cluster if it exists in counts? User implies we create noise, but maybe we ignore existing noise?
    # "Group the data by src_mac. If a MAC address exists in more than one cluster_id..."
    
    # Find MACs with multiple clusters
    mac_counts = counts.groupby("src_mac").size()
    conflict_macs = mac_counts[mac_counts > 1].index
    
    if len(conflict_macs) == 0:
        return df
        
    for mac in conflict_macs:
        # subset for this mac
        mac_rows = counts[counts["src_mac"] == mac]
        
        # Identify dominant (highest packet count)
        # If tie, pick first (arbitrary)
        dominant_row = mac_rows.sort_values("count", ascending=False).iloc[0]
        dominant_cluster = dominant_row["cluster_id"]
        
        # Set all other rows for this MAC to -1
        # mask: rows with this mac AND cluster_id != dominant
        mask = (df["src_mac"] == mac) & (df["cluster_id"] != dominant_cluster)
        df.loc[mask, "cluster_id"] = -1
        
        # Log? User: "Add logging to indicate when a MAC is split due to a 'Physics Violation'"
        # Actually proper logging would be inside the clusterer for the split event. 
        # But here we are resolving conflicts (merging back to one?). No, we are discarding minority.
        # This effectively enforces "One MAC -> One Cluster" for the whole file AFTER processing.
        # This seems to contradict "Hierarchical... Physics Split" which creates splits.
        # User requirement 3 says: "Physics violation... split the cluster". 
        # User requirement 5 says: "If a MAC... exists in more than one cluster... Keep dominant... others -1".
        # This means we *allow* the split during online processing (so we can track the 'new' identity temporarily?), 
        # but in post-processing we decide the 'split' was just noise/bad data and discard the minority?
        # That seems to be the logic.
    
    return df

def cluster_scan_df(df, config=None, use_confidence=True):
    """
    Cluster a scan DataFrame using Online Hierarchical Logic.
    Returns:
        (row_cluster_map, summary_placeholder)
        row_cluster_map is dict {index: cluster_id}
    """
    if config is None:
        config = ReidConfig()
        
    clusterer = OnlineClusterer(config)
    
    # Sort strictly by time to simulate online stream
    # Ensure index is preserved
    df_sorted = df.sort_values("timestamp_utc")
    
    # Store results: index -> cluster_id
    row_cluster_map = {}
    
    # Process
    for idx, row in df_sorted.iterrows():
        try:
            packet_data = extract_feature_vector(row)
            # Skip rows with no valid timestamp or MAC
            if pd.isna(packet_data['timestamp']) or not packet_data['src_mac']:
                continue
                
            c_id = clusterer.process_packet(packet_data)
            row_cluster_map[idx] = c_id
        except Exception as e:
            # Log error
            continue
            
    summary_placeholder = pd.DataFrame(index=range(len(clusterer.active_clusters))) 
    
    return row_cluster_map, summary_placeholder


def apply_clusters_to_df(df, cluster_ids):
    """
    Apply cluster IDs back to original dataframe.
    Handles both {mac: id} (legacy) and {index: id} (new) maps.
    """
    df = df.copy()
    
    if not cluster_ids:
        df["cluster_id"] = -1
        return df

    # Check key type to determine mode
    first_key = next(iter(cluster_ids))
    if isinstance(first_key, int) or isinstance(first_key, float):
        # Assume Index mapping
        df["cluster_id"] = df.index.map(cluster_ids)
    else:
        # Assume MAC mapping
        df["cluster_id"] = df["src_mac"].map(cluster_ids)
    
    # Fill NAs
    df["cluster_id"] = df["cluster_id"].fillna(-1).astype(int)
    return df


def run_reid_on_csv(csv_path, output_path=None, config=None, use_confidence=True, json_output_path=None):
    """
    Run full Re-ID pipeline on a CSV file.
    """
    df = load_scan_csv(csv_path)
    
    cluster_result, _ = cluster_scan_df(df, config=config, use_confidence=use_confidence)
    out_df = apply_clusters_to_df(df, cluster_result)
    
    # Conflict Resolution
    out_df = resolve_mac_conflicts(out_df)
    
    if output_path:
        out_df.to_csv(output_path, index=False)
    
    # Generate Localization Export
    generate_localization_export(out_df, output_path)

    return out_df


def _normalize_mac(series):
    """Lowercase MACs and standardize broadcast variations to ff:ff:ff:ff:ff:ff."""
    if series is None:
        return series
    broadcast_aliases = {
        "broadcast": "ff:ff:ff:ff:ff:ff",
        "ff-ff-ff-ff-ff-ff": "ff:ff:ff:ff:ff:ff",
        "ff.ff.ff.ff.ff.ff": "ff:ff:ff:ff:ff:ff",
    }
    series = series.astype(str).str.lower()
    return series.replace(broadcast_aliases)


def enrich_csv_with_pcap(csv_path, pcap_path, output_path=None, tolerance_ms=1000):
    df = pd.read_csv(csv_path)
    df = normalize_columns(df) # features.py normalize_columns
    if "timestamp_utc" in df.columns:
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], format="ISO8601", errors="coerce", utc=True)
    if "src_mac" in df.columns:
        df["src_mac"] = _normalize_mac(df["src_mac"])
    if "dst_mac" in df.columns:
        df["dst_mac"] = _normalize_mac(df["dst_mac"])
    if "bssid" in df.columns:
        df["bssid"] = _normalize_mac(df["bssid"])

    pcap_df = extract_pcap_features(pcap_path)
    if not pcap_df.empty:
        # Filter out rows with invalid timestamps
        valid_timestamp_mask = df["timestamp_utc"] > pd.Timestamp("2000-01-01", tz="UTC")
        df_valid = df[valid_timestamp_mask].copy()
        df_invalid = df[~valid_timestamp_mask].copy()
        
        df_valid = df_valid.sort_values("timestamp_utc").reset_index(drop=True)
        pcap_df = pcap_df.sort_values("timestamp_utc").reset_index(drop=True)

        # Normalize MAC addresses for matching
        df_valid["src_mac"] = _normalize_mac(df_valid["src_mac"])
        pcap_df["src_mac"] = _normalize_mac(pcap_df["src_mac"])

        # Add vendor lookup for src_mac
        if "src_mac" in df_valid.columns and "src_vendor" not in df_valid.columns:
            df_valid["src_vendor"] = get_vendor_series(df_valid["src_mac"])

        # Split CSV rows by expected destination type
        bcast = "ff:ff:ff:ff:ff:ff"
        broadcast_expected = df_valid[df_valid["frame_type"].isin(["beacon", "probe-req"])].copy()
        unicast_expected = df_valid[df_valid["frame_type"].isin(["probe-resp"])].copy()
        other_rows = df_valid[~df_valid.index.isin(broadcast_expected.index.union(unicast_expected.index))].copy()

        # Prepare filtered PCAP views
        # (Simplified filtering logic for merge robustness)
        pcap_broadcast = pcap_df[pcap_df["dst_mac"] == bcast].copy()
        pcap_unicast = pcap_df[pcap_df["dst_mac"] != bcast].copy()

        parts = []
        # Merge broadcast
        if not broadcast_expected.empty:
            m_b = pd.merge_asof(
                broadcast_expected,
                pcap_broadcast,
                left_on="timestamp_utc",
                right_on="timestamp_utc",
                by="src_mac",
                direction="nearest",
                tolerance=pd.Timedelta(milliseconds=tolerance_ms),
                suffixes=("", "_pcap"),
            )
            parts.append(m_b)

        # Merge unicast
        if not unicast_expected.empty:
            m_u = pd.merge_asof(
                unicast_expected,
                pcap_unicast,
                left_on="timestamp_utc",
                right_on="timestamp_utc",
                by="src_mac",
                direction="nearest",
                tolerance=pd.Timedelta(milliseconds=tolerance_ms),
                suffixes=("", "_pcap"),
            )
            parts.append(m_u)

        if not other_rows.empty:
            # Fallback merge
            m_o = pd.merge_asof(
                other_rows,
                pcap_df,
                left_on="timestamp_utc",
                right_on="timestamp_utc",
                by="src_mac",
                direction="nearest",
                tolerance=pd.Timedelta(milliseconds=tolerance_ms),
                suffixes=("", "_pcap"),
            )
            parts.append(m_o)

        merged = pd.concat(parts, ignore_index=True).sort_values("timestamp_utc").reset_index(drop=True)
        
        # Add match quality indicator
        if "timestamp_utc_pcap" in merged.columns:
            merged["_match_delta_ms"] = (
                (merged["timestamp_utc"] - merged["timestamp_utc_pcap"]).dt.total_seconds() * 1000
            ).abs()
            merged = merged.drop(columns=["timestamp_utc_pcap"], errors="ignore")
        
        # Combine valid and invalid
        if not df_invalid.empty:
            for col in merged.columns:
                if col not in df_invalid.columns:
                    df_invalid[col] = pd.NA
            df = pd.concat([merged, df_invalid], ignore_index=True).sort_values("timestamp_utc").reset_index(drop=True)
        else:
            df = merged

        # Handle features logic
        if "ssid_pcap" in df.columns:
            df["ssid"] = df["ssid"].combine_first(df["ssid_pcap"])
            df = df.drop(columns=["ssid_pcap"], errors="ignore")
            
        # Handle new PCAP-only columns
        for col in ["ie_ids", "ie_fingerprint", "ie_vendor_ouis", "frame_len"]:
            pcap_col = f"{col}_pcap"
            if pcap_col in df.columns:
                if col not in df.columns:
                    df[col] = df[pcap_col]
                else:
                    df[col] = df[col].combine_first(df[pcap_col])
                df = df.drop(columns=[pcap_col], errors="ignore")

    df = _coerce_types_local(df)
    if output_path:
        df.to_csv(output_path, index=False)
    return df

def _coerce_types_local(df):
    # Minimal coerce
    return df

