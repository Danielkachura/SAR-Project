# MOD-008 — Re-ID Module

## Responsibility

Run Re-ID over the active `*_ENRICHED.csv` artifact and generate official `*_REID.csv`
for Localization input.

## Inputs and Preconditions

- Active session exists
- Active ENRICHED artifact exists and is compatible
- Re-ID parameters are valid

If no active ENRICHED artifact exists, Re-ID is blocked with validation error.

## Output contract

The generated REID artifact preserves all input ENRICHED columns and adds:

- `cluster_id` (required)
- `cluster_type` (required, `static` or `dynamic`)

## Re-ID diagnostics and quality

Row-level assignment diagnostics are computed internally and surfaced via API aggregate
quality statistics (not as required persisted CSV columns in this phase).

Quality statistics include:

- total rows
- cluster count / singleton count / singleton ratio
- average, median, max cluster size
- high/medium/low confidence ratios
- coverage ratios (sequence, fingerprint, vendor, BLE signatures)
- confidence and method distributions

## Artifact behavior

- Output file name: `{enriched_stem}_REID.csv`
- Existing REID artifact for same stem is overwritten silently
- Generated REID artifact is activated in session state
- Active stage transitions to Localization

## API

### `POST /api/sessions/{session_id}/reid/run`

Request body:

```json
{
  "selected_enriched_artifact_id": "optional",
  "parameters": {}
}
```

Response includes:

- output artifact name
- row count
- cluster count
- quality statistics
- warnings
- updated session state
