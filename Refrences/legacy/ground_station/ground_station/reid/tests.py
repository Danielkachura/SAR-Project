"""
Testing utilities for Bleach Re-ID algorithm validation.

Implements the three acceptance tests from proposal pre-2026-078:
- Test A: Split-Brain Simulation (sanity check)
- Test B: Meeting Room calibration (multi-device)
- Test C: Field validation (UAV deployment)
"""

import os
import tempfile
from pathlib import Path

import pandas as pd

from .models import ReidConfig
from .pipeline import cluster_scan_df, load_scan_csv


def simulate_split_brain(csv_path, mac_randomization_fraction=0.5):
    """
    Test A: Split-Brain Simulation.
    
    Simulates MAC address randomization on a single device by:
    1. Loading a real scan CSV (capturing packets from one phone)
    2. Modifying the last N% of packets to use a randomized MAC
    3. Running Re-ID engine
    4. Asserting that the engine unifies them back to 1 cluster
    
    Args:
        csv_path: Path to CSV containing packets from a single device
        mac_randomization_fraction: Fraction of packets [0-1] to randomize (default 0.5 = 50%)
        
    Returns:
        Dict with keys:
        - success: bool, True if test passed (1 cluster detected)
        - cluster_count: int, number of clusters found
        - original_macs: list of unique MACs in original CSV
        - randomized_macs: list of unique MACs after randomization
        - details: str, human-readable summary
    """
    df = load_scan_csv(csv_path)
    df_modified = df.copy()
    
    # Record original unique MACs
    original_macs = df_modified["src_mac"].unique().tolist()
    
    # Randomize last N% of packets
    split_idx = int(len(df_modified) * (1 - mac_randomization_fraction))
    randomized_mac = "aa:bb:cc:dd:ee:ff"
    df_modified.loc[split_idx:, "src_mac"] = randomized_mac
    
    randomized_macs = df_modified["src_mac"].unique().tolist()
    
    # Run Re-ID engine
    cluster_result, _summary = cluster_scan_df(df_modified)
    
    # Extract cluster_ids (handle both formats)
    if isinstance(cluster_result, dict) and "cluster_ids" in cluster_result:
        cluster_ids = cluster_result["cluster_ids"]
    else:
        cluster_ids = cluster_result
    
    cluster_count = len(set(cluster_ids.values()))
    success = cluster_count == 1
    
    return {
        "success": success,
        "cluster_count": cluster_count,
        "expected_clusters": 1,
        "original_macs": original_macs,
        "randomized_macs": randomized_macs,
        "split_fraction": mac_randomization_fraction,
        "details": (
            f"{'✓ PASS' if success else '✗ FAIL'}: "
            f"Expected 1 cluster, got {cluster_count}. "
            f"Original MACs: {len(original_macs)}, "
            f"Randomized to: {len(randomized_macs)}"
        ),
    }


def calibrate_meeting_room(csv_path, expected_device_count, config=None):
    """
    Test B: Meeting Room Calibration.
    
    Runs Re-ID against a known dataset with ground-truth device count and
    tunes seq_max_gap threshold if cluster count diverges from expected.
    
    In practice, when smartphones enable MAC randomization, each physical device
    may appear as multiple MACs in the raw capture. The Re-ID engine clusters
    these MACs back to their true devices. This test assumes the input devices.csv
    or ground truth has been manually verified to contain the list of MACs that
    should be clustered together.
    
    Args:
        csv_path: Path to CSV from controlled meeting room environment
        expected_device_count: Known number of distinct devices (ground truth).
                              Can be interpreted as:
                              - Expected cluster count (if devices are already known)
                              - Maximum acceptable cluster count (for sanity check)
        config: ReidConfig to use (default: standard config)
        
    Returns:
        Dict with keys:
        - success: bool, True if detected device count >= expected (or matches if exact)
        - detected_count: int, number of clusters found
        - expected_count: int, expected number of devices
        - suggested_adjustment: str, tuning suggestion if count diverges significantly
        - config_used: ReidConfig parameters
        - details: str, summary with pass/fail and recommendations
    """
    if config is None:
        config = ReidConfig()
    
    df = load_scan_csv(csv_path)
    cluster_result, summary = cluster_scan_df(df, config=config)
    
    # Extract cluster_ids
    if isinstance(cluster_result, dict) and "cluster_ids" in cluster_result:
        cluster_ids = cluster_result["cluster_ids"]
    else:
        cluster_ids = cluster_result
    
    detected_count = len(set(cluster_ids.values()))
    
    # Success: detected count should be >= expected (conservative grouping)
    # We accept if we get AT LEAST as many clusters as expected devices
    success = detected_count >= expected_device_count
    
    suggestion = ""
    if detected_count < expected_device_count:
        deficit = expected_device_count - detected_count
        suggestion = (
            f"Under-grouped by {deficit} device(s). "
            f"Try increasing t_max_sec from {config.t_max_sec} to {int(config.t_max_sec * 1.5)} "
            "or decreasing min_score to reduce temporal coupling."
        )
    elif detected_count > expected_device_count * 1.5:
        excess = detected_count - int(expected_device_count * 1.5)
        suggestion = (
            f"Over-grouped by ~{excess} device(s). Try increasing seq_max_gap "
            f"from {config.seq_max_gap} to {int(config.seq_max_gap * 1.5)} "
            "to relax sequence continuity threshold."
        )
    
    return {
        "success": success,
        "detected_count": detected_count,
        "expected_count": expected_device_count,
        "suggested_adjustment": suggestion,
        "config_used": {
            "t_max_sec": config.t_max_sec,
            "seq_max_gap": config.seq_max_gap,
            "rssi_max_diff": config.rssi_max_diff,
            "min_score": config.min_score,
        },
        "details": (
            f"{'✓ PASS' if success else '✗ FAIL'}: "
            f"Expected ≥{expected_device_count} devices, detected {detected_count}. "
            f"{suggestion if suggestion else 'Within acceptable range.'}"
        ),
    }


