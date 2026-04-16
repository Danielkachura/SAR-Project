# MOD-012 Artifact Management (Phase 0-1 + Phase 4)

## Purpose
Centralize artifact classification, official naming, overwrite behavior, and activation lifecycle references.

## Current contract
- Recognizes official artifacts by suffix:
  - `*_ENRICHED.csv`
  - `*_REID.csv`
- Classifies file types into canonical artifact kinds:
  - raw CSV
  - PCAP / PCAPNG
  - ENRICHED CSV
  - REID CSV
- Builds official ENRICHED output name from selected raw CSV using `<raw_stem>_ENRICHED.csv`.
- ENRICHED generation overwrites existing official file silently.
- Supports activation flow through MOD-001 state transitions.
- Enrichment generation immediately activates produced ENRICHED artifact as active session input.

## Current known TODOs
- TODO: implement official REID naming/write helpers in artifact service.
- TODO: include export policy and persistent save package behavior in Save/Resume phase.
- TODO: include stronger lifecycle validation checks across TEMP vs official artifacts.

## Last updated
- 2026-04-16: Added phase-1 classification and official artifact detection helpers.
- 2026-04-16: Added Phase 4 official ENRICHED naming/overwrite lifecycle behavior.
