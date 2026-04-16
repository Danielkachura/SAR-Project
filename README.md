# SAR-Project

Phase 0 + Phase 1 foundation for the SAR Ground Station Refactor.

## Repository layout
- `backend/` — API skeleton, canonical models, session/inventory/artifact services, backend tests
- `frontend/` — Session Start + Overview skeleton UI and typed API contracts
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
- API skeleton for above flows

## Intentionally deferred
- calibration / enrichment / re-id / localization algorithms
- heavy overview rendering and map layers
- save/resume persistence implementation
