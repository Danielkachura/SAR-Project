# MOD-002 Dataset Discovery & Artifact Resolver (Phase 0-1)

## Purpose
Discover scan folders and file inventory under `DATA`, classify official artifacts, and provide stage jump suggestions.

## Current contract
- Lists immediate subfolders under `DATA`.
- Resolves folder inventory into:
  - raw CSV files
  - PCAP/PCAPNG files
  - official `*_ENRICHED.csv` artifacts
  - official `*_REID.csv` artifacts
- Detects mode from selected folder name (`ble` first, then `wifi` / `wi-fi`, then `scan*` prefix as Wi-Fi fallback; else `unknown`).
- Provides stage jump suggestion based on active artifact and/or discovered official artifacts.

## Current known TODOs
- TODO: finalize exhaustive mode-detection naming rules from spec addendum (currently token-based).
- TODO: add CSV↔PCAP basename matching helper API for enrichment preconditions.
- TODO: include richer warning taxonomy for partial/invalid folder content.

## Last updated
- 2026-04-16: Implemented folder listing, inventory classification, mode detection, and stage jump suggestion skeleton.
- 2026-04-16: Updated mode detection fallback so folders starting with `scan` default to Wi-Fi when BLE token is absent.
