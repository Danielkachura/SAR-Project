# MOD-007 — Enrichment Module

## Responsibility

Generate an official `*_ENRICHED.csv` artifact from one selected scan CSV and its
matching PCAP file by attaching protocol-specific PCAP-derived metadata and row-level
match diagnostics to each CSV row.

## Source of truth

Part A §MOD-007, Part B §3.3 (ENR parameters) and §5.3 (algorithm), Part C Phase 4.

---

## Algorithm (7 steps)

### Step 0 — Validate inputs

Validates: CSV exists in active folder inventory, PCAP exists in active folder
inventory, both files are readable. Raises `ValidationError` on any failure.

### Step 1 — Parse PCAP into frame-feature table

Pure-Python struct-based reader in `service._parse_pcap_file()`. Supports:

| Link type | Format | Protocol |
|-----------|--------|----------|
| 105 | IEEE 802.11 (raw) | Wi-Fi |
| 127 | IEEE 802.11 with RadioTap | Wi-Fi |
| 251 | Bluetooth LE Link Layer | BLE |
| 272 | BTLE (offset 14 bytes) | BLE |

**Wi-Fi extracted fields:** src MAC, dst MAC, BSSID, sequence number, frame type,
DS Parameter Set channel, IE tag list, IE fingerprint (sorted tag IDs), vendor OUIs
(tag 221 OUI bytes).

**BLE extracted fields:** advertiser address, address type (public/random), PDU type
(ADV_IND / ADV_NONCONN_IND / SCAN_RSP / …), flags, local name, TX power level,
16/32/128-bit service UUIDs, manufacturer specific data (hex), vendor company ID.

### Step 2 — Normalize

Timestamps are normalized to milliseconds (heuristic: values < 1×10¹⁰ treated as
seconds, otherwise as milliseconds). MAC addresses are lowercased hex with colons.

### Step 3 — Build searchable index (`_PcapIndex`)

Frames are indexed into 1-second time buckets and by identity key (src MAC or BLE
advertiser address). Lookup over `[row_ts − window, row_ts + window]` spans the
required bucket range.

### Step 4 — Generate candidate PCAP matches per CSV row

For each CSV row, derive timestamp (from standard timestamp columns) and identity
(from standard MAC columns). Retrieve frames from time-bucket index. Discard any
frame outside `match_time_window_ms`.

### Step 5 — Score candidates and choose best match

For each candidate:

```
time_score     = max(0, 1 − delta_ms / match_time_window_ms)
identity_score = 1.0 if row MAC == frame MAC else 0.0
context_score  = protocol-specific compatibility (BSSID for Wi-Fi, local name for BLE)

score = time_weight × time_score
      + identity_weight × identity_score
      + context_weight × context_score
```

The best-scoring frame is selected only if `score ≥ match_threshold`.

Match method assigned:
- `time_identity_best_match` — best candidate shared identity with the row
- `time_only_match` — best candidate matched by time only
- `no_match` — no candidate passed threshold

### Step 6 — Build enriched row

Every output row preserves all original scan CSV fields plus the enrichment columns
below. BLE enrichment columns are always present in the schema even when values are
empty (required by spec).

**Match diagnostics (always present):**

| Column | Description |
|--------|-------------|
| `match_found` | `"true"` / `"false"` |
| `match_delta_ms` | Absolute time delta to best PCAP frame |
| `match_score` | Composite match score |
| `match_method` | `time_identity_best_match` / `time_only_match` / `no_match` |

**Wi-Fi enrichment columns:**

`enr_src_vendor`, `enr_dst_mac`, `enr_bssid`, `enr_seq_num`, `enr_frame_length`,
`enr_ie_ids`, `enr_ie_fingerprint`, `enr_ie_vendor_ouis`, `enr_channel`,
`enr_frame_type`

**BLE enrichment columns:**

`enr_ble_advertiser_addr`, `enr_ble_addr_type`, `enr_ble_event_type`,
`enr_ble_manufacturer_data`, `enr_ble_service_uuids`, `enr_ble_local_name`,
`enr_ble_tx_power`, `enr_ble_flags`, `enr_ble_vendor_company_id`

### Step 7 — Write official ENRICHED artifact

Output file: `{csv_stem}_ENRICHED.csv` in the same scan folder. Overwrites silently
if already present. Activates the artifact in session state via
`SessionNavigationService.activate_artifact()`.

---

## Parameters (ENR-01 .. ENR-06)

| ID | Name | Default | Range |
|----|------|---------|-------|
| ENR-01 | `match_threshold` | 0.3 | [0, 1] |
| ENR-02 | `match_time_window_ms` | 500 | > 0 |
| ENR-03 | `time_score_weight` | 0.6 | [0, 1] |
| ENR-04 | `identity_score_weight` | 0.3 | [0, 1] |
| ENR-05 | `wifi_context_weight` | 0.1 | [0, 1] |
| ENR-06 | `ble_context_weight` | 0.1 | [0, 1] |

Defaults are protocol-global starters per spec (ENR-01/ENR-02 noted as TBD in Part B).

---

## API

### `POST /api/sessions/{session_id}/enrichment/run`

**Request:**
```json
{
  "selected_csv_file": "scan.csv",
  "selected_pcap_file": "scan.pcap",
  "parameters": {}
}
```

**Response (`EnrichmentRunPayload`):**
```json
{
  "enrichment": {
    "selected_csv_file": "scan.csv",
    "selected_pcap_file": "scan.pcap",
    "output_artifact_file_name": "scan_ENRICHED.csv",
    "protocol": "wifi",
    "parameters": { ... },
    "quality_stats": {
      "total_rows": 1000,
      "matched_rows": 870,
      "match_rate": 0.87
    }
  }
}
```

**Error codes:** 400 if CSV/PCAP not in inventory or file unreadable; 404 if session
not found.

---

## Failure behavior

- Full failure: no matching PCAP / unreadable CSV / unreadable PCAP / invalid parameters
- Row-level partial failure: row preserved with empty enrichment fields and `match_found=false`

---

## Integration constraints

- Does NOT perform clustering, localization, map rendering, GT handling, or scoring
- Provides richer per-row metadata to MOD-008 Re-ID
- Rerun propagation: Enrichment parameter change → enrichment → Re-ID → localization → result analysis

---

## Implementation files

| File | Role |
|------|------|
| `backend/app/modules/enrichment/service.py` | PCAP parser, index, matching, artifact writer |
| `backend/app/api/enrichment.py` | FastAPI router |
| `backend/app/models/canonical_models.py` | `EnrichmentParameters`, `EnrichmentRunPayload`, `EnrichmentQualityStats` |
| `backend/app/models/api_models.py` | `EnrichmentRunRequest`, `EnrichmentRunResponse` |
| `backend/tests/test_enrichment_service.py` | Unit tests |
| `backend/tests/test_enrichment_api.py` | API tests |
| `frontend/src/api/enrichment.ts` | API client |
| `frontend/src/types/contracts.ts` | TypeScript types |
| `frontend/src/pages/ReIdEnrichmentPage.tsx` | UI (enrichment half; Re-ID in Phase 5) |
