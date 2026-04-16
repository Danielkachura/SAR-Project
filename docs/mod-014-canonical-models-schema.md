# MOD-014 Canonical Models & Schema

## Purpose
Provide centralized canonical model definitions for cross-module data contracts.

## Current contract
- Defines canonical enums/models for:
  - protocol mode
  - artifact kinds
  - stage suggestion enum
  - scan folder model
  - artifact record model
  - folder inventory model
  - session state model (including `selected_overview_csv_file`)
  - stage jump suggestion model
  - Overview payload models:
    - context
    - summary stats
    - charts
    - preview
    - spatial payload
    - device analysis
- API models compose these canonical models for public request/response contracts.

## Current known TODOs
- TODO: add canonical scan/enriched/reid/calibration/saved-session schemas in later slices.
- TODO: add stricter schema validation rules once algorithm modules are implemented.
- TODO: align protocol-specific column mapping with MOD-003 normalization once available.

## Last updated
- 2026-04-16: Extended canonical models with Overview payload contracts for Phase 2.
