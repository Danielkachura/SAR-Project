"""Sidebar filter UI components for WiFi and BLE."""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

from .ble_analysis import apply_ble_filters as _apply_ble_filters, render_ble_filters as _render_ble_filters

WiFiFilters = Dict[str, object]
BLEFilters = Dict[str, object]


def _time_range(df: pd.DataFrame) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    if "timestamp_utc" not in df.columns or df["timestamp_utc"].isna().all():
        return None, None
    return df["timestamp_utc"].min(), df["timestamp_utc"].max()


def render_wifi_filters(df: pd.DataFrame) -> WiFiFilters:
    st.sidebar.markdown("### 🌪️ WiFi Filters")
    filters: WiFiFilters = {}

    # RSSI
    if not df.empty and df["rssi_dbm"].notna().any():
        rssi_min = int(df["rssi_dbm"].min())
        rssi_max = int(df["rssi_dbm"].max())
        if rssi_min == rssi_max:
            rssi_min -= 10
            rssi_max += 10
    else:
        rssi_min, rssi_max = -100, 0
    filters["rssi_range"] = st.sidebar.slider("RSSI Range (dBm)", rssi_min, rssi_max, (rssi_min, rssi_max), help="Filter packets by signal strength. Lower is weaker.")

    # Frame types
    types = sorted(df["frame_type"].dropna().unique()) if "frame_type" in df.columns else []
    filters["frame_types"] = st.sidebar.multiselect("Frame Types", options=types, default=types, help="Select specific WiFi frame types to include (e.g. Probe Request, Beacon).")

    # Channels
    chans = sorted(df["channel"].dropna().unique()) if "channel" in df.columns else []
    filters["channels"] = st.sidebar.multiselect("Channels", options=chans, default=chans, help="Filter by WiFi channel number.")

    # MAC privacy + SSID visibility
    col1, col2 = st.sidebar.columns(2)
    filters["mac_privacy"] = col1.radio("MAC Privacy", ["All", "Randomized (LAA)", "Fixed (Global)"], help="Filter by Randomized (LAA) or Fixed (Global) MAC addresses.")
    filters["ssid_filter"] = col2.radio("SSID Visibility", ["All", "Named Only", "Hidden/Empty Only"], help="Filter by SSID presence (Named vs Hidden/Empty).")

    # Vendor filter (optional)
    if "vendor" in df.columns:
        vendors = sorted(v for v in df["vendor"].dropna().unique() if v)
        filters["vendors"] = st.sidebar.multiselect("Vendors", options=vendors, default=[], help="Filter by device manufacturer (derived from OUI).")
    else:
        filters["vendors"] = []

    # Time range filter (Disabled)
    filters["time_range"] = None

    # Min packets
    filters["min_packets"] = st.sidebar.slider("Min Packets", 1, 100, 1, help="Exclude devices with fewer than N packets.")

    # MAC Filtering
    if "src_mac" in df.columns:
        mac_counts = df["src_mac"].value_counts()
        sort_by = st.sidebar.radio("Sort MACs by", ["Packets", "MAC Address", "Name"], index=0, horizontal=True, key="wifi_mac_sort", help="Sort order for the MAC address list below.")
        
        # Prepare list of dicts for flexible sorting
        mac_data = []
        for mac, count in mac_counts.items():
            vendor = "Unknown"
            if "vendor" in df.columns:
                # Get the first non-null vendor for this MAC
                v_series = df[df["src_mac"] == mac]["vendor"].dropna()
                if not v_series.empty:
                    vendor = v_series.iloc[0]
            mac_data.append({"mac": mac, "count": count, "vendor": vendor})

        if sort_by == "Packets":
            mac_data.sort(key=lambda x: x["count"], reverse=True)
        elif sort_by == "MAC Address":
            mac_data.sort(key=lambda x: x["mac"])
        elif sort_by == "Name":
            mac_data.sort(key=lambda x: (x["vendor"].lower(), x["mac"]))

        mac_options = [f"{d['mac']} ({d['count']} pkts, {d['vendor']})" for d in mac_data]
        
        mode = st.sidebar.radio("MAC Filter Mode", ["Include", "Exclude"], index=1, key="wifi_mac_mode", help="Include or Exclude the selected MAC addresses.")
        filters["mac_filter_mode"] = mode

        selected = st.sidebar.multiselect(f"{mode} MACs", options=mac_options, default=[], help="Select specific devices to filter.")
        filters["selected_macs"] = [opt.split(" (")[0] for opt in selected]
    else:
        filters["mac_filter_mode"] = "Exclude"
        filters["selected_macs"] = []

    return filters


