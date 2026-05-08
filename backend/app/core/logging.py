from __future__ import annotations

import logging
from logging.config import dictConfig


def configure_logging() -> None:
    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "loggers": {
            "app": {"level": "INFO", "propagate": True},
            "app.services.ai_providers": {"level": "INFO", "propagate": True},
            "httpx": {"level": "WARNING", "propagate": True},
            "uvicorn.access": {"level": "INFO", "propagate": True},
        },
    })
    logging.getLogger("app").debug("Logging configured")
