# MOD-007 Enrichment Module (Phase 4)

## Purpose
Generate an official `*_ENRICHED.csv` artifact from one selected raw scan CSV and a matching PCAP with identical basename.

## Current contract
- Enrichment runs on one selected raw CSV file per request.
- Matching PCAP is mandatory and must have identical basename to selected CSV.
- Pipeline is time-first, then protocol compatibility scoring.
- Output preserves all original scan fields.
- Output always includes fixed enrichment columns for both Wi-Fi and BLE families.
- Output always includes diagnostics columns:
  - `match_found`
  - `match_delta_ms`
  - `match_score`
  - `match_method`
- `match_method` enum currently supports:
  - `time_identity_best_match`
  - `time_only_match`
  - `no_match`
- Rows with no valid match are still preserved with null/empty enrichment values and `no_match` diagnostics.
- Official output naming is `<original_stem>_ENRICHED.csv`.
- Existing enriched artifact with same official name is overwritten silently.
- Generated artifact is activated immediately as active enriched input.
- Enrichment response includes quality statistics:
  - matched/unmatched ratios
  - sequence/fingerprint/vendor coverage ratios
  - match delta distribution
  - match score distribution

## Current known TODOs
- TODO: expand BLE field extraction to decode full AD structure families (service UUID lists, local-name value, TX-power field) when parser support matrix is finalized.
- TODO: externalize enrichment defaults from code constants to approved parameter registry when Phase 5+ parameter wiring is added.
- TODO: consider async execution-id model for long-running large PCAP enrichment jobs.

## Last updated
- 2026-04-16: Added Phase 4 enrichment backend flow, official artifact writing/activation behavior, diagnostics, and quality-stat contracts.
