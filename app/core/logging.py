"""
Logging configuration for the application.

Uses Loguru for structured logging with file rotation and contextual binding.
"""

from loguru import logger

from .config import settings


# Bound logger with a custom name available in record["extra"]
log = logger.bind(name="FTASK")

log.add(
    settings.LOG_FILE,
    format="{time} {level} [{extra[name]}] {message}",
    rotation="500 KB",
    backtrace=True,
    diagnose=True,
    level="DEBUG",
    enqueue=True,
)
