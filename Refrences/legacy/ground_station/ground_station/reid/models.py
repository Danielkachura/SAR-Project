from dataclasses import dataclass, field
from typing import Dict, Any, Set, List
from datetime import datetime

@dataclass
class ReidConfig:
    # --- Core Weights (Total 0.8) ---
    # --- Core Weights (Total 0.8) ---
    # A mismatch in these fields results in a score penalty (0 points for that component).
    w_ie_total: float = 0.75  # Distributed across 5 tags
    w_frame_len: float = 0.2

    # --- Bonus Weights (Total 0.2) ---
    # These increase confidence. A mismatch is neutral.
    w_ssid_bonus: float = 0.1
    w_seq_bonus: float = 0.05

    # IE Tags to fingerprint
    # Tags: 1 (Rates), 50 (Ext Rates), 45 (HT), 127 (Ext Caps), 221 (Vendor)
    ie_tags_to_check: List[int] = field(default_factory=lambda: [1, 50, 45, 127, 221])

    # --- Thresholds ---
    match_threshold: float = 0.8
    sanity_time_window_sec: float = 5.0
    sanity_rssi_diff_db: float = 30.0
    
    # Fuzzy Matching Threshold for IE Tags (0.0 to 1.0)
    # If bitwise similarity > threshold, we count it as a "close match" scaled by similarity.
    ie_similarity_threshold: float = 0.90
    
    # Sequence number rollover for 802.11 is 4096
    seq_modulus: int = 4096

@dataclass
class DeviceCluster:
    cluster_id: int
    is_global_mac: bool
    
    # Signature vector:
    # {
    #   'ies': {tag_id: hex_str, ...},
    #   'frame_len': float,
    #   'ssid': str or None,
    #   'last_seq': int
    # }
    signature_vector: Dict[str, Any]
    
    # State tracking
    last_seen_timestamp: datetime
    last_rssi: float
    packet_count: int = 0
    
    # Member MACs (for debugging and local history tracking)
    member_macs: Set[str] = field(default_factory=set)

    def update(self, timestamp: datetime, rssi: float, mac: str, seq_num: int = None):
        """Update cluster state with new observation."""
        if timestamp >= self.last_seen_timestamp:
            self.last_seen_timestamp = timestamp
            self.last_rssi = rssi
            if seq_num is not None:
                self.signature_vector['last_seq'] = seq_num
        self.packet_count += 1
        self.member_macs.add(mac)
