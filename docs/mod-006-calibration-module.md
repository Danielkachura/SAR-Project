# MOD-006 Calibration Module (Phase 3)

## Purpose
Derive or select one active session-level calibration parameter set from one selected calibration CSV and one selected MAC.

## Current contract
- Public APIs:
  - `POST /api/sessions/{session_id}/calibration/candidates`
  - `POST /api/sessions/{session_id}/calibration/run`
  - `POST /api/sessions/{session_id}/calibration/approve`
  - `POST /api/sessions/{session_id}/calibration/fallback`
- Behavior:
  - calibration candidates are MACs from one selected CSV only
  - calibration run is constrained to one selected CSV and one selected MAC
  - supported GT modes:
    - `manual_map_click`
    - `first_sample`
    - `mean_first_k`
  - defaults:
    - `gt_mode=mean_first_k`
    - `gt_first_k=5`
    - `enable_ransac=true`
    - `ransac_residual_threshold_db=4`
    - `ransac_iterations=100`
    - `distance_floor_m=1`
  - scatter payload uses:
    - `x=log10(distance)`
    - `y=RSSI`
  - optional RANSAC pre-cleaning runs before final linear regression
  - final fit model is `y = a + b*x`
  - derived parameters:
    - `rssi_at_1m = a`
    - `path_loss_n = -b/10`
    - `sigma` from residual standard deviation
  - weak fit emits warnings but does not block approval
  - fallback presets remain selectable and save as session calibration

## Explicit non-scope
- no enrichment
- no re-id
- no localization execution
- no result-analysis scoring
- no full rerun orchestration in this phase

## Current known TODOs
- TODO(spec): finalize `CAL-07 fit_warning_min_samples` threshold.
- TODO(spec): finalize `CAL-08 fit_warning_min_inlier_ratio` threshold.
- TODO(spec): revisit fallback preset values if Part B publishes normative numeric defaults.

## Last updated
- 2026-04-16: Added Phase 3 calibration backend/frontend flow, session persistence, and tests.
