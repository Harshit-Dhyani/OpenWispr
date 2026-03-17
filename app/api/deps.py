"""Dependency injection module for FastAPI services.

This module provides singleton service instances and dependency injection
helpers for the FastAPI application. Services are initialized during
application lifespan and accessed via getter functions that raise HTTPException
if the service is not ready.

Key services:
- BackendService: Main transcription and session orchestration
- HotkeyTranscriptionService: Push-to-talk transcription handling
- TranscriptHistoryService: Session history and analytics storage
- DictionaryService: User dictionary entries for text correction
- SnippetService: Text snippet expansion
- StyleService: Writing style profile management
- HistoryDatabase: SQLite database for persistent storage

Example:
    from app.api.deps import get_service, get_history_service
    
    @app.get("/api/health")
    def health(svc: BackendService = Depends(get_service)):
        return svc.get_snapshot()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from app.api.services import (
    DictionaryService,
    SnippetService,
    StyleService,
    TranscriptHistoryService,
)
from app.api.services.backend_service import BackendService
from app.api.strings.en import API_STRINGS
from app.storage.history_db import HistoryDatabase

if TYPE_CHECKING:
    from app.api.services import HotkeyTranscriptionService


service: BackendService | None = None
hotkey_service: HotkeyTranscriptionService | None = None
history_db: HistoryDatabase | None = None
history_service: TranscriptHistoryService | None = None
dictionary_service: DictionaryService | None = None
snippet_service: SnippetService | None = None
style_service: StyleService | None = None


def get_service() -> BackendService:
    if service is None:
        raise HTTPException(status_code=503, detail=API_STRINGS.errors.service_not_ready)
    return service


def get_hotkey_service() -> HotkeyTranscriptionService:
    if hotkey_service is None:
        raise HTTPException(
            status_code=503,
            detail=API_STRINGS.errors.hotkey_service_not_ready,
        )
    return hotkey_service


def get_history_service() -> TranscriptHistoryService:
    if history_service is None:
        raise HTTPException(status_code=503, detail="History service is not ready")
    return history_service


def get_dictionary_service() -> DictionaryService:
    if dictionary_service is None:
        raise HTTPException(status_code=503, detail="Dictionary service is not ready")
    return dictionary_service


def get_snippet_service() -> SnippetService:
    if snippet_service is None:
        raise HTTPException(status_code=503, detail="Snippet service is not ready")
    return snippet_service


def get_history_db() -> HistoryDatabase:
    if history_db is None:
        raise HTTPException(status_code=503, detail="History database is not ready")
    return history_db


def get_style_service() -> StyleService:
    if style_service is None:
        raise HTTPException(status_code=503, detail="Style service is not ready")
    return style_service
