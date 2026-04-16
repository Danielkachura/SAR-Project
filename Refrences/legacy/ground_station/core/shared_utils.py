"""
Shared utilities for WiFi and BLE visualization.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Tuple


def detect_protocol(df: pd.DataFrame) -> str:
    """
    Auto-detect protocol (WiFi or BLE) from DataFrame columns.
    
    Returns:
        'wifi' if WiFi columns detected
        'ble' if BLE columns detected
        'unknown' otherwise
    """
    cols_lower = {c.lower() for c in df.columns}
    
    # WiFi markers
    if 'frame_type' in cols_lower or 'ssid' in cols_lower or 'bssid' in cols_lower:
        return 'wifi'
    
    # BLE markers
    if 'event_type' in cols_lower or 'adv_data_hex' in cols_lower or 'company_id' in cols_lower:
        return 'ble'
    
    return 'unknown'


def load_csv_generic(file_path: Path) -> Tuple[pd.DataFrame, str]:
    """
    Load CSV with protocol auto-detection and basic cleaning.
    
    Returns:
        (DataFrame, protocol_type)
    """
    # Read with case-insensitive column normalization
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip().str.lower()
    
    protocol = detect_protocol(df)
    
    # Common cleaning
    if 'timestamp_utc' in df.columns:
        df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'], format='ISO8601', errors='coerce')
    
    if 'rssi_dbm' in df.columns:
        df['rssi_dbm'] = pd.to_numeric(df['rssi_dbm'], errors='coerce')
    
    # GPS columns
    gps_cols = ['gps_lat', 'gps_lon', 'gps_alt_m', 'gps_fix', 'gps_num_sats', 'gps_hdop', 'gps_age_ms']
    for col in gps_cols:
        if col not in df.columns:
            df[col] = np.nan
        else:
            if col in ['gps_lat', 'gps_lon', 'gps_alt_m', 'gps_hdop']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            elif col in ['gps_fix', 'gps_num_sats', 'gps_age_ms']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
    
    # Filter invalid GPS (0 or NaN lat/lon)
    df.loc[(df['gps_lat'].isna()) | (df['gps_lat'] == 0), 'gps_lat'] = np.nan
    df.loc[(df['gps_lon'].isna()) | (df['gps_lon'] == 0), 'gps_lon'] = np.nan
    
    # Protocol-specific defaults
    if protocol == 'ble':
        # Ensure BLE columns have defaults
        if 'company_name' not in df.columns:
            df['company_name'] = ''
        if 'company_id' not in df.columns:
            df['company_id'] = ''
        if 'address_type' not in df.columns:
            df['address_type'] = ''
        if 'tx_power' not in df.columns:
            df['tx_power'] = np.nan
        else:
            df['tx_power'] = pd.to_numeric(df['tx_power'], errors='coerce')
        if 'flags' not in df.columns:
            df['flags'] = ''
        
        # Fill NaN strings
        df['company_name'] = df['company_name'].fillna('').astype(str)
        df['company_id'] = df['company_id'].fillna('').astype(str)
        df['address_type'] = df['address_type'].fillna('').astype(str)
        df['flags'] = df['flags'].fillna('').astype(str)
    
    return df, protocol


def extract_heartbeats(df: pd.DataFrame, protocol: str) -> pd.DataFrame:
    """
    Extract heartbeat rows for GPS tracking.
    
    For WiFi: frame_type == 'heartbeat'
    For BLE: event_type == 'heartbeat'
    """
    if protocol == 'wifi':
        if 'frame_type' in df.columns:
            return df[df['frame_type'] == 'heartbeat'].copy()
    elif protocol == 'ble':
        if 'event_type' in df.columns:
            return df[df['event_type'] == 'heartbeat'].copy()
    
    return pd.DataFrame()


def filter_valid_data(df: pd.DataFrame, protocol: str) -> pd.DataFrame:
    """
    Filter to rows with valid MAC addresses and RSSI (exclude heartbeats).
    
    Args:
        df: Input DataFrame
        protocol: 'wifi' or 'ble'
    
    Returns:
        Filtered DataFrame
    """
    if protocol == 'wifi':
        # WiFi uses src_mac
        mac_col = 'src_mac'
        frame_col = 'frame_type'
    else:
        # BLE uses address
        mac_col = 'address'
        frame_col = 'event_type'
    
    if mac_col not in df.columns:
        return df
    
    # Keep rows with valid MAC and RSSI
    mask = (
        df[mac_col].notna() & 
        (df[mac_col] != '') & 
        df['rssi_dbm'].notna()
    )
    
    # OR heartbeats (for map visualization)
    if frame_col in df.columns:
        mask |= (df[frame_col] == 'heartbeat')
    
    return df[mask].copy()


def resolve_vendor(mac: str) -> str:
    """
    Resolve vendor from MAC address OUI.
    
    Returns vendor name or OUI prefix if not found.
    """
    if pd.isna(mac) or not mac:
        return ""
    
    try:
        from mac_vendor_lookup import MacLookup
        mac_lookup = MacLookup()
        vendor = mac_lookup.lookup(mac)
        
        # Skip if result is just hex (e.g., "3A:46:32")
        if ":" in vendor and all(c in "0123456789ABCDEF:" for c in vendor.upper()):
            return mac[:8]  # Return OUI prefix
        
        return vendor
    except:
        # Fall back to OUI prefix
        return mac[:8] if len(mac) >= 8 else mac


def is_randomized_mac(mac: str) -> bool:
    """
    Check if MAC address is randomized (LAA bit set).
    
    Locally Administered Address (LAA) has bit 1 of first octet set.
    """
    if pd.isna(mac) or not mac or len(mac) < 2:
        return False
    
    try:
        first_octet = int(mac.split(':')[0], 16)
        return bool(first_octet & 0x02)  # Check bit 1
    except:
        return False


def prepare_map_data(df: pd.DataFrame, protocol: str) -> pd.DataFrame:
    """
    Prepare DataFrame for map visualization.
    
    Includes both device locations and heartbeat route.
    """
    # Filter to rows with valid GPS
    map_df = df[df['gps_lat'].notna() & df['gps_lon'].notna()].copy()
    
    if map_df.empty:
        return map_df
    
    # Add is_heartbeat flag
    if protocol == 'wifi':
        map_df['is_heartbeat'] = (map_df.get('frame_type', '') == 'heartbeat')
    else:
        map_df['is_heartbeat'] = (map_df.get('event_type', '') == 'heartbeat')
    
    # Sort by time for route drawing
    if 'timestamp_utc' in map_df.columns:
        map_df = map_df.sort_values('timestamp_utc')
    
    return map_df


def get_mac_column(protocol: str) -> str:
    """Return the MAC address column name for the protocol."""
    return 'src_mac' if protocol == 'wifi' else 'address'


def get_frame_type_column(protocol: str) -> str:
    """Return the frame/event type column name for the protocol."""
    return 'frame_type' if protocol == 'wifi' else 'event_type'
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees).
    """
    # Convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula 
    dlat = lat2 - lat1 
    dlon = lon2 - lon1 
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a)) 
    r = 6371000 # Radius of earth in meters
    return c * r


def calculate_3d_distance(lat1: float, lon1: float, alt1: float, lat2: float, lon2: float, alt2: float) -> float:
    """
    Calculate 3D Euclidean distance (slant range) between two GPS points.
    """
    ground_dist = haversine_distance(lat1, lon1, lat2, lon2)
    alt_diff = alt1 - alt2
    return np.sqrt(ground_dist**2 + alt_diff**2)
