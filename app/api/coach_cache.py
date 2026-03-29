"""Coach service response caching for transcription refinement.

Provides thread-safe caching for coach service responses to reduce redundant
LLM calls. Uses SHA256 hashing to generate cache keys from request parameters.

Key features:
- Thread-safe operations with RLock
- JSON persistence to disk (lazy writes with dirty flag)
- Automatic LRU eviction when max_entries is exceeded
- TTL-based expiration (default 1 hour)
- Batched disk writes (only on put when dirty, not on every get)
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import threading
from pathlib import Path
from time import time
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 3600.0
DEFAULT_MAX_ENTRIES = 500


class CoachCache:
    def __init__(
        self,
        cache_path: Path,
        *,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._entries = self._load()
        self._dirty = False
        self._seq = itertools.count()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Failed to load cache from %s", self.cache_path)
            return {}

    def _persist(self) -> None:
        if not self._dirty:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        now = time()
        payload = self._entries
        evicted = 0
        if len(payload) > self.max_entries:
            ordered = sorted(
                payload.items(),
                key=lambda item: (item[1].get("accessed_at", 0), item[1].get("seq", 0)),
                reverse=True,
            )
            payload = dict(ordered[: self.max_entries])
            evicted = len(self._entries) - len(payload)
            self._entries = payload
        expired = self._evict_expired_unlocked(self._entries, now)
        payload = self._entries
        self.cache_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8"
        )
        self._dirty = False
        if evicted or expired:
            logger.debug(
                "CoachCache persisted: entries=%d evicted=%d expired=%d",
                len(payload),
                evicted,
                expired,
            )

    def _evict_expired_unlocked(self, entries: dict[str, dict[str, Any]], now: float) -> int:
        expired = [
            k for k, v in entries.items() if now - v.get("accessed_at", 0) > self.ttl_seconds
        ]
        for k in expired:
            del entries[k]
        return len(expired)

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
            now = time()
            if now - entry.get("accessed_at", 0) > self.ttl_seconds:
                del self._entries[key]
                self._dirty = True
                return None
            entry["accessed_at"] = now
            return dict(entry)

    def put(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._entries[key] = {
                **value,
                "accessed_at": time(),
                "seq": next(self._seq),
            }
            self._dirty = True
            if len(self._entries) > self.max_entries:
                self._persist()

    def flush(self) -> None:
        """Force write to disk."""
        with self._lock:
            self._persist()

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._entries.clear()
            self._dirty = True
            self._persist()

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        with self._lock:
            now = time()
            expired = sum(
                1
                for v in self._entries.values()
                if now - v.get("accessed_at", 0) > self.ttl_seconds
            )
            return {
                "entries": len(self._entries),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
                "expired": expired,
                "dirty": self._dirty,
            }
