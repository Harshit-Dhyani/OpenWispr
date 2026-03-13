from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from time import time
from typing import Any

logger = logging.getLogger(__name__)


class CoachCache:
    def __init__(self, cache_path: Path, *, max_entries: int = 500) -> None:
        self.cache_path = Path(cache_path)
        self.max_entries = max_entries
        self._lock = threading.RLock()
        self._entries = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load cache from %s", self.cache_path)
            return {}

    def _persist(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._entries
        if len(payload) > self.max_entries:
            ordered = sorted(
                payload.items(), key=lambda item: item[1].get("created_at", 0), reverse=True
            )
            payload = dict(ordered[: self.max_entries])
            self._entries = payload
        self.cache_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8"
        )

    @staticmethod
    def build_key(*parts: object) -> str:
        digest = hashlib.sha256()
        for part in parts:
            digest.update(str(part).encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            entry["created_at"] = time()
            self._persist()
            return dict(entry)

    def put(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._entries[key] = {
                **value,
                "created_at": time(),
            }
            self._persist()
