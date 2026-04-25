# MOD-014 Canonical Models & Schema

## Purpose
Provide centralized canonical model definitions for cross-module data contracts.

## Current contract
Defines canonical models for:
- session/navigation/inventory
- Overview payloads
- Calibration payloads/state
- Enrichment payloads and parameters (ENR-01..ENR-06)
- Re-ID payloads and parameters

## Re-ID canonical additions
- `ReIdParameters` (conservative defaults)
- `ReIdMethod` enum
- `ReIdConfidenceBand` enum
- `ReIdQualityStats` and distribution models
- `ReIdRunPayload`

## Re-ID artifact schema notes
Persisted REID output preserves upstream ENRICHED schema and includes:
- `cluster_id`
- `cluster_type`

## Last updated
- 2026-04-25: Added canonical Re-ID models and quality payload contracts.
