from fastapi import APIRouter

from app.api.calibration import router as calibration_router
from app.api.enrichment import router as enrichment_router
from app.api.executions import router as executions_router
from app.api.inventory import router as inventory_router
from app.api.localization import router as localization_router
from app.api.overview import router as overview_router
from app.api.reid import router as reid_router
from app.api.sessions import router as sessions_router

api_router = APIRouter(prefix="/api")
api_router.include_router(sessions_router)
api_router.include_router(inventory_router)
api_router.include_router(overview_router)
api_router.include_router(calibration_router)
api_router.include_router(enrichment_router)
api_router.include_router(reid_router)
api_router.include_router(localization_router)
api_router.include_router(executions_router)
