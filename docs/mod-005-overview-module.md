# MOD-005 Overview Module (Phase 2)

## Purpose
Provide lightweight CSV-level inspection for one selected scan CSV in the active session context.

## Current contract
- Public API: `POST /api/sessions/{session_id}/overview`.
- Returns these output categories:
  - overview context
  - summary stats
  - chart payloads
  - preview payload (capped)
  - spatial payload (GPS sample points only)
  - device-analysis payload
- Behavior:
  - if no CSV is selected, returns context only with warning and no file-level outputs
  - processes selected CSV in active session mode context
  - computes only lightweight CSV-level inspection
- Explicit non-scope:
  - no PCAP-dependent logic
  - no calibration, enrichment, re-id, localization, or result-analysis execution

## Current known TODOs
- TODO: integrate MOD-003 schema normalization hooks for protocol-specific field mapping.
- TODO: integrate MOD-004 global filter engine once global filter semantics are implemented.
- TODO: formalize chart payload schema if frontend charting library contract is introduced.

## Last updated
- 2026-04-16: Added Phase 2 Overview backend flow, payload contract, and tests.
