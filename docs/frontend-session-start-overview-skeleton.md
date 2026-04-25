# Frontend — Session Start + Overview + Calibration (Phase 3 state) + Re-ID/Enrichment (Phase 5 state)

## Purpose
Describe current frontend behavior and runtime scaffold for Session Start and Overview pages in the staged refactor.

## Current contract
- Runtime scaffold:
  - Vite + React app entry with `index.html`, `src/main.tsx`, `vite.config.ts`
  - frontend dev server scripts: `npm run dev`, `npm run build`, `npm run preview`
  - `/api` browser requests are proxied to backend `http://127.0.0.1:8000`
- `SessionStartPage`
  - lists scan folders
  - creates session from selected folder
  - supports manual mode override
- `OverviewPage`
  - opens after session creation
  - shows CSV selector for active folder
  - shows no file-level outputs until CSV selection
  - renders sections after selection:
    - summary stats
    - charts
    - file preview (capped)
    - spatial inspection
    - device inspection
  - includes navigation action into Calibration
- `CalibrationPage`
  - calibration CSV selection
  - MAC candidate fetch + selection
  - GT mode controls (`manual_map_click`, `first_sample`, `mean_first_k`)
  - optional RANSAC controls
  - calibration run action
  - scatter payload + diagnostics + warnings presentation
  - approve derived calibration action
  - fallback preset selection action
- `ReIdEnrichmentPage`
  - scan CSV + PCAP selection
  - enrichment parameter controls (ENR-01..ENR-06)
  - enrichment run action + quality panel
  - Re-ID parameter controls
  - Re-ID run action + summary panel
  - existing ENRICHED and REID artifact lists with active markers
- Spatial section currently renders point list + hover metadata payload marker from MOD-010 path.

## Current known TODOs
- TODO: wire shared map component for spatial rendering while preserving MOD-010 ownership.
- TODO: replace manual latitude/longitude input with shared map click component for calibration GT input.
- TODO: introduce router/layout shell as app structure matures.
- TODO: add global filter controls after MOD-004 implementation.

## Last updated
- 2026-04-16: Added runnable frontend scaffold and local `/api` dev proxy while preserving existing Phase 2 behavior.
- 2026-04-16: Added Calibration page flow and Phase 3 frontend contracts.
- 2026-04-25: Added minimal Re-ID/Enrichment Phase 5 flow.
