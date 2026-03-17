"""Persistence layer for history, dictionary, snippets, and session storage.

Provides:
- HistoryDatabase: SQLite-based storage for transcription history with thread-safe access
- SessionWriter: Session state persistence for metadata, transcripts, and audio
- DocumentStore: Document context storage for session-attached files
- Migrations: Schema versioning and migration management

All storage implementations use thread-safe patterns with WAL mode for SQLite.

Key collaborators: app.core.session_manager, app.api.history_routes.
"""
