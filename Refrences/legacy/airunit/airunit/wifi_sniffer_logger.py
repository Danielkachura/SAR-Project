#!/usr/bin/env python3
"""
Wi-Fi sniffer + GPS logger.

- Uses tcpdump in monitor mode on wlan1.
- Captures all management frames (beacons, probes, assoc/reassoc, auth/deauth/disassoc, action).
- Writes BOTH:
    * CSV with lightweight fields
    * PCAP per run for offline analysis
- Optional channel hopping (configurable list, dwell time, on/off).
- Prints status every ~3 seconds and a final summary (frames + elapsed).
"""

import csv
import datetime as dt
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import config
from gps_service import start_gps

SSID_RE = re.compile(
    r"(?:Probe (?:Request|Response)|Beacon|Association Request|Reassociation Request) \((.*?)\)"
)


def ensure_root():
    if os.geteuid() != 0:
        sys.exit("Run as root: sudo python3 wifi_sniffer_logger.py")


def configure_monitor_interface(channel: int):
    iface = config.WIFI_MONITOR_INTERFACE
    print(f"[wifi] Configuring {iface} as monitor on channel {channel}...")

    cmds = [
        ["ip", "link", "set", iface, "down"],
        ["iw", "dev", iface, "set", "type", "monitor"],
        ["ip", "link", "set", iface, "up"],
        ["iw", "dev", iface, "set", "channel", str(channel)],
    ]

    for cmd in cmds:
        print("[wifi]> ", " ".join(cmd))
        subprocess.run(cmd, check=True)

    print(f"[wifi] {iface} set to monitor mode on channel {channel}")


