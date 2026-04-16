"""
Global configuration for the airunit Wi-Fi + GPS sniffer.
Single dongle as monitor on wlan1. Optional channel hopping.
"""

import os
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE_PREFIX = "scan_"

os.makedirs(LOG_DIR, exist_ok=True)

# --- Wi-Fi sniffer interface ---
WIFI_MONITOR_INTERFACE = "wlan1"

# Channel hopping controls
HOP_ENABLED = False           # Set False to stay on HOP_BASE_CHANNEL (overridden by control app)
HOP_CHANNELS = [1, 6, 11]     # Channels to rotate through when hopping
HOP_INTERVAL_SEC = 0.5        # Dwell time per channel (seconds)
HOP_BASE_CHANNEL = 1          # Used when hopping is disabled

# --- BLE sniffer interface ---
BLE_HCI_INTERFACE = "hci0"    # Bluetooth HCI interface for BLE scanning

# --- GPS settings ---
GPS_SERIAL_DEVICE = "/dev/ttyACM0"
GPS_BAUDRATE = 9600
MAX_GPS_AGE_SEC = 10.0

# --- Heartbeat (no-signal) logging ---
HEARTBEAT_ENABLED = True          # Emit periodic heartbeat rows even if no packets
HEARTBEAT_INTERVAL_SEC = 2.0      # Interval in seconds (e.g., 1–3s)

# --- CSV format (lightweight fields) ---
CSV_HEADER = (
    "timestamp_utc,"
    "frame_type,"
    "src_mac,"
    "dst_mac,"
    "bssid,"
    "ssid,"
    "rssi_dbm,"
    "channel,"
    "freq_mhz,"
    "gps_lat,"
    "gps_lon,"
    "gps_alt_m,"
    "gps_fix,"
    "gps_num_sats,"
    "gps_hdop,"
    "gps_age_ms"
)

FIELDNAMES = [f.strip() for f in CSV_HEADER.split(",") if f.strip()]

# --- BLE CSV format ---
BLE_CSV_HEADER = (
    "timestamp_utc,"
    "event_type,"
    "address,"
    "address_type,"
    "rssi_dbm,"
    "company_id,"
    "company_name,"
    "adv_data_hex,"
    "flags,"
    "tx_power,"
    "gps_lat,"
    "gps_lon,"
    "gps_alt_m,"
    "gps_fix,"
    "gps_num_sats,"
    "gps_hdop,"
    "gps_age_ms"
)

BLE_FIELDNAMES = [f.strip() for f in BLE_CSV_HEADER.split(",") if f.strip()]
