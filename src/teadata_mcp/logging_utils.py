"""Small helpers for consistent, low-noise logging."""

from __future__ import annotations

import uuid
from typing import Any


def new_invocation_id() -> str:
    return uuid.uuid4().hex[:12]


def summarize_arguments(arguments: dict[str, Any] | None) -> dict[str, Any]:
    if not arguments:
        return {}

    summary: dict[str, Any] = {}
    for key, value in arguments.items():
        if value is None:
            continue
        if isinstance(value, str):
            trimmed = value.strip()
            summary[key] = trimmed[:160] + ("…" if len(trimmed) > 160 else "")
            continue
        if isinstance(value, (int, float, bool)):
            summary[key] = value
            continue
        if isinstance(value, (list, tuple)):
            if len(value) <= 10:
                summary[key] = value
            else:
                summary[key] = {"count": len(value)}
            continue
        if isinstance(value, dict):
            keys = list(value.keys())
            summary[key] = {"keys": keys[:20], "count": len(keys)}
            continue
        summary[key] = str(value)
    return summary


def summarize_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    summary: dict[str, Any] = {}

    for key in ("count", "missing_location_count"):
        value = payload.get(key)
        if isinstance(value, (int, float, str, bool)):
            summary[key] = value

    geojson = payload.get("geojson")
    if isinstance(geojson, dict):
        features = geojson.get("features")
        if isinstance(features, list):
            summary["geojson_features"] = len(features)

    for list_key in ("campuses", "results", "comparison"):
        value = payload.get(list_key)
        if isinstance(value, list):
            summary[list_key] = len(value)

    table = payload.get("table")
    if isinstance(table, dict):
        rows = table.get("rows")
        if isinstance(rows, list):
            summary["table_rows"] = len(rows)

    response_trimmed = payload.get("response_trimmed")
    if isinstance(response_trimmed, dict):
        applied = response_trimmed.get("applied")
        if isinstance(applied, bool):
            summary["trimmed"] = applied

    pagination = payload.get("pagination")
    if isinstance(pagination, dict):
        has_more = pagination.get("has_more")
        if isinstance(has_more, bool):
            summary["has_more"] = has_more

    return summary
