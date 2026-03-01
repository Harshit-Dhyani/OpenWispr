from __future__ import annotations

from pathlib import Path

from app.core.models import SessionDocument


class DocumentStore:
    def __init__(self) -> None:
        self._documents: list[SessionDocument] = []

    def add_pdf(self, path: str | Path) -> SessionDocument:
        file_path = Path(path).expanduser().resolve()
        document = SessionDocument(path=file_path, name=file_path.name)
        self._documents.append(document)
        return document

    def list_documents(self) -> list[SessionDocument]:
        return list(self._documents)


class ContextProvider:
    def __init__(self, document_store: DocumentStore) -> None:
        self.document_store = document_store

    def get_relevant_snippets(self, query: str) -> list[str]:
        return [
            f"PDF attached: {document.name} for query '{query}'"
            for document in self.document_store.list_documents()[:5]
        ]
