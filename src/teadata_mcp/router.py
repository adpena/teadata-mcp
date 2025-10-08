"""High level request routing for the MCP server."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .data_engine_provider import DataEngineProvider, DataEngineLoadError
from .query_models import QueryResult, QueryResultStatus


@dataclass(slots=True)
class QueryRouter:
    """Translate structured tool calls into ``teadata`` operations."""

    engine_provider: DataEngineProvider

    def get_district(self, identifier: str) -> QueryResult:
        """Resolve a district by name or TEA number.

        Parameters
        ----------
        identifier:
            Arbitrary string provided by the user.  ``DataEngine`` performs the
            heavy lifting when normalising identifiers so the router simply
            forwards the value.
        """

        identifier = identifier.strip()
        if not identifier:
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message="Please supply a district name or number.",
            )

        try:
            engine = self.engine_provider.ensure_loaded()
        except DataEngineLoadError as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Unable to load data engine: {exc}",
            )

        district = self._safe_getattr(engine, "get_district", default=None)
        if district is None:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message="This version of teadata does not expose get_district().",
            )

        try:
            result = district(identifier)
        except Exception as exc:  # pragma: no cover - depends on third-party
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Data engine raised an exception: {exc}",
            )

        if result is None:
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=(
                    "No district matched the supplied identifier. The MCP server "
                    "intentionally refrains from guessing when data is missing."
                ),
            )

        summary = self._summarise_district(result)
        return QueryResult(
            status=QueryResultStatus.OK,
            message=f"Found district: {summary['name']}",
            payload=summary,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_getattr(obj: Any, attr: str, default: Any = None):
        method = getattr(obj, attr, None)
        if method is None:
            return default
        if not callable(method):
            return default
        return method

    @staticmethod
    def _summarise_district(district: Any) -> dict:
        """Extract a small, serialisable summary from the district object."""

        summary = {
            "name": getattr(district, "name", "<unknown>"),
            "district_number": getattr(district, "district_number", None),
        }
        for attr in ("rating", "overall_rating_2025", "enrollment"):
            if hasattr(district, attr):
                summary[attr] = getattr(district, attr)
        location = getattr(district, "coords", None) or getattr(district, "centroid", None)
        if location is not None:
            summary["location"] = location
        return summary
