"""Lightweight perf logging helpers for tool calls."""
from __future__ import annotations

import json
import logging
import os
import platform
import time
from typing import Any, Optional

try:  # resource is not available on all platforms (e.g., Windows)
    import resource  # type: ignore
except Exception:  # pragma: no cover - platform dependent
    resource = None  # type: ignore

try:
    import tracemalloc
except Exception:  # pragma: no cover - platform dependent
    tracemalloc = None  # type: ignore


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

logger = logging.getLogger("teadata_mcp.perf")

_PERF_ENABLED = _env_flag("TEADATA_PERF_LOG", True)
_PAYLOAD_ENABLED = _env_flag("TEADATA_PERF_PAYLOAD", True)
_TRACEMALLOC_ENABLED = _env_flag("TEADATA_PERF_TRACEMALLOC", False)

if _PERF_ENABLED and _TRACEMALLOC_ENABLED and tracemalloc and not tracemalloc.is_tracing():
    try:
        tracemalloc.start()
    except Exception:
        pass


def _read_rss_bytes() -> Optional[int]:
    if resource is None:
        return None
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except Exception:
        return None
    # Linux reports kilobytes, macOS reports bytes.
    if platform.system() == "Linux":
        return int(usage) * 1024
    return int(usage)


def _read_tracemalloc() -> Optional[tuple[int, int]]:
    if _TRACEMALLOC_ENABLED and tracemalloc and tracemalloc.is_tracing():
        try:
            return tracemalloc.get_traced_memory()
        except Exception:
            return None
    return None


def _format_bytes(value: Optional[int]) -> str:
    if value is None:
        return "n/a"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _payload_stats(payload: Any) -> dict[str, int]:
    stats: dict[str, int] = {}
    if not isinstance(payload, dict):
        return stats
    geojson = payload.get("geojson")
    if isinstance(geojson, dict):
        features = geojson.get("features")
        if isinstance(features, list):
            stats["features"] = len(features)
    campuses = payload.get("campuses")
    if isinstance(campuses, list):
        stats["campuses"] = len(campuses)
    table = payload.get("table")
    if isinstance(table, dict):
        rows = table.get("rows")
        if isinstance(rows, list):
            stats["table_rows"] = len(rows)
    return stats


def _payload_size(payload: Any) -> Optional[int]:
    if not _PAYLOAD_ENABLED:
        return None
    if payload is None:
        return None
    try:
        return len(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))
    except Exception:
        return None


class PerfTimer:
    def __init__(
        self,
        tool_name: str,
        arguments: Optional[dict[str, Any]] = None,
        invocation_id: Optional[str] = None,
    ):
        self.tool_name = tool_name
        self.arguments = arguments or {}
        self.invocation_id = invocation_id
        self.started = time.perf_counter()
        self.rss_before = _read_rss_bytes()
        self.trace_before = _read_tracemalloc() if _TRACEMALLOC_ENABLED else None

    def finish(self, *, payload: Any = None, status: Optional[str] = None) -> None:
        duration_ms = (time.perf_counter() - self.started) * 1000
        rss_after = _read_rss_bytes()
        trace_after = _read_tracemalloc() if _TRACEMALLOC_ENABLED else None
        payload_bytes = _payload_size(payload)
        stats = _payload_stats(payload)

        parts = [
            "perf",
            f"invocation={self.invocation_id}" if self.invocation_id else None,
            f"tool={self.tool_name}",
            f"ms={duration_ms:.1f}",
        ]
        parts = [part for part in parts if part]
        if status:
            parts.append(f"status={status}")
        if self.rss_before is not None or rss_after is not None:
            parts.append(f"rss_before={_format_bytes(self.rss_before)}")
            parts.append(f"rss_after={_format_bytes(rss_after)}")
            if self.rss_before is not None and rss_after is not None:
                parts.append(f"rss_delta={_format_bytes(rss_after - self.rss_before)}")
        if self.trace_before or trace_after:
            before_current = self.trace_before[0] if self.trace_before else None
            after_current = trace_after[0] if trace_after else None
            after_peak = trace_after[1] if trace_after else None
            parts.append(f"py_current={_format_bytes(after_current)}")
            parts.append(f"py_peak={_format_bytes(after_peak)}")
            if before_current is not None and after_current is not None:
                parts.append(f"py_delta={_format_bytes(after_current - before_current)}")
        if payload_bytes is not None:
            parts.append(f"payload_bytes={payload_bytes}")
        for key, value in stats.items():
            parts.append(f"{key}={value}")
        extra = {
            "invocation_id": self.invocation_id,
            "tool": self.tool_name,
            "ms": round(duration_ms, 1),
            "status": status,
            "payload_bytes": payload_bytes,
            "rss_before_bytes": self.rss_before,
            "rss_after_bytes": rss_after,
            "rss_delta_bytes": (
                (rss_after - self.rss_before)
                if self.rss_before is not None and rss_after is not None
                else None
            ),
        }
        extra.update(stats)
        logger.info(" ".join(parts), extra=extra)


def start_perf_timer(
    tool_name: str,
    arguments: Optional[dict[str, Any]] = None,
    invocation_id: Optional[str] = None,
) -> Optional[PerfTimer]:
    if not _PERF_ENABLED:
        return None
    return PerfTimer(tool_name, arguments, invocation_id=invocation_id)


def finish_perf_timer(
    timer: Optional[PerfTimer], *, payload: Any = None, status: Optional[str] = None
) -> None:
    if timer is None:
        return
    timer.finish(payload=payload, status=status)
