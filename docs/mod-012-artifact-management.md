# MOD-012 Artifact Management (Phase 0-1)

## Purpose
Centralize artifact classification and official artifact recognition logic.

## Current contract
- Recognizes official artifacts by suffix:
  - `*_ENRICHED.csv`
  - `*_REID.csv`
- Classifies file types into canonical artifact kinds:
  - raw CSV
  - PCAP / PCAPNG
  - ENRICHED CSV
  - REID CSV
- Supports activation flow through MOD-001 state transitions.

## Current known TODOs
- TODO: implement naming/writing/overwrite/export operations for later phases.
- TODO: include validation and lifecycle policy checks for generated artifacts.

## Last updated
- 2026-04-16: Added phase-1 classification and official artifact detection helpers.
