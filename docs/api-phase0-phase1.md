# API Contracts — Phase 0 + Phase 1 + Phase 2 (Overview)

## Purpose
Document currently implemented public API groups for session/inventory plumbing and Overview inspection.

## Current contract
Implemented endpoints:
- `GET /api/scan-folders`
- `POST /api/sessions`
- `PATCH /api/sessions/{session_id}/mode`
- `GET /api/sessions/{session_id}/state`
- `GET /api/sessions/{session_id}/inventory`
- `POST /api/sessions/{session_id}/artifacts/activate`
- `POST /api/sessions/{session_id}/overview`

Overview behavior notes:
- If `selected_csv_file` is omitted/null and no prior selected CSV is stored, Overview returns context only and no file-level outputs.
- For valid selected CSV, Overview returns summary stats, chart payloads, preview payload, spatial payload, and device-analysis payload.
- Overview processing is CSV-level only and does not invoke downstream heavy stages.

## Current known TODOs
- TODO: add explicit error code map per endpoint contract.
- TODO: add request/response examples for both Wi-Fi and BLE sample inputs.
- TODO: add API contract tests for all error paths.

## Last updated
- 2026-04-16: Added Phase 2 Overview API contract and behavior.
