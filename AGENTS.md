# AGENTS.md

## Project role
You are working on the **SAR Ground Station Refactor**.

## Source of truth
Always follow this priority:
1. `Part A` — Core System Specification
2. `Part B` — Algorithms, Parameters, APIs
3. `Part C` — Implementation Order, UI Skeleton, AI Workflow
4. Legacy codebase — **reference only**, never authoritative

If legacy code conflicts with the spec, follow the spec.

## Working style
- Implement in small, reviewable steps
- Do not rewrite the whole system at once
- Do not add features not explicitly specified
- Do not make silent assumptions
- If a value or behavior is `TBD`, leave a clear `TODO`
- Preserve strict module boundaries
- Keep backend/frontend separation clean
- Keep session state explicit
- Keep artifact lifecycle explicit
- Prefer typed, testable, modular code

## Documentation rule
Maintain `/docs` as part of implementation.

For every changed:
- top-level module
- canonical model
- public API group
- algorithm

update the matching Markdown file in `/docs` in the same task.

Do not create documentation for trivial helper files.

## Before coding
Always do this first:
1. Summarize the task
2. List files to create/modify
3. List docs to create/update
4. Map the task to the spec modules
5. List remaining TODO/TBD items
6. State assumptions you are avoiding

If the task is large or ambiguous, stop after the plan and wait for approval.

## Implementation constraints
- Public APIs must match the approved API contracts
- Do not expose internal submodules as public endpoints
- Keep canonical models centralized
- Treat `*_ENRICHED.csv` and `*_REID.csv` as official artifacts
- Keep `TEMP` non-persistent
- Save/resume must not depend on reconstructing missing TEMP artifacts

## Testing
Add tests for implemented behavior.
Test contracts and edge cases, not only happy paths.

## Rerun discipline
Respect rerun propagation rules from Part B:
- Global Filter change -> rerun from first downstream consumer
- Calibration change -> calibration -> localization -> result analysis
- Enrichment change -> enrichment -> re-id -> localization -> result analysis
- Re-ID change -> re-id -> localization -> result analysis
- Localization change -> localization -> result analysis
- View-only changes -> no rerun
- Score-only changes -> result-analysis recompute only

## Current project priority
Start with:
1. repo skeleton
2. session/inventory/artifact plumbing
3. Overview
4. Calibration
5. Enrichment
6. Re-ID
7. Localization
8. Result Analysis
9. Save/Resume

Do not start with full end-to-end generation of the whole system.
