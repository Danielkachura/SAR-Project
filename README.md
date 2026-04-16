# SAR-Project

Phase 0 + Phase 1 + Phase 2 (Overview) foundation for the SAR Ground Station Refactor.

## Repository layout
- `backend/` — API contracts, canonical models, session/inventory services, overview services, backend tests
- `frontend/` — Session Start + Overview UI and typed API contracts
- `docs/` — specification docs and module/API documentation

## Backend quick start
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload
```

## Implemented scope
- scan folder listing under `DATA`
- session creation from selected folder
- mode detection + manual override
- folder inventory and artifact classification
- artifact activation and stage jump suggestion
- overview API + CSV-level inspection payloads
- overview frontend sections (selector, stats, charts, preview, spatial, device)

## Intentionally deferred
- calibration / enrichment / re-id / localization algorithms
- heavy map rendering and localization overlays
- save/resume persistence implementation
