from __future__ import annotations

from collections.abc import Mapping

from app.models.canonical_models import SessionState


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def upsert(self, state: SessionState) -> None:
        self._sessions[state.session_id] = state

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def all(self) -> Mapping[str, SessionState]:
        return self._sessions