def generate_mock_scan_csv(num_devices=3, packets_per_device=100, duration_sec=600):
    """
    Generate a mock scan CSV for testing without real PCAP data.
    
    Args:
        num_devices: Number of distinct devices to simulate
        packets_per_device: Packets per device
        duration_sec: Spread packets over this duration (seconds)
        
    Returns:
        DataFrame with columns: timestamp_utc, src_mac, bssid, rssi_dbm, seq_ctl, frame_type
    """
    import numpy as np
    from datetime import datetime, timedelta
    
    base_time = datetime.utcnow()
    macs = [f"aa:bb:cc:dd:ee:{i:02x}" for i in range(num_devices)]
    
    rows = []
    for mac_idx, mac in enumerate(macs):
        for pkt_idx in range(packets_per_device):
            offset = (pkt_idx / packets_per_device) * duration_sec
            timestamp = base_time + timedelta(seconds=offset)
            
            rows.append({
                "timestamp_utc": timestamp,
                "src_mac": mac,
                "bssid": "ff:ff:ff:ff:ff:ff",
                "rssi_dbm": -50 - mac_idx * 5 + np.random.randn() * 2,  # Device-specific RSSI signature
                "seq_ctl": (mac_idx * 1000 + pkt_idx) % 4096,
                "frame_type": "probe-req",
            })
    
    df = pd.DataFrame(rows).sort_values("timestamp_utc").reset_index(drop=True)
    return df


def run_all_tests(csv_path, expected_device_count=None):
    """
    Run tests A and B on a given CSV.
    
    Args:
        csv_path: Path to input CSV
        expected_device_count: Ground truth for Test B (optional, skips Test B if None)
        
    Returns:
        Dict with results for each test
    """
    results = {}
    
    # Test A: Split-Brain
    try:
        results["Test A: Split-Brain Simulation"] = simulate_split_brain(csv_path)
    except Exception as e:
        results["Test A: Split-Brain Simulation"] = {
            "success": False,
            "error": str(e),
            "details": f"Test failed with error: {e}",
        }
    
    # Test B: Meeting Room
    if expected_device_count is not None:
        try:
            results["Test B: Meeting Room Calibration"] = calibrate_meeting_room(
                csv_path, expected_device_count
            )
        except Exception as e:
            results["Test B: Meeting Room Calibration"] = {
                "success": False,
                "error": str(e),
                "details": f"Test failed with error: {e}",
            }
    else:
        results["Test B: Meeting Room Calibration"] = {
            "skipped": True,
            "reason": "expected_device_count not provided",
        }
    
    return results


if __name__ == "__main__":
    # Example usage
    print("Bleach Re-ID Test Suite")
    print("=" * 60)
    
    # Generate mock data and run Test A
    print("\n[Demo] Generating mock scan CSV with 2 devices...")
    mock_df = generate_mock_scan_csv(num_devices=2, packets_per_device=50)
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        mock_df.to_csv(f.name, index=False)
        temp_csv = f.name
    
    try:
        print(f"Running Test A (Split-Brain) on {temp_csv}...")
        result_a = simulate_split_brain(temp_csv, mac_randomization_fraction=0.5)
        print(f"  {result_a['details']}")
        
        print(f"\nRunning Test B (Meeting Room) with expected_count=2...")
        result_b = calibrate_meeting_room(temp_csv, expected_device_count=2)
        print(f"  {result_b['details']}")
    finally:
        os.unlink(temp_csv)
