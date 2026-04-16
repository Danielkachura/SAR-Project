from __future__ import annotations

from pathlib import Path

from app.core.config import AppConfig


class DataPathResolver:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    @property
    def data_dir(self) -> Path:
        return self._config.data_dir

    def ensure_data_dir(self) -> Path:
        self._config.data_dir.mkdir(parents=True, exist_ok=True)
        return self._config.data_dir

    def folder_path(self, folder_id: str) -> Path:
        return self._config.data_dir / folder_id
