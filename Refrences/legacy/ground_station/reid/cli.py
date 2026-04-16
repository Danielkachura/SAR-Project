import argparse
import glob
import os
import sys

from .models import ReidConfig
from .pipeline import enrich_csv_with_pcap, run_reid_on_csv, validate_required_columns, load_scan_csv


def _build_parser():
    parser = argparse.ArgumentParser(description="Re-ID clustering for scan CSVs.")
    sub = parser.add_subparsers(dest="command", required=True)

    cluster = sub.add_parser("cluster", help="Cluster a scan CSV (or glob).")
    cluster.add_argument("input", help="CSV path or glob (e.g., data/scan*/scan.csv).")
    cluster.add_argument("--out-dir", default=None, help="Output directory for *_reid.csv.")
    cluster.add_argument("--json", action="store_true", help="Save unified targets to *_targets.json.")
    cluster.add_argument("--confidence", action="store_true", help="Compute confidence scores for clusters.")

    enrich = sub.add_parser("enrich", help="Add PCAP-derived fields into a new CSV.")
    enrich.add_argument("csv", help="Input CSV path.")
    enrich.add_argument("--pcap", default=None, help="PCAP path (defaults to same stem).")
    enrich.add_argument("--out", default=None, help="Output CSV path (defaults to *_enriched.csv).")
    enrich.add_argument("--tolerance-ms", type=int, default=1000, help="Timestamp match tolerance in ms (default 1000).")
    return parser


def _resolve_inputs(pattern):
    if any(ch in pattern for ch in ["*", "?", "["]):
        return sorted(glob.glob(pattern))
    return [pattern]


def _default_out_path(csv_path, out_dir):
    base = os.path.basename(csv_path)
    stem, _ext = os.path.splitext(base)
    name = f"{stem}_reid.csv"
    if out_dir:
        return os.path.join(out_dir, name)
    return os.path.join(os.path.dirname(csv_path), name)


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "cluster":
        inputs = _resolve_inputs(args.input)
        if not inputs:
            print("Error: No input files matched.", file=sys.stderr)
            raise SystemExit(1)

        for path in inputs:
            try:
                # Validate CSV before processing
                df = load_scan_csv(path)
                validate_required_columns(df)
                
                out_path = _default_out_path(path, args.out_dir)
                json_path = None
                use_confidence = args.confidence  # Default from flag
                
                if args.json:
                    json_path = f"{os.path.splitext(out_path)[0]}_targets.json"
                    use_confidence = True  # Enable confidence when exporting JSON
                
                run_reid_on_csv(
                    path,
                    output_path=out_path,
                    config=ReidConfig(),
                    json_output_path=json_path,
                    use_confidence=use_confidence
                )
                print(f"[OK] Wrote {out_path}")
                if json_path:
                    print(f"[OK] Wrote {json_path}")
            except ValueError as e:
                print(f"Error processing {path}: {e}", file=sys.stderr)
                raise SystemExit(1)
            except Exception as e:
                print(f"Unexpected error processing {path}: {e}", file=sys.stderr)
                raise SystemExit(1)
    elif args.command == "enrich":
        csv_path = args.csv
        pcap_path = args.pcap
        if not pcap_path:
            stem, _ext = os.path.splitext(csv_path)
            pcap_path = f"{stem}.pcap"

        out_path = args.out
        if not out_path:
            out_path = f"{os.path.splitext(csv_path)[0]}_enriched.csv"

        try:
            enrich_csv_with_pcap(
                csv_path,
                pcap_path,
                output_path=out_path,
                tolerance_ms=args.tolerance_ms,
            )
            print(f"[OK] Wrote {out_path}")
        except Exception as e:
            print(f"Error enriching CSV: {e}", file=sys.stderr)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
