from __future__ import annotations

import logging
import os

import uvicorn

from app.core.config import AppSettings


def main() -> None:
    settings = AppSettings()
    env_level = os.getenv("TRANSCRIPTA_LOG_LEVEL")
    resolved_level = (env_level or settings.log_level or "INFO").upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if resolved_level not in valid_levels:
        resolved_level = "INFO"
    log_level = resolved_level.lower()

    logging.basicConfig(
        level=getattr(logging, resolved_level),
        format="%(levelname)s: %(name)s - %(message)s",
    )
    quiet_level = logging.DEBUG if resolved_level == "DEBUG" else logging.WARNING
    logging.getLogger("httpx").setLevel(quiet_level)
    logging.getLogger("httpcore").setLevel(quiet_level)

    uvicorn.run(
        "app.api.server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
