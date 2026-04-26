# MOD-009 — Localization Module

## Responsibility

Compute localization from an active `*_REID.csv` artifact and return per-cluster localization outputs.

## Inputs and Preconditions

- Active session exists
- Active REID artifact exists and is compatible
- Session has active calibration (derived or fallback)
- Localization parameters are valid

## Execution model

Localization uses async execution tracking:

- `POST /api/sessions/{session_id}/localization/run` returns `execution_id`
- `GET /api/executions/{execution_id}` reports status and result payload

Execution registry is in-memory for this phase.

## Filtering and grouping contract

- Pre-filters support optional `cluster_ids` and optional `mac_addresses`
- Filtering narrows rows before computation
- Computation remains cluster-based (`cluster_id`) after filtering

Input column compatibility notes:
- GPS accepted aliases include `latitude/lat/gps_lat/gps_latitude` and `longitude/lon/lng/gps_lon/gps_longitude`
- RSSI accepted aliases include `rssi`, `rssi_dbm`, `signal_dbm`, and `signal_strength`

## Output contract

Each successful cluster returns:

- primary peak point
- peak score
- one-to-three uncertainty regions
- warnings

Failed clusters return failed status and warnings.

## Boundaries

- Localization computes result objects only
- Spatial rendering/layer shaping reuses MOD-010 Spatial Presentation service
- Result Analysis scoring is out of scope in this phase

## Last updated

- 2026-04-26: Added async localization API + execution tracking + cluster/mac pre-filter support.
- 2026-04-26: Added `rssi_dbm` RSSI alias support for REID artifacts.
