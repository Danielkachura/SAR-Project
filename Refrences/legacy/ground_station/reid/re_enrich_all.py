"""
Re-enrich all scan CSVs in Scan_15.12 directory with current enrichment code.
This will overwrite existing *_enriched.csv files.
"""
import os
import sys
from pathlib import Path
from .pipeline import enrich_csv_with_pcap

def main():
    data_dir = Path(__file__).parent.parent / "data" / "Scan_15.12"
    
    # Find all scan CSVs (not enriched ones)
    csv_files = sorted(data_dir.glob("scan_*[!enriched].csv"))
    csv_files = [f for f in csv_files if not f.stem.endswith("_enriched") and not f.stem.endswith("_reid")]
    
    if not csv_files:
        print("No scan CSV files found in Scan_15.12/")
        return
    
    print(f"Found {len(csv_files)} scan CSV files to enrich:")
    for csv_file in csv_files:
        print(f"  - {csv_file.name}")
    
    print(f"\nStarting re-enrichment with 1000ms tolerance...")
    print(f"{'=' * 70}")
    
    success_count = 0
    fail_count = 0
    
    for csv_file in csv_files:
        # Check if corresponding PCAP exists
        pcap_file = csv_file.with_suffix(".pcap")
        if not pcap_file.exists():
            print(f"\n[SKIP] {csv_file.name} - no PCAP file found")
            continue
        
        output_file = csv_file.with_name(f"{csv_file.stem}_enriched.csv")
        
        print(f"\n[PROCESSING] {csv_file.name}")
        print(f"  PCAP: {pcap_file.name}")
        print(f"  Output: {output_file.name}")
        
        try:
            enrich_csv_with_pcap(
                str(csv_file),
                str(pcap_file),
                output_path=str(output_file),
                tolerance_ms=1000
            )
            
            # Verify enrichment quality
            import pandas as pd
            df = pd.read_csv(output_file)
            enriched = df['seq_ctl'].notna().sum()
            total = len(df)
            pct = enriched / total * 100 if total > 0 else 0
            
            print(f"  [OK] Enriched {enriched}/{total} rows ({pct:.1f}%)")
            success_count += 1
            
        except Exception as e:
            print(f"  [FAIL] Error: {e}")
            fail_count += 1
    
    print(f"\n{'=' * 70}")
    print(f"Re-enrichment complete:")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {fail_count}")
    
    if fail_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
