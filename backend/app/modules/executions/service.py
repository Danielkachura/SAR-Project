from __future__ import annotations

import logging
import threading
import traceback
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.core.errors import NotFoundError
from app.models.canonical_models import ExecutionRecord, ExecutionStatus

logger = logging.getLogger(__name__)


class ExecutionService:
    """In-memory execution registry for long-running workflow operations."""

    def __init__(self) -> None:
        self._records: dict[str, ExecutionRecord] = {}
        self._lock = threading.Lock()

    def start_execution(
        self,
        *,
        stage: str,
        session_id: str,
        runner: Callable[[], tuple[dict[str, Any], list[str]]],
    ) -> ExecutionRecord:
        execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        record = ExecutionRecord(
            execution_id=execution_id,
            stage=stage,
            session_id=session_id,
            status=ExecutionStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._records[execution_id] = record

        thread = threading.Thread(target=self._run, args=(execution_id, runner), daemon=True)
        thread.start()
        return record

    def _run(self, execution_id: str, runner: Callable[[], tuple[dict[str, Any], list[str]]]) -> None:
        self._update(execution_id, status=ExecutionStatus.RUNNING)
        try:
            result_metadata, warnings = runner()
            self._update(
                execution_id,
                status=ExecutionStatus.SUCCEEDED,
                result_metadata=result_metadata,
                warnings=warnings,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Execution %s failed at stage %s", execution_id, self.get(execution_id).stage)
            self._update(
                execution_id,
                status=ExecutionStatus.FAILED,
                error_message=str(exc),
                result_metadata={"traceback": traceback.format_exc()},
            )

    def get(self, execution_id: str) -> ExecutionRecord:
        with self._lock:
            record = self._records.get(execution_id)
        if record is None:
            raise NotFoundError(f"Execution not found: {execution_id}")
        return record

    def _update(self, execution_id: str, **changes: Any) -> None:
        with self._lock:
            existing = self._records.get(execution_id)
            if existing is None:
                return
            changes["updated_at"] = datetime.now(timezone.utc)
            self._records[execution_id] = existing.model_copy(update=changes)
