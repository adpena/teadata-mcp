"""In-memory export store for table payloads."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import io
import json
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any, Dict, Iterable, List, Optional

EXPORT_URI_PREFIX = "teadata://export/"
MAX_EXPORTS = 50


@dataclass(slots=True)
class ExportEntry:
    export_id: str
    content: str
    mime_type: str
    filename: str
    created_at: float
    size_bytes: int


class ExportStore:
    """In-memory store for CSV/JSON exports."""

    def __init__(self, max_exports: int = MAX_EXPORTS) -> None:
        self._entries: "OrderedDict[str, ExportEntry]" = OrderedDict()
        self._max_exports = max_exports
        self._lock = threading.Lock()

    def register(
        self,
        *,
        content: str,
        mime_type: str,
        filename: str,
    ) -> ExportEntry:
        export_id = uuid.uuid4().hex
        entry = ExportEntry(
            export_id=export_id,
            content=content,
            mime_type=mime_type,
            filename=filename,
            created_at=time.time(),
            size_bytes=len(content.encode("utf-8")),
        )
        with self._lock:
            self._entries[export_id] = entry
            self._entries.move_to_end(export_id)
            while len(self._entries) > self._max_exports:
                self._entries.popitem(last=False)
        return entry

    def get(self, export_id: str) -> Optional[ExportEntry]:
        with self._lock:
            entry = self._entries.get(export_id)
            if entry is None:
                return None
            self._entries.move_to_end(export_id)
            return entry


_STORE = ExportStore()


def is_export_uri(uri: str) -> bool:
    return uri.startswith(EXPORT_URI_PREFIX)


def parse_export_uri(uri: str) -> Optional[str]:
    if not is_export_uri(uri):
        return None
    export_id = uri[len(EXPORT_URI_PREFIX) :]
    return export_id or None


def register_export(
    *,
    content: str,
    mime_type: str,
    filename: str,
    format_name: str,
    row_count: int,
) -> Dict[str, Any]:
    entry = _STORE.register(content=content, mime_type=mime_type, filename=filename)
    return {
        "format": format_name,
        "resource_uri": f"{EXPORT_URI_PREFIX}{entry.export_id}",
        "mime_type": entry.mime_type,
        "filename": entry.filename,
        "size_bytes": entry.size_bytes,
        "row_count": row_count,
    }


def read_export(uri: str) -> Optional[ExportEntry]:
    export_id = parse_export_uri(uri)
    if export_id is None:
        return None
    return _STORE.get(export_id)


def _cell_to_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (dict, list)):
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    return str(value)


def _rows_to_objects(
    columns: Iterable[str], rows: Iterable[Iterable[Any]]
) -> List[Dict[str, Any]]:
    keys = list(columns)
    objects = []
    for row in rows:
        row_values = list(row)
        objects.append(
            {
                key: row_values[index] if index < len(row_values) else None
                for index, key in enumerate(keys)
            }
        )
    return objects


def create_table_exports(
    table: Dict[str, Any],
    *,
    filename_prefix: str,
    max_preview_rows: int = 5,
) -> Dict[str, Any]:
    columns = [col.get("key") for col in table.get("columns", []) if col.get("key")]
    rows = list(table.get("rows") or [])
    if not columns or not rows:
        return {
            "exports": None,
            "preview_rows": [],
            "row_count": len(rows),
        }

    row_objects = _rows_to_objects(columns, rows)
    preview_rows = [
        {key: _json_safe(value) for key, value in row.items()}
        for row in row_objects[:max_preview_rows]
    ]

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell_to_string(value) for value in row])
    csv_content = csv_buffer.getvalue()

    json_rows = [
        {key: _json_safe(value) for key, value in row.items()} for row in row_objects
    ]
    json_content = json.dumps(json_rows, ensure_ascii=False)

    exports = {
        "csv": register_export(
            content=csv_content,
            mime_type="text/csv",
            filename=f"{filename_prefix}.csv",
            format_name="csv",
            row_count=len(rows),
        ),
        "json": register_export(
            content=json_content,
            mime_type="application/json",
            filename=f"{filename_prefix}.json",
            format_name="json",
            row_count=len(rows),
        ),
    }
    return {
        "exports": exports,
        "preview_rows": preview_rows,
        "row_count": len(rows),
    }
