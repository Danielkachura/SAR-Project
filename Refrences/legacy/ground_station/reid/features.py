import pandas as pd
import numpy as np

def normalize_columns(df):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def is_global_mac(mac: str) -> bool:
    """
    Check if MAC is Global (Universal) or Locally Administered.
    Bit 1 of first byte: 0 = Universal (Global), 1 = Local.
    """
    try:
        if pd.isna(mac): return False
        clean_mac = str(mac).replace(":", "").replace("-", "").replace(".", "")
        if not clean_mac: return False
        first_byte = int(clean_mac[:2], 16)
        # Check Local bit (0x02). If 0, it is Global.
        return (first_byte & 0x02) == 0
    except Exception:
        return False

def parse_ie_fingerprint(fingerprint_str, tags_to_extract):
    """
    Parse ie_fingerprint 'ID:HEX;ID:HEX...' and extract specific tags.
    Returns dict {tag_id: hex_string or None}.
    """
    elements = {}
    if pd.isna(fingerprint_str) or not fingerprint_str:
        return {t: None for t in tags_to_extract}
    
    # Parse available tags
    parsed = {}
    parts = str(fingerprint_str).split(';')
    for part in parts:
        if ':' in part:
            try:
                ie_id_str, val = part.split(':', 1)
                parsed[int(ie_id_str)] = val.strip().lower()
            except ValueError:
                continue
    
    # Fill requested
    for tag in tags_to_extract:
        elements[tag] = parsed.get(tag)
        
    return elements

def extract_feature_vector(row, tags_to_extract=None):
    """
    Extracts features for Hierarchical Clustering.
    """
    if tags_to_extract is None:
        # Default tags as per new config
        tags_to_extract = [1, 50, 45, 127, 221]

    src_mac = str(row.get("src_mac", "")).lower() if pd.notna(row.get("src_mac")) else None
    
    # 1. Global Check
    # "Check the U/L bit (2nd bit of the 1st byte). If 0, flag is_global = True."
    is_global = is_global_mac(src_mac)
    
    # 2. IE Extraction
    ie_str = row.get("ie_fingerprint")
    ies = parse_ie_fingerprint(ie_str, tags_to_extract)
    
    # 3. Frame Length
    f_len = row.get("frame_len", None)
    if pd.notna(f_len):
        f_len = float(f_len)
    else:
        f_len = None
        
    # 4. SSID
    raw_ssid = row.get("ssid", None)
    ssid = None
    if pd.notna(raw_ssid):
        s = str(raw_ssid).strip()
        if s and s.lower() not in ["", "guest", "nan", "broadcast"]:
            ssid = s
            
    # 5. Sequence Number
    seq = row.get("seq_num", None)
    if pd.notna(seq):
        try:
            seq = int(float(seq))
        except:
            seq = None
            
    return {
        "src_mac": src_mac,
        "is_global": is_global,
        "timestamp": row.get("timestamp_utc"),
        "rssi": row.get("rssi_dbm"),
        "vector": {
            "ies": ies,
            "frame_len": f_len,
            "ssid": ssid,
            "seq_num": seq
        }
    }

def load_scan_csv(path):
    df = pd.read_csv(path)
    df = normalize_columns(df)
    if "timestamp_utc" in df.columns:
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], errors="coerce", utc=True)
    return df
