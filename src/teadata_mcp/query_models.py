"""Shared data structures used by the routing layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class QueryResultStatus(str, Enum):
    """Categorical status for responses returned by the MCP server."""

    OK = "ok"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass(slots=True)
class QueryResult:
    """Normalized response returned to the host.

    Parameters
    ----------
    status:
        High level outcome of the request.  ``UNKNOWN`` is used when the server
        could not find a confident answer and is therefore declining to
        fabricate information.
    message:
        Human-readable explanation accompanying the status.  The tests lean on
        this message to verify that we fail-safe when data is missing.
    payload:
        Optional machine-readable content that downstream clients can use to
        render richer responses.
    """

    status: QueryResultStatus
    message: str
    payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result into a JSON-serialisable dictionary."""

        data = {
            "status": self.status.value,
            "message": self.message,
        }
        if self.payload is not None:
            data["payload"] = self.payload
        return data
