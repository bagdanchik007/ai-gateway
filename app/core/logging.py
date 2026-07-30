"""Zentrale structlog-Konfiguration.

Wird einmal beim App-Start aufgerufen (siehe app/main.py). Lokal
(app_debug=True) ein lesbares Konsolenformat, in Produktion JSON-Zeilen —
für das Parsen durch Log-Aggregatoren (ELK/Loki/CloudWatch & Co.).
"""

import logging

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.is_production
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if settings.app_debug else logging.INFO,
    )
