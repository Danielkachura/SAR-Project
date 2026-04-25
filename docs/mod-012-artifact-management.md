# MOD-012 Artifact Management

## Purpose
Centralize artifact classification and official artifact recognition logic.

## Current contract
- Official artifacts:
  - `*_ENRICHED.csv`
  - `*_REID.csv`
- Classification kinds:
  - raw CSV
  - PCAP / PCAPNG
  - ENRICHED CSV
  - REID CSV
- Activation flow:
  - ENRICHED activation -> `active_enriched_artifact_id`, stage `reid_enrichment`
  - REID activation -> `active_reid_artifact_id`, stage `localization`

## Generation behavior currently implemented
- Enrichment writes `{csv_stem}_ENRICHED.csv`, silent overwrite, then activates artifact.
- Re-ID writes `{enriched_stem}_REID.csv`, silent overwrite, then activates artifact.

## Last updated
- 2026-04-25: Added explicit REID generation and activation behavior notes.
