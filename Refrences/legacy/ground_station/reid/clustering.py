from datetime import timedelta
import math
from typing import List, Optional, Dict, Set
import pandas as pd
import numpy as np

from .models import DeviceCluster, ReidConfig

class OnlineClusterer:
    def __init__(self, config: ReidConfig):
        self.config = config
        self.active_clusters: List[DeviceCluster] = []
        self.next_cluster_id = 0
        
        # Maps MAC address to a Set of cluster_ids it has been associated with.
        # {mac: {cluster_id, ...}}
        self.mac_history: Dict[str, Set[int]] = {} 
        
        # Maps Global MACs to their single Cluster ID
        self.global_mac_map: Dict[str, int] = {}

    def _get_seq_delta(self, seq_new: int, seq_old: int) -> int:
        """Calculate forward distance between sequence numbers with modulo."""
        if seq_new is None or seq_old is None:
            return None
        diff = (seq_new - seq_old) % self.config.seq_modulus
        return diff

    def _compute_bitwise_similarity(self, hex_a: str, hex_b: str) -> float:
        """
        Compute similarity between two hex strings.
        - If lengths differ -> Return 0.0 (Strict on structure)
        - If lengths match -> Bitwise similarity (1 - diff_bits / total_bits)
        """
        if not hex_a or not hex_b:
            return 0.0
        
        # If lengths match, do bitwise XOR
        if len(hex_a) == len(hex_b):
            try:
                # Convert hex to bytes
                # (Integers are easier for XOR)
                int_a = int(hex_a, 16)
                int_b = int(hex_b, 16)
                
                xor_diff = int_a ^ int_b
                
                # Count set bits in the difference
                diff_bits = bin(xor_diff).count('1')
                
                # Total bits
                total_bits = len(hex_a) * 4 # 1 hex char = 4 bits
                
                if total_bits == 0: return 1.0 # Empty strings match
                
                return 1.0 - (diff_bits / total_bits)
            except ValueError:
                return 0.0 # Invalid hex
                
        return 0.0 # Length mismatch is structural mismatch

    def calculate_similarity(self, pkt_vec: dict, cls_vec: dict, packet_timestamp, cluster_timestamp, packet_rssi, cluster_rssi) -> float:
        """
        Calculate weighted score with physics sanity check.
        Returns score (0.0 to ~1.0+).
        """
        score = 0.0
        
        # --- Core Weights (Identity Anchors) ---
        
        # 1. IE Tags
        # Total Weight = 0.6. Distributed across tags.
        # Mismatch = 0 points (Penalty). Missing = Match (neutral/optimistic? User says "If both values are missing (None), they count as a match.")
        
        num_tags = len(self.config.ie_tags_to_check)
        weight_per_tag = self.config.w_ie_total / num_tags if num_tags > 0 else 0
        
        pkt_ies = pkt_vec.get('ies', {})
        cls_ies = cls_vec.get('ies', {})
        
        for tag in self.config.ie_tags_to_check:
            val_pkt = pkt_ies.get(tag)
            val_cls = cls_ies.get(tag)
            
            if val_pkt is None and val_cls is None:
                # Both missing -> Match
                score += weight_per_tag
            elif val_pkt is not None and val_cls is not None:
                # Fuzzy Match Check
                similarity = self._compute_bitwise_similarity(val_pkt, val_cls)
                
                if similarity >= self.config.ie_similarity_threshold:
                    # Scaled score: (Base Weight) * (Similarity Factor)
                    # We might want to give full weight if it passes threshold, or partial.
                    # Given the request "multiply the result by the weight" -> weight * similarity
                    score += weight_per_tag * similarity
                else:
                    # Below threshold -> 0 points (Penalty)
                    pass
            else:
                # One missing, one present -> Treat as mismatch or neutral?
                # User says: "Ensure handling of NaN or missing... If both values are missing (None), they count as a match."
                # Doesn't explicitly say what to do if ONE is missing. 
                # "mismatch in these fields must result in a score penalty."
                # If one is known and other unknown, we can't be sure it's a mismatch. 
                # Usually in Re-ID, if unknown, we don't penalize. 
                # But to be "Strict", maybe we do? 
                # Given "Bonus Weights... mismatch is neutral", implying Core mismatch is NOT neutral.
                # I will assume if one is missing, we don't add points but don't penalize? 
                # Actually, if we just don't add points, it is a penalty because we lose the 0.1 opportunity.
                # So simply doing nothing (score += 0) is the penalty.
                pass

        # 2. Frame Length
        # Weight 0.2.
        f_len_pkt = pkt_vec.get('frame_len')
        f_len_cls = cls_vec.get('frame_len')
        
        if f_len_pkt is None and f_len_cls is None:
            score += self.config.w_frame_len
        elif f_len_pkt is not None and f_len_cls is not None:
            if abs(f_len_pkt - f_len_cls) < 1.0: # Tolerance
                score += self.config.w_frame_len
        
        # --- Bonus Weights ---
        
        # 3. SSID
        # Weight 0.15. Match = Bonus. Mismatch = Neutral (0).
        ssid_pkt = pkt_vec.get('ssid')
        ssid_cls = cls_vec.get('ssid')
        
        if ssid_pkt and ssid_cls:
            if ssid_pkt == ssid_cls:
                score += self.config.w_ssid_bonus
            # Mismatch -> 0
        # If missing -> 0
        
        # 4. Sequence Number
        # Weight 0.05.
        seq_pkt = pkt_vec.get('seq_num')
        seq_cls = cls_vec.get('last_seq') # Cluster stores 'last_seq'
        
        if seq_pkt is not None and seq_cls is not None:
            delta = self._get_seq_delta(seq_pkt, seq_cls)
            # If delta is reasonable (e.g. < 1000) and positive?
            # Or just small?
            # A 'reasonable' gap for normal traffic. 
            # If delta is small (e.g. < 128), it's likely sequential.
            if 0 < delta < 128:
                score += self.config.w_seq_bonus
                
        # --- Physics Sanity Check ---
        # "A match is only valid if (Current_Time - Cluster_Last_Time < 5s) AND abs(Current_RSSI - Cluster_Last_RSSI) > 30dB is FALSE."
        # i.e. If Time < 5s AND RSSI_Diff > 30dB -> IMPOSSIBLE -> INVALID.
        
        if packet_timestamp and cluster_timestamp:
            try:
                dt_sec = (packet_timestamp - cluster_timestamp).total_seconds()
                
                # We only check if packet is fresher or close. 
                # If packet is OLDER than cluster (negative dt), we might skip or penalize?
                # For live streams, it's usually newer.
                
                if 0 <= dt_sec < self.config.sanity_time_window_sec:
                    # Check Physics
                    rssi_diff = abs(packet_rssi - cluster_rssi)
                    if rssi_diff > self.config.sanity_rssi_diff_db:
                        print(f"Physics Violation: Split MAC from Cluster. dt={dt_sec:.2f}s, dRSSI={rssi_diff:.2f}dB")
                        return 0.0
            except:
                pass
        
        # DEBUG PRINT
        # print(f"DEBUG: Score={score:.4f} (IE={score-(0.2 if abs(f_len_pkt - f_len_cls) < 1.0 else 0):.4f}) for IEs: {pkt_ies.get(221)} vs {cls_vec['ies'].get(221)}")
        
        return score

    def process_packet(self, packet_data: dict) -> int:
        src_mac = packet_data['src_mac']
        is_global = packet_data['is_global']
        vector = packet_data['vector']
        timestamp = packet_data['timestamp']
        rssi = packet_data['rssi']
        
        if not src_mac:
            return -1

        # --- Stage 1: Global MAC Handling ---
        if is_global:
            if src_mac in self.global_mac_map:
                c_id = self.global_mac_map[src_mac]
                # Find the cluster object
                # Optimization: Could store object in map, but list lookup is O(N). 
                # For high performance, map to object. For now, find by ID.
                for cls in self.active_clusters:
                    if cls.cluster_id == c_id:
                        cls.update(timestamp, rssi, src_mac, vector.get('seq_num'))
                        return c_id
                # Only if inconsistent state (map has ID but cluster gone)
            
            # Create new global cluster
            return self._create_new_cluster(packet_data, is_global=True)

        # --- Stage 2: Randomized MAC Handling ---
        
        best_cluster = None
        best_score = -1.0
        
        # Sub-hierarchy A: Local History Check (Priority)
        # Check clusters this MAC has been in
        candidate_ids = self.mac_history.get(src_mac, set())
        
        # We need to test these specific clusters first
        # We will split candidates into "History" and "Others"
        
        history_clusters = []
        other_clusters = []
        
        for cls in self.active_clusters:
            if cls.cluster_id in candidate_ids:
                history_clusters.append(cls)
            elif not cls.is_global_mac: 
                # "iterate through all other non-global clusters"
                other_clusters.append(cls)

        # A. Local History Check
        for cls in history_clusters:
            score = self.calculate_similarity(
                vector, cls.signature_vector, 
                timestamp, cls.last_seen_timestamp, 
                rssi, cls.last_rssi
            )
            
            if score >= self.config.match_threshold:
                if score > best_score:
                    best_score = score
                    best_cluster = cls
        
        if best_cluster:
            # Found in history
            self._update_cluster(best_cluster, packet_data)
            return best_cluster.cluster_id
            
        # B. Global Search Check (if no match in history)
        for cls in other_clusters:
            score = self.calculate_similarity(
                vector, cls.signature_vector, 
                timestamp, cls.last_seen_timestamp, 
                rssi, cls.last_rssi
            )
            
            if score >= self.config.match_threshold:
                if score > best_score:
                    best_score = score
                    best_cluster = cls
        
        if best_cluster:
            # Found in Global Search
            self._update_cluster(best_cluster, packet_data)
            return best_cluster.cluster_id
            
        # C. Create New Cluster
        return self._create_new_cluster(packet_data, is_global=False)

    def _create_new_cluster(self, packet_data, is_global):
        c_id = self.next_cluster_id
        src_mac = packet_data['src_mac']
        
        new_cls = DeviceCluster(
            cluster_id=c_id,
            is_global_mac=is_global,
            signature_vector=packet_data['vector'], # Initial vector
            last_seen_timestamp=packet_data['timestamp'],
            last_rssi=packet_data['rssi'],
            member_macs={src_mac}
        )
        if packet_data['vector'].get('seq_num') is not None:
             new_cls.signature_vector['last_seq'] = packet_data['vector']['seq_num']
             
        self.active_clusters.append(new_cls)
        self.next_cluster_id += 1
        
        # Update maps
        if is_global:
            self.global_mac_map[src_mac] = c_id
            
        if src_mac not in self.mac_history:
            self.mac_history[src_mac] = set()
        self.mac_history[src_mac].add(c_id)
        
        return c_id

    def _update_cluster(self, cls, packet_data):
        src_mac = packet_data['src_mac']
        cls.update(
            packet_data['timestamp'], 
            packet_data['rssi'], 
            src_mac, 
            packet_data['vector'].get('seq_num')
        )
        
        # Update history map
        if src_mac not in self.mac_history:
            self.mac_history[src_mac] = set()
        self.mac_history[src_mac].add(cls.cluster_id)
        
        # Merge knowledge (e.g. SSID if missing)
        self._merge_features(cls, packet_data['vector'])

    def _merge_features(self, cls, new_vec):
        curr = cls.signature_vector
        # Update fields if current is None/Unknown and new is Known
        if curr.get('ssid') is None and new_vec.get('ssid'):
            curr['ssid'] = new_vec['ssid']
        # IEs? Usually fixed, but we could merge missing tags?
        # For now, keep it simple.
        if curr.get('frame_len') is None and new_vec.get('frame_len'):
            curr['frame_len'] = new_vec['frame_len']

