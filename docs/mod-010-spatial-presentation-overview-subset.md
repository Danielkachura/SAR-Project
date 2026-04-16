# MOD-010 Spatial Presentation (Overview Subset)

## Purpose
Provide shared spatial payload construction for Overview without localization or analysis overlays.

## Current contract
- Builds spatial payload from CSV GPS coordinates only.
- Includes lightweight hover metadata when available (`device_id/mac`, `cluster_id`, `rssi`, `timestamp`).
- Used by MOD-005 Overview module.
- Explicit non-scope:
  - no localization layers
  - no uncertainty overlays
  - no heatmap computation
  - no GT or distance tools

## Current known TODOs
- TODO: replace temporary frontend list rendering with shared map component once frontend map stack is formalized.
- TODO: normalize coordinate field naming through MOD-003 when available.

## Last updated
- 2026-04-16: Added basic Overview spatial payload builder and hover metadata support.
