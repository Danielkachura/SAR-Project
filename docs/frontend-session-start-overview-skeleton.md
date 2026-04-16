# Frontend Skeleton — Session Start + Overview (Phase 0-1)

## Purpose
Describe the minimal frontend page skeleton delivered for early workflow wiring.

## Current contract
- `SessionStartPage`
  - loads scan folder options
  - creates session from selected folder
  - displays detected mode
  - supports manual mode override
- `OverviewPage`
  - renders active session context (folder + mode)
  - declares Phase 2 TODO for charts/tables/maps/stats
- App routing state is currently simple conditional page rendering by session presence.

## Current known TODOs
- TODO: implement real router and layout shell.
- TODO: add inventory display and artifact activation UI controls.
- TODO: implement full Overview sections in Phase 2.

## Last updated
- 2026-04-16: Added basic Session Start and Overview skeleton pages and API bindings.
