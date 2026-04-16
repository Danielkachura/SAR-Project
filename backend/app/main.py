from __future__ import annotations

from fastapi import FastAPI

from app.api import api_router
from app.core.config import build_config
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.session_navigation.service import SessionNavigationService
from app.storage.data_paths import DataPathResolver
from app.storage.session_store import InMemorySessionStore

config = build_config()
path_resolver = DataPathResolver(config=config)
session_store = InMemorySessionStore()
dataset_service = DatasetDiscoveryService(path_resolver=path_resolver)
session_navigation_service = SessionNavigationService(
    dataset_service=dataset_service,
    session_store=session_store,
)


def get_dataset_discovery_service() -> DatasetDiscoveryService:
    return dataset_service


def get_session_navigation_service() -> SessionNavigationService:
    return session_navigation_service


app = FastAPI(title="SAR Ground Station Refactor")
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
