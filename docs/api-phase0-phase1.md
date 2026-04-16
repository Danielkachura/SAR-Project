# API Contracts — Phase 0 + Phase 1 + Phase 2 (Overview) + Phase 3 (Calibration)

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
- `POST /api/sessions/{session_id}/calibration/candidates`
- `POST /api/sessions/{session_id}/calibration/run`
- `POST /api/sessions/{session_id}/calibration/approve`
- `POST /api/sessions/{session_id}/calibration/fallback`

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
- 2026-04-16: Added Phase 3 Calibration API contract and behavior notes.

Calibration behavior notes:
- Calibration runs on one selected CSV and one selected MAC only.
- `run` supports GT modes `manual_map_click`, `first_sample`, and `mean_first_k`.
- `run` returns scatter payload (`x=log10(distance)`, `y=RSSI`), optional inlier tagging, fit diagnostics, and derived parameters.
- Weak fit warnings do not block `approve`; approval remains manual.
- `fallback` stores active session calibration with parameter source `fallback`.
