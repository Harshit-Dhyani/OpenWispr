"""Re-exports SessionWriter from app.storage.session_store.

This module exists for backward compatibility. The canonical source is
app.storage.session_store.SessionWriter.

Key collaborators: app.storage.session_store (canonical source).
"""


from app.storage.session_store import SessionWriter

__all__ = ["SessionWriter"]
