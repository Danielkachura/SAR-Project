import io
import os
import shutil
import subprocess
from datetime import timezone
from collections import defaultdict

import pandas as pd


def _find_tshark():
    # First check if tshark is in PATH
    tshark = shutil.which("tshark")
    if tshark:
        return tshark
    
    # Check common Windows Wireshark installation paths
    common_paths = [
        r"C:\Program Files\Wireshark\tshark.exe",
        r"C:\Program Files (x86)\Wireshark\tshark.exe",
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    return None


def _extract_ssid_with_scapy(pcap_path):
    """
    Extract SSIDs directly from PCAP using scapy to preserve non-ASCII (Hebrew, etc).
    Returns dict: src_mac -> most common SSID for that MAC
    
    Args:
        pcap_path: Path to PCAP file
    """

    try:
        import logging
        logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
        from scapy.all import Dot11, Dot11Elt, PcapReader
    except Exception as e:
        return {}

    ssid_by_mac = defaultdict(list)
    try:
        with PcapReader(pcap_path) as reader:
            for pkt in reader:
                if not pkt.haslayer(Dot11):
                    continue
                dot11 = pkt[Dot11]
                src_mac = (dot11.addr2 or "").lower()
                if not src_mac:
                    continue

                # Extract SSID from IE element (ID=0)
                elt = pkt.getlayer(Dot11Elt)
                while elt is not None:
                    eid = int(getattr(elt, "ID", -1))
                    if eid == 0:
                        ssid_bytes = bytes(getattr(elt, "info", b""))
                        if ssid_bytes:
                            ssid = ssid_bytes.decode("utf-8", errors="replace")
                            ssid_by_mac[src_mac].append(ssid)
                        break
                    elt = elt.payload.getlayer(Dot11Elt)
    except Exception as e:
        pass

    # Return most common SSID per MAC
    result = {}
    for mac, ssids in ssid_by_mac.items():
        if ssids:
            from collections import Counter
            result[mac] = Counter(ssids).most_common(1)[0][0]

    return result



def _extract_with_tshark(pcap_path):
    tshark = _find_tshark()
    if not tshark:
        return None

    cmd = [
        tshark,
        "-r",
        pcap_path,
        "-T",
        "fields",
        "-E",
        "header=y",
        "-E",
        "separator=,",
        "-E",
        "quote=d",
        "-E",
        "occurrence=a",
        "-e",
        "frame.time_epoch",
        "-e",
        "wlan.sa",
        "-e",
        "wlan.da",
        "-e",
        "wlan.bssid",
        "-e",
        "wlan.fc.type_subtype",
        "-e",
        "wlan.seq",
        "-e",
        "wlan.fc.frag",
        "-e",
        "frame.len",
        "-e",
        "wlan.tag.number",
        "-e",
        "wlan.ssid",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "tshark failed to parse pcap.")

    if not result.stdout.strip():
        return pd.DataFrame(
            columns=[
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
        )

    df = pd.read_csv(io.StringIO(result.stdout))
    rename_map = {
        "frame.time_epoch": "timestamp_epoch",
        "wlan.sa": "src_mac",
        "wlan.da": "dst_mac",
        "wlan.bssid": "bssid",
        "wlan.fc.type_subtype": "fc_type_subtype",
        "wlan.seq": "seq_num",
        "wlan.fc.frag": "frag_num",
        "frame.len": "frame_len",
        "wlan.tag.number": "ie_ids",
        "wlan.ssid": "ssid",
    }
    df = df.rename(columns=rename_map)

    df["timestamp_utc"] = pd.to_datetime(df["timestamp_epoch"], unit="s", utc=True, errors="coerce")
    df["src_mac"] = df["src_mac"].astype(str).str.lower()
    df["dst_mac"] = df["dst_mac"].astype(str).str.lower()
    df["bssid"] = df["bssid"].astype(str).str.lower()

    def _map_subtype(val):
        try:
            num = int(str(val), 0)
        except Exception:
            return "unknown"
        return {4: "probe-req", 5: "probe-resp", 8: "beacon", 11: "auth", 13: "action"}.get(num, "unknown")

    if "fc_type_subtype" in df.columns:
        df["frame_type_pcap"] = df["fc_type_subtype"].apply(_map_subtype)
    else:
        df["frame_type_pcap"] = "unknown"

    df["seq_num"] = pd.to_numeric(df.get("seq_num"), errors="coerce")
    df["frag_num"] = pd.to_numeric(df.get("frag_num"), errors="coerce")
    df["seq_ctl"] = df["seq_num"] * 16 + df["frag_num"].fillna(0)

    df["frame_len"] = pd.to_numeric(df.get("frame_len"), errors="coerce")
    df["ie_ids"] = df.get("ie_ids", "").fillna("").astype(str)
    df["ie_fingerprint"] = ""
    df["ie_vendor_ouis"] = ""

    # Extract clean SSIDs from PCAP via scapy to preserve Hebrew and other non-ASCII
    scapy_ssids = _extract_ssid_with_scapy(pcap_path)
    if scapy_ssids:
        # Replace ALL tshark SSIDs with scapy's clean versions where available
        # (scapy decodes IE element 0 directly as UTF-8, avoiding tshark mojibake)
        df['ssid'] = df['src_mac'].map(scapy_ssids).fillna(df['ssid'])

    df = df.drop(columns=["timestamp_epoch", "seq_num", "frag_num", "fc_type_subtype"], errors="ignore")
    return df


def _extract_with_scapy(pcap_path):
    try:
        import logging
        logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
        from scapy.all import Dot11, Dot11Elt, PcapReader
    except Exception as exc:
        raise RuntimeError("scapy not available. Install with: python -m pip install scapy") from exc

    ie_keep_ids = {1, 50, 45, 61, 127, 191, 192, 221}

    def build_ie_features(pkt):
        ids, fingerprint_parts, vendor_ouis = [], [], []
        ssid_bytes = b""
        elt = pkt.getlayer(Dot11Elt)
        while elt is not None:
            eid = int(getattr(elt, "ID", -1))
            info = bytes(getattr(elt, "info", b""))
            if eid == 0:
                ssid_bytes = info
            if eid in ie_keep_ids:
                ids.append(str(eid))
                fingerprint_parts.append(f"{eid}:{info.hex()}")
                if eid == 221 and len(info) >= 3:
                    vendor_ouis.append(info[:3].hex())
            elt = elt.payload.getlayer(Dot11Elt)
        return ",".join(ids), ";".join(fingerprint_parts), ",".join(vendor_ouis), ssid_bytes

    rows = []
    pkt_count = 0
    with PcapReader(pcap_path) as reader:
        for pkt in reader:
            pkt_count += 1
            if not pkt.haslayer(Dot11):
                continue
            dot11 = pkt[Dot11]
            ts = getattr(pkt, "time", None)
            if ts is None:
                continue
            ie_ids, ie_fingerprint, ie_vendor_ouis, ssid_bytes = build_ie_features(pkt)
            rows.append(
                {
                    "timestamp_utc": pd.to_datetime(float(ts), unit="s", utc=True, errors="coerce"),
                    "src_mac": (dot11.addr2 or "").lower(),
                    "dst_mac": (dot11.addr1 or "").lower(),
                    "bssid": (dot11.addr3 or "").lower(),
                    "seq_ctl": getattr(dot11, "SC", None),
                    "frame_len": len(pkt),
                    "ie_ids": ie_ids,
                    "ie_fingerprint": ie_fingerprint,
                    "ie_vendor_ouis": ie_vendor_ouis,
                    "ssid": ssid_bytes.decode("utf-8", errors="replace"),
                }
            )
    
    if not rows:
        return pd.DataFrame(
            columns=[
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
        )
    return pd.DataFrame(rows)


def extract_pcap_features(pcap_path):
    df = _extract_with_tshark(pcap_path)
    if df is not None:
        # Extract clean SSIDs from PCAP via scapy to preserve Hebrew and other non-ASCII
        scapy_ssids = _extract_ssid_with_scapy(pcap_path)
        if scapy_ssids:
            # Replace ALL tshark SSIDs with scapy's clean versions where available
            df['ssid'] = df['src_mac'].map(scapy_ssids).fillna(df['ssid'])
        return df
    return _extract_with_scapy(pcap_path)