def apply_wifi_filters(df: pd.DataFrame, filters: WiFiFilters) -> pd.DataFrame:
    if df.empty:
        return df

    # Separate Heartbeats
    is_heartbeat = df["frame_type"] == "heartbeat" if "frame_type" in df.columns else pd.Series(False, index=df.index)
    heartbeats = df[is_heartbeat].copy()
    others = df[~is_heartbeat].copy()

    # --- Filter 'Others' (Normal Packets) ---
    mask = (
        (others["rssi_dbm"] >= filters["rssi_range"][0]) &
        (others["rssi_dbm"] <= filters["rssi_range"][1])
    )

    # Frame types
    if filters.get("frame_types"):
        mask &= others["frame_type"].isin(filters["frame_types"])

    # Channels
    if filters.get("channels"):
        mask &= others["channel"].isin(filters["channels"])

    # MAC privacy
    if filters.get("mac_privacy") == "Randomized (LAA)" and "is_randomized" in others.columns:
        mask &= others["is_randomized"] == True
    elif filters.get("mac_privacy") == "Fixed (Global)" and "is_randomized" in others.columns:
        mask &= others["is_randomized"] == False

    # SSID visibility
    if filters.get("ssid_filter") == "Named Only" and "ssid" in others.columns:
        mask &= others["ssid"] != ""
    elif filters.get("ssid_filter") == "Hidden/Empty Only" and "ssid" in others.columns:
        mask &= others["ssid"] == ""

    # Vendors
    if filters.get("vendors") and "vendor" in others.columns:
        mask &= others["vendor"].isin(filters["vendors"])

    # MAC Filtering
    selected_macs = filters.get("selected_macs", []) or []
    mac_mode = filters.get("mac_filter_mode", "Exclude")
    if selected_macs and "src_mac" in others.columns:
        if mac_mode == "Include":
            mask &= others["src_mac"].isin(selected_macs)
        else: # Exclude
            mask &= ~others["src_mac"].isin(selected_macs)
            
    filtered_others = others[mask]

    # Min packet threshold (only for others)
    min_pkts = int(filters.get("min_packets", 1))
    if min_pkts > 1 and "src_mac" in filtered_others.columns:
        counts = filtered_others["src_mac"].value_counts()
        valid = counts[counts >= min_pkts].index
        filtered_others = filtered_others[filtered_others["src_mac"].isin(valid)]

    # --- Time Window (Apply to Both) ---
    time_window = filters.get("time_range")
    if time_window and "timestamp_utc" in df.columns:
        start, end = map(pd.to_datetime, time_window)
        # Apply to others
        filtered_others = filtered_others[filtered_others["timestamp_utc"].between(start, end)]
        # Apply to heartbeats
        heartbeats = heartbeats[heartbeats["timestamp_utc"].between(start, end)]

    # Combine
    result = pd.concat([filtered_others, heartbeats])
    if "timestamp_utc" in result.columns:
        result = result.sort_values("timestamp_utc")
        
    return result


def render_ble_filters(df: pd.DataFrame) -> BLEFilters:
    filters = _render_ble_filters(df)

    # Add time window on top of existing BLE filters
    # Time range filter (Disabled)
    filters["time_range"] = None
    return filters


def apply_ble_filters(df: pd.DataFrame, filters: BLEFilters) -> pd.DataFrame:
    filtered = _apply_ble_filters(
        df,
        rssi_range=filters["rssi_range"],
        selected_event_types=filters["event_types"],
        selected_companies=filters["companies"],
        tx_power_range=filters["tx_power_range"],
        address_type_filter=filters["address_types"],
        min_packets=filters["min_packets"],
        selected_macs=filters["selected_macs"],
        mac_filter_mode=filters["mac_filter_mode"],
    )

    time_window = filters.get("time_range")
    if time_window and "timestamp_utc" in filtered.columns:
        start, end = time_window
        start = pd.to_datetime(start)
        end = pd.to_datetime(end)
        filtered = filtered[filtered["timestamp_utc"].between(start, end)]

    return filtered


def render(df: pd.DataFrame, protocol: str) -> Dict[str, object]:
    if protocol == "wifi":
        return render_wifi_filters(df)
    if protocol == "ble":
        return render_ble_filters(df)
    st.sidebar.info("Protocol not recognized; using empty filters.")
    return {}


def apply_filters(df: pd.DataFrame, protocol: str, filters: Dict[str, object]) -> pd.DataFrame:
    if protocol == "wifi":
        return apply_wifi_filters(df, filters)
    if protocol == "ble":
        return apply_ble_filters(df, filters)
    return df


def render_blank_placeholder():
    st.info("Filters are disabled for this view.")
