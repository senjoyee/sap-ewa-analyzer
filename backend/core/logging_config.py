"""Application logging configuration."""
from __future__ import annotations

import logging
import logging.config
import os


DEFAULT_LOG_LEVEL = "INFO"


def setup_logging() -> None:
    """Configure structured logging for the application."""
    log_level = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": log_level,
                }
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
        }
    )
