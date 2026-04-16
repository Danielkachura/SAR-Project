from fastapi import APIRouter

from app.api.inventory import router as inventory_router
from app.api.sessions import router as sessions_router

api_router = APIRouter(prefix="/api")
api_router.include_router(sessions_router)
api_router.include_router(inventory_router)
