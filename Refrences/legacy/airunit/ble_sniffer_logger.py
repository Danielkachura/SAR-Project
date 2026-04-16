#!/usr/bin/env python3
"""
BLE sniffer + GPS logger.

- Uses btmon to capture BLE advertising packets.
- Writes BOTH:
    * CSV with lightweight fields
    * PCAP per run for offline analysis
- Prints status every ~3 seconds and a final summary (packets + elapsed).
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


def ensure_root():
    if os.geteuid() != 0:
        sys.exit("Run as root: sudo python3 ble_sniffer_logger.py")


def create_log_files():
    Path(config.LOG_DIR).mkdir(exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    csv_path = config.LOG_DIR / f"ble_{ts}Z.csv"
    pcap_path = config.LOG_DIR / f"ble_{ts}Z.pcap"

    csv_file = open(csv_path, "w", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=config.BLE_FIELDNAMES)
    writer.writeheader()

    print(f"[ble] Logging CSV to {csv_path}")
    print(f"[ble] Writing PCAP to {pcap_path}")
    return csv_file, writer, pcap_path


def status_printer_thread(stats: Dict[str, int], gps_state: Any, stop_event: threading.Event):
    while not stop_event.is_set():
        stop_event.wait(3)
        if stop_event.is_set():
            break
        count = stats["packets"]
        gps = gps_state.get()
        fix = gps.get("gps_fix", 0)
        lat = gps.get("gps_lat")
        lon = gps.get("gps_lon")
        pos_str = f"{lat:.5f}, {lon:.5f}" if (lat is not None and lon is not None) else "No Fix"
        print(f"[status] BLE Packets: {count} | GPS Fix: {fix} | Pos: {pos_str}")


def heartbeat_thread(writer, csv_file, gps_state: Any, stop_event: threading.Event, interval: float):
    while not stop_event.is_set():
        if stop_event.wait(interval):
            break
        timestamp_iso = (
            dt.datetime.now(dt.timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        base_row = {
            "timestamp_utc": timestamp_iso,
            "event_type": "heartbeat",
            "address": "",
            "address_type": "",
            "rssi_dbm": "",
            "company_id": "",
            "company_name": "",
            "adv_data_hex": "",
            "flags": "",
            "tx_power": "",
        }
        gps_data = gps_state.get()
        row = {**base_row, **gps_data}
        writer.writerow(row)
        csv_file.flush()


def parse_btmon_line(line: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse btmon text output for LE Advertising Report events.
    
    Example btmon output:
    > HCI Event: LE Meta Event (0x3e) plen 43                   #5 [hci0] 43.841640
          LE Advertising Report (0x02)
            Num reports: 1
            Event type: Non connectable undirected - ADV_NONCONN_IND (0x03)
            Address type: Random (0x01)
            Address: 26:49:B3:1C:DA:E2 (Non-Resolvable)
            Data length: 31
            Company: Microsoft (6)
              Data[27]: 01092022713d311f9992ebe7e4ff595aa8629c1861c2bd3ecc5ed8
            RSSI: -47 dBm (0xd1)
    """
    line = line.strip()
    if not line:
        return None

    # Detect start of new advertising report
    if "LE Advertising Report" in line:
        context["in_report"] = True
        context["current"] = {}
        return None
    
    if not context.get("in_report"):
        return None

    # Parse event type
    if "Event type:" in line:
        match = re.search(r"Event type: (.+?) - (\w+)", line)
        if match:
            context["current"]["event_type"] = match.group(2)
    
    # Parse address
    elif line.startswith("Address:"):
        match = re.search(r"Address: ([0-9A-F:]+)(?: \((.+?)\))?", line)
        if match:
            context["current"]["address"] = match.group(1)
            if match.group(2):
                context["current"]["address_type"] = match.group(2)
    
    # Parse address type
    elif "Address type:" in line:
        match = re.search(r"Address type: (.+?) \(", line)
        if match:
            context["current"]["address_type"] = match.group(1)
    
    # Parse company
    elif line.startswith("Company:"):
        match = re.search(r"Company: (.+?) \((\d+)\)", line)
        if match:
            context["current"]["company_name"] = match.group(1)
            context["current"]["company_id"] = match.group(2)
    
    # Parse advertising data
    elif "Data[" in line and ":" in line:
        match = re.search(r"Data\[\d+\]: ([0-9a-f]+)", line)
        if match:
            existing = context["current"].get("adv_data_hex", "")
            context["current"]["adv_data_hex"] = existing + match.group(1)
    
    # Parse flags
    elif line.startswith("Flags:"):
        match = re.search(r"Flags: (0x[0-9a-f]+)", line)
        if match:
            context["current"]["flags"] = match.group(1)
    
    # Parse TX power
    elif "TX power:" in line:
        match = re.search(r"TX power: (-?\d+) dBm", line)
        if match:
            context["current"]["tx_power"] = match.group(1)
    
    # Parse RSSI (end of report)
    elif "RSSI:" in line:
        match = re.search(r"RSSI: (-?\d+) dBm", line)
        if match:
            context["current"]["rssi_dbm"] = match.group(1)
        
        # End of report - emit the parsed data
        timestamp_iso = (
            dt.datetime.now(dt.timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        
        result = {
            "timestamp_utc": timestamp_iso,
            "event_type": context["current"].get("event_type", ""),
            "address": context["current"].get("address", ""),
            "address_type": context["current"].get("address_type", ""),
            "rssi_dbm": context["current"].get("rssi_dbm", ""),
            "company_id": context["current"].get("company_id", ""),
            "company_name": context["current"].get("company_name", ""),
            "adv_data_hex": context["current"].get("adv_data_hex", ""),
            "flags": context["current"].get("flags", ""),
            "tx_power": context["current"].get("tx_power", ""),
        }
        
        context["in_report"] = False
        context["current"] = {}
        return result
    
    return None


def start_ble_scan():
    """Start BLE scanning using hcitool."""
    iface = getattr(config, "BLE_HCI_INTERFACE", "hci0")
    print(f"[ble] Starting LE scan on {iface}...")
    
    # Start scanning with hcitool (passive scan, no duplicates filter)
    cmd = ["hcitool", "-i", iface, "lescan", "--duplicates"]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def main():
    ensure_root()

    capture_start = time.monotonic()
    stats = {"packets": 0}

    # GPS
    print("[gps] Starting GPS service thread...")
    gps_state, gps_stop, gps_thread = start_gps()

    # Status thread
    status_stop = threading.Event()
    status_thread = threading.Thread(
        target=status_printer_thread,
        args=(stats, gps_state, status_stop),
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
            args=(writer, csv_file, gps_state, heartbeat_stop, config.HEARTBEAT_INTERVAL_SEC),
            daemon=True,
        )
        heartbeat_thread_obj.start()

    # Start BLE scan
    scan_proc = start_ble_scan()
    time.sleep(1)  # Give hcitool time to start

    # Start btmon with PCAP output
    iface = getattr(config, "BLE_HCI_INTERFACE", "hci0")
    hci_num = iface.replace("hci", "")
    btmon_cmd = ["btmon", "-i", hci_num, "-w", str(pcap_path)]
    
    print(f"[ble] Starting btmon: {' '.join(btmon_cmd)}")
    print(f"[ble] BLE sniffer running - watching for LE Advertising Reports...")
    
    btmon_proc = subprocess.Popen(
        btmon_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    parse_context = {"in_report": False, "current": {}}

    try:
        for line in btmon_proc.stdout:
            parsed_ble = parse_btmon_line(line, parse_context)
            if not parsed_ble:
                continue

            gps_data = gps_state.get()
            row = {**parsed_ble, **gps_data}
            writer.writerow(row)
            csv_file.flush()
            stats["packets"] += 1
    except KeyboardInterrupt:
        print("\n[+] KeyboardInterrupt – stopping BLE sniffer...")
    finally:
        print("[ble] Shutting down btmon + scan + GPS...")
        btmon_proc.terminate()
        scan_proc.terminate()
        status_stop.set()
        status_thread.join(timeout=2)
        if heartbeat_stop:
            heartbeat_stop.set()
        if heartbeat_thread_obj:
            heartbeat_thread_obj.join(timeout=2)
        gps_stop.set()
        gps_thread.join(timeout=2)
        csv_file.close()

        elapsed_s = time.monotonic() - capture_start
        print(f"[+] BLE sniffer stopped cleanly. Packets captured: {stats['packets']}, elapsed: {elapsed_s:.1f}s")
        print(f"[+] CSV: {csv_file.name}")
        print(f"[+] PCAP: {pcap_path}")


if __name__ == "__main__":
    main()
