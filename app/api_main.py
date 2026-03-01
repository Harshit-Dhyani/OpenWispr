from __future__ import annotations

import logging

import uvicorn

from app.core.config import AppSettings


def main() -> None:
    settings = AppSettings()
    log_level = settings.log_level.lower()

    # Configure root logger to see module DEBUG logs
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(levelname)s: %(name)s - %(message)s",
    )

    uvicorn.run(
        "app.api.server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
