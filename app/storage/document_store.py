"""In-memory document store for session documents.

Provides DocumentStore class for tracking documents associated with
transcription sessions, and ContextProvider for document-based context retrieval.

Components:
    - DocumentStore: In-memory storage for session-attached PDFs and files
    - ContextProvider: Query-based snippet retrieval from stored documents

Key collaborators: app.core.models.SessionDocument, app.api.context_routes.

Note: Currently in-memory only; not persisted to disk.
"""

from __future__ import annotations

from pathlib import Path

from app.core.models import SessionDocument


class DocumentStore:
    """
    In-memory document store for session documents.

    State owned: List of SessionDocument objects.

    Lifecycle: Created per-session; documents are not persisted to disk.
    Currently stores PDF documents in memory only.
    """

    def __init__(self) -> None:
        self._documents: list[SessionDocument] = []

    def add_pdf(self, path: str | Path) -> SessionDocument:
        """
        Add PDF document to the store.

        Args:
            path: File path to PDF.

        Returns:
            Created SessionDocument.
        """
        file_path = Path(path).expanduser().resolve()
        document = SessionDocument(path=file_path, name=file_path.name)
        self._documents.append(document)
        return document

    def list_documents(self) -> list[SessionDocument]:
        """Return list of all stored documents."""
        return list(self._documents)


class ContextProvider:
    """
    Provides relevant document context for queries.

    State owned: Reference to DocumentStore.

    Lifecycle: Created with DocumentStore instance; get_relevant_snippets
    returns placeholder text for attached documents (stub implementation).
    """

    def __init__(self, document_store: DocumentStore) -> None:
        self.document_store = document_store

    def get_relevant_snippets(self, query: str) -> list[str]:
        """Return placeholder snippets for attached documents.

        Currently returns stub text. Full implementation would perform
        document content retrieval and relevance scoring.

        Args:
            query: The search query string.

        Returns:
            List of placeholder snippet strings (max 5 documents).
        """
        return [
            f"PDF attached: {document.name} for query '{query}'"
            for document in self.document_store.list_documents()[:5]
        ]
