# Frontend — Session Start + Overview (Phase 2 state)

## Purpose
Describe current frontend behavior for Session Start and Overview pages in the staged refactor.

## Current contract
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
- Spatial section currently renders point list + hover metadata payload marker from MOD-010 path.

## Current known TODOs
- TODO: wire shared map component for spatial rendering while preserving MOD-010 ownership.
- TODO: introduce router/layout shell as app structure matures.
- TODO: add global filter controls after MOD-004 implementation.

## Last updated
- 2026-04-16: Upgraded Overview from placeholder to Phase 2 lightweight inspection flow.
