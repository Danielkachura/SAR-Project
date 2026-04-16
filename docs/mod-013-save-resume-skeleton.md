# MOD-013 Save / Resume (Skeleton)

## Purpose
Provide the module boundary and contract placeholder for save/resume without implementing persistence yet.

## Current contract
- Exposes a minimal skeleton service marker used for module wiring.
- No save/resume persistence logic implemented in Phase 0/1.

## Current known TODOs
- TODO: implement save contract (`POST /api/sessions/{session_id}/save`).
- TODO: implement saved session listing and resume contracts.
- TODO: ensure resume never relies on missing TEMP artifacts.

## Last updated
- 2026-04-16: Created explicit save/resume module skeleton boundary.
