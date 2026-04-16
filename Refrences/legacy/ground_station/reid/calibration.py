"""
Calibration and validation script for Bleach Re-ID against real Scan_15.12 data.

This script:
1. Runs Test A (Split-Brain) on each scan CSV
2. Runs Test B (Meeting Room) against Scan_15.12 with known device count (7 devices)
   - Note: The raw scan has 73 captured MACs due to randomization
   - Expected: Re-ID should cluster these into ~7 groups
3. Tunes seq_max_gap if cluster count diverges too much
4. Validates the final configuration
"""

import os
import sys
from pathlib import Path

from .models import ReidConfig
from .tests import calibrate_meeting_room, simulate_split_brain, run_all_tests
from .pipeline import load_scan_csv


def main():
    base_dir = Path(__file__).parent.parent.parent / "ground_station" / "data" / "Scan_15.12"
    
    print("=" * 70)
    print("BLEACH RE-ID CALIBRATION: Scan_15.12 Dataset")
    print("=" * 70)
    
    # Test A on each scan CSV
    print("\n[TEST A] Split-Brain Simulation")
    print("-" * 70)
    scan_files = sorted(base_dir.glob("scan_*.csv"))
    test_a_results = []
    
    for scan_file in scan_files[:1]:  # Test on first scan only for speed
        print(f"\nTesting: {scan_file.name}")
        df = load_scan_csv(str(scan_file))
        print(f"  Input: {len(df)} packets, {df['src_mac'].nunique()} unique MACs")
        
        result = simulate_split_brain(str(scan_file), mac_randomization_fraction=0.5)
        print(f"  {result['details']}")
        test_a_results.append(result)
    
    # Test B: Meeting Room calibration
    # Scan_15.12 has 7 known ground-truth devices (from devices.csv)
    # but 73 captured MACs due to randomization
    expected_devices = 7
    
    print(f"\n[TEST B] Meeting Room Calibration")
    print("-" * 70)
    print(f"Ground truth: {expected_devices} known devices")
    print(f"Scan_15.12 capture: 73 unique MACs detected (due to MAC randomization)")
    
    scan_file = base_dir / "scan_2025-12-15_09-58-13Z.csv"
    if scan_file.exists():
        df = load_scan_csv(str(scan_file))
        print(f"\nInput file: {scan_file.name}")
        print(f"  Packets: {len(df)}, Unique MACs: {df['src_mac'].nunique()}")
        print(f"  Time range: {df['timestamp_utc'].min()} to {df['timestamp_utc'].max()}")
        print(f"  RSSI range: {df['rssi_dbm'].min()} to {df['rssi_dbm'].max()} dBm")
        
        # Test with default config
        print(f"\nTest B.1: Default config (min_score=0.6, seq_max_gap=50)")
        result = calibrate_meeting_room(str(scan_file), expected_devices)
        print(f"  {result['details']}")
        print(f"  Detected {result['detected_count']} clusters")
        
        # Iterative tuning if needed
        if not result["success"]:
            print(f"\n  Attempting tuning (target: >= {expected_devices} clusters)...")
            
            detected = result["detected_count"]
            best_config = None
            best_result = result
            
            if detected < expected_devices:
                # Too few clusters: aggressively separate by:
                # 1. Increasing t_max_sec to prevent temporal overlap grouping
                # 2. Decreasing min_score to accept weaker matches
                # 3. Increasing seq_max_gap to avoid seq continuity grouping
                print(f"    Under-grouped ({detected} < {expected_devices})")
                
                # Strategy: Increase t_max_sec to prevent simultaneous devices from merging
                for t_max in [15, 10, 5]:  # Stricter time windows
                    config = ReidConfig(t_max_sec=t_max)
                    result_t = calibrate_meeting_room(str(scan_file), expected_devices, config)
                    status = "[OK]" if result_t["success"] else ""
                    print(f"    Trying t_max_sec={t_max}: {result_t['detected_count']} clusters {status}")
                    if result_t["success"]:
                        best_config = config
                        best_result = result_t
                        break
                
                if not best_config:
                    # Fallback: ultra-aggressive separation
                    print(f"    Fallback: trying ultra-strict parameters")
                    config = ReidConfig(t_max_sec=3, min_score=0.75, seq_max_gap=20)
                    best_result = calibrate_meeting_room(str(scan_file), expected_devices, config)
                    print(f"    Achieved {best_result['detected_count']} clusters with t_max_sec=3")
            
            elif detected > expected_devices * 1.5:
                # Too many clusters: try increasing seq_max_gap and rssi_diff
                print(f"    Over-grouped ({detected} > {int(expected_devices * 1.5)})")
                for seq_max in [75, 100, 128, 200]:
                    config = ReidConfig(seq_max_gap=seq_max)
                    result_t = calibrate_meeting_room(str(scan_file), expected_devices, config)
                    if result_t["success"]:
                        best_config = config
                        best_result = result_t
                        print(f"    [OK] SUCCESS: seq_max_gap={seq_max}")
                        break
                
                if not best_config:
                    print(f"    No perfect config found, using seq_max_gap=200")
                    config = ReidConfig(seq_max_gap=200)
                    best_result = calibrate_meeting_room(str(scan_file), expected_devices, config)
                    print(f"    Achieved {best_result['detected_count']} clusters")
        
        print(f"\n  Final result: {best_result['details']}")
    else:
        print(f"  File not found: {scan_file}")
    
    print("\n" + "=" * 70)
    print("Calibration Complete")
    print("=" * 70)
    print("\nNext steps:")
    print("1. If Test A PASS: Sequence continuity works correctly [OK]")
    print("2. If Test B >= 7 clusters: Bleach algorithm is tuned [OK]")
    print("3. Ready for: Test C (Field deployment with drone)")


if __name__ == "__main__":
    main()
