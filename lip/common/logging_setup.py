"""
logging_setup.py — Shared app-level logging configuration for LIP services.

Uvicorn's default ``LOGGING_CONFIG`` attaches a StreamHandler only to the
``uvicorn`` / ``uvicorn.error`` / ``uvicorn.access`` loggers. The root logger
is left unconfigured, so application-level loggers (``lip.*``) fall through to
Python's last-resort handler, which only emits ``WARNING`` and above. The
practical effect is that ``logger.info(...)`` calls inside LIP service code
are silently dropped in production containers.

``configure_app_logging()`` installs a single StreamHandler on the ``lip``
logger namespace and sets its level from ``LIP_LOG_LEVEL`` (default ``INFO``).
The call is idempotent — if a StreamHandler is already attached (pytest,
prior invocation), the function is a no-op and the existing level is left
alone.
"""
from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False
_DEFAULT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_app_logging(default_level: str = "INFO") -> None:
    """Install a StreamHandler on the ``lip`` logger at the configured level.

    Args:
        default_level: Log level used when ``LIP_LOG_LEVEL`` is unset.

    The function is safe to call from any LIP service entrypoint at import
    time. It does not modify the root logger and does not disable propagation,
    so tests that configure their own handlers continue to work unchanged.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.environ.get("LIP_LOG_LEVEL", default_level).upper()
    level = getattr(logging, level_name, logging.INFO)

    lip_logger = logging.getLogger("lip")
    already_has_stream = any(
        isinstance(h, logging.StreamHandler) for h in lip_logger.handlers
    )
    if not already_has_stream:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        lip_logger.addHandler(handler)

    lip_logger.setLevel(level)
    _CONFIGURED = True
