"""Logging configuration helpers for teadata-mcp.

The MCP server is often run under Uvicorn (which configures logging), but it can
also be launched directly via ``python -m teadata_mcp``. This module provides a
small opt-in configuration layer that:

- Avoids clobbering an existing logging setup (e.g., Uvicorn).
- Supports optional JSON logs for easier sharing + analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
from typing import Any


_RESERVED = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - logging override
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except TypeError:
                payload[key] = str(value)

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_CONFIGURED = False


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None else value


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def configure_logging() -> None:
    """Configure logging when the process has no handlers yet.

    - Always honors ``TEADATA_LOG_FILE`` (adds a file handler).
    - Otherwise only configures stderr logging when no handlers exist.
    """

    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = _env("TEADATA_LOG_LEVEL", "INFO").upper()
    log_format = _env("TEADATA_LOG_FORMAT", "json").strip().lower()
    log_file = os.getenv("TEADATA_LOG_FILE")
    if log_file is None:
        log_file = "logs/teadata-mcp.log"

    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    formatter: logging.Formatter
    if log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    if log_file:
        try:
            path = Path(log_file).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            max_bytes = _env_int("TEADATA_LOG_FILE_MAX_BYTES", 5 * 1024 * 1024)
            backup_count = _env_int("TEADATA_LOG_FILE_BACKUPS", 3)
            file_handler = RotatingFileHandler(
                path,
                maxBytes=max(0, max_bytes),
                backupCount=max(0, backup_count),
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
            for logger_name in ("uvicorn.error", "uvicorn.access"):
                logging.getLogger(logger_name).addHandler(file_handler)
        except Exception:
            root.exception("Failed to configure TEADATA_LOG_FILE", extra={"log_file": log_file})

    logging.getLogger("teadata_mcp").setLevel(level)
    logging.getLogger("teadata").setLevel(level)
    _CONFIGURED = True
