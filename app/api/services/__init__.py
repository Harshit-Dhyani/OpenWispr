"""Service layer exports for the OpenWispr API.

This module re-exports the main service classes for convenient imports
across the API. Each service handles a specific domain:

Transcription Services:
- HotkeyTranscriptionService: Push-to-talk transcription with real-time processing

Post-Processing Services:
- DictionaryService: User dictionary for word replacements
- SnippetService: Text snippet expansion
- StyleService: Writing style profile management

History Services:
- TranscriptHistoryService: Session persistence and analytics

Usage:
    from app.api.services import (
        HotkeyTranscriptionService,
        TranscriptHistoryService,
    )
    
    service = HotkeyTranscriptionService(settings)
    await service.start_session(...)

Note: BackendService is imported directly from backend_service module
as it has additional dependencies not needed by other services.
"""

from .dictionary_service import DictionaryService
from .hotkey_transcription_service import HotkeyTranscriptionService
from .snippet_service import SnippetService
from .style_service import StyleService
from .transcript_history_service import TranscriptHistoryService

__all__ = [
    "DictionaryService",
    "HotkeyTranscriptionService",
    "SnippetService",
    "StyleService",
    "TranscriptHistoryService",
]
