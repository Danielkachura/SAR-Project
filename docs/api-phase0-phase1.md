# API Contracts — Phase 0 + Phase 1 Foundation

## Purpose
Document current public API group implemented for session and inventory/artifact plumbing.

## Current contract
Implemented endpoints:
- `GET /api/scan-folders`
- `POST /api/sessions`
- `PATCH /api/sessions/{session_id}/mode`
- `GET /api/sessions/{session_id}/state`
- `GET /api/sessions/{session_id}/inventory`
- `POST /api/sessions/{session_id}/artifacts/activate`

Behavior notes:
- Session creation detects mode from folder name and sets `mode_source="detected"`.
- Manual override updates mode and sets `mode_source="manual"`.
- Inventory separates raw CSV, PCAP, ENRICHED, REID artifacts.
- Activating ENRICHED sets stage to `reid_enrichment`.
- Activating REID sets stage to `localization`.

## Current known TODOs
- TODO: add explicit error code map per endpoint contract.
- TODO: add API contract tests at HTTP layer in addition to service tests.
- TODO: add remaining workflow endpoints in later phases.

## Last updated
- 2026-04-16: Added initial Phase 0/1 session + inventory + artifact activation APIs.
