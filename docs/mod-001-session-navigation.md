# MOD-001 App Session & Navigation (Phase 0-1)

## Purpose
Manage explicit application session state and stage navigation without domain algorithm execution.

## Current contract
- Owns in-memory `SessionState` lifecycle for active runtime session(s).
- Creates session from selected DATA folder.
- Stores detected mode and manual mode override source.
- Stores currently active artifacts (`raw`, `enriched`, `reid`) and current stage.
- Applies immediate stage updates when official artifacts are activated.

## Current known TODOs
- TODO: Persist session state beyond process lifecycle.
- TODO: Add save/resume integration with MOD-013 persistence contracts.
- TODO: Add readiness flags for downstream stages beyond Phase 1.

## Last updated
- 2026-04-16: Added Phase 0/1 session creation, mode override, artifact activation, and stage state skeleton.
