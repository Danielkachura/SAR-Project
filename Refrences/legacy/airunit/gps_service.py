"""
Minimal GPS reader for /dev/ttyACM0.

- Reads NMEA sentences as plain text (like `cat /dev/ttyACM0`).
- Parses only GPGGA/GNGGA for position/altitude/fix.
- Keeps last state in a thread-safe object that the sniffer can query.
"""

import threading
import time
from typing import Optional, Dict, Any

import config


class GpsState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_update: Optional[float] = None

        self.lat: Optional[float] = None
        self.lon: Optional[float] = None
        self.alt: Optional[float] = None
        self.fix: int = 0
        self.sats: int = 0
        self.hdop: Optional[float] = None

    def update(
        self,
        lat: Optional[float],
        lon: Optional[float],
        alt: Optional[float],
        fix: int,
        sats: int,
        hdop: Optional[float],
    ) -> None:
        with self._lock:
            self.lat = lat
            self.lon = lon
            self.alt = alt
            self.fix = fix
            self.sats = sats
            self.hdop = hdop
            self._last_update = time.time()

    def get(self) -> Dict[str, Any]:
        with self._lock:
            if self._last_update is None:
                age_ms = None
            else:
                age_sec = time.time() - self._last_update
                age_ms = int(age_sec * 1000)

            return {
                "gps_lat": self.lat,
                "gps_lon": self.lon,
                "gps_alt_m": self.alt,
                "gps_fix": self.fix,
                "gps_num_sats": self.sats,
                "gps_hdop": self.hdop,
                "gps_age_ms": age_ms,
            }


def _to_deg(val: str, direction: str, is_lat: bool) -> Optional[float]:
    """Convert NMEA ddmm.mmmm or dddmm.mmmm to decimal degrees."""
    if not val or not direction:
        return None
    try:
        if is_lat:
            deg = int(val[:2])
            minutes = float(val[2:])
        else:
            deg = int(val[:3])
            minutes = float(val[3:])
        dec = deg + minutes / 60.0
        if direction in ("S", "W"):
            dec = -dec
        return dec
    except Exception:
        return None


def parse_gga(line: str):
    # Remove checksum
    if "*" in line:
        line = line.split("*", 1)[0]

    parts = line.split(",")
    if len(parts) < 10:
        return None

    lat_raw, lat_dir = parts[2], parts[3]
    lon_raw, lon_dir = parts[4], parts[5]
    fix_str = parts[6]
    sats_str = parts[7]
    hdop_str = parts[8]
    alt_str = parts[9]

    try:
        fix = int(fix_str)
    except Exception:
        fix = 0

    try:
        sats = int(sats_str)
    except Exception:
        sats = 0

    try:
        hdop = float(hdop_str)
    except Exception:
        hdop = None

    try:
        alt = float(alt_str)
    except Exception:
        alt = None

    lat = _to_deg(lat_raw, lat_dir, True)
    lon = _to_deg(lon_raw, lon_dir, False)

    return lat, lon, alt, fix, sats, hdop


def gps_thread(state: GpsState, stop_event: threading.Event) -> None:
    device = config.GPS_SERIAL_DEVICE
    baud = config.GPS_BAUDRATE

    print(f"[gps] Opening {device} @ {baud} (as plain text)")
    try:
        # Open as text; the kernel driver already handles baud rate etc.
        with open(device, "r", encoding="ascii", errors="ignore") as f:
            print("[gps] Device opened, reading NMEA...")
            while not stop_event.is_set():
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                line = line.strip()
                if not line:
                    continue

                # Commented out to reduce noise
                # print("NMEA:", line)

                if line.startswith(("$GPGGA", "$GNGGA")):
                    parsed = parse_gga(line)
                    if parsed:
                        lat, lon, alt, fix, sats, hdop = parsed
                        state.update(lat, lon, alt, fix, sats, hdop)
    except Exception as e:
        print("[gps] ERROR:", e)


def start_gps():
    state = GpsState()
    stop_event = threading.Event()
    t = threading.Thread(target=gps_thread, args=(state, stop_event), daemon=True)
    t.start()
    return state, stop_event, t


if __name__ == "__main__":
    st, stop, th = start_gps()
    try:
        while True:
            print("STATE:", st.get())
            time.sleep(2)
    except KeyboardInterrupt:
        stop.set()
        th.join()
