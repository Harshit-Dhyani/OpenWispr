"""Backward compatibility shim - AppSettings moved to app.core.settings.config."""

from app.core.settings.config import AppSettings

__all__ = ["AppSettings"]
