# MOD-007 — Enrichment Module

## Responsibility

Generate an official `*_ENRICHED.csv` artifact from one selected scan CSV and its
matching PCAP file by attaching protocol-specific PCAP-derived metadata and row-level
match diagnostics to each CSV row.

## Implementation notes (current)

Current implementation uses Scapy packet parsing for feature extraction. Wi-Fi row/frame
correlation uses a vectorized `pandas.merge_asof` flow (`by=src_mac`, nearest timestamp
within tolerance) with broadcast/unicast partitioning by frame type. BLE still uses the
existing row-wise matcher in this phase (best-effort extraction + current scoring path).

## Match diagnostics columns (always present)

- `match_found`
- `match_delta_ms`
- `match_score`
- `match_method`

## Parameters (ENR-01 .. ENR-06)

- `match_threshold` (default 0.3)
- `match_time_window_ms` (default 500)
- `time_score_weight` (default 0.6)
- `identity_score_weight` (default 0.3)
- `wifi_context_weight` (default 0.1)
- `ble_context_weight` (default 0.1)

## Constraints

- Selected PCAP basename must match selected CSV basename
- Existing ENRICHED output is overwritten silently
- Generated ENRICHED artifact is activated after write
- Wi-Fi matching method labels remain canonical (`TIME_IDENTITY_BEST_MATCH` or `NO_MATCH`)
  and continue to honor `match_threshold`

## Last updated
- 2026-04-26: Replaced Wi-Fi matching inner loops with vectorized `merge_asof` partition
  strategy for large-scan performance; preserved output contract and BLE path behavior.
- 2026-04-25: Synced docs to implemented scoring parameters, diagnostics, and basename guard.