def create_log_files():
    Path(config.LOG_DIR).mkdir(exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    csv_path = config.LOG_DIR / f"{config.LOG_FILE_PREFIX}{ts}Z.csv"
    pcap_path = config.LOG_DIR / f"{config.LOG_FILE_PREFIX}{ts}Z.pcap"

    csv_file = open(csv_path, "w", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=config.FIELDNAMES)
    writer.writeheader()

    print(f"[wifi] Logging CSV to {csv_path}")
    print(f"[wifi] Writing PCAP to {pcap_path}")
    return csv_file, writer, pcap_path


def status_printer_thread(stats: Dict[str, int], gps_state: Any, hop_state: Dict[str, int], stop_event: threading.Event):
    while not stop_event.is_set():
        stop_event.wait(3)
        if stop_event.is_set():
            break
        count = stats["frames"]
        gps = gps_state.get()
        fix = gps.get("gps_fix", 0)
        lat = gps.get("gps_lat")
        lon = gps.get("gps_lon")
        pos_str = f"{lat:.5f}, {lon:.5f}" if (lat is not None and lon is not None) else "No Fix"
        ch = hop_state.get("channel")
        print(f"[status] Packets: {count} | GPS Fix: {fix} | Pos: {pos_str} | Chan: {ch}")


def channel_hopper_thread(iface: str, channels, interval: float, state: Dict[str, int], stop_event: threading.Event):
    idx = 0
    while not stop_event.is_set():
        ch = channels[idx % len(channels)]
        try:
            subprocess.run(
                ["iw", "dev", iface, "set", "channel", str(ch)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            state["channel"] = ch
        except Exception as e:
            print(f"[wifi] hopper error on channel {ch}: {e}")
        if stop_event.wait(interval):
            break
        idx += 1


def heartbeat_thread(writer, csv_file, gps_state: Any, hop_state: Dict[str, int], stop_event: threading.Event, interval: float):
    while not stop_event.is_set():
        if stop_event.wait(interval):
            break
        timestamp_iso = (
            dt.datetime.now(dt.timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        ch = hop_state.get("channel", config.HOP_BASE_CHANNEL)
        freq_mhz = 2412 + 5 * (ch - 1)
        base_row = {
            "timestamp_utc": timestamp_iso,
            "frame_type": "heartbeat",
            "src_mac": "",
            "dst_mac": "",
            "bssid": "",
            "ssid": "",
            "rssi_dbm": "",
            "channel": ch,
            "freq_mhz": freq_mhz,
        }
        gps_data = gps_state.get()
        row = {**base_row, **gps_data}
        writer.writerow(row)
        csv_file.flush()


def classify_frame(line: str) -> str:
    if "Probe Request" in line:
        return "probe-req"
    if "Probe Response" in line:
        return "probe-resp"
    if "Beacon" in line:
        return "beacon"
    if "Association Request" in line:
        return "assoc-req"
    if "Association Response" in line:
        return "assoc-resp"
    if "Reassociation Request" in line:
        return "reassoc-req"
    if "Reassociation Response" in line:
        return "reassoc-resp"
    if "Deauthentication" in line:
        return "deauth"
    if "Disassociation" in line:
        return "disassoc"
    if "Authentication" in line:
        return "auth"
    if "Action" in line:
        return "action"
    return "unknown"


def parse_tcpdump_line(line: str, current_channel: int) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None

    if line.startswith(("tcpdump:", "reading from", "listening on")):
        print("[tcpdump]", line)
        return None

    parts = line.split()
    if not parts:
        return None

    try:
        ts_epoch = float(parts[0])
        timestamp_iso = (
            dt.datetime.fromtimestamp(ts_epoch, dt.timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    except Exception:
        timestamp_iso = (
            dt.datetime.now(dt.timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )

    frame_type = classify_frame(line)

    macs = {}
    for token in parts:
        if token.startswith(("SA:", "TA:", "DA:", "RA:", "BSSID:")):
            key, val = token.split(":", 1)
            macs[key.lower()] = val

    m = SSID_RE.search(line)
    ssid = m.group(1) if m else ""
    if ssid == r"\x00":
        ssid = ""

    rssi = None
    for token in parts:
        if token.endswith("dBm"):
            try:
                rssi = int(token[:-3])
                break
            except Exception:
                continue

    freq_mhz = 2412 + 5 * (current_channel - 1)  # simple 2.4 GHz map for 2.4 GHz band

    return {
        "timestamp_utc": timestamp_iso,
        "frame_type": frame_type,
        "src_mac": macs.get("sa", ""),
        "dst_mac": macs.get("da", ""),
        "bssid": macs.get("bssid", ""),
        "ssid": ssid,
        "rssi_dbm": rssi if rssi is not None else "",
        "channel": current_channel,
        "freq_mhz": freq_mhz,
    }


def main():
    ensure_root()

    capture_start = time.monotonic()
    stats = {"frames": 0}

    # GPS
    print("[gps] Starting GPS service thread...")
    gps_state, gps_stop, gps_thread = start_gps()

    # Channel hopping state
    hop_state = {"channel": config.HOP_BASE_CHANNEL}
    hopper_stop = None
    hopper_thread = None

    # Configure monitor interface on base channel (for initial setup)
    configure_monitor_interface(config.HOP_BASE_CHANNEL)

    # Start hopper if enabled
    if config.HOP_ENABLED:
        print(f"[wifi] Channel hopping ENABLED: {config.HOP_CHANNELS} @ {config.HOP_INTERVAL_SEC}s")
        hopper_stop = threading.Event()
        hopper_thread = threading.Thread(
            target=channel_hopper_thread,
            args=(
                config.WIFI_MONITOR_INTERFACE,
                config.HOP_CHANNELS,
                config.HOP_INTERVAL_SEC,
                hop_state,
                hopper_stop,
            ),
            daemon=True,
        )
        hopper_thread.start()
    else:
        print(f"[wifi] Channel hopping DISABLED; fixed on channel {config.HOP_BASE_CHANNEL}")
        hop_state["channel"] = config.HOP_BASE_CHANNEL

    # Status thread
    status_stop = threading.Event()
    status_thread = threading.Thread(
        target=status_printer_thread,
        args=(stats, gps_state, hop_state, status_stop),
        daemon=True,
    )
    status_thread.start()

    # Logs
    csv_file, writer, pcap_path = create_log_files()

    # Heartbeat thread (periodic no-signal rows)
    heartbeat_stop = None
    heartbeat_thread_obj = None
    if getattr(config, "HEARTBEAT_ENABLED", False):
        heartbeat_stop = threading.Event()
        heartbeat_thread_obj = threading.Thread(
            target=heartbeat_thread,
            args=(writer, csv_file, gps_state, hop_state, heartbeat_stop, config.HEARTBEAT_INTERVAL_SEC),
            daemon=True,
        )
        heartbeat_thread_obj.start()

    # Build capture pipeline: tcpdump -> tee -> tcpdump text
    iface = config.WIFI_MONITOR_INTERFACE
    capture_cmd = [
        "tcpdump",
        "-i",
        iface,
        "-e",
        "-s",
        "256",
        "-tt",
        "-U",
        "-w",
        "-",
        "type",
        "mgt",
    ]
    text_cmd = [
        "tcpdump",
        "-tt",
        "-e",
        "-r",
        "-",
    ]
    pipeline = f"{' '.join(capture_cmd)} | tee {pcap_path} | {' '.join(text_cmd)}"

    print("[wifi] Starting capture pipeline:")
    print(" ", pipeline)

    proc = subprocess.Popen(
        pipeline,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    try:
        for line in proc.stdout:
            current_channel = hop_state.get("channel", config.HOP_BASE_CHANNEL)
            parsed_wifi = parse_tcpdump_line(line, current_channel)
            if not parsed_wifi:
                continue

            gps_data = gps_state.get()
            row = {**parsed_wifi, **gps_data}
            writer.writerow(row)
            csv_file.flush()
            stats["frames"] += 1
    except KeyboardInterrupt:
        print("\n[+] KeyboardInterrupt – stopping sniffer...")
    finally:
        print("[wifi] Shutting down tcpdump + GPS + hopper...")
        proc.terminate()
        status_stop.set()
        status_thread.join(timeout=2)
        if hopper_stop:
            hopper_stop.set()
        if hopper_thread:
            hopper_thread.join(timeout=2)
        if heartbeat_stop:
            heartbeat_stop.set()
        if heartbeat_thread_obj:
            heartbeat_thread_obj.join(timeout=2)
        gps_stop.set()
        gps_thread.join(timeout=2)
        csv_file.close()

        elapsed_s = time.monotonic() - capture_start
        print(f"[+] Sniffer stopped cleanly. Frames captured: {stats['frames']}, elapsed: {elapsed_s:.1f}s")
        print(f"[+] CSV: {csv_file.name}")
        print(f"[+] PCAP: {pcap_path}")


if __name__ == "__main__":
    main()
