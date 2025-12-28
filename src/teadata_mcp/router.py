"""High level request routing for the MCP server."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, List, Dict, Optional
from urllib.parse import urlencode, quote

from teadata.classes import inspect_object

from .data_engine_provider import DataEngineProvider, DataEngineLoadError
from .export_store import create_table_exports
from .query_models import QueryResult, QueryResultStatus
from .logic import (
    CampusSummary,
    build_summary,
    iter_campuses,
    find_campus,
    find_district,
    _format_distance_miles,
    _rating_score_from_text,
    campus_district_name,
    collect_staff_and_teacher_stats,
    collect_class_size_stats,
    collect_demographic_stats,
    extract_coordinates,
    extract_geometry,
    extract_location,
    extract_overall_rating_2025,
    extract_meta_fields,
)
from .tooling_guide import get_tooling_guide


@dataclass(slots=True)
class QueryRouter:
    """Translate structured tool calls into ``teadata`` operations."""

    engine_provider: DataEngineProvider
    _campus_cache: Optional[List[CampusSummary]] = field(default=None, init=False)

    def get_district(self, identifier: str, meta_fields: Optional[List[str]] = None) -> QueryResult:
        """Resolve a district by name or TEA number."""
        identifier = identifier.strip()
        if len(identifier) > 100:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message="Identifier too long (max 100 chars).",
            )
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

        district = find_district(engine, identifier)
        if district is None:
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=(
                    "No district matched the supplied identifier. The MCP server "
                    "intentionally refrains from guessing when data is missing."
                ),
            )

        summary = self._summarise_district(district)
        summary["do_not_web_search"] = True
        meta_fields = self._normalize_fields(meta_fields)
        if meta_fields:
            extra_meta = extract_meta_fields(district, meta_fields)
            if extra_meta:
                summary["meta"] = extra_meta
        return QueryResult(
            status=QueryResultStatus.OK,
            message=f"Found district: {summary['name']}",
            payload=summary,
        )

    def get_data_fields(self, entity_type: str, identifier: str) -> QueryResult:
        """Return a list of available meta keys for a campus or district."""
        entity_type = (entity_type or "").strip().lower()
        identifier = (identifier or "").strip()
        
        if entity_type not in ("campus", "district"):
             return QueryResult(
                status=QueryResultStatus.ERROR,
                message="Please choose entity_type 'campus' or 'district'.",
            )
        
        if not identifier:
             return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message="Please supply an identifier.",
            )

        try:
            engine = self.engine_provider.ensure_loaded()
        except DataEngineLoadError as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Unable to load data engine: {exc}",
            )

        if entity_type == "campus":
            entity = find_campus(engine, identifier)
        else:
            entity = find_district(engine, identifier)
            
        if entity is None:
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=f"{entity_type.title()} '{identifier}' not found.",
            )
            
        meta = getattr(entity, "meta", {}) or {}
        keys = sorted(list(meta.keys()))
        
        return QueryResult(
            status=QueryResultStatus.OK,
            message=f"Found {len(keys)} data fields for {getattr(entity, 'name', identifier)}.",
            payload={"entity_type": entity_type, "identifier": identifier, "fields": keys},
        )

    def search_campuses(
        self,
        query: str = "",
        status: str = "all",
        rating: str = "all",
        grade_level: str = "all",
        limit: int = 20,
        meta_fields: Optional[List[str]] = None,
        cursor: Optional[int] = None,
        include_total: bool = False,
    ) -> QueryResult:
        """Search for campuses by name, number, or district."""
        if len(query) > 100:
             return QueryResult(
                status=QueryResultStatus.ERROR,
                message="Search query too long (max 100 chars).",
            )
        try:
            engine = self.engine_provider.ensure_loaded()
        except DataEngineLoadError as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Unable to load data engine: {exc}",
            )

        # Populate cache if needed
        if self._campus_cache is None:
            self._campus_cache = []
            for campus in iter_campuses(engine):
                self._campus_cache.append(build_summary(campus))

        query = query.strip().lower()
        status = status.strip().lower()
        rating = rating.strip().upper()
        grade_level = grade_level.strip().upper()
        
        meta_fields = self._normalize_fields(meta_fields)
        cursor_value = self._normalize_cursor(cursor)
        include_total = bool(include_total)
        results = []
        matched_count = 0
        has_more = False

        for summary in self._campus_cache:
            # Status filter
            if status == "charter" and (not summary.charter or summary.is_private):
                continue
            if status in ("isd", "district") and (summary.charter or summary.is_private):
                continue
            if status == "private" and not summary.is_private:
                continue

            # Rating filter
            if rating != "ALL" and rating:
                # summary.rating is typically "A", "B", "C", "D", "F", or "Not Rated"
                # We do a simple prefix/exact match
                campus_rating = (summary.rating or "").upper()
                if rating == "NR" or rating == "NOT RATED":
                    if campus_rating not in ("NOT RATED", "NR", ""):
                        continue
                elif campus_rating != rating:
                    continue

            # Grade Level filter (simple text match in grade_range string)
            # summary.grade_range is like "EE-05", "09-12"
            if grade_level != "ALL" and grade_level:
                # Heuristic: "ELEMENTARY" matches if ends in 05 or starts with EE/PK and doesn't go to 12
                # But safer to just match user input against range string or basic logic
                r = (summary.grade_range or "").upper()
                if grade_level == "ELEMENTARY":
                    if "09" in r or "10" in r or "11" in r or "12" in r: continue
                elif grade_level == "MIDDLE":
                    if "06" not in r and "07" not in r and "08" not in r: continue
                elif grade_level == "HIGH":
                    if "09" not in r and "10" not in r and "11" not in r and "12" in r: continue
                # Allow exact match if user passes "09-12"
                elif grade_level not in r:
                     continue

            # Text query filter
            if query:
                text_match = (
                    query in summary.name_lower
                    or query in summary.campus_number_lower
                    or query in summary.district_name_lower
                )
                if not text_match:
                    continue

            matched_count += 1
            if matched_count <= cursor_value:
                continue
            if len(results) >= limit:
                has_more = True
                if not include_total:
                    break
                continue

            campus_data = summary.to_dict()
            # In the cached version, we rely on summary.rating which typically holds the overall rating.
            # We explicitly set this key for frontend compatibility if it expects it.
            campus_data["overall_rating_2025"] = summary.rating
            
            # If meta_fields are requested, we must fetch the live object.
            # This is a trade-off: fast search, slower meta extraction.
            if meta_fields:
                campus = find_campus(engine, summary.campus_number)
                if campus:
                    extra_meta = extract_meta_fields(campus, meta_fields)
                    if extra_meta:
                        campus_data["meta"] = extra_meta

            results.append(campus_data)

        total_matches = matched_count if include_total else None
        if include_total:
            has_more = (cursor_value + len(results)) < total_matches
        next_cursor = cursor_value + len(results) if has_more else None
        message = f"Found {len(results)} campuses."
        if next_cursor is not None:
            message += f" More available; next_cursor={next_cursor}."

        payload = {
            "do_not_web_search": True,
            "instructions": [
                "If pagination.next_cursor is present, call search_campuses again with cursor=next_cursor.",
                "If completeness.needs_follow_up is true, do not finalize results; follow next_tool_call.",
                "Use payload.table for deterministic table rendering and payload.exports for CSV/JSON export.",
            ],
            "pagination": {
                "cursor": cursor_value,
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": limit,
                "total_matches": total_matches,
            },
            "next_tool_call": (
                {
                    "tool": "search_campuses",
                    "arguments": {
                        "query": query,
                        "status": status,
                        "rating": rating,
                        "grade_level": grade_level,
                        "limit": limit,
                        "meta_fields": meta_fields or None,
                        "cursor": cursor_value + len(results),
                        "include_total": False,
                    },
                    "reason": "Fetch the next page of search results.",
                }
                if has_more
                else None
            ),
            "results": results,
            "query_summary": {
                "query": query,
                "status": status,
                "rating": rating,
                "grade_level": grade_level,
                "limit": limit,
                "cursor": cursor_value,
                "include_total": include_total,
            },
            "snapshot": self._snapshot_info(),
        }
        payload["completeness"] = self._build_completeness(
            returned_count=len(results),
            total_matches=total_matches,
            has_more=has_more,
            trimmed=False,
            missing_count=0,
        )

        columns = [
            ("name", "Campus"),
            ("district_name", "District"),
            ("campus_number", "Campus #"),
            ("overall_rating_2025", "2025 Overall Rating"),
        ]
        if meta_fields:
            columns.extend((field, field) for field in meta_fields)
        table = self._build_table(
            items=results,
            columns=columns,
            row_id_keys=["campus_number", "name"],
        )
        table["row_actions"] = self._campus_row_actions()
        export_info = create_table_exports(
            table, filename_prefix=f"search-campuses-{self._slugify(query or 'all')}"
        )
        table["exports"] = export_info["exports"]
        table["preview_rows"] = export_info["preview_rows"]
        payload["table"] = table
        payload["exports"] = export_info["exports"]
        payload["preview_rows"] = export_info["preview_rows"]

        return QueryResult(
            status=QueryResultStatus.OK,
            message=message,
            payload=payload,
        )

    def get_campus_detail(
        self,
        identifier: str,
        meta_fields: Optional[List[str]] = None,
    ) -> QueryResult:
        """Get detailed information about a specific campus."""
        try:
            engine = self.engine_provider.ensure_loaded()
        except DataEngineLoadError as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Unable to load data engine: {exc}",
            )

        campus = find_campus(engine, identifier)
        if campus is None:
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=f"Campus '{identifier}' not found.",
            )

        summary = build_summary(campus)
        detail = summary.to_dict()
        detail["overall_rating_2025"] = extract_overall_rating_2025(campus)
        meta_fields = self._normalize_fields(meta_fields)
        
        # Ported rich data from teadata-app
        detail["staffing"] = collect_staff_and_teacher_stats(campus)
        detail["class_sizes"] = collect_class_size_stats(campus)
        detail["demographics"] = collect_demographic_stats(campus)
        
        # Add geographic coordinates
        lat, lon = extract_coordinates(campus)
        detail["location"] = {"lat": lat, "lon": lon}
        
        # Add transfer data (simplified)
        try:
            transfers_out = []
            for to_campus, count, masked in engine.transfers_out(campus):
                if to_campus:
                    transfers_out.append({
                        "to_campus": getattr(to_campus, "name", "Unknown"),
                        "to_number": getattr(to_campus, "campus_number", ""),
                        "count": count,
                        "masked": masked,
                        "is_charter": getattr(to_campus, "is_charter", False)
                    })
            detail["transfers_out"] = transfers_out
        except Exception:
            detail["transfers_out"] = []

        if meta_fields:
            extra_meta = extract_meta_fields(campus, meta_fields)
            if extra_meta:
                detail["meta"] = extra_meta

        return QueryResult(
            status=QueryResultStatus.OK,
            message=f"Details for {summary.name}",
            payload=detail,
        )

    def get_district_detail(
        self,
        identifier: str,
        meta_fields: Optional[List[str]] = None,
        campus_meta_fields: Optional[List[str]] = None,
        limit: Optional[int] = 200,
        cursor: Optional[int] = None,
        include_total: bool = False,
    ) -> QueryResult:
        """Get detailed information about a district and its campuses."""
        try:
            engine = self.engine_provider.ensure_loaded()
        except DataEngineLoadError as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Unable to load data engine: {exc}",
            )

        district = find_district(engine, identifier)
        if district is None:
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=f"District '{identifier}' not found.",
            )

        summary = self._summarise_district(district)
        meta_fields = self._normalize_fields(meta_fields)
        campus_meta_fields = self._normalize_fields(campus_meta_fields)
        cursor_value = self._normalize_cursor(cursor)
        include_total = bool(include_total)
        if limit is None:
            limit = 200
        if limit < 0:
            limit = 0
        if meta_fields:
            extra_meta = extract_meta_fields(district, meta_fields)
            if extra_meta:
                summary["meta"] = extra_meta
        
        # List campuses in district
        campuses = []
        matched_count = 0
        has_more = False
        try:
            for campus in engine.campuses_in(district):
                matched_count += 1
                if limit and matched_count <= cursor_value:
                    continue
                if limit and len(campuses) >= limit:
                    has_more = True
                    if not include_total:
                        break
                    continue
                campus_summary = build_summary(campus).to_dict()
                if campus_meta_fields:
                    extra_meta = extract_meta_fields(campus, campus_meta_fields)
                    if extra_meta:
                        campus_summary["meta"] = extra_meta
                campuses.append(campus_summary)
        except Exception:
            pass
        
        summary["campuses"] = campuses
        total_matches = matched_count if include_total else None
        if include_total and limit:
            has_more = (cursor_value + len(campuses)) < total_matches
        summary["pagination"] = {
            "cursor": cursor_value,
            "next_cursor": cursor_value + len(campuses) if has_more else None,
            "has_more": has_more,
            "page_size": limit,
            "total_matches": total_matches,
        }
        summary["instructions"] = [
            "If pagination.next_cursor is present, call get_district_detail again with cursor=next_cursor.",
            "If completeness.needs_follow_up is true, do not finalize results; follow next_tool_call.",
            "Use payload.table for deterministic table rendering and payload.exports for CSV/JSON export.",
        ]
        summary["next_tool_call"] = (
            {
                "tool": "get_district_detail",
                "arguments": {
                    "identifier": identifier,
                    "meta_fields": meta_fields or None,
                    "campus_meta_fields": campus_meta_fields or None,
                    "limit": limit,
                    "cursor": cursor_value + len(campuses),
                    "include_total": False,
                },
                "reason": "Fetch the next page of district campuses.",
            }
            if has_more
            else None
        )
        summary["query_summary"] = {
            "identifier": identifier,
            "limit": limit,
            "cursor": cursor_value,
            "include_total": include_total,
            "campus_meta_fields": campus_meta_fields,
            "meta_fields": meta_fields,
        }
        summary["snapshot"] = self._snapshot_info()
        summary["completeness"] = self._build_completeness(
            returned_count=len(campuses),
            total_matches=total_matches,
            has_more=has_more,
            trimmed=False,
            missing_count=0,
        )

        columns = [
            ("name", "Campus"),
            ("district_name", "District"),
            ("campus_number", "Campus #"),
            ("overall_rating_2025", "2025 Overall Rating"),
        ]
        if campus_meta_fields:
            columns.extend((field, field) for field in campus_meta_fields)
        table = self._build_table(
            items=campuses,
            columns=columns,
            row_id_keys=["campus_number", "name"],
        )
        table["row_actions"] = self._campus_row_actions()
        export_info = create_table_exports(
            table,
            filename_prefix=f"district-campuses-{self._slugify(summary.get('name') or identifier)}",
        )
        table["exports"] = export_info["exports"]
        table["preview_rows"] = export_info["preview_rows"]
        summary["table"] = table
        summary["exports"] = export_info["exports"]
        summary["preview_rows"] = export_info["preview_rows"]
        
        return QueryResult(
            status=QueryResultStatus.OK,
            message=f"Details for {summary['name']}",
            payload=summary,
        )

    def get_entity_geometry(self, entity_type: str, identifier: str) -> QueryResult:
        """Return geometry/location for a campus or district if available."""
        entity_type = (entity_type or "").strip().lower()
        identifier = (identifier or "").strip()
        if entity_type not in ("campus", "district"):
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message="Please choose entity_type 'campus' or 'district'.",
            )
        if not identifier:
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message="Please supply a campus or district identifier.",
            )

        try:
            engine = self.engine_provider.ensure_loaded()
        except DataEngineLoadError as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Unable to load data engine: {exc}",
            )

        if entity_type == "campus":
            entity = find_campus(engine, identifier)
        else:
            entity = find_district(engine, identifier)
        if entity is None:
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=f"{entity_type.title()} '{identifier}' not found.",
            )

        geometry, geometry_source = extract_geometry(entity)
        lat, lon, location_source = extract_location(entity)
        geometry_fields: dict[str, str] = {}
        try:
            inspected = inspect_object(entity)
        except Exception:
            inspected = None
        if isinstance(inspected, dict):
            for key, value in inspected.items():
                key_lower = key.lower()
                if any(
                    token in key_lower
                    for token in (
                        "geom",
                        "boundary",
                        "polygon",
                        "point",
                        "location",
                        "coord",
                        "shape",
                        "centroid",
                    )
                ):
                    geometry_fields[key] = type(value).__name__
        payload = {
            "entity_type": entity_type,
            "identifier": identifier,
            "name": getattr(entity, "name", None),
            "geometry": geometry,
            "geometry_source": geometry_source,
            "location": {"lat": lat, "lon": lon} if lat is not None and lon is not None else None,
            "location_source": location_source,
        }
        if geometry_fields:
            payload["geometry_fields"] = geometry_fields

        if geometry is None and (lat is None or lon is None):
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=f"No geometry or location found for {entity_type} '{identifier}'.",
                payload=payload,
            )

        return QueryResult(
            status=QueryResultStatus.OK,
            message=f"Geometry for {entity_type} '{payload.get('name') or identifier}'.",
            payload=payload,
        )

    def get_tooling_guide(self, topic: str = "") -> QueryResult:
        """Return prompt-to-tool guidance for MCP clients."""
        guide = get_tooling_guide(topic)
        return QueryResult(
            status=QueryResultStatus.OK,
            message="Tooling guide entries available.",
            payload=guide,
        )

    def get_nearby_campuses(
        self,
        identifier: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_miles: float = 5.0,
        limit: int = 50,
        cursor: Optional[int] = None,
        include_total: bool = False,
    ) -> QueryResult:
        """Find campuses within a specific radius of a school or coordinate."""
        try:
            engine = self.engine_provider.ensure_loaded()
        except DataEngineLoadError as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Unable to load data engine: {exc}",
            )

        center_lat = latitude
        center_lon = longitude
        origin_name = "coordinates"

        if identifier:
            campus = find_campus(engine, identifier)
            if campus is None:
                return QueryResult(
                    status=QueryResultStatus.UNKNOWN,
                    message=f"Campus '{identifier}' not found.",
                )
            center_lat, center_lon = extract_coordinates(campus)
            origin_name = getattr(campus, "name", identifier)

        if center_lat is None or center_lon is None:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message="Could not determine location coordinates for search.",
            )

        if not hasattr(engine, "radius_campuses"):
             return QueryResult(
                status=QueryResultStatus.ERROR,
                message="Data engine does not support radius queries.",
            )

        try:
            # radius_campuses typically takes (lon, lat, radius) based on teadata conventions
            # We verified this in charter_public_rating_overlap.py: 
            # nearby = engine.radius_campuses(charter_coords[0], charter_coords[1], radius_miles)
            # where coords were (lon, lat)
            nearby = list(engine.radius_campuses(center_lon, center_lat, radius_miles))
        except Exception as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Radius search failed: {exc}",
            )

        cursor_value = self._normalize_cursor(cursor)
        include_total = bool(include_total)
        if limit < 0:
            limit = 0
        results = []
        for campus in nearby:
            summary = build_summary(campus).to_dict()
            lat, lon = extract_coordinates(campus)
            
            distance = None
            if lat is not None and lon is not None:
                distance = _format_distance_miles(center_lat, center_lon, lat, lon)
            
            summary["distance_miles"] = float(distance) if distance else None
            results.append(summary)

        # Sort by distance
        results.sort(key=lambda x: x.get("distance_miles") or 9999)
        total_matches = len(results) if include_total else None
        if cursor_value:
            results = results[cursor_value:]
        if limit:
            results = results[:limit]
        has_more = False
        if limit:
            total_for_paging = total_matches if include_total else None
            if total_for_paging is None:
                has_more = cursor_value + len(results) < len(nearby)
            else:
                has_more = (cursor_value + len(results)) < total_for_paging
        next_cursor = cursor_value + len(results) if has_more else None
        message = (
            f"Found {len(results)} campuses within {radius_miles} miles of {origin_name}."
        )
        if next_cursor is not None:
            message += f" More available; next_cursor={next_cursor}."

        payload = {
            "do_not_web_search": True,
            "instructions": [
                "If pagination.next_cursor is present, call get_nearby_campuses again with cursor=next_cursor.",
                "If completeness.needs_follow_up is true, do not finalize results; follow next_tool_call.",
                "Use payload.table for deterministic table rendering and payload.exports for CSV/JSON export.",
            ],
            "pagination": {
                "cursor": cursor_value,
                "next_cursor": next_cursor,
                "has_more": has_more,
                "page_size": limit,
                "total_matches": total_matches,
            },
            "next_tool_call": (
                {
                    "tool": "get_nearby_campuses",
                    "arguments": {
                        "identifier": identifier,
                        "latitude": latitude,
                        "longitude": longitude,
                        "radius_miles": radius_miles,
                        "limit": limit,
                        "cursor": cursor_value + len(results),
                        "include_total": False,
                    },
                    "reason": "Fetch the next page of nearby campuses.",
                }
                if has_more
                else None
            ),
            "origin": origin_name,
            "radius_miles": radius_miles,
            "results": results,
            "query_summary": {
                "identifier": identifier,
                "latitude": latitude,
                "longitude": longitude,
                "radius_miles": radius_miles,
                "limit": limit,
                "cursor": cursor_value,
                "include_total": include_total,
            },
            "snapshot": self._snapshot_info(),
        }
        payload["completeness"] = self._build_completeness(
            returned_count=len(results),
            total_matches=total_matches,
            has_more=has_more,
            trimmed=False,
            missing_count=0,
        )

        columns = [
            ("name", "Campus"),
            ("district_name", "District"),
            ("distance_miles", "Miles"),
            ("overall_rating_2025", "2025 Overall Rating"),
            ("campus_number", "Campus #"),
        ]
        table = self._build_table(
            items=results,
            columns=columns,
            row_id_keys=["campus_number", "name"],
        )
        table["row_actions"] = self._campus_row_actions()
        export_info = create_table_exports(
            table, filename_prefix=f"nearby-campuses-{self._slugify(origin_name)}"
        )
        table["exports"] = export_info["exports"]
        table["preview_rows"] = export_info["preview_rows"]
        payload["table"] = table
        payload["exports"] = export_info["exports"]
        payload["preview_rows"] = export_info["preview_rows"]

        return QueryResult(
            status=QueryResultStatus.OK,
            message=message,
            payload=payload,
        )

    def find_campuses_in_district_boundary(
        self,
        district_identifier: str,
        campus_query: str = "",
        status: str = "all",
        limit: int = 100,
        include_campus_geometry: bool = False,
        include_geojson: bool = True,
        boundary_delivery: str = "reference",
        response_profile: str = "map",
        campus_meta_fields: Optional[List[str]] = None,
        campus_list_format: str = "id_name",
        include_total: bool = False,
        cursor: Optional[int] = None,
        max_response_bytes: Optional[int] = None,
    ) -> QueryResult:
        """Find campuses that fall within a district's boundary geometry."""
        district_identifier = (district_identifier or "").strip()
        if not district_identifier:
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message="Please supply a district identifier.",
            )

        try:
            engine = self.engine_provider.ensure_loaded()
        except DataEngineLoadError as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Unable to load data engine: {exc}",
            )

        district = find_district(engine, district_identifier)
        if district is None:
            return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=f"District '{district_identifier}' not found.",
            )

        district_summary = self._summarise_district(district)
        polygon = getattr(district, "polygon", None) or getattr(district, "boundary", None)
        district_geometry, geometry_source = extract_geometry(district)
        if (
            polygon is None
            or not district_geometry
            or district_geometry.get("type") not in ("Polygon", "MultiPolygon")
        ):
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"District '{district_summary['name']}' does not expose boundary geometry.",
            )

        boundary_delivery = (boundary_delivery or "reference").strip().lower()
        if boundary_delivery not in ("inline", "reference", "none"):
            boundary_delivery = "reference"

        response_profile = (response_profile or "map").strip().lower()
        if response_profile not in ("map", "list", "both"):
            response_profile = "map"

        campus_list_format = (campus_list_format or "id_name").strip().lower()
        if campus_list_format not in ("full", "id", "id_name"):
            campus_list_format = "id_name"

        include_total = bool(include_total)
        campus_query = (campus_query or "").strip().lower()
        status = (status or "all").strip().lower()
        if limit is None or limit < 1:
            limit = 100

        campus_meta_fields = self._normalize_fields(campus_meta_fields)
        cursor_value = self._normalize_cursor(cursor)
        if max_response_bytes is None:
            max_bytes = self._normalize_max_bytes(
                self.engine_provider.config.max_response_bytes
            )
        else:
            max_bytes = self._normalize_max_bytes(max_response_bytes)
        max_bytes_argument = max_bytes if max_bytes is not None else 0
        include_geojson_output = include_geojson and response_profile in ("map", "both")
        include_campuses = response_profile in ("list", "both")
        if not include_geojson_output and not include_campuses:
            response_profile = "list"
            include_campuses = True

        results = []
        features = []
        missing_location = 0

        try:
            if status == "charter":
                if hasattr(engine, "charter_campuses_within"):
                    candidates = engine.charter_campuses_within(district)
                else:
                    candidates = self._campuses_within_boundary(
                        engine,
                        district,
                        predicate=lambda c: bool(getattr(c, "is_charter", False))
                        and not bool(getattr(c, "is_private", False)),
                    )
            elif status == "private":
                if hasattr(engine, "private_campuses_within"):
                    candidates = engine.private_campuses_within(district)
                else:
                    candidates = self._campuses_within_boundary(
                        engine,
                        district,
                        predicate=lambda c: bool(getattr(c, "is_private", False)),
                    )
            else:
                def predicate(campus):
                    if status in ("isd", "district"):
                        return not bool(getattr(campus, "is_charter", False)) and not bool(
                            getattr(campus, "is_private", False)
                        )
                    return True

                candidates = self._campuses_within_boundary(
                    engine,
                    district,
                    predicate=predicate,
                )
        except Exception as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Boundary search failed: {exc}",
            )

        candidates_list = list(candidates or [])
        candidates_list.sort(key=self._campus_sort_key)

        matched_index = 0
        returned_count = 0
        has_more = False
        for campus in candidates_list:
            summary = build_summary(campus)

            if campus_query:
                text_match = (
                    campus_query in summary.name_lower
                    or campus_query in summary.campus_number_lower
                    or campus_query in summary.district_name_lower
                    or campus_query in summary.charter_label_lower
                )
                if not text_match:
                    continue

            lat, lon = extract_coordinates(campus)
            if lat is None or lon is None:
                missing_location += 1
                continue

            matched_index += 1
            if matched_index <= cursor_value:
                continue
            if returned_count >= limit:
                has_more = True
                if not include_total:
                    break
                continue
            overall_rating_2025 = extract_overall_rating_2025(campus)
            need_meta = bool(campus_meta_fields) and (
                campus_list_format == "full" or include_geojson_output
            )
            campus_meta = (
                extract_meta_fields(campus, campus_meta_fields)
                if need_meta
                else None
            )
            campus_identifier = summary.campus_number or summary.name

            if include_campuses:
                if campus_list_format == "full":
                    campus_data = summary.to_dict()
                    campus_data["overall_rating_2025"] = overall_rating_2025
                    campus_data["location"] = {"lat": lat, "lon": lon}
                    if campus_meta:
                        campus_data["meta"] = campus_meta
                    if include_campus_geometry:
                        campus_geometry, campus_geometry_source = extract_geometry(campus)
                        if campus_geometry is not None:
                            campus_data["geometry"] = campus_geometry
                            campus_data["geometry_source"] = campus_geometry_source
                    results.append(campus_data)
                elif campus_list_format == "id":
                    results.append(campus_identifier)
                else:
                    results.append(
                        {
                            "campus_number": summary.campus_number,
                            "name": summary.name,
                        }
                    )

            if include_geojson_output:
                properties = {
                    "name": summary.name,
                    "campus_number": summary.campus_number,
                    "district_name": summary.district_name,
                    "charter": summary.charter,
                    "is_private": summary.is_private,
                    "rating": summary.rating,
                    "overall_rating_2025": overall_rating_2025,
                    "enrollment": summary.enrollment,
                }
                if campus_meta:
                    properties["meta"] = campus_meta
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                        "properties": properties,
                    }
                )
            returned_count += 1

        total_matches = matched_index if include_total else None
        if include_total:
            has_more = (cursor_value + returned_count) < (total_matches or 0)

        district_payload = {
            "name": district_summary.get("name"),
            "district_number": district_summary.get("district_number"),
            "geometry": district_geometry if boundary_delivery == "inline" else None,
            "geometry_source": geometry_source,
            "geometry_delivery": boundary_delivery,
            "geometry_bounds": self._geometry_bounds(polygon, district_geometry),
        }
        if boundary_delivery == "reference":
            district_payload["boundary_reference"] = self._census_boundary_reference(
                district_payload["name"] or district_identifier
            )

        filters_payload = {
            "campus_query": campus_query,
            "status": status,
            "limit": limit,
            "response_profile": response_profile,
            "include_geojson": include_geojson,
            "campus_list_format": campus_list_format,
            "include_total": include_total,
        }
        if campus_meta_fields:
            filters_payload["campus_meta_fields"] = campus_meta_fields
        filters_payload["max_response_bytes"] = max_bytes_argument

        trim_notes: list[str] = []

        def build_payload(
            current_results: list[dict],
            current_features: list[dict],
            boundary_delivery_value: str,
            has_more_value: bool,
            returned_count_value: int,
            total_matches_value: Optional[int],
            notes: list[str],
        ) -> dict:
            next_cursor = (
                cursor_value + returned_count_value if has_more_value else None
            )
            pagination_payload = {
                "cursor": cursor_value,
                "next_cursor": next_cursor,
                "has_more": has_more_value,
                "page_size": limit,
                "total_matches": total_matches_value,
            }
            instructions = []
            if boundary_delivery_value == "reference":
                instructions.append(
                    "Do not use web search for boundaries; use district.boundary_reference.download_url."
                )
            elif boundary_delivery_value == "inline":
                instructions.append(
                    "District boundary polygon included in district.geometry; geojson.features contain campus points."
                )
            if include_geojson_output:
                instructions.append(
                    "Use geojson.features (campus points) for markers; style markers by charter/is_private and overall_rating_2025."
                )
            else:
                instructions.append(
                    "GeoJSON campus points not included; re-run with response_profile='map' and include_geojson=true for markers."
                )
            instructions.append(
                "If pagination.next_cursor is present, call again with cursor=next_cursor for the next page."
            )
            if campus_meta_fields:
                instructions.append(
                    "Requested campus_meta_fields are returned under campuses[].meta and geojson.features[].properties.meta."
                )
            if include_campuses:
                if campus_list_format == "full":
                    instructions.append(
                        "Campuses list includes full summaries; use campus_number with get_campus_detail for deeper data."
                    )
                elif campus_list_format == "id":
                    instructions.append(
                        "Campuses list contains identifiers; call get_campus_detail(identifier=<campus_number_or_name>) for details."
                    )
                else:
                    instructions.append(
                        "Campuses list contains campus_number and name; call get_campus_detail(identifier=<campus_number>) to fetch full campus data (fallback to name if campus_number is empty)."
                    )
                if campus_meta_fields and campus_list_format != "full":
                    if include_geojson_output:
                        instructions.append(
                            "campus_meta_fields apply to GeoJSON properties; list entries are compact."
                        )
                    else:
                        instructions.append(
                            "campus_meta_fields requested but list entries are compact; re-run with campus_list_format='full' to include them in the list."
                        )
            if notes:
                instructions.append(
                    "Response trimmed to stay under max_response_bytes; see response_trimmed.notes."
                )
            instructions.append(
                "If completeness.needs_follow_up is true, do not finalize results; follow next_tool_call."
            )
            if include_campuses:
                instructions.append(
                    "Use payload.table for deterministic table rendering and payload.exports for CSV/JSON export."
                )

            payload = {
                "do_not_web_search": True,
                "instructions": instructions,
                "district": district_payload,
                "filters": filters_payload,
                "pagination": pagination_payload,
                "count": returned_count_value,
                "missing_location_count": missing_location,
                "map_instructions": instructions,
                "next_tool_call": None,
            }
            if include_campuses:
                payload["campuses"] = current_results

            if include_geojson_output:
                payload["geojson"] = {
                    "type": "FeatureCollection",
                    "features": current_features,
                }

            if has_more_value and next_cursor is not None:
                payload["next_tool_call"] = {
                    "tool": "find_campuses_in_district_boundary",
                    "arguments": {
                        "district_identifier": district_identifier,
                        "campus_query": campus_query,
                        "status": status,
                        "limit": limit,
                        "include_campus_geometry": include_campus_geometry,
                        "include_geojson": include_geojson,
                        "boundary_delivery": boundary_delivery_value,
                        "response_profile": response_profile,
                        "campus_meta_fields": campus_meta_fields or None,
                        "campus_list_format": campus_list_format,
                        "include_total": False,
                        "cursor": next_cursor,
                        "max_response_bytes": max_bytes_argument,
                    },
                    "reason": "Fetch the next page of campuses within the district boundary.",
                }

            if notes:
                payload["response_trimmed"] = {
                    "applied": True,
                    "max_response_bytes": max_bytes,
                    "notes": notes,
                }

            return payload

        if include_campuses:
            returned_count = len(results)
        else:
            returned_count = len(features)

        payload = build_payload(
            results,
            features,
            boundary_delivery,
            has_more,
            returned_count,
            total_matches,
            trim_notes,
        )

        if max_bytes is not None:
            payload_size = self._payload_size(payload)
            if payload_size > max_bytes and boundary_delivery == "inline":
                boundary_delivery = "reference"
                district_payload["geometry"] = None
                district_payload["geometry_delivery"] = boundary_delivery
                if "boundary_reference" not in district_payload:
                    district_payload["boundary_reference"] = self._census_boundary_reference(
                        district_payload["name"] or district_identifier
                    )
                trim_notes.append(
                    "Inline boundary geometry omitted to stay under max_response_bytes; use boundary_reference.download_url."
                )
                payload = build_payload(
                    results,
                    features,
                    boundary_delivery,
                    has_more,
                    returned_count,
                    total_matches,
                    trim_notes,
                )
                payload_size = self._payload_size(payload)

            if payload_size > max_bytes and (results or features):
                trim_notes.append(
                    "Results trimmed to stay under max_response_bytes; use pagination.next_cursor to fetch remaining results."
                )
                while payload_size > max_bytes and (results or features):
                    if include_campuses and results:
                        results.pop()
                    if include_geojson_output and features:
                        features.pop()
                    returned_count = len(results) if include_campuses else len(features)
                    has_more = True
                    payload = build_payload(
                        results,
                        features,
                        boundary_delivery,
                        has_more,
                        returned_count,
                        total_matches,
                        trim_notes,
                    )
                    payload_size = self._payload_size(payload)
                if returned_count == 0 and payload_size > max_bytes:
                    trim_notes.append(
                        "Payload still above max_response_bytes after trimming; consider raising max_response_bytes."
                    )
                    payload = build_payload(
                        results,
                        features,
                        boundary_delivery,
                        has_more,
                        returned_count,
                        total_matches,
                        trim_notes,
                    )

        payload["completeness"] = self._build_completeness(
            returned_count=returned_count,
            total_matches=total_matches,
            has_more=bool(payload.get("pagination", {}).get("has_more")),
            trimmed=bool(payload.get("response_trimmed", {}).get("applied")),
            missing_count=missing_location,
        )
        payload["query_summary"] = {
            "district_identifier": district_identifier,
            "campus_query": campus_query,
            "status": status,
            "limit": limit,
            "cursor": cursor_value,
            "include_total": include_total,
            "response_profile": response_profile,
            "campus_list_format": campus_list_format,
            "boundary_delivery": boundary_delivery,
            "include_geojson": include_geojson,
            "include_campus_geometry": include_campus_geometry,
            "campus_meta_fields": campus_meta_fields,
        }
        payload["snapshot"] = self._snapshot_info()

        if include_campuses:
            if campus_list_format == "id":
                columns = [("campus_number", "Campus #")]
            elif campus_list_format == "id_name":
                columns = [("campus_number", "Campus #"), ("name", "Campus")]
            else:
                columns = [
                    ("name", "Campus"),
                    ("district_name", "District"),
                    ("campus_number", "Campus #"),
                    ("overall_rating_2025", "2025 Overall Rating"),
                ]
                if campus_meta_fields:
                    columns.extend((field, field) for field in campus_meta_fields)
            table = self._build_table(
                items=payload.get("campuses", []),
                columns=columns,
                row_id_keys=["campus_number", "name"],
            )
            table["row_actions"] = self._campus_row_actions()
            export_info = create_table_exports(
                table,
                filename_prefix=f"boundary-campuses-{self._slugify(district_summary.get('name') or district_identifier)}",
            )
            table["exports"] = export_info["exports"]
            table["preview_rows"] = export_info["preview_rows"]
            payload["table"] = table
            payload["exports"] = export_info["exports"]
            payload["preview_rows"] = export_info["preview_rows"]

        message = (
            f"Returned {returned_count} campuses within {district_summary.get('name')} boundaries."
        )
        if total_matches is not None:
            message += f" Total matches: {total_matches}."
        if cursor_value:
            message += f" (cursor {cursor_value})"
        next_cursor = payload.get("pagination", {}).get("next_cursor")
        if next_cursor is not None:
            message += f" More available; next_cursor={next_cursor}."
        if missing_location:
            message += f" Skipped {missing_location} campuses without coordinates."
        if trim_notes:
            message += " Response trimmed to stay under max_response_bytes."

        return QueryResult(
            status=QueryResultStatus.OK,
            message=message,
            payload=payload,
        )

    def compare_campuses(
        self,
        identifiers: List[str],
        meta_fields: Optional[List[str]] = None,
    ) -> QueryResult:
        """Compare multiple campuses side-by-side."""
        if len(identifiers) < 2:
             return QueryResult(
                status=QueryResultStatus.ERROR,
                message="Please provide at least two campus identifiers to compare.",
            )

        try:
            engine = self.engine_provider.ensure_loaded()
        except DataEngineLoadError as exc:
            return QueryResult(
                status=QueryResultStatus.ERROR,
                message=f"Unable to load data engine: {exc}",
            )

        comparison_data = []
        meta_fields = self._normalize_fields(meta_fields)
        not_found = []

        for identifier in identifiers:
            campus = find_campus(engine, identifier)
            if campus is None:
                not_found.append(identifier)
                continue
            
            summary = build_summary(campus).to_dict()
            staffing = collect_staff_and_teacher_stats(campus)
            demographics = collect_demographic_stats(campus)
            
            # Flatten crucial metrics for easy comparison
            flat = {
                "name": summary["name"],
                "campus_number": summary["campus_number"],
                "rating": summary["rating"],
                "enrollment": summary["enrollment"],
                "avg_teacher_salary": staffing.get("avg_teacher_salary"),
                "student_teacher_ratio": staffing.get("student_teacher_ratio"),
                "percent_econ_disadv": demographics["programs_percent"].get("econ_disadv"),
                "percent_special_ed": demographics["programs_percent"].get("special_ed"),
            }
            if meta_fields:
                extra_meta = extract_meta_fields(campus, meta_fields)
                if extra_meta:
                    flat["meta"] = extra_meta
            comparison_data.append(flat)

        if not comparison_data:
             return QueryResult(
                status=QueryResultStatus.UNKNOWN,
                message=f"None of the requested campuses were found: {', '.join(not_found)}",
            )

        message = f"Compared {len(comparison_data)} campuses."
        if not_found:
            message += f" (Could not find: {', '.join(not_found)})"

        columns = [
            ("name", "Campus"),
            ("campus_number", "Campus #"),
            ("rating", "Rating"),
            ("enrollment", "Enrollment"),
            ("avg_teacher_salary", "Avg Teacher Salary"),
            ("student_teacher_ratio", "Student/Teacher Ratio"),
            ("percent_econ_disadv", "Percent Econ Disadv"),
            ("percent_special_ed", "Percent Special Ed"),
        ]
        if meta_fields:
            columns.extend((field, field) for field in meta_fields)
        table = self._build_table(
            items=comparison_data,
            columns=columns,
            row_id_keys=["campus_number", "name"],
        )
        table["row_actions"] = self._campus_row_actions()
        export_info = create_table_exports(
            table,
            filename_prefix=f"compare-campuses-{self._slugify('-'.join(identifiers))}",
        )
        table["exports"] = export_info["exports"]
        table["preview_rows"] = export_info["preview_rows"]

        payload = {
            "comparison": comparison_data,
            "query_summary": {"identifiers": identifiers, "meta_fields": meta_fields},
            "snapshot": self._snapshot_info(),
            "completeness": self._build_completeness(
                returned_count=len(comparison_data),
                total_matches=len(comparison_data),
                has_more=False,
                trimmed=False,
                missing_count=len(not_found),
            ),
            "table": table,
            "exports": export_info["exports"],
            "preview_rows": export_info["preview_rows"],
        }

        return QueryResult(
            status=QueryResultStatus.OK,
            message=message,
            payload=payload,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _geometry_bounds(polygon: Any, geojson: Optional[dict]) -> Optional[tuple[float, float, float, float]]:
        if polygon is not None and hasattr(polygon, "bounds"):
            try:
                bounds = tuple(float(v) for v in polygon.bounds)
                if len(bounds) == 4:
                    return bounds  # (minx, miny, maxx, maxy)
            except Exception:
                pass
        if not geojson:
            return None

        def iter_coords(coords):
            if not coords:
                return
            if isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
                yield coords[0], coords[1]
                return
            for item in coords:
                yield from iter_coords(item)

        coords = geojson.get("coordinates")
        if not coords:
            return None
        xs = []
        ys = []
        for x, y in iter_coords(coords):
            try:
                xs.append(float(x))
                ys.append(float(y))
            except Exception:
                continue
        if not xs or not ys:
            return None
        return (min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def _census_boundary_reference(district_name: str) -> dict:
        name = (district_name or "").strip().upper()
        if not name:
            return {}
        escaped_name = name.replace("'", "''")
        endpoint = (
            "https://tigerweb.geo.census.gov/arcgis/rest/services/"
            "TIGERweb/SchoolDistricts/MapServer/2/query"
        )
        where = f"STATE='48' AND NAME='{escaped_name}'"
        params = {
            "where": where,
            "outFields": "NAME,STATE,GEOID,LSAD",
            "outSR": "4326",
            "returnGeometry": "true",
            "f": "geojson",
        }
        download_url = f"{endpoint}?{urlencode(params, quote_via=quote)}"
        return {
            "source": "census_tigerweb",
            "layer": "Unified School Districts (MapServer/2)",
            "endpoint": endpoint,
            "params": params,
            "download_url": download_url,
            "how_to_use": (
                "Perform an HTTP GET to download_url to fetch GeoJSON; "
                "use features[0].geometry as the district boundary polygon."
            ),
            "notes": [
                "Use download_url to fetch GeoJSON directly from the Census TIGERweb service.",
                "If the NAME filter returns 0 features, try a LIKE clause (e.g., NAME LIKE '%AUSTIN%') or remove 'ISD'.",
                "Returned coordinates are in EPSG:4326 (lon/lat).",
                "If external download is not available, call this tool with boundary_delivery='inline' (may be large).",
            ],
        }

    @staticmethod
    def _campuses_within_boundary(engine: Any, district: Any, predicate) -> list[Any]:
        if predicate is None:
            predicate = lambda _campus: True
        if hasattr(engine, "_campuses_within_filtered"):
            try:
                return engine._campuses_within_filtered(
                    district,
                    predicate=predicate,
                    label="campuses_within",
                )
            except Exception:
                pass

        campuses = []
        contains = getattr(district, "__contains__", None)
        for campus in iter_campuses(engine):
            try:
                if not predicate(campus):
                    continue
            except Exception:
                continue
            try:
                inside = contains(campus) if callable(contains) else False
            except Exception:
                inside = False
            if inside:
                campuses.append(campus)
        return campuses

    def _snapshot_info(self) -> dict[str, Any]:
        config = self.engine_provider.config
        return {
            "load_snapshot": bool(config.load_snapshot),
            "snapshot_configured": bool(config.snapshot_path),
            "max_response_bytes": config.max_response_bytes,
        }

    @staticmethod
    def _build_completeness(
        *,
        returned_count: int,
        total_matches: Optional[int],
        has_more: bool,
        trimmed: bool,
        missing_count: int = 0,
    ) -> dict[str, Any]:
        needs_follow_up = bool(has_more or trimmed)
        return {
            "returned_count": returned_count,
            "total_matches": total_matches,
            "has_more": bool(has_more),
            "trimmed": bool(trimmed),
            "missing_count": int(missing_count or 0),
            "needs_follow_up": needs_follow_up,
        }

    @staticmethod
    def _slugify(text: str) -> str:
        if not text:
            return "export"
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
        return slug or "export"

    @staticmethod
    def _row_object(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return item
        if isinstance(item, str):
            return {"campus_number": item, "name": item}
        return {}

    @staticmethod
    def _row_value(item: dict[str, Any], key: str) -> Any:
        if key in item and item.get(key) is not None:
            return item.get(key)
        meta = item.get("meta")
        if isinstance(meta, dict) and meta.get(key) is not None:
            return meta.get(key)
        if key == "overall_rating_2025":
            return item.get("rating")
        return None

    @classmethod
    def _resolve_row_id(cls, item: dict[str, Any], keys: list[str]) -> str:
        for key in keys:
            value = cls._row_value(item, key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    @classmethod
    def _build_table(
        cls,
        *,
        items: list[Any],
        columns: list[tuple[str, str]],
        row_id_keys: list[str],
    ) -> dict[str, Any]:
        table_columns = [{"key": key, "label": label} for key, label in columns]
        table_rows = []
        row_ids = []
        for item in items:
            row_obj = cls._row_object(item)
            row_ids.append(cls._resolve_row_id(row_obj, row_id_keys))
            table_rows.append([cls._row_value(row_obj, key) for key, _ in columns])
        return {
            "columns": table_columns,
            "rows": table_rows,
            "row_ids": row_ids,
        }

    @staticmethod
    def _campus_row_actions() -> list[dict[str, Any]]:
        return []

    @staticmethod
    def _campus_sort_key(campus: Any) -> tuple[str, str]:
        campus_number = getattr(campus, "campus_number", "") or ""
        name = getattr(campus, "name", "") or ""
        return (str(campus_number).strip(), str(name).strip().lower())

    @staticmethod
    def _normalize_cursor(value: Any) -> int:
        try:
            cursor = int(value)
        except (TypeError, ValueError):
            return 0
        return max(cursor, 0)

    @staticmethod
    def _normalize_max_bytes(value: Any) -> Optional[int]:
        try:
            size = int(value)
        except (TypeError, ValueError):
            return None
        if size <= 0:
            return None
        return size

    @staticmethod
    def _payload_size(payload: dict) -> int:
        return len(json.dumps(payload, separators=(",", ":"), ensure_ascii=True))

    @staticmethod
    def _strip_district_feature(features: list[dict]) -> list[dict]:
        return [
            feature
            for feature in features
            if feature.get("properties", {}).get("kind") != "district"
        ]

    @staticmethod
    def _normalize_fields(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if isinstance(value, (list, tuple)):
            fields = []
            for item in value:
                if item is None:
                    continue
                text = str(item).strip()
                if text:
                    fields.append(text)
            return fields
        text = str(value).strip()
        return [text] if text else []

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
